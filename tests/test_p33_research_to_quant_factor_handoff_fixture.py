from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sec_agent.p33_research_to_quant_factor_handoff_fixture import (
    CONTRACT_ID,
    RELEASE_DECISION_PASS,
    build_p33_research_to_quant_factor_handoff_fixture,
    default_p33_research_to_quant_factor_handoff_fixture_paths,
)
from sec_agent.r53_r60_runtime_task_spine import json_loads
from sec_agent.r53_r60_research_to_quant_lab import S9_TASK_ID, default_s9_paths
from test_r53_r60_research_to_quant_lab import seed_s9_fixture


def test_p33_research_to_quant_fixture_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_s9_fixture(tmp_path)

    manifest = build_p33_research_to_quant_factor_handoff_fixture(tmp_path)
    paths = default_p33_research_to_quant_factor_handoff_fixture_paths(tmp_path)

    assert manifest["status"] == "pass"
    assert manifest["contract_id"] == CONTRACT_ID
    assert manifest["release_decision"] == RELEASE_DECISION_PASS
    assert manifest["closeout_level"] == "L4_scope_pass"
    assert manifest["promotion_recommendation"] == "active_registry_ready_runtime_alignment_only"
    assert manifest["gate_fail_count"] == 0
    assert paths.manifest_path.exists()
    assert paths.report_path.exists()


def test_p33_handoff_records_have_l3_input_and_output_contract_fields(tmp_path: Path) -> None:
    seed_s9_fixture(tmp_path)

    manifest = build_p33_research_to_quant_factor_handoff_fixture(tmp_path)
    records = manifest["handoff_records"]
    approved = [row for row in records if row["approved_for_backtest"]]

    assert len(records) == 3
    assert len(approved) == 2
    for row in records:
        inputs = row["input_mapping"]
        assert inputs["judgment_card_ids"]
        assert row["thesis_driver_id"] not in inputs["judgment_card_ids"]
        assert inputs["signal_definition"]
        assert inputs["candidate_feature_refs"]
        assert inputs["point_in_time_data_manifest"]["source_refs"]
        assert inputs["human_approval_policy"]["dataset_build"] == "required"
        assert inputs["human_approval_policy"]["backtest"] == "required"
    for row in approved:
        outputs = row["output_mapping"]
        assert outputs["factor_hypothesis_id"]
        assert outputs["signal_observation_refs"]
        assert outputs["backtest_plan_id"]
        assert outputs["leakage_guard_status"] == "pass"
        assert outputs["human_approval_state"]["factor_hypothesis"] == "approved"
        assert outputs["human_approval_state"]["dataset_build"] == "approved"
        assert outputs["human_approval_state"]["backtest"] == "approved"
        assert outputs["research_experience_record_id"]


def test_p33_judgment_cards_are_first_class_source_backed_rows(tmp_path: Path) -> None:
    seed_s9_fixture(tmp_path)

    manifest = build_p33_research_to_quant_factor_handoff_fixture(tmp_path)

    audit = manifest["judgment_card_audit"]
    assert audit["status"] == "pass"
    assert audit["judgment_card_count"] == 3
    assert audit["referenced_judgment_card_count"] == 3
    assert audit["missing_judgment_card_ids"] == []
    assert audit["malformed_judgment_card_ids"] == []
    assert audit["direct_thesis_id_substitute_count"] == 0


def test_p33_pit_leakage_and_human_approval_fail_closed(tmp_path: Path) -> None:
    seed_s9_fixture(tmp_path)

    manifest = build_p33_research_to_quant_factor_handoff_fixture(tmp_path)

    assert manifest["pit_audit"]["status"] == "pass"
    assert manifest["pit_audit"]["pit_bad"] == 0
    assert manifest["pit_audit"]["backtest_without_passed_leakage"] == 0
    assert manifest["approval_audit"]["status"] == "pass"
    assert manifest["approval_audit"]["blocked_factor_pit_row_count"] == 0
    assert manifest["approval_audit"]["denied_approval_count"] >= 1


def test_p33_blocked_candidate_has_no_backtest_plan_or_trading_path(tmp_path: Path) -> None:
    seed_s9_fixture(tmp_path)

    manifest = build_p33_research_to_quant_factor_handoff_fixture(tmp_path)
    blocked = [row for row in manifest["handoff_records"] if not row["approved_for_backtest"]]

    assert len(blocked) == 1
    outputs = blocked[0]["output_mapping"]
    assert blocked[0]["dataset_plan_status"] == "blocked_no_human_approval"
    assert outputs["blocked_before_backtest_plan"] is True
    assert outputs["backtest_plan_id"] == ""
    assert outputs["leakage_guard_status"] == "blocked_no_human_approval"
    assert outputs["human_approval_state"]["dataset_build"] == "denied"
    assert manifest["advice_audit"]["paper_started_count"] == 0
    assert manifest["advice_audit"]["bad_backtest_advice_count"] == 0


def test_s9_runtime_payload_materializes_p33_handoff_contract(tmp_path: Path) -> None:
    seed_s9_fixture(tmp_path)
    build_p33_research_to_quant_factor_handoff_fixture(tmp_path)
    db_path = default_s9_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        missing_judgment_payload = conn.execute(
            """
            select count(*)
            from factor_hypotheses_s9
            where task_id = ?
              and (
                payload_json not like '%judgment_card_ids%'
                or payload_json not like '%point_in_time_data_manifest%'
                or payload_json not like '%human_approval_policy%'
              )
            """,
            (S9_TASK_ID,),
        ).fetchone()[0]
        approved_without_backtest_plan = conn.execute(
            """
            select count(*)
            from dataset_build_plans_s9
            where task_id = ?
              and status = 'ready_for_leakage_check'
              and payload_json not like '%backtest_plan_id%'
            """,
            (S9_TASK_ID,),
        ).fetchone()[0]
        judgment_rows = conn.execute(
            """
            select judgment_card_id, thesis_driver_id, source_refs_json,
                   authority_boundary, counter_view, failure_view, forbidden_claims_json
            from research_judgment_cards_s9
            where task_id = ?
            """,
            (S9_TASK_ID,),
        ).fetchall()
        factor_rows = conn.execute(
            """
            select thesis_driver_id, payload_json
            from factor_hypotheses_s9
            where task_id = ?
            """,
            (S9_TASK_ID,),
        ).fetchall()

    assert missing_judgment_payload == 0
    assert approved_without_backtest_plan == 0
    judgment_ids = {row["judgment_card_id"] for row in judgment_rows}
    assert len(judgment_ids) == 3
    for row in judgment_rows:
        assert json_loads(row["source_refs_json"], [])
        assert row["authority_boundary"]
        assert row["counter_view"]
        assert row["failure_view"]
        forbidden = set(json_loads(row["forbidden_claims_json"], []))
        assert {"external_investment_advice", "live_trading"}.issubset(forbidden)
    for row in factor_rows:
        payload = json_loads(row["payload_json"], {})
        payload_ids = set(payload["judgment_card_ids"])
        assert payload_ids <= judgment_ids
        assert row["thesis_driver_id"] not in payload_ids
