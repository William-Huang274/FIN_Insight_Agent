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
from . import dell_report_internal_chain_ceiling_r5 as r5
from .query_plan import canonical_digest


POLICY_SCHEMA_VERSION = "fin_ia_dell_report_internal_chain_ceiling_policy_v1_5"
PRIVATE_RESULT_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_candidate_ceiling_private_result_v1_5"
)
PUBLIC_RESULT_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_candidate_ceiling_result_v1_5"
)
ATTEMPT_ID = "dell-rsq-03b-internal-chain-r6"
PROGRAM_ID = "FIN-0.1.3-S1-DELL-RSQ-03B-R6"
BRANCH = r5.BRANCH
POLICY_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_5.json"
)
PUBLIC_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_5.json"
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
MAX_ADJACENT_UNITS = r5.MAX_ADJACENT_UNITS
MIN_FREE_BYTES_BEFORE_ATTEMPT = 512 * 1024 * 1024
TARGET_IDS = r5.TARGET_IDS
ZERO_EXECUTION_FIELDS = r5.ZERO_EXECUTION_FIELDS
EXECUTION_CONTRACT = dict(r5.EXECUTION_CONTRACT)
AUTHORITY = dict(r5.AUTHORITY)
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
        "typed_clause_subject_predicate_object_direction_and_polarity"
    ),
    "yield_role": (
        "typed_clause_observed_measure_with_modality_and_process_guard"
    ),
    "units_role": (
        "typed_clause_Dell_actor_shipper_company_period_physical_server_count"
    ),
    "ASP_role": (
        "affirmative_bounded_configuration_or_bundle_price_not_company_realized_ASP"
    ),
    "material_coverage_mode": (
        "target_role_and_entity_period_canonical_typed_anchor_v2_coverage"
    ),
    "coverage_count_mode": (
        "canonical_claim_and_raw_source_occurrence_both_reported"
    ),
    "reranker_useful_at_k": 10,
    "candidate_not_evidence": True,
    "public_projection_mode": "recursive_explicit_allowlist_fail_closed",
}
EXPECTED_IMPLEMENTATION_PATHS = frozenset(
    set(r5.EXPECTED_IMPLEMENTATION_PATHS)
    | {
        "src/retrieval/dell_report_internal_chain_ceiling_r6.py",
        "scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r6.py",
    }
)
EXPECTED_BOUND_INPUT_IDS = frozenset(
    set(r5.EXPECTED_BOUND_INPUT_IDS)
    | {
        "R5_policy",
        "R5_public",
        "R5_private",
        "R5_attempt_receipt",
        "R5_fresh_audit",
    }
)
R5_AUDIT_STATUS = (
    "fail_material_semantic_anchor_privacy_and_report_findings_"
    "same_stage_R6_required"
)
R5_REQUIRED_ROOT_CAUSES = {
    "RC-S1-079-DELL-03B-clause-scope-polarity-modality-direction-and-ASP-affirmation",
    "RC-S1-080-DELL-03B-typed-anchor-product-code-and-fiscal-year-normalization",
    "RC-S0-105-R5-public-projector-denylist-not-fail-closed",
}


