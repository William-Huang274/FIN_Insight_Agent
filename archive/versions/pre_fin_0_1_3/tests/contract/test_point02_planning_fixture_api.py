from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from apps.workbench.backend.application.case_service import CaseService
from apps.workbench.backend.app import create_app
from sec_agent.canonical_runtime.models import PlanningCheckpointVersion
from sec_agent.canonical_runtime.store import OBJECT_TABLES, SQLiteCanonicalStore


CONTRACT = json.loads(
    (REPO_ROOT / "configs/releases/point02_p02_4_vertical_contract_increment_v1_0.json").read_text(
        encoding="utf-8"
    )
)


def _headers(
    *,
    tenant: str = "tenant_fixture",
    permissions: str = "case:read,case:create,planning:read,planning:write,planning:review",
) -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": tenant,
        "X-Fin-Case-Project": "project_fixture",
        "X-Fin-Case-Actor": "analyst_fixture",
        "X-Fin-Case-Permissions": permissions,
        "X-Trace-Id": "trace_point02_planning_fixture",
    }


def _client(tmp_path: Path) -> tuple[TestClient, Path]:
    fixture_root = tmp_path / "p02-planning-fixture"
    case_service = CaseService.for_fixture_root(fixture_root, repo_root=REPO_ROOT)
    return (
        TestClient(
            create_app(
                store_path=tmp_path / "workbench.sqlite",
                p02_case_service=case_service,
            )
        ),
        fixture_root,
    )


def _create_case(client: TestClient, *, key: str = "case-create-planning-001") -> dict[str, Any]:
    response = client.post(
        "/api/v1/cases",
        headers=_headers(),
        json={
            "query": "Assess AI infrastructure demand and value capture",
            "as_of": "2026-07-18T00:00:00Z",
            "language": "en",
            "source_policy_ref": "fixture:internal",
            "idempotency_key": key,
        },
    )
    assert response.status_code == 202
    return response.json()


def _compile_payload(*, key: str = "planning-compile-001") -> dict[str, Any]:
    return {
        "expected_case_version": 1,
        "expected_summary_version": 1,
        "compiler_policy_ref": "fixture:p36-three-cell-v1",
        "pack_selection_ref": "fixture:p36-ai-infrastructure-v1",
        "actor_ref": "analyst_fixture",
        "idempotency_key": key,
    }


def _table_counts(db_path: Path) -> dict[str, int]:
    with sqlite3.connect(db_path) as connection:
        tables = [*OBJECT_TABLES, "canonical_events", "canonical_idempotency"]
        return {
            table: int(connection.execute(f"select count(*) from {table}").fetchone()[0])
            for table in tables
        }


def test_compile_projects_exact_three_cell_contract_and_uses_no_execution_tables(tmp_path: Path) -> None:
    client, fixture_root = _client(tmp_path)
    workspace = _create_case(client)
    case_id = workspace["case_id"]

    response = client.post(
        f"/api/v1/cases/{case_id}/planning/compile",
        headers=_headers(),
        json=_compile_payload(),
    )

    assert response.status_code == 202
    view = response.json()
    assert view["case_id"] == case_id
    assert view["contract_version"] == 1
    assert view["contract_version_id"] == f'{view["contract_id"]}:v1'
    assert view["checkpoint_version"] == 1
    assert view["review_status"] == "awaiting_review"
    assert len(view["cells"]) == 3
    for actual, expected in zip(view["cells"], CONTRACT["fixed_cells"], strict=True):
        assert actual["cell_version"] == 1
        assert actual["decision_question"] == expected["decision_question"]
        assert actual["owner"] == expected["owner_role"]
        assert actual["materiality"] == expected["materiality"]
        assert actual["stop_rule"] == expected["stop_rule"]
        assert actual["what_would_change"] == expected["what_would_change"]
        assert len(actual["evidence_slots"]) == 2
        for actual_slot, expected_slot in zip(
            actual["evidence_slots"], expected["evidence_slots"], strict=True
        ):
            assert {
                "evidence_role": actual_slot["evidence_role"],
                "entity_scope": actual_slot["entity_scope"],
                "period_scope": actual_slot["period_scope"],
                "source_policy_ref": actual_slot["source_policy_ref"],
                "required": actual_slot["required"],
            } == expected_slot

    repeated = client.post(
        f"/api/v1/cases/{case_id}/planning/compile",
        headers=_headers(),
        json=_compile_payload(),
    )
    assert repeated.status_code == 202
    assert repeated.json() == view

    counts = _table_counts(fixture_root / "canonical.sqlite")
    assert counts["canonical_decision_surface_contract_versions"] == 1
    assert counts["canonical_decision_surface_cell_versions"] == 3
    assert counts["canonical_evidence_slot_versions"] == 6
    assert counts["canonical_planning_checkpoint_versions"] == 1
    assert counts["canonical_work_units"] == 0
    assert counts["canonical_attempts"] == 0
    assert counts["canonical_artifact_versions"] == 0
    assert len(list((fixture_root / "objects").rglob("*.json"))) == 1

    summary = SQLiteCanonicalStore(fixture_root / "canonical.sqlite").list_latest(
        "canonical_case_control_versions", case_id=case_id
    )[0]
    assert summary["planning_authority"] == "legacy"


