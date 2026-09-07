from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence

from . import dell_report_internal_chain_ceiling as legacy
from .query_plan import canonical_digest


POLICY_SCHEMA_VERSION = "fin_ia_dell_report_internal_chain_ceiling_policy_v1_2"
PRIVATE_RESULT_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_ceiling_private_result_v1_1"
)
PUBLIC_RESULT_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_ceiling_public_result_v1_1"
)
AUDIT_SCHEMA_VERSION = "fin_ia_independent_readonly_audit_result_v1_0"

PROGRAM_ID = "FIN-0.1.3-S1-DELL-RSQ-03B-R3"
ATTEMPT_ID = "dell-rsq-03b-internal-chain-r3"
BRANCH = "codex/fin013-dell-s1-s2-product-bridge"

POLICY_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_2.json"
)
PRIVATE_REF = (
    "data/workbench_private/"
    "fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/"
    f"{ATTEMPT_ID}/full_result.json"
)
ATTEMPT_RECEIPT_REF = (
    "data/workbench_private/"
    "fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/"
    f"{ATTEMPT_ID}/attempt_consumed.json"
)
PUBLIC_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_2.json"
)

R1_POLICY_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_0.json"
)
R1_FAILURE_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_r1_failure_receipt_v1_0.json"
)
R2_POLICY_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_1.json"
)
R2_PUBLIC_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_1.json"
)
R2_PRIVATE_REF = (
    "data/workbench_private/"
    "fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/"
    "dell-rsq-03b-internal-chain-r2/full_result.json"
)
R2_AUDIT_REF = (
    "configs/audits/"
    "fin_ia_0_1_3_commit_2a604156_dell_03b_r2_fresh_audit_fail_v1_0.json"
)

EXPECTED_IMPLEMENTATION_PATHS = frozenset(
    {
        "src/retrieval/dell_report_internal_chain_ceiling.py",
        "src/retrieval/dell_report_internal_chain_ceiling_r3.py",
        "scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r3.py",
        "apps/workbench/backend/application/research_retrieval_service.py",
    }
)

EXECUTION_CONTRACT = {
    "request_count": 5,
    "local_embedding_inference_batches": 1,
    "candidate_union_count_per_request": 96,
    "final_review_count_per_request": 16,
    "raw_union_rank_permutation_start": 1,
    "raw_union_rank_permutation_end": 96,
    "final_output_rank_permutation_start": 1,
    "final_output_rank_permutation_end": 16,
    "network_calls": 0,
    "model_calls": 0,
    "generation_model_calls": 0,
    "provider_calls": 0,
    "external_capture_calls": 0,
    "4B_embedding_calls": 0,
    "reranker_calls": 0,
    "retries": 0,
    "current_mutations": 0,
    "candidate_promotions": 0,
    "evidence_promotions": 0,
    "gap_closures": 0,
}

SEMANTIC_CONTRACT = {
    "term_match_mode": "unicode_casefold_alphanumeric_token_or_phrase_boundary",
    "entity_relation_mode": "target_specific_subject_object_direction_required",
    "evidence_unit_mode": "same_canonical_source_record_only",
    "slice_aggregation_mode": "same_source_bounded_role_package_no_document_concat",
    "source_owner_scope_mode": "ticker_or_target_entity_and_reviewed_source_role",
    "ASP_role": "bounded_configuration_or_bundle_price_not_company_realized_ASP",
    "capacity_role": "product_availability_separate_from_upstream_Dell_allocation",
    "supplier_role": "relationship_delivery_separate_from_capacity_allocation",
    "units_role": "server_or_system_shipments_not_GPU_counts_or_procurement_purchases",
    "source_to_object_semantic_coverage_required": True,
    "reranker_useful_at_k": 10,
    "candidate_not_evidence": True,
}

AUTHORITY = {
    "03B_internal_chain_execution_authorized": True,
    "current_0_6B_query_embedding_authorized": True,
    "network_authorized": False,
    "external_capture_authorized": False,
    "4B_embedding_authorized": False,
    "reranker_authorized": False,
    "candidate_decision_authorized": False,
    "evidence_promotion_authorized": False,
    "gap_closure_authorized": False,
    "public_information_boundary_authorized": False,
}

INHERITED_WITHOUT_CHANGE = [
    "six_unoverlapped_targets_and_three_qualified_human_held_targets",
    "five_frozen_request_payloads_and_current_R38_inputs",
    "BM25_Qwen0_6B_typed_graph_candidate_generation",
    "one_fresh_local_query_embedding_batch_and_zero_paid_or_external_calls",
    "candidate_not_evidence_and_zero_promotion_or_gap_closure",
    "R1_terminal_failure_and_R2_bytes_remain_immutable",
]

ONLY_SUCCESSOR_CHANGES = {
    "execution_seal": "exact_raw_receipt_five_unique_requests_96_16_ranks_all_authority_fields",
    "attempt_seal": "exact_branch_implementation_parent_canonical_paths_consumption_receipt",
    "publication": "exclusive_atomic_private_public_pair_with_rollback",
    "term_semantics": "token_entity_boundary_and_directional_relationships",
    "evidence_unit": "bounded_same_source_role_package_across_adjacent_slices",
    "scope_separation": "configuration_vs_company_ASP_availability_vs_allocation_relationship_vs_capacity",
    "semantic_coverage": "source_record_to_compiled_object_material_sentence_gate",
    "eligibility": "recompute_4B_reranker_and_residual_03C_after_semantic_repair",
    "R2_result_or_scores_reused": False,
    "fresh_R3_query_embedding_batch_required": True,
}

ZERO_EXECUTION_FIELDS = (
    "network_calls",
    "model_calls",
    "generation_model_calls",
    "provider_calls",
    "external_capture_calls",
    "4B_embedding_calls",
    "reranker_calls",
    "retries",
    "current_mutations",
    "candidate_promotions",
    "evidence_promotions",
    "gap_closures",
)


