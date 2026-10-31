"""Deterministic model surface over the native, unchanged conversation journal.

No financial summarization, second memory store, or age-based evidence eviction.
Only consumed navigation can become a saved-result index under pressure. Source
text, calculations, errors, unknown results and the latest tool batch survive.
Large identical provenance objects are stored once *in this request*, with exact
references. A new/recovered request rebuilds its own self-contained dictionary.
"""
from __future__ import annotations

import hashlib
import json

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.messages.utils import count_tokens_approximately

from .source_result_view import source_message_views


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _body(message):
    if not isinstance(message, ToolMessage) or message.status != "success" or not isinstance(message.content, str):
        return None
    try:
        value = json.loads(message.content)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _navigation(body):
    return (body.get("operation") in {"catalog", "outline", "search"}
            and body.get("read_only") is True and isinstance(body.get("items"), list)
            and "source_snapshot_sha256" in body
            and all(isinstance(item, dict) and item.get("result_state") == "retrieval_candidate"
                    for item in body["items"]))


def _archive_navigation(message, body):
    # Preserve every candidate, its identity and navigation parameters. Never
    # rank/select candidates here. Only original receipts can supply evidence.
    locator_keys = {"candidate_id", "title", "result_state", "fiscal_period", "publication_date"}
    index = {key: value for key, value in body.items()
             if key not in {"items", "shared_retrieval", "shared_organization_source"}}
    index["items"] = [{**{key: value for key, value in item.items() if key in locator_keys},
                       "original_json_pointer": item.get("original_json_pointer", f"/items/{position}")}
                      for position, item in enumerate(body["items"])]
    index["context_surface"] = {
        "kind": "consumed_navigation_index",
        "tool_call_id": message.tool_call_id,
        "readback": {"tool": "read_saved_result", "arguments": {"tool_call_id": message.tool_call_id}},
        "notice": "All candidates retained as locators, not evidence. Use read_saved_result with this tool_call_id and an item's original_json_pointer as json_pointer for the exact original item. Omit json_pointer for the full receipt and diagnostics; no new search is needed.",
    }
    return message.model_copy(update={"content": _json(index)})


def _intern_provenance(messages):
    """Exact, in-request references; never merge source periods or revisions."""
    result, known = [], {}
    from collections import Counter
    keys = {"organization_source", "original_source", "retrieval", "shared_retrieval",
            "shared_organization_source", "source_provenance", "source_locator"}
    notices = {"notice", "authority_note"}
    counts = Counter()

    def eligible(key, item):
        return ((key in keys and isinstance(item, dict) and len(_json(item)) >= 256)
                or (key in notices and isinstance(item, str) and len(item) >= 128))

    def envelope(body):
        return body is not None and (("source_snapshot_sha256" in body and isinstance(body.get("items"), list))
            or ("calculation_id" in body and isinstance(body.get("operands"), dict)))

    def count(value):
        if isinstance(value, list):
            for item in value: count(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if eligible(key, item): counts[_json(item)] += 1
                count(item)

    for message in messages:
        body = _body(message)
        if envelope(body): count(body)
    for message in messages:
        body = _body(message)
        # Restrict to known source envelopes, not arbitrary user/tool JSON.
        if not envelope(body):
            result.append(message)
            continue
        definitions = {}

        def visit(value):
            if isinstance(value, list):
                return [visit(item) for item in value]
            if not isinstance(value, dict):
                return value
            row = {}
            for key, item in value.items():
                serialized = _json(item)
                if eligible(key, item) and counts[serialized] > 1:
                    digest = hashlib.sha256(serialized.encode()).hexdigest()
                    ref = "provenance:" + digest
                    if ref not in known:
                        known[ref] = serialized
                        definitions[ref] = item
                    elif known[ref] != serialized:
                        raise ValueError("context_provenance_hash_conflict")
                    row[key] = {"context_ref": ref}
                else:
                    row[key] = visit(item)
            return row

        view = visit(body)
        if definitions:
            view["context_provenance"] = definitions
        result.append(message.model_copy(update={"content": _json(view)}) if view != body else message)
    return result


def expand_provenance(messages):
    """Losslessly resolve our own request references (also used by replay)."""
    definitions = {}
    for message in messages:
        body = _body(message)
        if body is not None:
            definitions.update(body.get("context_provenance", {}))

    def expand(value):
        if isinstance(value, list):
            return [expand(item) for item in value]
        if isinstance(value, dict):
            if set(value) == {"context_ref"}:
                return definitions[value["context_ref"]]
            return {key: expand(item) for key, item in value.items() if key != "context_provenance"}
        return value

    result = []
    for message in messages:
        body = _body(message)
        if body is not None and definitions:
            expanded = expand(body)
            if expanded != body:
                message = message.model_copy(update={"content": _json(expanded)})
        result.append(message)
    return result


def continuous_surface(messages, *, trigger_tokens, saved_result_reader):
    """Use pressure to retire consumed navigation, never last-N source reads.

    The token estimate controls an optional view optimization, not admission or
    billing. The audited provider request keeps its independent hard ceiling.
    Caller must start from native messages / an accepted summary plus suffix.
    """
    from .model_context import deduplicate_read_results

    base = source_message_views(expand_provenance(messages))
    exact = deduplicate_read_results(_intern_provenance(base))
    if trigger_tokens is None or count_tokens_approximately(exact) < trigger_tokens or not saved_result_reader:
        return exact
    last_assistant = max((i for i, m in enumerate(base) if isinstance(m, AIMessage)), default=-1)
    # Archive before factoring: a reference may never point to a definition
    # which this projection just removed with an old navigation receipt.
    projected = []
    for i, message in enumerate(base):
        body = _body(message)
        if i < last_assistant and body is not None and _navigation(body):
            message = _archive_navigation(message, body)
        projected.append(message)
    return deduplicate_read_results(_intern_provenance(projected))


def prefix_fingerprint(messages):
    """Detect edited interiors as well as changed first/last message IDs."""
    return hashlib.sha256(_json([m.model_dump(mode="json") for m in messages]).encode()).hexdigest()


def saved_evidence_index(messages):
    """Exact IDs and original receipt readers, not extracted research claims."""
    rows = []
    for message in messages:
        body = _body(message)
        if body is None:
            continue
        ids, locations = set(), []

        def visit(value, pointer=""):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"passage_id", "calculation_id", "numeric_fact_id"} and isinstance(item, str) and item:
                        ids.add(item)
                        locations.append({"id": item, "json_pointer": pointer})
                    else:
                        visit(item, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    visit(item, pointer + "/" + str(i))

        visit(body)
        if ids:
            rows.append({"ids": sorted(ids), "tool_call_id": message.tool_call_id,
                         "read_tool": "read_saved_result", "locations": locations})
    return rows
