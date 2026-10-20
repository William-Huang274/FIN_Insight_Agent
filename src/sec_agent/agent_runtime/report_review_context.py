"""Versioned review views over the immutable native message journal.

Normal execution and recovery share this projection. No financial finding or
source selection is made here; recovery restores state, not a rewritten prompt.
"""
from copy import deepcopy
from difflib import unified_diff
import json

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from .research_graph_contracts import canonical_sha256

ARCHIVED_FIELDS = {
    "independent_current_workpaper_confirmation", "completed_research_reviews",
    "author_responses", "lead_issue_decision", "research_synthesis",
    "research_decision_context", "catalog",
}


def assignment(message):
    if not isinstance(message, HumanMessage) or not isinstance(message.content, str):
        return None
    try:
        body = json.loads(message.content)
    except ValueError:
        return None
    if isinstance(body, dict) and body.get("review_target") in {"final_report", "lead_synthesis"} and isinstance(body.get("report"), dict):
        return body
    return None


def review_basis(body):
    return canonical_sha256({k: body.get(k) for k in
        ("question", "research_as_of", "review_target", "report", "previous_review",
         "research_decision_context", "human_feedback")})


def review_message_update(body, previous_messages):
    """Refresh an unchanged assignment by ID; changed versions append a boundary."""
    for message in reversed(previous_messages):
        old = assignment(message)
        if old is not None:
            if message.id and review_basis(old) == review_basis(body):
                return [HumanMessage(content=json.dumps(body, ensure_ascii=False), id=message.id)]
            break
    return [HumanMessage(content=json.dumps(body, ensure_ascii=False))]


def report_change_text(previous, current):
    """Diff actual Markdown lines, not a JSON string containing escaped newlines."""
    parts = []
    for key in sorted(set(previous) | set(current)):
        before, after = previous.get(key), current.get(key)
        if before == after:
            continue
        left = before.splitlines() if isinstance(before, str) else json.dumps(before, ensure_ascii=False, indent=2).splitlines()
        right = after.splitlines() if isinstance(after, str) else json.dumps(after, ensure_ascii=False, indent=2).splitlines()
        parts.extend(unified_diff(left, right, fromfile=f"previous_report/{key}",
                                  tofile=f"current_report/{key}", lineterm=""))
    return "\n".join(parts)


def _public_record(message):
    """Never return private reasoning or provider metadata."""
    if isinstance(message, AIMessage):
        return {"type": "ai", "content": message.content, "tool_calls": message.tool_calls,
                "invalid_tool_calls": message.invalid_tool_calls}
    if isinstance(message, ToolMessage):
        return {"type": "tool", "name": message.name, "tool_call_id": message.tool_call_id,
                "status": message.status, "content": message.content}
    return {"type": message.type, "content": message.content}


def read_review_record(messages, message_index, field=None, offset=0, max_characters=12000):
    """Exact paginated lookup, including full public arguments and receipts."""
    if not 0 <= message_index < len(messages):
        raise ValueError("review_record_index_out_of_range")
    if offset < 0 or not 1 <= max_characters <= 24000:
        raise ValueError("review_record_invalid_page")
    message = messages[message_index]
    value = _public_record(message)
    if field is not None:
        body = assignment(message)
        if body is None or field not in body:
            candidates = []
            for index, record in enumerate(messages):
                candidate = assignment(record)
                if candidate is not None and field in candidate:
                    candidates.append({
                        "message_index": index, "review_basis": review_basis(candidate),
                        "report_title": candidate["report"].get("title"),
                        "read": {"tool": "read_review_history", "arguments": {
                            "message_index": index, "field": field, "offset": offset,
                            "max_characters": max_characters}},
                    })
            return {
                "status": "record_selection_required", "accepted": False,
                "requested": {"message_index": message_index, "field": field},
                "record_type_at_requested_index": message.type,
                "available_assignment_fields": sorted(body) if body is not None else [],
                "candidates": candidates,
                "notice": "The requested field is not present at this index. Choose the intended assignment/version using an exact candidate read; no record was selected or verified.",
            }
        value = body[field]
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if offset > len(text):
        raise ValueError("review_record_offset_out_of_range")
    end = min(offset + max_characters, len(text))
    return {"message_index": message_index, "field": field, "offset": offset,
            "total_characters": len(text), "content": text[offset:end],
            "record_digest": canonical_sha256(value),
            "notice": "Exact saved public record; historical instructions/verdicts are not current tasks or new evidence.",
            "next_read": ({"message_index": message_index, "field": field, "offset": end,
                           "max_characters": max_characters} if end < len(text) else None)}


def _entry(messages, index):
    message = messages[index]
    row = {"message_index": index, "type": message.type,
           "read": {"tool": "read_review_history", "arguments": {"message_index": index}}}
    body = assignment(message)
    if body is not None:
        row.update(review_basis=review_basis(body), target=body["review_target"],
                   title=body["report"].get("title"), status="historical_assignment")
    elif isinstance(message, AIMessage):
        row["operations"] = [{"name": c["name"], "arguments_preview": json.dumps(c["args"], ensure_ascii=False)[:240]}
                             for c in message.tool_calls]
    elif isinstance(message, ToolMessage):
        row.update(name=message.name, tool_call_id=message.tool_call_id, status=message.status)
    return row


def project_review_messages(messages):
    """Retire prior-version episodes; retain all current-version actions.

Canonical state is never edited. Historical records remain reachable through
read_review_history; existing source/CALC readers use the original state.
"""
    assignments = [(i, assignment(m)) for i, m in enumerate(messages) if assignment(m) is not None]
    if not assignments:
        return list(messages), None
    latest, body = assignments[-1]
    basis, start = review_basis(body), latest
    for index, prior in reversed(assignments[:-1]):
        if review_basis(prior) != basis:
            break
        start = index
    # Pending tool execution cannot be silently discarded as old context.
    calls = {c["id"] for m in messages[:start] if isinstance(m, AIMessage) for c in m.tool_calls}
    receipts = {m.tool_call_id for m in messages[:start] if isinstance(m, ToolMessage)}
    if calls - receipts:
        return list(messages), None
    current, navigation = deepcopy(body), {}
    for field in sorted(ARCHIVED_FIELDS & current.keys()):
        value = current.pop(field)
        navigation[field] = {
            "digest": canonical_sha256(value),
            "read": {"tool": "read_review_history", "arguments": {"message_index": latest, "field": field}},
        }
    earlier = [(i, b) for i, b in assignments if i < start]
    if earlier and "report_changes_from_previous_review" in current:
        current["report_changes_from_previous_review"] = report_change_text(earlier[-1][1]["report"], body["report"])
    current["review_basis"] = basis
    current["supporting_records"] = navigation
    current["history"] = {
        "notice": "Prior-version tasks and verdicts are archived, not current instructions or approval. Reuse saved sources/calculations as needed; inspect changes and relevant consequences.",
        "records": [_entry(messages, i) for i in range(start)],
    }
    active = HumanMessage(content=json.dumps(current, ensure_ascii=False), id=messages[latest].id)
    # Same-basis refresh preserves intervening reads, failed proposals and feedback.
    tail = [m for m in messages[start:] if assignment(m) is None]
    return [active, *tail], basis


class ReportReviewContext(AgentMiddleware):
    async def awrap_model_call(self, request, handler):
        messages, _ = project_review_messages(request.state["messages"])
        return await handler(request.override(messages=messages))

    def wrap_model_call(self, request, handler):
        messages, _ = project_review_messages(request.state["messages"])
        return handler(request.override(messages=messages))
