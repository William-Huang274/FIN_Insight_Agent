from __future__ import annotations

import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.financial_research_core_unchanged_transfer import (
    FinancialResearchTransferError,
    load_core_unchanged_transfer_policy,
)
from sec_agent.financial_research_source_object_vertical import normalized_sha256


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_mu_nvda_"
    "core_unchanged_transfer_policy_v1_0.json"
)
TRANSFER_RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_mu_nvda_"
    "core_unchanged_transfer_result_v1_0.json"
)
CASE_RESULT_PATHS = {
    "MU": ROOT
    / "configs/releases/fin_ia_0_1_3_s1_mu_financial_source_object_transfer_result_v1_0.json",
    "NVDA": ROOT
    / "configs/releases/fin_ia_0_1_3_s1_nvda_financial_source_object_transfer_result_v1_0.json",
}


def test_transfer_policy_locks_dell_proven_core_and_changes_only_case_surfaces() -> None:
    policy = load_core_unchanged_transfer_policy(POLICY_PATH, repo_root=ROOT)
    assert tuple(row.case_key for row in policy.case_policies) == ("MU", "NVDA")
    assert len(policy.locked_artifacts) == 3
    assert all(
        normalized_sha256(ROOT / row.path) == row.normalized_sha256
        for row in policy.locked_artifacts
    )
    assert policy.expected_core_fingerprint == (
        "94af69dcc875ba285afca587d36622dfa859b092c7a2bf686141c5e43308b458"
    )
    assert policy.hard_boundaries["core_modification_allowed"] is False
    assert all(
        policy.hard_boundaries[key] == 0
        for key in (
            "network",
            "provider",
            "model",
            "embedding",
            "rerank",
            "evidence_promotion",
        )
    )


def test_transfer_queries_do_not_embed_review_target_ids() -> None:
    policy = load_core_unchanged_transfer_policy(POLICY_PATH, repo_root=ROOT)
    for case in policy.case_policies:
        targets_by_lane: dict[str, set[str]] = {}
        for binding in case.reviewed_candidate_bindings:
            targets_by_lane.setdefault(binding.lane_id, set()).add(
                binding.target_id.casefold()
            )
        for lane in case.query_lanes:
            for query in lane.query_texts:
                assert all(
                    target not in query.casefold()
                    for target in targets_by_lane.get(lane.lane_id, set())
                )


def test_locked_artifact_digest_mutation_fails_closed(tmp_path: Path) -> None:
    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    payload["locked_artifacts"][0]["normalized_sha256"] = "0" * 64
    mutated = tmp_path / "mutated-transfer-policy.json"
    mutated.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        FinancialResearchTransferError,
        match="transfer_locked_artifact_digest_mismatch",
    ):
        load_core_unchanged_transfer_policy(mutated, repo_root=ROOT)


def test_transfer_result_and_case_results_are_content_addressed() -> None:
    transfer = json.loads(TRANSFER_RESULT_PATH.read_text(encoding="utf-8"))
    transfer_digest = transfer.pop("result_digest")
    assert canonical_digest(transfer) == transfer_digest
    assert transfer["status"] == "engineering_pass_core_unchanged_transfer"
    assert transfer["locked_artifacts_before"] == transfer["locked_artifacts_after"]
    assert all(value == 0 for value in transfer["observed_calls"].values())
    assert transfer["stage_acceptance"] == {
        "external_supplement_admitted": False,
        "held_out_generalization_admitted": True,
        "locked_core_unchanged": True,
        "model_synthesis_admitted": False,
        "mu_transfer_pass": True,
        "nvda_transfer_pass": True,
        "sparse_dense_rebuild_admitted": False,
        "ticker_specific_core_branch_added": False,
    }
    assert transfer["compatibility_finding"] == {
        "blocking": False,
        "code": "legacy_dell_vertical_executor_namespace",
        "meaning": (
            "The frozen executor retains a DELL-named internal run scope and raw result "
            "schema. Transfer acceptance is case-neutral and is computed by this wrapper; "
            "the legacy labels must be renamed only in a later versioned contract change."
        ),
    }
    summaries = {row["case_key"]: row for row in transfer["case_summaries"]}
    assert set(summaries) == set(CASE_RESULT_PATHS)
    for case_key, path in CASE_RESULT_PATHS.items():
        result = json.loads(path.read_text(encoding="utf-8"))
        digest = result.pop("result_digest")
        assert canonical_digest(result) == digest
        assert summaries[case_key]["result_digest"] == digest
        assert summaries[case_key]["transfer_acceptance"] == "pass"
        assert summaries[case_key]["undeclared_missing_facets"] == []
        assert summaries[case_key]["redundant_declared_gaps"] == []
        assert all(value == 0 for value in result["observed_calls"].values())
        assert "target_content" not in json.dumps(result, ensure_ascii=False)


def test_mu_transfer_preserves_concrete_business_meaning_and_honest_gaps() -> None:
    result = json.loads(CASE_RESULT_PATHS["MU"].read_text(encoding="utf-8"))
    assert result["status"] == "engineering_pass_product_pack_incomplete"
    assert result["observed_counts"] == {
        "candidate_contract_rejections": 0,
        "declared_residual_gaps": 13,
        "qualified_candidates": 24,
        "query_lanes": 24,
        "retrieved_candidate_rows": 256,
        "reviewed_candidate_bindings": 24,
        "reviewed_candidate_misses": 0,
        "source_records": 16,
    }
    qualifications = {
        row["qualification_id"]: row for row in result["candidate_qualifications"]
    }
    assert "ASP 与 bit shipment" in qualifications["mu-pricing-pvm"][
        "business_meaning_zh"
    ]
    assert "押金不是已确认收入或 RPO" in qualifications[
        "mu-cash-customer-deposit"
    ]["content_limitation_zh"]
    gaps = {
        (row["slot_id"], row["facet_id"]): row
        for row in result["declared_residual_gap_business"]
    }
    assert gaps[("capacity_inputs_execution", "advanced_packaging_capacity")][
        "gap_code"
    ] == "commercial_data_gap"
    assert gaps[("demand_volume_quality", "pull_forward_or_digestion")][
        "gap_code"
    ] == "commercial_data_gap"


def test_nvda_transfer_keeps_counterparty_readthrough_separate_from_attribution() -> None:
    result = json.loads(CASE_RESULT_PATHS["NVDA"].read_text(encoding="utf-8"))
    assert result["status"] == "engineering_pass_product_pack_incomplete"
    assert result["observed_counts"] == {
        "candidate_contract_rejections": 0,
        "declared_residual_gaps": 13,
        "qualified_candidates": 26,
        "query_lanes": 26,
        "retrieved_candidate_rows": 262,
        "reviewed_candidate_bindings": 26,
        "reviewed_candidate_misses": 0,
        "source_records": 13,
    }
    qualifications = {
        row["qualification_id"]: row for row in result["candidate_qualifications"]
    }
    assert "无法拆出 NVIDIA GPU 金额" in qualifications["nvda-demand-dell"][
        "content_limitation_zh"
    ]
    assert "四个直接客户" in qualifications["nvda-demand-concentration"][
        "business_meaning_zh"
    ]
    assert "政策冲击的已实现财务后果" in qualifications[
        "nvda-regulatory-loss"
    ]["business_meaning_zh"]
    finding_codes = {row["code"] for row in result["hierarchy_findings"]}
    assert finding_codes == {
        "current_regulatory_parent_missing",
        "metric_object_period_label_ambiguous",
        "source_period_metadata_conflation",
    }
