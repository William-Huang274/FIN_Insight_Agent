from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports" / "release_evidence"


def _read(name: str) -> dict:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def test_shadow_senior_review_preserves_human_and_release_boundaries() -> None:
    review = _read("fin_ia_0_1_p36_real_candidate_shadow_senior_r2_v1_0.json")

    assert review["exact_candidate"]["selected_cell_count"] == 10
    assert review["exact_candidate"]["mandatory_family_count"] == 6
    assert review["review_result"]["numeric_reproducibility"].startswith("pass_")
    assert review["review_result"]["exact_human_lead_review"] == "missing"
    assert review["gate_effect"]["RG3_research_outcome"].startswith("blocked_")
    assert review["gate_effect"]["RG4_review_product_value"].startswith("blocked_")
    assert review["gate_effect"]["RG1_vertical_path"] == "not_authorized"
    assert review["gate_effect"]["FIN_0_1_INTERNAL_ALPHA_RELEASED"] is False
    assert review["bounded_follow_up"]["budget"] == "one_review_cycle_only"


def test_human_baseline_protocol_cannot_fabricate_product_value() -> None:
    baseline = _read("fin_ia_0_1_p36_human_task_baseline_protocol_v1_0.json")

    assert baseline["status"] == "product_ui_ready_not_started"
    assert len(baseline["analyst_task"]) == 4
    assert all(
        value is None
        for key, value in baseline["metrics_to_record"].items()
        if key not in {"network_calls", "model_calls", "commercial_data_spend"}
    )
    assert baseline["acceptance_rule"]["follow_up"] == "at_most_one_bounded_cycle"
    assert baseline["hard_boundaries"]["automatic_RG1_authorization"] == 0
    assert baseline["hard_boundaries"]["release_admission"] == 0
