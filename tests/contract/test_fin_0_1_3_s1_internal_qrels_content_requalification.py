from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_qrels_content_requalification import (  # noqa: E402
    S1InternalQrelsContentRequalificationError,
    build_qrels_content_requalification_packet,
    load_bound_qrels_content_requalification_inputs,
    load_qrels_content_requalification_policy,
    materialize_qrels_content_requalification_packet,
    validate_qrels_content_requalification_packet,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_internal_qrels_content_requalification_policy_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_internal_qrels_content_requalification_packet_v1_0.json"
)


def _policy_and_inputs() -> tuple[dict, dict]:
    policy = load_qrels_content_requalification_policy(POLICY_PATH, repo_root=ROOT)
    inputs = load_bound_qrels_content_requalification_inputs(policy, repo_root=ROOT)
    return policy, inputs


def _preflight() -> dict:
    return {
        "status": "pass",
        "run_scope": "S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH",
        "open_full_chain_blocker_count": 0,
    }


def test_all_eighteen_labels_receive_business_coverage_not_only_a_score() -> None:
    policy, inputs = _policy_and_inputs()
    result = build_qrels_content_requalification_packet(
        policy=policy,
        inputs=inputs,
        project_os_preflight=_preflight(),
    )
    validate_qrels_content_requalification_packet(result)
    summary = result["content_requalification_summary"]
    assert summary == {
        "reviewed_row_count": 18,
        "ranking_label_valid_count": 18,
        "retain_current_candidate_count": 13,
        "replacement_proposal_count": 5,
        "complete_slot_facet_coverage_count": 4,
        "material_partial_slot_coverage_count": 14,
        "typed_gap_count": 0,
        "prior_preview_only_finding_corrected_count": 2,
    }
    assert all(row["business_reason_zh"] for row in result["row_reviews"])
    assert all(row["covered_facets"] for row in result["row_reviews"])
    assert all(
        row["candidate_may_be_promoted_to_evidence"] is False
        for row in result["row_reviews"]
    )


def test_five_cleaner_targets_are_from_each_rows_frozen_pool() -> None:
    policy, inputs = _policy_and_inputs()
    result = build_qrels_content_requalification_packet(
        policy=policy,
        inputs=inputs,
        project_os_preflight=_preflight(),
    )
    replacements = [
        row for row in result["row_reviews"] if row["owner_reconfirmation_required"]
    ]
    assert len(replacements) == 5
    assert {
        row["recommended_candidate"]["source_key"] for row in replacements
    } == {
        "MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04_CLAIM_3A923AB6",
        "8K_EARNINGS::NVDA::000104581026000051::Q1FY27PRHTM::"
        "BLOCK_0003::CHUNK_0001_CLAIM_EBFEA572",
    }
    assert {row["evidence_owner_ticker"] for row in replacements} == {
        "MSFT",
        "NVDA",
    }
    assert all(
        row["recommended_candidate"]["route_id"] == "internal_object_bm25"
        for row in replacements
    )
    nvda = [row for row in replacements if row["evidence_owner_ticker"] == "NVDA"]
    assert all(
        row["recommended_candidate"]["lineage_resolution_method"]
        == "exact_accession_exhibit"
        for row in nvda
    )
    assert all(
        row["recommended_candidate"]["source_url"].endswith("/q1fy27pr.htm")
        for row in nvda
    )


def test_preview_only_nvda_defect_is_corrected_without_hiding_chunk_noise() -> None:
    policy, inputs = _policy_and_inputs()
    result = build_qrels_content_requalification_packet(
        policy=policy,
        inputs=inputs,
        project_os_preflight=_preflight(),
    )
    nvda_supply = [
        row
        for row in result["row_reviews"]
        if row["evidence_owner_ticker"] == "NVDA"
        and row["evidence_slot_id"] == "supply_chain_capacity_and_counterevidence"
    ]
    assert len(nvda_supply) == 2
    assert all(row["ranking_label_valid"] is True for row in nvda_supply)
    assert all(
        row["prior_finding_disposition"]
        == "superseded_preview_only_defect_chunk_relevant_but_low_precision"
        for row in nvda_supply
    )
    assert all("safe_harbor" in row["content_precision_risk"] for row in nvda_supply)


