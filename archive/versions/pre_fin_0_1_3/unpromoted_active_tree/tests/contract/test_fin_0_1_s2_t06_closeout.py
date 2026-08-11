from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "releases"))

from run_fin_ia_0_1_s2_t06_closeout import T06CloseoutError, assess_t06


def _load(name: str) -> dict:
    return json.loads((ROOT / "configs" / "releases" / name).read_text(encoding="utf-8"))


def _inputs() -> tuple[dict, dict, dict, dict, dict]:
    return (
        _load("fin_ia_0_1_s2_t01_one_cell_bounded_agent_preflight_v1_0.json"),
        _load("fin_ia_0_1_s2_t03_deepseek_segmented_v4_live_validation_result_v1_0.json"),
        _load("fin_ia_0_1_s2_t04_live_artifact_validation_result_v1_0.json"),
        _load("fin_ia_0_1_s2_t05_exact_agent_fallback_review_v1_0.json"),
        _load("fin_ia_0_1_program_release_backlog_v2_0.json"),
    )


def test_t06_closes_s2_with_bounded_material_value_and_no_alpha_claim() -> None:
    result = assess_t06(*_inputs())
    assert result["status"] == "pass_independent_S2_closeout"
    assert result["stage_acceptance"]["S2"].startswith("pass_")
    assert result["stage_acceptance"]["S3"].startswith("ready_pending_")
    assert "not_investment_alpha_or_recommendation_quality" in result["honest_non_claims"]
    assert set(result["new_execution_counts"].values()) == {0}


def test_t06_rejects_missing_owner_material_gain_acceptance() -> None:
    inputs = list(_inputs())
    inputs[3] = deepcopy(inputs[3])
    inputs[3]["owner_product_review"]["material_gain_accepted"] = False
    with pytest.raises(T06CloseoutError, match="t06_t05_owner_acceptance_required"):
        assess_t06(*inputs)


def test_t06_rejects_incomplete_live_agent_artifact_set() -> None:
    inputs = list(_inputs())
    inputs[1] = deepcopy(inputs[1])
    inputs[1]["canonical_terminal_truth"]["artifact_count"] = 8
    with pytest.raises(T06CloseoutError, match="t06_t03_closed_artifact_set_required"):
        assess_t06(*inputs)
