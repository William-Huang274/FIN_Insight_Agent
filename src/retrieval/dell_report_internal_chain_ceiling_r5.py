from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence

from . import dell_report_internal_chain_ceiling as legacy
from . import dell_report_internal_chain_ceiling_r3 as r3
from . import dell_report_internal_chain_ceiling_r4 as r4
from .query_plan import canonical_digest


POLICY_SCHEMA_VERSION = "fin_ia_dell_report_internal_chain_ceiling_policy_v1_4"
PRIVATE_RESULT_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_candidate_ceiling_private_result_v1_4"
)
PUBLIC_RESULT_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_candidate_ceiling_result_v1_4"
)
ATTEMPT_ID = "dell-rsq-03b-internal-chain-r5"
PROGRAM_ID = "FIN-0.1.3-S1-DELL-RSQ-03B-R5"
BRANCH = r4.BRANCH
POLICY_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_4.json"
)
PUBLIC_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_4.json"
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
MAX_ADJACENT_UNITS = r4.MAX_ADJACENT_UNITS
MIN_FREE_BYTES_BEFORE_ATTEMPT = 512 * 1024 * 1024
TARGET_IDS = r4.TARGET_IDS
ZERO_EXECUTION_FIELDS = r4.ZERO_EXECUTION_FIELDS
EXECUTION_CONTRACT = dict(r4.EXECUTION_CONTRACT)
AUTHORITY = dict(r4.AUTHORITY)
SEMANTIC_CONTRACT = {
    "canonical_source_family_mode": (
        "page_parent_and_slice_family_with_raw_occurrence_positions"
    ),
    "adjacency_order_mode": (
        "raw_sentence_occurrence_before_dedup_then_absolute_position"
    ),
    "maximum_adjacent_source_or_object_units": MAX_ADJACENT_UNITS,
    "selected_pool_adjacency_mode": (
        "absolute_corpus_positions_not_selected_only_positions"
    ),
    "supplier_role": (
        "positive_named_supplier_Dell_direction_with_scoped_polarity_guard"
    ),
    "yield_role": (
        "observed_measure_with_future_plan_forecast_pilot_process_guard"
    ),
    "units_role": (
        "Dell_subject_seller_shipper_company_period_physical_server_count"
    ),
    "ASP_role": (
        "bounded_configuration_or_bundle_price_not_company_realized_ASP"
    ),
    "material_coverage_mode": (
        "target_role_and_typed_token_exact_numeric_time_anchor_coverage"
    ),
    "coverage_count_mode": (
        "canonical_claim_and_raw_source_occurrence_both_reported"
    ),
    "reranker_useful_at_k": 10,
    "candidate_not_evidence": True,
}
EXPECTED_IMPLEMENTATION_PATHS = frozenset(
    set(r4.EXPECTED_IMPLEMENTATION_PATHS)
    | {
        "src/retrieval/dell_report_internal_chain_ceiling_r5.py",
        "scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r5.py",
    }
)
EXPECTED_BOUND_INPUT_IDS = frozenset(
    set(r4.EXPECTED_BOUND_INPUT_IDS)
    | {
        "R4_policy",
        "R4_public",
        "R4_private",
        "R4_fresh_audit",
        "R4_audit_correction",
    }
)
R4_AUDIT_STATUS = (
    "fail_material_semantic_route_and_report_findings_same_stage_R5_required"
)
R4_REQUIRED_ROOT_CAUSES = {
    "RC-S1-077-DELL-03B-dedup-before-position-and-substring-anchor-equivalence",
    "RC-S1-078-DELL-03B-polarity-direction-shipper-future-and-process-guards-incomplete",
}