def test_revision_preserves_ids_versions_every_child_and_reopens_latest_projection(tmp_path: Path) -> None:
    client, fixture_root = _client(tmp_path)
    case_id = _create_case(client)["case_id"]
    compiled = client.post(
        f"/api/v1/cases/{case_id}/planning/compile",
        headers=_headers(),
        json=_compile_payload(),
    ).json()
    changed_cell = compiled["cells"][0]
    revised_text = "Material digestion persists for three quarters or conversion falls below the fixture threshold."

    response = client.patch(
        f"/api/v1/cases/{case_id}/decision-surface",
        headers=_headers(),
        json={
            "expected_case_version": 1,
            "expected_decision_surface_contract_version": 1,
            "expected_checkpoint_version": 1,
            "changes": [
                {
                    "cell_id": changed_cell["cell_id"],
                    "what_would_change": revised_text,
                }
            ],
            "actor_ref": "analyst_fixture",
            "idempotency_key": "planning-revise-001",
        },
    )

    assert response.status_code == 202
    revised = response.json()
    assert revised["contract_id"] == compiled["contract_id"]
    assert revised["contract_version"] == 2
    assert revised["checkpoint_version"] == 2
    assert revised["review_status"] == "awaiting_review"
    assert [cell["cell_id"] for cell in revised["cells"]] == [
        cell["cell_id"] for cell in compiled["cells"]
    ]
    assert {cell["cell_version"] for cell in revised["cells"]} == {2}
    assert revised["cells"][0]["what_would_change"] == revised_text
    for old_cell, new_cell in zip(compiled["cells"], revised["cells"], strict=True):
        assert [slot["evidence_slot_id"] for slot in new_cell["evidence_slots"]] == [
            slot["evidence_slot_id"] for slot in old_cell["evidence_slots"]
        ]

    store = SQLiteCanonicalStore(fixture_root / "canonical.sqlite")
    assert len(store.list_versions("canonical_decision_surface_contract_versions", case_id=case_id)) == 2
    assert len(store.list_versions("canonical_decision_surface_cell_versions", case_id=case_id)) == 6
    assert len(store.list_versions("canonical_evidence_slot_versions", case_id=case_id)) == 12
    assert len(store.list_versions("canonical_planning_checkpoint_versions", case_id=case_id)) == 2
    prior = store.get_version(
        "canonical_decision_surface_contract_versions",
        compiled["contract_id"],
        1,
    )
    assert prior is not None
    assert prior["contract_version_id"] == compiled["contract_version_id"]

    accepted = client.post(
        f"/api/v1/cases/{case_id}/planning/checkpoint",
        headers=_headers(),
        json={
            "decision": "accept",
            "expected_case_version": 1,
            "expected_decision_surface_contract_version": 2,
            "expected_checkpoint_version": 2,
            "actor_ref": "analyst_fixture",
            "idempotency_key": "planning-accept-001",
        },
    )
    assert accepted.status_code == 202
    assert accepted.json()["review_status"] == "accepted"
    assert accepted.json()["contract_version"] == 2
    assert accepted.json()["checkpoint_version"] == 3
    counts = _table_counts(fixture_root / "canonical.sqlite")
    assert counts["canonical_decision_surface_contract_versions"] == 2
    assert counts["canonical_decision_surface_cell_versions"] == 6
    assert counts["canonical_evidence_slot_versions"] == 12
    assert counts["canonical_planning_checkpoint_versions"] == 3

    reopened = TestClient(
        create_app(
            store_path=tmp_path / "reopened-workbench.sqlite",
            p02_case_service=CaseService.for_fixture_root(fixture_root, repo_root=REPO_ROOT),
        )
    )
    reread = reopened.get(f"/api/v1/cases/{case_id}/decision-surface", headers=_headers())
    assert reread.status_code == 200
    assert reread.json() == accepted.json()