class DellReportInternalChainCeilingR6Error(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellReportInternalChainCeilingR6Error(code)


def _self_digest(value: Mapping[str, Any]) -> bool:
    body = dict(value)
    observed = str(body.pop("result_digest", ""))
    return bool(observed) and observed == canonical_digest(body)


def validate_dell_report_internal_chain_ceiling_r6_policy(
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
    r5_policy: Mapping[str, Any],
    r5_public: Mapping[str, Any],
    r5_private: Mapping[str, Any],
    r5_attempt_receipt: Mapping[str, Any],
    r5_fresh_audit: Mapping[str, Any],
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
    """Fail closed on R6 scope, immutable R5 failure and authority drift."""

    validated_r1 = r5.validate_dell_report_internal_chain_ceiling_r5_policy(
        r5_policy,
        r1_policy=r1_policy,
        r3_policy=r3_policy,
        r3_public=r3_public,
        r3_private=r3_private,
        r3_fresh_audit=r3_fresh_audit,
        r4_policy=r4_policy,
        r4_public=r4_public,
        r4_private=r4_private,
        r4_fresh_audit=r4_fresh_audit,
        r4_audit_correction=r4_audit_correction,
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
    _require(_self_digest(policy), "dell_03B_R6_policy_digest_invalid")
    _require(
        policy.get("schema_version") == POLICY_SCHEMA_VERSION
        and policy.get("status")
        == "same_stage_R6_execution_authorized_after_fresh_R5_audit_failure"
        and policy.get("program_id") == PROGRAM_ID
        and policy.get("attempt_id") == ATTEMPT_ID,
        "dell_03B_R6_policy_identity_invalid",
    )
    _require(
        dict(policy.get("execution_contract") or {}) == EXECUTION_CONTRACT
        and dict(policy.get("semantic_contract") or {}) == SEMANTIC_CONTRACT
        and dict(policy.get("authority") or {}) == AUTHORITY,
        "dell_03B_R6_policy_contract_invalid",
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
        and output.get("same_attempt_retry_authorized") is False
        and output.get("minimum_free_bytes_before_attempt")
        == MIN_FREE_BYTES_BEFORE_ATTEMPT,
        "dell_03B_R6_output_contract_invalid",
    )
    bound_inputs = dict(policy.get("bound_inputs") or {})
    _require(
        set(bound_inputs) == EXPECTED_BOUND_INPUT_IDS
        and all(
            isinstance(row, Mapping)
            and str(row.get("ref") or "").strip()
            and bool(
                re.fullmatch(
                    r"[0-9a-f]{64}", str(row.get("sha256") or "")
                )
            )
            for row in bound_inputs.values()
        ),
        "dell_03B_R6_bound_inputs_invalid",
    )
    bindings = list(policy.get("implementation_bindings") or ())
    _require(
        {str(row.get("path") or "") for row in bindings}
        == EXPECTED_IMPLEMENTATION_PATHS
        and all(
            isinstance(row, Mapping)
            and bool(
                re.fullmatch(
                    r"[0-9a-f]{64}", str(row.get("sha256") or "")
                )
            )
            for row in bindings
        ),
        "dell_03B_R6_implementation_bindings_invalid",
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
        "dell_03B_R6_execution_identity_invalid",
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
        "dell_03B_R6_token_budget_basis_invalid",
    )

    verdicts = dict(r5_fresh_audit.get("verdicts") or {})
    audit_authority = dict(r5_fresh_audit.get("authority") or {})
    _require(
        r5_fresh_audit.get("schema_version")
        == "fin_ia_independent_readonly_audit_result_v1_0"
        and r5_fresh_audit.get("status") == R5_AUDIT_STATUS
        and verdicts.get("overall") == "FAIL"
        and verdicts.get("new_R5_P0_P1_P2_P3") == [0, 0, 3, 0]
        and verdicts.get("R17_open_P0_P1_P2_P3") == [0, 1, 2, 1]
        and verdicts.get("R5_integrity") == "PASS"
        and verdicts.get("R5_route")
        == "PASS_BOUNDED_FOR_ACTUAL_IMMUTABLE_EXECUTION"
        and verdicts.get("03B_independent_pass") is False
        and audit_authority.get("R6_same_stage_successor_authorized")
        is True
        and audit_authority.get("R5_retry_or_overwrite_authorized")
        is False
        and _self_digest(r5_fresh_audit),
        "dell_03B_R6_predecessor_audit_invalid",
    )
    observed_root_causes = {
        str(row.get("root_cause_id") or "")
        for row in r5_fresh_audit.get("material_findings") or ()
        if isinstance(row, Mapping)
    }
    _require(
        R5_REQUIRED_ROOT_CAUSES.issubset(observed_root_causes),
        "dell_03B_R6_required_root_causes_missing",
    )
    reviewed = dict(r5_fresh_audit.get("reviewed_artifacts") or {})
    for binding_id, reviewed_id in (
        ("R5_policy", "R5_policy"),
        ("R5_public", "R5_public"),
        ("R5_private", "R5_private"),
        ("R5_attempt_receipt", "R5_attempt_receipt"),
    ):
        expected = dict(bound_inputs.get(binding_id) or {})
        observed = dict(reviewed.get(reviewed_id) or {})
        _require(
            observed.get("ref") == expected.get("ref")
            and observed.get("sha256") == expected.get("sha256"),
            f"dell_03B_R6_{binding_id}_audit_binding_invalid",
        )
    _require(
        dict(reviewed.get("R5_policy") or {}).get("result_digest")
        == r5_policy.get("result_digest")
        and dict(reviewed.get("R5_public") or {}).get("result_digest")
        == r5_public.get("result_digest")
        and dict(reviewed.get("R5_private") or {}).get("result_digest")
        == r5_private.get("result_digest")
        and dict(reviewed.get("R5_attempt_receipt") or {}).get(
            "result_digest"
        )
        == r5_attempt_receipt.get("result_digest"),
        "dell_03B_R6_R5_reviewed_digest_binding_invalid",
    )
    _require(
        r5_policy.get("attempt_id") == r5.ATTEMPT_ID
        and r5_public.get("attempt_id") == r5.ATTEMPT_ID
        and r5_private.get("attempt_id") == r5.ATTEMPT_ID
        and r5_attempt_receipt.get("attempt_id") == r5.ATTEMPT_ID
        and _self_digest(r5_policy)
        and _self_digest(r5_public)
        and _self_digest(r5_private)
        and _self_digest(r5_attempt_receipt)
        and r5_public.get("private_result_digest")
        == r5_private.get("result_digest")
        and r5_attempt_receipt.get("policy_digest")
        == r5_policy.get("result_digest")
        and r5_private.get("raw_execution_sha256")
        == dict(reviewed.get("raw_execution") or {}).get("sha256"),
        "dell_03B_R6_R5_result_binding_invalid",
    )
    verified = dict(
        r5_fresh_audit.get("verified_execution_and_integrity") or {}
    )
    _require(
        verified.get("bound_input_count") == 19
        and verified.get("implementation_binding_count") == 12
        and verified.get("exact_private_recompile_equal") is True
        and verified.get("exact_public_reprojection_equal") is True
        and verified.get("current_public_actual_sensitive_or_private_field_leak")
        is False
        and verified.get("request_count") == 5
        and verified.get("local_embedding_inference_batches") == 1
        and verified.get(
            "network_provider_generation_external_4B_reranker_retry_mutation_promotion_closure_all_zero"
        )
        is True,
        "dell_03B_R6_R5_execution_integrity_invalid",
    )
    private_authority = dict(r5_private.get("authority") or {})
    _require(
        private_authority.get("03B_R5_execution_consumed") is True
        and private_authority.get("03C_external_capture_authorized")
        is False
        and private_authority.get("03D_4B_embedding_authorized") is False
        and private_authority.get("03D_reranker_authorized") is False
        and private_authority.get("evidence_promotion_authorized") is False
        and private_authority.get("report_quality_pass") is False
        and private_authority.get("product_acceptance") is False,
        "dell_03B_R6_R5_authority_boundary_invalid",
    )
    return validated_r1

def _normalize_text(value: Any) -> str:
    return r4._normalize_text(value)  # noqa: SLF001


def _sentence_units(text: str) -> list[str]:
    return r4._sentence_units(text)  # noqa: SLF001


_CLAUSE_BOUNDARY = re.compile(
    r"\s*;\s*|\s+[—–]\s+|"
    r",\s*(?=(?:but|while|whereas|although|though|however|and)\b)|"
    r",\s*(?=(?:target|next\s+process|prototype|pilot)\b)|"
    r",\s*(?=(?:dell|nvidia|amd|gpu|hbm|poweredge|production|"
    r"manufacturing|yield|utilization|capacity|component|the\s+"
    r"(?:component|capacity|supplier|customer))\b[^,;]{0,40}\b"
    r"(?:did|does|do|was|were|is|are|has|have|had|will|would|"
    r"may|might|should|could|failed|rejected|refused|denied)\b)|"
    r"\s+(?=(?:but|while|whereas|although|though|however)\b)|"
    r"\s+and\s+(?="
    r"(?:amd|intel|micron|tsmc|wistron|foxconn|supermicro|"
    r"gpu|hbm|poweredge|production|manufacturing|"
    r"yield|utilization|capacity|component|another|a\s+separate|"
    r"the\s+(?:separate|component|capacity|supplier|customer))\b"
    r"[^,;]{0,40}\b"
    r"(?:did|does|do|was|were|is|are|has|have|had|failed|"
    r"will|would|may|might|should|could|rejected|refused|denied)\b)",
    re.IGNORECASE,
)
_NON_AFFIRMATIVE_PREDICATE = re.compile(
    r"\b(?:not|never|no|no\s+longer|did\s+not|does\s+not|do\s+not|"
    r"has\s+not|have\s+not|had\s+not|was\s+not|were\s+not|"
    r"is\s+not|are\s+not|cannot|can't|didn't|doesn't|isn't|aren't|"
    r"wasn't|weren't|hasn't|haven't|hadn't|"
    r"fail(?:s|ed|ing)?\s+to|unable\s+to|"
    r"declin(?:e|es|ed|ing)\s+to|"
    r"refus(?:e|es|ed|ing)\s+to|den(?:y|ies|ied|ying)|"
    r"reject(?:s|ed|ing)?|refut(?:e|es|ed|ing)|"
    r"cancel(?:s|l?ed|ling|ing)?|terminat(?:e|es|ed|ing)|"
    r"revok(?:e|es|ed|ing)|withdraw(?:s|n|ing)?|withdrew|"
    r"dissolv(?:e|es|ed|ing)|expir(?:e|es|ed|ing)|end(?:s|ed|ing)|"
    r"unavailable)\b|"
    r"\bwithout\b[^,;]{0,24}\b"
    r"(?:supply|delivery|partnership|collaboration|allocation|"
    r"capacity|shipment|shipping|quote|price)\b|"
    r"\black(?:s|ed|ing)?\b[^,;]{0,24}\b"
    r"(?:supply|delivery|partnership|collaboration|allocation|"
    r"capacity|shipment|quote|price)\b"
)
_SPECULATIVE_PREDICATE = re.compile(
    r"\b(?:may|might|could|would|should|will|"
    r"expect(?:s|ed|ing)?|forecast(?:s|ed|ing)?|"
    r"anticipat(?:e|es|ed|ing)|estimat(?:e|es|ed|ing)|"
    r"plan(?:s|ned|ning)?|propos(?:e|es|ed|ing)|"
    r"intend(?:s|ed|ing)?|aim(?:s|ed|ing)?|"
    r"indicative|preliminary|hypothetical|likely|unlikely|"
    r"possibly|potential(?:ly)?)\b"
)
_NON_AFFIRMATIVE_SUFFIX = re.compile(
    r"^\s*(?:(?:it|this|that)\s+)?"
    r"(?:(?:is|are|was|were|has\s+been|have\s+been|had\s+been)\s+)?"
    r"(?:not|never|no|denied|rejected|refuted|cancelled|canceled|"
    r"terminated|revoked|withdrawn|dissolved|expired|ended|"
    r"unavailable|without)\b"
)
_SPECULATIVE_SUFFIX = re.compile(
    r"^\s*(?:(?:it|this|that)\s+)?"
    r"(?:(?:is|are|was|were|has\s+been|have\s+been|had\s+been)\s+)?"
    r"(?:expected|forecast|anticipated|estimated|estimate|planned|"
    r"proposed|intended|targeted|indicative|preliminary|"
    r"hypothetical|possible)\b"
)
_NON_OBSERVED_MODALITY = re.compile(
    r"\b(?:future|target(?:s|ed|ing)?|expect(?:s|ed|ing)?|"
    r"forecast(?:s|ed|ing)?|anticipat(?:e|es|ed|ing)|"
    r"estimat(?:e|es|ed|ing)|plan(?:s|ned|ning)?|"
    r"project(?:s|ed|ing)?|should|will|would|could|may|might|"
    r"aim(?:s|ed|ing)?|guidance|prototype(?:-line)?|"
    r"pilot(?:\s+line)?|trial|test(?:ing)?|a14|sram|n2|"
    r"next\s+process)\b"
)
_NAMED_SUPPLIER = (
    r"(?:nvidia|micron|tsmc|taiwan\s+semiconductor|"
    r"sk\s+hynix|broadcom)"
)


def _clause_units(text: str) -> list[str]:
    clauses: list[str] = []
    for sentence in _sentence_units(text):
        clauses.extend(
            part.strip(" ,")
            for part in _CLAUSE_BOUNDARY.split(sentence)
            if part.strip(" ,")
        )
    return clauses


def _affirmative_predicate(
    clause: str,
    match: re.Match[str],
    *,
    before: int = 64,
    after: int = 32,
) -> bool:
    normalized = _normalize_text(clause)
    predicate_start = (
        match.start("predicate")
        if "predicate" in match.re.groupindex
        else match.start()
    )
    predicate_end = (
        match.end("predicate")
        if "predicate" in match.re.groupindex
        else match.end()
    )
    prefix_start = max(0, predicate_start - before)
    prefix = normalized[prefix_start:predicate_start]
    punctuation = max(
        prefix.rfind(","),
        prefix.rfind(";"),
        prefix.rfind("—"),
        prefix.rfind("–"),
    )
    if punctuation >= 0:
        prefix = prefix[punctuation + 1 :]
    subject_conjunctions = list(
        re.finditer(
            r"\b(?:and|but|while|whereas|although|though|however)\s+"
            r"(?=(?:dell|nvidia|amd|intel|micron|tsmc|gpu|hbm|"
            r"poweredge|production|manufacturing|yield|utilization|"
            r"capacity|component|another|the\s+(?:company|component|"
            r"capacity|supplier|customer))\b)",
            prefix,
        )
    )
    if subject_conjunctions:
        prefix = prefix[subject_conjunctions[-1].end() :]
    predicate_scope = prefix + normalized[predicate_start:predicate_end]
    predicate_scope = re.sub(
        r"\b(?:not\s+(?:only|alone)|not\s+previously\s+disclosed|"
        r"no\s+later\s+than)\b",
        "",
        predicate_scope,
    )
    suffix = normalized[predicate_end : min(len(normalized), predicate_end + after)]
    return (
        _NON_AFFIRMATIVE_PREDICATE.search(predicate_scope) is None
        and _NON_AFFIRMATIVE_SUFFIX.search(suffix) is None
        and _SPECULATIVE_PREDICATE.search(predicate_scope) is None
        and _SPECULATIVE_SUFFIX.search(suffix) is None
    )


_SUPPLIER_PROPOSITIONS = tuple(
    re.compile(pattern)
    for pattern in (
        rf"(?:dell\s+and\s+{_NAMED_SUPPLIER}|"
        rf"{_NAMED_SUPPLIER}\s+and\s+dell)"
        r"[^,;]{0,100}(?P<predicate>"
        r"partner(?:s|ed|ing|ship)?|collaborat(?:e|es|ed|ing|ion)|"
        r"team(?:s|ed|ing)?\s+up|all(?:y|ies|ied|iance))\b",
        rf"{_NAMED_SUPPLIER}[^,;]{{0,100}}"
        r"(?P<predicate>suppl(?:ies|ied|ying)|"
        r"supply(?=\s+(?:to\s+)?dell\b)|"
        r"deliver(?:s|ed|ing|y)?|allocat(?:e|es|ed|ing)|"
        r"ship(?:s|ped|ping)?)\b[^,;]{0,80}(?:to\s+)?dell\b",
        rf"\bdell\b[^,;]{{0,90}}servers?[^,;]{{0,70}}"
        rf"(?:with|powered\s+by)[^,;]{{0,50}}{_NAMED_SUPPLIER}"
        r"[^,;]{0,100}(?P<predicate>"
        r"ship(?:s|ped|ping)?|available|deliver(?:s|ed|ing)?)\b",
        rf"{_NAMED_SUPPLIER}[^,;]{{0,100}}"
        r"(?P<predicate>available)\s+(?:from|through)\s+dell\b",
    )
)


def _positive_supplier_direction_r6(text: str) -> bool:
    for clause in _clause_units(text):
        normalized = _normalize_text(clause)
        for pattern in _SUPPLIER_PROPOSITIONS:
            match = pattern.search(normalized)
            if match and _affirmative_predicate(normalized, match):
                return True
    return False


_ALLOCATION_PROPOSITIONS = tuple(
    re.compile(pattern)
    for pattern in (
        r"(?:capacity|allocation|supply)[^,;]{0,100}"
        r"(?P<predicate>allocat(?:e|es|ed|ing)|"
        r"secur(?:e|es|ed|ing)|reserv(?:e|es|ed|ing)|"
        r"commit(?:s|ted|ting)?|dedicat(?:e|es|ed|ing)|"
        r"assign(?:s|ed|ing)?|grant(?:s|ed|ing)?|"
        r"suppl(?:y|ies|ied|ying)|available|"
        r"configur(?:e|es|ed|ing))\b"
        r"[^,;]{0,60}(?:to|for)\s+dell\b",
        r"(?P<predicate>allocat(?:e|es|ed|ing)|"
        r"reserv(?:e|es|ed|ing)|"
        r"assign(?:s|ed|ing)?|grant(?:s|ed|ing)?)\b"
        r"[^,;]{0,60}(?:to|for)\s+dell\b",
        r"(?P<predicate>suppl(?:ies|ied|ying)|"
        r"deliver(?:s|ed|ing))\b[^,;]{0,60}(?:to\s+)?dell\b",
        r"\bdell\b[^,;]{0,80}"
        r"(?P<predicate>secur(?:e|es|ed|ing)|"
        r"reserv(?:e|es|ed|ing)|receiv(?:e|es|ed|ing)|"
        r"was\s+allocated|has\s+been\s+allocated)\b"
        r"[^,;]{0,60}(?:capacity|allocation|supply)\b",
        r"(?:capacity|allocation|supply)[^,;]{0,80}"
        r"(?P<predicate>available)\s+(?:to|for)\s+dell\b",
    )
)


def _positive_dell_allocation_clause(clause: str) -> bool:
    normalized = _normalize_text(clause)
    for pattern in _ALLOCATION_PROPOSITIONS:
        match = pattern.search(normalized)
        if match and _affirmative_predicate(normalized, match):
            return True
    return False


def _positive_dell_allocation_r6(text: str) -> bool:
    return any(
        _positive_dell_allocation_clause(clause)
        for clause in _clause_units(text)
    )


_HBM_BRIDGE = re.compile(
    r"\b(?:dell|poweredge)\b[^,;]{0,120}"
    r"(?P<predicate>configur(?:e|es|ed|ing)|"
    r"power(?:s|ed|ing)?|equip(?:s|ped|ping)?)\b"
    r"[^,;]{0,80}\bhbm\b"
)


def _positive_hbm_dell_bridge_r6(text: str) -> bool:
    for clause in _clause_units(text):
        normalized = _normalize_text(clause)
        if not r4._has_any(  # noqa: SLF001
            normalized,
            ("hbm", "high bandwidth memory", "high-bandwidth memory"),
        ):
            continue
        if _positive_dell_allocation_clause(normalized):
            return True
        match = _HBM_BRIDGE.search(normalized)
        if (
            match
            and re.search(
                r"\bwithout\s+(?:hbm|high[- ]bandwidth\s+memory)\b",
                normalized,
            )
            is None
            and _affirmative_predicate(normalized, match)
        ):
            return True
    return False


_YIELD_MEASURE = re.compile(
    r"(?:yield|utilization)(?:\s+rate|\s+level)?[^.%]{0,48}"
    r"[0-9]{1,3}(?:\.[0-9]+)?%"
)
_YIELD_SUFFIX_NON_OBSERVED = re.compile(
    r"^\s*(?:is|was|as)?\s*(?:a\s+)?"
    r"(?:target|forecast|estimate|projection)\b|"
    r"\b(?:expected|anticipated|estimated)\s+(?:level|rate)\b|"
    r"\bby\s+20[0-9]{2}\b|"
    r"\b(?:prototype(?:-line)?|pilot(?:\s+line)?|trial|"
    r"test(?:ing)?|a14|sram|n2|next\s+process)\b"
)


def _valid_observed_yield_measure_r6(text: str) -> bool:
    for clause in _clause_units(text):
        normalized = _normalize_text(clause)
        measures = list(_YIELD_MEASURE.finditer(normalized))
        for phrase in (
            "at full utilization",
            "near full utilization",
            "below full utilization",
        ):
            measures.extend(re.finditer(re.escape(phrase), normalized))
        for measure in measures:
            prefix = normalized[: measure.end()]
            suffix = normalized[measure.end() : measure.end() + 64]
            if _NON_AFFIRMATIVE_PREDICATE.search(prefix):
                continue
            if _NON_OBSERVED_MODALITY.search(prefix):
                continue
            if _YIELD_SUFFIX_NON_OBSERVED.search(suffix):
                continue
            return True
    return False


_PHYSICAL_SERVER_QUANTITY = (
    r"(?<![$0-9a-z])(?:[0-9][0-9,]*|one|two|three|four|five|six|"
    r"seven|eight|nine|ten)(?:\s*\([0-9]+\))?"
    r"(?:\s+[a-z0-9-]+){0,4}\s+(?:server units|servers|systems)"
    r"(?![0-9a-z])"
)
_DELL_DIRECT_SHIPMENT = tuple(
    re.compile(pattern)
    for pattern in (
        rf"\bdell\b\s+(?:said|reported|disclosed|announced|confirmed)\s+"
        rf"(?:that\s+)?(?:it\s+)?(?P<predicate>shipped|delivered)\b"
        rf"[^,;]{{0,80}}{_PHYSICAL_SERVER_QUANTITY}",
        rf"\bdell\b[^,;]{{0,48}}\b(?:when|as)\s+it\s+"
        rf"(?P<predicate>shipped|delivered)\b"
        rf"[^,;]{{0,80}}{_PHYSICAL_SERVER_QUANTITY}",
        rf"\bdell\b\s+(?:(?:has|had|already|recently|currently)\s+)"
        rf"{{0,3}}(?P<predicate>shipped|delivered)\b"
        rf"[^,;]{{0,80}}{_PHYSICAL_SERVER_QUANTITY}",
        rf"\bdell\b\s+(?P<predicate>shipped|delivered)\b"
        rf"[^,;]{{0,80}}{_PHYSICAL_SERVER_QUANTITY}",
        rf"{_PHYSICAL_SERVER_QUANTITY}[^,;]{{0,80}}"
        rf"(?P<predicate>shipped|delivered)\s+by\s+dell\b",
        rf"\bdell(?:'s)?\b[^,;]{{0,40}}"
        rf"(?P<predicate>shipments?|deliveries)\s+of"
        rf"[^,;]{{0,60}}{_PHYSICAL_SERVER_QUANTITY}",
    )
)
_THIRD_PARTY_REPORT_PREFIX = re.compile(
    r"\b(?:said|reported|claimed|disclosed|announced|stated|"
    r"according\s+to)\b"
)


def _third_party_report_precedes_dell_match(
    normalized: str, match: re.Match[str]
) -> bool:
    prefix = normalized[max(0, match.start() - 96) : match.start()]
    reports = list(_THIRD_PARTY_REPORT_PREFIX.finditer(prefix))
    if not reports:
        return False
    reporter_scope = prefix[max(0, reports[-1].start() - 48) :]
    return "dell" not in reporter_scope


def _valid_dell_seller_r6(text: str) -> bool:
    for clause in _clause_units(text):
        normalized = _normalize_text(clause)
        for pattern in _DELL_DIRECT_SHIPMENT:
            match = pattern.search(normalized)
            if (
                match
                and not _third_party_report_precedes_dell_match(
                    normalized, match
                )
                and _affirmative_predicate(normalized, match)
            ):
                return True
    return False


_PRICE_SURFACE = re.compile(
    r"(?:usd|us\$|\$)\s*[0-9][0-9,]*(?:\.[0-9]+)?"
)
_PRICE_PROPOSITIONS = tuple(
    re.compile(pattern)
    for pattern in (
        r"(?P<predicate>quot(?:e|es|ed|ing)|"
        r"pric(?:e|es|ed|ing)|cost(?:s|ed|ing)?)\b",
        r"(?P<predicate>contract\s+amount|total\s+contract\s+cost|"
        r"purchase\s+price|configuration\s+price|recommended\s+price|"
        r"quoted\s+price)\b",
    )
)
def _positive_asp_price_r6(text: str) -> bool:
    for clause in _clause_units(text):
        normalized = _normalize_text(clause)
        if not _PRICE_SURFACE.search(normalized) and not r4._has_any(  # noqa: SLF001
            normalized,
            (
                "quoted price",
                "purchase price",
                "configuration price",
                "contract amount",
                "total contract cost",
                "recommended price",
            ),
        ):
            continue
        for pattern in _PRICE_PROPOSITIONS:
            match = pattern.search(normalized)
            if not match:
                continue
            if _affirmative_predicate(normalized, match):
                return True
    return False


def _set_group(assessment: dict[str, Any], group: str, hit: bool) -> None:
    groups = set(assessment.get("matched_group_ids") or ())
    if hit:
        groups.add(group)
    else:
        groups.discard(group)
    assessment["matched_group_ids"] = sorted(groups)


def _guarded_completion(
    assessment: dict[str, Any],
    *,
    guard_group: str,
    hit: bool,
    complete_role: str,
    partial_role: str,
    limitation: str,
    add_required_group: bool = False,
) -> None:
    _set_group(assessment, guard_group, hit)
    required = list(assessment.get("required_group_ids") or ())
    if add_required_group and guard_group not in required:
        required.append(guard_group)
        assessment["required_group_ids"] = required
    groups = set(assessment.get("matched_group_ids") or ())
    limitations = set(assessment.get("limitations") or ())
    if (
        assessment.get("in_period") is True
        and all(group in groups for group in required)
        and not (
            assessment.get("target_id") == "DELL-RSQ-03A-TARGET-UNITS"
            and {
                "buyer_procurement_or_GPU_count_is_not_Dell_company_server_shipments",
                "shipment_value_is_not_physical_units",
            }
            & limitations
        )
    ):
        limitations.discard(limitation)
        assessment["classification"] = "complete_bounded_target_package"
        assessment["package_role"] = complete_role
    else:
        if hit:
            limitations.discard(limitation)
        else:
            limitations.add(limitation)
        if assessment.get("classification") == "complete_bounded_target_package":
            assessment["classification"] = "partial_context_only"
        assessment["package_role"] = partial_role
    assessment["limitations"] = sorted(limitations)


def classify_dell_report_internal_chain_r6_package(
    *, target_id: str, text: str, metadata: Mapping[str, Any]
) -> dict[str, Any]:
    """Recompute R4 groups with R6 typed clause propositions."""

    assessment = r4.classify_dell_report_internal_chain_r4_package(
        target_id=target_id,
        text=text,
        metadata=metadata,
    )
    assessment["semantic_guard_revision"] = "R6"
    if target_id == "DELL-RSQ-03A-TARGET-ASP":
        _guarded_completion(
            assessment,
            guard_group="affirmative_price_quote",
            hit=_positive_asp_price_r6(text),
            complete_role="bounded_configuration_or_bundle_price_package",
            partial_role="price_or_configuration_context",
            limitation="negative_estimated_or_missing_affirmative_price_quote",
            add_required_group=True,
        )
    elif target_id == "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH":
        _guarded_completion(
            assessment,
            guard_group="directional_relationship_delivery",
            hit=_positive_supplier_direction_r6(text),
            complete_role="supplier_to_Dell_relationship_delivery",
            partial_role="supplier_or_relationship_context",
            limitation=(
                "negative_undirected_or_missing_typed_supplier_proposition"
            ),
        )
    elif target_id == "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE":
        _guarded_completion(
            assessment,
            guard_group="upstream_Dell_allocation",
            hit=_positive_dell_allocation_r6(text),
            complete_role="upstream_capacity_release_to_Dell",
            partial_role="product_availability_or_delivery_context",
            limitation=(
                "negative_rejected_or_missing_typed_Dell_allocation"
            ),
        )
    elif target_id == "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD":
        _guarded_completion(
            assessment,
            guard_group="observed_measure",
            hit=_valid_observed_yield_measure_r6(text),
            complete_role="observed_relevant_supply_yield_or_utilization",
            partial_role="yield_or_utilization_context",
            limitation=(
                "non_observed_modal_prototype_or_wrong_process_measure"
            ),
        )
    elif target_id == "DELL-RSQ-03A-TARGET-HBM-SUPPLY":
        _guarded_completion(
            assessment,
            guard_group="directional_Dell_bridge",
            hit=_positive_hbm_dell_bridge_r6(text),
            complete_role=(
                "HBM_supply_with_Dell_configuration_or_allocation_bridge"
            ),
            partial_role="HBM_supply_context",
            limitation=(
                "negative_rejected_or_missing_typed_HBM_Dell_bridge"
            ),
        )
    elif target_id == "DELL-RSQ-03A-TARGET-UNITS":
        _guarded_completion(
            assessment,
            guard_group="Dell_seller_or_shipper_role",
            hit=_valid_dell_seller_r6(text),
            complete_role="Dell_company_period_physical_server_shipments",
            partial_role="qualitative_shipment_or_noncompany_count_context",
            limitation=(
                "negative_reported_or_non_Dell_typed_shipper_proposition"
            ),
        )
    return assessment


def _source_units_for_family_r6(
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


def build_dell_report_internal_chain_r6_corpus_index(
    *,
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    families, source_order = r4._source_families(source_rows)  # noqa: SLF001
    return {
        "families": families,
        "source_order": source_order,
        "source_units_by_family": {
            family_id: _source_units_for_family_r6(rows, source_order)
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


def _package_windows_r6(
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
        assessment = classify_dell_report_internal_chain_r6_package(
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
                unit_assessment = classify_dell_report_internal_chain_r6_package(
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


def _best_package_r6(
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
        value = classify_dell_report_internal_chain_r6_package(
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
_FISCAL_YEAR_WORD_ANCHOR = re.compile(
    r"(?<![0-9a-z-])fiscal[- ]year\s*([0-9]{2,4})(?![0-9a-z-])"
)
_QUARTER_ANCHOR = re.compile(r"(?<![0-9a-z-])q([1-4])(?![0-9a-z-])")
_YEAR_ANCHOR = re.compile(r"(?<![0-9a-z-])(20[0-9]{2})(?![0-9a-z-])")
_PRODUCT_CODE_ANCHOR = re.compile(
    r"(?<![0-9a-z])(?P<code>"
    r"xe(?:9680|9712)|gb(?:200|300)|mi(?:300x?|325x|355x)|"
    r"h(?:100|200)|b(?:100|200)|a(?:100|800)"
    r")(?![0-9a-z])"
)
_PRODUCT_CODE_FLEXIBLE_ANCHOR = re.compile(
    r"(?<![0-9a-z])(?P<prefix>xe|gb|mi|h|b)"
    r"(?:\s*[-/‐‑‒–—]\s*|\s+)"
    r"(?P<number>9680|9712|300x?|325x|355x|100|200|800)"
    r"(?![0-9a-z])"
)
_A_PRODUCT_CODE_SEPARATED_ANCHOR = re.compile(
    r"(?<![0-9a-z])(?P<prefix>a)\s*[-/‐‑‒–—]\s*"
    r"(?P<number>100|800)(?![0-9a-z])"
)
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


def _canonical_fiscal_year(value: str) -> str:
    year = int(value)
    if len(value) == 2:
        year += 2000
    return str(year)


def _canonical_product_code(match: re.Match[str]) -> str | None:
    if "code" in match.re.groupindex:
        code = str(match.group("code") or "").casefold()
        prefix = next(
            (
                value
                for value in ("xe", "gb", "mi", "h", "b", "a")
                if code.startswith(value)
            ),
            "",
        )
        number = code[len(prefix) :]
    else:
        prefix = str(match.group("prefix") or "").casefold()
        number = str(match.group("number") or "").casefold()
    allowed = {
        "xe": {"9680", "9712"},
        "gb": {"200", "300"},
        "mi": {"300", "300x", "325x", "355x"},
        "h": {"100", "200"},
        "b": {"100", "200"},
        "a": {"100", "800"},
    }
    if number not in allowed.get(prefix, set()):
        return None
    return f"{prefix}{number}"


def _typed_material_anchors(text: str) -> list[str]:
    """Return canonical typed anchors with product-code spans occupied."""

    normalized = _normalize_text(text)
    anchors: set[str] = set()
    occupied: list[tuple[int, int]] = []

    def record(
        pattern: re.Pattern[str],
        prefix: str,
        *,
        normalize: Any = _normalized_number,
        skip_occupied: bool = False,
    ) -> None:
        for match in pattern.finditer(normalized):
            if skip_occupied and any(
                match.start() < end and match.end() > start
                for start, end in occupied
            ):
                continue
            anchors.add(f"{prefix}:{normalize(match.group(1))}")
            occupied.append(match.span())

    for pattern in (
        _PRODUCT_CODE_ANCHOR,
        _PRODUCT_CODE_FLEXIBLE_ANCHOR,
        _A_PRODUCT_CODE_SEPARATED_ANCHOR,
    ):
        for match in pattern.finditer(normalized):
            if any(
                match.start() < end and match.end() > start
                for start, end in occupied
            ):
                continue
            product_code = _canonical_product_code(match)
            if product_code:
                anchors.add(f"product_code:{product_code}")
                occupied.append(match.span())
    record(_CURRENCY_ANCHOR, "currency_usd")
    record(_PERCENT_ANCHOR, "percent")
    record(_FY_ANCHOR, "fiscal_year", normalize=_canonical_fiscal_year)
    record(
        _FISCAL_YEAR_WORD_ANCHOR,
        "fiscal_year",
        normalize=_canonical_fiscal_year,
    )
    record(_QUARTER_ANCHOR, "quarter")
    record(_YEAR_ANCHOR, "calendar_year", skip_occupied=True)
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


def _material_anchor_text_r6(target_id: str, sentence: str) -> str:
    clauses = _clause_units(sentence)
    typed: list[str] = []
    for clause in clauses:
        hit = False
        if target_id == "DELL-RSQ-03A-TARGET-ASP":
            hit = _positive_asp_price_r6(clause)
        elif target_id == "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH":
            hit = _positive_supplier_direction_r6(clause)
        elif target_id == "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE":
            hit = _positive_dell_allocation_clause(clause)
        elif target_id == "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD":
            hit = _valid_observed_yield_measure_r6(clause)
        elif target_id == "DELL-RSQ-03A-TARGET-HBM-SUPPLY":
            hit = _positive_hbm_dell_bridge_r6(clause)
        elif target_id == "DELL-RSQ-03A-TARGET-UNITS":
            hit = _valid_dell_seller_r6(clause)
        if hit:
            typed.append(clause)
    return " ".join(typed) if typed else sentence


def _material_fingerprint_r6(
    target_id: str, sentence: str, metadata: Mapping[str, Any]
) -> dict[str, Any] | None:
    if not r4._target_hint(target_id, sentence):  # noqa: SLF001
        return None
    normalized = _normalize_text(sentence)
    assessment = classify_dell_report_internal_chain_r6_package(
        target_id=target_id,
        text=sentence,
        metadata=metadata,
    )
    groups = set(assessment["matched_group_ids"])
    required_groups: set[str] = set()
    if target_id == "DELL-RSQ-03A-TARGET-ASP":
        if "affirmative_price_quote" not in groups:
            return None
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
            required_groups = {
                "affirmative_price_quote",
                "price_surface",
            }
        elif {"dell_ai_server", "valid_denominator"}.issubset(groups):
            required_groups = {
                "affirmative_price_quote",
                "dell_ai_server",
                "valid_denominator",
            }
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
    anchor_text = _material_anchor_text_r6(target_id, sentence)
    return {
        "normalized_sentence": normalized,
        "sentence_digest": canonical_digest(normalized),
        "required_material_group_ids": sorted(required_groups),
        "material_anchors": _typed_material_anchors(anchor_text),
        "anchor_mode": "typed_entity_period_canonical_v2",
    }


def _coverage_gaps_r6(
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
            fingerprint = _material_fingerprint_r6(target_id, sentence, row)
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
            fingerprint := _material_fingerprint_r6(
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
                    "anchor_mode": "typed_entity_period_canonical_v2",
                    "reason": (
                        "canonical_material_source_claim_missing_from_bounded_"
                        "compiled_object_windows"
                    ),
                }
            )
    return gaps


def assess_dell_report_internal_chain_r6_packages(
    *,
    target_id: str,
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
    selected_object_ids: Iterable[str] | None = None,
    rank_by_object_id: Mapping[str, int] | None = None,
    corpus_index: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess R6 raw-position families and typed material coverage."""

    index = (
        dict(corpus_index)
        if corpus_index is not None
        else build_dell_report_internal_chain_r6_corpus_index(
            source_rows=source_rows,
            object_rows=object_rows,
        )
    )
    _require(
        int(index.get("source_record_count") or 0) == len(source_rows)
        and int(index.get("compiled_object_count") or 0) == len(object_rows)
        and index.get("source_position_mode")
        == "raw_occurrence_before_deduplication",
        "dell_03B_R6_corpus_index_population_or_position_drift",
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
            source_windows = _package_windows_r6(
                target_id=target_id,
                units=source_units,
                metadata=metadata,
                selected_object_ids=None,
                rank_by_object_id=None,
            )
            source_packages.append(
                _best_package_r6(
                    source_windows,
                    family_id=family_id,
                    metadata=metadata,
                    object_package=False,
                )
            )
        object_units = objects_by_family.get(family_id, [])
        object_windows = _package_windows_r6(
            target_id=target_id,
            units=object_units,
            metadata=metadata,
            selected_object_ids=selected,
            rank_by_object_id=rank_by_object_id,
        )
        compiled_packages.append(
            _best_package_r6(
                object_windows,
                family_id=family_id,
                metadata=metadata,
                object_package=True,
            )
        )
        if selected is None:
            coverage.extend(
                _coverage_gaps_r6(
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


def compile_dell_report_internal_chain_ceiling_r6_result(
    *,
    legacy_policy: Mapping[str, Any],
    r6_policy: Mapping[str, Any],
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
    """Compile the single-pass R6 semantic and material-coverage result."""

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
        "dell_03B_R6_execution_sha_mismatch",
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
    corpus_index = build_dell_report_internal_chain_r6_corpus_index(
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
            f"dell_03B_R6_candidate_object_binding_invalid:{target_id}",
        )
        total_union_occurrences += len(union_ids)
        corpus = assess_dell_report_internal_chain_r6_packages(
            target_id=target_id,
            source_rows=source_rows,
            object_rows=object_rows,
            corpus_index=corpus_index,
        )
        union_rank = r4._rank_map(  # noqa: SLF001
            union_ids, scoped_results, "minimum_raw_union_rank"
        )
        union = assess_dell_report_internal_chain_r6_packages(
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
        final = assess_dell_report_internal_chain_r6_packages(
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
                    "material_anchor_mode": (
                        "typed_entity_period_canonical_v2"
                    ),
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
                "dell_03B_R6_raw_position_typed_anchor_semantic_ceiling_executed"
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
                "03B_R6_execution_consumed": True,
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
                "R6 assigns immutable raw source-sentence occurrence positions "
                "before display deduplication, binds canonical product, fiscal-"
                "period and numeric anchors to affirmative typed proposition "
                "clauses, and fails closed on negative or speculative supplier, "
                "capacity and HBM direction; prospective, pilot or wrong-process "
                "yield; negative, third-party-reported or non-Dell shipment "
                "language; and negative or estimated price language. The public "
                "projection is a recursive explicit allowlist. Configuration "
                "prices remain non-company ASP and candidates remain non-"
                "Evidence. No 03C, 4B, reranker, promotion, gap closure, human, "
                "report, product, publication or release authority is granted."
            ),
            "policy_digest": r6_policy.get("result_digest"),
    }
    return {**body, "result_digest": canonical_digest(body)}


_PRIVATE_RESULT_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "attempt_id",
        "recorded_at",
        "prepared_from_commit",
        "case_key",
        "input_bindings",
        "runtime_registry",
        "raw_execution_receipt",
        "raw_execution_sha256",
        "raw_execution_projection_digest",
        "validated_execution_digest",
        "execution_summary",
        "target_results",
        "summary",
        "authority",
        "known_boundary",
        "policy_digest",
        "result_digest",
    }
)
_PUBLIC_TARGET_KEYS = frozenset(
    {
        "target_id",
        "pack_gap_id",
        "target_proposition",
        "request_ids",
        "semantic_evidence_unit",
        "candidate_ceiling",
        "downstream_disposition",
        "public_top_bounded_packages",
    }
)
_PRIVATE_TARGET_KEYS = frozenset(
    {
        "private_source_packages",
        "private_compiled_packages",
        "private_union_packages",
        "private_final_packages",
        "private_source_to_object_coverage_gaps",
    }
)
_CANDIDATE_CEILING_KEYS = frozenset(
    {
        "source_record_population",
        "canonical_source_family_population",
        "compiled_object_population",
        "complete_target_in_source_record_corpus_count",
        "complete_target_in_compiled_package_corpus_count",
        "partial_context_in_source_record_corpus_count",
        "partial_context_in_compiled_package_corpus_count",
        "candidate_union_object_count",
        "complete_target_in_candidate_union_package_count",
        "final_review_object_count",
        "complete_target_in_final_review_package_count",
        "best_complete_package_final_completion_rank",
        "complete_target_useful_at_10",
        "earliest_observed_limitation",
        "package_materialization_gap_count",
        "material_source_claim_coverage_gap_canonical_count",
        "material_source_claim_coverage_gap_occurrence_count",
        "source_to_object_semantic_coverage_pass",
        "source_position_mode",
        "material_anchor_mode",
        "source_package_scan_digest",
        "candidate_decision_state",
        "public_information_gap_eligible",
    }
)
_DOWNSTREAM_DISPOSITION_KEYS = frozenset(
    {
        "03D_4B_embedding_recall_challenger_eligible",
        "03D_same_pool_reranker_challenger_eligible",
        "03C_external_route_required_for_complete_bounded_target",
        "03C_scope_if_authorized",
        "03C_residual_route_requires_prior_capture_crosswalk",
        "03C_residual_scope_if_authorized",
        "remaining_non_03C_research_boundaries",
        "local_source_to_object_repair_required",
        "mandatory_external_route_contract_ids_if_authorized",
        "authority_granted_by_this_result",
    }
)
_PUBLIC_PACKAGE_KEYS = frozenset(
    {
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
    }
)
_EXECUTION_SUMMARY_KEYS = frozenset(
    {
        "request_count",
        "material_scope_required_request_count",
        "material_scope_ready_request_count",
        "material_set_complete_request_count",
        "snapshot_nonempty_lane_count",
        "compiled_lane_count",
        "hybrid_union_candidate_count",
        "hybrid_selected_candidate_count",
        "model_calls",
        "provider_calls",
        "network_calls",
        "generation_model_calls",
        "local_embedding_inference_batches",
        "external_capture_calls",
        "4B_embedding_calls",
        "reranker_calls",
        "retries",
        "current_mutations",
        "candidate_promotions",
        "evidence_promotions",
        "numeric_fact_count",
        "typed_fact_resolved_count",
        "typed_fact_gap_count",
        "typed_fact_conflict_count",
        "gap_closures",
    }
)
_SUMMARY_KEYS = frozenset(
    {
        "target_count",
        "held_target_execution_count",
        "request_count",
        "candidate_union_occurrence_count",
        "embedding_challenger_eligible_target_count",
        "reranker_challenger_eligible_target_count",
        "external_route_required_target_count",
        "residual_research_boundary_target_count",
        "local_source_to_object_repair_target_count",
        *ZERO_EXECUTION_FIELDS,
    }
)
_AUTHORITY_KEYS = frozenset(
    {
        "03B_R6_execution_consumed",
        "03C_external_capture_authorized",
        "03D_4B_embedding_authorized",
        "03D_reranker_authorized",
        "candidate_decision_authorized",
        "evidence_promotion_authorized",
        "proved_information_boundary_authorized",
        "G3_pass",
        "S1_pass",
        "S2_pass",
        "S3_pass",
        "report_quality_pass",
        "product_acceptance",
        "publication",
        "release_ready",
    }
)
_RUNTIME_REGISTRY_KEYS = frozenset(
    {"registry_id", "resource_canonical_digest"}
)
_STANDARD_BINDING_KEYS = frozenset({"ref", "sha256", "result_digest"})
_GIT_IDENTITY_KEYS = frozenset(
    {
        "branch",
        "head",
        "head_tree",
        "upstream",
        "upstream_equal",
        "clean",
        "implementation_commit",
        "implementation_tree",
        "authority_parent_exact",
        "authority_commit_changed_paths",
    }
)
_DISK_PREFLIGHT_KEYS = frozenset({"free_bytes", "minimum_free_bytes"})
_PUBLIC_BINDING_IDS = frozenset(
    set(EXPECTED_BOUND_INPUT_IDS)
    | {
        "R6_policy",
        "compiled_objects",
        "source_records",
        "attempt_consumption_receipt",
        "git_identity",
        "disk_capacity_preflight",
    }
)
_FORBIDDEN_PUBLIC_LOCATION = re.compile(
    r"(?:\b[a-z][a-z0-9+.-]{1,15}://|www\.|(?:urn|mailto|data):)|"
    r"(?:^|\s)(?:[a-z]:[\\/]|\\\\|//[^/\s]+/[^/\s]+|"
    r"/(?:home|users|tmp|var|etc|mnt|opt|root|workspace)(?:/|\b)|"
    r"/(?:[^/\s]+/)+[^/\s]+)",
    re.IGNORECASE | re.MULTILINE,
)


def _exact_public_mapping(
    value: Any,
    keys: frozenset[str],
    code: str,
) -> dict[str, Any]:
    _require(isinstance(value, Mapping), f"{code}_not_mapping")
    result = dict(value)
    _require(set(result) == keys, f"{code}_unknown_or_missing_key")
    return result


def _validate_public_scalar_tree(value: Any, *, path: str = "public") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key).casefold()
            _require(
                not any(
                    token in key_text
                    for token in (
                        "model_text",
                        "material_sentence",
                        "source_locator",
                        "secret",
                        "excerpt",
                        "raw_text",
                    )
                ),
                f"dell_03B_R6_public_forbidden_field:{path}.{key}",
            )
            _validate_public_scalar_tree(nested, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _validate_public_scalar_tree(nested, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        _require(
            _FORBIDDEN_PUBLIC_LOCATION.search(value) is None,
            f"dell_03B_R6_public_URL_or_absolute_locator:{path}",
        )
        return
    _require(
        value is None or isinstance(value, (bool, int, float)),
        f"dell_03B_R6_public_non_JSON_scalar:{path}",
    )


def _public_input_bindings(value: Any) -> dict[str, Any]:
    bindings = _exact_public_mapping(
        value,
        _PUBLIC_BINDING_IDS,
        "dell_03B_R6_public_input_bindings",
    )
    output: dict[str, Any] = {}
    for binding_id, raw in bindings.items():
        if binding_id == "git_identity":
            row = _exact_public_mapping(
                raw,
                _GIT_IDENTITY_KEYS,
                "dell_03B_R6_public_git_identity",
            )
            _require(
                row.get("branch") == BRANCH
                and all(
                    bool(re.fullmatch(r"[0-9a-f]{40}", str(row.get(key) or "")))
                    for key in (
                        "head",
                        "head_tree",
                        "upstream",
                        "implementation_commit",
                        "implementation_tree",
                    )
                )
                and row.get("upstream_equal") is True
                and row.get("clean") is True
                and row.get("authority_parent_exact") is True
                and row.get("authority_commit_changed_paths") == [POLICY_REF],
                "dell_03B_R6_public_git_identity_value_invalid",
            )
            output[binding_id] = row
        elif binding_id == "disk_capacity_preflight":
            row = _exact_public_mapping(
                raw,
                _DISK_PREFLIGHT_KEYS,
                "dell_03B_R6_public_disk_preflight",
            )
            _require(
                isinstance(row.get("free_bytes"), int)
                and row.get("free_bytes") >= MIN_FREE_BYTES_BEFORE_ATTEMPT
                and row.get("minimum_free_bytes")
                == MIN_FREE_BYTES_BEFORE_ATTEMPT,
                "dell_03B_R6_public_disk_preflight_value_invalid",
            )
            output[binding_id] = row
        else:
            _require(
                isinstance(raw, Mapping),
                f"dell_03B_R6_public_binding_not_mapping:{binding_id}",
            )
            row = dict(raw)
            _require(
                {"ref", "sha256"}.issubset(row)
                and set(row).issubset(_STANDARD_BINDING_KEYS),
                f"dell_03B_R6_public_binding_unknown_or_missing_key:{binding_id}",
            )
            _require(
                bool(str(row.get("ref") or "").strip())
                and bool(
                    re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256") or ""))
                )
                and (
                    "result_digest" not in row
                    or bool(
                        re.fullmatch(
                            r"[0-9a-f]{64}",
                            str(row.get("result_digest") or ""),
                        )
                    )
                ),
                f"dell_03B_R6_public_binding_value_invalid:{binding_id}",
            )
            output[binding_id] = row
    return output


def _public_target_row(value: Any) -> dict[str, Any]:
    _require(
        isinstance(value, Mapping),
        "dell_03B_R6_public_target_not_mapping",
    )
    raw = dict(value)
    _require(
        set(raw) == _PUBLIC_TARGET_KEYS | _PRIVATE_TARGET_KEYS,
        "dell_03B_R6_public_target_unknown_or_missing_key",
    )
    ceiling = _exact_public_mapping(
        raw["candidate_ceiling"],
        _CANDIDATE_CEILING_KEYS,
        "dell_03B_R6_public_candidate_ceiling",
    )
    downstream = _exact_public_mapping(
        raw["downstream_disposition"],
        _DOWNSTREAM_DISPOSITION_KEYS,
        "dell_03B_R6_public_downstream_disposition",
    )
    packages = []
    _require(
        isinstance(raw["public_top_bounded_packages"], (list, tuple)),
        "dell_03B_R6_public_packages_not_sequence",
    )
    for package in raw["public_top_bounded_packages"]:
        packages.append(
            _exact_public_mapping(
                package,
                _PUBLIC_PACKAGE_KEYS,
                "dell_03B_R6_public_package",
            )
        )
    return {
        "target_id": raw["target_id"],
        "pack_gap_id": raw["pack_gap_id"],
        "target_proposition": raw["target_proposition"],
        "request_ids": list(raw["request_ids"]),
        "semantic_evidence_unit": raw["semantic_evidence_unit"],
        "candidate_ceiling": ceiling,
        "downstream_disposition": downstream,
        "public_top_bounded_packages": packages,
    }


def build_dell_report_internal_chain_ceiling_r6_public_projection(
    *, private_result: Mapping[str, Any], private_ref: str, private_sha256: str
) -> dict[str, Any]:
    """Project only schema-known public fields and reject all drift."""

    private = _exact_public_mapping(
        private_result,
        _PRIVATE_RESULT_KEYS,
        "dell_03B_R6_private_result",
    )
    _require(
        private.get("schema_version") == PRIVATE_RESULT_SCHEMA_VERSION
        and private.get("attempt_id") == ATTEMPT_ID
        and private.get("status")
        == "dell_03B_R6_raw_position_typed_anchor_semantic_ceiling_executed"
        and private.get("case_key") == "DELL"
        and bool(
            re.fullmatch(
                r"[0-9a-f]{40}",
                str(private.get("prepared_from_commit") or ""),
            )
        )
        and all(
            bool(
                re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(private.get(key) or ""),
                )
            )
            for key in (
                "raw_execution_sha256",
                "raw_execution_projection_digest",
                "validated_execution_digest",
                "policy_digest",
            )
        )
        and _self_digest(private),
        "dell_03B_R6_private_projection_identity_invalid",
    )
    _require(
        private_ref == PRIVATE_REF
        and bool(re.fullmatch(r"[0-9a-f]{64}", private_sha256)),
        "dell_03B_R6_private_projection_binding_invalid",
    )
    raw_targets = private.get("target_results")
    _require(
        isinstance(raw_targets, (list, tuple)),
        "dell_03B_R6_public_targets_not_sequence",
    )
    target_results = [_public_target_row(row) for row in raw_targets]
    _require(
        len(target_results) == len(TARGET_IDS)
        and {str(row["target_id"]) for row in target_results} == set(TARGET_IDS),
        "dell_03B_R6_public_target_population_invalid",
    )
    authority = _exact_public_mapping(
        private["authority"],
        _AUTHORITY_KEYS,
        "dell_03B_R6_public_authority",
    )
    _require(
        authority.get("03B_R6_execution_consumed") is True
        and all(
            authority.get(key) is False
            for key in _AUTHORITY_KEYS - {"03B_R6_execution_consumed"}
        ),
        "dell_03B_R6_public_authority_value_invalid",
    )
    body = {
        "schema_version": PUBLIC_RESULT_SCHEMA_VERSION,
        "status": private["status"],
        "attempt_id": private["attempt_id"],
        "recorded_at": private["recorded_at"],
        "prepared_from_commit": private["prepared_from_commit"],
        "case_key": private["case_key"],
        "input_bindings": _public_input_bindings(private["input_bindings"]),
        "runtime_registry": _exact_public_mapping(
            private["runtime_registry"],
            _RUNTIME_REGISTRY_KEYS,
            "dell_03B_R6_public_runtime_registry",
        ),
        "raw_execution_sha256": private["raw_execution_sha256"],
        "raw_execution_projection_digest": private[
            "raw_execution_projection_digest"
        ],
        "validated_execution_digest": private["validated_execution_digest"],
        "execution_summary": _exact_public_mapping(
            private["execution_summary"],
            _EXECUTION_SUMMARY_KEYS,
            "dell_03B_R6_public_execution_summary",
        ),
        "target_results": target_results,
        "summary": _exact_public_mapping(
            private["summary"],
            _SUMMARY_KEYS,
            "dell_03B_R6_public_summary",
        ),
        "private_result_ref": private_ref,
        "private_result_sha256": private_sha256,
        "private_result_digest": private["result_digest"],
        "authority": authority,
        "known_boundary": private["known_boundary"],
        "policy_digest": private["policy_digest"],
    }
    _validate_public_scalar_tree(body)
    return {**body, "result_digest": canonical_digest(body)}


__all__ = [
    "ATTEMPT_ID",
    "ATTEMPT_RECEIPT_REF",
    "BRANCH",
    "DellReportInternalChainCeilingR6Error",
    "EXECUTION_CONTRACT",
    "MIN_FREE_BYTES_BEFORE_ATTEMPT",
    "POLICY_REF",
    "POLICY_SCHEMA_VERSION",
    "PRIVATE_REF",
    "PRIVATE_RESULT_SCHEMA_VERSION",
    "PUBLIC_REF",
    "PUBLIC_RESULT_SCHEMA_VERSION",
    "assess_dell_report_internal_chain_r6_packages",
    "build_dell_report_internal_chain_r6_corpus_index",
    "build_dell_report_internal_chain_ceiling_r6_public_projection",
    "classify_dell_report_internal_chain_r6_package",
    "compile_dell_report_internal_chain_ceiling_r6_result",
    "validate_dell_report_internal_chain_ceiling_r6_policy",
]
