from __future__ import annotations

import sqlite3
from pathlib import Path

from sec_agent.r53_r60_context_graph_skill_registry import (
    REQUIRED_ACTORS,
    REQUIRED_GRAPH_PACKS,
    REQUIRED_MEMORY_TIERS,
    build_s4_gate,
)
from sec_agent.r53_r60_durable_runtime_hil_resource_router import build_p12_gate
from sec_agent.r53_r60_graph_skill_memory_lifecycle import (
    NEGATIVE_PATCH_ID,
    P13_LIFECYCLE_DRILL_TASK_ID,
    P13_TASK_ID,
    build_p13_gate,
    default_p13_paths,
    graph_skill_memory_lifecycle_schema_contract,
)
from sec_agent.r53_r60_runtime_task_spine import json_loads
from sec_agent.r53_r60_retrieval_evidence_spine import build_s3_gate
from test_r53_r60_context_graph_skill_registry import seed_s3_fixture
from test_r53_r60_durable_runtime_hil_resource_router import seed_p12_fixture


def seed_p13_fixture(root: Path) -> None:
    seed_s3_fixture(root)
    assert build_s3_gate(root)["release_decision"] == "S3_L4_scope_pass"
    assert build_s4_gate(root)["release_decision"] == "S4_L4_scope_pass"
    seed_p12_fixture(root)
    assert build_p12_gate(root)["release_decision"] == "P12_L4_scope_pass_runtime_drill_ready"


def test_build_p13_gate_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_p13_fixture(tmp_path)

    summary = build_p13_gate(tmp_path)

    assert summary["release_decision"] == "P13_L4_scope_pass_graph_skill_memory_lifecycle_ready"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["status"] == "pass"
    assert summary["inventory_status"] == "baseline_inventory_ready"
    assert summary["staging_eval_status"] == "stage_eval_guard_pass"
    assert summary["hil_status"] == "human_approval_required_and_recorded"
    assert summary["canary_status"] == "internal_canary_pass"
    assert summary["active_version_status"] == "active_versions_promoted_with_rollback_refs"
    assert summary["contextengine_status"] == "contextengine_policy_ready"
    assert summary["lifecycle_rollout_status"] == "controlled_lifecycle_drill_only"
    assert summary["counts"]["gate_count"] == 12
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["asset_inventory_count"] > 0
    assert summary["counts"]["patch_proposal_count"] == 4
    assert summary["counts"]["blocked_negative_patch_count"] == 1
    assert summary["counts"]["human_approval_count"] == 4
    assert summary["counts"]["canary_count"] == 3
    assert summary["counts"]["promotion_count"] == 3
    assert summary["counts"]["context_policy_count"] >= len(REQUIRED_ACTORS)
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()


def test_p13_inventory_covers_s4_graph_skill_memory_assets(tmp_path: Path) -> None:
    seed_p13_fixture(tmp_path)
    build_p13_gate(tmp_path)
    db_path = default_p13_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        graph_ids = {row[0] for row in conn.execute("select asset_id from capability_asset_inventory_p13 where asset_type = 'graph'").fetchall()}
        skill_count = conn.execute("select count(*) from capability_asset_inventory_p13 where asset_type = 'skill'").fetchone()[0]
        memory_tiers = {
            json_loads(row[0], {}).get("tier")
            for row in conn.execute("select payload_json from capability_asset_inventory_p13 where asset_type = 'memory'").fetchall()
        }

    assert set(graph_skill_memory_lifecycle_schema_contract()["tables"]).issubset(tables)
    assert set(REQUIRED_GRAPH_PACKS).issubset(graph_ids)
    assert skill_count >= 10
    assert set(REQUIRED_MEMORY_TIERS).issubset(memory_tiers)


