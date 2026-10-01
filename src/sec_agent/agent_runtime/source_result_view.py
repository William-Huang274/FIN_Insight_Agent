"""Model-facing source cards; full parser/transport records stay in observations.

Normalize only structured source results. Never parse prose, truncate evidence,
limit candidates, or infer that two different periods/revisions are equivalent.
"""
import json
from collections.abc import Mapping


_SOURCE_STATES = {"retrieval_candidate", "source_bound_passage"}
_TRANSPORT_KEYS = {"mcp_receipt_chain", "mcp_receipt", "cell_binding_used", "source_tool_lane_receipt_id"}
# Implementation names are not source coverage. Keep revision explanations,
# acquisition URLs, parsing limitations, dates, hashes and unknown metadata.
_PARSER_IMPLEMENTATION_KEYS = {"parser", "material_card_version"}


def _metadata(value):
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            return value
        if not isinstance(decoded, dict):
            return value
        value = decoded
    if not isinstance(value, Mapping):
        return value
    row = {k: v for k, v in value.items() if k not in _PARSER_IMPLEMENTATION_KEYS | _TRANSPORT_KEYS}
    if "routing_metadata_v1" in row:
        routing = _metadata(row["routing_metadata_v1"])
        if isinstance(routing, dict):
            # Only exact copies disappear. Conflicts remain visible at their
            # original path; do not silently choose one period/identity.
            routing = {k: v for k, v in routing.items() if k not in row or row[k] != v}
        if routing != {}:
            row["routing_metadata_v1"] = routing
        else:
            row.pop("routing_metadata_v1")
    return row


def source_result_view(value):
    """Idempotent request-only projection shared by fresh and restored reads."""
    if isinstance(value, Mapping):
        row = {k: source_result_view(v) for k, v in value.items() if k not in _TRANSPORT_KEYS}
        if row.get("result_state") in _SOURCE_STATES and "metadata" in row:
            metadata = _metadata(row["metadata"])
            if isinstance(metadata, dict):
                # The public card already carries these values. URL/date
                # aliases are removed only when their values also match.
                aliases = {"origin_url": "url", "publication_date": "published_at"}
                metadata = {k: v for k, v in metadata.items()
                            if k not in row or row[k] != v}
                metadata = {k: v for k, v in metadata.items()
                            if aliases.get(k) not in row or row[aliases[k]] != v}
            if metadata != {}:
                row["metadata"] = metadata
            else:
                row.pop("metadata")
        return row
    if isinstance(value, (list, tuple)):
        return [source_result_view(v) for v in value]
    return value


def source_message_views(messages):
    """Reproject legacy saved messages as well as freshly assembled results."""
    from langchain_core.messages import HumanMessage, ToolMessage
    result = []
    changed = False
    for message in messages:
        view = message
        if isinstance(message, (HumanMessage, ToolMessage)) and isinstance(message.content, str):
            try:
                body = json.loads(message.content)
            except (ValueError, TypeError):
                body = None
            # User prose and unknown JSON contracts are not a tool result.
            if isinstance(body, dict) and ("progress" in body or (isinstance(message, ToolMessage) and "result" in body)):
                projected = source_result_view(body)
                if projected != body:
                    view = message.model_copy(update={"content": json.dumps(projected, ensure_ascii=False, separators=(",", ":"))})
                    changed = True
        result.append(view)
    return result if changed else messages
