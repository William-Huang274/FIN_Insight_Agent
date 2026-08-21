from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime import canonical_digest
from sec_agent.research.multi_agent_preview import (
    SPECIALIST_AGENT_IDS,
    revalidate_bound_specialist_workpaper,
    validate_specialist_workpaper,
)


SUCCESSOR_FRONTIER_SCHEMA_VERSION = (
    "fin_ia_multi_agent_successor_execution_frontier_v1_0"
)
SUCCESSOR_FRONTIER_HIERARCHICAL_SCHEMA_VERSION = (
    "fin_ia_multi_agent_successor_execution_frontier_v1_1"
)
SUCCESSOR_FRONTIER_HIERARCHICAL_CHECKPOINT_SCHEMA_VERSION = (
    "fin_ia_multi_agent_successor_execution_frontier_v1_2"
)
SUCCESSOR_FRONTIER_STATUS = (
    "completed_and_pending_nodes_compiled_from_immutable_lineage"
)
MONOLITHIC_EVALUATION_STRATEGY = "claim_bound_monolithic_v1"
HIERARCHICAL_EVALUATION_STRATEGY = (
    "local_L1_six_role_content_audits_cross_role_consistency_v1"
)
HIERARCHICAL_EVALUATOR_ZERO_CALL_PROOF_SCHEMA_VERSION = (
    "fin_ia_s3_hierarchical_evaluator_zero_call_proof_v1_0"
)
HIERARCHICAL_EVALUATOR_ZERO_CALL_PROOF_STATUS = (
    "hierarchical_evaluator_capture_replay_fake_mutation_zero_call_pass"
)
COMPLETED_DISPOSITIONS = {"exact_reuse", "derived_digest_rebind"}
FRESH_DISPOSITIONS = {"fresh_rerun_required", "pending_fresh"}
ALL_DISPOSITIONS = COMPLETED_DISPOSITIONS | FRESH_DISPOSITIONS


