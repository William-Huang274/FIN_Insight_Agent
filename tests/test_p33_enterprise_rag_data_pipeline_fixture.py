from __future__ import annotations

import json
from pathlib import Path

from sec_agent.p33_enterprise_rag_data_pipeline_fixture import (
    CONTRACT_ID,
    RELEASE_DECISION_PASS,
    build_p33_enterprise_rag_data_pipeline_fixture,
    default_p33_enterprise_rag_fixture_paths,
)
from test_r53_r60_data_ingestion_retrieval_control_plane import seed_p14_fixture


def test_p33_enterprise_rag_fixture_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_p14_fixture(tmp_path)

    manifest = build_p33_enterprise_rag_data_pipeline_fixture(tmp_path)
    paths = default_p33_enterprise_rag_fixture_paths(tmp_path)

    assert manifest["status"] == "pass"
    assert manifest["release_decision"] == RELEASE_DECISION_PASS
    assert manifest["closeout_level"] == "L4_scope_pass"
    assert manifest["promotion_recommendation"] == "active_registry_ready_runtime_alignment_only"
    assert manifest["absorbed_contract_ids"] == [CONTRACT_ID]
    assert manifest["gate_fail_count"] == 0
    assert all(row["status"] == "pass" for row in manifest["acceptance_gates"])
    assert paths.manifest_path.exists()
    assert paths.report_path.exists()

    written = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
    assert written["contract_id"] == CONTRACT_ID


def test_p33_promoted_evidence_rows_have_required_lineage(tmp_path: Path) -> None:
    seed_p14_fixture(tmp_path)
    manifest = build_p33_enterprise_rag_data_pipeline_fixture(tmp_path)

    evidence_rows = manifest["evidence_rows"]
    assert evidence_rows
    required_fields = {
        "source_id",
        "source_role",
        "raw_artifact_ref",
        "parser_profile",
        "parser_execution_id",
        "chunk_or_table_artifact_ref",
        "retrieval_index_ref",
        "lineage_ref",
        "authority_policy",
        "quality_probe_result",
    }
    for row in evidence_rows:
        assert required_fields.issubset(row)
        assert all(row[field] for field in required_fields)
        assert all(row["lineage_checks"].values())
        assert row["typed_gap_if_failed"] is None

    authority_modes = {row["authority_policy"] for row in evidence_rows}
    assert {"exact_company_fact_authority", "technical_fact_authority", "deployment_signal_authority"}.issubset(
        authority_modes
    )


def test_p33_parser_failure_is_typed_gap_not_public_source_absent(tmp_path: Path) -> None:
    seed_p14_fixture(tmp_path)
    manifest = build_p33_enterprise_rag_data_pipeline_fixture(tmp_path)

    typed_gap = manifest["typed_parser_gap"]
    gap_payload = typed_gap["typed_gap_if_failed"]

    assert typed_gap["parser_status"] == "parser_gap_blocked"
    assert typed_gap["can_enter_context"] is False
    assert typed_gap["can_enter_claim_card"] is False
    assert gap_payload["gap_type"] == "parser_gap"
    assert gap_payload["source_absent"] is False
    assert gap_payload["public_source_absent"] is False
    assert "parser" in gap_payload["next_action"]


def test_p33_milvus_boundary_and_refresh_status_are_visible(tmp_path: Path) -> None:
    seed_p14_fixture(tmp_path)
    manifest = build_p33_enterprise_rag_data_pipeline_fixture(tmp_path)

    milvus_rows = [row for row in manifest["index_refresh_rows"] if row["index_type"] == "milvus_semantic"]
    assert milvus_rows
    assert all(row["milvus_not_exact_authority"] is True for row in milvus_rows)
    assert all(row["refresh_status"] == "refresh_ready" for row in manifest["index_refresh_rows"])
    assert all(row["lineage_complete"] is True for row in manifest["index_refresh_rows"])

    gate_by_id = {row["gate_id"]: row for row in manifest["acceptance_gates"]}
    assert gate_by_id["p33_generic_vector_hit_cannot_override_exact_first_authority"]["status"] == "pass"
    assert gate_by_id["p33_refresh_status_and_quality_probe_visible"]["status"] == "pass"
