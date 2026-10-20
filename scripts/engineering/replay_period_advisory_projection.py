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
                if "period_relation_checks" not in result:
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
    main(parser.parse_args())
