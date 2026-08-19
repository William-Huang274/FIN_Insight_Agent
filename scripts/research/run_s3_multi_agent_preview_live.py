from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.canonical_runtime import (  # noqa: E402
    canonical_digest,
    create_context_checkpoint,
    resume_agent_session,
    validate_runtime_artifact,
)
from sec_agent.providers import (  # noqa: E402
    load_chat_completion_profile,
)
from sec_agent.research.bounded_finance_loop import (  # noqa: E402
    validate_deepseek_ga_node_profile,
    validate_deepseek_ga_profile,
)
from sec_agent.research.case_truth_reconciliation import (  # noqa: E402
    compile_case_truth_model_view,
)
from sec_agent.research.multi_agent_preview import (  # noqa: E402
    RESEARCH_LEAD_AGENT_ID,
    SPECIALIST_AGENT_IDS,
    WRITER_AGENT_ID,
    compile_challenge_catalog,
    compile_evaluation_messages,
    compile_lead_coordination_messages,
    compile_lead_plan_messages,
    compile_report_messages,
    compile_specialist_context,
    compile_specialist_workpaper_messages,
    evaluation_tool,
    lead_coordination_tool,
    lead_plan_tool,
    load_multi_agent_role_topology,
    local_case_absence_findings,
    report_draft_tool,
    specialist_workpaper_tool,
    validate_analysis_fragment_checkpoint,
    validate_specialist_plan_checkpoint,
    validate_evaluation,
    validate_lead_coordination_decision,
    validate_lead_plan,
    validate_report_draft,
    validate_specialist_workpaper,
)
from sec_agent.research.multi_agent_preview_runtime import (  # noqa: E402
    MultiAgentPreviewRuntimeError,
    PreviewAgentSessionState,
    compile_cross_role_feedback_receipt,
    compile_multi_agent_preview_materialization,
    execute_analyzed_preview_node,
    rebind_preview_session_plan,
    start_preview_agent_session,
)
from sec_agent.project_os_preflight import (  # noqa: E402
    MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_DECISION_SCHEMA,
    MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_DECISION_STATUS,
    MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_SCHEMA,
    MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_STATUS,
    MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE,
    validate_multi_agent_preview_analysis_successor_scope_decision,
    validate_multi_agent_preview_plan_successor_scope_decision,
)


PLAN_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_3"
)
ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_4"
)
FULL_SCHEMA_V1 = "fin_ia_s3_dell_multi_agent_preview_live_full_result_v1_1"
FULL_SCHEMA_V2 = "fin_ia_s3_dell_multi_agent_preview_live_full_result_v1_2"
PUBLIC_SCHEMA_V1 = "fin_ia_s3_dell_multi_agent_preview_live_result_v1_1"
PUBLIC_SCHEMA_V2 = "fin_ia_s3_dell_multi_agent_preview_live_result_v1_2"


class MultiAgentPreviewLiveError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(ref: str) -> Path:
    path = (ROOT / ref).resolve()
    path.relative_to(ROOT)
    return path


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_output_identity_consumed"
        ) from exc


