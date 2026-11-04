"use strict";
(function () {
  // ---------- policy constants ----------
  var REQUEST_TIMEOUT_MS = 60000; // a POST can need two 15 s children; never shorter than 45 s
  var RECOVERABLE_PHASES = { pending: true, recovered: true, unresolved: true };
  var EXPECTED_CRASH_EXIT_CODE = 17; // the demo worker's deliberate exit after the SQLite commit
  var UNKNOWN_TEXT = "unknown";      // shown for evidence the server reported as null
  var OPERATION = { RUNNING: "running", RECOVERING: "recovering", LOADING: "loading" };
  var CURRENT_STATE_PATH = "api/state";
  var RUNS_PATH = "api/runs";
  function runPath(runId) { return RUNS_PATH + "/" + runId; }
  function recoverPath(runId) { return runPath(runId) + "/recover"; }

  var consoleState = null;     // last console State received from the server (null until the first response)
  var activeOperation = null;  // null or an OPERATION value: the request now in flight
  var retainedNotice = null;   // explanation kept visible after a failed or uncertain request

  function getElementById(elementId) { return document.getElementById(elementId); }

  // ---------- DOM helpers (all server values are rendered as text) ----------
  function createElement(tagName, className, text) {
    var node = document.createElement(tagName);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }
  function formatJson(value) {
    try { return JSON.stringify(value, null, 2); } catch (err) { return String(value); }
  }
  // Saved result content is an exact string; pretty-print it only when it parses as JSON.
  function formatSavedContent(content) {
    if (typeof content !== "string") return formatJson(content);
    try { return JSON.stringify(JSON.parse(content), null, 2); } catch (err) { return content; }
  }
  function createDetailList(labelValuePairs) {
    var list = createElement("dl", "detail-list");
    labelValuePairs.forEach(function (pair) {
      list.appendChild(createElement("dt", null, pair[0]));
      list.appendChild(createElement("dd", null, pair[1]));
    });
    return list;
  }
  function createPlaceholder(text) { return createElement("p", "placeholder", text); }
  function createPill(text, tone) {
    return createElement("span", "pill" + (tone ? " " + tone : ""), text);
  }
  function isUnknown(value) { return value === null || value === undefined; }
  function createIdentifierBlock(labelValuePairs) {
    var block = createElement("div", "identifiers");
    labelValuePairs.forEach(function (pair) {
      block.appendChild(createElement("div", null, pair[0] + ": " + (isUnknown(pair[1]) ? UNKNOWN_TEXT : pair[1])));
    });
    return block;
  }
  // True before any run exists (the server's idle State) or before any State has arrived.
  function hasNoRun() { return !consoleState || consoleState.phase === "idle"; }
  function isConsoleState(body) {
    return body && typeof body === "object" && "phase" in body && "schema_version" in body;
  }

  // ---------- network ----------
  // Resolves to {status, body}; body is null when the response is not JSON. Rejects on transport failure.
  function requestJson(method, path) {
    var abortController = new AbortController();
    var timeoutId = setTimeout(function () { abortController.abort(); }, REQUEST_TIMEOUT_MS);
    var options = { method: method, signal: abortController.signal, cache: "no-store", headers: {} };
    if (method === "POST") {
      options.headers["Content-Type"] = "application/json";
      options.body = "{}";
    }
    // The timer also covers reading the body; finally clears it on success, fetch failure and body-read failure.
    return fetch(path, options).then(function (response) {
      return response.text().then(function (text) {
        var body = null;
        try { body = text ? JSON.parse(text) : null; } catch (err) { body = null; }
        return { status: response.status, body: body };
      });
    }).finally(function () {
      clearTimeout(timeoutId);
    });
  }

  // Store a State response; for an error-only body keep the old snapshot and retain a notice.
  // Returns the new State, or null when the body was not a State.
  function acceptResponse(result, operationLabel) {
    var body = result.body;
    if (isConsoleState(body)) {
      consoleState = body;
      return body;
    }
    var errorInfo = body && body.error;
    retainedNotice = {
      code: (errorInfo && errorInfo.code) || ("http_" + result.status),
      message: ((errorInfo && errorInfo.message) || "The server returned an unexpected response (HTTP " + result.status + ").") +
        " The previous snapshot is shown; the outcome of this " + operationLabel + " may be uncertain.",
    };
    return null;
  }

  function retainTransportNotice(err, operationLabel) {
    retainedNotice = {
      code: "transport_error",
      message: "Could not complete the " + operationLabel + " request (" + (err && err.message ? err.message : "network error") +
        "). The previous snapshot is shown; the outcome may be uncertain, so the current state was re-read.",
    };
  }

  // One GET after an uncertain POST or an error State. Never retries a POST.
  function reloadStateFrom(path) {
    return requestJson("GET", path).then(function (result) {
      if (isConsoleState(result.body)) consoleState = result.body; // the retained notice stays visible
    }, function () { /* leave the snapshot as is */ });
  }

  function loadInitialState() {
    activeOperation = OPERATION.LOADING;
    render();
    return requestJson("GET", CURRENT_STATE_PATH).then(function (result) {
      acceptResponse(result, "state");
    }, function (err) {
      retainTransportNotice(err, "state");
    }).then(function () {
      activeOperation = null;
      render();
    });
  }

  // action: "run" starts a new crash demo; "recover" recovers the currently shown run.
  function performAction(action) {
    if (activeOperation) return;
    var operationLabel, path;
    if (action === "run") {
      operationLabel = "crash demo"; path = RUNS_PATH; activeOperation = OPERATION.RUNNING;
    } else {
      if (!canRecover()) return;
      operationLabel = "recovery"; path = recoverPath(consoleState.run_id); activeOperation = OPERATION.RECOVERING;
    }
    retainedNotice = null;
    render();
    var needsReinspection = false;
    // New-run uncertainty re-reads the active run; recovery re-reads the run it targeted (captured now).
    var reinspectPath = action === "run" ? CURRENT_STATE_PATH : runPath(consoleState.run_id);
    requestJson("POST", path).then(function (result) {
      var newState = acceptResponse(result, operationLabel);
      if (!newState) { needsReinspection = true; return null; }
      // A State with an error (e.g. worker failure): keep its message, then do one GET.
      if (newState.phase === "error" && newState.run_id) {
        needsReinspection = true;
        if (action === "run") reinspectPath = runPath(newState.run_id); // the newly allocated run
      }
      return null;
    }, function (err) {
      needsReinspection = true;
      retainTransportNotice(err, operationLabel);
    }).then(function () {
      if (!needsReinspection) return null;
      var failedPostError = consoleState && consoleState.error;
      return reloadStateFrom(reinspectPath).then(function () {
        // The fresh GET may clear the State's error; keep the failed POST's explanation visible.
        if (failedPostError && !retainedNotice) {
          retainedNotice = { code: failedPostError.code, message: failedPostError.message, reason: failedPostError.reason };
        }
      });
    }).then(function () {
      activeOperation = null;
      render();
    });
  }

  // ---------- derived view ----------
  function canRecover() {
    return !activeOperation && consoleState && consoleState.run_id && consoleState.request &&
      RECOVERABLE_PHASES[consoleState.phase] === true;
  }

  // phase -> [badge text, badge tone, explanation]
  var PHASE_STATUS = {
    idle:       ["Idle", "", "No demo yet. Run the crash demo to start."],
    pending:    ["Interrupted", "warn", "The worker exited with code 17 after the database commit. The request is saved but has no result."],
    recovered:  ["Recovered", "ok", "Rumi saved the confirmed result and a fresh process found no pending calls."],
    unresolved: ["Unresolved", "warn", "The ledger evidence does not confirm the original request. Nothing was recorded."],
    unsupported:["Unsupported", "bad", "Rumi rejected the saved history. No repair was attempted."],
    error:      ["Error", "bad", "A step failed; completion is unknown. Nothing here claims success."],
  };

  // Returns [badge text, badge tone, explanation] for the current operation or phase.
  function currentStatus() {
    if (activeOperation === OPERATION.RUNNING)    return ["Working", "", "Creating record and interrupting worker…"];
    if (activeOperation === OPERATION.RECOVERING) return ["Working", "", "Checking SQLite and saving confirmed result…"];
    if (activeOperation === OPERATION.LOADING)    return ["Loading", "", "Loading current state…"];
    if (!consoleState)                            return ["Unavailable", "bad", "No state is available from the server."];
    return PHASE_STATUS[consoleState.phase] || [String(consoleState.phase), "", ""];
  }

  // ---------- rendering ----------
  function renderCounter(valueElementId, count) {
    var valueNode = getElementById(valueElementId);
    valueNode.textContent = isUnknown(count) ? UNKNOWN_TEXT : String(count);
    valueNode.className = isUnknown(count) ? "count-value unknown" : "count-value";
  }

  function renderRequestPanel(panelBody) {
    panelBody.textContent = "";
    var request = consoleState && consoleState.request;
    if (!request) { panelBody.appendChild(createPlaceholder("Nothing requested yet.")); return; }
    panelBody.appendChild(createElement("p", null, "The agent asked to call:"));
    panelBody.appendChild(createElement("div", "tool-name mono", request.tool_name));
    panelBody.appendChild(createElement("pre", null, formatJson(request.arguments)));
    panelBody.appendChild(createIdentifierBlock([["request_idea_id", request.request_idea_id], ["tool_call_id", request.tool_call_id]]));
    if (consoleState.agent) {
      panelBody.appendChild(createIdentifierBlock([["agent", consoleState.agent.type + " / " + consoleState.agent.id]]));
    }
  }

  function renderLedgerEvidencePanel(panelBody) {
    panelBody.textContent = "";
    if (hasNoRun()) {
      panelBody.appendChild(createPlaceholder("No tool has run yet."));
      return;
    }
    var verification = consoleState.verification || {};
    var exitCode = verification.worker_exit_code;
    panelBody.appendChild(createDetailList([
      ["Worker exit", isUnknown(exitCode) ? UNKNOWN_TEXT : String(exitCode) + (exitCode === EXPECTED_CRASH_EXIT_CODE ? " (died after commit)" : "")],
      ["Ledger check", verification.record || UNKNOWN_TEXT],
      ["Fresh inspection", verification.fresh_inspection ? "yes" : "no"],
    ]));
    var ledger = consoleState.ledger || {};
    if (isUnknown(ledger.rows)) {
      panelBody.appendChild(createPlaceholder("Ledger rows: unknown (database unreadable)."));
    } else if (ledger.rows.length === 0) {
      panelBody.appendChild(createPlaceholder("Ledger has 0 payment rows."));
    } else {
      var table = createElement("table"), headerRow = createElement("tr");
      ["order_id", "amount"].forEach(function (columnName) { headerRow.appendChild(createElement("th", null, columnName)); });
      table.appendChild(headerRow);
      ledger.rows.forEach(function (ledgerRow) {
        var tableRow = createElement("tr");
        tableRow.appendChild(createElement("td", "mono", String(ledgerRow.order_id)));
        tableRow.appendChild(createElement("td", "mono", String(ledgerRow.amount)));
        table.appendChild(tableRow);
      });
      panelBody.appendChild(table);
      panelBody.appendChild(createElement("p", "identifiers", "Committed rows in SQLite: " + (isUnknown(ledger.count) ? UNKNOWN_TEXT : ledger.count)));
    }
  }

  function renderSavedResultPanel(panelBody) {
    panelBody.textContent = "";
    if (hasNoRun()) {
      panelBody.appendChild(createPlaceholder("Nothing saved yet."));
      return;
    }
    var pendingCalls = consoleState.pending_calls;
    var pendingLine = createElement("p");
    if (isUnknown(pendingCalls)) {
      pendingLine.appendChild(createPill("pending calls unknown", "warn"));
    } else if (pendingCalls.length === 0) {
      pendingLine.appendChild(createPill("0 pending calls", "ok"));
    } else {
      pendingLine.appendChild(createPill(pendingCalls.length + " pending call" + (pendingCalls.length === 1 ? "" : "s"), "warn"));
    }
    panelBody.appendChild(pendingLine);
    if (!isUnknown(pendingCalls) && pendingCalls.length) {
      pendingCalls.forEach(function (pendingCall) {
        panelBody.appendChild(createPlaceholder("Waiting for a result for " + pendingCall.tool_name + "."));
      });
    }
    var savedResult = consoleState.saved_result;
    if (!savedResult) {
      panelBody.appendChild(createPlaceholder("No result saved for the original request."));
      return;
    }
    var resultLine = createElement("p");
    var isRecovered = savedResult.recovered === true; // the contract is a literal true
    resultLine.appendChild(createPill(isRecovered ? "recovered result" : "saved result", isRecovered ? "ok" : ""));
    panelBody.appendChild(resultLine);
    panelBody.appendChild(createElement("pre", null, formatSavedContent(savedResult.content)));
    panelBody.appendChild(createIdentifierBlock([
      ["result idea_id", savedResult.idea_id],
      ["request_idea_id", savedResult.request_idea_id],
      ["tool_call_id", savedResult.tool_call_id],
    ]));
  }

  // Shows the State's own error and any retained notice from a failed request.
  function renderErrorBox() {
    var errorBox = getElementById("error");
    errorBox.textContent = "";
    var messages = [];
    if (consoleState && consoleState.error) messages.push(consoleState.error);
    if (retainedNotice) messages.push(retainedNotice);
    if (!messages.length) { errorBox.hidden = true; return; }
    messages.forEach(function (errorInfo) {
      var messageLine = createElement("p");
      messageLine.appendChild(createElement("strong", null, errorInfo.message || "An error occurred."));
      errorBox.appendChild(messageLine);
      var metaText = [errorInfo.code, errorInfo.reason ? "reason: " + errorInfo.reason : null].filter(Boolean).join(" · ");
      if (metaText) errorBox.appendChild(createElement("p", "error-meta", metaText));
    });
    errorBox.hidden = false;
  }

  function render() {
    var status = currentStatus();
    var badge = getElementById("status-badge");
    badge.textContent = status[0];
    badge.className = "badge" + (status[1] ? " " + status[1] : "");
    getElementById("status-text").textContent = status[2];

    getElementById("btn-run").disabled = !!activeOperation;
    getElementById("btn-recover").disabled = !canRecover();
    getElementById("helper").textContent = (!activeOperation && consoleState && consoleState.phase === "recovered") ? "Safe to repeat" : "";

    var counts = consoleState
      ? (consoleState.counts || { records: 0, saved_results: 0, pending_calls: 0 })
      : { records: null, saved_results: null, pending_calls: null };
    renderCounter("c-records", counts.records);
    renderCounter("c-results", counts.saved_results);
    renderCounter("c-pending", counts.pending_calls);

    getElementById("run-id").textContent = consoleState && consoleState.run_id ? consoleState.run_id : "none";
    renderErrorBox();
    renderRequestPanel(getElementById("p-request"));
    renderLedgerEvidencePanel(getElementById("p-happened"));
    renderSavedResultPanel(getElementById("p-saved"));
  }

  getElementById("btn-run").addEventListener("click", function () { performAction("run"); });
  getElementById("btn-recover").addEventListener("click", function () { performAction("recover"); });
  loadInitialState();
})();
