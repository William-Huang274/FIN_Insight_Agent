from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]

from retrieval.dell_report_internal_chain_ceiling_r5 import (
    ATTEMPT_ID,
    ATTEMPT_RECEIPT_REF,
    AUTHORITY,
    BRANCH,
    EXECUTION_CONTRACT,
    EXPECTED_BOUND_INPUT_IDS,
    EXPECTED_IMPLEMENTATION_PATHS,
    MIN_FREE_BYTES_BEFORE_ATTEMPT,
    POLICY_REF,
    POLICY_SCHEMA_VERSION,
    PRIVATE_REF,
    PROGRAM_ID,
    PUBLIC_REF,
    SEMANTIC_CONTRACT,
    DellReportInternalChainCeilingR5Error,
    _typed_material_anchors,
    assess_dell_report_internal_chain_r5_packages,
    classify_dell_report_internal_chain_r5_package,
    validate_dell_report_internal_chain_ceiling_r5_policy,
)
from retrieval.dell_report_internal_chain_ceiling_r4 import (
    assess_dell_report_internal_chain_r4_packages,
    classify_dell_report_internal_chain_r4_package,
)
from retrieval.query_plan import canonical_digest
from scripts.data_retrieval import (
    run_dell_report_internal_chain_ceiling_r5 as r5_runner,
)


def _metadata(ticker: str = "NVDA") -> dict:
    return {
        "ticker": ticker,
        "source_type": "PUBLIC_WEB",
        "source_tier": "named_counterparty_or_standards_primary",
        "publication_date": "2025-05-27",
    }


def _source(source_id: str, text: str, ticker: str = "NVDA") -> dict:
    return {
        "evidence_id": source_id,
        "text": text,
        "metadata": {},
        **_metadata(ticker),
    }


def _object(
    object_id: str,
    source_id: str,
    text: str,
    *,
    ticker: str = "NVDA",
) -> dict:
    return {
        "compiled_object_id": object_id,
        "candidate_not_evidence": True,
        "evidence_promoted": False,
        "numeric_authority": False,
        "lineage_source_record_ids": [source_id],
        "model_text": text,
        "base_object_view": {
            "source_record_id": source_id,
            "focus_binding": {"mode": "parent_context"},
            **_metadata(ticker),
        },
    }


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA have no partnership for delivery.",
        ),
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA lack a partnership for delivery.",
        ),
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA denied a partnership for delivery.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was not allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was never allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was unavailable to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was not yet allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was denied to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield rate will reach 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield rate is forecast to reach 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield rate is planned to reach 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "N2 pilot line HBM production yield rate is 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "HBM availability was unavailable to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "HBM supply capacity was not allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "HBM supply capacity was unavailable to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "HBM supply capacity was not configured for Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell has not shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell never shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell denied it shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell has not yet shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell said NVIDIA shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell said the customer shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
    ],
)
def test_R5_freezes_every_R4_semantic_attack(
    target_id: str, text: str
) -> None:
    predecessor = classify_dell_report_internal_chain_r4_package(
        target_id=target_id,
        text=text,
        metadata=_metadata("DELL"),
    )
    result = classify_dell_report_internal_chain_r5_package(
        target_id=target_id,
        text=text,
        metadata=_metadata("DELL"),
    )
    assert predecessor["classification"] == "complete_bounded_target_package"
    assert result["classification"] != "complete_bounded_target_package"


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA partnered for delivery; no capacity allocation was disclosed.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity, not previously disclosed, was allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield rate was 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield rate was 80%, and will reach 90% in 2027.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "HBM supply capacity was allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell was not alone when it shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell said it shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
    ],
)
def test_R5_positive_roles_remain_complete(target_id: str, text: str) -> None:
    result = classify_dell_report_internal_chain_r5_package(
        target_id=target_id,
        text=text,
        metadata=_metadata("DELL"),
    )
    assert result["classification"] == "complete_bounded_target_package"


def test_R5_assigns_positions_before_identical_sentence_deduplication() -> None:
    source_id = "SRC::RAW-POSITION-ASP"
    price = "Dell quoted a configuration price of $15."
    noise = "Administrative sentence."
    configuration = (
        "The two Dell PowerEdge XE9680 AI servers are configured systems."
    )
    source_rows = [
        _source(
            source_id,
            " ".join([price, *([noise] * 20), configuration]),
            "DELL",
        )
    ]
    predecessor = assess_dell_report_internal_chain_r4_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=source_rows,
        object_rows=[],
    )
    result = assess_dell_report_internal_chain_r5_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=source_rows,
        object_rows=[],
    )
    assert predecessor["source_packages"][0]["classification"] == (
        "complete_bounded_target_package"
    )
    assert result["source_packages"][0]["classification"] != (
        "complete_bounded_target_package"
    )


def test_R5_preserves_true_bounded_raw_occurrence_adjacency() -> None:
    source_id = "SRC::BOUNDED-RAW-POSITION-ASP"
    text = " ".join(
        [
            "Dell quoted a configuration price of $15.",
            *(["Administrative sentence."] * 5),
            "The two Dell PowerEdge XE9680 AI servers are configured systems.",
        ]
    )
    result = assess_dell_report_internal_chain_r5_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=[_source(source_id, text, "DELL")],
        object_rows=[],
    )
    package = result["source_packages"][0]
    assert package["classification"] == "complete_bounded_target_package"
    assert package["window_unit_span"] == 7


