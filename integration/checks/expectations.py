"""Expected identity, payment, result and State shape for the Cashier demo (SPEC final v1)."""
from __future__ import annotations

import json
import re

__all__ = [
    "AGENT_ID", "AGENT_TYPE", "CRASH_EXIT_CODE", "EXPECTED_LEDGER_ROW",
    "EXPECTED_MATCHED_VERIFICATION", "EXPECTED_RECOVERED_RESULT",
    "EXPECTED_RECOVERED_RESULT_TEXT", "EXPECTED_SINGLE_ROW_LEDGER", "MAX_REQUEST_BODY_BYTES",
    "RUN_ID_PATTERN", "STATE_FIELD_NAMES", "TOOL_CALL_ID", "UNUSED_HEX_ID", "build_expected_request",
]

# These are the values the checks expect to OBSERVE. They are written out here on
# purpose instead of being imported from demo/ or backend/, so a wrong constant in
# the app cannot silently make its own check pass.

AGENT_TYPE, AGENT_ID, TOOL_CALL_ID = "demo.cashier.Cashier", "till-1", "call_pay_1"
EXPECTED_PAYMENT_ARGUMENTS = {"order_id": "A-1", "amount": 42}
EXPECTED_RECOVERED_RESULT = {"order_id": "A-1", "amount": 42, "status": "recorded"}
EXPECTED_RECOVERED_RESULT_TEXT = json.dumps(EXPECTED_RECOVERED_RESULT, ensure_ascii=False)
STATE_FIELD_NAMES = {"schema_version", "demo", "phase", "run_id", "agent", "request", "pending_calls",
              "ledger", "saved_result", "counts", "verification", "error"}
RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
UNUSED_HEX_ID = "0" * 32  # well-formed 32-hex id that no run or request uses
CRASH_EXIT_CODE = 17  # the crash worker's exit after the SQLite commit
EXPECTED_LEDGER_ROW = ("A-1", 42)  # the one payments row, as read back from SQLite
EXPECTED_SINGLE_ROW_LEDGER = {"rows": [{"order_id": "A-1", "amount": 42}], "count": 1}
EXPECTED_MATCHED_VERIFICATION = {"record": "matched", "fresh_inspection": True,
                                 "worker_exit_code": CRASH_EXIT_CODE}
MAX_REQUEST_BODY_BYTES = 4096  # SPEC: a larger POST body is rejected with 413


def build_expected_request(request_idea_id: str) -> dict:
    return {"request_idea_id": request_idea_id, "tool_call_id": TOOL_CALL_ID, "tool_name": "record_payment",
            "arguments": EXPECTED_PAYMENT_ARGUMENTS}
