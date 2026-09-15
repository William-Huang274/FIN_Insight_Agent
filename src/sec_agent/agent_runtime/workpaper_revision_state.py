"""Restore witnessed repair locations; author proposals never become source truth."""
from collections.abc import Mapping

import jsonpatch

from .research_graph_contracts import canonical_sha256


def revision_state(state):
    targets = dict(state.get("revision_targets", {}))
    origins = dict(state.get("revision_target_origins", {}))
    if state.get("revision_tracking_version") == 1:
        return {"revision_targets": targets, "revision_target_origins": origins, "revision_tracking_version": 1}
    candidate = (state.get("last_submission_attempt") or {}).get("arguments")
    if isinstance(candidate, Mapping):
        # A legacy notebook records the original actions, including rejected
        # atomic edits. Recover only old values still present in the candidate;
        # never parse malformed JSON, apply proposed corrections or infer prose.
        for turn in state.get("notebook", {}).get("model_turn_records", []):
            action = turn.get("action", {})
            calls = action.get("tool_calls", []) if action.get("action") == "native_tool_batch" else []
            scope = action.get("runtime_tool_scope")
            for call in calls:
                if (call.get("name") != "ReviseWorkpaperAction" or call.get("type", "tool_call") != "tool_call"
                    or scope is not None and call["name"] not in scope):
                    continue
                args = call.get("args")
                if not isinstance(args, Mapping):
                    continue
                edits = args.get("edits")
                if not isinstance(edits, (list, tuple)):
                    continue
                for edit in edits:
                    path = edit.get("path") if isinstance(edit, Mapping) else None
                    if not isinstance(path, str) or path in targets:
                        continue
                    try:
                        value = jsonpatch.JsonPointer(path).resolve(candidate)
                    except (jsonpatch.JsonPointerException, TypeError):
                        continue
                    old_key = "old_string" if edit.get("op") == "str_replace" else "old_value"
                    if old_key not in edit:
                        continue
                    old = edit[old_key]
                    matches = (bool(old) and value.count(old) == 1) if isinstance(old, str) and isinstance(value, str) else canonical_sha256(old) == canonical_sha256(value)
                    if matches:
                        targets[path] = canonical_sha256(value)
                        origins[path] = {"basis": "legacy_record_old_value_still_present",
                            "turn_index": turn.get("turn_index"), "tool_call_id": call.get("id"),
                            "old_value_digest": canonical_sha256(old),
                            "notice": "Recorded repair intent, not a verified financial correction. Proposed new text has not been applied."}
    return {"revision_targets": targets, "revision_target_origins": origins, "revision_tracking_version": 1}


def revision_progress(state, candidate):
    restored = revision_state(state)
    rows = []
    for path, digest in restored["revision_targets"].items():
        try:
            current = jsonpatch.JsonPointer(path).resolve(candidate)
            unchanged = canonical_sha256(current) == digest
            status = "unchanged_since_revision_requested" if unchanged else "changed_not_semantically_verified"
        except (jsonpatch.JsonPointerException, TypeError):
            status = "target_not_found"
        rows.append({"path": path, "status": status,
            "origin": restored["revision_target_origins"].get(path, {"basis": "recorded_edit_request"})})
    return rows


def revision_submission_issues(state, candidate):
    # An unchanged requested field cannot be discharged by writing a completion
    # note. Changes still require independent financial review. An author who
    # contests the repair can hand off to Lead with the actual disagreement.
    return [{"location": jsonpatch.JsonPointer(row["path"]).parts,
        "type": "requested_revision_not_applied", "path": row["path"],
        "message": "Requested repair location is unchanged in this candidate; a completed task note is not an applied edit.",
        "remedy": "Inspect this current field and use str_replace for the affected text; keep related claims and prose consistent. "
            "If the earlier repair intent was wrong, use RequestHumanReviewAction with the actual disagreement for Lead/reviewer resolution. "
            "Do not make cosmetic edits to satisfy this check."}
        for row in revision_progress(state, candidate) if row["status"] == "unchanged_since_revision_requested"]
