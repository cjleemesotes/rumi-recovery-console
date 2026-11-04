"""Read-only access to the payments ledger and classification of its evidence."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from demo.runtime.contract import LEDGER_READ_TIMEOUT_SECONDS, is_expected_arguments

__all__ = ["read_payments_ledger", "classify_demo_payment_evidence"]


def read_payments_ledger(path: Path) -> dict:
    """All rows, read-only; never creates the database."""
    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=LEDGER_READ_TIMEOUT_SECONDS)
        try:
            rows = conn.execute("SELECT order_id, amount FROM payments ORDER BY rowid").fetchall()
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as exc:
        return {"rows": None, "count": None, "error": f"{type(exc).__name__}: {exc}"}
    return {"rows": [{"order_id": r[0], "amount": r[1]} for r in rows], "count": len(rows),
            "error": None}


def classify_demo_payment_evidence(ledger: dict) -> str:
    """unreadable | absent | ambiguous | mismatched | matched, against the demo's expected payment."""
    if ledger["rows"] is None:
        return "unreadable"
    rows = ledger["rows"]
    if not rows:
        return "absent"
    if len(rows) > 1:
        return "ambiguous"
    return "matched" if is_expected_arguments(rows[0]) else "mismatched"
