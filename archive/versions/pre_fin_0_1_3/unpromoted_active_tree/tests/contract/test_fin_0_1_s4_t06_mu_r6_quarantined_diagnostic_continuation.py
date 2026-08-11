from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.releases.run_fin_ia_0_1_s4_t06_mu_r6_quarantined_diagnostic_continuation import (
    MAXIMUM_NEW_LIVE_CALLS,
    NUMERIC_PLACEHOLDER,
    QuarantinedCompletionCache,
    _diagnostic_local_numeric_text_capacity_projection,
    _load_R6_seed_interactions,
    _repair_json_output,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    DeepSeekS3ThreeCellNodeExecutor,
)


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_r6_quarantined_diagnostic_"
    "continuation_and_aggregate_defect_surface_decision_v1_0.json"
)
AGGREGATE_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_r6_quarantined_diagnostic_"
    "aggregate_defect_and_proof_strategy_result_v1_0.json"
)


def _numeric_request() -> dict:
    seeded = _load_R6_seed_interactions()
    row = seeded[
        "domain_specialist:value_and_profit_capture:"
        "facts_explanation_and_terminal"
    ]
    return json.loads(row["model_visible_request"][-1]["content"])


def test_decision_is_diagnostic_only_and_non_promotable() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    assert decision["status"] == (
        "authorized_diagnostic_only_non_promotable_collect_all_continuation"
    )
    assert decision["authority"]["formal_R6_status_mutation_authorized"] is False
    assert decision["authority"]["diagnostic_shadow_execution_authorized"] is True
    assert decision["diagnostic_contract"]["maximum_new_live_model_calls"] == 8
    assert decision["diagnostic_contract"]["business_artifact_promotion_allowed"] is False
    assert decision["acceptance_boundary"]["diagnostic_completion_is_formal_T06_pass"] is False


def test_aggregate_result_keeps_formal_boundary_and_avoids_per_fix_live() -> None:
    result = json.loads(AGGREGATE_RESULT.read_text(encoding="utf-8"))
    assert result["status"] == (
        "diagnostic_complete_nine_quarantined_artifacts_not_acceptance_eligible"
    )
    assert result["authority_boundary"]["formal_T06_pass_claimed"] is False
    assert result["execution_summary"]["quarantined_artifacts"] == 9
    assert result["execution_summary"]["new_live_interactions_acquired_and_cached"] == 8
    assert result["decision"]["one_by_one_full_live_required"] is False
    assert result["decision"]["formal_exact_live_remains_fail_fast"] is True
    assert len(result["root_cause_clusters"]) == 4


def test_diagnostic_capacity_projection_is_local_numeric_only() -> None:
    findings: list[dict] = []
    with _diagnostic_local_numeric_text_capacity_projection(findings):
        DeepSeekS3ThreeCellNodeExecutor._validate_segment_narrative_text(
            segment_id="facts_explanation_and_terminal",
            output={
                "fact_layer": [
                    {
                        "statement": (
                            f"exact local clause；{NUMERIC_PLACEHOLDER}"
                        ),
                        "boundary": "bound",
                    }
                ],
                "explanation_layer": ["explain"],
                "remaining_gaps": ["gap"],
            },
            maximum_characters=10,
        )
    assert findings == [
        {
            "repair_code": (
                "local_numeric_rendering_vs_legacy_text_limit_collision"
            ),
            "segment_id": "facts_explanation_and_terminal",
            "field_id": "fact_layer.statement_or_boundary",
            "legacy_maximum_characters": 10,
            "diagnostic_projected_maximum_characters": (
                len(f"exact local clause；{NUMERIC_PLACEHOLDER}")
            ),
            "failing_item_count": 1,
            "provider_narrative_limit_relaxed": False,
            "exact_local_rendering_limit_relaxed": True,
            "acceptance_eligible": False,
        }
    ]


