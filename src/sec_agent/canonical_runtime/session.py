from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


BASE_CONTRACT_REF = (
    "configs/research/"
    "fin_ia_0_1_3_agent_runtime_reflection_context_continuity_contract_v1_0.json"
)
SUCCESSOR_CONTRACT_REF = (
    "configs/research/"
    "fin_ia_0_1_3_agent_runtime_reflection_context_continuity_contract_v1_1.json"
)


class CanonicalRuntimeError(ValueError):
    """Raised when durable runtime state cannot be trusted or resumed."""


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CanonicalRuntimeError(code)


def _nonempty(value: object, code: str) -> str:
    text = str(value or "").strip()
    _require(bool(text), code)
    return text


def _iso_datetime(value: object, code: str) -> str:
    text = _nonempty(value, code)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CanonicalRuntimeError(code) from exc
    return text


def _iso_date(value: object, code: str) -> str:
    text = _nonempty(value, code)
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise CanonicalRuntimeError(code) from exc
    return text


def _refs(value: object, code: str) -> list[str]:
    _require(isinstance(value, (list, tuple)), code)
    refs = [str(item).strip() for item in value]
    _require(all(refs) and len(refs) == len(set(refs)), code)
    return refs


def _digest(value: object, code: str) -> str:
    text = _nonempty(value, code)
    _require(
        len(text) == 64 and all(ch in "0123456789abcdef" for ch in text),
        code,
    )
    return text