def test_R5_typed_anchors_exclude_product_code_digits() -> None:
    anchors = _typed_material_anchors(
        "NVIDIA H100 and Dell XE9680 systems were discussed in Q1 FY2026."
    )
    assert "number:100" not in anchors
    assert "number:9680" not in anchors
    assert "quarter:1" in anchors
    assert "fiscal_year:2026" in anchors


def test_R5_numeric_anchor_15_is_not_covered_by_150() -> None:
    source_id = "SRC::EXACT-NUMERIC-ANCHOR"
    source_text = (
        "Dell quoted a configuration price of $15 for one Dell PowerEdge "
        "XE9680 AI server."
    )
    compiled_text = (
        "Dell quoted a configuration price of $150 for one Dell PowerEdge "
        "XE9680 AI server."
    )
    result = assess_dell_report_internal_chain_r5_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=[_source(source_id, source_text, "DELL")],
        object_rows=[
            _object("COBJ::ANCHOR-150", source_id, compiled_text, ticker="DELL")
        ],
    )
    assert result["coverage_gap_canonical_family_claim_count"] == 1
    assert "currency_usd:15" in result["coverage_gaps"][0][
        "material_anchors"
    ]


def test_R5_exact_typed_anchor_is_covered() -> None:
    source_id = "SRC::EXACT-TYPED-COVERAGE"
    text = (
        "Dell quoted a configuration price of $15 for one Dell PowerEdge "
        "XE9680 AI server."
    )
    result = assess_dell_report_internal_chain_r5_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=[_source(source_id, text, "DELL")],
        object_rows=[_object("COBJ::ANCHOR-15", source_id, text, ticker="DELL")],
    )
    assert result["coverage_gap_canonical_family_claim_count"] == 0


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _R5_policy_inputs() -> tuple[dict, dict[str, dict]]:
    refs = {
        "R1_policy": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_0.json",
        "R3_policy": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_2.json",
        "R3_public": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_2.json",
        "R3_private": "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/dell-rsq-03b-internal-chain-r3/full_result.json",
        "R3_fresh_audit": "configs/audits/fin_ia_0_1_3_commit_28158e04_dell_03b_r3_fresh_audit_fail_v1_0.json",
        "R4_policy": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_3.json",
        "R4_public": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_3.json",
        "R4_private": "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/dell-rsq-03b-internal-chain-r4/full_result.json",
        "R4_fresh_audit": "configs/audits/fin_ia_0_1_3_commit_3629272c_dell_03b_r4_fresh_dual_audit_fail_v1_0.json",
        "R4_audit_correction": "configs/audits/fin_ia_0_1_3_dell_03b_r4_audit_public_digest_correction_v1_0.json",
        "R39_repair_result": "configs/retrieval/fin_ia_0_1_3_s1_abbreviation_claim_repair_successor_result_v1_0.json",
        "R39_embedding_result": "configs/retrieval/fin_ia_0_1_3_s1c_qwen_embedding_cache_successor_result_v1_3.json",
        "R39_route_policy": "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_6.json",
        "R39_hybrid_policy": "configs/retrieval/fin_ia_0_1_3_s1c_hybrid_candidate_runtime_policy_v1_9.json",
        "runtime_registry": "configs/runtime/fin_ia_0_1_3_clean_baseline_runtime_resource_registry_v1_0.json",
        "runtime_binding_receipt": "configs/runtime/fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_15.json",
        "residual_program": "configs/retrieval/fin_ia_0_1_3_s1_dell_report_residual_source_ladder_program_v1_1.json",
        "execution_program": "configs/retrieval/fin_ia_0_1_3_s1_dell_proposition_coverage_execution_program_v1_3.json",
        "dell_product_readiness": "configs/retrieval/fin_ia_0_1_3_s1_dell_current_product_readiness_result_v1_7.json",
    }
    assert set(refs) == EXPECTED_BOUND_INPUT_IDS
    values = {
        key: json.loads((ROOT / ref).read_text(encoding="utf-8"))
        for key, ref in refs.items()
    }
    policy = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "status": (
            "same_stage_R5_execution_authorized_after_fresh_R4_audit_failure"
        ),
        "program_id": PROGRAM_ID,
        "attempt_id": ATTEMPT_ID,
        "recorded_at": "2026-08-26",
        "execution_contract": deepcopy(EXECUTION_CONTRACT),
        "semantic_contract": deepcopy(SEMANTIC_CONTRACT),
        "output_contract": {
            "policy_ref": POLICY_REF,
            "private_result_ref": PRIVATE_REF,
            "public_result_ref": PUBLIC_REF,
            "attempt_consumption_receipt_ref": ATTEMPT_RECEIPT_REF,
            "alternate_output_paths_authorized": False,
            "private_public_same_path_authorized": False,
            "exclusive_create_required": True,
            "atomic_pair_with_rollback_required": True,
            "same_attempt_retry_authorized": False,
            "minimum_free_bytes_before_attempt": MIN_FREE_BYTES_BEFORE_ATTEMPT,
        },
        "bound_inputs": {
            key: {"ref": ref, "sha256": _sha(ROOT / ref)}
            for key, ref in refs.items()
        },
        "execution_identity": {
            "branch": BRANCH,
            "implementation_commit": "a" * 40,
            "implementation_tree": "b" * 40,
            "authority_commit_changed_paths": [POLICY_REF],
            "authority_commit_parent_must_equal_implementation_commit": True,
            "HEAD_must_equal_upstream": True,
        },
        "implementation_bindings": [
            {"path": path, "sha256": "c" * 64}
            for path in sorted(EXPECTED_IMPLEMENTATION_PATHS)
        ],
        "TokenBudgetBasis": {
            "node_purpose": "one exact R5 local candidate-chain audit",
            "input_scale": "five requests, 1,888 sources, 34,199 objects",
            "required_outputs": "raw positions, typed coverage and routes",
            "schema_burden": "R4 failure, R39 runtime and zero authority",
            "materiality_quality_risk": "false adjacency, anchors or roles",
            "comparable_run_evidence": "immutable R4 plus failed fresh audit",
            "reasoning_profile": "one local 0.6B batch and deterministic R5",
            "stop_and_truncation": "any identity or authority drift stops",
        },
        "authority": deepcopy(AUTHORITY),
    }
    policy["result_digest"] = canonical_digest(policy)
    return policy, values