@pytest.mark.parametrize("decision,expected_status", [("accept", "accepted"), ("return", "returned")])
def test_review_decisions_append_only_one_checkpoint_version(
    tmp_path: Path,
    decision: str,
    expected_status: str,
) -> None:
    client, fixture_root = _client(tmp_path)
    case_id = _create_case(client, key=f"case-create-{decision}")["case_id"]
    compiled = client.post(
        f"/api/v1/cases/{case_id}/planning/compile",
        headers=_headers(),
        json=_compile_payload(key=f"planning-compile-{decision}"),
    ).json()
    before = _table_counts(fixture_root / "canonical.sqlite")
    payload = {
        "decision": decision,
        "expected_case_version": 1,
        "expected_decision_surface_contract_version": 1,
        "expected_checkpoint_version": 1,
        "actor_ref": "analyst_fixture",
        "idempotency_key": f"planning-{decision}-001",
    }

    response = client.post(
        f"/api/v1/cases/{case_id}/planning/checkpoint",
        headers=_headers(),
        json=payload,
    )

    assert response.status_code == 202
    assert response.json()["review_status"] == expected_status
    assert response.json()["contract_version"] == compiled["contract_version"]
    assert response.json()["cells"] == compiled["cells"]
    after = _table_counts(fixture_root / "canonical.sqlite")
    changed_object_tables = {
        table for table in OBJECT_TABLES if after[table] != before[table]
    }
    assert changed_object_tables == {"canonical_planning_checkpoint_versions"}
    assert after["canonical_planning_checkpoint_versions"] == before[
        "canonical_planning_checkpoint_versions"
    ] + 1

    repeated = client.post(
        f"/api/v1/cases/{case_id}/planning/checkpoint",
        headers=_headers(),
        json=payload,
    )
    assert repeated.status_code == 202
    assert repeated.json() == response.json()
    assert _table_counts(fixture_root / "canonical.sqlite") == after


