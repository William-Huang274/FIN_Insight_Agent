"""Replay saved author batches and real request views without provider calls.

Original proposals, states, messages and receipts are immutable inputs. Output
contains diagnostic evidence only, never a replacement research/recovery state.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import messages_from_dict

from sec_agent.agent_runtime.period_relations import workpaper_period_checks
from sec_agent.agent_runtime.research_context_view import (
    working_view, public_operation, current_context, compact_current_context,
)
from sec_agent.agent_runtime.specialist_graph import (
    SaveWorkpaperEditsAction, SpecialistNotebook, _model_request,
)
from sec_agent.agent_runtime.workpaper_drafts import save_draft


def check_paths(value, path=""):
    """Inspect the complete message payload, including JSON tool envelopes."""
    if isinstance(value, str):
        try:
            return check_paths(json.loads(value), path + "<json>")
        except (ValueError, TypeError):
            return []
    if isinstance(value, list):
        return [p for i, item in enumerate(value) for p in check_paths(item, f"{path}/{i}")]
    if isinstance(value, dict):
        found = ([(path + "/period_relation_checks", len(value["period_relation_checks"]))]
                 if "period_relation_checks" in value else [])
        return found + [p for key, item in value.items() if key != "period_relation_checks"
                        for p in check_paths(item, path + "/" + key)]
    return []


def audit_request(response):
    messages = messages_from_dict([{"type": m["type"], "data": m} for m in response["messages"]])
    frozen = deepcopy(messages)
    projected = working_view(messages)
    snapshot = next(json.loads(m.content) for m in projected
                    if m.additional_kwargs.get("fin_research_working_view"))
    with patch("sec_agent.agent_runtime.period_relations.project_period_receipt",
               side_effect=deepcopy):
        unretired = working_view(messages)
    baseline = next(json.loads(m.content) for m in unretired
                    if m.additional_kwargs.get("fin_research_working_view"))
    assert snapshot["current_materials"] == baseline["current_materials"]
    assert snapshot["current_material_bindings"] == baseline["current_material_bindings"]
    expected = workpaper_period_checks(current_context(messages)["submission_to_repair"]["candidate"])
    assert snapshot["current_context"]["submission_to_repair"]["period_relation_checks"] == expected
    archived = []
    for message in messages:
        if message.type != "tool" or message.name != "SaveWorkpaperEditsAction":
            continue
        body = json.loads(message.content)
        result = body.get("result", body)
        original = public_operation(messages, message.tool_call_id)
        assert original["receipt"]["result"] == result
        archived.append(message.tool_call_id)
    for message in projected:
        if message.type == "tool" and message.name == "SaveWorkpaperEditsAction":
            assert not check_paths(message.content), "stale checks in native save envelope"
    # Projection must not touch model reasoning, proposals or tool-call pairing.
    original_ai = {m.id: m for m in messages if m.type == "ai" and m.id}
    for message in projected:
        if message.type == "ai" and message.id in original_ai:
            assert message.additional_kwargs == original_ai[message.id].additional_kwargs
    assert messages == frozen
    return {"call_id": response.get("call_id"),
            "before_check_paths": check_paths([m.model_dump() for m in messages]),
            "after_check_paths": check_paths([m.model_dump() for m in projected]),
            "current_check_count": len(expected), "archive_readbacks": archived,
            "materials": snapshot["current_materials"], "bindings": snapshot["current_material_bindings"]}


def requests_only(args):
    paths = [args.before, args.saved, *args.responses, *args.preserve]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    with patch("socket.socket.connect", side_effect=AssertionError("offline_network_forbidden")):
        views = [audit_request(json.loads(p.read_text(encoding="utf-8"))) for p in args.responses]
    assert all(v["materials"] == views[0]["materials"] and v["bindings"] == views[0]["bindings"]
               for v in views)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    result = {"provider_calls": 0, "original_file_hashes": hashes,
              "requests_replayed": len(views), "material_count": len(views[0]["materials"]),
              "material_bindings_preserved": True, "original_records_unchanged": True,
              "native_save_active_historical_checks": 0,
              "current_check_counts": [v["current_check_count"] for v in views],
              "financial_quality_pass": False}
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in (("result", result), ("request-observations", views)):
        (args.output / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False, indent=2),
                                                  encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


def main(args):
    paths = [args.before, args.saved, *args.responses]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before, saved, *responses = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    original = deepcopy((before, saved, responses))
    state = deepcopy(before)
    calls = [c for record in saved["notebook"]["model_turn_records"]
             for c in record["action"].get("tool_calls", [])
             if c["name"] == "SaveWorkpaperEditsAction"]
    replayed, views = [], []
    with patch("socket.socket.connect", side_effect=AssertionError("offline_network_forbidden")):
        for response in responses:
            audit_request(response)
            raw_calls = response["raw_response"]["tool_calls"]
            assert len(raw_calls) == 1 and raw_calls[0]["name"] == "SaveWorkpaperEditsAction"
            operation = raw_calls[0]["args"]["operation_id"]
            matches = [c for c in calls if c["args"].get("operation_id") == operation]
            assert len(matches) == 1
            call = matches[0]
            # Native bookkeeping supplies context_digest; all author edits and
            # reason_summary must be identical to the paid response.
            assert all(call["args"].get(k) == v for k, v in raw_calls[0]["args"].items())
            action = SaveWorkpaperEditsAction.model_validate_json(json.dumps(call["args"]))
            draft, receipt = save_draft(state, action)
            historical = saved["workpaper_draft"]["receipts"][operation]["receipt"]
            assert draft["digest"] == historical["draft_digest"]
            assert receipt["saved"] and not receipt["submitted"] and not receipt["accepted"]
            assert receipt["automatic_repairs"] == historical["automatic_repairs"]
            assert receipt.get("period_relation_checks", []) == []
            assert not workpaper_period_checks(draft["arguments"])
            state.update(workpaper_draft=draft, last_edit_feedback=receipt)
            replayed.append({"operation_id": operation, "receipt": receipt,
                "historical_checks": historical.get("period_relation_checks", []),
                "candidate_digest_unchanged": True})

            messages = messages_from_dict([{"type": m["type"], "data": m}
                                           for m in response["messages"]])
            frozen_messages = deepcopy(messages)
            view = working_view(messages)
            assert view is not None
            snapshot = next(json.loads(m.content) for m in view
                            if m.additional_kwargs.get("fin_research_working_view"))
            context = current_context(messages)
            candidate = context["submission_to_repair"]["candidate"]
            expected = workpaper_period_checks(candidate)
            assert snapshot["current_context"]["submission_to_repair"]["period_relation_checks"] == expected
            repair = snapshot["current_context"]["submission_to_repair"]
            assert "period_relation_checks" not in (repair.get("last_edit_feedback") or {})
            reads = []
            for message in messages:
                if message.type != "tool" or message.name != "SaveWorkpaperEditsAction":
                    continue
                body = json.loads(message.content)
                result = body.get("result", body)
                if not check_paths(result):
                    continue
                archived = public_operation(messages, message.tool_call_id)
                assert archived is not None
                assert archived["receipt"]["result"] == result
                reads.append(message.tool_call_id)
            assert messages == frozen_messages
            views.append({"call_id": response.get("call_id"), "current_check_count": len(expected),
                          "materials": snapshot["current_materials"],
                          "bindings": snapshot["current_material_bindings"],
                          "historical_receipts_readable": reads})

        assert state["workpaper_draft"]["arguments"] == saved["workpaper_draft"]["arguments"]
        assert state["workpaper_draft"]["digest"] == saved["workpaper_draft"]["digest"]
        assert state["notebook"]["observations"] == saved["notebook"]["observations"]
        # Resume projection of the original saved state, INCLUDING old warning
        # receipts. The runtime must refresh it without editing that state.
        request = _model_request(state=saved,
            notebook=SpecialistNotebook.model_validate_json(json.dumps(saved["notebook"])),
            allow_workpaper_field_edits=True, working_state_enabled=True, authoring_enabled=True)
        projected = compact_current_context(request)
        repair = projected["submission_to_repair"]
        assert not repair["period_relation_checks"]
        assert "period_relation_checks" not in (repair.get("last_edit_feedback") or {})
        assert "period_checks_at" not in projected["task_context"].get("revision_step", {})
        # Replacing stale parser observations may not change materials, their
        # binding or source-identity metadata across these save-only rounds.
        assert all(v["materials"] == views[0]["materials"] and v["bindings"] == views[0]["bindings"]
                   for v in views)
        # Request projection is deterministic, without state mutation.
        assert (before, saved, responses) == original
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in hashes.items())
    result = {
        "provider_calls": 0, "original_file_hashes": hashes,
        "saved_batches_replayed": len(replayed), "original_proposals_unchanged": True,
        "candidate_and_digest_unchanged": True, "original_materials_and_bindings_preserved": True,
        "current_material_count": len(views[0]["materials"]),
        "old_receipts_readable": True, "original_state_and_records_unchanged": True,
        "new_save_false_positive_counts": [len(r["receipt"].get("period_relation_checks", [])) for r in replayed],
        "real_request_current_check_counts": [v["current_check_count"] for v in views],
        "resume_current_check_count": len(repair["period_relation_checks"]),
        "submitted": False, "financial_quality_pass": False,
        "diagnostic_observations_injected": False,
    }
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in (("result", result), ("replayed-saves", replayed), ("request-observations", views)):
        (args.output / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False, indent=2),
                                                  encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("before", "saved", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--responses", type=Path, nargs="+", required=True)
    parser.add_argument("--requests-only", action="store_true",
                        help="Audit complete real requests without replaying saved/finalized proposals.")
    parser.add_argument("--preserve", type=Path, nargs="*", default=[],
                        help="Additional accepted-state files to hash-check in requests-only mode.")
    args = parser.parse_args()
    (requests_only if args.requests_only else main)(args)
