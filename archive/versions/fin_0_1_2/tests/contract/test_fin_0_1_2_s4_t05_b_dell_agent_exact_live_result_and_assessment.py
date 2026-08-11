from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.releases.materialize_fin_ia_0_1_2_s4_t05_b_dell_agent_exact_live_result_and_assessment import (  # noqa: E402
    DEFAULT_OUTPUT,
    T05BDellExactAssessmentError,
    materialize,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


def test_exact_result_is_live_success_with_independent_L1_and_honest_L4_block() -> None:
    result = materialize()
    assert result == json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    assert result["result_digest"] == canonical_digest(
        {key: value for key, value in result.items() if key != "result_digest"}
    )
    assert result["status"] == (
        "exact_live_success_independent_L1_pass_product_L4_blocked"
    )
    assert list(result["execution"].values())[:4] == [
        "deepseek-v4-pro",
        9,
        3,
        9,
    ]
    assert result["execution"]["business_artifacts"] == 9
    assert result["execution"]["input_tokens"] == 57739
    assert result["execution"]["output_tokens"] == 3323
    assert result["execution"]["retry_count"] == 0
    assert result["independent_assessment"]["L1_deterministic_integrity"].startswith(
        "pass"
    )
    assert result["independent_assessment"]["L4_final_delivery"].startswith(
        "fail"
    )
    assert all(
        result["independent_assessment"]["delivery_surface_findings"].values()
    )
    assert result["paired_and_owner_boundary"]["DELL_current_R2"] is False


def test_result_mutation_breaks_content_addressed_record() -> None:
    result = deepcopy(json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8")))
    result["execution"]["input_tokens"] += 1
    assert result["result_digest"] != canonical_digest(
        {key: value for key, value in result.items() if key != "result_digest"}
    )


def test_missing_delivery_surface_finding_cannot_silently_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.releases.materialize_fin_ia_0_1_2_s4_t05_b_dell_agent_exact_live_result_and_assessment as module

    original = module._load

    def changed(path: Path):
        value = original(path)
        if path == module.EXACT_RESULT:
            value = deepcopy(value)
            for artifact in value["artifacts"]:
                if artifact["artifact_type"] == "bounded_agent_report":
                    artifact["payload"]["report"]["limitations_zh_cn"] = [
                        "已本地化限制"
                    ]
        return value

    monkeypatch.setattr(module, "_load", changed)
    with pytest.raises(
        T05BDellExactAssessmentError,
        match="s4_t05_b_expected_delivery_surface_finding_drift",
    ):
        module.materialize()
