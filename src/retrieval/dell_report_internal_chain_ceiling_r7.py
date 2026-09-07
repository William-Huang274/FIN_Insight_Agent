from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from pathlib import PurePosixPath
import re
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import unquote

from . import dell_report_internal_chain_ceiling as legacy
from . import dell_report_internal_chain_ceiling_r3 as r3
from . import dell_report_internal_chain_ceiling_r4 as r4
from . import dell_report_internal_chain_ceiling_r6 as r6
from .dell_report_proposition_semantics_r7 import (
    classify_package as _classify_single_proposition_r7,
    extract_typed_propositions,
    generic_typed_material_anchors,
)
from .query_plan import canonical_digest


POLICY_SCHEMA_VERSION = "fin_ia_dell_report_internal_chain_ceiling_policy_v1_6"
PRIVATE_RESULT_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_candidate_ceiling_private_result_v1_6"
)
PUBLIC_RESULT_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_candidate_ceiling_result_v1_6"
)
ATTEMPT_ID = "dell-rsq-03b-internal-chain-r7"
PROGRAM_ID = "FIN-0.1.3-S1-DELL-RSQ-03B-R7"
BRANCH = r6.BRANCH
POLICY_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_6.json"
)
PUBLIC_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_6.json"
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
MIN_FREE_BYTES_BEFORE_ATTEMPT = 512 * 1024 * 1024
TARGET_IDS = r6.TARGET_IDS
ZERO_EXECUTION_FIELDS = r6.ZERO_EXECUTION_FIELDS
EXECUTION_CONTRACT = dict(r6.EXECUTION_CONTRACT)
AUTHORITY = dict(r6.AUTHORITY)
SEMANTIC_CONTRACT = {
    "canonical_source_family_mode": (
        "page_parent_and_slice_family_with_raw_occurrence_positions"
    ),
    "adjacency_order_mode": (
        "raw_sentence_occurrence_before_dedup_then_absolute_position"
    ),
    "maximum_adjacent_source_or_object_units": 1,
    "selected_pool_adjacency_mode": (
        "absolute_corpus_positions_not_selected_only_positions"
    ),
    "proposition_mode": (
        "one_complete_equals_one_typed_proposition_no_cross_clause_or_sentence_group_union"
    ),
    "supplier_role": "one_proposition_supplier_Dell_direction_and_status",
    "yield_role": "one_proposition_observed_measure_process_and_period",
    "units_role": "one_proposition_Dell_shipper_physical_quantity_and_period",
    "ASP_role": (
        "affirmative_bounded_configuration_or_bundle_price_not_company_realized_ASP"
    ),
    "material_coverage_mode": (
        "accepted_proposition_role_bound_product_price_quantity_period_process_anchor_v3"
    ),
    "coverage_count_mode": (
        "canonical_claim_and_raw_source_occurrence_both_reported"
    ),
    "reranker_useful_at_k": 10,
    "candidate_not_evidence": True,
    "public_projection_mode": (
        "recursive_explicit_allowlist_plus_field_typed_content_fail_closed"
    ),
}
EXPECTED_IMPLEMENTATION_PATHS = frozenset(
    set(r6.EXPECTED_IMPLEMENTATION_PATHS)
    | {
        "src/retrieval/dell_report_proposition_semantics_r7.py",
        "src/retrieval/dell_report_internal_chain_ceiling_r7.py",
        "scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r7.py",
    }
)
EXPECTED_BOUND_INPUT_IDS = frozenset(
    set(r6.EXPECTED_BOUND_INPUT_IDS)
    | {
        "R6_policy",
        "R6_public",
        "R6_private",
        "R6_attempt_receipt",
        "R6_fresh_audit",
    }
)
R6_AUDIT_STATUS = (
    "fail_material_semantic_anchor_privacy_and_report_findings_"
    "same_stage_R7_required"
)
R6_REQUIRED_ROOT_CAUSES = {
    "RC-S1-079-DELL-03B-clause-scope-polarity-modality-direction-and-ASP-affirmation",
    "RC-S1-080-DELL-03B-typed-anchor-product-code-and-fiscal-year-normalization",
    "RC-S0-105-R5-public-projector-denylist-not-fail-closed",
}


