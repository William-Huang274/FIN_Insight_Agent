from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_numeric_sql_qrels import (  # noqa: E402
    S1InternalNumericSqlQrelsError,
    load_numeric_sql_qrels_policy,
    materialize_numeric_sql_qrels_observation,
    validate_numeric_sql_qrels_observation,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_numeric_sql_qrels_policy_v1_0.json"
)


def _observation() -> dict:
    policy = load_numeric_sql_qrels_policy(POLICY_PATH, repo_root=ROOT)
    result = materialize_numeric_sql_qrels_observation(policy, repo_root=ROOT)
    validate_numeric_sql_qrels_observation(result)
    return result


def test_numeric_qrels_separate_annual_exact_truth_from_current_quarter_freshness() -> None:
    result = _observation()
    assert result["status"] == "annual_exact_route_ready_current_quarter_refresh_blocked"
    assert len(result["qrels"]) == 15
    assert result["observed_calls"] == {
        "network": 0,
        "provider": 0,
        "model": 0,
        "embedding": 0,
        "rerank": 0,
        "evidence_promotion": 0,
    }
    successor = result["observations"]["current_three_case_successor_mart"]
    assert successor["strata"]["latest_available_annual"] == {
        "qrel_count": 9,
        "exact_match_count": 9,
        "typed_freshness_gap_count": 0,
    }
    assert successor["strata"]["current_quarter_product_input"] == {
        "qrel_count": 6,
        "exact_match_count": 0,
        "typed_freshness_gap_count": 6,
    }


def test_legacy_main_mart_is_not_misreported_as_the_current_numeric_authority() -> None:
    result = _observation()
    legacy = result["observations"]["legacy_main_mart"]
    assert result["observations"]["candidate_policy_configured_exact_asset"].endswith(
        "gold_fact_signal_mart_v0_1.sqlite"
    )
    assert legacy["strata"]["latest_available_annual"]["exact_match_count"] == 3
    assert legacy["strata"]["latest_available_annual"]["typed_freshness_gap_count"] == 6
    assert result["gate_decision"]["latest_available_annual_exact_sql_ready"] is True
    assert result["gate_decision"]["current_quarter_exact_sql_ready"] is False
    assert result["gate_decision"]["BGE_fusion_rerank_admitted_by_this_gate"] is False


def test_benchmark_pack_is_evaluator_only_and_cannot_refresh_sqlite(
    tmp_path: Path,
) -> None:
    policy = load_numeric_sql_qrels_policy(POLICY_PATH, repo_root=ROOT)
    mutated = deepcopy(policy)
    mutated["hard_boundaries"]["benchmark_pack_may_refresh_sqlite"] = True
    import json

    temp = tmp_path / "policy.json"
    temp.write_text(json.dumps(mutated), encoding="utf-8")
    with pytest.raises(
        S1InternalNumericSqlQrelsError,
        match="numeric_sql_policy_boundary_invalid",
    ):
        load_numeric_sql_qrels_policy(temp, repo_root=ROOT)


def test_observation_digest_fails_closed_on_mutation() -> None:
    result = _observation()
    mutated = deepcopy(result)
    mutated["gate_decision"]["current_quarter_exact_sql_ready"] = True
    with pytest.raises(
        S1InternalNumericSqlQrelsError,
        match="numeric_sql_observation_digest_invalid",
    ):
        validate_numeric_sql_qrels_observation(mutated)
