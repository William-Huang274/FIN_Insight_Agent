from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/eval_multi_agent/run_p33_humanmade_gold_set_matrix_audit.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("p33_humanmade_gold_set_matrix_audit", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_matrix_audit_covers_full_humanmade_gold_set():
    runner = _load_runner()
    spec = runner.load_json(runner.DEFAULT_SPEC_PATH)
    exemplars = runner.load_json(runner.DEFAULT_EXEMPLARS_PATH)
    artifact_audit = runner.load_json(runner.DEFAULT_ARTIFACT_AUDIT_PATH)

    audit = runner.build_matrix_audit(spec, exemplars, artifact_audit)

    assert audit["status"] == "no_paid_matrix_audit_completed_findings_open"
    assert audit["scope"]["deep_gold_case_count"] == 1
    assert audit["scope"]["rubric_gold_case_count"] == 8
    assert audit["scope"]["negative_gold_case_count"] == 6
    assert len(audit["case_results"]) == 15
    assert "paid_llm" in audit["scope"]["not_run"]
    assert "full_chain" in audit["scope"]["not_run"]
    assert "model_comparison" in audit["scope"]["not_run"]


def test_matrix_audit_preserves_storyline_and_known_failure_modes():
    runner = _load_runner()
    spec = runner.load_json(runner.DEFAULT_SPEC_PATH)
    exemplars = runner.load_json(runner.DEFAULT_EXEMPLARS_PATH)
    artifact_audit = runner.load_json(runner.DEFAULT_ARTIFACT_AUDIT_PATH)

    audit = runner.build_matrix_audit(spec, exemplars, artifact_audit)
    rows = {row["case_id"]: row for row in audit["case_results"]}

    assert len(audit["story_chapters"]) >= 5
    assert rows["ai_semis_dell_nvda_anchor_v0_1"]["status"] == "artifact_backed_fail_for_gold_depth"
    assert (
        rows["negative_available_evidence_not_used_v0_1"]["status"]
        == "open_guard_needed_old_memo_showed_symptom"
    )
    assert (
        rows["negative_demand_pool_not_supplier_allocation_v0_1"]["status"]
        == "partial_guard_present_needs_machine_check"
    )
    assert audit["next_repair_order"][0].startswith("Implement artifact-backed HumanmadeGoldSetAudit")
