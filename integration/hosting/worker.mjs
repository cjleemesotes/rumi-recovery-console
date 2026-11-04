/** Public page and bounded API bridge; the VPC binding fixes the private target. */
const BASE_PATH = "/recovery-agent";
const MAX_BODY_BYTES = 4096;
const ORIGIN_TIMEOUT_MS = 55_000;
const RATE_LIMIT_RETRY_SECONDS = 60;
const STATIC_ASSETS = new Map([
  ["/", "/index.html"],
  ["/app.js", "/assets/js/console.js"],
  ["/styles.css", "/assets/css/console.css"],
]);

class PayloadTooLargeError extends Error {}

function errorResponse(status, code, message, extraHeaders = {}) {
  return Response.json({ error: { code, message } }, {
    status,
    headers: { "Cache-Control": "no-store", ...extraHeaders },
  });
}

function uncachedResponse(response) {
  const headers = new Headers(response.headers);
  headers.set("Cache-Control", "no-store");
  headers.set("X-Content-Type-Options", "nosniff");
  return new Response(response.body, {
    status: response.status, statusText: response.statusText, headers,
  });
}

async function readLimitedBody(request) {
  const declaredLength = Number(request.headers.get("Content-Length") || 0);
  if (declaredLength > MAX_BODY_BYTES) throw new PayloadTooLargeError();
  if (!request.body) return new Uint8Array();
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_BODY_BYTES) {
        await reader.cancel();
        throw new PayloadTooLargeError();
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const body = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

export async function handleRequest(request, env, fetchOrigin = fetch) {
  const url = new URL(request.url);
  if (url.pathname !== BASE_PATH && !url.pathname.startsWith(BASE_PATH + "/")) {
    // The route wildcard can catch a similar name; preserve that site's origin.
    return fetchOrigin(request);
  }
  if (url.protocol !== "https:") {
    url.protocol = "https:";
    return Response.redirect(url.href, 308);
  }
  if (url.pathname === BASE_PATH) {
    url.pathname += "/"; // relative asset/API URLs need the directory form
    return Response.redirect(url.href, 308);
  }

  const path = url.pathname.slice(BASE_PATH.length);
  const asset = STATIC_ASSETS.get(path);
  if (asset && (request.method === "GET" || request.method === "HEAD")) {
    const assetUrl = new URL(request.url);
    assetUrl.pathname = asset;
    return uncachedResponse(await env.ASSETS.fetch(new Request(assetUrl, {
      method: request.method,
    })));
  }
  if (!path.startsWith("/api/")) return errorResponse(404, "not_found", "Not found.");
  if (!["GET", "HEAD", "POST"].includes(request.method)) {
    return errorResponse(405, "method_not_allowed", "Method not allowed.", { Allow: "GET, HEAD, POST" });
  }
  if (request.method === "POST" && request.headers.has("Origin")
      && request.headers.get("Origin") !== url.origin) {
    return errorResponse(403, "invalid_origin", "Use the demo from this website.");
  }

  try {
    const client = request.headers.get("CF-Connecting-IP") || "unknown";
    const allowance = await env.API_RATE_LIMITER.limit({ key: client });
    if (!allowance.success) {
      return errorResponse(429, "rate_limited", "Too many demo requests. Wait a minute and refresh.", {
        "Retry-After": String(RATE_LIMIT_RETRY_SECONDS),
      });
    }
    const headers = new Headers({ Accept: "application/json" });
    const options = { method: request.method, headers, redirect: "manual", signal: AbortSignal.timeout(ORIGIN_TIMEOUT_MS) };
    if (request.method === "POST") {
      // Fixed-length bytes avoid chunked transfer, which the Python API refuses.
      options.body = await readLimitedBody(request);
      headers.set("Content-Type", request.headers.get("Content-Type") || "application/json");
      headers.set("Content-Length", String(options.body.byteLength));
    }
    const upstream = new Request("http://recovery-agent.internal" + path + url.search, options);
    return uncachedResponse(await env.RECOVERY_API.fetch(upstream));
  } catch (error) {
    if (error instanceof PayloadTooLargeError) {
      return errorResponse(413, "payload_too_large", "Request body too large.");
    }
    return errorResponse(503, "origin_unavailable",
      "The demo server is unavailable. Keep the host computer and hosting processes running, then refresh.");
  }
}

export default {
  // Cloudflare passes ExecutionContext as a third argument; keep it out of the handler's fetch seam.
  fetch: (request, env) => handleRequest(request, env),
};