class DellReportInternalChainCeilingR3Error(ValueError):
    """Raised when the R3 successor cannot prove its bounded contract."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellReportInternalChainCeilingR3Error(code)


def _mapping(value: Any, code: str) -> dict[str, Any]:
    _require(isinstance(value, Mapping), code)
    return dict(value)


def _sequence(value: Any, code: str) -> list[Any]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes)), code
    )
    return list(value)


def _nonblank(value: Any, code: str) -> str:
    text = str(value or "").strip()
    _require(bool(text), code)
    return text


def _exact_int(value: Any, expected: int, code: str) -> int:
    _require(type(value) is int and value == expected, code)
    return value


def _self_digest(value: Mapping[str, Any], field: str = "result_digest") -> bool:
    body = {key: row for key, row in value.items() if key != field}
    return value.get(field) == canonical_digest(body)


def validate_dell_report_internal_chain_ceiling_r3_policy(
    policy: Mapping[str, Any],
    *,
    r2_policy: Mapping[str, Any],
    r1_policy: Mapping[str, Any],
    r1_failure_receipt: Mapping[str, Any],
    r2_public_result: Mapping[str, Any],
    r2_private_result: Mapping[str, Any],
    r2_audit: Mapping[str, Any],
    residual_program: Mapping[str, Any],
    execution_program: Mapping[str, Any],
    runtime_registry: Mapping[str, Any],
    runtime_binding_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate R3 and return its immutable R1 target/request contract."""

    inherited = legacy.validate_dell_report_internal_chain_ceiling_successor_policy(
        r2_policy,
        predecessor_policy=r1_policy,
        predecessor_failure_receipt=r1_failure_receipt,
        residual_program=residual_program,
        execution_program=execution_program,
        runtime_registry=runtime_registry,
        runtime_binding_receipt=runtime_binding_receipt,
    )
    value = dict(policy)
    _require(
        value.get("schema_version") == POLICY_SCHEMA_VERSION,
        "dell_03B_R3_policy_schema_invalid",
    )
    _require(
        value.get("status")
        == "same_stage_R3_execution_authorized_after_fresh_R2_audit_failure",
        "dell_03B_R3_policy_status_invalid",
    )
    _require(
        value.get("program_id") == PROGRAM_ID
        and value.get("attempt_id") == ATTEMPT_ID,
        "dell_03B_R3_identity_invalid",
    )
    _require(_self_digest(value), "dell_03B_R3_policy_digest_invalid")

    predecessor = _mapping(
        value.get("predecessor"), "dell_03B_R3_predecessor_invalid"
    )
    expected_refs = {
        "R1_policy_ref": R1_POLICY_REF,
        "R1_failure_ref": R1_FAILURE_REF,
        "R2_policy_ref": R2_POLICY_REF,
        "R2_public_ref": R2_PUBLIC_REF,
        "R2_private_ref": R2_PRIVATE_REF,
        "R2_audit_ref": R2_AUDIT_REF,
    }
    _require(
        all(predecessor.get(key) == expected for key, expected in expected_refs.items()),
        "dell_03B_R3_predecessor_ref_invalid",
    )
    for field in (
        "R1_policy_sha256",
        "R1_failure_sha256",
        "R2_policy_sha256",
        "R2_public_sha256",
        "R2_private_sha256",
        "R2_audit_sha256",
    ):
        _require(
            re.fullmatch(r"[0-9a-f]{64}", str(predecessor.get(field) or ""))
            is not None,
            f"dell_03B_R3_predecessor_sha_invalid:{field}",
        )
    _require(
        predecessor.get("R2_result_commit")
        == "2a604156777a027d06a15c3e379632d945c70703"
        and predecessor.get("R2_result_tree")
        == "2baf3d50282f1cd76c9775e429d0556bbc631da5"
        and predecessor.get("R2_audit_digest") == r2_audit.get("result_digest")
        and predecessor.get("R2_public_digest")
        == r2_public_result.get("result_digest")
        and predecessor.get("R2_private_digest")
        == r2_private_result.get("result_digest"),
        "dell_03B_R3_predecessor_identity_invalid",
    )
    _require(
        _self_digest(r2_public_result)
        and _self_digest(r2_private_result)
        and _self_digest(r2_audit)
        and r2_public_result.get("private_result_digest")
        == r2_private_result.get("result_digest")
        and r2_public_result.get("attempt_id")
        == r2_private_result.get("attempt_id")
        == "dell-rsq-03b-internal-chain-r2",
        "dell_03B_R3_R2_result_integrity_invalid",
    )
    _require(
        r2_audit.get("schema_version") == AUDIT_SCHEMA_VERSION
        and r2_audit.get("status")
        == "fail_material_findings_preserved_same_stage_R3_required"
        and r2_audit.get("reviewed_identity", {}).get("commit")
        == predecessor.get("R2_result_commit")
        and r2_audit.get("verdicts", {}).get("03B_pass") is False
        and r2_audit.get("next_legal_action", "").startswith("Preserve R2"),
        "dell_03B_R3_audit_failure_binding_invalid",
    )

    _require(
        value.get("inherited_without_change") == INHERITED_WITHOUT_CHANGE,
        "dell_03B_R3_inheritance_invalid",
    )
    _require(
        value.get("only_successor_changes") == ONLY_SUCCESSOR_CHANGES,
        "dell_03B_R3_delta_invalid",
    )
    _require(
        value.get("execution_contract") == EXECUTION_CONTRACT,
        "dell_03B_R3_execution_contract_invalid",
    )
    _require(
        value.get("semantic_contract") == SEMANTIC_CONTRACT,
        "dell_03B_R3_semantic_contract_invalid",
    )
    _require(
        value.get("authority") == AUTHORITY,
        "dell_03B_R3_authority_invalid",
    )
    output = _mapping(value.get("output_contract"), "dell_03B_R3_output_invalid")
    _require(
        output
        == {
            "policy_ref": POLICY_REF,
            "private_result_ref": PRIVATE_REF,
            "public_result_ref": PUBLIC_REF,
            "attempt_consumption_receipt_ref": ATTEMPT_RECEIPT_REF,
            "alternate_output_paths_authorized": False,
            "private_public_same_path_authorized": False,
            "exclusive_create_required": True,
            "atomic_pair_with_rollback_required": True,
            "same_attempt_retry_authorized": False,
        },
        "dell_03B_R3_output_contract_invalid",
    )
    execution_identity = _mapping(
        value.get("execution_identity"), "dell_03B_R3_execution_identity_invalid"
    )
    _require(
        execution_identity.get("branch") == BRANCH
        and re.fullmatch(
            r"[0-9a-f]{40}",
            str(execution_identity.get("implementation_commit") or ""),
        )
        and re.fullmatch(
            r"[0-9a-f]{40}", str(execution_identity.get("implementation_tree") or "")
        )
        and execution_identity.get("authority_commit_changed_paths") == [POLICY_REF]
        and execution_identity.get("authority_commit_parent_must_equal_implementation_commit")
        is True
        and execution_identity.get("HEAD_must_equal_upstream") is True,
        "dell_03B_R3_execution_identity_invalid",
    )
    bindings = _sequence(
        value.get("implementation_bindings"),
        "dell_03B_R3_implementation_bindings_invalid",
    )
    paths = [str(row.get("path") or "") for row in bindings if isinstance(row, Mapping)]
    _require(
        len(paths) == len(set(paths))
        and set(paths) == EXPECTED_IMPLEMENTATION_PATHS
        and all(
            isinstance(row, Mapping)
            and re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256") or ""))
            for row in bindings
        ),
        "dell_03B_R3_implementation_bindings_invalid",
    )
    token_basis = _mapping(
        value.get("TokenBudgetBasis"), "dell_03B_R3_token_budget_basis_invalid"
    )
    for field in (
        "node_purpose",
        "input_scale",
        "required_outputs",
        "schema_burden",
        "materiality_quality_risk",
        "comparable_run_evidence",
        "reasoning_profile",
        "stop_and_truncation",
    ):
        _nonblank(
            token_basis.get(field), f"dell_03B_R3_token_budget_basis_missing:{field}"
        )
    return inherited


