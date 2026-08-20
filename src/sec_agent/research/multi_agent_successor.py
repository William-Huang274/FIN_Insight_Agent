from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime import canonical_digest
from sec_agent.research.multi_agent_preview import (
    revalidate_bound_specialist_workpaper,
    validate_specialist_workpaper,
)


SUCCESSOR_FRONTIER_SCHEMA_VERSION = (
    "fin_ia_multi_agent_successor_execution_frontier_v1_0"
)
SUCCESSOR_FRONTIER_STATUS = (
    "completed_and_pending_nodes_compiled_from_immutable_lineage"
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
    execution_limits = {
        "maximum_new_model_nodes": fresh_count + 5,
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
    body = {
        "schema_version": SUCCESSOR_FRONTIER_SCHEMA_VERSION,
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
        },
    }
    return {**body, "result_digest": canonical_digest(body)}


def validate_successor_execution_frontier(
    frontier: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(frontier))
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
    supplied_digest = str(value.pop("result_digest", ""))
    _require(
        set(frontier) == expected_fields
        and value.get("schema_version") == SUCCESSOR_FRONTIER_SCHEMA_VERSION
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
    )
    _require(
        rebuilt == dict(frontier),
        "multi_agent_successor_frontier_recompile_drift",
    )
    return rebuilt
