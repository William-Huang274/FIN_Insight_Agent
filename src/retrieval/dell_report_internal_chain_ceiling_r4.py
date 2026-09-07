from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence

from . import dell_report_internal_chain_ceiling as legacy
from . import dell_report_internal_chain_ceiling_r3 as r3
from .query_plan import canonical_digest


POLICY_SCHEMA_VERSION = "fin_ia_dell_report_internal_chain_ceiling_policy_v1_3"
PRIVATE_RESULT_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_candidate_ceiling_private_result_v1_3"
)
PUBLIC_RESULT_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_candidate_ceiling_result_v1_3"
)
ATTEMPT_ID = "dell-rsq-03b-internal-chain-r4"
BRANCH = "codex/fin013-dell-s1-s2-product-bridge"
POLICY_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_3.json"
)
PUBLIC_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_3.json"
)
PRIVATE_REF = (
    "data/workbench_private/"
    "fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/"
    f"{ATTEMPT_ID}/full_result.json"
)
ATTEMPT_RECEIPT_REF = (
    "data/workbench_private/"
    "fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/"
    f"{ATTEMPT_ID}/attempt_consumption_receipt.json"
)
MAX_ADJACENT_UNITS = 8
TARGET_IDS = frozenset(
    {
        "DELL-RSQ-03A-TARGET-ASP",
        "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
        "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
        "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
        "DELL-RSQ-03A-TARGET-UNITS",
    }
)
ZERO_EXECUTION_FIELDS = r3.ZERO_EXECUTION_FIELDS
PROGRAM_ID = "FIN-0.1.3-S1-DELL-RSQ-03B-R4"
EXECUTION_CONTRACT = dict(r3.EXECUTION_CONTRACT)
SEMANTIC_CONTRACT = {
    "canonical_source_family_mode": "page_parent_and_slice_family_deduplicated",
    "adjacency_order_mode": "slice_index_then_char_offset_then_frozen_input_order",
    "maximum_adjacent_source_or_object_units": MAX_ADJACENT_UNITS,
    "selected_pool_adjacency_mode": "absolute_corpus_positions_not_selected_only_positions",
    "supplier_role": "positive_named_supplier_Dell_direction_with_negation_guard",
    "yield_role": "observed_measure_with_symmetric_future_wrong_process_guard",
    "units_role": "Dell_seller_shipper_company_period_physical_server_count",
    "ASP_role": "bounded_configuration_or_bundle_price_not_company_realized_ASP",
    "material_coverage_mode": "target_role_and_exact_numeric_time_anchor_coverage",
    "coverage_count_mode": "canonical_claim_and_raw_source_occurrence_both_reported",
    "reranker_useful_at_k": 10,
    "candidate_not_evidence": True,
}
AUTHORITY = dict(r3.AUTHORITY)
EXPECTED_IMPLEMENTATION_PATHS = frozenset(
    {
        "src/retrieval/dell_report_internal_chain_ceiling.py",
        "src/retrieval/dell_report_internal_chain_ceiling_r3.py",
        "src/retrieval/dell_report_internal_chain_ceiling_r4.py",
        "src/retrieval/object_view_compiler.py",
        "src/retrieval/object_view_compiler_v2.py",
        "src/retrieval/route_compiler.py",
        "scripts/data_retrieval/materialize_s1_abbreviation_claim_repair_successor.py",
        "scripts/data_retrieval/promote_s1_abbreviation_claim_repair_to_current_runtime.py",
        "scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r4.py",
        "apps/workbench/backend/application/research_retrieval_service.py",
    }
)
EXPECTED_BOUND_INPUT_IDS = frozenset(
    {
        "R1_policy",
        "R3_policy",
        "R3_public",
        "R3_private",
        "R3_fresh_audit",
        "R39_repair_result",
        "R39_embedding_result",
        "R39_route_policy",
        "R39_hybrid_policy",
        "runtime_registry",
        "runtime_binding_receipt",
        "residual_program",
        "execution_program",
        "dell_product_readiness",
    }
)