def validate_dell_report_internal_chain_ceiling_r3_execution(
    execution: Mapping[str, Any], *, expected_request_ids: Iterable[str]
) -> dict[str, Any]:
    """Fail-close the raw current-runtime execution before semantic compilation."""

    value = dict(execution)
    _require(
        value.get("status") == "current_runtime_request_batch_zero_call_executed",
        "dell_03B_R3_execution_status_invalid",
    )
    _require(_self_digest(value, "projection_digest"), "dell_03B_R3_execution_digest_invalid")
    expected_ids = set(expected_request_ids)
    _require(len(expected_ids) == 5, "dell_03B_R3_expected_request_set_invalid")
    summary = _mapping(value.get("summary"), "dell_03B_R3_execution_summary_invalid")
    _exact_int(summary.get("request_count"), 5, "dell_03B_R3_request_count_invalid")
    _exact_int(
        summary.get("local_embedding_inference_batches"),
        1,
        "dell_03B_R3_fresh_batch_count_invalid",
    )
    for field in ZERO_EXECUTION_FIELDS:
        _exact_int(
            summary.get(field), 0, f"dell_03B_R3_execution_authority_invalid:{field}"
        )

    request_results = [
        _mapping(row, "dell_03B_R3_request_result_invalid")
        for row in _sequence(
            value.get("request_results"), "dell_03B_R3_request_results_invalid"
        )
    ]
    _require(len(request_results) == 5, "dell_03B_R3_request_result_count_invalid")
    request_ids = [
        _nonblank(
            _mapping(row.get("request"), "dell_03B_R3_request_invalid").get(
                "request_id"
            ),
            "dell_03B_R3_request_id_missing",
        )
        for row in request_results
    ]
    _require(
        len(request_ids) == len(set(request_ids)),
        "dell_03B_R3_duplicate_request_result",
    )
    _require(set(request_ids) == expected_ids, "dell_03B_R3_request_set_invalid")

    for request_id, row in zip(request_ids, request_results):
        hybrid = _mapping(
            row.get("hybrid_object_retrieval"),
            f"dell_03B_R3_hybrid_result_missing:{request_id}",
        )
        seeds = [
            _mapping(seed, f"dell_03B_R3_seed_invalid:{request_id}")
            for seed in _sequence(
                hybrid.get("candidate_decision_seed"),
                f"dell_03B_R3_seed_population_invalid:{request_id}",
            )
        ]
        candidates = [
            _mapping(candidate, f"dell_03B_R3_final_invalid:{request_id}")
            for candidate in _sequence(
                hybrid.get("candidates"),
                f"dell_03B_R3_final_population_invalid:{request_id}",
            )
        ]
        _require(len(seeds) == 96, f"dell_03B_R3_union_count_invalid:{request_id}")
        _require(
            len(candidates) == 16, f"dell_03B_R3_final_count_invalid:{request_id}"
        )
        seed_ids = [
            _nonblank(
                seed.get("compiled_object_id"),
                f"dell_03B_R3_seed_object_id_missing:{request_id}",
            )
            for seed in seeds
        ]
        final_ids = [
            _nonblank(
                candidate.get("compiled_object_id"),
                f"dell_03B_R3_final_object_id_missing:{request_id}",
            )
            for candidate in candidates
        ]
        _require(
            len(seed_ids) == len(set(seed_ids)),
            f"dell_03B_R3_seed_object_duplicate:{request_id}",
        )
        _require(
            len(final_ids) == len(set(final_ids)) and set(final_ids).issubset(seed_ids),
            f"dell_03B_R3_final_object_invalid:{request_id}",
        )
        raw_ranks: list[int] = []
        final_rank_by_id: dict[str, int] = {}
        for object_id, seed in zip(seed_ids, seeds):
            rank_trace = _mapping(
                seed.get("rank_trace"), f"dell_03B_R3_rank_trace_invalid:{request_id}"
            )
            raw_rank = rank_trace.get("raw_union_rank")
            _require(
                type(raw_rank) is int,
                f"dell_03B_R3_raw_rank_type_invalid:{request_id}",
            )
            raw_ranks.append(raw_rank)
            final_rank = rank_trace.get("final_output_rank")
            if final_rank is not None:
                _require(
                    type(final_rank) is int,
                    f"dell_03B_R3_final_rank_type_invalid:{request_id}",
                )
                final_rank_by_id[object_id] = final_rank
            _require(
                seed.get("candidate_not_evidence") is True
                and seed.get("evidence_promoted") is False
                and seed.get("numeric_authority") is False,
                f"dell_03B_R3_seed_authority_invalid:{request_id}",
            )
            route_membership = set(seed.get("route_membership") or ())
            _require(
                not any("4b" in str(route).casefold() or "rerank" in str(route).casefold() for route in route_membership),
                f"dell_03B_R3_forbidden_route_membership:{request_id}",
            )
        _require(
            set(raw_ranks) == set(range(1, 97)) and len(raw_ranks) == len(set(raw_ranks)),
            f"dell_03B_R3_raw_rank_permutation_invalid:{request_id}",
        )
        _require(
            set(final_rank_by_id) == set(final_ids)
            and set(final_rank_by_id.values()) == set(range(1, 17))
            and len(final_rank_by_id.values()) == len(set(final_rank_by_id.values())),
            f"dell_03B_R3_final_rank_permutation_invalid:{request_id}",
        )
        ordered_final_ids = [
            object_id
            for object_id, _ in sorted(final_rank_by_id.items(), key=lambda item: item[1])
        ]
        _require(
            final_ids == ordered_final_ids,
            f"dell_03B_R3_final_candidate_order_invalid:{request_id}",
        )
    return {
        "summary": summary,
        "request_results": request_results,
        "request_results_by_id": dict(zip(request_ids, request_results)),
        "raw_execution_digest": value.get("projection_digest"),
        "validated_execution_digest": canonical_digest(value),
    }


def _normalize_text(value: Any) -> str:
    text = str(value or "").casefold()
    text = text.replace("‐", "-").replace("‑", "-").replace("–", "-")
    text = text.replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def _bounded_term_hit(text: str, term: str) -> bool:
    normalized = _normalize_text(term)
    if not normalized:
        return False
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    left = r"(?<![0-9a-z])" if normalized[0].isalnum() else ""
    right = r"(?![0-9a-z])" if normalized[-1].isalnum() else ""
    return re.search(f"{left}{escaped}{right}", text) is not None


def _has_any(text: str, terms: Iterable[str]) -> bool:
    return any(_bounded_term_hit(text, term) for term in terms)


def _iso_date_in_scope(metadata: Mapping[str, Any]) -> bool:
    try:
        observed = date.fromisoformat(str(metadata.get("publication_date") or ""))
    except ValueError:
        return False
    return date(2025, 2, 1) <= observed <= date(2026, 8, 6)