def _git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _validate_authority(
    authority_path: Path,
) -> tuple[dict[str, Any], dict[str, Path], dict[str, Any]]:
    authority = _json(authority_path)
    expected = {
        "schema_version",
        "status",
        "authorized_at",
        "implementation_commit",
        "bound_inputs",
        "execution_limits",
        "outputs",
        "authority_statement",
    }
    schema = str(authority.get("schema_version") or "")
    analysis_successor = schema == ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA
    expected_status = (
        "approved_for_one_R4_analysis_checkpoint_feedback_continuation_"
        "successor_after_project_os_preflight"
        if analysis_successor
        else (
            "approved_for_one_R3_plan_checkpoint_analysis_submission_"
            "successor_after_project_os_preflight"
        )
    )
    if not (
        set(authority) == expected
        and schema
        in {PLAN_SUCCESSOR_AUTHORITY_SCHEMA, ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA}
        and authority.get("status") == expected_status
        and authority.get("implementation_commit") == _git_head()
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_authority_identity_invalid"
        )
    inputs: dict[str, Path] = {}
    for name, raw in authority["bound_inputs"].items():
        if set(raw) != {"ref", "sha256"}:
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_authority_binding_invalid"
            )
        path = _resolve(str(raw["ref"]))
        if not path.is_file() or _sha(path) != str(raw["sha256"]):
            raise MultiAgentPreviewLiveError(
                f"multi_agent_preview_authority_binding_drift:{name}"
            )
        inputs[name] = path
    base_inputs = {
        "project_os_scope_decision",
        "topology",
        "objective",
        "zero_call_proof",
        "successor_zero_call_proof",
        "planning_overlay",
        "analysis_profile",
        "submission_profile",
        "historical_five_cell_assessment",
        "predecessor_plan_checkpoint",
    }
    required_inputs = (
        base_inputs
        | {
            "predecessor_scope_decision",
            "predecessor_authority",
            "predecessor_result",
            "analysis_checkpoint",
            "analysis_successor_zero_call_proof",
            "analysis_continuation_profile",
        }
        if analysis_successor
        else base_inputs | {"predecessor_authority", "predecessor_result"}
    )
    if set(inputs) != required_inputs:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_authority_inputs_invalid"
        )
    scope_decision = _json(inputs["project_os_scope_decision"])
    if analysis_successor:
        scope_projection = (
            validate_multi_agent_preview_analysis_successor_scope_decision(
                root=ROOT, decision=scope_decision
            )
        )
        base_scope_decision = _json(inputs["predecessor_scope_decision"])
        scope_valid = (
            scope_decision.get("schema_version")
            == MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_DECISION_SCHEMA
            and scope_decision.get("status")
            == MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_DECISION_STATUS
            and scope_decision.get("run_scope_id")
            == MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_SCOPE
            and scope_projection.get(
                "multi_agent_preview_analysis_checkpoint_successor"
            )
            is True
        )
    else:
        scope_projection = validate_multi_agent_preview_plan_successor_scope_decision(
            root=ROOT, decision=scope_decision
        )
        base_scope_decision = scope_decision
        scope_valid = (
            scope_decision.get("schema_version")
            == MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_SCHEMA
            and scope_decision.get("status")
            == MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_STATUS
            and scope_decision.get("run_scope_id")
            == MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE
            and scope_projection.get(
                "multi_agent_preview_plan_checkpoint_successor"
            )
            is True
        )
    if not scope_valid:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_project_os_scope_invalid"
        )
    base_scope_bindings = {
        "topology": ("topology_ref", "topology_sha256"),
        "objective": ("objective_ref", "objective_sha256"),
        "zero_call_proof": ("zero_call_proof_ref", "zero_call_proof_sha256"),
        "successor_zero_call_proof": (
            "successor_zero_call_proof_ref",
            "successor_zero_call_proof_sha256",
        ),
        "planning_overlay": (
            "planning_overlay_ref",
            "planning_overlay_sha256",
        ),
        "analysis_profile": (
            "analysis_profile_ref",
            "analysis_profile_sha256",
        ),
        "submission_profile": (
            "submission_profile_ref",
            "submission_profile_sha256",
        ),
        "historical_five_cell_assessment": (
            "historical_five_cell_assessment_ref",
            "historical_five_cell_assessment_sha256",
        ),
        "predecessor_plan_checkpoint": (
            "predecessor_plan_checkpoint_ref",
            "predecessor_plan_checkpoint_sha256",
        ),
    }
    for input_name, (ref_field, sha_field) in base_scope_bindings.items():
        if not (
            _relative(inputs[input_name]) == base_scope_decision.get(ref_field)
            and _sha(inputs[input_name]) == base_scope_decision.get(sha_field)
        ):
            raise MultiAgentPreviewLiveError(
                f"multi_agent_preview_project_os_binding_drift:{input_name}"
            )
    if analysis_successor:
        current_scope_bindings = {
            "predecessor_scope_decision": (
                "predecessor_scope_decision_ref",
                "predecessor_scope_decision_sha256",
            ),
            "predecessor_authority": (
                "predecessor_live_authority_ref",
                "predecessor_live_authority_sha256",
            ),
            "predecessor_result": (
                "predecessor_live_result_ref",
                "predecessor_live_result_sha256",
            ),
            "analysis_checkpoint": (
                "analysis_checkpoint_ref",
                "analysis_checkpoint_sha256",
            ),
            "analysis_successor_zero_call_proof": (
                "analysis_successor_zero_call_proof_ref",
                "analysis_successor_zero_call_proof_sha256",
            ),
            "analysis_continuation_profile": (
                "analysis_continuation_profile_ref",
                "analysis_continuation_profile_sha256",
            ),
        }
    else:
        current_scope_bindings = {
            "predecessor_authority": (
                "predecessor_authority_ref",
                "predecessor_authority_sha256",
            ),
            "predecessor_result": (
                "predecessor_result_ref",
                "predecessor_result_sha256",
            ),
        }
    for input_name, (ref_field, sha_field) in current_scope_bindings.items():
        if not (
            _relative(inputs[input_name]) == scope_decision.get(ref_field)
            and _sha(inputs[input_name]) == scope_decision.get(sha_field)
        ):
            raise MultiAgentPreviewLiveError(
                f"multi_agent_preview_project_os_binding_drift:{input_name}"
            )
    zero = _json(inputs["zero_call_proof"])
    if zero.get("status") != "zero_call_topology_and_current_tool_spine_pass":
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_zero_call_proof_not_passed"
        )
    successor_zero = _json(inputs["successor_zero_call_proof"])
    controlled = (
        (successor_zero.get("materialization_readiness") or {}).get(
            "controlled_plan_summary"
        )
        or {}
    )
    if not (
        successor_zero.get("status")
        == "R3_plan_checkpoint_successor_zero_call_pass"
        and successor_zero.get("result_digest")
        == base_scope_decision.get("successor_zero_call_proof_result_digest")
        and controlled.get("proposed_atom_count") == 13
        and controlled.get("selected_atom_count") == 12
        and controlled.get("deferred_atom_count") == 1
        and controlled.get("execution_request_budget") == 12
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_successor_zero_call_proof_not_passed"
        )
    if analysis_successor:
        analysis_successor_zero = _json(
            inputs["analysis_successor_zero_call_proof"]
        )
        analysis_checkpoint = validate_analysis_fragment_checkpoint(
            _json(inputs["analysis_checkpoint"])
        )
        if not (
            analysis_successor_zero.get("status")
            == "R4_visible_analysis_checkpoint_successor_zero_call_pass"
            and analysis_successor_zero.get("result_digest")
            == scope_decision.get(
                "analysis_successor_zero_call_proof_result_digest"
            )
            and analysis_checkpoint.get("checkpoint_digest")
            == scope_decision.get("analysis_checkpoint_digest")
            and analysis_checkpoint.get("continuation_policy", {}).get(
                "maximum_continuation_calls"
            )
            == 1
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_analysis_successor_zero_call_not_passed"
            )
    planning_overlay = _json(inputs["planning_overlay"])
    if not (
        planning_overlay.get("status")
        == "provider_neutral_preview_proposal_execution_budget_separation"
        and planning_overlay.get("max_proposed_atoms_override") == 20
        and planning_overlay.get("max_evidence_requests_must_remain") == 12
        and (planning_overlay.get("authority") or {}).get(
            "product_pointer_promotion"
        )
        is False
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_planning_overlay_not_bound"
        )
    limits = authority["execution_limits"]
    if limits != scope_decision.get("execution_limits"):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_project_os_limit_drift"
        )
    if not (
        limits.get("maximum_new_model_nodes") == 16
        and (
            limits.get("maximum_resumed_lead_analysis_continuations") == 1
            and limits.get("maximum_new_analysis_calls_per_other_node") == 1
            if analysis_successor
            else limits.get("maximum_analysis_calls_per_node") == 1
        )
        and limits.get("maximum_submission_attempts_per_node") == 2
        and limits.get("reused_specialist_plan_count") == 6
        and limits.get("maximum_counter_challenge_repairs") == 3
        and limits.get("maximum_evaluator_repairs") == 2
        and limits.get("maximum_evaluation_rounds") == 2
        and limits.get("external_source_network_calls") == 0
        and limits.get("candidate_promotions") == 0
        and limits.get("product_publication") is False
        and limits.get("qualified_human_acceptance") is False
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_execution_limits_invalid"
        )
    topology = load_multi_agent_role_topology(_json(inputs["topology"]))
    checkpoint = validate_specialist_plan_checkpoint(
        _json(inputs["predecessor_plan_checkpoint"]), topology=topology
    )
    if not (
        checkpoint.get("reused_specialist_plan_count") == 6
        and checkpoint.get("new_model_calls") == 0
        and checkpoint.get("new_network_calls") == 0
        and checkpoint.get("new_candidate_promotions") == 0
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_plan_checkpoint_invalid"
        )
    outputs = authority["outputs"]
    expected_outputs = {
        "run_id",
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
    }
    if set(outputs) != expected_outputs:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_outputs_invalid"
        )
    paths = {key: _resolve(str(value)) for key, value in outputs.items() if key != "run_id"}
    if (
        paths["capture_root_ref"].exists()
        or paths["private_output_root_ref"].exists()
        or paths["public_result_ref"].exists()
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_output_identity_consumed"
        )
    return authority, inputs, {**outputs, **paths}