class MultiAgentSuccessorError(ValueError):
    """Raised when a successor frontier cannot be proved fail-closed."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise MultiAgentSuccessorError(code)


def _business_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = deepcopy(dict(payload))
    raw.pop("context_digest", None)
    raw.pop("workpaper_digest", None)
    return raw


def compile_completed_workpaper_frontier_node(
    *,
    challenge_id: str,
    node_id: str,
    target_agent_id: str,
    source_run_id: str,
    source_workpaper: Mapping[str, Any],
    model_visible_context: Mapping[str, Any],
    source_terminal_ref: str,
    source_terminal_sha256: str,
    source_terminal_digest: str,
    source_request_ref: str,
    source_request_sha256: str,
    source_request_digest: str,
) -> dict[str, Any]:
    """Compile exact reuse or a derived-only rebind against visible context.

    No business field is editable here.  The exact persisted payload is stripped
    only of locally derived digests and passed through the normal workpaper
    validator against the capture-bound model-visible context.
    """

    source = deepcopy(dict(source_workpaper))
    original_workpaper_digest = str(source.get("workpaper_digest") or "")
    original_context_digest = str(source.get("context_digest") or "")
    context_digest = str(model_visible_context.get("context_digest") or "")
    _require(
        bool(challenge_id)
        and bool(node_id)
        and bool(source_run_id)
        and len(source_request_sha256) == 64
        and len(source_request_digest) == 64
        and len(source_terminal_sha256) == 64
        and len(source_terminal_digest) == 64
        and len(original_workpaper_digest) == 64
        and len(original_context_digest) == 64
        and len(context_digest) == 64,
        "multi_agent_successor_completed_identity_invalid",
    )
    business = _business_payload(source)
    normalized = validate_specialist_workpaper(
        business,
        context=model_visible_context,
        expected_agent_id=target_agent_id,
    )
    business_digest = canonical_digest(business)
    disposition = (
        "exact_reuse"
        if original_workpaper_digest == normalized["workpaper_digest"]
        and original_context_digest == normalized["context_digest"]
        else "derived_digest_rebind"
    )
    if disposition == "exact_reuse":
        revalidate_bound_specialist_workpaper(
            source,
            context=model_visible_context,
            expected_agent_id=target_agent_id,
        )
    row_body = {
        "challenge_id": challenge_id,
        "target_agent_id": target_agent_id,
        "node_id": node_id,
        "disposition": disposition,
        "source_run_id": source_run_id,
        "source_terminal_ref": source_terminal_ref,
        "source_terminal_sha256": source_terminal_sha256,
        "source_terminal_digest": source_terminal_digest,
        "source_request_ref": source_request_ref,
        "source_request_sha256": source_request_sha256,
        "source_request_digest": source_request_digest,
        "source_validation_context_digest": original_context_digest,
        "model_visible_context_digest": context_digest,
        "source_workpaper_digest": original_workpaper_digest,
        "business_payload_digest": business_digest,
        "normalized_workpaper_digest": normalized["workpaper_digest"],
        "business_payload_byte_equivalent": True,
        "normalized_workpaper": normalized,
    }
    return {
        **row_body,
        "node_receipt_digest": canonical_digest(row_body),
    }


def compile_fresh_frontier_node(
    *,
    challenge_id: str,
    node_id: str,
    target_agent_id: str,
    disposition: str,
    reason_code: str,
) -> dict[str, Any]:
    _require(
        disposition in FRESH_DISPOSITIONS,
        "multi_agent_successor_fresh_disposition_invalid",
    )
    row_body = {
        "challenge_id": challenge_id,
        "target_agent_id": target_agent_id,
        "node_id": node_id,
        "disposition": disposition,
        "reason_code": reason_code,
    }
    _require(
        all(str(row_body[key]).strip() for key in row_body),
        "multi_agent_successor_fresh_identity_invalid",
    )
    return {
        **row_body,
        "node_receipt_digest": canonical_digest(row_body),
    }


def compile_successor_execution_frontier(
    *,
    case_key: str,
    cell_id: str,
    accepted_challenge_ids: Sequence[str],
    lead_coordination_checkpoint_digest: str,
    predecessor_failure: Mapping[str, Any],
    nodes: Sequence[Mapping[str, Any]],
    evaluation_strategy: str = MONOLITHIC_EVALUATION_STRATEGY,
    completed_role_evaluation_agent_ids: Sequence[str] = (),
    evaluation_progress_checkpoint_digest: str = "",
) -> dict[str, Any]:
    normalized_nodes = [deepcopy(dict(row)) for row in nodes]
    accepted = [str(value) for value in accepted_challenge_ids]
    _require(
        case_key == "DELL"
        and cell_id == "MULTI_AGENT_PREVIEW"
        and len(accepted) == len(set(accepted)) == len(normalized_nodes)
        and [str(row.get("challenge_id") or "") for row in normalized_nodes]
        == accepted
        and len(lead_coordination_checkpoint_digest) == 64,
        "multi_agent_successor_frontier_identity_invalid",
    )
    for row in normalized_nodes:
        disposition = str(row.get("disposition") or "")
        receipt = str(row.get("node_receipt_digest") or "")
        unsigned = {
            key: value
            for key, value in row.items()
            if key != "node_receipt_digest"
        }
        _require(
            disposition in ALL_DISPOSITIONS
            and receipt == canonical_digest(unsigned),
            "multi_agent_successor_node_receipt_invalid",
        )
        if disposition in COMPLETED_DISPOSITIONS:
            _require(
                row.get("business_payload_byte_equivalent") is True
                and isinstance(row.get("normalized_workpaper"), Mapping)
                and row["normalized_workpaper"].get("workpaper_digest")
                == row.get("normalized_workpaper_digest"),
                "multi_agent_successor_completed_node_invalid",
            )
        else:
            _require(
                "normalized_workpaper" not in row,
                "multi_agent_successor_fresh_node_payload_forbidden",
            )
    predecessor = deepcopy(dict(predecessor_failure))
    _require(
        set(predecessor)
        == {
            "authority_ref",
            "authority_sha256",
            "public_result_ref",
            "public_result_sha256",
            "public_result_digest",
            "terminal_result_ref",
            "terminal_result_sha256",
            "terminal_result_digest",
            "failure_code",
            "provider_attempt_count",
        }
        and bool(str(predecessor.get("failure_code") or "").strip())
        and isinstance(predecessor.get("provider_attempt_count"), int)
        and predecessor["provider_attempt_count"] >= 0
        and all(
            len(str(predecessor[field])) == 64
            and all(
                ch in "0123456789abcdef"
                for ch in str(predecessor[field])
            )
            for field in (
                "authority_sha256",
                "public_result_sha256",
                "public_result_digest",
                "terminal_result_sha256",
                "terminal_result_digest",
            )
        ),
        "multi_agent_successor_predecessor_failure_invalid",
    )
    completed_count = sum(
        row["disposition"] in COMPLETED_DISPOSITIONS
        for row in normalized_nodes
    )
    fresh_count = len(normalized_nodes) - completed_count
    _require(
        evaluation_strategy
        in {MONOLITHIC_EVALUATION_STRATEGY, HIERARCHICAL_EVALUATION_STRATEGY},
        "multi_agent_successor_evaluation_strategy_invalid",
    )
    hierarchical = evaluation_strategy == HIERARCHICAL_EVALUATION_STRATEGY
    completed_role_evaluations = [
        str(agent_id) for agent_id in completed_role_evaluation_agent_ids
    ]
    _require(
        (
            hierarchical
            and completed_role_evaluations
            == list(SPECIALIST_AGENT_IDS[: len(completed_role_evaluations)])
            and len(completed_role_evaluations) <= len(SPECIALIST_AGENT_IDS)
            and (
                (not completed_role_evaluations and not evaluation_progress_checkpoint_digest)
                or (
                    bool(completed_role_evaluations)
                    and len(evaluation_progress_checkpoint_digest) == 64
                )
            )
        )
        or (
            not hierarchical
            and not completed_role_evaluations
            and not evaluation_progress_checkpoint_digest
        ),
        "multi_agent_successor_evaluation_checkpoint_invalid",
    )
    reused_role_evaluation_count = len(completed_role_evaluations)
    execution_limits = {
        "maximum_new_model_nodes": fresh_count
        + (
            13 - reused_role_evaluation_count
            if hierarchical
            else 5
        ),
        "maximum_new_lead_plan_model_calls": 0,
        "maximum_new_initial_workpaper_nodes": 0,
        "maximum_new_lead_coordination_model_calls": 0,
        "maximum_resumed_downstream_analysis_continuations": 0,
        "maximum_new_analysis_calls_per_other_node": 1,
        "maximum_submission_attempts_per_node": 2,
        "reused_specialist_plan_count": 6,
        "reused_lead_plan_count": 1,
        "reused_workpaper_count": 6,
        "reused_lead_coordination_count": 1,
        "reused_completed_challenge_repair_count": completed_count,
        "maximum_new_counter_challenge_repairs": fresh_count,
        "maximum_counter_challenge_repairs": len(normalized_nodes),
        "maximum_evaluator_repairs": 2,
        "maximum_evaluation_rounds": 2,
        "external_source_network_calls": 0,
        "candidate_promotions": 0,
        "product_publication": False,
        "qualified_human_acceptance": False,
    }
    if hierarchical:
        execution_limits.update(
            {
                "maximum_initial_role_evaluation_nodes": 6,
                "maximum_cross_role_evaluation_nodes": 2,
                "maximum_affected_role_reevaluation_nodes": 2,
            }
        )
        if completed_role_evaluations:
            execution_limits["reused_role_evaluation_count"] = (
                reused_role_evaluation_count
            )
    body = {
        "schema_version": (
            (
                SUCCESSOR_FRONTIER_HIERARCHICAL_CHECKPOINT_SCHEMA_VERSION
                if completed_role_evaluations
                else SUCCESSOR_FRONTIER_HIERARCHICAL_SCHEMA_VERSION
            )
            if hierarchical
            else SUCCESSOR_FRONTIER_SCHEMA_VERSION
        ),
        "status": SUCCESSOR_FRONTIER_STATUS,
        "case_key": case_key,
        "cell_id": cell_id,
        "accepted_challenge_ids": accepted,
        "lead_coordination_checkpoint_digest": (
            lead_coordination_checkpoint_digest
        ),
        "predecessor_failure": predecessor,
        "nodes": normalized_nodes,
        "execution_limits": execution_limits,
        "constraints": {
            "business_payload_changes_during_rebind_forbidden": True,
            "capture_bound_model_visible_context_required": True,
            "completed_node_model_rerun_forbidden": True,
            "analysis_continuation_forbidden": True,
            "research_inputs_unchanged": True,
            "external_source_network_forbidden": True,
            "candidate_promotion_forbidden": True,
            **(
                {
                    "local_full_L1_precedes_model_evaluation": True,
                    "role_scoped_content_audits_required": True,
                    "cross_role_audit_consumes_reviewed_summaries_only": True,
                    "unaffected_role_reevaluation_forbidden": True,
                }
                if hierarchical
                else {}
            ),
        },
    }
    if hierarchical:
        body["evaluation_strategy"] = evaluation_strategy
        if completed_role_evaluations:
            body["completed_role_evaluation_agent_ids"] = (
                completed_role_evaluations
            )
            body["evaluation_progress_checkpoint_digest"] = str(
                evaluation_progress_checkpoint_digest
            )
            body["execution_limits"][
                "maximum_initial_role_evaluation_nodes"
            ] = len(SPECIALIST_AGENT_IDS) - reused_role_evaluation_count
            body["constraints"][
                "completed_role_evaluation_rerun_forbidden"
            ] = True
    return {**body, "result_digest": canonical_digest(body)}


def validate_successor_execution_frontier(
    frontier: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(frontier))
    schema = str(value.get("schema_version") or "")
    hierarchical = schema in {
        SUCCESSOR_FRONTIER_HIERARCHICAL_SCHEMA_VERSION,
        SUCCESSOR_FRONTIER_HIERARCHICAL_CHECKPOINT_SCHEMA_VERSION,
    }
    checkpointed_hierarchical = (
        schema == SUCCESSOR_FRONTIER_HIERARCHICAL_CHECKPOINT_SCHEMA_VERSION
    )
    expected_fields = {
        "schema_version",
        "status",
        "case_key",
        "cell_id",
        "accepted_challenge_ids",
        "lead_coordination_checkpoint_digest",
        "predecessor_failure",
        "nodes",
        "execution_limits",
        "constraints",
        "result_digest",
    }
    if hierarchical:
        expected_fields.add("evaluation_strategy")
    if checkpointed_hierarchical:
        expected_fields.update(
            {
                "completed_role_evaluation_agent_ids",
                "evaluation_progress_checkpoint_digest",
            }
        )
    supplied_digest = str(value.pop("result_digest", ""))
    _require(
        set(frontier) == expected_fields
        and schema
        in {
            SUCCESSOR_FRONTIER_SCHEMA_VERSION,
            SUCCESSOR_FRONTIER_HIERARCHICAL_SCHEMA_VERSION,
            SUCCESSOR_FRONTIER_HIERARCHICAL_CHECKPOINT_SCHEMA_VERSION,
        }
        and value.get("status") == SUCCESSOR_FRONTIER_STATUS
        and supplied_digest == canonical_digest(value),
        "multi_agent_successor_frontier_digest_invalid",
    )
    rebuilt = compile_successor_execution_frontier(
        case_key=str(value["case_key"]),
        cell_id=str(value["cell_id"]),
        accepted_challenge_ids=value["accepted_challenge_ids"],
        lead_coordination_checkpoint_digest=str(
            value["lead_coordination_checkpoint_digest"]
        ),
        predecessor_failure=value["predecessor_failure"],
        nodes=value["nodes"],
        evaluation_strategy=(
            str(value["evaluation_strategy"])
            if hierarchical
            else MONOLITHIC_EVALUATION_STRATEGY
        ),
        completed_role_evaluation_agent_ids=(
            value["completed_role_evaluation_agent_ids"]
            if checkpointed_hierarchical
            else ()
        ),
        evaluation_progress_checkpoint_digest=(
            str(value["evaluation_progress_checkpoint_digest"])
            if checkpointed_hierarchical
            else ""
        ),
    )
    _require(
        rebuilt == dict(frontier),
        "multi_agent_successor_frontier_recompile_drift",
    )
    return rebuilt


def compile_hierarchical_evaluator_zero_call_proof(
    *,
    frontier_ref: str,
    frontier_sha256: str,
    frontier: Mapping[str, Any],
    role_view_receipts: Sequence[Mapping[str, Any]],
    cross_role_view_receipt: Mapping[str, Any],
    local_case_absence_blocking_finding_count: int,
    mutation_checks: Mapping[str, bool],
    fake_execution_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    trusted_frontier = validate_successor_execution_frontier(frontier)
    _require(
        trusted_frontier.get("evaluation_strategy")
        == HIERARCHICAL_EVALUATION_STRATEGY
        and len(frontier_sha256) == 64
        and bool(str(frontier_ref).strip()),
        "multi_agent_hierarchical_proof_frontier_invalid",
    )
    roles = [deepcopy(dict(row)) for row in role_view_receipts]
    expected_role_fields = {
        "agent_id",
        "workpaper_digest",
        "context_digest",
        "content_view_digest",
        "input_characters",
        "evidence_ref_count",
        "numeric_ref_count",
        "numeric_relation_ref_count",
        "typed_gap_ref_count",
    }
    _require(
        len(roles) == len(SPECIALIST_AGENT_IDS)
        and {str(row.get("agent_id") or "") for row in roles}
        == set(SPECIALIST_AGENT_IDS),
        "multi_agent_hierarchical_proof_role_coverage_invalid",
    )
    roles.sort(key=lambda row: str(row["agent_id"]))
    for row in roles:
        _require(
            set(row) == expected_role_fields
            and all(
                len(str(row[field])) == 64
                for field in (
                    "workpaper_digest",
                    "context_digest",
                    "content_view_digest",
                )
            )
            and 1_000 <= int(row["input_characters"]) <= 25_000
            and all(
                isinstance(row[field], int) and row[field] >= 0
                for field in (
                    "evidence_ref_count",
                    "numeric_ref_count",
                    "numeric_relation_ref_count",
                    "typed_gap_ref_count",
                )
            ),
            "multi_agent_hierarchical_proof_role_receipt_invalid",
        )
    cross = deepcopy(dict(cross_role_view_receipt))
    _require(
        set(cross)
        == {
            "cross_role_view_digest",
            "input_characters",
            "role_count",
            "referenced_authority_included",
        }
        and len(str(cross["cross_role_view_digest"])) == 64
        and 1_000 <= int(cross["input_characters"]) <= 60_000
        and cross["role_count"] == len(SPECIALIST_AGENT_IDS)
        and cross["referenced_authority_included"] is False,
        "multi_agent_hierarchical_proof_cross_receipt_invalid",
    )
    reused_role_evaluation_count = int(
        trusted_frontier["execution_limits"].get(
            "reused_role_evaluation_count", 0
        )
    )
    expected_mutations = {
        "missing_role_fails_closed",
        "wrong_role_target_fails_closed",
        "unresolved_authority_ref_fails_closed",
        "workpaper_permutation_is_stable",
        "frontier_budget_mutation_fails_closed",
        "unaffected_role_reevaluation_is_forbidden",
        *(
            {"completed_role_evaluation_rerun_is_forbidden"}
            if reused_role_evaluation_count
            else set()
        ),
    }
    checks = {str(key): value for key, value in mutation_checks.items()}
    _require(
        set(checks) == expected_mutations
        and all(value is True for value in checks.values()),
        "multi_agent_hierarchical_proof_mutation_invalid",
    )
    fake = deepcopy(dict(fake_execution_receipt))
    expected_fake = {
        "pass_without_repair_node_count": 8 - reused_role_evaluation_count,
        "maximum_two_repair_path_node_count": 13 - reused_role_evaluation_count,
        "third_repair_path_node_count": 15 - reused_role_evaluation_count,
        "maximum_authorized_model_nodes": 13 - reused_role_evaluation_count,
        "conditional_writer_count": 1,
        "unaffected_role_reevaluation_count": 0,
    }
    _require(
        fake == expected_fake
        and trusted_frontier["execution_limits"]["maximum_new_model_nodes"]
        == expected_fake["maximum_authorized_model_nodes"],
        "multi_agent_hierarchical_proof_fake_execution_invalid",
    )
    _require(
        local_case_absence_blocking_finding_count == 0,
        "multi_agent_hierarchical_proof_local_L1_blocking",
    )
    body = {
        "schema_version": HIERARCHICAL_EVALUATOR_ZERO_CALL_PROOF_SCHEMA_VERSION,
        "status": HIERARCHICAL_EVALUATOR_ZERO_CALL_PROOF_STATUS,
        "frontier_ref": str(frontier_ref),
        "frontier_sha256": str(frontier_sha256),
        "frontier_result_digest": trusted_frontier["result_digest"],
        "evaluation_strategy": HIERARCHICAL_EVALUATION_STRATEGY,
        "role_view_receipts": roles,
        "cross_role_view_receipt": cross,
        "local_case_absence_blocking_finding_count": 0,
        "mutation_checks": checks,
        "fake_execution_receipt": fake,
        "provider_model_calls": 0,
        "local_retrieval_materialization_replayed": True,
        "network_calls": 0,
        "paid_tool_calls": 0,
        "known_boundary": (
            "Capture replay and deterministic fakes prove context selection, "
            "lineage, mutation closure and node budgets; they do not prove "
            "natural evaluator judgment, Writer quality, S3 or release."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def validate_hierarchical_evaluator_zero_call_proof(
    proof: Mapping[str, Any], *, frontier: Mapping[str, Any]
) -> dict[str, Any]:
    value = deepcopy(dict(proof))
    supplied = str(value.pop("result_digest", ""))
    _require(
        set(proof)
        == {
            "schema_version",
            "status",
            "frontier_ref",
            "frontier_sha256",
            "frontier_result_digest",
            "evaluation_strategy",
            "role_view_receipts",
            "cross_role_view_receipt",
            "local_case_absence_blocking_finding_count",
            "mutation_checks",
            "fake_execution_receipt",
            "provider_model_calls",
            "local_retrieval_materialization_replayed",
            "network_calls",
            "paid_tool_calls",
            "known_boundary",
            "result_digest",
        }
        and value.get("schema_version")
        == HIERARCHICAL_EVALUATOR_ZERO_CALL_PROOF_SCHEMA_VERSION
        and value.get("status")
        == HIERARCHICAL_EVALUATOR_ZERO_CALL_PROOF_STATUS
        and value.get("provider_model_calls") == 0
        and value.get("local_retrieval_materialization_replayed") is True
        and value.get("network_calls") == 0
        and value.get("paid_tool_calls") == 0
        and supplied == canonical_digest(value),
        "multi_agent_hierarchical_proof_digest_invalid",
    )
    rebuilt = compile_hierarchical_evaluator_zero_call_proof(
        frontier_ref=str(value["frontier_ref"]),
        frontier_sha256=str(value["frontier_sha256"]),
        frontier=frontier,
        role_view_receipts=value["role_view_receipts"],
        cross_role_view_receipt=value["cross_role_view_receipt"],
        local_case_absence_blocking_finding_count=int(
            value["local_case_absence_blocking_finding_count"]
        ),
        mutation_checks=value["mutation_checks"],
        fake_execution_receipt=value["fake_execution_receipt"],
    )
    _require(
        rebuilt == dict(proof)
        and value["frontier_result_digest"]
        == validate_successor_execution_frontier(frontier)["result_digest"],
        "multi_agent_hierarchical_proof_recompile_drift",
    )
    return rebuilt
