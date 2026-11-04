"""Locate and decode the original stored tool request in a Cashier's Rumi history."""
from __future__ import annotations

import json

from rumi.ideas.types import ToolRequestIdea, ToolResultIdea

from demo.runtime.contract import AGENT_TYPE, CALL_ID, TOOL_NAME, is_expected_arguments

__all__ = ["find_original_request", "results_after_request"]


def _parse_expected_payment_call(request_idea: ToolRequestIdea) -> dict | None:
    """Decode the stored request into the original_call dict, or None if it is not
    exactly the demo's single record_payment call."""
    tool_calls = request_idea.content
    if not isinstance(tool_calls, list) or len(tool_calls) != 1 or not isinstance(tool_calls[0], dict):
        return None
    call = tool_calls[0]
    function_spec = call.get("function") or {}
    if call.get("id") != CALL_ID or function_spec.get("name") != TOOL_NAME:
        return None
    try:
        args = json.loads(function_spec.get("arguments") or "{}")
    except (TypeError, ValueError):
        return None
    if not is_expected_arguments(args):
        return None
    return {"request_idea_id": request_idea.id, "tool_call_id": CALL_ID,
            "tool_name": TOOL_NAME, "arguments": args}


def find_original_request(agent, retained_request_idea_id):
    """Return (original_call, request_problem, request_index).

    original_call is the decoded call dict of the stored ToolRequestIdea (or None);
    request_index is that idea's position in the agent's history (-1 if not found).
    """
    ideas = agent.ideas
    tool_requests = [(history_index, idea) for history_index, idea in enumerate(ideas)
                     if isinstance(idea, ToolRequestIdea)]
    if agent.agent_type != AGENT_TYPE:
        return None, "demo_identity_mismatch", -1
    if retained_request_idea_id is not None:
        matching_requests = [(history_index, request_idea)
                             for history_index, request_idea in tool_requests
                             if request_idea.id == retained_request_idea_id]
        if not matching_requests:
            return None, "original_request_missing", -1
        request_index, request_idea = matching_requests[0]
    else:
        if not tool_requests:
            return None, "original_request_missing", -1
        if len(tool_requests) > 1:
            return None, "demo_identity_mismatch", -1
        request_index, request_idea = tool_requests[0]
    original_call = _parse_expected_payment_call(request_idea)
    if original_call is None:
        return None, "demo_identity_mismatch", -1
    return original_call, None, request_index


def results_after_request(agent, request_index: int) -> list:
    """Results contiguous right after the original request with its call id."""
    ideas = agent.ideas
    matching_results = []
    for idea in ideas[request_index + 1:]:
        if not isinstance(idea, ToolResultIdea) or idea.tool_call_id != CALL_ID:
            break
        try:
            parsed = json.loads(idea.content)
        except (TypeError, ValueError):
            parsed = None
        matching_results.append({
            "idea_id": idea.id, "request_idea_id": ideas[request_index].id,
            "tool_call_id": idea.tool_call_id, "tool_name": idea.name,
            "content": idea.content, "result": parsed,
            "recovered": (idea.metadata or {}).get("recovered") is True})
    return matching_results