def _base_groups(text: str) -> dict[str, bool]:
    dell = _has_any(text, ("dell", "poweredge", "dell ai factory"))
    ai_server = _has_any(
        text,
        (
            "ai server",
            "ai-optimized server",
            "poweredge xe",
            "poweredge ai",
            "poweredge blackwell",
            "xe9680",
            "gb200",
        ),
    )
    named_supplier = _has_any(
        text,
        (
            "nvidia",
            "micron",
            "tsmc",
            "taiwan semiconductor",
            "sk hynix",
            "broadcom",
        ),
    )
    return {"dell_subject": dell, "dell_ai_server": ai_server, "named_supplier": named_supplier}


def _classification(complete: bool, partial: bool) -> str:
    if complete:
        return "complete_bounded_target_package"
    if partial:
        return "partial_context_only"
    return "not_target_semantic_equivalent"


def classify_dell_report_internal_chain_r3_package(
    *, target_id: str, text: str, metadata: Mapping[str, Any]
) -> dict[str, Any]:
    """Classify one bounded canonical-source package with target-specific roles."""

    normalized = _normalize_text(text)
    in_period = _iso_date_in_scope(metadata)
    base = _base_groups(normalized)
    groups: dict[str, bool] = dict(base)
    limitations: list[str] = []
    role = "none"
    complete = False
    partial = False

    if target_id == "DELL-RSQ-03A-TARGET-ASP":
        groups["price_surface"] = bool(
            re.search(r"(?:usd|us\$|\$)\s*[0-9][0-9,]*(?:\.[0-9]+)?", normalized)
            or _has_any(normalized, ("quoted price", "purchase price", "configuration price"))
        )
        quantity_pattern = (
            r"(?<![0-9a-z])(?:[0-9][0-9,]*|one|two|three|four|five|six|seven|eight|nine|ten)"
            r"(?:\s*\([0-9]+\))?(?:\s+[a-z0-9-]+){0,5}\s+"
            r"(?:server units|servers|systems|nodes)(?![0-9a-z])"
        )
        groups["valid_denominator"] = bool(re.search(quantity_pattern, normalized))
        groups["bundle_boundary"] = _has_any(
            normalized,
            (
                "support",
                "service",
                "installation",
                "training",
                "switches",
                "maintenance",
                "prodeploy",
                "prosupport",
            ),
        )
        complete = (
            in_period
            and base["dell_subject"]
            and base["dell_ai_server"]
            and groups["price_surface"]
            and groups["valid_denominator"]
        )
        partial = in_period and (
            groups["price_surface"] or base["dell_ai_server"]
        )
        role = "bounded_configuration_or_bundle_price_package" if complete else "price_or_configuration_context"
        if groups["bundle_boundary"]:
            limitations.append("bundle_contains_non_hardware_or_multi_year_service_components")
        limitations.append("not_company_wide_realized_ASP")
        required = ("dell_subject", "dell_ai_server", "price_surface", "valid_denominator")

    elif target_id == "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH":
        directional_patterns = (
            r"(?:dell\s+and\s+nvidia|nvidia\s+and\s+dell).{0,100}(?:partner|collaborat)",
            r"(?:nvidia\s+and\s+dell).{0,100}partnering\s+to\s+deliver",
            r"dell\s+servers?.{0,100}(?:with|powered\s+by).{0,50}nvidia.{0,100}(?:shipping|available|deliver)",
            r"(?:allocated|allocation|deliver(?:y|ed)?|suppl(?:y|ies|ied)).{0,60}(?:to\s+)?dell",
            r"available\s+(?:from|through)\s+dell",
        )
        groups["directional_relationship_delivery"] = any(
            re.search(pattern, normalized) for pattern in directional_patterns
        )
        groups["capacity_allocation"] = bool(
            re.search(
                r"(?:capacity|allocation|supply).{0,100}(?:for|to|secured\s+by)\s+dell",
                normalized,
            )
        )
        complete = (
            in_period
            and base["dell_subject"]
            and base["named_supplier"]
            and groups["directional_relationship_delivery"]
        )
        partial = in_period and base["named_supplier"] and (
            base["dell_subject"] or groups["directional_relationship_delivery"]
        )
        role = "supplier_to_Dell_relationship_delivery" if complete else "supplier_or_relationship_context"
        if complete and not groups["capacity_allocation"]:
            limitations.append("supplier_capacity_or_allocation_readthrough_remains_open")
        required = ("dell_subject", "named_supplier", "directional_relationship_delivery")

    elif target_id == "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE":
        groups["relevant_supply"] = _has_any(
            normalized,
            ("hbm", "gpu", "accelerator", "blackwell", "advanced packaging", "cowos", "component supply"),
        )
        groups["capacity_or_availability_event"] = _has_any(
            normalized,
            (
                "capacity expansion",
                "capacity ramp",
                "production capacity",
                "manufacturing capacity",
                "available later",
                "globally available",
                "shipping at scale",
                "factory can ship",
            ),
        )
        groups["timing_surface"] = bool(
            re.search(r"(?:20(?:25|26|27)|q[1-4]|quarter|half|later this year|in a week)", normalized)
        )
        groups["upstream_Dell_allocation"] = bool(
            re.search(
                r"(?:capacity|allocation|supply).{0,100}(?:allocated|secured|reserved|for|to).{0,40}dell",
                normalized,
            )
            or re.search(r"allocated\s+to\s+dell", normalized)
        )
        complete = (
            in_period
            and groups["relevant_supply"]
            and groups["capacity_or_availability_event"]
            and groups["timing_surface"]
            and groups["upstream_Dell_allocation"]
        )
        partial = in_period and groups["relevant_supply"] and groups["capacity_or_availability_event"]
        role = "upstream_capacity_release_to_Dell" if complete else "product_availability_or_delivery_context"
        if partial and not groups["upstream_Dell_allocation"]:
            limitations.append("product_availability_is_not_upstream_capacity_allocation")
        required = ("relevant_supply", "capacity_or_availability_event", "timing_surface", "upstream_Dell_allocation")

    elif target_id == "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD":
        groups["relevant_supply"] = _has_any(
            normalized,
            ("hbm", "accelerator", "gpu", "advanced packaging", "cowos", "wafer", "dram"),
        )
        groups["observed_yield_or_utilization"] = _has_any(
            normalized,
            ("yield rate", "production yield", "manufacturing yield", "capacity utilization", "utilization rate"),
        )
        groups["observed_measure"] = bool(
            re.search(r"(?:yield|utilization)(?:\s+rate|\s+level)?[^.%]{0,40}[0-9]{1,3}(?:\.[0-9]+)?%", normalized)
            or _has_any(normalized, ("at full utilization", "near full utilization", "below full utilization"))
        )
        future_or_wrong_process = bool(
            re.search(r"(?:future|target|expect|could|may|a14|sram).{0,80}(?:yield|utilization)", normalized)
        )
        complete = (
            in_period
            and groups["relevant_supply"]
            and groups["observed_yield_or_utilization"]
            and groups["observed_measure"]
            and not future_or_wrong_process
        )
        partial = in_period and groups["relevant_supply"] and groups["observed_yield_or_utilization"]
        role = "observed_relevant_supply_yield_or_utilization" if complete else "yield_or_utilization_context"
        if future_or_wrong_process:
            limitations.append("future_or_non_target_process_yield_not_current_Dell_supply_fact")
        required = ("relevant_supply", "observed_yield_or_utilization", "observed_measure")

    elif target_id == "DELL-RSQ-03A-TARGET-HBM-SUPPLY":
        groups["hbm_subject"] = _has_any(normalized, ("hbm", "high bandwidth memory", "high-bandwidth memory"))
        groups["supply_state"] = _has_any(
            normalized,
            ("availability", "capacity", "supply tightness", "supply constraint", "shortage", "sold out", "supply-demand balance"),
        )
        groups["time_surface"] = bool(
            re.search(r"(?:20(?:25|26|27|28)|q[1-4]|quarter|half|this year|next year)", normalized)
        )
        groups["directional_Dell_bridge"] = bool(
            re.search(
                r"hbm.{0,180}(?:allocated|configured|available|supply|capacity).{0,80}(?:for|to|in|supports?)\s+(?:dell|poweredge)",
                normalized,
            )
            or re.search(
                r"(?:dell|poweredge).{0,120}(?:configured|powered).{0,80}hbm",
                normalized,
            )
        )
        complete = (
            in_period
            and groups["hbm_subject"]
            and groups["supply_state"]
            and groups["time_surface"]
            and groups["directional_Dell_bridge"]
        )
        partial = in_period and groups["hbm_subject"] and groups["supply_state"]
        role = "HBM_supply_with_Dell_configuration_or_allocation_bridge" if complete else "HBM_supply_context"
        if partial and not groups["directional_Dell_bridge"]:
            limitations.append("HBM_market_context_without_Dell_allocation_or_configuration_bridge")
        required = ("hbm_subject", "supply_state", "time_surface", "directional_Dell_bridge")

    elif target_id == "DELL-RSQ-03A-TARGET-UNITS":
        groups["shipment_or_delivery"] = _has_any(
            normalized, ("shipped", "shipments", "delivered", "delivery")
        )
        groups["physical_server_or_system_count"] = bool(
            re.search(
                r"(?<![$0-9a-z])(?:[0-9][0-9,]*|one|two|three|four|five|six|seven|eight|nine|ten)"
                r"(?:\s*\([0-9]+\))?(?:\s+[a-z0-9-]+){0,4}\s+(?:server units|servers|systems)(?![0-9a-z])",
                normalized,
            )
        )
        procurement_or_gpu = bool(
            _has_any(normalized, ("purchase agreement", "contract amount", "procurement"))
            or re.search(r"[0-9][0-9,]*\s+(?:nvidia\s+)?gpus", normalized)
        )
        dollar_shipments = bool(
            re.search(r"(?:shipments.{0,30}\$|\$.{0,30}shipments)", normalized)
        )
        complete = (
            in_period
            and base["dell_subject"]
            and base["dell_ai_server"]
            and groups["shipment_or_delivery"]
            and groups["physical_server_or_system_count"]
            and not procurement_or_gpu
            and not dollar_shipments
        )
        partial = in_period and base["dell_ai_server"] and groups["shipment_or_delivery"]
        role = "Dell_company_period_physical_server_shipments" if complete else "qualitative_shipment_or_noncompany_count_context"
        if procurement_or_gpu:
            limitations.append("procurement_system_or_GPU_count_is_not_Dell_company_server_shipments")
        if dollar_shipments:
            limitations.append("shipment_value_is_not_physical_units")
        required = ("dell_subject", "dell_ai_server", "shipment_or_delivery", "physical_server_or_system_count")

    else:
        raise DellReportInternalChainCeilingR3Error(
            f"dell_03B_R3_unknown_target:{target_id}"
        )

    matched = sorted(group_id for group_id, hit in groups.items() if hit)
    return {
        "target_id": target_id,
        "classification": _classification(complete, partial and not complete),
        "package_role": role,
        "matched_group_ids": matched,
        "required_group_ids": list(required),
        "limitations": sorted(set(limitations)),
        "in_period": in_period,
        "ticker": str(metadata.get("ticker") or ""),
        "source_type": str(metadata.get("source_type") or ""),
        "source_tier": str(metadata.get("source_tier") or ""),
        "publication_date": str(metadata.get("publication_date") or ""),
        "model_text": str(text or ""),
    }