def _input_ref_count(messages: Sequence[Mapping[str, Any]]) -> int:
    text = "".join(str(row.get("content") or "") for row in messages)
    return sum(text.count(prefix) for prefix in ("EV::", "NUM::", "REL::", "GAP::"))


def _load_bound_analysis_checkpoint_draft(
    checkpoint: Mapping[str, Any],
) -> str:
    response_path = _resolve(str(checkpoint["response_capture_ref"]))
    request_path = _resolve(str(checkpoint["request_capture_ref"]))
    if not (
        _sha(request_path) == checkpoint["request_capture_sha256"]
        and _sha(response_path) == checkpoint["response_capture_sha256"]
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_analysis_checkpoint_capture_drift"
        )
    request = _json(request_path)
    response = _json(response_path)
    try:
        choice = response["response_body"]["choices"][0]
        draft = str(choice["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_analysis_checkpoint_content_missing"
        ) from exc
    if not (
        request.get("request_digest") == checkpoint["request_digest"]
        and response.get("response_digest") == checkpoint["response_digest"]
        and response.get("response_body_complete") is True
        and response.get("eligible_for_business_promotion") is False
        and choice.get("finish_reason") == "length"
        and canonical_digest(draft) == checkpoint["partial_draft_digest"]
        and len(draft) == checkpoint["partial_draft_character_count"]
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_analysis_checkpoint_content_drift"
        )
    return draft


def _compile_evaluator_feedback_receipt(
    *,
    target_session_id: str,
    finding: Mapping[str, Any],
) -> dict[str, Any]:
    identity = {
        "target_session_id": target_session_id,
        "finding_code": finding["finding_code"],
        "target_agent_id": finding["target_agent_id"],
    }
    body = {
        "feedback_id": "FEEDBACK::" + canonical_digest(identity)[:24].upper(),
        "session_id": target_session_id,
        "source_node_id": "EVAL::L1_AND_CONTENT",
        "target_node_id": str(finding["target_agent_id"]),
        "failure_class": "independent_evaluation_finding",
        "failure_code": str(finding["finding_code"]),
        "owning_plane": (
            "agent_work_mode_plane"
            if finding["failure_owner"]
            in {"agent_orchestration_and_role_design", "model_judgment"}
            else (
                "harness_control_plane"
                if finding["failure_owner"] == "harness_control"
                else "infrastructure_and_tool_plane"
            )
        ),
        "owning_stage": "S3",
        "artifact_refs": [
            f"evaluation-finding://{finding['finding_code']}",
            *[str(ref) for ref in finding["evidence_refs"]],
        ],
        "model_visible_summary": str(finding["explanation"]),
        "permitted_next_actions": [str(finding["permitted_repair"])],
        "forbidden_interpretations": [
            "The finding is not new Evidence or a NumericFact",
            "A role repair cannot conceal an infrastructure or Harness failure",
            "Do not broaden the conclusion or add sources, facts or numbers",
        ],
        "created_at": _now(),
    }
    validated = validate_runtime_artifact("FeedbackReceipt", body)
    return {**validated, "feedback_digest": canonical_digest(validated)}


def _merge_local_evaluation(
    *,
    model_evaluation: Mapping[str, Any],
    local_findings: Sequence[Mapping[str, Any]],
    workpapers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not local_findings:
        return deepcopy(dict(model_evaluation))
    combined = {
        "schema_version": model_evaluation["schema_version"],
        "findings": [
            *[deepcopy(dict(row)) for row in model_evaluation["findings"]],
            *[deepcopy(dict(row)) for row in local_findings],
        ],
        "cross_role_conflicts": list(model_evaluation["cross_role_conflicts"]),
        "report_may_proceed": False,
    }
    return validate_evaluation(combined, workpapers=workpapers)


def _checkpoint_and_resume_for_feedback(
    *,
    state: PreviewAgentSessionState,
    context: Mapping[str, Any],
    prior_workpaper: Mapping[str, Any],
    feedback_receipts: Sequence[Mapping[str, Any]],
    objective_digest: str,
    plan_digest: str,
) -> None:
    feedback_ids = tuple(str(row["feedback_id"]) for row in feedback_receipts)
    for receipt in feedback_receipts:
        state.feedback_receipts.append(deepcopy(dict(receipt)))
    state.append(
        event_type="feedback_issued",
        actor_id="HARNESS::FEEDBACK_ROUTER",
        feedback_refs=feedback_ids,
    )
    checkpoint_id = (
        f"CHECKPOINT::DELL::{state.agent_id.split('::')[-1]}::"
        f"{len(state.checkpoints) + 1:02d}"
    )
    state.append(
        event_type="checkpoint_created",
        actor_id=state.agent_id,
        output_refs=(f"checkpoint://{checkpoint_id}",),
    )
    cell = context["cell_analysis_view"]["cell"]
    evidence_refs = tuple(
        str(row["evidence_ref"]) for row in cell["cell_evidence_views"]
    )
    numeric_refs = tuple(str(row) for row in cell["allowed_numeric_refs"])
    gap_refs = tuple(str(row["gap_ref"]) for row in cell["residual_gap_cards"])
    question_refs = tuple(
        "question://" + canonical_digest(text)
        for text in prior_workpaper["what_would_change"]
    )
    checkpoint = create_context_checkpoint(
        session=state.session,
        events=state.events,
        checkpoint_id=checkpoint_id,
        objective_digest=objective_digest,
        plan_digest=plan_digest,
        research_graph_digest=canonical_digest(
            context["cell_analysis_view"].get("numeric_relation_catalog") or []
        ),
        accepted_evidence_refs=evidence_refs,
        numeric_fact_refs=numeric_refs,
        open_gap_refs=gap_refs,
        unresolved_feedback_refs=feedback_ids,
        agent_local_state_refs=(
            f"workpaper://{prior_workpaper['workpaper_digest']}",
        ),
        authority_refs=(
            f"context://{context['context_digest']}",
            f"plan://{plan_digest}",
        ),
        counterevidence_refs=tuple(
            str(ref)
            for receipt in feedback_receipts
            for ref in receipt["artifact_refs"]
        ),
        open_question_refs=question_refs,
    )
    state.checkpoints.append(checkpoint)
    resume = resume_agent_session(
        session=state.session,
        events=state.events,
        checkpoint=checkpoint,
        expected_case_id="DELL",
        expected_case_version="fin-0.1.3-preview",
        expected_as_of_date="2026-08-06",
        expected_active_plan_ref=state.session["active_plan_ref"],
        resumed_at=_now(),
        required_authority_refs=checkpoint["authority_refs"],
        required_open_gap_refs=gap_refs,
        required_unresolved_feedback_refs=feedback_ids,
        required_counterevidence_refs=checkpoint["counterevidence_refs"],
        required_open_question_refs=question_refs,
    )
    state.resume_receipts.append(resume)
    state.append(
        event_type="session_resumed",
        actor_id=state.agent_id,
        input_refs=(f"checkpoint://{checkpoint_id}",),
        output_refs=(f"resume://{resume['resume_receipt_digest']}",),
        feedback_refs=feedback_ids,
    )


def _stop_role(
    *,
    state: PreviewAgentSessionState,
    context: Mapping[str, Any] | None,
    evaluation: Mapping[str, Any],
) -> None:
    findings = [
        row
        for row in evaluation["findings"]
        if row["target_agent_id"] == state.agent_id and row["blocks_report"]
    ]
    gap_refs = (
        [
            str(row["gap_ref"])
            for row in context["cell_analysis_view"]["cell"]["residual_gap_cards"]
        ]
        if context is not None
        else []
    )
    if any(
        row["failure_owner"] == "data_infrastructure_or_tool"
        for row in findings
    ):
        decision = "pause_for_tool_recovery"
    elif findings:
        decision = "stop_contract_failure"
    elif gap_refs:
        decision = "stop_information_boundary"
    else:
        decision = "stop_sufficient"
    stop = {
        "stop_decision_id": (
            "STOP::" + canonical_digest(
                {"session_id": state.session["session_id"], "decision": decision}
            )[:24].upper()
        ),
        "session_id": state.session["session_id"],
        "decided_by_agent_id": state.agent_id,
        "decision": decision,
        "reason_codes": (
            [str(row["finding_code"]) for row in findings]
            or (["typed_information_boundary_preserved"] if gap_refs else ["role_workpaper_complete"])
        ),
        "coverage_state_refs": [
            "coverage://" + (str(context["context_digest"]) if context else state.agent_id)
        ],
        "unresolved_feedback_refs": [
            str(row["feedback_id"])
            for row in state.feedback_receipts
            if findings
        ],
        "remaining_gap_refs": gap_refs,
        "budget_state": {"new_model_steps_authorized": 0},
        "quality_risk": (
            "; ".join(str(row["explanation"]) for row in findings)
            if findings
            else "remaining typed gaps are visible and no blocking evaluator finding remains"
        ),
        "harness_validation_status": "accepted",
    }
    validated = validate_runtime_artifact("StopDecision", stop)
    state.stop_decisions.append(validated)
    state.append(
        event_type="stop_decided",
        actor_id=state.agent_id,
        output_refs=(f"stop://{validated['stop_decision_id']}",),
        feedback_refs=tuple(validated["unresolved_feedback_refs"]),
    )


def run(authority_path: Path) -> dict[str, Any]:
    authority, paths, outputs = _validate_authority(authority_path)
    analysis_successor = (
        authority["schema_version"] == ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA
    )
    full_schema = FULL_SCHEMA_V2 if analysis_successor else FULL_SCHEMA_V1
    public_schema = PUBLIC_SCHEMA_V2 if analysis_successor else PUBLIC_SCHEMA_V1
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise MultiAgentPreviewLiveError("deepseek_api_key_missing")
    topology = load_multi_agent_role_topology(_json(paths["topology"]))
    objective_payload = _json(paths["objective"])
    analysis_profile = load_chat_completion_profile(
        _json(paths["analysis_profile"])
    )
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile"])
    )
    continuation_profile = (
        load_chat_completion_profile(_json(paths["analysis_continuation_profile"]))
        if analysis_successor
        else None
    )
    validate_deepseek_ga_profile(analysis_profile, strict_tools=False)
    validate_deepseek_ga_node_profile(
        submission_profile,
        node_class="contract_submission_non_thinking",
    )
    if analysis_successor and not (
        continuation_profile is not None
        and continuation_profile.provider_id == "deepseek"
        and continuation_profile.model == "deepseek-v4-pro"
        and continuation_profile.base_url == "https://api.deepseek.com"
        and continuation_profile.endpoint == "/chat/completions"
        and dict(continuation_profile.request_defaults)
        == {
            "max_tokens": 4000,
            "stream": False,
            "thinking": {"type": "enabled"},
            "reasoning_effort": "low",
        }
        and continuation_profile.authority.get("retry_count") == 0
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_analysis_continuation_profile_invalid"
        )
    plan_checkpoint = validate_specialist_plan_checkpoint(
        _json(paths["predecessor_plan_checkpoint"]), topology=topology
    )
    successor_zero = _json(paths["successor_zero_call_proof"])
    analysis_successor_zero = (
        _json(paths["analysis_successor_zero_call_proof"])
        if analysis_successor
        else None
    )
    analysis_checkpoint = (
        validate_analysis_fragment_checkpoint(_json(paths["analysis_checkpoint"]))
        if analysis_successor
        else None
    )
    analysis_checkpoint_draft = (
        _load_bound_analysis_checkpoint_draft(analysis_checkpoint)
        if analysis_checkpoint is not None
        else None
    )
    planning_overlay = _json(paths["planning_overlay"])
    run_id = str(outputs["run_id"])
    capture_root = outputs["capture_root_ref"]
    private_root = outputs["private_output_root_ref"]
    public_result_path = outputs["public_result_ref"]
    capture_root.mkdir(parents=True, exist_ok=True)
    analysis_successor_bindings = (
        {
            "predecessor_analysis_checkpoint": {
                "ref": _relative(paths["analysis_checkpoint"]),
                "sha256": _sha(paths["analysis_checkpoint"]),
                "checkpoint_digest": analysis_checkpoint["checkpoint_digest"],
                "source_run_id": analysis_checkpoint["run_id"],
                "partial_draft_character_count": analysis_checkpoint[
                    "partial_draft_character_count"
                ],
                "partial_draft_business_promoted": False,
            },
            "analysis_successor_zero_call_proof": {
                "ref": _relative(paths["analysis_successor_zero_call_proof"]),
                "sha256": _sha(paths["analysis_successor_zero_call_proof"]),
                "result_digest": analysis_successor_zero["result_digest"],
            },
        }
        if analysis_successor
        and analysis_checkpoint is not None
        and analysis_successor_zero is not None
        else {}
    )

    sessions: dict[str, PreviewAgentSessionState] = {}
    node_records: list[dict[str, Any]] = []
    node_index = 0

    def state(agent_id: str) -> PreviewAgentSessionState:
        if agent_id not in sessions:
            sessions[agent_id] = start_preview_agent_session(
                agent_id=agent_id,
                run_id=run_id,
                objective_ref=f"objective://{_sha(paths['objective'])}",
                active_plan_ref="plan://pending-specialist-opinions",
            )
        return sessions[agent_id]

    def execute_node(
        *,
        agent_id: str,
        node_suffix: str,
        messages: Sequence[Mapping[str, Any]],
        tool: Mapping[str, Any],
        validator: Any,
        purpose: str,
        required_outputs: Sequence[str],
        risk: str,
        analysis_tokens: int,
        submission_tokens: int,
        resume_bound_analysis: bool = False,
    ) -> dict[str, Any]:
        nonlocal node_index
        node_index += 1
        if node_index > authority["execution_limits"]["maximum_new_model_nodes"]:
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_model_node_budget_exceeded"
            )
        execution = execute_analyzed_preview_node(
            analysis_profile=analysis_profile,
            submission_profile=submission_profile,
            session_state=state(agent_id),
            messages=messages,
            tool=tool,
            validator=validator,
            capture_root=capture_root,
            run_id=run_id,
            node_id=f"{agent_id}::{node_suffix}",
            purpose=purpose,
            input_reference_count=_input_ref_count(messages),
            required_outputs=required_outputs,
            schema_burden="one strict nested financial research tool contract",
            materiality_quality_risk=risk,
            comparable_run_evidence=(
                "DELL dynamic five-cell R7 content assessment",
                "DELL multi-agent zero-call preview v1.2",
            ),
            analysis_output_token_ceiling=analysis_tokens,
            submission_output_token_ceiling=submission_tokens,
            maximum_submission_successor_attempts=(
                authority["execution_limits"][
                    "maximum_submission_attempts_per_node"
                ]
                - 1
            ),
            analysis_checkpoint=(
                analysis_checkpoint if resume_bound_analysis else None
            ),
            analysis_checkpoint_draft=(
                analysis_checkpoint_draft if resume_bound_analysis else None
            ),
            analysis_continuation_profile=(
                continuation_profile if resume_bound_analysis else None
            ),
        )
        record = execution.as_dict()
        node_records.append(record)
        _write_new(
            private_root / f"node_{node_index:02d}_{node_suffix}.json", record
        )
        return deepcopy(dict(execution.validated_payload))

    try:
        opinions = [
            deepcopy(dict(row))
            for row in plan_checkpoint["specialist_plans"]
        ]
        opinions_by_agent = {
            str(row["agent_id"]): row for row in opinions
        }
        if set(opinions_by_agent) != set(SPECIALIST_AGENT_IDS):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_checkpoint_specialist_set_invalid"
            )
        checkpoint_ref = (
            "checkpoint://" + str(plan_checkpoint["checkpoint_digest"])
        )
        for agent_id in SPECIALIST_AGENT_IDS:
            state(agent_id).append(
                event_type="plan_bound",
                actor_id="HARNESS::R3_PLAN_CHECKPOINT",
                input_refs=(
                    checkpoint_ref,
                    "predecessor-run://" + str(
                        plan_checkpoint["predecessor_run_id"]
                    ),
                ),
                output_refs=(
                    "plan-opinion://"
                    + str(opinions_by_agent[agent_id]["plan_opinion_digest"]),
                ),
            )

        lead_messages = compile_lead_plan_messages(
            topology=topology,
            objective=objective_payload,
            opinions=opinions,
        )
        lead = execute_node(
            agent_id=RESEARCH_LEAD_AGENT_ID,
            node_suffix="LEAD_PLAN",
            messages=lead_messages,
            tool=lead_plan_tool(topology=topology),
            validator=lambda payload: validate_lead_plan(
                payload, opinions=opinions, topology=topology
            ),
            purpose="汇总六个独立角色意见，覆盖全部研究面并冻结协调问题和终止条件。",
            required_outputs=(
                "accepted_agent_ids",
                "accepted_facets",
                "coordination_questions",
                "expected_information_boundaries",
                "stop_conditions",
            ),
            risk="dropping a role or Evidence Slot would create a structurally incomplete preview",
            analysis_tokens=4000 if analysis_successor else 12000,
            submission_tokens=4000,
            resume_bound_analysis=analysis_successor,
        )
        plan_ref = f"plan://{lead['lead_plan_digest']}"
        for session_state in sessions.values():
            rebind_preview_session_plan(session_state, active_plan_ref=plan_ref)

        materialization = compile_multi_agent_preview_materialization(
            repo_root=ROOT,
            topology=topology,
            objective_payload=objective_payload,
            opinions=opinions,
            lead_plan=lead,
        )
        readiness = materialization.readiness_summary()
        if readiness["blocking_empty_role_ids"]:
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_role_authority_empty_after_materialization"
            )
        contexts = materialization.context_by_agent()

        workpapers_by_agent: dict[str, dict[str, Any]] = {}
        for agent_id in lead["ordered_agent_ids"]:
            context = contexts[agent_id]
            messages = compile_specialist_workpaper_messages(context=context)
            workpapers_by_agent[agent_id] = execute_node(
                agent_id=agent_id,
                node_suffix="WORKPAPER_R1",
                messages=messages,
                tool=specialist_workpaper_tool(
                    agent_id=agent_id, context=context
                ),
                validator=lambda payload, current=agent_id, current_context=context: validate_specialist_workpaper(
                    payload,
                    context=current_context,
                    expected_agent_id=current,
                ),
                purpose="使用本角色已审证据、数字事实和关系上下文形成完整金融研究底稿。",
                required_outputs=(
                    "thesis",
                    "sourced_claims",
                    "mechanism",
                    "alternative_explanations",
                    "strongest_counterarguments",
                    "what_would_change",
                    "stop_reason",
                ),
                risk="false absence, causal overreach or cross-company attribution is material L1/L2 risk",
                analysis_tokens=16000,
                submission_tokens=8000,
            )

        initial_workpapers = [
            workpapers_by_agent[agent_id] for agent_id in lead["ordered_agent_ids"]
        ]
        challenge_catalog = compile_challenge_catalog(
            workpapers=initial_workpapers
        )
        coordination = execute_node(
            agent_id=RESEARCH_LEAD_AGENT_ID,
            node_suffix="COORDINATION_R1",
            messages=compile_lead_coordination_messages(
                workpapers=initial_workpapers,
                challenge_catalog=challenge_catalog,
            ),
            tool=lead_coordination_tool(challenge_catalog=challenge_catalog),
            validator=lambda payload: validate_lead_coordination_decision(
                payload, challenge_catalog=challenge_catalog
            ),
            purpose="审查跨角色挑战并把可局部修正问题路由回原角色，把数据或 Harness 缺陷留在原责任层。",
            required_outputs=(
                "accepted_challenge_ids",
                "deferred_challenge_ids",
                "coordination_rationale",
                "next_state",
            ),
            risk="misrouting a data defect to an agent would create false conclusions and hide the root cause",
            analysis_tokens=16000,
            submission_tokens=4500,
        )

        challenge_by_id = {
            str(row["challenge_id"]): row for row in challenge_catalog
        }
        accepted_challenges = [
            challenge_by_id[challenge_id]
            for challenge_id in coordination["accepted_challenge_ids"]
        ]
        counter_repairs = 0
        for challenge in accepted_challenges:
            target = str(challenge["target_agent_id"])
            receipt = compile_cross_role_feedback_receipt(
                target_session_id=state(target).session["session_id"],
                challenge=challenge,
            )
            prior = workpapers_by_agent[target]
            _checkpoint_and_resume_for_feedback(
                state=state(target),
                context=contexts[target],
                prior_workpaper=prior,
                feedback_receipts=[receipt],
                objective_digest=canonical_digest(objective_payload),
                plan_digest=lead["lead_plan_digest"],
            )
            repaired_context = compile_specialist_context(
                topology=topology,
                agent_id=target,
                research_input=materialization.research_input,
                tool_execution_input=materialization.dynamic_research_input,
                case_truth_packet=materialization.case_truth_packet,
                plan_opinion=next(row for row in opinions if row["agent_id"] == target),
                lead_plan=lead,
                feedback_receipts=[receipt],
                prior_workpaper=prior,
            )
            workpapers_by_agent[target] = execute_node(
                agent_id=target,
                node_suffix="COUNTER_REPAIR",
                messages=compile_specialist_workpaper_messages(
                    context=repaired_context
                ),
                tool=specialist_workpaper_tool(
                    agent_id=target, context=repaired_context
                ),
                validator=lambda payload, current=target, current_context=repaired_context: validate_specialist_workpaper(
                    payload,
                    context=current_context,
                    expected_agent_id=current,
                ),
                purpose="消费研究负责人的已接受反方反馈，只修正受影响判断并保留全部证据边界。",
                required_outputs=(
                    "revised_thesis",
                    "revised_sourced_claims",
                    "revised_counterarguments",
                    "revised_what_would_change",
                ),
                risk="repair must narrow or correct the judgment without inventing new authority",
                analysis_tokens=12000,
                submission_tokens=8000,
            )
            counter_repairs += 1

        evaluations: list[dict[str, Any]] = []
        evaluator_state = state("EVAL::L1_AND_CONTENT")
        rebind_preview_session_plan(evaluator_state, active_plan_ref=plan_ref)
        evaluator_repairs = 0
        for evaluation_round in (1, 2):
            current_workpapers = [
                workpapers_by_agent[agent_id]
                for agent_id in lead["ordered_agent_ids"]
            ]
            model_evaluation = execute_node(
                agent_id="EVAL::L1_AND_CONTENT",
                node_suffix=f"EVALUATION_R{evaluation_round}",
                messages=compile_evaluation_messages(
                    workpapers=current_workpapers,
                    case_truth_model_view=compile_case_truth_model_view(
                        materialization.case_truth_packet
                    ),
                ),
                tool=evaluation_tool(),
                validator=lambda payload, current=current_workpapers: validate_evaluation(
                    payload, workpapers=current
                ),
                purpose="独立检查事实、期间、引用、因果边界、角色冲突与最早责任层，不代写结论。",
                required_outputs=(
                    "findings",
                    "cross_role_conflicts",
                    "report_may_proceed",
                ),
                risk="a false pass would publish materially wrong financial research; a false block would hide agent capability",
                analysis_tokens=16000,
                submission_tokens=7000,
            )
            local_findings = local_case_absence_findings(
                workpapers=current_workpapers,
                case_truth_model_view=compile_case_truth_model_view(
                    materialization.case_truth_packet
                ),
            )
            evaluation = _merge_local_evaluation(
                model_evaluation=model_evaluation,
                local_findings=local_findings,
                workpapers=current_workpapers,
            )
            evaluations.append(evaluation)
            if evaluation["report_may_proceed"] or evaluation_round == 2:
                break
            repairable = [
                row
                for row in evaluation["findings"]
                if row["blocks_report"]
                and row["failure_owner"]
                in {"agent_orchestration_and_role_design", "model_judgment"}
            ][: authority["execution_limits"]["maximum_evaluator_repairs"]]
            unrepairable = [
                row
                for row in evaluation["findings"]
                if row["blocks_report"]
                and row["failure_owner"]
                in {"data_infrastructure_or_tool", "harness_control"}
            ]
            if unrepairable or not repairable:
                break
            by_target: dict[str, list[dict[str, Any]]] = {}
            for finding in repairable:
                target = str(finding["target_agent_id"])
                by_target.setdefault(target, []).append(
                    _compile_evaluator_feedback_receipt(
                        target_session_id=state(target).session["session_id"],
                        finding=finding,
                    )
                )
            for target, receipts in by_target.items():
                prior = workpapers_by_agent[target]
                _checkpoint_and_resume_for_feedback(
                    state=state(target),
                    context=contexts[target],
                    prior_workpaper=prior,
                    feedback_receipts=receipts,
                    objective_digest=canonical_digest(objective_payload),
                    plan_digest=lead["lead_plan_digest"],
                )
                repaired_context = compile_specialist_context(
                    topology=topology,
                    agent_id=target,
                    research_input=materialization.research_input,
                    tool_execution_input=materialization.dynamic_research_input,
                    case_truth_packet=materialization.case_truth_packet,
                    plan_opinion=next(row for row in opinions if row["agent_id"] == target),
                    lead_plan=lead,
                    feedback_receipts=receipts,
                    prior_workpaper=prior,
                )
                workpapers_by_agent[target] = execute_node(
                    agent_id=target,
                    node_suffix=f"EVALUATOR_REPAIR_R{evaluation_round}",
                    messages=compile_specialist_workpaper_messages(
                        context=repaired_context
                    ),
                    tool=specialist_workpaper_tool(
                        agent_id=target, context=repaired_context
                    ),
                    validator=lambda payload, current=target, current_context=repaired_context: validate_specialist_workpaper(
                        payload,
                        context=current_context,
                        expected_agent_id=current,
                    ),
                    purpose="消费独立评估反馈，局部修正事实、边界或角色冲突后重新提交底稿。",
                    required_outputs=(
                        "revised_thesis",
                        "revised_sourced_claims",
                        "revised_mechanism",
                        "revised_counterarguments",
                    ),
                    risk="evaluator repair must not hide an upstream data or Harness defect",
                    analysis_tokens=12000,
                    submission_tokens=8000,
                )
                evaluator_repairs += 1

        final_evaluation = evaluations[-1]
        final_workpapers = [
            workpapers_by_agent[agent_id] for agent_id in lead["ordered_agent_ids"]
        ]
        report: dict[str, Any] | None = None
        if final_evaluation["report_may_proceed"]:
            writer_state = state(WRITER_AGENT_ID)
            rebind_preview_session_plan(writer_state, active_plan_ref=plan_ref)
            report = execute_node(
                agent_id=WRITER_AGENT_ID,
                node_suffix="REPORT_DRAFT",
                messages=compile_report_messages(
                    workpapers=final_workpapers,
                    evaluation=final_evaluation,
                ),
                tool=report_draft_tool(workpapers=final_workpapers),
                validator=lambda payload: validate_report_draft(
                    payload, workpapers=final_workpapers
                ),
                purpose="把已验收的多角色底稿编成可伸缩研报，不增加事实、数字、引用或因果关系。",
                required_outputs=(
                    "report_title",
                    "executive_thesis",
                    "sections",
                    "remaining_gaps",
                    "what_would_change",
                    "confidence_statement",
                ),
                risk="writer synthesis can reintroduce a false fact or erase material counterevidence",
                analysis_tokens=16000,
                submission_tokens=9000,
            )

        for agent_id in SPECIALIST_AGENT_IDS:
            _stop_role(
                state=state(agent_id),
                context=contexts[agent_id],
                evaluation=final_evaluation,
            )

        full_body = {
            "schema_version": full_schema,
            "status": (
                "multi_agent_preview_report_compiled_content_assessment_pending"
                if report is not None
                else "multi_agent_preview_completed_report_blocked_by_evaluation"
            ),
            "recorded_at": _now(),
            "authority_ref": _relative(authority_path),
            "authority_sha256": _sha(authority_path),
            "implementation_commit": authority["implementation_commit"],
            "case_key": "DELL",
            "research_as_of": "2026-08-06",
            "predecessor_plan_checkpoint": {
                "ref": _relative(paths["predecessor_plan_checkpoint"]),
                "sha256": _sha(paths["predecessor_plan_checkpoint"]),
                "checkpoint_digest": plan_checkpoint["checkpoint_digest"],
                "predecessor_run_id": plan_checkpoint["predecessor_run_id"],
                "reused_specialist_plan_count": 6,
            },
            "successor_zero_call_proof": {
                "ref": _relative(paths["successor_zero_call_proof"]),
                "sha256": _sha(paths["successor_zero_call_proof"]),
                "result_digest": successor_zero["result_digest"],
            },
            **analysis_successor_bindings,
            "planning_overlay": {
                "ref": _relative(paths["planning_overlay"]),
                "sha256": _sha(paths["planning_overlay"]),
                "maximum_proposed_atoms": 20,
                "maximum_evidence_requests": 12,
            },
            "opinions": opinions,
            "lead_plan": lead,
            "materialization_readiness": readiness,
            "initial_workpapers": initial_workpapers,
            "challenge_catalog": challenge_catalog,
            "lead_coordination": coordination,
            "final_workpapers": final_workpapers,
            "evaluations": evaluations,
            "report": report,
            "node_executions": node_records,
            "sessions": {
                agent_id: session_state.as_dict()
                for agent_id, session_state in sessions.items()
            },
            "execution": {
                "new_model_nodes": node_index,
                "reused_specialist_plan_count": 6,
                "new_specialist_plan_model_calls": 0,
                "analysis_calls": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase")
                    in {"analysis", "analysis_continuation"}
                ),
                "analysis_continuation_calls": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase") == "analysis_continuation"
                ),
                "submission_attempts": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase") == "submission"
                ),
                "provider_attempts": sum(
                    len(row["attempts"]) for row in node_records
                ),
                "successor_attempts": sum(
                    int(row["successor_attempt_count"]) for row in node_records
                ),
                "counter_challenge_repairs": counter_repairs,
                "evaluator_repairs": evaluator_repairs,
                "evaluation_rounds": len(evaluations),
                "external_source_network_calls": 0,
                "candidate_promotions": 0,
                "product_publication": False,
                "private_reasoning_persisted": False,
                "analysis_drafts_business_promoted": False,
            },
            "acceptance": {
                "true_independent_agent_sessions_proven": True,
                "R3_specialist_plan_checkpoint_reused_without_rerun": True,
                "analysis_submission_separation_proven": all(
                    "submission"
                    in {attempt.get("phase") for attempt in row["attempts"]}
                    and bool(
                        {attempt.get("phase") for attempt in row["attempts"]}
                        & {"analysis", "analysis_continuation"}
                    )
                    for row in node_records
                ),
                "feedback_checkpoint_resume_proven": any(
                    bool(session_state.resume_receipts)
                    for session_state in sessions.values()
                ),
                **(
                    {
                        "R4_analysis_checkpoint_resumed_once": sum(
                            1
                            for row in node_records
                            for attempt in row["attempts"]
                            if attempt.get("phase")
                            == "analysis_continuation"
                        )
                        == 1
                    }
                    if analysis_successor
                    else {}
                ),
                "report_contract_valid": report is not None,
                "formal_eight_dimension_assessment_pending": report is not None,
                "S1_pass": False,
                "S3_pass": False,
                "qualified_human_acceptance": False,
                "release_ready": False,
            },
        }
        full = {**full_body, "full_result_digest": canonical_digest(full_body)}
        full_path = private_root / "full_result.json"
        _write_new(full_path, full)
        public_body = {
            "schema_version": public_schema,
            "status": full["status"],
            "recorded_at": full["recorded_at"],
            "authority_ref": full["authority_ref"],
            "authority_sha256": full["authority_sha256"],
            "implementation_commit": full["implementation_commit"],
            "case_key": "DELL",
            "research_as_of": "2026-08-06",
            "predecessor_plan_checkpoint": full[
                "predecessor_plan_checkpoint"
            ],
            "successor_zero_call_proof": full["successor_zero_call_proof"],
            **analysis_successor_bindings,
            "planning_overlay": full["planning_overlay"],
            "role_inventory": {
                "declared_true_agent_ids": [
                    RESEARCH_LEAD_AGENT_ID,
                    *SPECIALIST_AGENT_IDS,
                    WRITER_AGENT_ID,
                ],
                "activated_true_agent_ids": [
                    agent_id
                    for agent_id in [
                        RESEARCH_LEAD_AGENT_ID,
                        *SPECIALIST_AGENT_IDS,
                        WRITER_AGENT_ID,
                    ]
                    if agent_id in sessions
                ],
                "evaluator_execution_ids": ["EVAL::L1_AND_CONTENT"],
                "tools_and_label_roles_remain_non_agents": True,
            },
            "materialization_readiness": readiness,
            "collaboration": {
                "independent_specialist_opinions": len(opinions),
                "independent_specialist_workpapers": len(final_workpapers),
                "cross_role_challenges": len(challenge_catalog),
                "accepted_challenges": len(
                    coordination["accepted_challenge_ids"]
                ),
                "feedback_checkpoint_resume_cycles": sum(
                    len(session_state.resume_receipts)
                    for session_state in sessions.values()
                ),
                "evaluation_rounds": len(evaluations),
                "blocking_findings": [
                    {
                        "finding_code": row["finding_code"],
                        "severity": row["severity"],
                        "target_agent_id": row["target_agent_id"],
                        "failure_owner": row["failure_owner"],
                        "explanation": row["explanation"],
                    }
                    for row in final_evaluation["findings"]
                    if row["blocks_report"]
                ],
            },
            "report_preview": report,
            "execution": full["execution"],
            "acceptance": full["acceptance"],
            "historical_comparison_ref": _relative(
                paths["historical_five_cell_assessment"]
            ),
            "full_result_ref": _relative(full_path),
            "full_result_sha256": _sha(full_path),
            "known_boundary": (
                (
                    "This is one DELL R4-analysis-checkpoint feedback-and-"
                    "continuation Multi-Agent Preview successor over unchanged "
                    "current local S1/S2 authority. The incomplete Research Lead "
                    "draft was preserved as non-business evidence, resumed once "
                    "only for its missing outputs, then submitted through the "
                    "existing strict contract. "
                )
                if analysis_successor
                else (
                    "This is one DELL R3-plan-checkpoint Multi-Agent Preview "
                    "successor over unchanged current local S1/S2 authority. Six "
                    "validated specialist plans were reused without paid reruns; "
                    "all new nodes separated visible analysis from strict submission. "
                )
            )
            + (
                "It does not qualify open-web research, S1, S3, generalization, "
                "qualified-human acceptance, Workbench publication or release."
            ),
        }
        public = {**public_body, "result_digest": canonical_digest(public_body)}
        _write_new(public_result_path, public)
        return public
    except Exception as exc:
        failure_code = str(getattr(exc, "code", "") or str(exc) or type(exc).__name__)
        terminal_attempts = [
            deepcopy(dict(row))
            for row in getattr(exc, "attempts", ())
        ]
        failure_body = {
            "schema_version": full_schema,
            "status": "multi_agent_preview_terminal_failure_preserved",
            "recorded_at": _now(),
            "authority_ref": _relative(authority_path),
            "implementation_commit": authority["implementation_commit"],
            "failure_code": failure_code,
            "failure_type": type(exc).__name__,
            "predecessor_plan_checkpoint": {
                "ref": _relative(paths["predecessor_plan_checkpoint"]),
                "sha256": _sha(paths["predecessor_plan_checkpoint"]),
                "checkpoint_digest": plan_checkpoint["checkpoint_digest"],
                "reused_specialist_plan_count": 6,
            },
            "successor_zero_call_proof": {
                "ref": _relative(paths["successor_zero_call_proof"]),
                "sha256": _sha(paths["successor_zero_call_proof"]),
                "result_digest": successor_zero["result_digest"],
            },
            **analysis_successor_bindings,
            "planning_overlay": {
                "ref": _relative(paths["planning_overlay"]),
                "sha256": _sha(paths["planning_overlay"]),
                "maximum_proposed_atoms": 20,
                "maximum_evidence_requests": 12,
            },
            "terminal_node_attempts": terminal_attempts,
            "node_executions": node_records,
            "sessions": {
                agent_id: session_state.as_dict()
                for agent_id, session_state in sessions.items()
            },
            "execution": {
                "new_model_nodes_started": node_index,
                "reused_specialist_plan_count": 6,
                "new_specialist_plan_model_calls": 0,
                "analysis_calls_preserved": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase")
                    in {"analysis", "analysis_continuation"}
                )
                + sum(
                    1
                    for attempt in terminal_attempts
                    if attempt.get("phase")
                    in {"analysis", "analysis_continuation"}
                ),
                "analysis_continuation_calls_preserved": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase") == "analysis_continuation"
                )
                + sum(
                    1
                    for attempt in terminal_attempts
                    if attempt.get("phase") == "analysis_continuation"
                ),
                "submission_attempts_preserved": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase") == "submission"
                )
                + sum(
                    1
                    for attempt in terminal_attempts
                    if attempt.get("phase") == "submission"
                ),
                "provider_attempts_preserved": sum(
                    len(row["attempts"]) for row in node_records
                )
                + len(terminal_attempts),
                "external_source_network_calls": 0,
                "candidate_promotions": 0,
                "product_publication": False,
                "analysis_drafts_business_promoted": False,
            },
        }
        failure = {
            **failure_body,
            "full_result_digest": canonical_digest(failure_body),
        }
        _write_new(private_root / "terminal_failure.json", failure)
        public_body = {
            "schema_version": public_schema,
            "status": failure["status"],
            "recorded_at": failure["recorded_at"],
            "authority_ref": failure["authority_ref"],
            "implementation_commit": failure["implementation_commit"],
            "failure_code": failure_code,
            "predecessor_plan_checkpoint": failure[
                "predecessor_plan_checkpoint"
            ],
            "successor_zero_call_proof": failure[
                "successor_zero_call_proof"
            ],
            **analysis_successor_bindings,
            "planning_overlay": failure["planning_overlay"],
            "execution": failure["execution"],
            "full_result_ref": _relative(private_root / "terminal_failure.json"),
            "acceptance": {
                "true_multi_agent_preview_completed": False,
                "S1_pass": False,
                "S3_pass": False,
                "qualified_human_acceptance": False,
                "release_ready": False,
            },
        }
        public = {**public_body, "result_digest": canonical_digest(public_body)}
        _write_new(public_result_path, public)
        return public


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    args = parser.parse_args(argv)
    result = run(_resolve(args.authority))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"].startswith("multi_agent_preview_") and "failure" not in result["status"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
