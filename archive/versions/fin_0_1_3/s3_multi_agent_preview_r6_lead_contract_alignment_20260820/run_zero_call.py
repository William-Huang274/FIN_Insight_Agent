from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.canonical_runtime import canonical_digest  # noqa: E402
from sec_agent.research.multi_agent_preview import (  # noqa: E402
    MultiAgentPreviewError,
    compile_lead_plan_cardinality_policy,
    compile_lead_plan_checkpoint,
    compile_tool_contract_constraints,
    compile_tool_contract_failure_feedback,
    lead_plan_tool,
    load_multi_agent_role_topology,
    validate_lead_plan,
    validate_lead_plan_checkpoint,
    validate_specialist_plan_checkpoint,
)


TOPOLOGY = ROOT / "configs/research/fin_ia_0_1_3_multi_agent_role_topology_v1_0.json"
PLAN_CHECKPOINT = ROOT / (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R3_specialist_plan_checkpoint_v1_0.json"
)
R6_AUTHORITY = ROOT / (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "live_authority_v1_5.json"
)
R6_RESULT = ROOT / (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "live_result_v1_5.json"
)
R6_CAPTURE_ROOT = ROOT / (
    "data/captures/fin_0_1_3_s3_dell_multi_agent_preview_r6_20260820/"
    "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R6_20260820"
)
ATTEMPT_PREFIX = (
    "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R6_20260820-"
    "AGENT-RESEARCH_LEAD-LEAD_PLAN-SUBMISSION-ATTEMPT-"
)
LEAD_CHECKPOINT = ROOT / (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R6_lead_plan_checkpoint_v1_0.json"
)
RESULT = ROOT / (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R7_lead_contract_alignment_zero_call_result_v1_0.json"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ref(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )


def _capture_paths(attempt: int) -> tuple[Path, Path]:
    root = R6_CAPTURE_ROOT / f"{ATTEMPT_PREFIX}{attempt:02d}"
    return root / "model_visible_request.json", root / "provider_response.json"


def _tool_payload(response: Mapping[str, Any]) -> dict[str, Any]:
    try:
        message = response["response_body"]["choices"][0]["message"]
        calls = message["tool_calls"]
        function = calls[0]["function"]
        payload = json.loads(str(function["arguments"]))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("R6_lead_submission_capture_invalid") from exc
    if not (
        response.get("response_body_complete") is True
        and response.get("eligible_for_business_promotion") is False
        and response["response_body"]["choices"][0].get("finish_reason")
        == "tool_calls"
        and len(calls) == 1
        and function.get("name") == "submit_lead_plan"
        and isinstance(payload, dict)
    ):
        raise RuntimeError("R6_lead_submission_capture_shape_invalid")
    return payload


def _rejects(
    payload: Mapping[str, Any],
    *,
    opinions: list[dict[str, Any]],
    topology: Mapping[str, Any],
    expected_code: str,
) -> bool:
    try:
        validate_lead_plan(payload, opinions=opinions, topology=topology)
    except MultiAgentPreviewError as exc:
        return exc.code == expected_code
    return False


def run() -> dict[str, Any]:
    topology = load_multi_agent_role_topology(_json(TOPOLOGY))
    specialist_checkpoint = validate_specialist_plan_checkpoint(
        _json(PLAN_CHECKPOINT), topology=topology
    )
    opinions = [deepcopy(dict(row)) for row in specialist_checkpoint["specialist_plans"]]
    authority = _json(R6_AUTHORITY)
    public_result = _json(R6_RESULT)
    if not (
        authority.get("schema_version")
        == "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_5"
        and public_result.get("status")
        == "multi_agent_preview_terminal_failure_preserved"
        and public_result.get("failure_code")
        == "multi_agent_lead_coordination_questions_invalid"
        and public_result.get("result_digest")
        == "d65591c604c34f9ce10e3ea0d28807afb1af6073519915cb28694b2bda7e2283"
        and (public_result.get("execution") or {}).get(
            "provider_attempts_preserved"
        )
        == 2
        and (public_result.get("execution") or {}).get(
            "new_specialist_plan_model_calls"
        )
        == 0
        and (public_result.get("acceptance") or {}).get(
            "true_multi_agent_preview_completed"
        )
        is False
    ):
        raise RuntimeError("R6_public_failure_binding_invalid")

    attempts: list[dict[str, Any]] = []
    for attempt in (1, 2):
        request_path, response_path = _capture_paths(attempt)
        request = _json(request_path)
        response = _json(response_path)
        payload = _tool_payload(response)
        old_tool = request["request_body"]["tools"][0]
        old_feedback = compile_tool_contract_failure_feedback(
            tool=old_tool,
            payload=payload,
            failure_code="multi_agent_lead_coordination_questions_invalid",
        )
        violations = {
            (row.get("field"), row.get("rule"), row.get("observed"), row.get("allowed_maximum"))
            for row in old_feedback["violations"]
        }
        expected_violations = {
            ("coordination_questions", "maxItems", 13, 8),
            ("expected_information_boundaries", "maxItems", 11, 10),
            ("stop_conditions", "maxItems", 9, 8),
        }
        if not (
            request.get("attempt_id", "").endswith(f"ATTEMPT-{attempt:02d}")
            and response.get("attempt_id") == request.get("attempt_id")
            and expected_violations.issubset(violations)
        ):
            raise RuntimeError(f"R6_attempt_{attempt}_old_contract_replay_invalid")
        attempts.append(
            {
                "attempt_id": request["attempt_id"],
                "request_path": request_path,
                "response_path": response_path,
                "request": request,
                "response": response,
                "payload": payload,
                "old_feedback": old_feedback,
            }
        )

    current_policy = compile_lead_plan_cardinality_policy(topology=topology)
    current_tool = lead_plan_tool(topology=topology)
    current_constraints = compile_tool_contract_constraints(current_tool)
    expected_maxima = {
        field: current_constraints["field_constraints"][field]["maxItems"]
        for field in (
            "coordination_questions",
            "expected_information_boundaries",
            "stop_conditions",
        )
    }
    if expected_maxima != {
        "coordination_questions": 13,
        "expected_information_boundaries": 13,
        "stop_conditions": 9,
    }:
        raise RuntimeError("topology_derived_lead_capacity_invalid")

    first_payload = attempts[0]["payload"]
    second_payload = attempts[1]["payload"]
    first_validated = validate_lead_plan(
        first_payload, opinions=opinions, topology=topology
    )
    second_validated = validate_lead_plan(
        second_payload, opinions=opinions, topology=topology
    )
    del first_validated
    # Attempt 1 carried a stale literal ('the eleven coordination questions')
    # inside one stop condition.  Attempt 2 removed that contradiction while
    # preserving all 13 substantive questions, so only Attempt 2 is checkpointed.
    first_stale_count = any(
        "eleven coordination questions" in row.casefold()
        for row in first_payload["stop_conditions"]
    )
    second_stale_count = any(
        "eleven coordination questions" in row.casefold()
        for row in second_payload["stop_conditions"]
    )
    if not first_stale_count or second_stale_count:
        raise RuntimeError("R6_attempt_selection_semantic_consistency_invalid")

    over_coordination = deepcopy(second_payload)
    over_coordination["coordination_questions"].append(
        "An additional coordination question must fail closed beyond topology capacity."
    )
    over_boundaries = deepcopy(second_payload)
    over_boundaries["expected_information_boundaries"].extend(
        [
            "Boundary twelve remains inside the topology-derived capacity.",
            "Boundary thirteen remains inside the topology-derived capacity.",
            "Boundary fourteen must fail closed beyond topology-derived capacity.",
        ]
    )
    over_stops = deepcopy(second_payload)
    over_stops["stop_conditions"].append(
        "A tenth stop condition must fail closed beyond topology-derived capacity."
    )
    duplicate = deepcopy(second_payload)
    duplicate["coordination_questions"][1] = duplicate["coordination_questions"][0]
    unknown_facet = deepcopy(second_payload)
    unknown_facet["accepted_facets"][0] = "unknown_facet"
    negative = {
        "coordination_max_plus_one_rejected": _rejects(
            over_coordination,
            opinions=opinions,
            topology=topology,
            expected_code="multi_agent_lead_coordination_questions_invalid",
        ),
        "boundary_max_plus_one_rejected": _rejects(
            over_boundaries,
            opinions=opinions,
            topology=topology,
            expected_code="multi_agent_lead_expected_information_boundaries_invalid",
        ),
        "stop_max_plus_one_rejected": _rejects(
            over_stops,
            opinions=opinions,
            topology=topology,
            expected_code="multi_agent_lead_stop_conditions_invalid",
        ),
        "duplicate_coordination_rejected": _rejects(
            duplicate,
            opinions=opinions,
            topology=topology,
            expected_code="multi_agent_lead_coordination_questions_invalid",
        ),
        "unknown_facet_rejected": _rejects(
            unknown_facet,
            opinions=opinions,
            topology=topology,
            expected_code="multi_agent_lead_facets_invalid",
        ),
    }
    if not all(negative.values()):
        raise RuntimeError("lead_contract_negative_mutation_failed")

    selected = attempts[1]
    checkpoint = compile_lead_plan_checkpoint(
        case_key="DELL",
        node_id="AGENT::RESEARCH_LEAD::LEAD_PLAN",
        source_run_id=str(selected["request"]["run_id"]),
        source_authority_ref=_ref(R6_AUTHORITY),
        source_authority_sha256=_sha(R6_AUTHORITY),
        source_public_result_ref=_ref(R6_RESULT),
        source_public_result_sha256=_sha(R6_RESULT),
        source_public_result_digest=str(public_result["result_digest"]),
        source_failure_code=str(public_result["failure_code"]),
        selected_attempt_id=str(selected["request"]["attempt_id"]),
        request_capture_ref=_ref(selected["request_path"]),
        request_capture_sha256=_sha(selected["request_path"]),
        request_digest=str(selected["request"]["request_digest"]),
        response_capture_ref=_ref(selected["response_path"]),
        response_capture_sha256=_sha(selected["response_path"]),
        response_digest=str(selected["response"]["response_digest"]),
        specialist_plan_checkpoint_ref=_ref(PLAN_CHECKPOINT),
        specialist_plan_checkpoint_sha256=_sha(PLAN_CHECKPOINT),
        specialist_plan_checkpoint_digest=str(
            specialist_checkpoint["checkpoint_digest"]
        ),
        lead_plan_payload=second_payload,
        opinions=opinions,
        topology=topology,
        predecessor_contract_feedback=selected["old_feedback"],
        created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    trusted_checkpoint = validate_lead_plan_checkpoint(
        checkpoint, opinions=opinions, topology=topology
    )
    mutated_checkpoint = deepcopy(checkpoint)
    mutated_checkpoint["checkpoint_digest"] = "0" * 64
    checkpoint_digest_mutation_rejected = False
    try:
        validate_lead_plan_checkpoint(
            mutated_checkpoint, opinions=opinions, topology=topology
        )
    except MultiAgentPreviewError as exc:
        checkpoint_digest_mutation_rejected = (
            exc.code == "multi_agent_lead_plan_checkpoint_digest_invalid"
        )
    if not checkpoint_digest_mutation_rejected:
        raise RuntimeError("lead_checkpoint_digest_mutation_not_rejected")

    body = {
        "schema_version": (
            "fin_ia_s3_dell_multi_agent_preview_"
            "R7_lead_contract_alignment_zero_call_result_v1_0"
        ),
        "status": "R6_failure_preserved_lead_contract_alignment_zero_call_pass",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "case_key": "DELL",
        "bindings": {
            "topology_ref": _ref(TOPOLOGY),
            "topology_sha256": _sha(TOPOLOGY),
            "specialist_plan_checkpoint_ref": _ref(PLAN_CHECKPOINT),
            "specialist_plan_checkpoint_sha256": _sha(PLAN_CHECKPOINT),
            "R6_authority_ref": _ref(R6_AUTHORITY),
            "R6_authority_sha256": _sha(R6_AUTHORITY),
            "R6_public_result_ref": _ref(R6_RESULT),
            "R6_public_result_sha256": _sha(R6_RESULT),
            "R6_public_result_digest": public_result["result_digest"],
            "lead_plan_checkpoint_ref": _ref(LEAD_CHECKPOINT),
            "lead_plan_checkpoint_digest": trusted_checkpoint["checkpoint_digest"],
        },
        "root_cause": {
            "owning_plane": "harness_control_plane",
            "earliest_faulty_layer": (
                "Lead cardinality literals and opaque contract feedback"
            ),
            "data_or_S1_failure": False,
            "agent_research_failure": False,
            "provider_transport_failure": False,
            "schema_validator_drift": True,
            "old_schema_maxima": {
                "coordination_questions": 8,
                "expected_information_boundaries": 10,
                "stop_conditions": 8,
            },
            "old_validator_maxima": {
                "coordination_questions": 10,
                "expected_information_boundaries": 10,
                "stop_conditions": 10,
            },
            "topology_derived_maxima": expected_maxima,
        },
        "replay": {
            "attempt_count": 2,
            "selected_attempt_id": selected["request"]["attempt_id"],
            "selected_counts": {
                field: len(second_payload[field])
                for field in (
                    "coordination_questions",
                    "expected_information_boundaries",
                    "stop_conditions",
                )
            },
            "attempt_1_stale_internal_count_detected": first_stale_count,
            "attempt_2_stale_internal_count_detected": second_stale_count,
            "selected_payload_digest": canonical_digest(second_payload),
            "validated_lead_plan_digest": second_validated["lead_plan_digest"],
            "R6_status_rewritten": False,
        },
        "cardinality_policy": current_policy,
        "negative_mutations": {
            **negative,
            "checkpoint_digest_mutation_rejected": (
                checkpoint_digest_mutation_rejected
            ),
        },
        "claims": {
            "model_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "candidate_promotions": 0,
            "R6_failure_preserved": True,
            "Lead_plan_checkpoint_created": True,
            "S1_pass": False,
            "S3_pass": False,
            "true_multi_agent_preview_completed": False,
        },
    }
    result = {**body, "result_digest": canonical_digest(body)}
    _write_new(LEAD_CHECKPOINT, checkpoint)
    _write_new(RESULT, result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2, sort_keys=True))