def test_stale_permission_and_idempotency_conflicts_have_zero_partial_writes(tmp_path: Path) -> None:
    client, fixture_root = _client(tmp_path)
    case_id = _create_case(client)["case_id"]
    compiled = client.post(
        f"/api/v1/cases/{case_id}/planning/compile",
        headers=_headers(),
        json=_compile_payload(),
    ).json()
    baseline = _table_counts(fixture_root / "canonical.sqlite")
    revision = {
        "expected_case_version": 1,
        "expected_decision_surface_contract_version": 0,
        "expected_checkpoint_version": 1,
        "changes": [
            {
                "cell_id": compiled["cells"][0]["cell_id"],
                "what_would_change": "A stale write must never persist this text.",
            }
        ],
        "actor_ref": "analyst_fixture",
        "idempotency_key": "stale-revision-001",
    }

    stale_revision = client.patch(
        f"/api/v1/cases/{case_id}/decision-surface",
        headers=_headers(),
        json=revision,
    )
    assert stale_revision.status_code == 409
    assert stale_revision.json()["error"]["error_code"] == "version_conflict"
    assert _table_counts(fixture_root / "canonical.sqlite") == baseline

    stale_review = client.post(
        f"/api/v1/cases/{case_id}/planning/checkpoint",
        headers=_headers(),
        json={
            "decision": "return",
            "expected_case_version": 1,
            "expected_decision_surface_contract_version": 1,
            "expected_checkpoint_version": 0,
            "actor_ref": "analyst_fixture",
            "idempotency_key": "stale-review-001",
        },
    )
    assert stale_review.status_code == 409
    assert _table_counts(fixture_root / "canonical.sqlite") == baseline

    denied = client.patch(
        f"/api/v1/cases/{case_id}/decision-surface",
        headers=_headers(permissions="planning:read"),
        json={**revision, "expected_decision_surface_contract_version": 1},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["error_code"] == "permission_denied"
    assert _table_counts(fixture_root / "canonical.sqlite") == baseline

    denied_review = client.post(
        f"/api/v1/cases/{case_id}/planning/checkpoint",
        headers=_headers(permissions="planning:read"),
        json={
            "decision": "accept",
            "expected_case_version": 1,
            "expected_decision_surface_contract_version": 1,
            "expected_checkpoint_version": 1,
            "actor_ref": "analyst_fixture",
            "idempotency_key": "denied-review-001",
        },
    )
    assert denied_review.status_code == 403
    assert denied_review.json()["error"]["error_code"] == "permission_denied"
    assert _table_counts(fixture_root / "canonical.sqlite") == baseline

    denied_read = client.get(
        f"/api/v1/cases/{case_id}/decision-surface",
        headers=_headers(permissions="planning:write"),
    )
    assert denied_read.status_code == 403
    assert denied_read.json()["error"]["error_code"] == "permission_denied"
    assert _table_counts(fixture_root / "canonical.sqlite") == baseline

    idempotency_conflict = client.post(
        f"/api/v1/cases/{case_id}/planning/compile",
        headers=_headers(),
        json={**_compile_payload(), "expected_summary_version": 0},
    )
    assert idempotency_conflict.status_code == 409
    assert idempotency_conflict.json()["error"]["error_code"] == "idempotency_conflict"
    assert _table_counts(fixture_root / "canonical.sqlite") == baseline


def test_checkpoint_parent_trigger_rejects_a_contract_version_from_another_case(tmp_path: Path) -> None:
    client, fixture_root = _client(tmp_path)
    first_case_id = _create_case(client, key="case-parent-first")["case_id"]
    client.post(
        f"/api/v1/cases/{first_case_id}/planning/compile",
        headers=_headers(),
        json=_compile_payload(key="compile-parent-first"),
    )
    second_case_id = _create_case(client, key="case-parent-second")["case_id"]
    store = SQLiteCanonicalStore(fixture_root / "canonical.sqlite")
    first_checkpoint = store.list_latest(
        "canonical_planning_checkpoint_versions", case_id=first_case_id
    )[0]
    forged = PlanningCheckpointVersion.model_validate(
        {
            **first_checkpoint,
            "case_id": second_case_id,
            "checkpoint_id": "checkpoint_cross_case",
            "checkpoint_version_id": "checkpoint_cross_case:v1",
            "checkpoint_version": 1,
        }
    )
    before = _table_counts(fixture_root / "canonical.sqlite")

    with pytest.raises(sqlite3.IntegrityError, match="planning_checkpoint_contract_parent_missing"):
        with store.transaction() as tx:
            tx.insert(
                "canonical_planning_checkpoint_versions",
                forged.checkpoint_id,
                forged.checkpoint_version,
                forged.model_dump(mode="json"),
            )

    assert _table_counts(fixture_root / "canonical.sqlite") == before


def test_runtime_openapi_exposes_the_approved_p02_4_planning_delta(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    document = client.get("/openapi.json").json()
    paths = document["paths"]

    assert paths["/api/v1/cases/{case_id}/planning/compile"]["post"]["operationId"] == (
        "compileDecisionSurface"
    )
    assert paths["/api/v1/cases/{case_id}/decision-surface"]["patch"]["operationId"] == (
        "reviseDecisionSurface"
    )
    assert paths["/api/v1/cases/{case_id}/planning/checkpoint"]["post"]["operationId"] == (
        "reviewPlanningCheckpoint"
    )
    assert paths["/api/v1/cases/{case_id}/decision-surface"]["get"]["operationId"] == (
        "getDecisionSurface"
    )
    schemas = document["components"]["schemas"]
    assert set(schemas["DecisionSurfaceView"]["required"]) >= {
        "case_id",
        "contract_id",
        "contract_version",
        "contract_version_id",
        "checkpoint_version",
        "review_status",
        "cells",
    }
    assert set(schemas["DecisionSurfaceCellView"]["required"]) >= {
        "cell_id",
        "cell_version",
        "decision_question",
        "owner",
        "materiality",
        "stop_rule",
        "what_would_change",
        "evidence_slots",
    }
    assert set(schemas["EvidenceSlotView"]["required"]) >= {
        "evidence_slot_id",
        "evidence_role",
        "entity_scope",
        "period_scope",
        "source_policy_ref",
        "required",
    }