def load_runtime_contract(
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[3]
    base_path = root / BASE_CONTRACT_REF
    successor_path = root / SUCCESSOR_CONTRACT_REF
    try:
        base = json.loads(base_path.read_text(encoding="utf-8"))
        successor = json.loads(successor_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalRuntimeError("runtime_contract_unreadable") from exc
    _require(
        base.get("schema_version")
        == "fin_ia_agent_runtime_reflection_context_continuity_contract_v1_0",
        "runtime_base_contract_schema_invalid",
    )
    _require(
        successor.get("schema_version")
        == "fin_ia_agent_runtime_reflection_context_continuity_contract_v1_1",
        "runtime_successor_contract_schema_invalid",
    )
    binding = successor.get("base_contract") or {}
    _require(binding.get("ref") == BASE_CONTRACT_REF, "runtime_base_contract_ref_drift")
    return {"base": base, "successor": successor}


def validate_runtime_artifact(
    artifact_type: str,
    payload: Mapping[str, Any],
    *,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    loaded = dict(contract or load_runtime_contract())
    base = loaded.get("base") or {}
    specs = base.get("artifact_contracts") or {}
    _require(artifact_type in specs, f"runtime_artifact_type_unknown:{artifact_type}")
    value = deepcopy(dict(payload))
    required = list(specs[artifact_type].get("required_fields") or ())
    missing = [field for field in required if field not in value]
    _require(not missing, f"runtime_artifact_fields_missing:{artifact_type}:{','.join(missing)}")

    if "session_id" in value:
        _nonempty(value["session_id"], "runtime_artifact_session_id_invalid")
    if artifact_type == "AgentSession":
        _iso_date(value["as_of_date"], "runtime_session_as_of_invalid")
        _iso_datetime(value["created_at"], "runtime_session_created_at_invalid")
        _iso_datetime(value["updated_at"], "runtime_session_updated_at_invalid")
        _require(
            value["status"] in {"active", "paused", "stopped", "completed"},
            "runtime_session_status_invalid",
        )
    elif artifact_type == "FeedbackReceipt":
        _require(
            value["owning_plane"]
            in {
                "infrastructure_and_tool_plane",
                "harness_control_plane",
                "agent_work_mode_plane",
                "skill_graph_overlap_plane",
            },
            "runtime_feedback_plane_invalid",
        )
        _require(
            value["owning_stage"] in {"S0", "S1", "S2", "S3", "S4", "S5"},
            "runtime_feedback_stage_invalid",
        )
        for field in (
            "artifact_refs",
            "permitted_next_actions",
            "forbidden_interpretations",
        ):
            _refs(value[field], f"runtime_feedback_{field}_invalid")
        _iso_datetime(value["created_at"], "runtime_feedback_created_at_invalid")
    elif artifact_type == "PlanDelta":
        _digest(value["base_plan_digest"], "runtime_plan_delta_base_digest_invalid")
        _refs(value["reason_feedback_refs"], "runtime_plan_delta_feedback_refs_invalid")
        _require(
            value["validation_status"] in {"pending", "accepted", "rejected"},
            "runtime_plan_delta_validation_status_invalid",
        )
    elif artifact_type == "GraphDelta":
        _digest(value["base_graph_digest"], "runtime_graph_delta_base_digest_invalid")
        _refs(value["supporting_evidence_refs"], "runtime_graph_delta_evidence_refs_invalid")
        _require(
            value["validation_status"] in {"pending", "accepted", "rejected"},
            "runtime_graph_delta_validation_status_invalid",
        )
    elif artifact_type == "ContextCheckpoint":
        extension = (
            loaded.get("successor", {})
            .get("context_checkpoint_extension", {})
            .get("required_fields", ())
        )
        missing_extension = [field for field in extension if field not in value]
        _require(
            not missing_extension,
            "runtime_checkpoint_extension_fields_missing:"
            + ",".join(missing_extension),
        )
        _iso_date(value["as_of_date"], "runtime_checkpoint_as_of_invalid")
        for field in (
            "accepted_evidence_refs",
            "numeric_fact_refs",
            "open_gap_refs",
            "unresolved_feedback_refs",
            "agent_local_state_refs",
            "authority_refs",
            "counterevidence_refs",
            "open_question_refs",
        ):
            _refs(value[field], f"runtime_checkpoint_{field}_invalid")
        expected = canonical_digest(
            {key: item for key, item in value.items() if key != "checkpoint_digest"}
        )
        _require(
            value["checkpoint_digest"] == expected,
            "runtime_checkpoint_digest_invalid",
        )
    elif artifact_type == "StopDecision":
        allowed = set(specs[artifact_type].get("allowed_decisions") or ())
        _require(value["decision"] in allowed, "runtime_stop_decision_invalid")
        for field in (
            "reason_codes",
            "coverage_state_refs",
            "unresolved_feedback_refs",
            "remaining_gap_refs",
        ):
            _refs(value[field], f"runtime_stop_{field}_invalid")
    return value


def create_agent_session(
    *,
    session_id: str,
    run_id: str,
    case_id: str,
    case_version: str,
    as_of_date: str,
    objective_ref: str,
    active_plan_ref: str,
    created_at: str,
) -> dict[str, Any]:
    body = {
        "session_id": _nonempty(session_id, "runtime_session_id_invalid"),
        "run_id": _nonempty(run_id, "runtime_run_id_invalid"),
        "case_id": _nonempty(case_id, "runtime_case_id_invalid"),
        "case_version": _nonempty(case_version, "runtime_case_version_invalid"),
        "as_of_date": _iso_date(as_of_date, "runtime_session_as_of_invalid"),
        "objective_ref": _nonempty(objective_ref, "runtime_objective_ref_invalid"),
        "active_plan_ref": _nonempty(active_plan_ref, "runtime_plan_ref_invalid"),
        "event_log_ref": f"runtime://sessions/{session_id}/events",
        "current_checkpoint_ref": None,
        "status": "active",
        "created_at": _iso_datetime(created_at, "runtime_session_created_at_invalid"),
        "updated_at": created_at,
    }
    validated = validate_runtime_artifact("AgentSession", body)
    return {**validated, "session_digest": canonical_digest(validated)}


def apply_accepted_plan_delta(
    *,
    session: Mapping[str, Any],
    plan_delta: Mapping[str, Any],
    expected_base_plan_digest: str,
    accepted_plan_digest: str,
    accepted_plan_ref: str,
    updated_at: str,
) -> dict[str, Any]:
    """Advance one session only after a validated PlanDelta is accepted.

    The function deliberately changes no case, period, objective or authority
    state.  It closes the previously missing seam between a durable feedback
    receipt and the plan reference saved in the next checkpoint.
    """

    current = validate_runtime_artifact("AgentSession", session)
    delta = validate_runtime_artifact("PlanDelta", plan_delta)
    _require(
        delta["session_id"] == current["session_id"],
        "runtime_plan_delta_session_mismatch",
    )
    _require(
        delta["validation_status"] == "accepted",
        "runtime_plan_delta_not_accepted",
    )
    _require(
        delta["base_plan_digest"]
        == _digest(
            expected_base_plan_digest,
            "runtime_plan_delta_expected_base_digest_invalid",
        ),
        "runtime_plan_delta_base_plan_mismatch",
    )
    new_digest = _digest(
        accepted_plan_digest, "runtime_accepted_plan_digest_invalid"
    )
    new_ref = _nonempty(accepted_plan_ref, "runtime_accepted_plan_ref_invalid")
    _require(
        new_digest != delta["base_plan_digest"],
        "runtime_accepted_plan_did_not_change",
    )
    value = {
        key: deepcopy(item)
        for key, item in current.items()
        if key != "session_digest"
    }
    value["active_plan_ref"] = new_ref
    value["updated_at"] = _iso_datetime(
        updated_at, "runtime_session_updated_at_invalid"
    )
    validated = validate_runtime_artifact("AgentSession", value)
    return {**validated, "session_digest": canonical_digest(validated)}


def append_session_event(
    events: Sequence[Mapping[str, Any]],
    *,
    session_id: str,
    event_type: str,
    actor_id: str,
    occurred_at: str,
    attempt_id: str | None = None,
    input_refs: Sequence[str] = (),
    output_refs: Sequence[str] = (),
    feedback_refs: Sequence[str] = (),
) -> dict[str, Any]:
    existing = validate_event_log(events, expected_session_id=session_id)
    loaded = load_runtime_contract()
    allowed = set(
        loaded["successor"]["session_event_envelope"]["allowed_event_types"]
    )
    _require(event_type in allowed, "runtime_event_type_invalid")
    sequence = len(existing) + 1
    prior_digest = existing[-1]["event_digest"] if existing else None
    identity = {
        "session_id": session_id,
        "sequence": sequence,
        "event_type": event_type,
        "actor_id": actor_id,
        "attempt_id": attempt_id,
        "occurred_at": occurred_at,
    }
    unsigned = {
        "schema_version": "fin_ia_agent_session_event_v1_0",
        "event_id": "EVENT::" + canonical_digest(identity)[:24].upper(),
        "session_id": _nonempty(session_id, "runtime_event_session_id_invalid"),
        "sequence": sequence,
        "event_type": event_type,
        "actor_id": _nonempty(actor_id, "runtime_event_actor_id_invalid"),
        "attempt_id": (
            _nonempty(attempt_id, "runtime_event_attempt_id_invalid")
            if attempt_id is not None
            else None
        ),
        "input_refs": _refs(list(input_refs), "runtime_event_input_refs_invalid"),
        "output_refs": _refs(list(output_refs), "runtime_event_output_refs_invalid"),
        "feedback_refs": _refs(list(feedback_refs), "runtime_event_feedback_refs_invalid"),
        "prior_event_digest": prior_digest,
        "occurred_at": _iso_datetime(occurred_at, "runtime_event_occurred_at_invalid"),
    }
    event = {**unsigned, "event_digest": canonical_digest(unsigned)}
    validate_event_log([*existing, event], expected_session_id=session_id)
    return event


def validate_event_log(
    events: Sequence[Mapping[str, Any]],
    *,
    expected_session_id: str | None = None,
) -> list[dict[str, Any]]:
    loaded = load_runtime_contract()
    envelope = loaded["successor"]["session_event_envelope"]
    required = set(envelope["required_fields"])
    allowed = set(envelope["allowed_event_types"])
    normalized: list[dict[str, Any]] = []
    event_ids: set[str] = set()
    terminal_attempts: set[str] = set()
    terminal_types = {
        "tool_execution_completed",
        "tool_execution_failed",
        "provider_attempt_completed",
        "provider_attempt_failed",
    }
    for expected_sequence, raw in enumerate(events, start=1):
        value = deepcopy(dict(raw))
        _require(required.issubset(value), "runtime_event_fields_missing")
        _require(value["sequence"] == expected_sequence, "runtime_event_sequence_invalid")
        _require(value["event_type"] in allowed, "runtime_event_type_invalid")
        _require(
            expected_session_id is None or value["session_id"] == expected_session_id,
            "runtime_event_session_mismatch",
        )
        _require(value["event_id"] not in event_ids, "runtime_event_id_duplicate")
        event_ids.add(value["event_id"])
        expected_prior = normalized[-1]["event_digest"] if normalized else None
        _require(
            value["prior_event_digest"] == expected_prior,
            "runtime_event_prior_digest_invalid",
        )
        _iso_datetime(value["occurred_at"], "runtime_event_occurred_at_invalid")
        for field in ("input_refs", "output_refs", "feedback_refs"):
            _refs(value[field], f"runtime_event_{field}_invalid")
        unsigned = {key: item for key, item in value.items() if key != "event_digest"}
        _require(
            value["event_digest"] == canonical_digest(unsigned),
            "runtime_event_digest_invalid",
        )
        attempt_id = value.get("attempt_id")
        if value["event_type"] in terminal_types:
            _require(bool(attempt_id), "runtime_terminal_event_attempt_missing")
            _require(attempt_id not in terminal_attempts, "runtime_attempt_terminal_duplicate")
            terminal_attempts.add(str(attempt_id))
        normalized.append(value)
    return normalized


def create_context_checkpoint(
    *,
    session: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    checkpoint_id: str,
    objective_digest: str,
    plan_digest: str,
    research_graph_digest: str,
    accepted_evidence_refs: Sequence[str] = (),
    numeric_fact_refs: Sequence[str] = (),
    open_gap_refs: Sequence[str] = (),
    unresolved_feedback_refs: Sequence[str] = (),
    agent_local_state_refs: Sequence[str] = (),
    authority_refs: Sequence[str] = (),
    counterevidence_refs: Sequence[str] = (),
    open_question_refs: Sequence[str] = (),
    compression_policy_version: str = "fin_ia_context_projection_v1_0",
) -> dict[str, Any]:
    current_session = validate_runtime_artifact("AgentSession", session)
    log = validate_event_log(events, expected_session_id=current_session["session_id"])
    _require(bool(log), "runtime_checkpoint_event_log_empty")
    body = {
        "checkpoint_id": _nonempty(checkpoint_id, "runtime_checkpoint_id_invalid"),
        "session_id": current_session["session_id"],
        "event_sequence": len(log),
        "objective_digest": _digest(objective_digest, "runtime_objective_digest_invalid"),
        "plan_digest": _digest(plan_digest, "runtime_plan_digest_invalid"),
        "research_graph_digest": _digest(
            research_graph_digest, "runtime_graph_digest_invalid"
        ),
        "accepted_evidence_refs": _refs(
            list(accepted_evidence_refs), "runtime_checkpoint_evidence_refs_invalid"
        ),
        "numeric_fact_refs": _refs(
            list(numeric_fact_refs), "runtime_checkpoint_numeric_refs_invalid"
        ),
        "open_gap_refs": _refs(
            list(open_gap_refs), "runtime_checkpoint_gap_refs_invalid"
        ),
        "unresolved_feedback_refs": _refs(
            list(unresolved_feedback_refs),
            "runtime_checkpoint_feedback_refs_invalid",
        ),
        "agent_local_state_refs": _refs(
            list(agent_local_state_refs), "runtime_checkpoint_local_refs_invalid"
        ),
        "compression_policy_version": _nonempty(
            compression_policy_version, "runtime_checkpoint_compression_policy_invalid"
        ),
        "case_id": current_session["case_id"],
        "case_version": current_session["case_version"],
        "as_of_date": current_session["as_of_date"],
        "active_plan_ref": current_session["active_plan_ref"],
        "last_event_digest": log[-1]["event_digest"],
        "authority_refs": _refs(
            list(authority_refs), "runtime_checkpoint_authority_refs_invalid"
        ),
        "counterevidence_refs": _refs(
            list(counterevidence_refs),
            "runtime_checkpoint_counterevidence_refs_invalid",
        ),
        "open_question_refs": _refs(
            list(open_question_refs), "runtime_checkpoint_question_refs_invalid"
        ),
    }
    checkpoint = {**body, "checkpoint_digest": canonical_digest(body)}
    return validate_runtime_artifact("ContextCheckpoint", checkpoint)


def resume_agent_session(
    *,
    session: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    checkpoint: Mapping[str, Any],
    expected_case_id: str,
    expected_case_version: str,
    expected_as_of_date: str,
    expected_active_plan_ref: str,
    resumed_at: str,
    required_authority_refs: Sequence[str] = (),
    required_open_gap_refs: Sequence[str] = (),
    required_unresolved_feedback_refs: Sequence[str] = (),
    required_counterevidence_refs: Sequence[str] = (),
    required_open_question_refs: Sequence[str] = (),
) -> dict[str, Any]:
    current_session = validate_runtime_artifact("AgentSession", session)
    log = validate_event_log(events, expected_session_id=current_session["session_id"])
    current_checkpoint = validate_runtime_artifact("ContextCheckpoint", checkpoint)
    _require(
        current_checkpoint["session_id"] == current_session["session_id"],
        "runtime_resume_session_mismatch",
    )
    bindings = {
        "case_id": expected_case_id,
        "case_version": expected_case_version,
        "as_of_date": expected_as_of_date,
        "active_plan_ref": expected_active_plan_ref,
    }
    for field, expected in bindings.items():
        _require(
            current_session[field] == expected and current_checkpoint[field] == expected,
            f"runtime_resume_{field}_mismatch",
        )
    sequence = int(current_checkpoint["event_sequence"])
    _require(0 < sequence <= len(log), "runtime_resume_event_sequence_invalid")
    _require(
        log[sequence - 1]["event_digest"] == current_checkpoint["last_event_digest"],
        "runtime_resume_event_binding_invalid",
    )
    required_sets = {
        "authority_refs": required_authority_refs,
        "open_gap_refs": required_open_gap_refs,
        "unresolved_feedback_refs": required_unresolved_feedback_refs,
        "counterevidence_refs": required_counterevidence_refs,
        "open_question_refs": required_open_question_refs,
    }
    for field, required_values in required_sets.items():
        missing = set(required_values) - set(current_checkpoint[field])
        _require(not missing, f"runtime_resume_material_state_dropped:{field}")
    preserved = {
        "accepted_evidence": len(current_checkpoint["accepted_evidence_refs"]),
        "numeric_facts": len(current_checkpoint["numeric_fact_refs"]),
        "open_gaps": len(current_checkpoint["open_gap_refs"]),
        "unresolved_feedback": len(current_checkpoint["unresolved_feedback_refs"]),
        "authority_refs": len(current_checkpoint["authority_refs"]),
        "counterevidence": len(current_checkpoint["counterevidence_refs"]),
        "open_questions": len(current_checkpoint["open_question_refs"]),
    }
    unsigned = {
        "schema_version": "fin_ia_agent_session_resume_receipt_v1_0",
        "session_id": current_session["session_id"],
        "checkpoint_id": current_checkpoint["checkpoint_id"],
        "checkpoint_digest": current_checkpoint["checkpoint_digest"],
        "replayed_through_sequence": len(log),
        "last_event_digest": log[-1]["event_digest"],
        "case_id": current_session["case_id"],
        "case_version": current_session["case_version"],
        "as_of_date": current_session["as_of_date"],
        "active_plan_ref": current_session["active_plan_ref"],
        "preserved_state_counts": preserved,
        "status": "resume_replay_verified",
        "resumed_at": _iso_datetime(resumed_at, "runtime_resume_time_invalid"),
    }
    return {**unsigned, "resume_receipt_digest": canonical_digest(unsigned)}


__all__ = [
    "BASE_CONTRACT_REF",
    "SUCCESSOR_CONTRACT_REF",
    "CanonicalRuntimeError",
    "apply_accepted_plan_delta",
    "append_session_event",
    "canonical_digest",
    "create_agent_session",
    "create_context_checkpoint",
    "load_runtime_contract",
    "resume_agent_session",
    "validate_event_log",
    "validate_runtime_artifact",
]