class DellReportInternalChainCeilingR5Error(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellReportInternalChainCeilingR5Error(code)


def _self_digest(value: Mapping[str, Any]) -> bool:
    body = dict(value)
    observed = str(body.pop("result_digest", ""))
    return bool(observed) and observed == canonical_digest(body)


def validate_dell_report_internal_chain_ceiling_r5_policy(
    policy: Mapping[str, Any],
    *,
    r1_policy: Mapping[str, Any],
    r3_policy: Mapping[str, Any],
    r3_public: Mapping[str, Any],
    r3_private: Mapping[str, Any],
    r3_fresh_audit: Mapping[str, Any],
    r4_policy: Mapping[str, Any],
    r4_public: Mapping[str, Any],
    r4_private: Mapping[str, Any],
    r4_fresh_audit: Mapping[str, Any],
    r4_audit_correction: Mapping[str, Any],
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
    """Fail closed on R5 scope, immutable R4 failure and authority drift."""

    validated_r1 = r4.validate_dell_report_internal_chain_ceiling_r4_policy(
        r4_policy,
        r1_policy=r1_policy,
        r3_policy=r3_policy,
        r3_public=r3_public,
        r3_private=r3_private,
        r3_fresh_audit=r3_fresh_audit,
        r39_repair_result=r39_repair_result,
        r39_embedding_result=r39_embedding_result,
        r39_route_policy=r39_route_policy,
        r39_hybrid_policy=r39_hybrid_policy,
        runtime_registry=runtime_registry,
        runtime_binding_receipt=runtime_binding_receipt,
        residual_program=residual_program,
        execution_program=execution_program,
        dell_product_readiness=dell_product_readiness,
    )
    _require(_self_digest(policy), "dell_03B_R5_policy_digest_invalid")
    _require(
        policy.get("schema_version") == POLICY_SCHEMA_VERSION
        and policy.get("status")
        == "same_stage_R5_execution_authorized_after_fresh_R4_audit_failure"
        and policy.get("program_id") == PROGRAM_ID
        and policy.get("attempt_id") == ATTEMPT_ID,
        "dell_03B_R5_policy_identity_invalid",
    )
    _require(
        dict(policy.get("execution_contract") or {}) == EXECUTION_CONTRACT
        and dict(policy.get("semantic_contract") or {}) == SEMANTIC_CONTRACT
        and dict(policy.get("authority") or {}) == AUTHORITY,
        "dell_03B_R5_policy_contract_invalid",
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
        "dell_03B_R5_output_contract_invalid",
    )
    _require(
        output.get("minimum_free_bytes_before_attempt")
        == MIN_FREE_BYTES_BEFORE_ATTEMPT,
        "dell_03B_R5_output_capacity_contract_invalid",
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
        "dell_03B_R5_bound_inputs_invalid",
    )
    bindings = list(policy.get("implementation_bindings") or ())
    _require(
        {str(row.get("path") or "") for row in bindings}
        == EXPECTED_IMPLEMENTATION_PATHS
        and all(
            isinstance(row, Mapping)
            and bool(re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256") or "")))
            for row in bindings
        ),
        "dell_03B_R5_implementation_bindings_invalid",
    )
    identity = dict(policy.get("execution_identity") or {})
    _require(
        identity.get("branch") == BRANCH
        and bool(
            re.fullmatch(
                r"[0-9a-f]{40}",
                str(identity.get("implementation_commit") or ""),
            )
        )
        and bool(
            re.fullmatch(
                r"[0-9a-f]{40}",
                str(identity.get("implementation_tree") or ""),
            )
        )
        and identity.get("authority_commit_changed_paths") == [POLICY_REF]
        and identity.get(
            "authority_commit_parent_must_equal_implementation_commit"
        )
        is True
        and identity.get("HEAD_must_equal_upstream") is True,
        "dell_03B_R5_execution_identity_invalid",
    )
    token_basis = dict(policy.get("TokenBudgetBasis") or {})
    token_fields = {
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
        set(token_basis) == token_fields
        and all(str(token_basis[field]).strip() for field in token_fields),
        "dell_03B_R5_token_budget_basis_invalid",
    )

    _require(
        r4_fresh_audit.get("schema_version")
        == "fin_ia_independent_readonly_audit_result_v1_0"
        and r4_fresh_audit.get("status") == R4_AUDIT_STATUS
        and r4_fresh_audit.get("verdicts", {}).get("overall") == "FAIL"
        and r4_fresh_audit.get("verdicts", {}).get("new_R4_P0_P1_P2_P3")
        == [0, 1, 1, 0]
        and r4_fresh_audit.get("authority", {}).get(
            "R5_same_stage_successor_authorized"
        )
        is True
        and r4_fresh_audit.get("authority", {}).get(
            "R4_retry_or_overwrite_authorized"
        )
        is False
        and _self_digest(r4_fresh_audit),
        "dell_03B_R5_predecessor_audit_invalid",
    )
    observed_root_causes = {
        str(row.get("root_cause_id") or "")
        for row in r4_fresh_audit.get("material_findings") or ()
        if isinstance(row, Mapping)
    }
    _require(
        R4_REQUIRED_ROOT_CAUSES.issubset(observed_root_causes),
        "dell_03B_R5_required_root_causes_missing",
    )
    reviewed = dict(r4_fresh_audit.get("reviewed_artifacts") or {})
    correction_original = dict(
        r4_audit_correction.get("original_audit") or {}
    )
    correction_binding = dict(
        r4_audit_correction.get("corrected_binding") or {}
    )
    correction_scope = dict(r4_audit_correction.get("scope") or {})
    _require(
        r4_audit_correction.get("schema_version")
        == "fin_ia_audit_artifact_correction_receipt_v1_0"
        and r4_audit_correction.get("status")
        == "append_only_public_result_digest_transcription_correction_no_verdict_change"
        and correction_original.get("ref")
        == bound_inputs["R4_fresh_audit"].get("ref")
        and correction_original.get("sha256")
        == bound_inputs["R4_fresh_audit"].get("sha256")
        and correction_original.get("result_digest")
        == r4_fresh_audit.get("result_digest")
        and correction_original.get("preserved_unchanged") is True
        and correction_binding.get("field")
        == "reviewed_artifacts.R4_public.result_digest"
        and correction_binding.get("recorded_value")
        == reviewed.get("R4_public", {}).get("result_digest")
        and correction_binding.get("recorded_value_length") == 65
        and correction_binding.get("correct_value")
        == r4_public.get("result_digest")
        and correction_binding.get("correct_value_length") == 64
        and correction_binding.get("R4_public_ref")
        == bound_inputs["R4_public"].get("ref")
        and correction_binding.get("R4_public_sha256")
        == bound_inputs["R4_public"].get("sha256")
        and correction_binding.get("R4_public_self_digest_valid") is True
        and correction_scope.get("correction_only") is True
        and correction_scope.get("changed_source_or_result_files") == 0
        and correction_scope.get("changed_audit_verdicts") == 0
        and correction_scope.get("changed_route_or_authority_decisions") == 0
        and r4_audit_correction.get("authority", {}).get(
            "R5_may_bind_original_audit_plus_this_correction"
        )
        is True
        and _self_digest(r4_audit_correction),
        "dell_03B_R5_R4_audit_correction_invalid",
    )
    _require(
        r4_policy.get("attempt_id") == r4.ATTEMPT_ID
        and r4_public.get("attempt_id") == r4.ATTEMPT_ID
        and r4_private.get("attempt_id") == r4.ATTEMPT_ID
        and r4_policy.get("result_digest")
        == reviewed.get("R4_policy", {}).get("policy_digest")
        and r4_public.get("result_digest")
        == correction_binding.get("correct_value")
        and r4_private.get("result_digest")
        == reviewed.get("R4_private", {}).get("result_digest")
        and r4_public.get("private_result_digest")
        == r4_private.get("result_digest")
        and _self_digest(r4_public)
        and _self_digest(r4_private),
        "dell_03B_R5_R4_result_binding_invalid",
    )
    _require(
        r4_private.get("authority", {}).get("03B_R4_execution_consumed") is True
        and r4_private.get("authority", {}).get(
            "03C_external_capture_authorized"
        )
        is False
        and r4_private.get("authority", {}).get("03D_4B_embedding_authorized")
        is False
        and r4_private.get("authority", {}).get("03D_reranker_authorized")
        is False,
        "dell_03B_R5_R4_authority_boundary_invalid",
    )
    return validated_r1


def _normalize_text(value: Any) -> str:
    return r4._normalize_text(value)  # noqa: SLF001


def _sentence_units(text: str) -> list[str]:
    return r4._sentence_units(text)  # noqa: SLF001


_SUPPLIER_NEGATIVE = re.compile(
    r"(?:\bno\b|\bwithout\b|\black(?:s|ed|ing)?\b|"
    r"\bden(?:y|ies|ied)\b)[^.!?]{0,30}"
    r"(?:partnership|collaboration|delivery|supply\s+relationship)|"
    r"\b(?:not|never|no\s+longer)\s+"
    r"(?:(?:currently|yet|ever|actually)\s+)?"
    r"(?:partnered|partnering|collaborat\w*|deliver\w*|suppl\w*)|"
    r"(?:partnership|collaboration|relationship)[^.!?]{0,30}"
    r"(?:\bwas\b|\bis\b|\bwere\b|\bare\b|\bdid\b|\bdoes\b)"
    r"\s+(?:not|never|denied)\b"
)
_ALLOCATION_NEGATIVE = re.compile(
    r"\b(?:not|never|no\s+longer)\s+"
    r"(?:(?:currently|yet|ever|actually|formally|commercially|fully|"
    r"directly|previously)\s+)?(?:been\s+)?"
    r"(?:allocated|reserved|secured|supplied|available|configured)\b|"
    r"\bno\s+(?:capacity|allocation|supply|availability|configuration)\b|"
    r"\b(?:without|lack(?:s|ed|ing)?)\b[^.!?]{0,20}"
    r"(?:capacity|allocation|supply|availability)\b|"
    r"\bden(?:y|ies|ied)\b[^.!?]{0,30}"
    r"(?:capacity|allocation|supply|availability)\b|"
    r"\bunavailable\b|"
    r"(?:allocation|capacity|supply|availability|configuration)"
    r"[^.!?]{0,40}(?:\bwas\b|\bis\b|\bwere\b|\bare\b)"
    r"\s+(?:not|never|denied)\b"
)
_SHIPMENT_NEGATIVE = re.compile(
    r"\b(?:not|never|no\s+longer)\s+"
    r"(?:(?:currently|yet|ever|actually|formally|commercially)\s+)?"
    r"(?:been\s+)?"
    r"(?:shipped|delivered)\b|"
    r"\bno\s+(?:shipments|deliveries)\b|"
    r"\bwithout\s+(?:shipping|delivering|shipments|deliveries)\b|"
    r"\bden(?:y|ies|ied)\b[^.!?]{0,30}"
    r"(?:shipped|delivered|shipments|deliveries)\b|"
    r"(?:shipments|deliveries)[^.!?]{0,50}"
    r"(?:\bwas\b|\bis\b|\bwere\b|\bare\b)\s+(?:not|never)\b"
)


def _negative_supplier_scope(sentence: str) -> bool:
    return bool(_SUPPLIER_NEGATIVE.search(_normalize_text(sentence)))


def _negative_allocation_scope(sentence: str) -> bool:
    return bool(_ALLOCATION_NEGATIVE.search(_normalize_text(sentence)))


def _negative_shipment_scope(sentence: str) -> bool:
    return bool(_SHIPMENT_NEGATIVE.search(_normalize_text(sentence)))


def _positive_supplier_direction_r5(text: str) -> bool:
    patterns = (
        r"(?:dell\s+and\s+nvidia|nvidia\s+and\s+dell)"
        r".{0,100}(?:partner|collaborat)",
        r"(?:nvidia\s+and\s+dell).{0,100}partnering\s+to\s+deliver",
        r"dell\s+servers?.{0,100}(?:with|powered\s+by)"
        r".{0,50}nvidia.{0,100}(?:shipping|available|deliver)",
        r"(?:allocated|allocation|deliver(?:y|ed)?|suppl(?:y|ies|ied))"
        r".{0,60}(?:to\s+)?dell",
        r"available\s+(?:from|through)\s+dell",
    )
    for sentence in _sentence_units(text):
        normalized = _normalize_text(sentence)
        if any(re.search(pattern, normalized) for pattern in patterns):
            if not _negative_supplier_scope(normalized):
                return True
    return False


_YIELD_MEASURE = re.compile(
    r"(?:yield|utilization)(?:\s+rate|\s+level)?[^.%]{0,40}"
    r"[0-9]{1,3}(?:\.[0-9]+)?%"
)
_YIELD_EXCLUSION = re.compile(
    r"(?:\bfuture\b|\btarget(?:s|ed)?\b|\bexpect(?:s|ed)?\b|"
    r"\bforecast(?:s|ed)?\b|\bplan(?:s|ned)?\b|\bproject(?:s|ed)?\b|"
    r"\bwill\b|\b(?:could|may|might)\b[^.!?]{0,20}"
    r"(?:reach|be|increase|improve|achieve|attain)|\ba14\b|\bsram\b|"
    r"\bn2\b|\bpilot(?:\s+line)?\b|\btrial\b|\btest(?:ing)?\b|"
    r"\bnext\s+process\b)"
)
_YIELD_SUFFIX_EXCLUSION = re.compile(
    r"(?:\ba\s+)?\btarget\b[^.!?]{0,20}\bfuture\b|"
    r"\bwill\s+(?:be\s+)?(?:achieved|attained)\b|"
    r"\ba14\b|\bsram\b|\bn2\b|\bpilot(?:\s+line)?\b|"
    r"\bnext\s+process\b"
)


def _valid_observed_yield_measure_r5(text: str) -> bool:
    for sentence in _sentence_units(text):
        normalized = _normalize_text(sentence)
        measures = list(_YIELD_MEASURE.finditer(normalized))
        for phrase in (
            "at full utilization",
            "near full utilization",
            "below full utilization",
        ):
            measures.extend(re.finditer(re.escape(phrase), normalized))
        for measure in measures:
            clause_start = max(
                normalized.rfind(";", 0, measure.start()),
                normalized.rfind(".", 0, measure.start()),
                normalized.rfind("!", 0, measure.start()),
                normalized.rfind("?", 0, measure.start()),
            )
            prefix = normalized[clause_start + 1 : measure.end()]
            suffix = normalized[measure.end() : measure.end() + 80]
            if _YIELD_EXCLUSION.search(prefix):
                continue
            if _YIELD_SUFFIX_EXCLUSION.search(suffix):
                continue
            return True
    return False


def _positive_dell_allocation_r5(text: str) -> bool:
    patterns = (
        r"(?:capacity|allocation|supply).{0,100}"
        r"(?:allocated|secured|reserved|for|to).{0,40}dell",
        r"(?:allocated|reserved|secured|supplied).{0,60}(?:to\s+)?dell",
        r"dell.{0,80}(?:secured|reserved|was\s+allocated).{0,60}"
        r"(?:capacity|allocation|supply)",
    )
    for sentence in _sentence_units(text):
        normalized = _normalize_text(sentence)
        if re.search(r"\bunavailable\b", normalized):
            continue
        if any(re.search(pattern, normalized) for pattern in patterns):
            if not _negative_allocation_scope(normalized):
                return True
    return False


def _positive_hbm_dell_bridge_r5(text: str) -> bool:
    patterns = (
        r"hbm.{0,180}(?:allocated|configured|available|supply|capacity)"
        r".{0,80}(?:for|to|in|supports?)\s+(?:dell|poweredge)",
        r"(?:dell|poweredge).{0,120}(?:configured|powered).{0,80}hbm",
    )
    for sentence in _sentence_units(text):
        normalized = _normalize_text(sentence)
        if re.search(r"\bunavailable\b", normalized):
            continue
        if any(re.search(pattern, normalized) for pattern in patterns):
            if not _negative_allocation_scope(normalized):
                return True
    return False


_PHYSICAL_SERVER_QUANTITY = (
    r"(?<![$0-9a-z])(?:[0-9][0-9,]*|one|two|three|four|five|six|"
    r"seven|eight|nine|ten)(?:\s*\([0-9]+\))?"
    r"(?:\s+[a-z0-9-]+){0,4}\s+(?:server units|servers|systems)"
    r"(?![0-9a-z])"
)
_DELL_SELLER_PATTERNS = (
    rf"\bdell\b[^.!?]{{0,100}}(?:shipped|delivered)"
    rf"[^.!?]{{0,80}}{_PHYSICAL_SERVER_QUANTITY}",
    rf"{_PHYSICAL_SERVER_QUANTITY}[^.!?]{{0,80}}"
    rf"(?:shipped|delivered)\s+by\s+dell",
    rf"\bdell\b[^.!?]{{0,100}}shipments?\s+of"
    rf"[^.!?]{{0,60}}{_PHYSICAL_SERVER_QUANTITY}",
)
_REPORTED_COUNTERPARTY_SHIPPER = re.compile(
    r"\bdell\b.{0,50}"
    r"(?:said|stated|reported|announced|noted|confirmed)\s+(?:that\s+)?"
    r"(?:(?:the|a|an)\s+)?"
    r"(?:nvidia|amd|intel|micron|tsmc|foxconn|supermicro|"
    r"supplier|customer|partner|distributor)"
    r".{0,80}(?:shipped|delivered)"
)


def _valid_dell_seller_r5(text: str) -> bool:
    for sentence in _sentence_units(text):
        normalized = _normalize_text(sentence)
        if not any(re.search(pattern, normalized) for pattern in _DELL_SELLER_PATTERNS):
            continue
        if _negative_shipment_scope(normalized):
            continue
        if _REPORTED_COUNTERPARTY_SHIPPER.search(normalized):
            continue
        return True
    return False


def _set_group(assessment: dict[str, Any], group: str, hit: bool) -> None:
    groups = set(assessment.get("matched_group_ids") or ())
    if hit:
        groups.add(group)
    else:
        groups.discard(group)
    assessment["matched_group_ids"] = sorted(groups)


def _downgrade_complete(
    assessment: dict[str, Any], *, limitation: str, role: str
) -> None:
    limitations = set(assessment.get("limitations") or ())
    limitations.add(limitation)
    assessment["limitations"] = sorted(limitations)
    if assessment.get("classification") == "complete_bounded_target_package":
        assessment["classification"] = "partial_context_only"
        assessment["package_role"] = role


def classify_dell_report_internal_chain_r5_package(
    *, target_id: str, text: str, metadata: Mapping[str, Any]
) -> dict[str, Any]:
    """Apply the immutable R4 classifier, then fail closed on R5 attacks."""

    assessment = r4.classify_dell_report_internal_chain_r4_package(
        target_id=target_id,
        text=text,
        metadata=metadata,
    )
    assessment["semantic_guard_revision"] = "R5"
    if target_id == "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH":
        hit = _positive_supplier_direction_r5(text)
        _set_group(assessment, "directional_relationship_delivery", hit)
        if not hit:
            _downgrade_complete(
                assessment,
                limitation="negative_or_undirected_supplier_relation_not_affirmative",
                role="supplier_or_relationship_context",
            )
    elif target_id == "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE":
        hit = _positive_dell_allocation_r5(text)
        _set_group(assessment, "upstream_Dell_allocation", hit)
        if not hit:
            _downgrade_complete(
                assessment,
                limitation="negative_or_missing_upstream_Dell_allocation",
                role="product_availability_or_delivery_context",
            )
    elif target_id == "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD":
        hit = _valid_observed_yield_measure_r5(text)
        _set_group(assessment, "observed_measure", hit)
        if not hit:
            _downgrade_complete(
                assessment,
                limitation="prospective_pilot_or_wrong_process_measure_not_observed",
                role="yield_or_utilization_context",
            )
    elif target_id == "DELL-RSQ-03A-TARGET-HBM-SUPPLY":
        hit = _positive_hbm_dell_bridge_r5(text)
        _set_group(assessment, "directional_Dell_bridge", hit)
        if not hit:
            _downgrade_complete(
                assessment,
                limitation="negative_or_missing_HBM_Dell_allocation_bridge",
                role="HBM_supply_context",
            )
    elif target_id == "DELL-RSQ-03A-TARGET-UNITS":
        hit = _valid_dell_seller_r5(text)
        _set_group(assessment, "Dell_seller_or_shipper_role", hit)
        if not hit:
            _downgrade_complete(
                assessment,
                limitation="negative_or_counterparty_shipper_not_Dell_company_units",
                role="qualitative_shipment_or_noncompany_count_context",
            )
    return assessment


def _source_units_for_family_r5(
    rows: Sequence[Mapping[str, Any]], source_order: Mapping[str, int]
) -> list[dict[str, Any]]:
    """Assign immutable positions to every raw sentence occurrence."""

    slice_order = r4._family_slice_order(rows)  # noqa: SLF001
    if slice_order:
        scoped = [row for row in rows if r4._source_id(row) in slice_order]  # noqa: SLF001
        scoped.sort(key=lambda row: slice_order[r4._source_id(row)])  # noqa: SLF001
    else:
        scoped = sorted(
            rows,
            key=lambda row: source_order[r4._source_id(row)],  # noqa: SLF001
        )
    units: list[dict[str, Any]] = []
    for row in scoped:
        source_id = r4._source_id(row)  # noqa: SLF001
        for sentence_index, sentence in enumerate(
            _sentence_units(str(row.get("text") or ""))
        ):
            if not _normalize_text(sentence):
                continue
            position = len(units)
            units.append(
                {
                    "unit_id": (
                        f"{source_id}::RAW-SENT::{sentence_index:05d}"
                    ),
                    "source_record_id": source_id,
                    "text": sentence,
                    "position": position,
                    "raw_occurrence_position": position,
                }
            )
    return units


def build_dell_report_internal_chain_r5_corpus_index(
    *,
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    families, source_order = r4._source_families(source_rows)  # noqa: SLF001
    return {
        "families": families,
        "source_order": source_order,
        "source_units_by_family": {
            family_id: _source_units_for_family_r5(rows, source_order)
            for family_id, rows in families.items()
        },
        "objects_by_family": r4._ordered_object_units(  # noqa: SLF001
            object_rows=object_rows,
            families=families,
        ),
        "source_record_count": len(source_rows),
        "compiled_object_count": len(object_rows),
        "source_position_mode": "raw_occurrence_before_deduplication",
    }


def _package_windows_r5(
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
        if r4._target_hint(target_id, str(unit.get("text") or ""))  # noqa: SLF001
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
        assessment = classify_dell_report_internal_chain_r5_package(
            target_id=target_id,
            text="\n".join(str(unit.get("text") or "") for unit in visible),
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
                rank = rank_by_object_id.get(str(unit["unit_id"]))
                if rank is None:
                    continue
                unit_assessment = classify_dell_report_internal_chain_r5_package(
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


def _best_package_r5(
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
        value = classify_dell_report_internal_chain_r5_package(
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


def _normalized_number(value: str) -> str:
    try:
        number = Decimal(value.replace(",", ""))
    except InvalidOperation:
        return value.replace(",", "").casefold()
    rendered = format(number.normalize(), "f")
    return "0" if rendered in {"-0", ""} else rendered


_CURRENCY_ANCHOR = re.compile(
    r"(?<![0-9a-z-])(?:usd|us\$|\$)\s*"
    r"([0-9][0-9,]*(?:\.[0-9]+)?)(?![0-9a-z-])"
)
_PERCENT_ANCHOR = re.compile(
    r"(?<![0-9a-z-])([0-9][0-9,]*(?:\.[0-9]+)?)\s*%"
    r"(?![0-9a-z-])"
)
_FY_ANCHOR = re.compile(r"(?<![0-9a-z-])fy\s*([0-9]{2,4})(?![0-9a-z-])")
_QUARTER_ANCHOR = re.compile(r"(?<![0-9a-z-])q([1-4])(?![0-9a-z-])")
_YEAR_ANCHOR = re.compile(r"(?<![0-9a-z-])(20[0-9]{2})(?![0-9a-z-])")
_NUMBER_ANCHOR = re.compile(
    r"(?<![0-9a-z-])([0-9][0-9,]*(?:\.[0-9]+)?)(?![0-9a-z-])"
)
_NUMBER_WORD_ANCHOR = re.compile(
    r"(?<![0-9a-z-])"
    r"(one|two|three|four|five|six|seven|eight|nine|ten)"
    r"(?![0-9a-z-])"
)
_TIME_OR_MAGNITUDE_ANCHOR = re.compile(
    r"(?<![0-9a-z-])"
    r"(thousand|thousands|million|millions|billion|billions|"
    r"week|weeks|quarter|quarters|half|halves)"
    r"(?![0-9a-z-])"
)


def _typed_material_anchors(text: str) -> list[str]:
    """Return token-exact typed anchors; product-code digits are excluded."""

    normalized = _normalize_text(text)
    anchors: set[str] = set()
    occupied: list[tuple[int, int]] = []

    def record(pattern: re.Pattern[str], prefix: str) -> None:
        for match in pattern.finditer(normalized):
            anchors.add(f"{prefix}:{_normalized_number(match.group(1))}")
            occupied.append(match.span())

    record(_CURRENCY_ANCHOR, "currency_usd")
    record(_PERCENT_ANCHOR, "percent")
    record(_FY_ANCHOR, "fiscal_year")
    record(_QUARTER_ANCHOR, "quarter")
    record(_YEAR_ANCHOR, "calendar_year")
    for match in _NUMBER_ANCHOR.finditer(normalized):
        if any(
            match.start() < end and match.end() > start
            for start, end in occupied
        ):
            continue
        anchors.add(f"number:{_normalized_number(match.group(1))}")
    for match in _NUMBER_WORD_ANCHOR.finditer(normalized):
        anchors.add(f"number_word:{match.group(1)}")
    for match in _TIME_OR_MAGNITUDE_ANCHOR.finditer(normalized):
        token = match.group(1)
        singular = {
            "thousands": "thousand",
            "millions": "million",
            "billions": "billion",
            "weeks": "week",
            "quarters": "quarter",
            "halves": "half",
        }.get(token, token)
        prefix = "magnitude" if singular in {
            "thousand",
            "million",
            "billion",
        } else "time_unit"
        anchors.add(f"{prefix}:{singular}")
    return sorted(anchors)


def _material_fingerprint_r5(
    target_id: str, sentence: str, metadata: Mapping[str, Any]
) -> dict[str, Any] | None:
    if not r4._target_hint(target_id, sentence):  # noqa: SLF001
        return None
    normalized = _normalize_text(sentence)
    assessment = classify_dell_report_internal_chain_r5_package(
        target_id=target_id,
        text=sentence,
        metadata=metadata,
    )
    groups = set(assessment["matched_group_ids"])
    required_groups: set[str] = set()
    if target_id == "DELL-RSQ-03A-TARGET-ASP":
        explicit_price_role = r4._has_any(  # noqa: SLF001
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
            and explicit_price_role
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
        if candidate.issubset(groups) and "upstream_Dell_allocation" in groups:
            required_groups = candidate | {"upstream_Dell_allocation"}
    elif target_id == "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD":
        candidate = {
            "relevant_supply",
            "observed_yield_or_utilization",
            "observed_measure",
        }
        if candidate.issubset(groups):
            required_groups = candidate
    elif target_id == "DELL-RSQ-03A-TARGET-HBM-SUPPLY":
        candidate = {
            "hbm_subject",
            "supply_state",
            "time_surface",
            "directional_Dell_bridge",
        }
        if candidate.issubset(groups):
            required_groups = candidate
    elif assessment["classification"] == "complete_bounded_target_package":
        required_groups = set(assessment["required_group_ids"])
    if not required_groups:
        return None
    return {
        "normalized_sentence": normalized,
        "sentence_digest": canonical_digest(normalized),
        "required_material_group_ids": sorted(required_groups),
        "material_anchors": _typed_material_anchors(normalized),
        "anchor_mode": "typed_token_exact_v1",
    }


def _coverage_gaps_r5(
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
            fingerprint = _material_fingerprint_r5(target_id, sentence, row)
            if fingerprint is None:
                continue
            digest = str(fingerprint["sentence_digest"])
            occurrence_counts[digest] += 1
            occurrence_source_ids[digest].add(r4._source_id(row))  # noqa: SLF001
            fingerprints.setdefault(digest, fingerprint)
    canonical_digests = {
        str(fingerprint["sentence_digest"])
        for unit in source_units
        if (
            fingerprint := _material_fingerprint_r5(
                target_id,
                str(unit.get("text") or ""),
                metadata,
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
            compiled_anchors = set(
                _typed_material_anchors(window.get("model_text") or "")
            )
            if anchors.issubset(compiled_anchors):
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
                    "anchor_mode": "typed_token_exact_v1",
                    "reason": (
                        "canonical_material_source_claim_missing_from_bounded_"
                        "compiled_object_windows"
                    ),
                }
            )
    return gaps


def assess_dell_report_internal_chain_r5_packages(
    *,
    target_id: str,
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
    selected_object_ids: Iterable[str] | None = None,
    rank_by_object_id: Mapping[str, int] | None = None,
    corpus_index: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess R5 raw-position families and typed material coverage."""

    index = (
        dict(corpus_index)
        if corpus_index is not None
        else build_dell_report_internal_chain_r5_corpus_index(
            source_rows=source_rows,
            object_rows=object_rows,
        )
    )
    _require(
        int(index.get("source_record_count") or 0) == len(source_rows)
        and int(index.get("compiled_object_count") or 0) == len(object_rows)
        and index.get("source_position_mode")
        == "raw_occurrence_before_deduplication",
        "dell_03B_R5_corpus_index_population_or_position_drift",
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
            source_windows = _package_windows_r5(
                target_id=target_id,
                units=source_units,
                metadata=metadata,
                selected_object_ids=None,
                rank_by_object_id=None,
            )
            source_packages.append(
                _best_package_r5(
                    source_windows,
                    family_id=family_id,
                    metadata=metadata,
                    object_package=False,
                )
            )
        object_units = objects_by_family.get(family_id, [])
        object_windows = _package_windows_r5(
            target_id=target_id,
            units=object_units,
            metadata=metadata,
            selected_object_ids=selected,
            rank_by_object_id=rank_by_object_id,
        )
        compiled_packages.append(
            _best_package_r5(
                object_windows,
                family_id=family_id,
                metadata=metadata,
                object_package=True,
            )
        )
        if selected is None:
            coverage.extend(
                _coverage_gaps_r5(
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


def compile_dell_report_internal_chain_ceiling_r5_result(
    *,
    legacy_policy: Mapping[str, Any],
    r5_policy: Mapping[str, Any],
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
    """Compile the single-pass R5 semantic and material-coverage result."""

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
        "dell_03B_R5_execution_sha_mismatch",
    )
    source_ids_list = [r4._source_id(row) for row in source_rows]  # noqa: SLF001
    objects_by_id, source_ids = (
        legacy.validate_dell_report_source_compiled_identity_population(
            object_rows=object_rows,
            source_record_ids=source_ids_list,
            runtime_binding_receipt=runtime_binding_receipt,
        )
    )
    request_by_id = validated["request_results_by_id"]
    object_ids = set(objects_by_id)
    corpus_index = build_dell_report_internal_chain_r5_corpus_index(
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
        target_contracts, key=lambda row: str(row.get("target_id") or "")
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
            union_ids.issubset(object_ids) and final_ids.issubset(union_ids),
            f"dell_03B_R5_candidate_object_binding_invalid:{target_id}",
        )
        total_union_occurrences += len(union_ids)
        corpus = assess_dell_report_internal_chain_r5_packages(
            target_id=target_id,
            source_rows=source_rows,
            object_rows=object_rows,
            corpus_index=corpus_index,
        )
        union_rank = r4._rank_map(  # noqa: SLF001
            union_ids, scoped_results, "minimum_raw_union_rank"
        )
        union = assess_dell_report_internal_chain_r5_packages(
            target_id=target_id,
            source_rows=source_rows,
            object_rows=object_rows,
            selected_object_ids=union_ids,
            rank_by_object_id=union_rank,
            corpus_index=corpus_index,
        )
        final_rank = r4._rank_map(  # noqa: SLF001
            final_ids, scoped_results, "minimum_final_output_rank"
        )
        final = assess_dell_report_internal_chain_r5_packages(
            target_id=target_id,
            source_rows=source_rows,
            object_rows=object_rows,
            selected_object_ids=final_ids,
            rank_by_object_id=final_rank,
            corpus_index=corpus_index,
        )
        source_complete = r4._complete_ids(corpus["source_packages"])  # noqa: SLF001
        compiled_complete = r4._complete_ids(corpus["compiled_packages"])  # noqa: SLF001
        union_complete = r4._complete_ids(union["compiled_packages"])  # noqa: SLF001
        final_complete = r4._complete_ids(final["compiled_packages"])  # noqa: SLF001
        source_partial = r4._partial_ids(corpus["source_packages"])  # noqa: SLF001
        compiled_partial = r4._partial_ids(corpus["compiled_packages"])  # noqa: SLF001
        materialization_gaps = source_complete - compiled_complete
        coverage_gaps = corpus["coverage_gaps"]
        coverage_pass = not materialization_gaps and not coverage_gaps

        if materialization_gaps or coverage_gaps:
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
        residual = r4._residual_scope(target_id, source_complete)  # noqa: SLF001
        residual_target = residual_by_id[target_id]
        mandatory_external_routes = sorted(
            str(route.get("route_contract_id") or "")
            for route in residual_target.get("route_contracts") or ()
            if route.get("mandatory_for_target") is True
            and route.get("route_family_id") != "local_data_object_index_sql"
        )
        public_packages = sorted(
            (
                r4._public_package(row)  # noqa: SLF001
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
                    "bounded_eight_raw_occurrence_position_"
                    "canonical_source_family_window"
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
                        materialization_gaps
                    ),
                    "material_source_claim_coverage_gap_canonical_count": len(
                        coverage_gaps
                    ),
                    "material_source_claim_coverage_gap_occurrence_count": corpus[
                        "coverage_gap_source_occurrence_count"
                    ],
                    "source_to_object_semantic_coverage_pass": coverage_pass,
                    "source_position_mode": (
                        "raw_occurrence_before_deduplication"
                    ),
                    "material_anchor_mode": "typed_token_exact_v1",
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
                        materialization_gaps or coverage_gaps
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
            "status": (
                "dell_03B_R5_raw_position_typed_anchor_semantic_ceiling_executed"
            ),
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
            "raw_execution_projection_digest": execution.get(
                "projection_digest"
            ),
            "validated_execution_digest": validated[
                "validated_execution_digest"
            ],
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
                "03B_R5_execution_consumed": True,
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
                "R5 assigns immutable raw source-sentence occurrence positions "
                "before display deduplication, uses typed token-exact numeric "
                "and time anchors, and fails closed on negative supplier, "
                "capacity and HBM direction; prospective, pilot or wrong-process "
                "yield; and negative or counterparty Dell shipment language. "
                "Configuration prices remain non-company ASP and candidates "
                "remain non-Evidence. No 03C, 4B, reranker, promotion, gap "
                "closure, human, report, product, publication or release "
                "authority is granted."
            ),
            "policy_digest": r5_policy.get("result_digest"),
    }
    return {**body, "result_digest": canonical_digest(body)}


def build_dell_report_internal_chain_ceiling_r5_public_projection(
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
    _require("model_text" not in serialized, "dell_03B_R5_public_model_text_leak")
    _require(
        "material_sentence" not in serialized,
        "dell_03B_R5_public_sentence_leak",
    )
    _require(
        "http://" not in serialized and "https://" not in serialized,
        "dell_03B_R5_public_url_leak",
    )
    return {**body, "result_digest": canonical_digest(body)}


__all__ = [
    "ATTEMPT_ID",
    "ATTEMPT_RECEIPT_REF",
    "BRANCH",
    "DellReportInternalChainCeilingR5Error",
    "EXECUTION_CONTRACT",
    "MIN_FREE_BYTES_BEFORE_ATTEMPT",
    "POLICY_REF",
    "POLICY_SCHEMA_VERSION",
    "PRIVATE_REF",
    "PRIVATE_RESULT_SCHEMA_VERSION",
    "PUBLIC_REF",
    "PUBLIC_RESULT_SCHEMA_VERSION",
    "assess_dell_report_internal_chain_r5_packages",
    "build_dell_report_internal_chain_r5_corpus_index",
    "build_dell_report_internal_chain_ceiling_r5_public_projection",
    "classify_dell_report_internal_chain_r5_package",
    "compile_dell_report_internal_chain_ceiling_r5_result",
    "validate_dell_report_internal_chain_ceiling_r5_policy",
]
