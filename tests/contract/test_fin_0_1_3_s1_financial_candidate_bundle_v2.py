from __future__ import annotations

import json
from pathlib import Path

import pytest

from sec_agent.financial_research_candidate_bundle_v2 import (
    FinancialCandidateBundleV2Error,
    load_candidate_bundle_v2_policy,
    project_candidate_bundle_v2,
    validate_candidate_bundle_v2_result,
)


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_financial_"
    "candidate_bundle_v2_policy_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_financial_"
    "candidate_bundle_v2_result_v1_0.json"
)


def _lane(ticker: str = "ASML") -> dict:
    return {
        "lane_id": "fixture_cash",
        "slot_id": "cash_conversion_balance_sheet",
        "asset_id": "financial_objects",
        "evidence_owner_entity_key": "FIXTURE_ISSUER",
        "evidence_owner_ticker": ticker,
        "relationship_direction": "subject_self_disclosure",
    }


def _candidate() -> dict:
    return {
        "asset_id": "financial_objects",
        "target_id": "fixture_metric",
        "source_record_id": "fixture_parent",
        "object_type": "metric",
        "ticker": "ASML",
    }


def _parent(ticker: str = "ASML") -> dict:
    return {
        "evidence_id": "fixture_parent",
        "ticker": ticker,
        "source_url": "https://issuer.example/annual-report",
        "publication_date": "2026-02-01",
        "period_end": "2025-12-31",
        "section": "Financial statements",
        "text": (
            "[TABLE_START id=42 rows=2] Year ended December 31 (€, in millions) | "
            "2024 | 2025 Net cash provided by operating activities | 11,166.2 | "
            "12,658.5 [TABLE_END]"
        ),
    }


def _child(unit: str = "eur_millions") -> dict:
    return {
        "object_id": "fixture_metric",
        "object_type": "metric",
        "source_evidence_id": "fixture_parent",
        "ticker": "ASML",
        "section": "Financial statements",
        "metric_name": "Net cash provided by operating activities",
        "row_label": "Net cash provided by operating activities",
        "column_label": "2025",
        "raw_value": "12,658.5",
        "value": 12658.5,
        "unit": unit,
    }


def _project(*, child: dict | None = None, parent: dict | None = None) -> dict:
    return project_candidate_bundle_v2(
        case_key="ASML",
        research_as_of="2026-08-06",
        reporting_currency="EUR",
        reporting_currency_authority="fixture_case_profile",
        lane=_lane(),
        candidate=_candidate(),
        parent=_parent() if parent is None else parent,
        child=_child() if child is None else child,
    )


def test_policy_freezes_six_case_order_and_zero_call_boundary() -> None:
    policy = load_candidate_bundle_v2_policy(POLICY_PATH, repo_root=ROOT)
    assert tuple(row.case_key for row in policy.case_inputs) == (
        "DELL",
        "MU",
        "NVDA",
        "ORCL",
        "ASML",
        "ANET",
    )
    assert all(policy.hard_boundaries[key] == 0 for key in (
        "network",
        "provider",
        "model",
        "embedding",
        "rerank",
        "evidence_promotion",
    ))


def test_eur_parent_and_eur_child_form_atomic_numeric_bundle() -> None:
    result = _project()
    assert result["terminal_state"] == "bundle_projected"
    authority = result["bundle"]["currency_unit_authority"]
    assert authority["canonical_unit"] == "eur_millions"
    assert authority["status"] == "source_and_child_consistent"
    assert result["bundle"]["table_path"]["table_id"] == "42"
    assert result["bundle"]["candidate_state"] == (
        "bundle_candidate_only_not_evidence"
    )


def test_asml_parent_eur_child_usd_conflict_fails_closed() -> None:
    result = _project(child=_child("usd_millions"))
    assert result["terminal_state"] == "rejected_typed_gap"
    assert result["gap_code"] == "object_context_gap"
    assert "currency_unit_conflict" in result["finding_codes"]
    assert "bundle" not in result


def test_malformed_numeric_child_fails_closed() -> None:
    child = _child()
    child["raw_value"] = "Earnings per share (2024: €19.25)"
    child["value"] = -2024.0
    result = _project(child=child)
    assert result["terminal_state"] == "rejected_typed_gap"
    assert "numeric_cell_parse_invalid" in result["finding_codes"]


def test_wrong_parent_lineage_fails_closed() -> None:
    child = _child()
    child["source_evidence_id"] = "other_parent"
    result = _project(child=child)
    assert result["terminal_state"] == "rejected_typed_gap"
    assert "parent_child_lineage_mismatch" in result["finding_codes"]


def test_missing_table_context_is_object_context_gap() -> None:
    parent = _parent()
    parent["text"] = "No table is present."
    result = _project(parent=parent)
    assert result["terminal_state"] == "rejected_typed_gap"
    assert "table_semantic_path_missing" in result["finding_codes"]


def test_case_currency_authority_is_external_config_not_ticker_branch(
    tmp_path: Path,
) -> None:
    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    payload["case_inputs"][4]["reporting_currency"] = "USD"
    mutated = tmp_path / "bundle-v2-policy.json"
    mutated.write_text(json.dumps(payload), encoding="utf-8")
    # A valid case-profile change is allowed only in a newly frozen policy. The
    # loader still accepts the shape, while immutable upstream digests remain bound.
    loaded = load_candidate_bundle_v2_policy(mutated, repo_root=ROOT)
    assert loaded.case_inputs[4].reporting_currency == "USD"


def test_materialized_result_is_content_addressed_and_blocks_rebuild() -> None:
    if not RESULT_PATH.exists():
        pytest.skip("candidate bundle v2 result not materialized")
    payload = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    validate_candidate_bundle_v2_result(payload)
    assert payload["status"] == (
        "bundle_v2_engineering_pass_fail_closed_current_sources_pending"
    )
    assert payload["stage_acceptance"]["sparse_dense_rebuild_admitted"] is False
    asml = next(row for row in payload["case_results"] if row["case_key"] == "ASML")
    assert asml["finding_counts"]["currency_unit_conflict"] >= 1
    assert asml["observed_counts"]["unsafe_numeric_bundle_admissions"] == 0


def test_invalid_materialized_digest_is_rejected() -> None:
    payload = {
        "schema_version": "wrong",
        "result_digest": "0" * 64,
    }
    with pytest.raises(
        FinancialCandidateBundleV2Error,
        match="bundle_v2_result_digest_invalid",
    ):
        validate_candidate_bundle_v2_result(payload)
