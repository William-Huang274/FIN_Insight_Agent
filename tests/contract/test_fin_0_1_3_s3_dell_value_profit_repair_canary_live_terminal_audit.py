from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


AUDIT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_repair_canary_"
    "live_terminal_and_root_cause_audit_v1_0.json"
)


def _load() -> dict:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def test_terminal_audit_is_canonical_and_preserves_failed_status() -> None:
    audit = _load()
    body = {key: value for key, value in audit.items() if key != "result_digest"}
    assert audit["result_digest"] == canonical_digest(body)
    assert audit["formal_terminal"]["status"] == "failed"
    assert audit["formal_terminal"]["terminal_code"] == (
        "s3_repair_canary_model_numeric_surface_forbidden"
    )
    assert audit["formal_terminal"]["business_artifact_promotion"] is False
    assert audit["provider_observation"]["provider_calls"] == 1
    assert audit["provider_observation"]["model_calls"] == 1
    assert audit["provider_observation"]["retries"] == 0


def test_audit_separates_model_strength_surface_false_positive_and_semantic_failures() -> None:
    audit = _load()
    semantic = audit["captured_output_semantic_audit"]
    assert semantic["accepted_evidence_refs_exact"] == ["E021"]
    assert semantic["evidence_semantics_exact"] is True
    failures = {row["failure_id"]: row for row in audit["failure_expansion"]}
    assert failures["F2_evidence_alias_digits_trigger_generic_numeric_guard"][
        "owner"
    ] == "project_guard_severity_false_positive"
    assert failures["F3_target_cell_changed_flag_false"][
        "blocks_repair_promotion"
    ] is True
    assert failures["F4_price_in_cell_changed_from_cannot_infer_to_mixed"][
        "blocks_repair_promotion"
    ] is True
    assert failures["F6_failed_terminal_points_to_unwritten_validated_output_ref"][
        "raw_output_lost"
    ] is False


def test_counterfactual_is_diagnostic_and_structural_repair_is_selected() -> None:
    audit = _load()
    progression = audit["zero_call_counterfactual_progression"]
    assert progression[0]["next_failure"] == (
        "s3_repair_canary_target_readjudication_invalid"
    )
    assert progression[1]["next_failure"] == (
        "s3_repair_canary_price_in_boundary_invalid"
    )
    assert progression[2]["result"] == "validator_pass"
    disposition = audit["root_cause_disposition"]
    assert disposition["model_can_classify_small_research_semantics"] is True
    assert disposition["model_should_not_own_affected_cell_state_transition"] is True
    assert disposition["deepseek_specific_core_branches_forbidden"] is True
    assert audit["stage_acceptance"]["natural_repair_canary"] is False
    assert audit["stop_and_next"]["automatic_second_model_call"] is False
    assert audit["stop_and_next"]["complete_report_execution"] is False
