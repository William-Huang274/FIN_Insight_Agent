from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.canonical_runtime.facade import REPLAY_EVENT_TYPES
from sec_agent.canonical_runtime.schema_export import build_schema_bundle
from sec_agent.canonical_runtime.store import OBJECT_TABLES, SQLiteCanonicalStore


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    REPO_ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_vt3_deliverable_review_trace_contract_v1_0.json"
)


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_vt3_scope_is_a_three_cell_product_vertical_not_point06_owner_closeout() -> None:
    contract = _contract()

    assert contract["status"] == "active_fixture_shadow_internal_development"
    assert contract["current_scope"]["point06_owner_closeout"] == "not_claimed"
    assert contract["consumes"]["active_cell_roles"] == [
        "demand_signal",
        "revenue_capture",
        "thesis_counterevidence",
    ]
    assert "P05.6_P36_10_to_20_cell_calibration" in contract["current_scope"][
        "deferred_execution_points"
    ]
    assert "REL_PROD_001_RG1_operational_vertical" in contract["current_scope"][
        "deferred_execution_points"
    ]


def test_vt3_no_source_composer_and_release_boundaries_are_explicit() -> None:
    contract = _contract()

    assert contract["composer_contract"]["mode"] == "deterministic_no_source_fixture_composer"
    assert set(contract["composer_contract"]["call_counts"].values()) == {0}
    for key in (
        "network_calls",
        "tool_invocations",
        "model_calls",
        "provider_calls",
        "paid_full_chain",
        "writer_model_execution",
        "runtime_promotion",
        "release_evidence",
    ):
        assert contract["hard_boundaries"][key] == 0
    assert contract["hard_boundaries"]["production_cutover"] == "forbidden"


def test_vt3_routes_review_and_trace_bind_exact_artifact_identity() -> None:
    contract = _contract()
    routes = {(row["method"], row["operation"], row["permission"]) for row in contract["routes"]}

    assert routes == {
        ("GET", "getDeliverableHead", "deliverable:read"),
        ("POST", "compileDeliverablePreviewFixture", "deliverable:write"),
        ("POST", "createDeliverableReviewAction", "deliverable_review:decide"),
        ("GET", "getCaseTrace", "trace:read"),
    }
    assert contract["review_contract"]["target_binding"] == [
        "artifact_version_id",
        "artifact_version",
        "content_digest",
        "canonical_presentation_digest",
    ]
    assert contract["trace_contract"]["directions"] == ["claim_to_source", "source_to_claim"]
    assert contract["wire_contract"]["compile_command_fields"] == [
        "expected_workpaper_version",
        "expected_workpaper_content_digest",
        "writer_admission_id",
        "actor_ref",
        "idempotency_key",
    ]
    assert set(contract["wire_contract"]["deliverable_view_fields"]) == {
        "case_id",
        "deliverable_id",
        "artifact_version_id",
        "artifact_version",
        "content_digest",
        "canonical_presentation_digest",
        "status",
        "title",
        "sections",
        "material_claims",
        "renderings",
        "review_actions",
        "hard_boundaries",
    }


def test_vt3_canonical_tables_and_replay_events_exist(tmp_path: Path) -> None:
    expected_tables = {
        "canonical_deliverable_projection_versions",
        "canonical_deliverable_review_action_versions",
        "canonical_artifact_provenance_manifest_versions",
    }
    assert expected_tables.issubset(OBJECT_TABLES)
    assert {
        "DELIVERABLE_PREVIEW_COMPILED",
        "DELIVERABLE_REVIEW_RECORDED",
        "TRACE_MANIFEST_COMPILED",
    }.issubset(REPLAY_EVENT_TYPES)

    db_path = tmp_path / "vt3.sqlite3"
    SQLiteCanonicalStore(db_path)
    with sqlite3.connect(db_path) as connection:
        actual = {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        }
    assert expected_tables.issubset(actual)


def test_vt3_canonical_models_are_schema_exported() -> None:
    schemas = build_schema_bundle()["models"]

    assert {
        "CanonicalPresentationModelVersion",
        "DeliverableReviewActionVersion",
        "ArtifactProvenanceManifestVersion",
    }.issubset(schemas)
