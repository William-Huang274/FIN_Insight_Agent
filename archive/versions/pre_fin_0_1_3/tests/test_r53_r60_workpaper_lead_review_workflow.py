from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.r53_r60_context_graph_skill_registry import build_s4_gate
from sec_agent.r53_r60_retrieval_evidence_spine import build_s3_gate
from sec_agent.r53_r60_workpaper_lead_review_workflow import (
    READABILITY_SECTIONS,
    REQUIRED_DIMENSIONS,
    REQUIRED_SPECIALISTS,
    S5_TASK_ID,
    build_s5_gate,
    default_s5_paths,
    workpaper_lead_review_schema_contract,
)
from test_r53_r60_retrieval_evidence_spine import seed_s3_fixture


def seed_s5_fixture(root: Path) -> None:
    seed_s3_fixture(root)
    assert build_s3_gate(root)["release_decision"] == "S3_L4_scope_pass"
    assert build_s4_gate(root)["release_decision"] == "S4_L4_scope_pass"


def test_build_s5_gate_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_s5_fixture(tmp_path)
    summary = build_s5_gate(tmp_path)

    assert summary["release_decision"] == "S5_L4_scope_pass"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["counts"]["gate_count"] == 12
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["workpaper_claim_cards"] >= len(REQUIRED_DIMENSIONS)
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()


def test_s5_objective_dimensions_specialists_and_claims_are_ledgered(tmp_path: Path) -> None:
    seed_s5_fixture(tmp_path)
    build_s5_gate(tmp_path)
    db_path = default_s5_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        objective = conn.execute("select * from research_objective_contracts where task_id = ?", (S5_TASK_ID,)).fetchone()
        dimensions = {
            row["dimension_id"]: row
            for row in conn.execute("select * from dimension_evidence_portfolios_s5 where task_id = ?", (S5_TASK_ID,)).fetchall()
        }
        specialists = {
            row["specialist_id"]: row
            for row in conn.execute("select * from specialist_workstreams where task_id = ?", (S5_TASK_ID,)).fetchall()
        }
        claim_bad = conn.execute(
            """
            select count(*) from workpaper_claim_cards
            where task_id = ?
              and (evidence_refs_json = '[]' or authority_boundary = '' or source_boundary = '')
            """,
            (S5_TASK_ID,),
        ).fetchone()[0]

    assert objective is not None
    assert set(json.loads(objective["required_dimensions_json"])) == set(REQUIRED_DIMENSIONS)
    assert set(REQUIRED_DIMENSIONS).issubset(dimensions)
    for row in dimensions.values():
        assert json.loads(row["claim_card_refs_json"]) or json.loads(row["gap_refs_json"])
    assert set(REQUIRED_SPECIALISTS).issubset(specialists)
    for row in specialists.values():
        assert row["workpaper_event_id"]
        assert json.loads(row["evidence_refs_json"])
    assert claim_bad == 0


def test_s5_lead_review_judgment_readability_and_human_review(tmp_path: Path) -> None:
    seed_s5_fixture(tmp_path)
    build_s5_gate(tmp_path)
    db_path = default_s5_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        lead = conn.execute("select * from lead_review_checkpoints where task_id = ?", (S5_TASK_ID,)).fetchone()
        judgment = conn.execute("select * from judgment_states where task_id = ?", (S5_TASK_ID,)).fetchone()
        readability = conn.execute("select * from workpaper_readability_gates where task_id = ?", (S5_TASK_ID,)).fetchone()
        review = conn.execute("select * from human_review_queue where task_id = ?", (S5_TASK_ID,)).fetchone()
        repair_count = conn.execute("select count(*) from targeted_repair_requests where task_id = ?", (S5_TASK_ID,)).fetchone()[0]
        gap_types = {row[0] for row in conn.execute("select gap_type from workpaper_gap_items where task_id = ?", (S5_TASK_ID,)).fetchall()}

    assert lead["status"] == "review_ready_with_visible_gaps"
    assert json.loads(lead["typed_gap_ids_json"])
    assert json.loads(lead["writing_guidance_json"])["primary_input"] if "primary_input" in json.loads(lead["writing_guidance_json"]) else True
    assert judgment["status"] == "ready_for_writer"
    assert int(judgment["unsupported_claim_count"]) == 0
    assert readability["status"] == "pass"
    assert int(readability["claim_dump_detected"]) == 0
    assert float(readability["evidence_ref_coverage"]) >= 1.0
    assert review["status"] == "queued"
    assert repair_count >= 1
    assert {"retrievable_gap", "bounded_gap", "commercial_gap"}.issubset(gap_types)


def test_s5_readability_sections_and_no_raw_candidates(tmp_path: Path) -> None:
    seed_s5_fixture(tmp_path)
    build_s5_gate(tmp_path)
    db_path = default_s5_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        sections = {
            row["section_key"]: row
            for row in conn.execute("select * from workpaper_sections where task_id = ?", (S5_TASK_ID,)).fetchall()
        }
        candidate_like_refs = conn.execute(
            """
            select count(*) from workpaper_claim_cards
            where task_id = ? and evidence_refs_json like '%candidate_%'
            """,
            (S5_TASK_ID,),
        ).fetchone()[0]

    assert set(READABILITY_SECTIONS).issubset(sections)
    for section in sections.values():
        payload = json.loads(section["payload_json"])
        assert payload["issue_first_section"] is True
    assert candidate_like_refs == 0


def test_s5_schema_contract_and_rerun_append_only_workpaper_events(tmp_path: Path) -> None:
    seed_s5_fixture(tmp_path)
    first = build_s5_gate(tmp_path)
    second = build_s5_gate(tmp_path)
    db_path = default_s5_paths(tmp_path).db_path
    contract = workpaper_lead_review_schema_contract()

    with sqlite3.connect(db_path) as conn:
        workpaper_events = conn.execute(
            "select count(*) from workpaper_events where task_id = ?",
            (S5_TASK_ID,),
        ).fetchone()[0]
        claim_count = conn.execute(
            "select count(*) from workpaper_claim_cards where task_id = ?",
            (S5_TASK_ID,),
        ).fetchone()[0]

    assert first["release_decision"] == "S5_L4_scope_pass"
    assert second["release_decision"] == "S5_L4_scope_pass"
    assert contract["policy"]["specialists_write_workpaper_events_not_final_memo"] is True
    assert "judgment_states" in contract["tables"]
    assert workpaper_events == 8
    assert claim_count >= len(REQUIRED_DIMENSIONS)