def _validate_policy(policy: dict, values: dict[str, dict]) -> dict:
    return validate_dell_report_internal_chain_ceiling_r5_policy(
        policy,
        r1_policy=values["R1_policy"],
        r3_policy=values["R3_policy"],
        r3_public=values["R3_public"],
        r3_private=values["R3_private"],
        r3_fresh_audit=values["R3_fresh_audit"],
        r4_policy=values["R4_policy"],
        r4_public=values["R4_public"],
        r4_private=values["R4_private"],
        r4_fresh_audit=values["R4_fresh_audit"],
        r4_audit_correction=values["R4_audit_correction"],
        r39_repair_result=values["R39_repair_result"],
        r39_embedding_result=values["R39_embedding_result"],
        r39_route_policy=values["R39_route_policy"],
        r39_hybrid_policy=values["R39_hybrid_policy"],
        runtime_registry=values["runtime_registry"],
        runtime_binding_receipt=values["runtime_binding_receipt"],
        residual_program=values["residual_program"],
        execution_program=values["execution_program"],
        dell_product_readiness=values["dell_product_readiness"],
    )


def test_R5_policy_binds_immutable_R4_failure_and_R39_runtime() -> None:
    policy, values = _R5_policy_inputs()
    legacy = _validate_policy(policy, values)
    assert len(legacy["target_contracts"]) == 6


def test_R5_policy_rejects_missing_R4_root_cause() -> None:
    policy, values = _R5_policy_inputs()
    drift = deepcopy(values)
    audit = deepcopy(values["R4_fresh_audit"])
    audit["material_findings"] = [
        row
        for row in audit["material_findings"]
        if row.get("root_cause_id")
        != "RC-S1-077-DELL-03B-dedup-before-position-and-substring-anchor-equivalence"
    ]
    body = dict(audit)
    body.pop("result_digest")
    audit["result_digest"] = canonical_digest(body)
    drift["R4_fresh_audit"] = audit
    with pytest.raises(
        DellReportInternalChainCeilingR5Error,
        match="required_root_causes",
    ):
        _validate_policy(policy, drift)


@pytest.mark.parametrize(
    ("section", "field"),
    (
        ("original_audit", "sha256"),
        ("corrected_binding", "R4_public_sha256"),
    ),
)
def test_R5_policy_rejects_correction_SHA_not_cross_bound_to_policy(
    section: str, field: str
) -> None:
    policy, values = _R5_policy_inputs()
    drift = deepcopy(values)
    correction = deepcopy(values["R4_audit_correction"])
    correction[section][field] = "0" * 64
    body = dict(correction)
    body.pop("result_digest")
    correction["result_digest"] = canonical_digest(body)
    drift["R4_audit_correction"] = correction
    with pytest.raises(
        DellReportInternalChainCeilingR5Error,
        match="R4_audit_correction_invalid",
    ):
        _validate_policy(policy, drift)


def test_R5_disk_capacity_gate_runs_before_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        r5_runner.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=1000, used=900, free=100),
    )
    with pytest.raises(RuntimeError, match="minimum_free_disk_capacity"):
        r5_runner._require_output_disk_capacity()

    monkeypatch.setattr(
        r5_runner.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(
            total=MIN_FREE_BYTES_BEFORE_ATTEMPT * 2,
            used=MIN_FREE_BYTES_BEFORE_ATTEMPT,
            free=MIN_FREE_BYTES_BEFORE_ATTEMPT,
        ),
    )
    receipt = r5_runner._require_output_disk_capacity()
    assert receipt["minimum_free_bytes"] == MIN_FREE_BYTES_BEFORE_ATTEMPT
