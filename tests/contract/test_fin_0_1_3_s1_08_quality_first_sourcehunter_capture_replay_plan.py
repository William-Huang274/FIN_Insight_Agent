import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_3_s1_08_quality_first_sourcehunter_capture_replay_integrated_upgrade_plan_v1_0.json"
)


def _load_plan() -> dict:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def test_plan_fuses_quality_and_replay_without_authorizing_live() -> None:
    plan = _load_plan()
    assert plan["status"] == "approved_plan_implementation_not_started"
    assert plan["principles"]["quality_before_ranking"] is True
    assert plan["principles"]["replay_is_part_of_each_quality_ticket"] is True
    assert plan["principles"]["planner_gold_visibility"] is False
    assert plan["principles"]["live_calls_authorized_by_this_plan"] == 0
    assert [package["id"] for package in plan["work_packages"]] == [
        "S1-08Q-A",
        "S1-08Q-B",
        "S1-08Q-C",
        "S1-08Q-D",
        "S1-08Q-E",
        "S1-08Q-F",
        "S1-08Q-G",
        "S1-08Q-H",
    ]
    assert all(package["replay_proof"] for package in plan["work_packages"])


def test_plan_preserves_quality_reliability_and_privacy_gates() -> None:
    plan = _load_plan()
    integrity = plan["acceptance_gates"]["replay_and_integrity"]
    quality = plan["acceptance_gates"]["research_source_quality"]
    budget = plan["acceptance_gates"]["proposed_DELL_R2_budget"]

    assert integrity["request_without_terminal_capture"] == 0
    assert integrity["known_navigation_noise_fetches"] == 0
    assert integrity["stale_filing_selected_when_newer_eligible_exists"] == 0
    assert integrity["partial_result_materialization_ratio"] == 1.0
    assert quality["DELL_target_in_pool"] == 1.0
    assert quality["required_slot_recall_at_8"] == 1.0
    assert quality["false_promotion"] == 0
    assert quality["qualified_document_yield_min"] >= 0.5
    assert budget["network_calls_max"] <= 16
    assert budget["model_calls"] == 0
    assert budget["retry_calls"] == 0
    assert plan["replay_corpus"]["portable_sanitized_fixtures"]["hidden_gold_included"] is False
    assert "runtime_contact_plaintext" in plan["replay_corpus"]["restricted_exact_manifest"]["forbidden"]
