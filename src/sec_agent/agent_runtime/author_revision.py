"""Resume the original expert; expose only its submitted artifact to other roles."""
from copy import deepcopy
import json

from langchain_core.messages import messages_from_dict

from .case_artifacts import CaseArtifacts
from .workpaper_review_graph import validate_workpaper_state


def restore_author_history(adapter, state, audit_paths):
    """Read the existing private audit, bound to the last accepted model receipt.

    Paths are host supplied within this task's audit directory. No browser or
    model path is accepted, no histories cross authors, and missing history
    stops before transport rather than silently constructing a new expert.
    """
    record = state["notebook"]["model_turn_records"][-1]
    receipt = record.get("runtime_receipt") or {}
    if not receipt.get("request_digest") or receipt.get("actor") != state["agent_id"]:
        raise ValueError("original_author_model_receipt_unavailable")
    for path in audit_paths:
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue  # An incomplete last write cannot match a receipt.
                if (event.get("actor") != state["agent_id"] or event.get("request_digest") != receipt.get("request_digest")
                        or not event.get("messages") or not event.get("raw_response")):
                    continue
                raw = event["raw_response"]
                calls = [*raw.get("tool_calls", []), *raw.get("invalid_tool_calls", [])]
                expected = record["action"].get("tool_calls", [])
                if expected and [c["id"] for c in calls] != [c["id"] for c in expected]:
                    raise ValueError("author_history_last_action_binding_mismatch")
                for actual, recorded in zip(calls, expected):
                    args = deepcopy(recorded.get("args"))
                    if isinstance(args, dict):
                        args.pop("context_digest", None)  # host-injected receipt binding
                    original_args = deepcopy(actual.get("args"))
                    if isinstance(original_args, dict):
                        original_args.pop("context_digest", None)
                    if actual.get("name") != recorded.get("name") or args != original_args:
                        raise ValueError("author_history_last_action_content_mismatch")
                adapter._agentic_history[state["agent_id"]] = messages_from_dict(
                    [{"type": m["type"], "data": m} for m in [*event["messages"], raw]])
                return
    raise ValueError("original_author_private_history_unavailable")


def native_revision_view(state, artifacts, paper_id, feedback):
    """Translate validated source identities, keeping existing aliases stable."""
    saved = validate_workpaper_state(state)
    fresh = CaseArtifacts([saved])
    paper = fresh.read_paper("P01")
    aliases, sources = {}, {}
    source_keys = ("passage_id", "evidence_id", "numeric_fact_id", "calculation_id", "fact_id")
    existing = {next(item[k] for k in source_keys if item.get(k)): ref
                for ref in artifacts.read_paper(paper_id, "sources")
                if (item := artifacts.source_item(ref)) and any(item.get(k) for k in source_keys)}
    for ref in fresh.read_paper("P01", "sources"):
        item = fresh.source_item(ref)
        canonical = next(item[k] for k in source_keys if item.get(k))
        alias = existing.get(canonical, canonical)
        aliases[ref] = alias
        if canonical not in existing:
            item.pop("operand_source_aliases", None)
            sources[alias] = item
    for claim in paper["claims"]:
        claim["source_ids"] = [aliases[r] for r in claim["source_ids"]]
        claim["citation_quotes"] = {aliases[r]: q for r, q in claim["citation_quotes"].items()}
    responses = (paper.get("task_note") or {}).get("finding_responses") or []
    ids = [r["finding_id"] for r in responses]
    if len(ids) != len(set(ids)) or set(ids) != {r["finding_id"] for r in feedback}:
        raise ValueError("native_author_revision_finding_response_scope_mismatch")
    return {"status": "revision_submitted", "paper_id": paper_id, "workpaper": paper,
        "sources": sources, "finding_responses": deepcopy(responses), "author_state": saved,
        "author_identity": {"agent_id": state["agent_id"], "task_id": state["task"]["task_id"],
            "lifetime_model_turns": state["notebook"]["model_turn_count"],
            "lifetime_tool_actions": state["notebook"]["tool_action_count"]}}


def author_feedback(findings, artifacts):
    """Review aliases are navigation; restore their actual source identity."""
    result = deepcopy(findings)
    for finding in result:
        for check in finding.get("source_checks", []):
            ref = check["source_id"]
            item = artifacts.source_item(ref)
            canonical = next(item[k] for k in ("passage_id", "evidence_id", "numeric_fact_id", "calculation_id", "fact_id") if item.get(k))
            check.update(source_id=canonical, review_source_alias=ref)
    return result


def current_author_state(artifacts, paper_id, revisions):
    state = (revisions.get(paper_id) or {}).get("author_state") or artifacts._author_states.get(paper_id)
    if not state:
        raise ValueError("original_author_state_unavailable")
    # Editorial changes must not be silently replaced by an older native draft.
    view = CaseArtifacts([state]).read_paper("P01")
    current = artifacts.with_revisions(revisions).read_paper(paper_id)
    for field in ("thesis", "mechanism", "narrative_markdown", "counterevidence", "what_would_change", "open_gaps"):
        if view.get(field) != current.get(field):
            raise ValueError("original_author_candidate_requires_editorial_reconciliation:" + field)
    return deepcopy(state)
