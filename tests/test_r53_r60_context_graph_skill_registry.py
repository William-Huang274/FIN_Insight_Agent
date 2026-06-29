from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.r53_r60_context_graph_skill_registry import (
    LIFECYCLE_OPERATIONS,
    REQUIRED_ACTORS,
    REQUIRED_GRAPH_PACKS,
    REQUIRED_MEMORY_TIERS,
    S4_TASK_ID,
    build_s4_gate,
    context_graph_skill_schema_contract,
    default_s4_paths,
)
from sec_agent.r53_r60_retrieval_evidence_spine import build_s3_gate
from test_r53_r60_retrieval_evidence_spine import seed_s3_fixture


def test_build_s4_gate_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_s3_fixture(tmp_path)
    s3_summary = build_s3_gate(tmp_path)
    summary = build_s4_gate(tmp_path)

    assert s3_summary["release_decision"] == "S3_L4_scope_pass"
    assert summary["release_decision"] == "S4_L4_scope_pass"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["counts"]["gate_count"] == 12
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["context_injection_plans"] >= len(REQUIRED_ACTORS)
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()


def test_s4_registries_cover_required_graph_skill_and_memory_assets(tmp_path: Path) -> None:
    seed_s3_fixture(tmp_path)
    build_s3_gate(tmp_path)
    build_s4_gate(tmp_path)
    db_path = default_s4_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        graph_ids = {row[0] for row in conn.execute("select graph_pack_id from graph_pack_registry").fetchall()}
        memory_tiers = {row[0] for row in conn.execute("select tier from memory_pack_registry").fetchall()}
        skill_count = conn.execute("select count(*) from skill_pack_registry").fetchone()[0]
        bad_skill_count = conn.execute(
            """
            select count(*) from skill_pack_registry
            where prompt_digest = '' or forbidden_behaviors_json = '[]' or eval_hooks_json = '[]'
            """
        ).fetchone()[0]

    assert set(REQUIRED_GRAPH_PACKS).issubset(graph_ids)
    assert set(REQUIRED_MEMORY_TIERS).issubset(memory_tiers)
    assert skill_count >= 10
    assert bad_skill_count == 0


def test_s4_context_injection_preserves_exact_refs_and_drops_with_reasons(tmp_path: Path) -> None:
    seed_s3_fixture(tmp_path)
    build_s3_gate(tmp_path)
    build_s4_gate(tmp_path)
    db_path = default_s4_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        artifacts = conn.execute(
            "select * from context_compression_artifacts where task_id = ?",
            (S4_TASK_ID,),
        ).fetchall()
        dropped_missing_reason = conn.execute(
            "select count(*) from context_dropped_refs where task_id = ? and trim(drop_reason) = ''",
            (S4_TASK_ID,),
        ).fetchone()[0]
        dropped_count = conn.execute(
            "select count(*) from context_dropped_refs where task_id = ?",
            (S4_TASK_ID,),
        ).fetchone()[0]

    assert artifacts
    assert sum(int(row["exact_ref_count"]) for row in artifacts) > 0
    for row in artifacts:
        payload = json.loads(row["payload_json"])
        assert all(isinstance(ref, str) for ref in payload["preserved_exact_refs"])
    assert dropped_count > 0
    assert dropped_missing_reason == 0


def test_s4_lead_and_specialists_declare_consumed_pack_refs(tmp_path: Path) -> None:
    seed_s3_fixture(tmp_path)
    build_s3_gate(tmp_path)
    build_s4_gate(tmp_path)
    db_path = default_s4_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "select * from lead_specialist_consumed_pack_refs where task_id = ?",
            (S4_TASK_ID,),
        ).fetchall()
        operations = {row[0] for row in conn.execute("select operation from context_lifecycle_events").fetchall()}

    assert {row["actor_id"] for row in rows}.issuperset(REQUIRED_ACTORS)
    for row in rows:
        assert json.loads(row["graph_pack_refs_json"])
        assert json.loads(row["skill_pack_refs_json"])
        assert json.loads(row["memory_pack_refs_json"])
        assert json.loads(row["evidence_refs_json"])
    assert set(LIFECYCLE_OPERATIONS).issubset(operations)


def test_s4_schema_contract_and_rerun_append_only_runtime(tmp_path: Path) -> None:
    seed_s3_fixture(tmp_path)
    build_s3_gate(tmp_path)
    first = build_s4_gate(tmp_path)
    second = build_s4_gate(tmp_path)
    db_path = default_s4_paths(tmp_path).db_path
    contract = context_graph_skill_schema_contract()

    with sqlite3.connect(db_path) as conn:
        workpaper_events = conn.execute(
            "select count(*) from workpaper_events where task_id = ?",
            (S4_TASK_ID,),
        ).fetchone()[0]
        plan_count = conn.execute(
            "select count(*) from context_injection_plans where task_id = ?",
            (S4_TASK_ID,),
        ).fetchone()[0]

    assert first["release_decision"] == "S4_L4_scope_pass"
    assert second["release_decision"] == "S4_L4_scope_pass"
    assert contract["policy"]["exact_company_fact_refs_are_preserved_not_summarized"] is True
    assert "context_injection_plans" in contract["tables"]
    assert workpaper_events == 2
    assert plan_count == len(REQUIRED_ACTORS)
