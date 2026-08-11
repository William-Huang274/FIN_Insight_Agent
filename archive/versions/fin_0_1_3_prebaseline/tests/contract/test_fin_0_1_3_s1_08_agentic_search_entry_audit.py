from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.s1_08_agentic_search_quality_program import (
    S108AgenticSearchQualityError,
    compile_s1_08_entry_audit,
    load_s1_08_policy,
    validate_s1_08_entry_audit,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_agentic_search_quality_evaluation_policy_v1_0.json"


def _load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _inputs() -> dict:
    return {
        "policy": load_s1_08_policy(POLICY),
        "freeze": _load(
            "configs/releases/fin_ia_0_1_3_s2_04_shared_benchmark_evidence_freeze_v1_0.json"
        ),
        "visible_pack": _load(
            "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
        ),
        "hidden_scoring": _load(
            "eval_sets/fin_0_1_3_same_evidence_v1/evaluator_only/hidden_gold_scoring_objects_v1.json"
        ),
        "governed_pack_result": _load(
            "configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0.json"
        ),
        "source_runtime_result": _load(
            "configs/releases/fin_ia_0_1_3_s1_07_current_source_canary_result_v1_3.json"
        ),
    }


def test_entry_audit_blocks_ranking_before_candidate_ceiling() -> None:
    inputs = _inputs()
    result = compile_s1_08_entry_audit(**inputs)
    validate_s1_08_entry_audit(result, policy=inputs["policy"])
    assert result["status"] == "upstream_blocked_candidate_generation_before_ranking"
    assert result["benchmark_binding"]["evidence_items"] == 33
    assert result["benchmark_binding"]["mandatory_evidence_items"] == 32
    assert result["benchmark_binding"]["target_groups"] == 12
    assert result["candidate_ceiling_audit"]["ranking_metrics_admitted"] is False
    assert result["decision"]["reranker_training_or_tuning"] is False
    assert result["decision"]["model_provider_network_calls"] == [0, 0, 0]


def test_policy_threshold_or_gold_visibility_drift_fails_closed(tmp_path: Path) -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    policy["metrics"]["target_in_pool_recall"]["threshold"] = 0.5
    path = tmp_path / "weak-policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(S108AgenticSearchQualityError) as exc:
        load_s1_08_policy(path)
    assert exc.value.code == "s1_08_metric_gate_drift"

    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    policy["query_revision"][
        "gold_expected_insight_or_evidence_ids_visible_to_planner"
    ] = True
    path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(S108AgenticSearchQualityError) as exc:
        load_s1_08_policy(path)
    assert exc.value.code == "s1_08_governance_gate_invalid"


def test_cross_case_target_and_future_source_fail_closed() -> None:
    inputs = _inputs()
    cross_case = deepcopy(inputs)
    cross_case["hidden_scoring"]["cases"][0]["required_insights"][0][
        "evidence_ids"
    ] = ["MU_E01"]
    with pytest.raises(S108AgenticSearchQualityError) as exc:
        compile_s1_08_entry_audit(**cross_case)
    assert exc.value.code == "s1_08_hidden_target_evidence_binding_invalid"

    future = deepcopy(inputs)
    future["visible_pack"]["source_registry"][0]["published_on"] = "2026-08-07"
    with pytest.raises(S108AgenticSearchQualityError) as exc:
        compile_s1_08_entry_audit(**future)
    assert exc.value.code == "s1_08_future_source_invalid"


def test_current_exact_source_match_does_not_bypass_missing_runtime() -> None:
    inputs = _inputs()
    source_runtime = deepcopy(inputs["source_runtime_result"])
    benchmark_url = inputs["visible_pack"]["source_registry"][0]["url"]
    source_runtime["results"]["DELL"]["final_url"] = benchmark_url
    inputs["source_runtime_result"] = source_runtime
    result = compile_s1_08_entry_audit(**inputs)
    assert (
        result["candidate_ceiling_audit"][
            "benchmark_http_source_exact_url_matches"
        ]
        == 1
    )
    codes = {row["code"] for row in result["blockers"]}
    assert "s1_08_current_provider_neutral_search_contract_missing" in codes
    assert "s1_08_query_revision_runtime_missing" in codes