def test_assignment_and_facet_mutations_fail_closed() -> None:
    policy, inputs = _policy_and_inputs()
    missing = deepcopy(policy)
    missing["assignments"] = missing["assignments"][:-1]
    with pytest.raises(
        S1InternalQrelsContentRequalificationError,
        match="qrels_content_assignment_set_mismatch",
    ):
        build_qrels_content_requalification_packet(
            policy=missing,
            inputs=inputs,
            project_os_preflight=_preflight(),
        )

    drift = deepcopy(policy)
    drift["content_profiles"]["nvda_cashflow_single_facet_partial"]["covered_facets"] = [
        "cash flow",
        "export risk",
    ]
    with pytest.raises(
        S1InternalQrelsContentRequalificationError,
        match="qrels_content_facet_partition_invalid",
    ):
        build_qrels_content_requalification_packet(
            policy=drift,
            inputs=inputs,
            project_os_preflight=_preflight(),
        )


def test_unknown_replacement_cannot_escape_frozen_candidate_pool() -> None:
    policy, inputs = _policy_and_inputs()
    mutated = deepcopy(policy)
    mutated["content_profiles"]["msft_ai_infra_partial_replace"][
        "recommended_source_key"
    ] = "UNFROZEN_STANDARD_ANSWER"
    with pytest.raises(
        S1InternalQrelsContentRequalificationError,
        match="qrels_content_replacement_not_in_frozen_pool",
    ):
        build_qrels_content_requalification_packet(
            policy=mutated,
            inputs=inputs,
            project_os_preflight=_preflight(),
        )


def test_parent_8k_url_cannot_be_signed_as_child_claim_replacement() -> None:
    policy, inputs = _policy_and_inputs()
    mutated = deepcopy(inputs)
    changed = False
    for terminal in mutated["candidate_observation"]["route_terminals"]:
        if terminal["case_key"] != "DELL":
            continue
        for candidate in terminal["candidates"]:
            if str(candidate.get("source_key") or "").endswith("CLAIM_EBFEA572"):
                candidate["source_url"] = (
                    "https://www.sec.gov/Archives/edgar/data/1045810/"
                    "000104581026000051/nvda-20260520.htm"
                )
                candidate["lineage_resolution_method"] = "exact_accession"
                body = dict(candidate)
                body.pop("candidate_id", None)
                body.pop("candidate_digest", None)
                digest = canonical_digest(body)
                candidate["candidate_digest"] = digest
                candidate["candidate_id"] = f"internal_candidate_{digest[:24]}"
                changed = True
    assert changed
    with pytest.raises(
        S1InternalQrelsContentRequalificationError,
        match="qrels_content_replacement_lineage_invalid",
    ):
        build_qrels_content_requalification_packet(
            policy=policy,
            inputs=mutated,
            project_os_preflight=_preflight(),
        )


def test_materialized_packet_is_digest_bound_and_stops_before_successor() -> None:
    result = validate_qrels_content_requalification_packet(
        json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    )
    assert result["successor_gate"]["successor_qrels_v1_4_materialization_admitted"] is False
    assert result["preserved_boundaries"]["index_build_executed"] is False
    assert result["preserved_boundaries"]["ranking_executed"] is False
    mutated = deepcopy(result)
    mutated["successor_gate"]["successor_qrels_v1_4_materialization_admitted"] = True
    with pytest.raises(
        S1InternalQrelsContentRequalificationError,
        match="qrels_content_requalification_packet_invalid",
    ):
        validate_qrels_content_requalification_packet(mutated)


def test_real_materializer_keeps_all_calls_zero() -> None:
    policy = load_qrels_content_requalification_policy(POLICY_PATH, repo_root=ROOT)
    result = materialize_qrels_content_requalification_packet(policy, repo_root=ROOT)
    assert all(value == 0 for value in result["observed_calls"].values())
    assert result == json.loads(RESULT_PATH.read_text(encoding="utf-8"))
