"""The importable Cashier agent shared by every demo phase.

Always imported as ``demo.cashier`` (never run as ``__main__``) so the agent's
qualified type, and with it the Tablet scope on disk, is ``demo.cashier.Cashier``
in every process.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from rumi import Dervish, HeartConfig, Voice, World, tool

from demo.runtime.contract import AGENT_ID, CRASH_ENV, CRASH_EXIT_CODE, LEDGER_ENV

__all__ = ["Cashier", "record_payment", "open_agent"]


class Cashier(Dervish):
    heart_config = HeartConfig(voices=[Voice(model_name="mock/cashier")])


@tool(["Cashier"])
def record_payment(order_id: str, amount: int) -> dict:
    """Record a payment in the ledger."""
    conn = sqlite3.connect(os.environ[LEDGER_ENV])
    try:
        conn.execute(
            "INSERT INTO payments (order_id, amount) VALUES (?, ?)", (order_id, amount)
        )
        conn.commit()
    finally:
        conn.close()
    if os.environ.get(CRASH_ENV) == "1":
        # The effect is committed. Die now: nothing for rumi to catch or save.
        os._exit(CRASH_EXIT_CODE)
    return {"order_id": order_id, "amount": amount, "status": "recorded"}


def open_agent(data_dir: str | Path) -> Cashier:
    """Construct the agent from storage, as any restarted process would."""
    world = World(openrouter_api_key="sk-test", data_dir=data_dir)
    return Cashier(world=world, agent_id=AGENT_ID)