class DellReportInternalChainCeilingR4Error(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellReportInternalChainCeilingR4Error(code)


def _self_digest(value: Mapping[str, Any]) -> bool:
    body = dict(value)
    observed = str(body.pop("result_digest", ""))
    return bool(observed) and observed == canonical_digest(body)


def validate_dell_report_internal_chain_ceiling_r4_policy(
    policy: Mapping[str, Any],
    *,
    r1_policy: Mapping[str, Any],
    r3_policy: Mapping[str, Any],
    r3_public: Mapping[str, Any],
    r3_private: Mapping[str, Any],
    r3_fresh_audit: Mapping[str, Any],
    r39_repair_result: Mapping[str, Any],
    r39_embedding_result: Mapping[str, Any],
    r39_route_policy: Mapping[str, Any],
    r39_hybrid_policy: Mapping[str, Any],
    runtime_registry: Mapping[str, Any],
    runtime_binding_receipt: Mapping[str, Any],
    residual_program: Mapping[str, Any],
    execution_program: Mapping[str, Any],
    dell_product_readiness: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed on R4 scope, R39 runtime, predecessor and authority drift."""

    _require(_self_digest(policy), "dell_03B_R4_policy_digest_invalid")
    _require(
        policy.get("schema_version") == POLICY_SCHEMA_VERSION
        and policy.get("status")
        == "same_stage_R4_execution_authorized_after_fresh_R3_audit_failure"
        and policy.get("program_id") == PROGRAM_ID
        and policy.get("attempt_id") == ATTEMPT_ID,
        "dell_03B_R4_policy_identity_invalid",
    )
    _require(
        dict(policy.get("execution_contract") or {}) == EXECUTION_CONTRACT
        and dict(policy.get("semantic_contract") or {}) == SEMANTIC_CONTRACT
        and dict(policy.get("authority") or {}) == AUTHORITY,
        "dell_03B_R4_policy_contract_invalid",
    )
    output = dict(policy.get("output_contract") or {})
    _require(
        output.get("policy_ref") == POLICY_REF
        and output.get("private_result_ref") == PRIVATE_REF
        and output.get("public_result_ref") == PUBLIC_REF
        and output.get("attempt_consumption_receipt_ref")
        == ATTEMPT_RECEIPT_REF
        and output.get("alternate_output_paths_authorized") is False
        and output.get("private_public_same_path_authorized") is False
        and output.get("exclusive_create_required") is True
        and output.get("atomic_pair_with_rollback_required") is True
        and output.get("same_attempt_retry_authorized") is False,
        "dell_03B_R4_output_contract_invalid",
    )
    bound_inputs = dict(policy.get("bound_inputs") or {})
    _require(
        set(bound_inputs) == EXPECTED_BOUND_INPUT_IDS
        and all(
            isinstance(row, Mapping)
            and str(row.get("ref") or "").strip()
            and bool(re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256") or "")))
            for row in bound_inputs.values()
        ),
        "dell_03B_R4_bound_inputs_invalid",
    )
    identity = dict(policy.get("execution_identity") or {})
    _require(
        identity.get("branch") == BRANCH
        and bool(
            re.fullmatch(
                r"[0-9a-f]{40}", str(identity.get("implementation_commit") or "")
            )
        )
        and bool(
            re.fullmatch(
                r"[0-9a-f]{40}", str(identity.get("implementation_tree") or "")
            )
        )
        and identity.get("authority_commit_changed_paths") == [POLICY_REF]
        and identity.get("authority_commit_parent_must_equal_implementation_commit")
        is True
        and identity.get("HEAD_must_equal_upstream") is True,
        "dell_03B_R4_execution_identity_invalid",
    )
    bindings = list(policy.get("implementation_bindings") or ())
    _require(
        {str(row.get("path") or "") for row in bindings}
        == EXPECTED_IMPLEMENTATION_PATHS
        and all(
            bool(re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256") or "")))
            for row in bindings
            if isinstance(row, Mapping)
        ),
        "dell_03B_R4_implementation_bindings_invalid",
    )
    token_basis = dict(policy.get("TokenBudgetBasis") or {})
    token_basis_fields = {
        "node_purpose",
        "input_scale",
        "required_outputs",
        "schema_burden",
        "materiality_quality_risk",
        "comparable_run_evidence",
        "reasoning_profile",
        "stop_and_truncation",
    }
    _require(
        set(token_basis) == token_basis_fields
        and all(str(token_basis[field]).strip() for field in token_basis_fields),
        "dell_03B_R4_token_budget_basis_invalid",
    )

    _require(
        r3_fresh_audit.get("schema_version")
        == "fin_ia_independent_readonly_audit_result_v1_0"
        and r3_fresh_audit.get("status")
        == "fail_material_semantic_route_and_report_findings_same_stage_R4_required"
        and r3_fresh_audit.get("verdicts", {}).get("overall") == "FAIL"
        and r3_fresh_audit.get("authority", {}).get(
            "R4_same_stage_successor_authorized"
        )
        is True
        and _self_digest(r3_fresh_audit),
        "dell_03B_R4_predecessor_audit_invalid",
    )
    required_findings = {
        "AUDIT-28158E04-P1-01",
        "AUDIT-28158E04-P2-01",
        "AUDIT-28158E04-P1-R17-01",
    }
    _require(
        required_findings.issubset(
            {
                str(row.get("finding_id") or "")
                for row in r3_fresh_audit.get("material_findings") or ()
                if isinstance(row, Mapping)
            }
        ),
        "dell_03B_R4_required_findings_missing",
    )
    _require(
        r3_policy.get("attempt_id") == r3.ATTEMPT_ID
        and r3_policy.get("result_digest")
        == r3_fresh_audit.get("reviewed_artifacts", {})
        .get("R3_policy", {})
        .get("policy_digest")
        and r3_public.get("attempt_id") == r3.ATTEMPT_ID
        and r3_private.get("attempt_id") == r3.ATTEMPT_ID
        and r3_public.get("private_result_digest") == r3_private.get("result_digest")
        and _self_digest(r3_public)
        and _self_digest(r3_private),
        "dell_03B_R4_R3_result_binding_invalid",
    )

    repair_summary = dict(r39_repair_result.get("summary") or {})
    _require(
        _self_digest(r39_repair_result)
        and repair_summary.get("base_source_record_count") == 1888
        and repair_summary.get("successor_source_record_count") == 1888
        and repair_summary.get("base_object_count") == 34198
        and repair_summary.get("appended_object_count") == 1
        and repair_summary.get("successor_object_count") == 34199
        and r39_repair_result.get("authority", {}).get("candidate_is_not_evidence")
        is True
        and r39_repair_result.get("authority", {}).get("numeric_authority")
        is False,
        "dell_03B_R4_R39_repair_invalid",
    )
    _require(
        r39_embedding_result.get("runtime", {}).get("device") == "cuda:0"
        and r39_embedding_result.get("runtime", {}).get("parameter_dtype")
        == "torch.float16"
        and r39_embedding_result.get("runtime", {}).get(
            "new_object_count_embedded"
        )
        == 1
        and r39_embedding_result.get("runtime", {}).get("cpu_fallback_count")
        == 0
        and r39_embedding_result.get("outputs", {}).get("object_count") == 34199,
        "dell_03B_R4_R39_embedding_invalid",
    )
    _require(
        r39_route_policy.get("object_compiler", {}).get(
            "claim_segmentation_mode"
        )
        == "sentence_with_wrapped_line_reflow_v2"
        and r39_route_policy.get("object_compiler", {}).get(
            "claim_overflow_policy"
        )
        == "emit_typed_diagnostic_and_fail_qualification"
        and r39_hybrid_policy.get("object_store", {}).get("objects_ref")
        == r39_repair_result.get("outputs", {}).get("objects_ref"),
        "dell_03B_R4_R39_runtime_policy_invalid",
    )
    lineage = dict(runtime_binding_receipt.get("source_object_index_lineage") or {})
    _require(
        runtime_registry.get("registry_id")
        == "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R39"
        and runtime_binding_receipt.get("registry_binding", {}).get("registry_id")
        == runtime_registry.get("registry_id")
        and lineage.get("source_record_count") == 1888
        and lineage.get("compiled_object_count") == 34199
        and runtime_binding_receipt.get("embedding_index", {}).get("object_count")
        == 34199
        and runtime_binding_receipt.get("acceptance", {}).get(
            "s1_qualified_stable"
        )
        is False,
        "dell_03B_R4_R39_binding_invalid",
    )

    target_contracts = list(r1_policy.get("target_contracts") or ())
    target_ids = {str(row.get("target_id") or "") for row in target_contracts}
    request_ids = {
        str(request_id)
        for row in target_contracts
        for request_id in row.get("request_ids") or ()
    }
    _require(
        target_ids == TARGET_IDS
        and len(target_contracts) == 6
        and len(request_ids) == 5,
        "dell_03B_R4_target_request_contract_invalid",
    )
    _require(
        target_ids.issubset(
            {
            str(row.get("target_id") or "")
            for row in residual_program.get("route_targets") or ()
            if isinstance(row, Mapping)
            }
        )
        and request_ids.issubset(
            {
                str(row.get("request_id") or "")
                for row in execution_program.get("evidence_requests") or ()
                if isinstance(row, Mapping)
            }
        )
        and dell_product_readiness.get("case_key") == "DELL"
        and dell_product_readiness.get("authority", {}).get(
            "S1_qualification_claimed"
        )
        is False,
        "dell_03B_R4_program_readiness_binding_invalid",
    )
    return dict(r1_policy)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _bounded_term_hit(text: str, term: str) -> bool:
    normalized = _normalize_text(term)
    escaped = re.escape(normalized)
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


def _sentence_units(text: str) -> list[str]:
    # A full stop after an uppercase initial is deliberately not a boundary;
    # this retains U.S./U.K. while preserving normal sentence endings.
    boundary = (
        r"(?<=[!?])\s+|"
        r"(?<=[a-z0-9\u2019\u201d\"])\.\s+(?=[A-Z\u201c\"]|$)"
    )
    return [
        sentence.strip()
        for paragraph in str(text or "").splitlines()
        for sentence in re.split(boundary, paragraph)
        if sentence.strip()
    ]


def _base_groups(text: str) -> dict[str, bool]:
    return {
        "dell_subject": _has_any(
            text, ("dell", "poweredge", "dell ai factory")
        ),
        "dell_ai_server": _has_any(
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
        ),
        "named_supplier": _has_any(
            text,
            (
                "nvidia",
                "micron",
                "tsmc",
                "taiwan semiconductor",
                "sk hynix",
                "broadcom",
            ),
        ),
    }


def _classification(complete: bool, partial: bool) -> str:
    if complete:
        return "complete_bounded_target_package"
    if partial:
        return "partial_context_only"
    return "not_target_semantic_equivalent"


def _positive_supplier_direction(text: str) -> bool:
    patterns = (
        r"(?:dell\s+and\s+nvidia|nvidia\s+and\s+dell).{0,100}(?:partner|collaborat)",
        r"(?:nvidia\s+and\s+dell).{0,100}partnering\s+to\s+deliver",
        r"dell\s+servers?.{0,100}(?:with|powered\s+by).{0,50}nvidia.{0,100}(?:shipping|available|deliver)",
        r"(?:allocated|allocation|deliver(?:y|ed)?|suppl(?:y|ies|ied)).{0,60}(?:to\s+)?dell",
        r"available\s+(?:from|through)\s+dell",
    )
    negation = re.compile(
        r"(?:\bnot\b|\bnever\b|\bno\s+longer\b|\bdo\s+not\b|"
        r"\bdoes\s+not\b|\bdid\s+not\b|\bhave\s+not\b|\bhas\s+not\b)"
    )
    for sentence in _sentence_units(text):
        normalized = _normalize_text(sentence)
        if any(re.search(pattern, normalized) for pattern in patterns):
            if negation.search(normalized):
                continue
            return True
    return False


def _valid_observed_yield_measure(text: str) -> bool:
    measure = re.compile(
        r"(?:yield|utilization)(?:\s+rate|\s+level)?[^.%]{0,40}"
        r"[0-9]{1,3}(?:\.[0-9]+)?%"
    )
    future_or_wrong = re.compile(
        r"(?:future|target|expect|expected|could|may|a14|sram|next\s+process)"
    )
    for sentence in _sentence_units(text):
        normalized = _normalize_text(sentence)
        has_measure = bool(measure.search(normalized)) or _has_any(
            normalized,
            (
                "at full utilization",
                "near full utilization",
                "below full utilization",
            ),
        )
        if has_measure and not future_or_wrong.search(normalized):
            return True
    return False


def _unit_role_groups(text: str) -> dict[str, bool]:
    quantity = (
        r"(?<![$0-9a-z])(?:[0-9][0-9,]*|one|two|three|four|five|six|"
        r"seven|eight|nine|ten)(?:\s*\([0-9]+\))?"
        r"(?:\s+[a-z0-9-]+){0,4}\s+(?:server units|servers|systems)"
        r"(?![0-9a-z])"
    )
    seller_patterns = (
        rf"\bdell\b[^.!?]{{0,100}}(?:shipped|delivered)[^.!?]{{0,80}}{quantity}",
        rf"{quantity}[^.!?]{{0,80}}(?:shipped|delivered)\s+by\s+dell",
        rf"\bdell\b[^.!?]{{0,100}}shipments?\s+of[^.!?]{{0,60}}{quantity}",
    )
    buyer_context = _has_any(
        text,
        (
            "university",
            "agency",
            "institution",
            "purchase agreement",
            "procurement",
            "contract amount",
            "confirmed delivery",
            "received",
            "ordered",
            "requests approval",
        ),
    )
    seller = any(re.search(pattern, text) for pattern in seller_patterns)
    period = bool(
        re.search(
            r"(?:fy\s*\d{2,4}|fiscal\s+(?:year|quarter)|q[1-4]|quarter|"
            r"20(?:25|26)|during\s+the\s+period|in\s+(?:a|one)\s+week)",
            text,
        )
    )
    return {
        "shipment_or_delivery": _has_any(
            text, ("shipped", "shipments", "delivered", "delivery")
        ),
        "physical_server_or_system_count": bool(re.search(quantity, text)),
        "Dell_seller_or_shipper_role": seller,
        "company_period_surface": period,
        "buyer_or_procurement_context": buyer_context and not seller,
    }


def classify_dell_report_internal_chain_r4_package(
    *, target_id: str, text: str, metadata: Mapping[str, Any]
) -> dict[str, Any]:
    """Classify one target-specific package after semantic role guards."""

    _require(target_id in TARGET_IDS, f"dell_03B_R4_unknown_target:{target_id}")
    normalized = _normalize_text(text)
    in_period = _iso_date_in_scope(metadata)
    base = _base_groups(normalized)
    groups: dict[str, bool] = dict(base)
    limitations: list[str] = []
    complete = False
    partial = False
    role = "none"

    if target_id == "DELL-RSQ-03A-TARGET-ASP":
        groups["price_surface"] = bool(
            re.search(
                r"(?:usd|us\$|\$)\s*[0-9][0-9,]*(?:\.[0-9]+)?",
                normalized,
            )
            or _has_any(
                normalized,
                ("quoted price", "purchase price", "configuration price"),
            )
        )
        groups["valid_denominator"] = bool(
            re.search(
                r"(?<![0-9a-z])(?:[0-9][0-9,]*|one|two|three|four|five|"
                r"six|seven|eight|nine|ten)(?:\s*\([0-9]+\))?"
                r"(?:\s+[a-z0-9-]+){0,5}\s+"
                r"(?:server units|servers|systems|nodes)(?![0-9a-z])",
                normalized,
            )
        )
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
        required = (
            "dell_subject",
            "dell_ai_server",
            "price_surface",
            "valid_denominator",
        )
        complete = in_period and all(groups[group] for group in required)
        partial = in_period and (
            groups["price_surface"] or base["dell_ai_server"]
        )
        role = (
            "bounded_configuration_or_bundle_price_package"
            if complete
            else "price_or_configuration_context"
        )
        if groups["bundle_boundary"]:
            limitations.append(
                "bundle_contains_non_hardware_or_multi_year_service_components"
            )
        limitations.append("not_company_wide_realized_ASP")

    elif target_id == "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH":
        groups["directional_relationship_delivery"] = _positive_supplier_direction(
            normalized
        )
        groups["capacity_allocation"] = bool(
            re.search(
                r"(?:capacity|allocation|supply).{0,100}"
                r"(?:for|to|secured\s+by)\s+dell",
                normalized,
            )
        )
        required = (
            "dell_subject",
            "named_supplier",
            "directional_relationship_delivery",
        )
        complete = in_period and all(groups[group] for group in required)
        partial = in_period and base["named_supplier"] and (
            base["dell_subject"]
            or groups["directional_relationship_delivery"]
        )
        role = (
            "supplier_to_Dell_relationship_delivery"
            if complete
            else "supplier_or_relationship_context"
        )
        if complete and not groups["capacity_allocation"]:
            limitations.append(
                "supplier_capacity_or_allocation_readthrough_remains_open"
            )

    elif target_id == "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE":
        groups["relevant_supply"] = _has_any(
            normalized,
            (
                "hbm",
                "gpu",
                "accelerator",
                "blackwell",
                "advanced packaging",
                "cowos",
                "component supply",
            ),
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
                "factories can ship",
            ),
        )
        groups["timing_surface"] = bool(
            re.search(
                r"(?:20(?:25|26|27)|q[1-4]|quarter|half|later this year|"
                r"in (?:a|one) week)",
                normalized,
            )
        )
        groups["upstream_Dell_allocation"] = bool(
            re.search(
                r"(?:capacity|allocation|supply).{0,100}"
                r"(?:allocated|secured|reserved|for|to).{0,40}dell",
                normalized,
            )
            or re.search(r"allocated\s+to\s+dell", normalized)
        )
        required = (
            "relevant_supply",
            "capacity_or_availability_event",
            "timing_surface",
            "upstream_Dell_allocation",
        )
        complete = in_period and all(groups[group] for group in required)
        partial = (
            in_period
            and groups["relevant_supply"]
            and groups["capacity_or_availability_event"]
        )
        role = (
            "upstream_capacity_release_to_Dell"
            if complete
            else "product_availability_or_delivery_context"
        )
        if partial and not groups["upstream_Dell_allocation"]:
            limitations.append(
                "product_availability_is_not_upstream_capacity_allocation"
            )

    elif target_id == "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD":
        groups["relevant_supply"] = _has_any(
            normalized,
            (
                "hbm",
                "accelerator",
                "gpu",
                "advanced packaging",
                "cowos",
                "wafer",
                "dram",
            ),
        )
        groups["observed_yield_or_utilization"] = _has_any(
            normalized,
            (
                "yield rate",
                "production yield",
                "manufacturing yield",
                "capacity utilization",
                "utilization rate",
            ),
        )
        groups["observed_measure"] = _valid_observed_yield_measure(normalized)
        required = (
            "relevant_supply",
            "observed_yield_or_utilization",
            "observed_measure",
        )
        complete = in_period and all(groups[group] for group in required)
        partial = (
            in_period
            and groups["relevant_supply"]
            and groups["observed_yield_or_utilization"]
        )
        role = (
            "observed_relevant_supply_yield_or_utilization"
            if complete
            else "yield_or_utilization_context"
        )
        if groups["observed_yield_or_utilization"] and not groups[
            "observed_measure"
        ]:
            limitations.append(
                "future_or_non_target_process_yield_not_current_Dell_supply_fact"
            )

    elif target_id == "DELL-RSQ-03A-TARGET-HBM-SUPPLY":
        groups["hbm_subject"] = _has_any(
            normalized,
            ("hbm", "high bandwidth memory", "high-bandwidth memory"),
        )
        groups["supply_state"] = _has_any(
            normalized,
            (
                "availability",
                "capacity",
                "supply tightness",
                "supply constraint",
                "shortage",
                "sold out",
                "supply-demand balance",
            ),
        )
        groups["time_surface"] = bool(
            re.search(
                r"(?:20(?:25|26|27|28)|q[1-4]|quarter|half|this year|"
                r"next year)",
                normalized,
            )
        )
        groups["directional_Dell_bridge"] = bool(
            re.search(
                r"hbm.{0,180}(?:allocated|configured|available|supply|capacity)"
                r".{0,80}(?:for|to|in|supports?)\s+(?:dell|poweredge)",
                normalized,
            )
            or re.search(
                r"(?:dell|poweredge).{0,120}(?:configured|powered).{0,80}hbm",
                normalized,
            )
        )
        required = (
            "hbm_subject",
            "supply_state",
            "time_surface",
            "directional_Dell_bridge",
        )
        complete = in_period and all(groups[group] for group in required)
        partial = (
            in_period and groups["hbm_subject"] and groups["supply_state"]
        )
        role = (
            "HBM_supply_with_Dell_configuration_or_allocation_bridge"
            if complete
            else "HBM_supply_context"
        )
        if partial and not groups["directional_Dell_bridge"]:
            limitations.append(
                "HBM_market_context_without_Dell_allocation_or_configuration_bridge"
            )

    else:
        groups.update(_unit_role_groups(normalized))
        procurement_or_gpu = bool(
            groups["buyer_or_procurement_context"]
            or re.search(r"[0-9][0-9,]*\s+(?:nvidia\s+)?gpus", normalized)
        )
        dollar_shipments = bool(
            re.search(r"(?:shipments.{0,30}\$|\$.{0,30}shipments)", normalized)
        )
        required = (
            "dell_subject",
            "dell_ai_server",
            "shipment_or_delivery",
            "physical_server_or_system_count",
            "Dell_seller_or_shipper_role",
            "company_period_surface",
        )
        complete = (
            in_period
            and all(groups[group] for group in required)
            and not procurement_or_gpu
            and not dollar_shipments
        )
        partial = (
            in_period
            and base["dell_ai_server"]
            and groups["shipment_or_delivery"]
        )
        role = (
            "Dell_company_period_physical_server_shipments"
            if complete
            else "qualitative_shipment_or_noncompany_count_context"
        )
        if procurement_or_gpu:
            limitations.append(
                "buyer_procurement_or_GPU_count_is_not_Dell_company_server_shipments"
            )
        if dollar_shipments:
            limitations.append("shipment_value_is_not_physical_units")
        if groups["physical_server_or_system_count"] and not groups[
            "Dell_seller_or_shipper_role"
        ]:
            limitations.append("Dell_brand_is_not_Dell_seller_or_shipper_role")
        if groups["Dell_seller_or_shipper_role"] and not groups[
            "company_period_surface"
        ]:
            limitations.append("company_period_surface_missing")

    matched = sorted(group for group, hit in groups.items() if hit)
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
    value = str(row.get("evidence_id") or "").strip()
    _require(bool(value), "dell_03B_R4_source_evidence_id_missing")
    return value


def _canonical_source_family_id(row: Mapping[str, Any]) -> str:
    source_id = _source_id(row)
    metadata = dict(row.get("metadata") or {})
    page_id = str(metadata.get("source_page_record_id") or "").strip()
    if page_id:
        return page_id
    if "::SLICE::" in source_id:
        return source_id.split("::SLICE::", 1)[0]
    return source_id


def _object_family_id(row: Mapping[str, Any]) -> str:
    base = dict(row.get("base_object_view") or {})
    lineage = dict(base.get("source_lineage") or {})
    page_id = str(lineage.get("source_page_record_id") or "").strip()
    if page_id:
        return page_id
    source_id = str(base.get("source_record_id") or "").strip()
    if "::SLICE::" in source_id:
        return source_id.split("::SLICE::", 1)[0]
    _require(bool(source_id), "dell_03B_R4_object_source_missing")
    return source_id


def _source_families(
    source_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_order: dict[str, int] = {}
    seen: set[str] = set()
    for index, raw in enumerate(source_rows):
        row = dict(raw)
        source_id = _source_id(row)
        _require(source_id not in seen, f"dell_03B_R4_source_duplicate:{source_id}")
        seen.add(source_id)
        source_order[source_id] = index
        families[_canonical_source_family_id(row)].append(row)
    return dict(families), source_order


def _family_slice_order(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    for row in rows:
        metadata = dict(row.get("metadata") or {})
        slice_ids = [
            str(value) for value in metadata.get("source_content_slice_ids") or ()
        ]
        if metadata.get("object_level") == "source_page_lineage_parent" and slice_ids:
            return {source_id: index for index, source_id in enumerate(slice_ids)}
    return {}


def _source_units_for_family(
    rows: Sequence[Mapping[str, Any]], source_order: Mapping[str, int]
) -> list[dict[str, Any]]:
    slice_order = _family_slice_order(rows)
    if slice_order:
        scoped = [row for row in rows if _source_id(row) in slice_order]
        scoped.sort(key=lambda row: slice_order[_source_id(row)])
    else:
        scoped = sorted(rows, key=lambda row: source_order[_source_id(row)])
    units: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in scoped:
        for sentence in _sentence_units(str(row.get("text") or "")):
            normalized = _normalize_text(sentence)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            units.append(
                {
                    "unit_id": f"{_source_id(row)}::SENT::{len(units):05d}",
                    "source_record_id": _source_id(row),
                    "text": sentence,
                    "position": len(units),
                }
            )
    return units


def _ordered_object_units(
    *,
    object_rows: Sequence[Mapping[str, Any]],
    families: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    slice_orders = {
        family_id: _family_slice_order(rows)
        for family_id, rows in families.items()
    }
    for input_index, raw in enumerate(object_rows):
        row = dict(raw)
        object_id = str(row.get("compiled_object_id") or "").strip()
        _require(bool(object_id), "dell_03B_R4_object_id_missing")
        family_id = _object_family_id(row)
        _require(
            family_id in families,
            f"dell_03B_R4_object_family_missing:{family_id}",
        )
        base = dict(row.get("base_object_view") or {})
        lineage = dict(base.get("source_lineage") or {})
        focus = dict(base.get("focus_binding") or {})
        slice_id = str(lineage.get("source_slice_record_id") or "")
        slice_order = slice_orders[family_id]
        grouped[family_id].append(
            {
                "unit_id": object_id,
                "object": row,
                "text": str(row.get("model_text") or ""),
                "slice_index": slice_order.get(slice_id, 0),
                "char_start": int(focus.get("char_start") or -1),
                "input_index": input_index,
            }
        )
    for family_id, units in grouped.items():
        units.sort(
            key=lambda unit: (
                unit["slice_index"],
                unit["char_start"],
                unit["input_index"],
            )
        )
        for position, unit in enumerate(units):
            unit["position"] = position
    return dict(grouped)


def _target_hint(target_id: str, text: str) -> bool:
    normalized = _normalize_text(text)
    terms = {
        "DELL-RSQ-03A-TARGET-ASP": ("$", "price", "dell", "poweredge", "server"),
        "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH": (
            "dell",
            "nvidia",
            "partner",
            "deliver",
            "supply",
        ),
        "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE": (
            "capacity",
            "allocation",
            "shipping",
            "factory",
            "blackwell",
            "hbm",
        ),
        "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD": (
            "yield",
            "utilization",
            "wafer",
            "hbm",
            "cowos",
        ),
        "DELL-RSQ-03A-TARGET-HBM-SUPPLY": (
            "hbm",
            "high bandwidth memory",
            "supply",
            "capacity",
        ),
        "DELL-RSQ-03A-TARGET-UNITS": (
            "shipped",
            "shipments",
            "delivered",
            "delivery",
            "poweredge",
            "server",
        ),
    }[target_id]
    return any(term in normalized for term in terms)


def _package_windows(
    *,
    target_id: str,
    units: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any],
    selected_object_ids: set[str] | None,
    rank_by_object_id: Mapping[str, int] | None,
) -> list[dict[str, Any]]:
    if not units:
        return []
    interesting = {
        int(unit["position"])
        for unit in units
        if _target_hint(target_id, str(unit.get("text") or ""))
    }
    starts = {
        max(0, position - offset)
        for position in interesting
        for offset in range(MAX_ADJACENT_UNITS)
    }
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for start in sorted(starts):
        raw_window = units[start : start + MAX_ADJACENT_UNITS]
        visible = [
            unit
            for unit in raw_window
            if selected_object_ids is None
            or str(unit["unit_id"]) in selected_object_ids
        ]
        if not visible:
            continue
        identity = tuple(str(unit["unit_id"]) for unit in visible)
        if identity in seen:
            continue
        seen.add(identity)
        text = "\n".join(str(unit.get("text") or "") for unit in visible)
        assessment = classify_dell_report_internal_chain_r4_package(
            target_id=target_id,
            text=text,
            metadata=metadata,
        )
        assessment.update(
            {
                "unit_ids": list(identity),
                "window_start_position": int(raw_window[0]["position"]),
                "window_end_position": int(raw_window[-1]["position"]),
                "window_unit_span": (
                    int(raw_window[-1]["position"])
                    - int(raw_window[0]["position"])
                    + 1
                ),
                "completion_rank": None,
            }
        )
        if (
            assessment["classification"] == "complete_bounded_target_package"
            and rank_by_object_id
        ):
            hits: dict[str, list[int]] = defaultdict(list)
            for unit in visible:
                unit_id = str(unit["unit_id"])
                rank = rank_by_object_id.get(unit_id)
                if rank is None:
                    continue
                unit_assessment = classify_dell_report_internal_chain_r4_package(
                    target_id=target_id,
                    text=str(unit.get("text") or ""),
                    metadata=metadata,
                )
                for group in unit_assessment["matched_group_ids"]:
                    hits[group].append(int(rank))
            required = assessment["required_group_ids"]
            if all(hits.get(group) for group in required):
                assessment["completion_rank"] = max(
                    min(hits[group]) for group in required
                )
        output.append(assessment)
    return output


def _best_package(
    windows: Sequence[Mapping[str, Any]],
    *,
    family_id: str,
    metadata: Mapping[str, Any],
    object_package: bool,
) -> dict[str, Any]:
    priority = {
        "complete_bounded_target_package": 0,
        "partial_context_only": 1,
        "not_target_semantic_equivalent": 2,
    }
    if windows:
        selected = min(
            windows,
            key=lambda row: (
                priority[str(row["classification"])],
                row.get("completion_rank")
                if row.get("completion_rank") is not None
                else 10**9,
                -len(row.get("matched_group_ids") or ()),
                int(row.get("window_unit_span") or 10**9),
                tuple(row.get("unit_ids") or ()),
            ),
        )
        value = dict(selected)
    else:
        value = classify_dell_report_internal_chain_r4_package(
            target_id=str(metadata.get("target_id") or ""),
            text="",
            metadata=metadata,
        )
        value.update(
            {
                "unit_ids": [],
                "window_start_position": None,
                "window_end_position": None,
                "window_unit_span": 0,
                "completion_rank": None,
            }
        )
    value["canonical_source_family_id"] = family_id
    value["source_record_id"] = family_id
    if object_package:
        value["compiled_object_ids"] = list(value.pop("unit_ids"))
    else:
        value["source_sentence_unit_ids"] = list(value.pop("unit_ids"))
    return value


def _material_fingerprint(
    target_id: str, sentence: str, metadata: Mapping[str, Any]
) -> dict[str, Any] | None:
    if not _target_hint(target_id, sentence):
        return None
    normalized = _normalize_text(sentence)
    assessment = classify_dell_report_internal_chain_r4_package(
        target_id=target_id,
        text=sentence,
        metadata=metadata,
    )
    groups = set(assessment["matched_group_ids"])
    required_groups: set[str] = set()
    if target_id == "DELL-RSQ-03A-TARGET-ASP":
        explicit_configuration_price_role = _has_any(
            normalized,
            (
                "quoted price",
                "purchase price",
                "configuration price",
                "contract amount",
                "contract cost",
                "total contract cost",
                "recommended price",
            ),
        )
        if (
            "price_surface" in groups
            and explicit_configuration_price_role
            and "dell_subject" in groups
        ):
            required_groups = {"price_surface"}
        elif {"dell_ai_server", "valid_denominator"}.issubset(groups):
            required_groups = {"dell_ai_server", "valid_denominator"}
    elif target_id == "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH":
        candidate = {
            "dell_subject",
            "named_supplier",
            "directional_relationship_delivery",
        }
        if candidate.issubset(groups):
            required_groups = candidate
    elif target_id == "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE":
        candidate = {
            "relevant_supply",
            "capacity_or_availability_event",
            "timing_surface",
        }
        if candidate.issubset(groups):
            required_groups = candidate
    elif target_id == "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD":
        candidate = {
            "relevant_supply",
            "observed_yield_or_utilization",
            "observed_measure",
        }
        if candidate.issubset(groups):
            required_groups = candidate
    elif target_id == "DELL-RSQ-03A-TARGET-HBM-SUPPLY":
        candidate = {"hbm_subject", "supply_state", "time_surface"}
        if candidate.issubset(groups):
            required_groups = candidate
    elif assessment["classification"] == "complete_bounded_target_package":
        required_groups = set(assessment["required_group_ids"])
    if not required_groups:
        return None
    anchors = sorted(
        set(
            re.findall(
                r"(?:\$\s*[0-9][0-9,]*(?:\.[0-9]+)?|"
                r"[0-9][0-9,]*(?:\.[0-9]+)?%?|"
                r"\b(?:thousand|thousands|million|millions|billion|billions|"
                r"week|weeks|quarter|quarters|q[1-4]|fy\s*\d{2,4})\b)",
                normalized,
            )
        )
    )
    return {
        "normalized_sentence": normalized,
        "sentence_digest": canonical_digest(normalized),
        "required_material_group_ids": sorted(required_groups),
        "material_anchors": anchors,
    }


def _coverage_gaps(
    *,
    target_id: str,
    family_id: str,
    family_rows: Sequence[Mapping[str, Any]],
    source_units: Sequence[Mapping[str, Any]],
    compiled_windows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    metadata = family_rows[0]
    occurrence_counts: dict[str, int] = defaultdict(int)
    occurrence_source_ids: dict[str, set[str]] = defaultdict(set)
    fingerprints: dict[str, dict[str, Any]] = {}
    for row in family_rows:
        for sentence in _sentence_units(str(row.get("text") or "")):
            fingerprint = _material_fingerprint(target_id, sentence, row)
            if fingerprint is None:
                continue
            digest = str(fingerprint["sentence_digest"])
            occurrence_counts[digest] += 1
            occurrence_source_ids[digest].add(_source_id(row))
            fingerprints.setdefault(digest, fingerprint)
    # Source-unit materiality is authoritative for canonical-family dedup; the
    # all-row pass above only preserves the raw parent/slice occurrence count.
    canonical_digests = {
        str(fingerprint["sentence_digest"])
        for unit in source_units
        if (
            fingerprint := _material_fingerprint(
                target_id, str(unit.get("text") or ""), metadata
            )
        )
        is not None
    }
    gaps: list[dict[str, Any]] = []
    for digest in sorted(canonical_digests):
        fingerprint = fingerprints[digest]
        groups = set(fingerprint["required_material_group_ids"])
        anchors = set(fingerprint["material_anchors"])
        covered = False
        for window in compiled_windows:
            if not groups.issubset(set(window.get("matched_group_ids") or ())):
                continue
            compiled_text = _normalize_text(window.get("model_text") or "")
            if all(anchor in compiled_text for anchor in anchors):
                covered = True
                break
        if not covered:
            gaps.append(
                {
                    "target_id": target_id,
                    "canonical_source_family_id": family_id,
                    "source_record_ids": sorted(occurrence_source_ids[digest]),
                    "source_occurrence_count": occurrence_counts[digest],
                    "material_sentence_digest": digest,
                    "required_material_group_ids": sorted(groups),
                    "material_anchors": sorted(anchors),
                    "reason": (
                        "canonical_material_source_claim_missing_from_bounded_"
                        "compiled_object_windows"
                    ),
                }
            )
    return gaps


def build_dell_report_internal_chain_r4_corpus_index(
    *,
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Precompute stable family/order state once for all targets and pools."""

    families, source_order = _source_families(source_rows)
    return {
        "families": families,
        "source_order": source_order,
        "source_units_by_family": {
            family_id: _source_units_for_family(rows, source_order)
            for family_id, rows in families.items()
        },
        "objects_by_family": _ordered_object_units(
            object_rows=object_rows,
            families=families,
        ),
        "source_record_count": len(source_rows),
        "compiled_object_count": len(object_rows),
    }


def assess_dell_report_internal_chain_r4_packages(
    *,
    target_id: str,
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
    selected_object_ids: Iterable[str] | None = None,
    rank_by_object_id: Mapping[str, int] | None = None,
    corpus_index: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess canonical families with bounded adjacency and material coverage."""

    index = (
        dict(corpus_index)
        if corpus_index is not None
        else build_dell_report_internal_chain_r4_corpus_index(
            source_rows=source_rows,
            object_rows=object_rows,
        )
    )
    _require(
        int(index.get("source_record_count") or 0) == len(source_rows)
        and int(index.get("compiled_object_count") or 0) == len(object_rows),
        "dell_03B_R4_corpus_index_population_drift",
    )
    families = dict(index["families"])
    source_units_by_family = dict(index["source_units_by_family"])
    objects_by_family = dict(index["objects_by_family"])
    selected = set(selected_object_ids) if selected_object_ids is not None else None
    source_packages: list[dict[str, Any]] = []
    compiled_packages: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    family_ids = (
        sorted(families)
        if selected is None
        else sorted(
            family_id
            for family_id, units in objects_by_family.items()
            if any(str(unit["unit_id"]) in selected for unit in units)
        )
    )
    for family_id in family_ids:
        family_rows = families[family_id]
        metadata = {**dict(family_rows[0]), "target_id": target_id}
        source_units = list(source_units_by_family[family_id])
        if selected is None:
            source_windows = _package_windows(
                target_id=target_id,
                units=source_units,
                metadata=metadata,
                selected_object_ids=None,
                rank_by_object_id=None,
            )
            source_packages.append(
                _best_package(
                    source_windows,
                    family_id=family_id,
                    metadata=metadata,
                    object_package=False,
                )
            )
        object_units = objects_by_family.get(family_id, [])
        object_windows = _package_windows(
            target_id=target_id,
            units=object_units,
            metadata=metadata,
            selected_object_ids=selected,
            rank_by_object_id=rank_by_object_id,
        )
        compiled_packages.append(
            _best_package(
                object_windows,
                family_id=family_id,
                metadata=metadata,
                object_package=True,
            )
        )
        if selected is None:
            coverage.extend(
                _coverage_gaps(
                    target_id=target_id,
                    family_id=family_id,
                    family_rows=family_rows,
                    source_units=source_units,
                    compiled_windows=object_windows,
                )
            )
    return {
        "source_packages": source_packages,
        "compiled_packages": compiled_packages,
        "coverage_gaps": coverage,
        "coverage_gap_canonical_family_claim_count": len(coverage),
        "coverage_gap_source_occurrence_count": sum(
            int(row["source_occurrence_count"]) for row in coverage
        ),
    }


def _complete_ids(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        str(row.get("canonical_source_family_id") or "")
        for row in rows
        if row.get("classification") == "complete_bounded_target_package"
    }


def _partial_ids(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        str(row.get("canonical_source_family_id") or "")
        for row in rows
        if row.get("classification") == "partial_context_only"
    }


def _rank_map(
    object_ids: set[str],
    request_results: Sequence[Mapping[str, Any]],
    rank_field: str,
) -> dict[str, int]:
    result: dict[str, int] = {}
    for object_id in object_ids:
        trace = legacy._candidate_trace(object_id, request_results)  # noqa: SLF001
        rank = trace.get(rank_field)
        if rank is not None:
            result[object_id] = int(rank)
    return result


def _public_package(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "canonical_source_family_id",
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
            "window_start_position",
            "window_end_position",
            "window_unit_span",
            "completion_rank",
        )
    }


def _residual_scope(target_id: str, complete_source_ids: set[str]) -> list[str]:
    if target_id == "DELL-RSQ-03A-TARGET-ASP":
        return ["Dell_company_realized_AI_server_ASP_and_mix"]
    if target_id == "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH":
        return ["supplier_capacity_allocation_or_constraint_to_Dell"]
    if target_id == "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE":
        return ["upstream_capacity_release_timetable_and_Dell_allocation"]
    if target_id == "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD":
        return ["current_observed_relevant_supply_yield_or_utilization"]
    if target_id == "DELL-RSQ-03A-TARGET-HBM-SUPPLY":
        return ["HBM_supply_with_Dell_configuration_or_allocation_bridge"]
    if target_id == "DELL-RSQ-03A-TARGET-UNITS":
        return ["Dell_company_period_physical_AI_server_shipments"]
    return [] if complete_source_ids else ["complete_target"]


def compile_dell_report_internal_chain_ceiling_r4_result(
    *,
    legacy_policy: Mapping[str, Any],
    r4_policy: Mapping[str, Any],
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
    target_contracts = list(legacy_policy.get("target_contracts") or ())
    expected_request_ids = {
        str(request_id)
        for contract in target_contracts
        for request_id in contract.get("request_ids") or ()
    }
    validated = r3.validate_dell_report_internal_chain_ceiling_r3_execution(
        execution,
        expected_request_ids=expected_request_ids,
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
        bool(re.fullmatch(r"[0-9a-f]{64}", execution_sha256))
        and execution_sha256 == actual_execution_sha256,
        "dell_03B_R4_execution_sha_mismatch",
    )
    source_ids_list = [_source_id(row) for row in source_rows]
    objects_by_id, source_ids = (
        legacy.validate_dell_report_source_compiled_identity_population(
            object_rows=object_rows,
            source_record_ids=source_ids_list,
            runtime_binding_receipt=runtime_binding_receipt,
        )
    )
    request_by_id = validated["request_results_by_id"]
    corpus_index = build_dell_report_internal_chain_r4_corpus_index(
        source_rows=source_rows,
        object_rows=object_rows,
    )
    residual_by_id = {
        str(row.get("target_id") or ""): dict(row)
        for row in residual_program.get("route_targets") or ()
        if isinstance(row, Mapping)
    }

    target_results: list[dict[str, Any]] = []
    total_union_occurrences = 0
    for contract in sorted(
        target_contracts, key=lambda row: str(row.get("target_id"))
    ):
        target_id = str(contract.get("target_id") or "")
        scoped_results = [
            request_by_id[str(request_id)]
            for request_id in contract.get("request_ids") or ()
        ]
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
            f"dell_03B_R4_candidate_object_binding_invalid:{target_id}",
        )
        total_union_occurrences += len(union_ids)
        corpus = assess_dell_report_internal_chain_r4_packages(
            target_id=target_id,
            source_rows=source_rows,
            object_rows=object_rows,
            corpus_index=corpus_index,
        )
        union_rank = _rank_map(
            union_ids, scoped_results, "minimum_raw_union_rank"
        )
        union = assess_dell_report_internal_chain_r4_packages(
            target_id=target_id,
            source_rows=source_rows,
            object_rows=object_rows,
            selected_object_ids=union_ids,
            rank_by_object_id=union_rank,
            corpus_index=corpus_index,
        )
        final_rank = _rank_map(
            final_ids, scoped_results, "minimum_final_output_rank"
        )
        final = assess_dell_report_internal_chain_r4_packages(
            target_id=target_id,
            source_rows=source_rows,
            object_rows=object_rows,
            selected_object_ids=final_ids,
            rank_by_object_id=final_rank,
            corpus_index=corpus_index,
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

        if package_materialization_gaps or coverage_gaps:
            earliest = "local_source_to_object_materialization_or_coverage_gap"
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
            if row.get("canonical_source_family_id") in final_complete
            and row.get("completion_rank") is not None
        ]
        best_final_rank = min(completion_ranks, default=None)
        embedding_eligible = bool(
            coverage_pass and compiled_complete and not union_complete
        )
        reranker_eligible = bool(
            coverage_pass
            and union_complete
            and (best_final_rank is None or best_final_rank > 10)
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
                if row.get("classification")
                != "not_target_semantic_equivalent"
            ),
            key=lambda row: (
                row.get("classification")
                != "complete_bounded_target_package",
                row.get("completion_rank") or 10**9,
                row.get("canonical_source_family_id") or "",
            ),
        )[:20]
        target_results.append(
            {
                "target_id": target_id,
                "pack_gap_id": residual_target.get("pack_gap_id"),
                "target_proposition": residual_target.get("target_proposition"),
                "request_ids": list(contract.get("request_ids") or ()),
                "semantic_evidence_unit": (
                    "bounded_eight_unit_canonical_source_family_window"
                ),
                "candidate_ceiling": {
                    "source_record_population": len(source_ids),
                    "canonical_source_family_population": len(
                        corpus["source_packages"]
                    ),
                    "compiled_object_population": len(objects_by_id),
                    "complete_target_in_source_record_corpus_count": len(
                        source_complete
                    ),
                    "complete_target_in_compiled_package_corpus_count": len(
                        compiled_complete
                    ),
                    "partial_context_in_source_record_corpus_count": len(
                        source_partial
                    ),
                    "partial_context_in_compiled_package_corpus_count": len(
                        compiled_partial
                    ),
                    "candidate_union_object_count": len(union_ids),
                    "complete_target_in_candidate_union_package_count": len(
                        union_complete
                    ),
                    "final_review_object_count": len(final_ids),
                    "complete_target_in_final_review_package_count": len(
                        final_complete
                    ),
                    "best_complete_package_final_completion_rank": best_final_rank,
                    "complete_target_useful_at_10": bool(
                        best_final_rank is not None and best_final_rank <= 10
                    ),
                    "earliest_observed_limitation": earliest,
                    "package_materialization_gap_count": len(
                        package_materialization_gaps
                    ),
                    "material_source_claim_coverage_gap_canonical_count": len(
                        coverage_gaps
                    ),
                    "material_source_claim_coverage_gap_occurrence_count": corpus[
                        "coverage_gap_source_occurrence_count"
                    ],
                    "source_to_object_semantic_coverage_pass": coverage_pass,
                    "source_package_scan_digest": canonical_digest(
                        [
                            {
                                key: row.get(key)
                                for key in (
                                    "canonical_source_family_id",
                                    "classification",
                                    "package_role",
                                    "matched_group_ids",
                                    "limitations",
                                    "window_start_position",
                                    "window_end_position",
                                )
                            }
                            for row in corpus["source_packages"]
                        ]
                    ),
                    "candidate_decision_state": (
                        "candidate_not_evidence_unadjudicated"
                    ),
                    "public_information_gap_eligible": False,
                },
                "downstream_disposition": {
                    "03D_4B_embedding_recall_challenger_eligible": (
                        embedding_eligible
                    ),
                    "03D_same_pool_reranker_challenger_eligible": (
                        reranker_eligible
                    ),
                    "03C_external_route_required_for_complete_bounded_target": (
                        external_required
                    ),
                    "03C_scope_if_authorized": (
                        residual if external_required else []
                    ),
                    "03C_residual_route_requires_prior_capture_crosswalk": bool(
                        residual
                    ),
                    "03C_residual_scope_if_authorized": residual,
                    "remaining_non_03C_research_boundaries": residual,
                    "local_source_to_object_repair_required": bool(
                        package_materialization_gaps or coverage_gaps
                    ),
                    "mandatory_external_route_contract_ids_if_authorized": (
                        mandatory_external_routes if external_required else []
                    ),
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
        "status": "dell_03B_R4_semantic_and_material_coverage_ceiling_executed",
        "attempt_id": ATTEMPT_ID,
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": "DELL",
        "input_bindings": dict(input_bindings),
        "runtime_registry": {
            "registry_id": runtime_registry.get("registry_id"),
            "resource_canonical_digest": runtime_registry.get(
                "resource_canonical_digest"
            ),
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
                row["downstream_disposition"][
                    "03D_4B_embedding_recall_challenger_eligible"
                ]
                is True
                for row in target_results
            ),
            "reranker_challenger_eligible_target_count": sum(
                row["downstream_disposition"][
                    "03D_same_pool_reranker_challenger_eligible"
                ]
                is True
                for row in target_results
            ),
            "external_route_required_target_count": sum(
                row["downstream_disposition"][
                    "03C_external_route_required_for_complete_bounded_target"
                ]
                is True
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
                row["downstream_disposition"][
                    "local_source_to_object_repair_required"
                ]
                is True
                for row in target_results
            ),
            **{
                field: execution_summary[field]
                for field in ZERO_EXECUTION_FIELDS
            },
        },
        "authority": {
            "03B_R4_execution_consumed": True,
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
            "R4 uses canonical-family deduplication, at most eight adjacent "
            "source/object units, explicit supplier negation, observed-yield, "
            "Dell seller/shipper and company-period role guards, plus material "
            "anchor coverage. Configuration prices remain non-company ASP; "
            "candidates remain non-Evidence. No 03C, 4B, reranker, promotion, "
            "gap closure, human, report, product, publication or release "
            "authority is granted."
        ),
        "policy_digest": r4_policy.get("result_digest"),
    }
    return {**body, "result_digest": canonical_digest(body)}


def build_dell_report_internal_chain_ceiling_r4_public_projection(
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
        "validated_execution_digest": private_result.get(
            "validated_execution_digest"
        ),
        "execution_summary": dict(
            private_result.get("execution_summary") or {}
        ),
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
    _require("model_text" not in serialized, "dell_03B_R4_public_model_text_leak")
    _require(
        "material_sentence" not in serialized,
        "dell_03B_R4_public_sentence_leak",
    )
    _require(
        "http://" not in serialized and "https://" not in serialized,
        "dell_03B_R4_public_url_leak",
    )
    return {**body, "result_digest": canonical_digest(body)}


__all__ = [
    "ATTEMPT_ID",
    "ATTEMPT_RECEIPT_REF",
    "BRANCH",
    "DellReportInternalChainCeilingR4Error",
    "EXECUTION_CONTRACT",
    "POLICY_REF",
    "POLICY_SCHEMA_VERSION",
    "PRIVATE_REF",
    "PRIVATE_RESULT_SCHEMA_VERSION",
    "PUBLIC_REF",
    "PUBLIC_RESULT_SCHEMA_VERSION",
    "assess_dell_report_internal_chain_r4_packages",
    "build_dell_report_internal_chain_r4_corpus_index",
    "build_dell_report_internal_chain_ceiling_r4_public_projection",
    "classify_dell_report_internal_chain_r4_package",
    "compile_dell_report_internal_chain_ceiling_r4_result",
    "validate_dell_report_internal_chain_ceiling_r4_policy",
]