def _source_id(row: Mapping[str, Any]) -> str:
    return _nonblank(row.get("evidence_id"), "dell_03B_R3_source_evidence_id_missing")


def _object_source_ids(row: Mapping[str, Any]) -> list[str]:
    values = [str(value).strip() for value in row.get("lineage_source_record_ids") or ()]
    _require(values and all(values), "dell_03B_R3_object_lineage_invalid")
    return values


def _object_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    return _mapping(row.get("base_object_view"), "dell_03B_R3_object_base_invalid")


def _split_material_sentences(target_id: str, text: str) -> list[str]:
    # Do not split abbreviations such as "U.S. factories". A sentence-ending
    # full stop must be followed by an uppercase/quote opener; ! and ? remain
    # unconditional boundaries.
    sentence_boundary = r"(?<=[!?])\s+|(?<=[a-z0-9\u2019\u201d\"])\.\s+(?=[A-Z\u201c\"])"
    sentences = [
        sentence.strip()
        for paragraph in str(text or "").splitlines()
        for sentence in re.split(sentence_boundary, paragraph)
        if sentence.strip()
    ]
    result: list[str] = []
    for sentence in sentences:
        normalized = _normalize_text(sentence)
        base = _base_groups(normalized)
        material = False
        if target_id == "DELL-RSQ-03A-TARGET-ASP":
            material = base["dell_subject"] and (
                bool(re.search(r"(?:usd|us\$|\$)\s*[0-9]", normalized))
                or base["dell_ai_server"]
            )
        elif target_id in {
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
        }:
            material = base["dell_subject"] and base["named_supplier"] and _has_any(
                normalized,
                (
                    "partner",
                    "deliver",
                    "shipping",
                    "available",
                    "factory can ship",
                    "factories can ship",
                    "capacity",
                    "allocation",
                ),
            )
        elif target_id == "DELL-RSQ-03A-TARGET-HBM-SUPPLY":
            material = base["dell_subject"] and _bounded_term_hit(normalized, "hbm")
        elif target_id == "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD":
            material = _has_any(normalized, ("yield rate", "capacity utilization", "utilization rate"))
        elif target_id == "DELL-RSQ-03A-TARGET-UNITS":
            material = base["dell_ai_server"] and _has_any(normalized, ("shipped", "shipments", "delivered"))
        if material:
            result.append(sentence)
    return result