def test_R6_numeric_violation_is_alias_preserving_and_manifested() -> None:
    seeded = _load_R6_seed_interactions()
    row = seeded[
        "domain_specialist:value_and_profit_capture:"
        "facts_explanation_and_terminal"
    ]
    repaired, findings = _repair_json_output(
        stage=(
            "domain_specialist:value_and_profit_capture:"
            "facts_explanation_and_terminal"
        ),
        request=_numeric_request(),
        assistant_output_text=row["assistant_output_text"],
    )
    parsed = json.loads(repaired)
    assert [fact["support_refs"] for fact in parsed["fact_layer"]] == [
        ["N020", "N009", "N004", "N015"],
        ["N007", "N008", "N019", "N010", "N018", "N011"],
        ["N016", "N006", "N005", "N014"],
    ]
    assert all(
        "rendered locally" in fact["statement"]
        for fact in parsed["fact_layer"]
    )
    assert len(findings) == 4
    assert {
        finding["repair_code"] for finding in findings
    } == {
        "numeric_fact_alias_preserving_local_projection",
        "material_numeric_narrative_quarantined",
    }
    assert all(finding["acceptance_eligible"] is False for finding in findings)
    assert all(
        "original_assistant_output_digest" in finding
        and "repaired_assistant_output_digest" in finding
        for finding in findings
    )


def test_cache_replays_R6_without_live_provider_call(tmp_path: Path) -> None:
    seeded = _load_R6_seed_interactions()
    calls = 0

    def forbidden_live(**_: object) -> dict:
        nonlocal calls
        calls += 1
        raise AssertionError("live provider call forbidden")

    cache = QuarantinedCompletionCache(
        output_root=tmp_path,
        seeded=seeded,
        live_completion=forbidden_live,
    )
    row = seeded[
        "domain_specialist:value_and_profit_capture:"
        "facts_explanation_and_terminal"
    ]
    result = cache(
        trace_tags={
            "stage": (
                "domain_specialist:value_and_profit_capture:"
                "facts_explanation_and_terminal"
            )
        },
        messages=row["model_visible_request"],
    )
    assert calls == 0
    assert cache.seed_replay_count == 1
    assert cache.new_live_call_count == 0
    assert json.loads(result["content"])["fact_layer"][0][
        "support_refs"
    ] == ["N020", "N009", "N004", "N015"]
    assert cache.summary()["repair_finding_count"] == 4


def test_cache_enforces_new_live_call_cap(tmp_path: Path) -> None:
    calls = 0

    def live(**kwargs: object) -> dict:
        nonlocal calls
        calls += 1
        return {
            "call_id": f"diagnostic-{calls}",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "status": "ok",
            "finish_reason": "stop",
            "content": "{}",
            "input_tokens": 1,
            "output_tokens": 1,
            "total_tokens": 2,
            "latency_ms": 1,
            "transport_attempt_count": 1,
        }

    cache = QuarantinedCompletionCache(
        output_root=tmp_path,
        seeded={},
        live_completion=live,
        maximum_new_live_calls=1,
    )
    cache(
        trace_tags={"stage": "stage-one"},
        messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "{}"},
        ],
    )
    try:
        cache(
            trace_tags={"stage": "stage-two"},
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "{}"},
            ],
        )
    except RuntimeError as exc:
        assert str(exc) == "diagnostic_new_live_call_cap_exceeded"
    else:
        raise AssertionError("expected diagnostic new-live cap failure")
    assert calls == 1
    assert MAXIMUM_NEW_LIVE_CALLS == 8

    def forbidden_live(**kwargs: object) -> dict:
        raise AssertionError(f"persisted interaction was not replayed: {kwargs}")

    restored = QuarantinedCompletionCache(
        output_root=tmp_path,
        seeded={},
        live_completion=forbidden_live,
        maximum_new_live_calls=1,
    )
    restored(
        trace_tags={"stage": "stage-one"},
        messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "{}"},
        ],
    )
    assert restored.summary()["live_replay_count"] == 1
    assert restored.summary()["new_live_call_count"] == 0
