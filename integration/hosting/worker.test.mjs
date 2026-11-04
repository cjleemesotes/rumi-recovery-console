import test from "node:test";
import assert from "node:assert/strict";
import worker, { handleRequest } from "./worker.mjs";

const BASE = "https://mineai.net/recovery-agent";

function bindings() {
  const calls = [];
  return {
    calls,
    ASSETS: { fetch: async request => {
      calls.push({ type: "asset", request });
      return new Response("asset", { headers: { "Content-Type": "text/html" } });
    } },
    API_RATE_LIMITER: { limit: async () => ({ success: true }) },
    RECOVERY_API: { fetch: async request => {
      calls.push({ type: "api", request });
      return Response.json({ phase: "pending", counts: { records: 1, saved_results: 0, pending_calls: 1 } }, { status: 201 });
    } },
  };
}

test("canonical directory redirect retains the query", async () => {
  const response = await handleRequest(new Request(BASE + "?demo=1"), bindings());
  assert.equal(response.status, 308);
  assert.equal(response.headers.get("Location"), BASE + "/?demo=1");
});

test("HTTPS applies only to the requested mount", async () => {
  const response = await handleRequest(new Request("http://mineai.net/recovery-agent/"), bindings());
  assert.equal(response.headers.get("Location"), BASE + "/");
});

test("unrelated and similarly named paths preserve the original site", async () => {
  for (const path of ["/", "/other", "/recovery-agent-other"]) {
    const request = new Request("https://mineai.net" + path);
    const response = await handleRequest(request, bindings(), async seen => {
      assert.equal(seen, request);
      return new Response("original site");
    });
    assert.equal(await response.text(), "original site");
  }
});

test("the deployed entrypoint accepts Cloudflare's execution context", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response("original site");
  try {
    const response = await worker.fetch(new Request("https://mineai.net/recovery-agent-other"),
      bindings(), { waitUntil() {} });
    assert.equal(await response.text(), "original site");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("the three frontend URLs map to actual static assets", async () => {
  for (const [path, file] of [["/", "/index.html"], ["/app.js", "/assets/js/console.js"], ["/styles.css", "/assets/css/console.css"]]) {
    const env = bindings();
    const response = await handleRequest(new Request(BASE + path), env);
    assert.equal(env.calls.length, 1);
    assert.equal(new URL(env.calls[0].request.url).pathname, file);
    assert.equal(response.headers.get("Cache-Control"), "no-store");
  }
});

test("unknown assets and private project documents are never served", async () => {
  const env = bindings();
  for (const path of ["/CLAUDE.md", "/README.md", "/assets/secret", "/not-found"]) {
    assert.equal((await handleRequest(new Request(BASE + path), env)).status, 404);
  }
  assert.equal(env.calls.length, 0);
});

test("API mount is stripped, query retained and only fixed-length JSON forwarded", async () => {
  const env = bindings();
  const response = await handleRequest(new Request(BASE + "/api/runs?test=1", {
    method: "POST", body: "{}",
    headers: { Origin: "https://mineai.net", Cookie: "private=value", Authorization: "private", "Content-Type": "application/json" },
  }), env);
  const request = env.calls[0].request;
  assert.equal(request.url, "http://recovery-agent.internal/api/runs?test=1");
  assert.equal(request.headers.get("Content-Length"), "2");
  assert.equal(request.headers.get("Cookie"), null);
  assert.equal(request.headers.get("Authorization"), null);
  assert.equal(await request.text(), "{}");
  assert.equal(response.status, 201);
  assert.deepEqual((await response.json()).counts, { records: 1, saved_results: 0, pending_calls: 1 });
});

test("absent POST body remains empty", async () => {
  const env = bindings();
  await handleRequest(new Request(BASE + "/api/runs", { method: "POST" }), env);
  assert.equal(env.calls[0].request.headers.get("Content-Length"), "0");
});

test("both declared and streamed oversize bodies are refused before the origin", async () => {
  for (const request of [
    new Request(BASE + "/api/runs", { method: "POST", body: "{}", headers: { "Content-Length": "5000" } }),
    new Request(BASE + "/api/runs", { method: "POST", body: "x".repeat(4097) }),
  ]) {
    const env = bindings();
    assert.equal((await handleRequest(request, env)).status, 413);
    assert.equal(env.calls.length, 0);
  }
});

test("cross-site POST and rate-limited requests never reach the PC", async () => {
  const env = bindings();
  assert.equal((await handleRequest(new Request(BASE + "/api/runs", {
    method: "POST", body: "{}", headers: { Origin: "https://other.example" },
  }), env)).status, 403);
  env.API_RATE_LIMITER.limit = async () => ({ success: false });
  const response = await handleRequest(new Request(BASE + "/api/state"), env);
  assert.equal(response.status, 429);
  assert.equal(response.headers.get("Retry-After"), "60");
  assert.equal(env.calls.length, 0);
});

test("origin failure is explicit and no request is retried", async () => {
  const env = bindings();
  let attempts = 0;
  env.RECOVERY_API.fetch = async () => { attempts++; throw new Error("offline"); };
  const response = await handleRequest(new Request(BASE + "/api/state"), env);
  assert.equal(response.status, 503);
  assert.equal((await response.json()).error.code, "origin_unavailable");
  assert.equal(attempts, 1);
});

test("domain refusal responses remain JSON with the original status", async () => {
  const env = bindings();
  env.RECOVERY_API.fetch = async () => Response.json({ phase: "unresolved", error: { code: "record_absent" } }, { status: 409 });
  const response = await handleRequest(new Request(BASE + "/api/runs/" + "a".repeat(32) + "/recover", { method: "POST", body: "{}" }), env);
  assert.equal(response.status, 409);
  assert.equal((await response.json()).error.code, "record_absent");
});