def assess_dell_report_internal_chain_r3_packages(
    *,
    target_id: str,
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
    selected_object_ids: Iterable[str] | None = None,
    rank_by_object_id: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Assess source truth, compiled bounded packages, and materialization coverage."""

    source_by_id: dict[str, dict[str, Any]] = {}
    for raw in source_rows:
        row = dict(raw)
        source_id = _source_id(row)
        _require(source_id not in source_by_id, f"dell_03B_R3_source_duplicate:{source_id}")
        source_by_id[source_id] = row
    selected = set(selected_object_ids) if selected_object_ids is not None else None
    objects_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in object_rows:
        row = dict(raw)
        object_id = _nonblank(
            row.get("compiled_object_id"), "dell_03B_R3_object_id_missing"
        )
        if selected is not None and object_id not in selected:
            continue
        for source_id in _object_source_ids(row):
            _require(
                source_id in source_by_id,
                f"dell_03B_R3_object_source_missing:{source_id}",
            )
            objects_by_source[source_id].append(row)

    source_packages: list[dict[str, Any]] = []
    compiled_packages: list[dict[str, Any]] = []
    coverage_gaps: list[dict[str, Any]] = []
    source_ids_to_assess = (
        source_by_id.keys() if selected is None else objects_by_source.keys()
    )
    for source_id in source_ids_to_assess:
        source = source_by_id[source_id]
        if selected is None:
            source_assessment = classify_dell_report_internal_chain_r3_package(
                target_id=target_id,
                text=str(source.get("text") or ""),
                metadata=source,
            )
            source_assessment["source_record_id"] = source_id
            source_packages.append(source_assessment)

        scoped_objects = objects_by_source.get(source_id, [])
        combined_text = "\n".join(str(row.get("model_text") or "") for row in scoped_objects)
        compiled_assessment = classify_dell_report_internal_chain_r3_package(
            target_id=target_id, text=combined_text, metadata=source
        )
        object_ids = [str(row.get("compiled_object_id") or "") for row in scoped_objects]
        compiled_assessment.update(
            {
                "source_record_id": source_id,
                "compiled_object_ids": object_ids,
                "completion_rank": None,
            }
        )
        if compiled_assessment["classification"] == "complete_bounded_target_package" and rank_by_object_id:
            object_group_hits: dict[str, list[int]] = defaultdict(list)
            for row in scoped_objects:
                object_id = str(row.get("compiled_object_id") or "")
                rank = rank_by_object_id.get(object_id)
                if rank is None:
                    continue
                object_assessment = classify_dell_report_internal_chain_r3_package(
                    target_id=target_id,
                    text=str(row.get("model_text") or ""),
                    metadata=source,
                )
                for group_id in object_assessment["matched_group_ids"]:
                    object_group_hits[group_id].append(int(rank))
            required = compiled_assessment["required_group_ids"]
            if all(object_group_hits.get(group_id) for group_id in required):
                compiled_assessment["completion_rank"] = max(
                    min(object_group_hits[group_id]) for group_id in required
                )
        compiled_packages.append(compiled_assessment)

        if selected is None:
            normalized_compiled = _normalize_text(combined_text)
            for sentence in _split_material_sentences(
                target_id, str(source.get("text") or "")
            ):
                normalized_sentence = _normalize_text(sentence)
                if normalized_sentence and normalized_sentence not in normalized_compiled:
                    coverage_gaps.append(
                        {
                            "source_record_id": source_id,
                            "target_id": target_id,
                            "sentence_sha256": hashlib.sha256(
                                normalized_sentence.encode("utf-8")
                            ).hexdigest(),
                            "material_sentence": sentence,
                            "reason": "material_source_sentence_missing_from_compiled_objects",
                        }
                    )
    return {
        "source_packages": source_packages,
        "compiled_packages": compiled_packages,
        "coverage_gaps": coverage_gaps,
    }


def _complete_ids(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        str(row.get("source_record_id") or "")
        for row in rows
        if row.get("classification") == "complete_bounded_target_package"
    }


def _partial_ids(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        str(row.get("source_record_id") or "")
        for row in rows
        if row.get("classification") == "partial_context_only"
    }


def _rank_map(
    object_ids: Iterable[str], request_results: Sequence[Mapping[str, Any]], field: str
) -> dict[str, int]:
    result: dict[str, int] = {}
    for object_id in object_ids:
        trace = legacy._candidate_trace(object_id, request_results)  # noqa: SLF001
        value = trace.get(field)
        if value is not None:
            result[object_id] = int(value)
    return result


def _public_package(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "source_record_id",
            "classification",
            "package_role",
            "matched_group_ids",
            "required_group_ids",
            "limitations",
            "ticker",
            "source_type",
            "source_tier",
            "publication_date",
            "compiled_object_ids",
            "completion_rank",
        )
    }


def _residual_scope(target_id: str, complete_source_ids: set[str]) -> list[str]:
    if target_id == "DELL-RSQ-03A-TARGET-ASP":
        return ["Dell_company_wide_realized_ASP_units_and_mix"]
    if target_id == "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH":
        return ["supplier_capacity_or_allocation_to_Dell"]
    if target_id == "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE":
        return ["upstream_capacity_release_timetable_and_Dell_allocation"]
    if target_id == "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD":
        return ["current_observed_relevant_supply_yield_or_utilization"]
    if target_id == "DELL-RSQ-03A-TARGET-HBM-SUPPLY":
        return ["HBM_supply_with_Dell_configuration_or_allocation_bridge"]
    if target_id == "DELL-RSQ-03A-TARGET-UNITS":
        return ["Dell_company_period_physical_AI_server_shipments"]
    return [] if complete_source_ids else ["complete_target"]


def compile_dell_report_internal_chain_ceiling_r3_result(
    *,
    legacy_policy: Mapping[str, Any],
    r3_policy: Mapping[str, Any],
    residual_program: Mapping[str, Any],
    runtime_registry: Mapping[str, Any],
    runtime_binding_receipt: Mapping[str, Any],
    execution: Mapping[str, Any],
    execution_sha256: str,
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
    recorded_at: str,
    prepared_from_commit: str,
    input_bindings: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile R3 from a fully sealed raw execution and bounded source packages."""

    target_contracts = list(legacy_policy.get("target_contracts") or ())
    expected_request_ids = {
        str(request_id)
        for contract in target_contracts
        for request_id in contract.get("request_ids") or ()
    }
    validated = validate_dell_report_internal_chain_ceiling_r3_execution(
        execution, expected_request_ids=expected_request_ids
    )
    _require(
        re.fullmatch(r"[0-9a-f]{64}", execution_sha256) is not None,
        "dell_03B_R3_execution_sha_invalid",
    )
    actual_execution_sha256 = hashlib.sha256(
        json.dumps(
            execution,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    _require(
        execution_sha256 == actual_execution_sha256,
        "dell_03B_R3_execution_sha_mismatch",
    )
    source_ids_list = [_source_id(row) for row in source_rows]
    objects_by_id, source_ids = legacy.validate_dell_report_source_compiled_identity_population(
        object_rows=object_rows,
        source_record_ids=source_ids_list,
        runtime_binding_receipt=runtime_binding_receipt,
    )
    request_by_id = validated["request_results_by_id"]
    residual_by_id = {
        str(row.get("target_id") or ""): dict(row)
        for row in residual_program.get("route_targets") or ()
        if isinstance(row, Mapping)
    }

    target_results: list[dict[str, Any]] = []
    total_union_occurrences = 0
    for contract in sorted(target_contracts, key=lambda row: str(row.get("target_id"))):
        target_id = str(contract.get("target_id") or "")
        scoped_results = [request_by_id[str(value)] for value in contract.get("request_ids") or ()]
        union_ids = {
            str(seed.get("compiled_object_id") or "")
            for row in scoped_results
            for seed in row["hybrid_object_retrieval"]["candidate_decision_seed"]
        }
        final_ids = {
            str(candidate.get("compiled_object_id") or "")
            for row in scoped_results
            for candidate in row["hybrid_object_retrieval"]["candidates"]
        }
        _require(
            union_ids.issubset(objects_by_id) and final_ids.issubset(union_ids),
            f"dell_03B_R3_candidate_object_binding_invalid:{target_id}",
        )
        total_union_occurrences += len(union_ids)
        corpus = assess_dell_report_internal_chain_r3_packages(
            target_id=target_id,
            source_rows=source_rows,
            object_rows=object_rows,
        )
        union_rank = _rank_map(
            union_ids, scoped_results, "minimum_raw_union_rank"
        )
        union = assess_dell_report_internal_chain_r3_packages(
            target_id=target_id,
            source_rows=source_rows,
            object_rows=object_rows,
            selected_object_ids=union_ids,
            rank_by_object_id=union_rank,
        )
        final_rank = _rank_map(
            final_ids, scoped_results, "minimum_final_output_rank"
        )
        final = assess_dell_report_internal_chain_r3_packages(
            target_id=target_id,
            source_rows=source_rows,
            object_rows=object_rows,
            selected_object_ids=final_ids,
            rank_by_object_id=final_rank,
        )
        source_complete = _complete_ids(corpus["source_packages"])
        compiled_complete = _complete_ids(corpus["compiled_packages"])
        union_complete = _complete_ids(union["compiled_packages"])
        final_complete = _complete_ids(final["compiled_packages"])
        source_partial = _partial_ids(corpus["source_packages"])
        compiled_partial = _partial_ids(corpus["compiled_packages"])
        package_materialization_gaps = source_complete - compiled_complete
        coverage_gaps = corpus["coverage_gaps"]
        coverage_pass = not package_materialization_gaps and not coverage_gaps

        if package_materialization_gaps:
            earliest = "local_source_to_object_complete_package_materialization_gap"
        elif not source_complete:
            earliest = "local_source_record_corpus_missing_complete_bounded_package"
        elif not compiled_complete:
            earliest = "local_compiled_package_missing_complete_target"
        elif not union_complete:
            earliest = "current_bm25_0_6b_graph_bounded_package_recall_miss"
        elif not final_complete:
            earliest = "post_union_rank_or_review_cut"
        else:
            earliest = "none_observed_through_final_bounded_package"

        completion_ranks = [
            int(row["completion_rank"])
            for row in final["compiled_packages"]
            if row.get("source_record_id") in final_complete
            and row.get("completion_rank") is not None
        ]
        best_final_rank = min(completion_ranks, default=None)
        embedding_eligible = bool(
            compiled_complete and not union_complete and not package_materialization_gaps
        )
        reranker_eligible = bool(
            union_complete and (best_final_rank is None or best_final_rank > 10)
        )
        external_required = not source_complete
        residual = _residual_scope(target_id, source_complete)
        residual_target = residual_by_id[target_id]
        mandatory_external_routes = sorted(
            str(route.get("route_contract_id") or "")
            for route in residual_target.get("route_contracts") or ()
            if route.get("mandatory_for_target") is True
            and route.get("route_family_id") != "local_data_object_index_sql"
        )
        public_packages = sorted(
            (
                _public_package(row)
                for row in final["compiled_packages"]
                if row.get("classification") != "not_target_semantic_equivalent"
            ),
            key=lambda row: (
                row.get("classification") != "complete_bounded_target_package",
                row.get("completion_rank") or 10**9,
                row.get("source_record_id") or "",
            ),
        )[:20]
        target_results.append(
            {
                "target_id": target_id,
                "pack_gap_id": residual_target.get("pack_gap_id"),
                "target_proposition": residual_target.get("target_proposition"),
                "request_ids": list(contract.get("request_ids") or ()),
                "semantic_evidence_unit": "bounded_same_canonical_source_record_package",
                "candidate_ceiling": {
                    "source_record_population": len(source_ids),
                    "compiled_object_population": len(objects_by_id),
                    "complete_target_in_source_record_corpus_count": len(source_complete),
                    "complete_target_in_compiled_package_corpus_count": len(compiled_complete),
                    "partial_context_in_source_record_corpus_count": len(source_partial),
                    "partial_context_in_compiled_package_corpus_count": len(compiled_partial),
                    "candidate_union_object_count": len(union_ids),
                    "complete_target_in_candidate_union_package_count": len(union_complete),
                    "final_review_object_count": len(final_ids),
                    "complete_target_in_final_review_package_count": len(final_complete),
                    "best_complete_package_final_completion_rank": best_final_rank,
                    "complete_target_useful_at_10": bool(best_final_rank is not None and best_final_rank <= 10),
                    "earliest_observed_limitation": earliest,
                    "package_materialization_gap_count": len(package_materialization_gaps),
                    "material_source_sentence_coverage_gap_count": len(coverage_gaps),
                    "source_to_object_semantic_coverage_pass": coverage_pass,
                    "source_package_scan_digest": canonical_digest(
                        [
                            {
                                key: row.get(key)
                                for key in (
                                    "source_record_id",
                                    "classification",
                                    "package_role",
                                    "matched_group_ids",
                                    "limitations",
                                )
                            }
                            for row in corpus["source_packages"]
                        ]
                    ),
                    "candidate_decision_state": "candidate_not_evidence_unadjudicated",
                    "public_information_gap_eligible": False,
                },
                "downstream_disposition": {
                    "03D_4B_embedding_recall_challenger_eligible": embedding_eligible,
                    "03D_same_pool_reranker_challenger_eligible": reranker_eligible,
                    "03C_external_route_required_for_complete_bounded_target": external_required,
                    "03C_scope_if_authorized": residual if external_required else [],
                    "03C_residual_route_requires_prior_capture_crosswalk": bool(
                        residual
                    ),
                    "03C_residual_scope_if_authorized": residual,
                    "remaining_non_03C_research_boundaries": residual,
                    "local_source_to_object_repair_required": bool(
                        package_materialization_gaps or coverage_gaps
                    ),
                    "mandatory_external_route_contract_ids_if_authorized": mandatory_external_routes if external_required else [],
                    "authority_granted_by_this_result": False,
                },
                "public_top_bounded_packages": public_packages,
                "private_source_packages": [
                    row
                    for row in corpus["source_packages"]
                    if row.get("classification")
                    != "not_target_semantic_equivalent"
                ],
                "private_compiled_packages": [
                    row
                    for row in corpus["compiled_packages"]
                    if row.get("classification")
                    != "not_target_semantic_equivalent"
                ],
                "private_union_packages": [
                    row
                    for row in union["compiled_packages"]
                    if row.get("classification")
                    != "not_target_semantic_equivalent"
                ],
                "private_final_packages": [
                    row
                    for row in final["compiled_packages"]
                    if row.get("classification")
                    != "not_target_semantic_equivalent"
                ],
                "private_source_to_object_coverage_gaps": coverage_gaps,
            }
        )

    execution_summary = dict(validated["summary"])
    body = {
        "schema_version": PRIVATE_RESULT_SCHEMA_VERSION,
        "status": "dell_03B_R3_bounded_source_package_ceiling_executed",
        "attempt_id": ATTEMPT_ID,
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": "DELL",
        "input_bindings": dict(input_bindings),
        "runtime_registry": {
            "registry_id": runtime_registry.get("registry_id"),
            "resource_canonical_digest": runtime_registry.get("resource_canonical_digest"),
        },
        "raw_execution_receipt": dict(execution),
        "raw_execution_sha256": execution_sha256,
        "raw_execution_projection_digest": execution.get("projection_digest"),
        "validated_execution_digest": validated["validated_execution_digest"],
        "execution_summary": execution_summary,
        "target_results": target_results,
        "summary": {
            "target_count": len(target_results),
            "held_target_execution_count": 0,
            "request_count": len(validated["request_results"]),
            "candidate_union_occurrence_count": total_union_occurrences,
            "embedding_challenger_eligible_target_count": sum(
                row["downstream_disposition"]["03D_4B_embedding_recall_challenger_eligible"] is True
                for row in target_results
            ),
            "reranker_challenger_eligible_target_count": sum(
                row["downstream_disposition"]["03D_same_pool_reranker_challenger_eligible"] is True
                for row in target_results
            ),
            "external_route_required_target_count": sum(
                row["downstream_disposition"]["03C_external_route_required_for_complete_bounded_target"] is True
                for row in target_results
            ),
            "residual_research_boundary_target_count": sum(
                bool(
                    row["downstream_disposition"].get(
                        "remaining_non_03C_research_boundaries"
                    )
                )
                for row in target_results
            ),
            "local_source_to_object_repair_target_count": sum(
                row["downstream_disposition"]["local_source_to_object_repair_required"] is True
                for row in target_results
            ),
            **{field: execution_summary[field] for field in ZERO_EXECUTION_FIELDS},
        },
        "authority": {
            "03B_R3_execution_consumed": True,
            "03C_external_capture_authorized": False,
            "03D_4B_embedding_authorized": False,
            "03D_reranker_authorized": False,
            "candidate_decision_authorized": False,
            "evidence_promotion_authorized": False,
            "proved_information_boundary_authorized": False,
            "G3_pass": False,
            "S1_pass": False,
            "S2_pass": False,
            "S3_pass": False,
            "report_quality_pass": False,
            "product_acceptance": False,
            "publication": False,
            "release_ready": False,
        },
        "known_boundary": (
            "R3 distinguishes bounded same-source evidence packages, source-to-object semantic coverage, "
            "candidate recall, final ranking and residual external acquisition. Configuration prices are not "
            "company-wide realized ASP; relationship or product availability is not supplier capacity allocation; "
            "candidates are not Evidence. No 03C, 4B, reranker, promotion, gap closure, human, report, product, "
            "publication or release authority is granted."
        ),
        "policy_digest": r3_policy.get("result_digest"),
    }
    return {**body, "result_digest": canonical_digest(body)}


def build_dell_report_internal_chain_ceiling_r3_public_projection(
    *, private_result: Mapping[str, Any], private_ref: str, private_sha256: str
) -> dict[str, Any]:
    target_results: list[dict[str, Any]] = []
    for raw in private_result.get("target_results") or ():
        row = dict(raw)
        for key in (
            "private_source_packages",
            "private_compiled_packages",
            "private_union_packages",
            "private_final_packages",
            "private_source_to_object_coverage_gaps",
        ):
            row.pop(key, None)
        target_results.append(row)
    body = {
        "schema_version": PUBLIC_RESULT_SCHEMA_VERSION,
        "status": private_result.get("status"),
        "attempt_id": private_result.get("attempt_id"),
        "recorded_at": private_result.get("recorded_at"),
        "prepared_from_commit": private_result.get("prepared_from_commit"),
        "case_key": private_result.get("case_key"),
        "input_bindings": dict(private_result.get("input_bindings") or {}),
        "runtime_registry": dict(private_result.get("runtime_registry") or {}),
        "raw_execution_sha256": private_result.get("raw_execution_sha256"),
        "raw_execution_projection_digest": private_result.get(
            "raw_execution_projection_digest"
        ),
        "validated_execution_digest": private_result.get("validated_execution_digest"),
        "execution_summary": dict(private_result.get("execution_summary") or {}),
        "target_results": target_results,
        "summary": dict(private_result.get("summary") or {}),
        "private_result_ref": private_ref,
        "private_result_sha256": private_sha256,
        "private_result_digest": private_result.get("result_digest"),
        "authority": dict(private_result.get("authority") or {}),
        "known_boundary": private_result.get("known_boundary"),
        "policy_digest": private_result.get("policy_digest"),
    }
    serialized = json.dumps(body, ensure_ascii=False, sort_keys=True).casefold()
    _require("model_text" not in serialized, "dell_03B_R3_public_model_text_leak")
    _require("material_sentence" not in serialized, "dell_03B_R3_public_sentence_leak")
    _require(
        "http://" not in serialized and "https://" not in serialized,
        "dell_03B_R3_public_url_leak",
    )
    return {**body, "result_digest": canonical_digest(body)}


__all__ = [
    "ATTEMPT_ID",
    "ATTEMPT_RECEIPT_REF",
    "BRANCH",
    "DellReportInternalChainCeilingR3Error",
    "EXECUTION_CONTRACT",
    "EXPECTED_IMPLEMENTATION_PATHS",
    "ONLY_SUCCESSOR_CHANGES",
    "POLICY_REF",
    "POLICY_SCHEMA_VERSION",
    "PRIVATE_REF",
    "PRIVATE_RESULT_SCHEMA_VERSION",
    "PROGRAM_ID",
    "PUBLIC_REF",
    "PUBLIC_RESULT_SCHEMA_VERSION",
    "SEMANTIC_CONTRACT",
    "assess_dell_report_internal_chain_r3_packages",
    "build_dell_report_internal_chain_ceiling_r3_public_projection",
    "classify_dell_report_internal_chain_r3_package",
    "compile_dell_report_internal_chain_ceiling_r3_result",
    "validate_dell_report_internal_chain_ceiling_r3_execution",
    "validate_dell_report_internal_chain_ceiling_r3_policy",
]