class DellReportInternalChainCeilingR7Error(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellReportInternalChainCeilingR7Error(code)


def _self_digest(value: Mapping[str, Any]) -> bool:
    body = dict(value)
    observed = str(body.pop("result_digest", ""))
    return bool(observed) and observed == canonical_digest(body)


def validate_dell_report_internal_chain_ceiling_r7_policy(
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
    r6_policy: Mapping[str, Any],
    r6_public: Mapping[str, Any],
    r6_private: Mapping[str, Any],
    r6_attempt_receipt: Mapping[str, Any],
    r6_fresh_audit: Mapping[str, Any],
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
    """Validate the R7 envelope and immutable fresh-R6 failure boundary."""

    validated_r1 = r6.validate_dell_report_internal_chain_ceiling_r6_policy(
        r6_policy,
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
        r5_policy=r5_policy,
        r5_public=r5_public,
        r5_private=r5_private,
        r5_attempt_receipt=r5_attempt_receipt,
        r5_fresh_audit=r5_fresh_audit,
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
    _require(_self_digest(policy), "dell_03B_R7_policy_digest_invalid")
    _require(
        policy.get("schema_version") == POLICY_SCHEMA_VERSION
        and policy.get("status")
        == "same_stage_R7_execution_authorized_after_fresh_R6_audit_failure"
        and policy.get("program_id") == PROGRAM_ID
        and policy.get("attempt_id") == ATTEMPT_ID,
        "dell_03B_R7_policy_identity_invalid",
    )
    _require(
        dict(policy.get("execution_contract") or {}) == EXECUTION_CONTRACT
        and dict(policy.get("semantic_contract") or {}) == SEMANTIC_CONTRACT
        and dict(policy.get("authority") or {}) == AUTHORITY,
        "dell_03B_R7_policy_contract_invalid",
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
        "dell_03B_R7_output_contract_invalid",
    )
    bound_inputs = dict(policy.get("bound_inputs") or {})
    _require(
        set(bound_inputs) == EXPECTED_BOUND_INPUT_IDS
        and all(
            isinstance(row, Mapping)
            and bool(str(row.get("ref") or "").strip())
            and bool(
                re.fullmatch(
                    r"[0-9a-f]{64}", str(row.get("sha256") or "")
                )
            )
            for row in bound_inputs.values()
        ),
        "dell_03B_R7_bound_inputs_invalid",
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
        "dell_03B_R7_implementation_bindings_invalid",
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
        "dell_03B_R7_execution_identity_invalid",
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
        "dell_03B_R7_token_budget_basis_invalid",
    )

    verdicts = dict(r6_fresh_audit.get("verdicts") or {})
    audit_authority = dict(r6_fresh_audit.get("authority") or {})
    _require(
        r6_fresh_audit.get("schema_version")
        == "fin_ia_independent_readonly_audit_result_v1_0"
        and r6_fresh_audit.get("status") == R6_AUDIT_STATUS
        and verdicts.get("overall") == "FAIL"
        and verdicts.get("new_R6_P0_P1_P2_P3") == [0, 0, 3, 0]
        and verdicts.get("R17_open_P0_P1_P2_P3") == [0, 1, 2, 1]
        and verdicts.get("R6_integrity") == "PASS"
        and verdicts.get("R6_actual_route")
        == "PASS_BOUNDED_FOR_ACTUAL_IMMUTABLE_EXECUTION"
        and verdicts.get("R6_general_semantic_anchor_privacy") == "FAIL"
        and verdicts.get("03B_independent_pass") is False
        and audit_authority.get("R7_same_stage_successor") is True
        and audit_authority.get("R6_retry_or_overwrite") is False
        and _self_digest(r6_fresh_audit),
        "dell_03B_R7_predecessor_audit_invalid",
    )
    findings = list(r6_fresh_audit.get("material_findings") or ())
    observed_root_causes = {
        str(row.get("root_cause_id") or "")
        for row in findings
        if isinstance(row, Mapping)
        and str(row.get("finding_id") or "").startswith("R6-")
    }
    _require(
        R6_REQUIRED_ROOT_CAUSES == observed_root_causes,
        "dell_03B_R7_required_root_causes_missing_or_extra",
    )
    _require(
        sum(
            isinstance(row, Mapping)
            and str(row.get("finding_id") or "").startswith("R6-")
            and row.get("severity") == "P2"
            for row in findings
        )
        == 3,
        "dell_03B_R7_R6_finding_population_invalid",
    )
    reviewed = dict(r6_fresh_audit.get("reviewed_artifacts") or {})
    for binding_id in (
        "R6_policy",
        "R6_public",
        "R6_private",
        "R6_attempt_receipt",
    ):
        expected = dict(bound_inputs.get(binding_id) or {})
        observed = dict(reviewed.get(binding_id) or {})
        _require(
            observed.get("ref") == expected.get("ref")
            and observed.get("sha256") == expected.get("sha256"),
            f"dell_03B_R7_{binding_id}_audit_binding_invalid",
        )
    _require(
        dict(reviewed.get("R6_policy") or {}).get("result_digest")
        == r6_policy.get("result_digest")
        and dict(reviewed.get("R6_public") or {}).get("result_digest")
        == r6_public.get("result_digest")
        and dict(reviewed.get("R6_private") or {}).get("result_digest")
        == r6_private.get("result_digest")
        and dict(reviewed.get("R6_attempt_receipt") or {}).get(
            "result_digest"
        )
        == r6_attempt_receipt.get("result_digest"),
        "dell_03B_R7_R6_reviewed_digest_binding_invalid",
    )
    _require(
        r6_policy.get("attempt_id") == r6.ATTEMPT_ID
        and r6_public.get("attempt_id") == r6.ATTEMPT_ID
        and r6_private.get("attempt_id") == r6.ATTEMPT_ID
        and r6_attempt_receipt.get("attempt_id") == r6.ATTEMPT_ID
        and _self_digest(r6_policy)
        and _self_digest(r6_public)
        and _self_digest(r6_private)
        and _self_digest(r6_attempt_receipt)
        and r6_public.get("private_result_digest")
        == r6_private.get("result_digest")
        and r6_attempt_receipt.get("policy_digest")
        == r6_policy.get("result_digest")
        and r6_private.get("raw_execution_sha256")
        == dict(reviewed.get("raw_execution") or {}).get("sha256"),
        "dell_03B_R7_R6_result_binding_invalid",
    )
    verified = dict(
        r6_fresh_audit.get("verified_execution_and_integrity") or {}
    )
    _require(
        verified.get("bound_inputs") == 24
        and verified.get("implementation_bindings") == 14
        and verified.get("all_hashes_valid") is True
        and verified.get("exact_private_recompile") is True
        and verified.get("exact_public_reprojection") is True
        and verified.get("current_public_actual_leak") is False
        and verified.get("request_count") == 5
        and verified.get("one_local_0_6B_batch") is True
        and verified.get("all_forbidden_call_mutation_promotion_closure_counters_zero")
        is True
        and verified.get("attempt_exact_once") is True,
        "dell_03B_R7_R6_execution_integrity_invalid",
    )
    private_authority = dict(r6_private.get("authority") or {})
    _require(
        private_authority.get("03B_R6_execution_consumed") is True
        and private_authority.get("03C_external_capture_authorized")
        is False
        and private_authority.get("03D_4B_embedding_authorized") is False
        and private_authority.get("03D_reranker_authorized") is False
        and private_authority.get("candidate_decision_authorized") is False
        and private_authority.get("evidence_promotion_authorized") is False
        and private_authority.get("report_quality_pass") is False
        and private_authority.get("product_acceptance") is False,
        "dell_03B_R7_R6_authority_boundary_invalid",
    )
    return validated_r1

def _normalize_text(value: Any) -> str:
    return r4._normalize_text(value)  # noqa: SLF001


def _sentence_units(text: str) -> list[str]:
    return r4._sentence_units(text)  # noqa: SLF001


def _source_units_for_family_r7(
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


def build_dell_report_internal_chain_r7_corpus_index(
    *,
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    families, source_order = r4._source_families(source_rows)  # noqa: SLF001
    return {
        "families": families,
        "source_order": source_order,
        "source_units_by_family": {
            family_id: _source_units_for_family_r7(rows, source_order)
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


def _target_hint_r7(target_id: str, text: str) -> bool:
    """Cheap recall-only prefilter that is a superset of each R7 extractor."""

    normalized = _normalize_text(text)
    terms = {
        "DELL-RSQ-03A-TARGET-ASP": (
            "$",
            "usd",
            "dollar",
            "price",
            "quote",
            "sold",
            "dell",
            "poweredge",
            "server",
            "system",
        ),
        "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH": (
            "dell",
            "nvidia",
            "micron",
            "tsmc",
            "taiwan semiconductor",
            "sk hynix",
            "broadcom",
            "partner",
            "collaborat",
            "alliance",
            "team",
            "suppl",
            "deliver",
            "ship",
            "available",
        ),
        "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE": (
            "capacity",
            "allocation",
            "supply",
        ),
        "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD": (
            "yield",
            "utilization",
        ),
        "DELL-RSQ-03A-TARGET-HBM-SUPPLY": (
            "hbm",
            "high bandwidth memory",
        ),
        "DELL-RSQ-03A-TARGET-UNITS": (
            "shipped",
            "delivered",
            "sent",
            "server",
            "system",
            "node",
            "poweredge",
        ),
    }[target_id]
    return any(term in normalized for term in terms)


def _package_windows_r7(
    *,
    target_id: str,
    units: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any],
    selected_object_ids: set[str] | None,
    rank_by_object_id: Mapping[str, int] | None,
) -> list[dict[str, Any]]:
    """Classify one raw sentence at a time under the R7 proposition contract."""

    if not units:
        return []
    output: list[dict[str, Any]] = []
    for unit in units:
        unit_id = str(unit["unit_id"])
        text = str(unit.get("text") or "")
        if (
            selected_object_ids is not None
            and unit_id not in selected_object_ids
        ) or not _target_hint_r7(target_id, text):
            continue
        assessment = classify_dell_report_internal_chain_r7_package(
            target_id=target_id,
            text=text,
            metadata=metadata,
        )
        position = int(unit["position"])
        assessment.update(
            {
                "unit_ids": [unit_id],
                "window_start_position": position,
                "window_end_position": position,
                "window_unit_span": 1,
                "completion_rank": None,
            }
        )
        if (
            assessment["classification"] == "complete_bounded_target_package"
            and rank_by_object_id
        ):
            accepted_rank = rank_by_object_id.get(unit_id)
            if accepted_rank is not None:
                assessment["completion_rank"] = int(accepted_rank)
        output.append(assessment)
    return output


def _best_package_r7(
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
        value = classify_dell_report_internal_chain_r7_package(
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


# R7 replaces the inherited R6 regex/group-aggregation seam; every package,
# rank and materialization call resolves this single-proposition classifier.
def classify_dell_report_internal_chain_r7_package(
    *, target_id: str, text: str, metadata: Mapping[str, Any]
) -> dict[str, Any]:
    return _classify_single_proposition_r7(
        target_id=target_id,
        text=text,
        metadata=metadata,
    )


def _typed_material_anchors(text: str) -> list[str]:
    """Compatibility surface backed by the R7 canonical grammar."""

    return generic_typed_material_anchors(text)


def _material_fingerprint_r7(
    target_id: str, sentence: str, metadata: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Fingerprint one accepted proposition; never union package groups."""

    if not _target_hint_r7(target_id, sentence):
        return None
    assessment = classify_dell_report_internal_chain_r7_package(
        target_id=target_id,
        text=sentence,
        metadata=metadata,
    )
    if assessment.get("classification") != "complete_bounded_target_package":
        return None
    proposition_id = assessment.get("accepted_proposition_id")
    proposition_digest = assessment.get("accepted_proposition_digest")
    anchors = list(
        assessment.get("accepted_proposition_role_anchors") or ()
    )
    _require(
        isinstance(proposition_id, str)
        and bool(proposition_id)
        and isinstance(proposition_digest, str)
        and bool(re.fullmatch(r"[0-9a-f]{64}", proposition_digest))
        and anchors,
        "dell_03B_R7_material_fingerprint_proposition_invalid",
    )
    normalized = _normalize_text(sentence)
    return {
        "normalized_sentence": normalized,
        "sentence_digest": canonical_digest(normalized),
        "accepted_proposition_id": proposition_id,
        "accepted_proposition_digest": proposition_digest,
        "required_material_group_ids": list(
            assessment.get("required_group_ids") or ()
        ),
        "material_anchors": sorted(str(anchor) for anchor in anchors),
        "anchor_mode": "accepted_proposition_role_bound_v3",
    }


def _coverage_gaps_r7(
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
    for unit in source_units:
        fingerprint = _material_fingerprint_r7(
            target_id,
            str(unit.get("text") or ""),
            metadata,
        )
        if fingerprint is None:
            continue
        digest = str(fingerprint["sentence_digest"])
        occurrence_counts[digest] += 1
        occurrence_source_ids[digest].add(
            str(unit.get("source_record_id") or family_id)
        )
        fingerprints.setdefault(digest, fingerprint)
    canonical_digests = set(fingerprints)
    gaps: list[dict[str, Any]] = []
    for digest in sorted(canonical_digests):
        fingerprint = fingerprints[digest]
        groups = set(fingerprint["required_material_group_ids"])
        anchors = set(fingerprint["material_anchors"])
        covered = False
        for window in compiled_windows:
            if (
                window.get("classification")
                != "complete_bounded_target_package"
                or not groups.issubset(
                    set(window.get("matched_group_ids") or ())
                )
            ):
                continue
            compiled_anchors = set(
                window.get("accepted_proposition_role_anchors") or ()
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
                    "anchor_mode": "accepted_proposition_role_bound_v3",
                    "reason": (
                        "canonical_material_source_claim_missing_from_bounded_"
                        "compiled_object_windows"
                    ),
                }
            )
    return gaps


def assess_dell_report_internal_chain_r7_packages(
    *,
    target_id: str,
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
    selected_object_ids: Iterable[str] | None = None,
    rank_by_object_id: Mapping[str, int] | None = None,
    corpus_index: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess R7 raw-position families and typed material coverage."""

    index = (
        dict(corpus_index)
        if corpus_index is not None
        else build_dell_report_internal_chain_r7_corpus_index(
            source_rows=source_rows,
            object_rows=object_rows,
        )
    )
    _require(
        int(index.get("source_record_count") or 0) == len(source_rows)
        and int(index.get("compiled_object_count") or 0) == len(object_rows)
        and index.get("source_position_mode")
        == "raw_occurrence_before_deduplication",
        "dell_03B_R7_corpus_index_population_or_position_drift",
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
            source_windows = _package_windows_r7(
                target_id=target_id,
                units=source_units,
                metadata=metadata,
                selected_object_ids=None,
                rank_by_object_id=None,
            )
            source_packages.append(
                _best_package_r7(
                    source_windows,
                    family_id=family_id,
                    metadata=metadata,
                    object_package=False,
                )
            )
        object_units = objects_by_family.get(family_id, [])
        object_windows = _package_windows_r7(
            target_id=target_id,
            units=object_units,
            metadata=metadata,
            selected_object_ids=selected,
            rank_by_object_id=rank_by_object_id,
        )
        compiled_packages.append(
            _best_package_r7(
                object_windows,
                family_id=family_id,
                metadata=metadata,
                object_package=True,
            )
        )
        if selected is None:
            coverage.extend(
                _coverage_gaps_r7(
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


def compile_dell_report_internal_chain_ceiling_r7_result(
    *,
    legacy_policy: Mapping[str, Any],
    r7_policy: Mapping[str, Any],
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
    """Compile the single-pass R7 semantic and material-coverage result."""

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
        "dell_03B_R7_execution_sha_mismatch",
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
    corpus_index = build_dell_report_internal_chain_r7_corpus_index(
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
            f"dell_03B_R7_candidate_object_binding_invalid:{target_id}",
        )
        total_union_occurrences += len(union_ids)
        corpus = assess_dell_report_internal_chain_r7_packages(
            target_id=target_id,
            source_rows=source_rows,
            object_rows=object_rows,
            corpus_index=corpus_index,
        )
        union_rank = r4._rank_map(  # noqa: SLF001
            union_ids, scoped_results, "minimum_raw_union_rank"
        )
        union = assess_dell_report_internal_chain_r7_packages(
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
        final = assess_dell_report_internal_chain_r7_packages(
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
                    "one_raw_sentence_single_typed_proposition_clause_"
                    "canonical_source_family_unit"
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
                        "accepted_proposition_role_bound_v3"
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
                                    "accepted_proposition_id",
                                    "accepted_proposition_digest",
                                    "accepted_proposition_role_anchors",
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
                "dell_03B_R7_single_proposition_role_anchor_public_content_ceiling_executed"
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
                "03B_R7_execution_consumed": True,
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
                "R7 assigns immutable raw source-sentence occurrence positions "
                "before display deduplication and permits completion only when "
                "one accepted typed proposition supplies every required actor, "
                "predicate, object, direction, status, quantity and period role. "
                "Material anchors are derived only from that proposition's roles; "
                "cross-clause, cross-sentence and package-level group union is "
                "non-authoritative. The recursive public key allowlist is paired "
                "with field-typed, percent-decoded content validation for refs, "
                "identifiers, digests, narrative, locators, traversal and secret-"
                "like values. Configuration prices remain non-company ASP and "
                "candidates remain non-Evidence. No 03C, 4B, reranker, promotion, "
                "gap closure, human, report, product, publication or release "
                "authority is granted."
            ),
            "policy_digest": r7_policy.get("result_digest"),
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
        "03B_R7_execution_consumed",
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
        "R7_policy",
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
_PARENT_TRAVERSAL = re.compile(r"(?:^|[\\/])\.\.(?:[\\/]|$)")
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"\b(?:api[_-]?key|access[_-]?token|auth(?:orization)?|bearer|"
    r"client[_-]?secret|credential|password|passwd|private[_-]?key)"
    r"\s*[:=]\s*['\"]?[^\s,;]{6,}",
    re.IGNORECASE,
)
_SECRET_LIKE_TOKEN = re.compile(
    r"\b(?:(?:secret|token|credential|private|key)[_-]"
    r"(?:live|prod|production|private|value)[_-][a-z0-9_=-]{8,}|"
    r"[a-z]{2}-(?:proj|live|prod)-[a-z0-9_-]{16,})\b",
    re.IGNORECASE,
)
_TOKEN_CANDIDATE = re.compile(r"[A-Za-z0-9_+/=-]{32,}")
_DIGEST_FIELDS = frozenset(
    {
        "sha256",
        "result_digest",
        "resource_canonical_digest",
        "source_package_scan_digest",
        "raw_execution_sha256",
        "raw_execution_projection_digest",
        "validated_execution_digest",
        "private_result_sha256",
        "private_result_digest",
        "policy_digest",
    }
)
_COMMIT_FIELDS = frozenset(
    {
        "head",
        "head_tree",
        "upstream",
        "implementation_commit",
        "implementation_tree",
        "prepared_from_commit",
    }
)
_REPO_REF_FIELDS = frozenset(
    {"ref", "private_result_ref", "authority_commit_changed_paths"}
)
_PUBLIC_REF_ROOTS = frozenset(
    {"configs", "data", "docs", "reports", "scripts", "src", "tests"}
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


def _decoded_public_string(value: str) -> str:
    decoded = value
    for _ in range(3):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    return decoded


def _token_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {token: value.count(token) for token in set(value)}
    length = len(value)
    return -sum(
        (count / length) * math.log2(count / length)
        for count in counts.values()
    )


def _validate_no_public_content_threat(value: str, *, path: str) -> str:
    _require(
        not any(ord(token) < 32 and token not in "\t\n\r" for token in value),
        f"dell_03B_R7_public_control_character:{path}",
    )
    decoded = _decoded_public_string(value)
    _require(
        _FORBIDDEN_PUBLIC_LOCATION.search(decoded) is None,
        f"dell_03B_R7_public_URL_or_absolute_locator:{path}",
    )
    _require(
        _PARENT_TRAVERSAL.search(decoded) is None,
        f"dell_03B_R7_public_relative_parent_traversal:{path}",
    )
    _require(
        _CREDENTIAL_ASSIGNMENT.search(decoded) is None,
        f"dell_03B_R7_public_credential_assignment:{path}",
    )
    _require(
        _SECRET_LIKE_TOKEN.search(decoded) is None,
        f"dell_03B_R7_public_secret_like_token:{path}",
    )
    return decoded


def _validate_repo_relative_ref(value: str, *, path: str) -> None:
    decoded = _validate_no_public_content_threat(value, path=path)
    _require(
        decoded == value
        and "\\" not in value
        and not value.startswith("/")
        and not re.match(r"^[a-zA-Z]:", value)
        and bool(re.fullmatch(r"[A-Za-z0-9._/-]+", value)),
        f"dell_03B_R7_public_repo_ref_grammar:{path}",
    )
    pure = PurePosixPath(value)
    _require(
        pure.parts
        and pure.parts[0] in _PUBLIC_REF_ROOTS
        and all(part not in {"", ".", ".."} for part in pure.parts),
        f"dell_03B_R7_public_repo_ref_scope:{path}",
    )


def _validate_public_identifier(value: str, *, field: str, path: str) -> bool:
    if field == "target_id":
        _require(
            value in TARGET_IDS,
            f"dell_03B_R7_public_target_id_value:{path}",
        )
        return True
    if field == "attempt_id":
        _require(
            value == ATTEMPT_ID,
            f"dell_03B_R7_public_attempt_id_value:{path}",
        )
        return True
    if field == "case_key":
        _require(
            value == "DELL",
            f"dell_03B_R7_public_case_key_value:{path}",
        )
        return True
    if field == "request_ids":
        _require(
            bool(re.fullmatch(r"REQ::DELL::[A-Z0-9_-]+::V[0-9]+", value)),
            f"dell_03B_R7_public_request_id_grammar:{path}",
        )
        return True
    if field == "compiled_object_ids":
        _require(
            bool(re.fullmatch(r"COBJ::[A-Za-z0-9_-]{8,64}", value)),
            f"dell_03B_R7_public_compiled_object_id_grammar:{path}",
        )
        return True
    if field in {"canonical_source_family_id", "source_record_id"}:
        _require(
            len(value) <= 512
            and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]+", value)),
            f"dell_03B_R7_public_source_identity_grammar:{path}",
        )
        return True
    if field == "pack_gap_id":
        _require(
            bool(re.fullmatch(r"[a-z0-9][a-z0-9_-]{3,96}", value)),
            f"dell_03B_R7_public_pack_gap_id_grammar:{path}",
        )
        return True
    return False


def _validate_public_string(value: str, *, field: str, path: str) -> None:
    if field in _DIGEST_FIELDS:
        _require(
            bool(re.fullmatch(r"[0-9a-f]{64}", value)),
            f"dell_03B_R7_public_digest_grammar:{path}",
        )
        return
    if field in _COMMIT_FIELDS:
        _require(
            bool(re.fullmatch(r"[0-9a-f]{40}", value)),
            f"dell_03B_R7_public_commit_grammar:{path}",
        )
        return
    if field in _REPO_REF_FIELDS:
        _validate_repo_relative_ref(value, path=path)
        return
    if _validate_public_identifier(value, field=field, path=path):
        return
    decoded = _validate_no_public_content_threat(value, path=path)
    _require(
        len(decoded) <= 8192,
        f"dell_03B_R7_public_string_too_long:{path}",
    )
    for token in _TOKEN_CANDIDATE.findall(decoded):
        _require(
            bool(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", token))
            or _token_entropy(token) < 4.35,
            f"dell_03B_R7_public_secret_like_high_entropy:{path}",
        )


def _validate_public_scalar_tree(
    value: Any,
    *,
    path: str = "public",
    field: str = "public",
) -> None:
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
                f"dell_03B_R7_public_forbidden_field:{path}.{key}",
            )
            _validate_public_scalar_tree(
                nested,
                path=f"{path}.{key}",
                field=str(key),
            )
        return
    if isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _validate_public_scalar_tree(
                nested,
                path=f"{path}[{index}]",
                field=field,
            )
        return
    if isinstance(value, str):
        _validate_public_string(value, field=field, path=path)
        return
    _require(
        value is None or isinstance(value, (bool, int, float)),
        f"dell_03B_R7_public_non_JSON_scalar:{path}",
    )


def _public_input_bindings(value: Any) -> dict[str, Any]:
    bindings = _exact_public_mapping(
        value,
        _PUBLIC_BINDING_IDS,
        "dell_03B_R7_public_input_bindings",
    )
    output: dict[str, Any] = {}
    for binding_id, raw in bindings.items():
        if binding_id == "git_identity":
            row = _exact_public_mapping(
                raw,
                _GIT_IDENTITY_KEYS,
                "dell_03B_R7_public_git_identity",
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
                "dell_03B_R7_public_git_identity_value_invalid",
            )
            output[binding_id] = row
        elif binding_id == "disk_capacity_preflight":
            row = _exact_public_mapping(
                raw,
                _DISK_PREFLIGHT_KEYS,
                "dell_03B_R7_public_disk_preflight",
            )
            _require(
                isinstance(row.get("free_bytes"), int)
                and row.get("free_bytes") >= MIN_FREE_BYTES_BEFORE_ATTEMPT
                and row.get("minimum_free_bytes")
                == MIN_FREE_BYTES_BEFORE_ATTEMPT,
                "dell_03B_R7_public_disk_preflight_value_invalid",
            )
            output[binding_id] = row
        else:
            _require(
                isinstance(raw, Mapping),
                f"dell_03B_R7_public_binding_not_mapping:{binding_id}",
            )
            row = dict(raw)
            _require(
                {"ref", "sha256"}.issubset(row)
                and set(row).issubset(_STANDARD_BINDING_KEYS),
                f"dell_03B_R7_public_binding_unknown_or_missing_key:{binding_id}",
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
                f"dell_03B_R7_public_binding_value_invalid:{binding_id}",
            )
            output[binding_id] = row
    return output


def _public_target_row(value: Any) -> dict[str, Any]:
    _require(
        isinstance(value, Mapping),
        "dell_03B_R7_public_target_not_mapping",
    )
    raw = dict(value)
    _require(
        set(raw) == _PUBLIC_TARGET_KEYS | _PRIVATE_TARGET_KEYS,
        "dell_03B_R7_public_target_unknown_or_missing_key",
    )
    ceiling = _exact_public_mapping(
        raw["candidate_ceiling"],
        _CANDIDATE_CEILING_KEYS,
        "dell_03B_R7_public_candidate_ceiling",
    )
    downstream = _exact_public_mapping(
        raw["downstream_disposition"],
        _DOWNSTREAM_DISPOSITION_KEYS,
        "dell_03B_R7_public_downstream_disposition",
    )
    packages = []
    _require(
        isinstance(raw["public_top_bounded_packages"], (list, tuple)),
        "dell_03B_R7_public_packages_not_sequence",
    )
    for package in raw["public_top_bounded_packages"]:
        packages.append(
            _exact_public_mapping(
                package,
                _PUBLIC_PACKAGE_KEYS,
                "dell_03B_R7_public_package",
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


def build_dell_report_internal_chain_ceiling_r7_public_projection(
    *, private_result: Mapping[str, Any], private_ref: str, private_sha256: str
) -> dict[str, Any]:
    """Project only schema-known public fields and reject all drift."""

    private = _exact_public_mapping(
        private_result,
        _PRIVATE_RESULT_KEYS,
        "dell_03B_R7_private_result",
    )
    _require(
        private.get("schema_version") == PRIVATE_RESULT_SCHEMA_VERSION
        and private.get("attempt_id") == ATTEMPT_ID
        and private.get("status")
        == "dell_03B_R7_single_proposition_role_anchor_public_content_ceiling_executed"
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
        "dell_03B_R7_private_projection_identity_invalid",
    )
    _require(
        private_ref == PRIVATE_REF
        and bool(re.fullmatch(r"[0-9a-f]{64}", private_sha256)),
        "dell_03B_R7_private_projection_binding_invalid",
    )
    raw_targets = private.get("target_results")
    _require(
        isinstance(raw_targets, (list, tuple)),
        "dell_03B_R7_public_targets_not_sequence",
    )
    target_results = [_public_target_row(row) for row in raw_targets]
    _require(
        len(target_results) == len(TARGET_IDS)
        and {str(row["target_id"]) for row in target_results} == set(TARGET_IDS),
        "dell_03B_R7_public_target_population_invalid",
    )
    authority = _exact_public_mapping(
        private["authority"],
        _AUTHORITY_KEYS,
        "dell_03B_R7_public_authority",
    )
    _require(
        authority.get("03B_R7_execution_consumed") is True
        and all(
            authority.get(key) is False
            for key in _AUTHORITY_KEYS - {"03B_R7_execution_consumed"}
        ),
        "dell_03B_R7_public_authority_value_invalid",
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
            "dell_03B_R7_public_runtime_registry",
        ),
        "raw_execution_sha256": private["raw_execution_sha256"],
        "raw_execution_projection_digest": private[
            "raw_execution_projection_digest"
        ],
        "validated_execution_digest": private["validated_execution_digest"],
        "execution_summary": _exact_public_mapping(
            private["execution_summary"],
            _EXECUTION_SUMMARY_KEYS,
            "dell_03B_R7_public_execution_summary",
        ),
        "target_results": target_results,
        "summary": _exact_public_mapping(
            private["summary"],
            _SUMMARY_KEYS,
            "dell_03B_R7_public_summary",
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
    "DellReportInternalChainCeilingR7Error",
    "EXECUTION_CONTRACT",
    "MIN_FREE_BYTES_BEFORE_ATTEMPT",
    "POLICY_REF",
    "POLICY_SCHEMA_VERSION",
    "PRIVATE_REF",
    "PRIVATE_RESULT_SCHEMA_VERSION",
    "PUBLIC_REF",
    "PUBLIC_RESULT_SCHEMA_VERSION",
    "assess_dell_report_internal_chain_r7_packages",
    "build_dell_report_internal_chain_r7_corpus_index",
    "build_dell_report_internal_chain_ceiling_r7_public_projection",
    "classify_dell_report_internal_chain_r7_package",
    "compile_dell_report_internal_chain_ceiling_r7_result",
    "extract_typed_propositions",
    "validate_dell_report_internal_chain_ceiling_r7_policy",
]