def test_p13_patch_eval_blocks_negative_and_requires_human_approval(tmp_path: Path) -> None:
    seed_p13_fixture(tmp_path)
    build_p13_gate(tmp_path)
    db_path = default_p13_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        negative_eval = conn.execute("select * from asset_patch_eval_results_p13 where patch_id = ?", (NEGATIVE_PATCH_ID,)).fetchone()
        negative_approval = conn.execute("select * from asset_human_approval_records_p13 where patch_id = ?", (NEGATIVE_PATCH_ID,)).fetchone()
        approved_promotions_without_approval = conn.execute(
            """
            select count(*)
            from asset_promotion_records_p13 p
            left join asset_human_approval_records_p13 h on h.patch_id = p.patch_id and h.decision = 'approved'
            where h.patch_id is null
            """
        ).fetchone()[0]
        rejected_promotion = conn.execute("select count(*) from asset_promotion_records_p13 where patch_id = ?", (NEGATIVE_PATCH_ID,)).fetchone()[0]

    assert negative_eval["decision"] == "blocked"
    assert int(negative_eval["authority_violation_count"]) > 0
    assert negative_approval["decision"] == "rejected"
    assert approved_promotions_without_approval == 0
    assert rejected_promotion == 0


def test_p13_tenant_overlay_canary_promotion_and_invalidation(tmp_path: Path) -> None:
    seed_p13_fixture(tmp_path)
    build_p13_gate(tmp_path)
    db_path = default_p13_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        overlay_bad = conn.execute("select count(*) from tenant_overlay_records_p13 where mutates_global_asset != 0").fetchone()[0]
        canary_bad = conn.execute("select count(*) from asset_canary_runs_p13 where status != 'canary_pass' or fail_count != 0").fetchone()[0]
        active_versions = conn.execute("select * from asset_active_versions_p13").fetchall()
        invalidations = conn.execute("select * from asset_invalidation_records_p13").fetchall()
        negative_invalidation = conn.execute("select * from asset_invalidation_records_p13 where invalidation_reason = 'blocked_by_authority_eval'").fetchone()

    assert overlay_bad == 0
    assert canary_bad == 0
    assert len(active_versions) == 3
    assert all(row["status"] == "active_internal_canary" for row in active_versions)
    assert len(invalidations) >= 4
    assert negative_invalidation["effective_status"] == "candidate_invalidated_no_activation"


def test_p13_contextengine_policy_preserves_exact_refs_and_memory_boundary(tmp_path: Path) -> None:
    seed_p13_fixture(tmp_path)
    build_p13_gate(tmp_path)
    db_path = default_p13_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("select * from contextengine_injection_policy_records_p13").fetchall()
        report = conn.execute("select * from asset_lifecycle_readiness_reports_p13").fetchone()

    assert {row["actor_id"] for row in rows}.issuperset(REQUIRED_ACTORS)
    for row in rows:
        assert json_loads(row["selected_graph_packs_json"], [])
        assert json_loads(row["selected_skill_packs_json"], [])
        assert json_loads(row["selected_memory_packs_json"], [])
        assert row["exact_ref_policy"] == "preserve_exact_refs_not_summaries"
        assert row["memory_fact_authority"] == "memory_not_fact_authority"
    assert json_loads(report["known_gaps_json"], [])
    assert report["lifecycle_rollout_status"] == "controlled_lifecycle_drill_only"


def test_p13_rerun_keeps_projection_stable_and_appends_workpaper_event(tmp_path: Path) -> None:
    seed_p13_fixture(tmp_path)
    first = build_p13_gate(tmp_path)
    second = build_p13_gate(tmp_path)
    db_path = default_p13_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        proposal_count = conn.execute("select count(*) from asset_patch_proposals_p13").fetchone()[0]
        gate_count = conn.execute("select count(*) from asset_lifecycle_gate_results_p13").fetchone()[0]
        event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'graph_skill_memory_lifecycle_ready'",
            (P13_TASK_ID,),
        ).fetchone()[0]
        drill_resume_count = conn.execute(
            "select resume_count from research_tasks where task_id = ?",
            (P13_LIFECYCLE_DRILL_TASK_ID,),
        ).fetchone()[0]

    assert first["release_decision"] == "P13_L4_scope_pass_graph_skill_memory_lifecycle_ready"
    assert second["release_decision"] == "P13_L4_scope_pass_graph_skill_memory_lifecycle_ready"
    assert proposal_count == 4
    assert gate_count == 12
    assert event_count == 2
    assert int(drill_resume_count) >= 1
