from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.case_service import CaseService
from apps.workbench.backend.application.execution_service import VT1_WORK_UNIT_TYPE
from apps.workbench.backend.application.research_runtime import FIN01_DETERMINISTIC_PROFILE_REF
from sec_agent.canonical_runtime.models import canonical_digest


TENANT_ID = "tenant-fin01-t02"
PROJECT_ID = "project-fin01-t02"
ACTOR_ID = "analyst-fin01-t02"
PERMISSIONS = ",".join(
    (
        "case:create",
        "case:read",
        "planning:write",
        "planning:review",
        "planning:read",
        "execution:write",
        "execution:read",
        "activity:read",
        "evidence:read",
    )
)
BUSINESS_TABLES = (
    "canonical_research_cases",
    "canonical_case_control_versions",
    "canonical_decision_surface_contract_versions",
    "canonical_decision_surface_cell_versions",
    "canonical_evidence_slot_versions",
    "canonical_compile_gap_versions",
    "canonical_planning_checkpoint_versions",
)


class DeterministicPreviewSpy:
    def __init__(self, facade: Any, *, fail: bool = False):
        self._facade = facade
        self._fail = fail
        self.calls: list[dict[str, Any]] = []

    def analysis_preview(self, case_id: str, principal: Any) -> dict[str, Any]:
        work_unit = self._facade.store.list_latest("canonical_work_units", case_id=case_id)[0]
        attempt = self._facade.store.list_latest("canonical_attempts", case_id=case_id)[0]
        research_run = self._facade.store.list_latest(
            "canonical_research_run_versions", case_id=case_id
        )[0]
        self.calls.append(
            {
                "case_id": case_id,
                "work_unit_state": work_unit["state"],
                "attempt_state": attempt["state"],
                "research_run_state": research_run["state"],
                "principal": principal,
            }
        )
        if self._fail:
            raise RuntimeError("bounded deterministic failure fixture")
        return {
            "analysis_digest": canonical_digest({"case_id": case_id, "fixture": "t02"}),
            "case_id": case_id,
            "case_version": 1,
            "as_of": "2026-07-19T00:00:00Z",
            "source_preview_digest": canonical_digest({"case_id": case_id, "source": "fixture"}),
            "analysis_mode": "bounded_local_deterministic_preview",
            "status": "internal_analysis_preview_ready",
            "numeric": {
                "status": "exact_local_facts_computed",
                "writer_citable": False,
                "typed_gaps": [],
                "derived_metrics": [],
                "facts": [
                    {
                        "candidate_id": "t02-spy-nvda-revenue",
                        "entity_ref": "NVDA",
                        "segment_ref": "__company_total__",
                        "metric_family": "revenue",
                        "label": "Revenues",
                        "row_label": "Revenues",
                        "value": "130497000000",
                        "unit": "USD",
                        "currency": "USD",
                        "scale_multiplier": 1,
                        "period": "FY2025-FY",
                        "source_ref": "fixture_evidence:t02:revenue",
                        "source_coordinate": "fixture_table:revenue",
                        "exact_value_authority": True,
                    },
                    {
                        "candidate_id": "t02-spy-nvda-gross-profit",
                        "entity_ref": "NVDA",
                        "segment_ref": "__company_total__",
                        "metric_family": "gross_profit",
                        "label": "Gross Profit",
                        "row_label": "Gross Profit",
                        "value": "97858000000",
                        "unit": "USD",
                        "currency": "USD",
                        "scale_multiplier": 1,
                        "period": "FY2025-FY",
                        "source_ref": "fixture_evidence:t02:gross_profit",
                        "source_coordinate": "fixture_table:gross_profit",
                        "exact_value_authority": True,
                    },
                    {
                        "candidate_id": "t02-spy-nvda-operating-income",
                        "entity_ref": "NVDA",
                        "segment_ref": "__company_total__",
                        "metric_family": "operating_income",
                        "label": "Operating Income (Loss)",
                        "row_label": "Operating Income (Loss)",
                        "value": "81453000000",
                        "unit": "USD",
                        "currency": "USD",
                        "scale_multiplier": 1,
                        "period": "FY2025-FY",
                        "source_ref": "fixture_evidence:t02:operating_income",
                        "source_coordinate": "fixture_table:operating_income",
                        "exact_value_authority": True,
                    },
                ],
            },
            "repairs": [],
            "judgments": [],
            "workpaper": {},
            "writer": {},
            "execution_counts": {
                "research_graph_queries": 1,
                "network_calls": 0,
                "model_calls": 0,
                "provider_calls": 0,
                "external_tool_calls": 0,
            },
            "hard_boundaries": {
                "case_mutations": 0,
                "canonical_store_writes": 0,
                "evidence_promotions": 0,
                "writer_source_access_calls": 0,
                "network_calls": 0,
                "model_calls": 0,
                "release_admission": 0,
                "senior_r2_required": 1,
            },
            "boundary": "T02 deterministic fixture; no business mutation or release admission.",
        }


def _headers() -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": PERMISSIONS,
    }


def _accepted_case(client: TestClient, *, key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    created = client.post(
        "/api/v1/cases",
        headers=_headers(),
        json={
            "query": "Execute the FIN 0.1 deterministic research path",
            "as_of": "2026-07-19T00:00:00Z",
            "language": "en",
            "source_policy_ref": "fixture:internal-only",
            "idempotency_key": f"{key}-case",
        },
    )
    assert created.status_code == 202, created.text
    case = created.json()
    compiled = client.post(
        f"/api/v1/cases/{case['case_id']}/planning/compile",
        headers=_headers(),
        json={
            "expected_case_version": case["case_version"],
            "expected_summary_version": case["summary_version"],
            "compiler_policy_ref": "fixture:p36-three-cell-v1",
            "pack_selection_ref": "fixture:p36-ai-infrastructure-v1",
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-compile",
        },
    )
    assert compiled.status_code == 202, compiled.text
    plan = compiled.json()
    accepted = client.post(
        f"/api/v1/cases/{case['case_id']}/planning/checkpoint",
        headers=_headers(),
        json={
            "decision": "accept",
            "expected_case_version": case["case_version"],
            "expected_decision_surface_contract_version": plan["contract_version"],
            "expected_checkpoint_version": plan["checkpoint_version"],
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-accept",
        },
    )
    assert accepted.status_code == 202, accepted.text
    return case, accepted.json()


def _create_work_unit(client: TestClient, case: dict[str, Any], plan: dict[str, Any], *, key: str):
    return client.post(
        f"/api/v1/cases/{case['case_id']}/work-units",
        headers=_headers(),
        json={
            "work_unit_type": VT1_WORK_UNIT_TYPE,
            "expected_case_version": case["case_version"],
            "input_head_digest": canonical_digest((plan["contract_version_id"],)),
            "actor_ref": ACTOR_ID,
            "idempotency_key": key,
        },
    )


def _business_snapshot(facade: Any) -> dict[str, list[dict[str, Any]]]:
    return {table: list(facade.store.list_versions(table)) for table in BUSINESS_TABLES}


def test_http_202_dispatches_deterministic_profile_through_exact_run_lineage(tmp_path: Path) -> None:
    fixture_root = tmp_path / "canonical-runtime"
    case_service = CaseService.for_fixture_root(fixture_root, repo_root=REPO_ROOT)
    spy = DeterministicPreviewSpy(case_service._facade)
    completed_commands = []
    complete_research_run = case_service._facade.complete_research_run

    def record_completion(command: Any):
        completed_commands.append(command)
        return complete_research_run(command)

    case_service._facade.complete_research_run = record_completion
    app = create_app(
        tmp_path / "workbench.sqlite",
        p02_case_service=case_service,
        p36_local_research_service=spy,
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="success")
        business_before = _business_snapshot(case_service._facade)
        response = _create_work_unit(client, case, plan, key="success-execute")
        assert response.status_code == 202, response.text
        assert response.json()["work_units"][0]["state"] == "pending"
        listed = client.get(
            f"/api/v1/cases/{case['case_id']}/work-units", headers=_headers()
        )
    assert listed.status_code == 200
    assert listed.json()["work_units"][0]["state"] == "succeeded"
    assert len(spy.calls) == 1
    assert spy.calls[0]["work_unit_state"] == "running"
    assert spy.calls[0]["attempt_state"] == "running"
    assert spy.calls[0]["research_run_state"] == "running"

    facade = case_service._facade
    work_unit = facade.store.list_latest("canonical_work_units", case_id=case["case_id"])[0]
    attempt = facade.store.list_latest("canonical_attempts", case_id=case["case_id"])[0]
    run_versions = facade.store.list_versions(
        "canonical_research_run_versions", case_id=case["case_id"]
    )
    artifacts = facade.store.list_latest(
        "canonical_artifact_versions", case_id=case["case_id"]
    )
    artifacts_by_type = {row["artifact_type"]: row for row in artifacts}
    artifact = artifacts_by_type["deterministic_research_result"]
    assert len(run_versions) == 2
    started_run, completed_run = run_versions
    assert started_run["research_run_id"] == completed_run["research_run_id"]
    assert started_run["research_run_version_id"].endswith(":v1")
    assert completed_run["research_run_version_id"].endswith(":v2")
    assert completed_run["supersedes_version_id"] == started_run["research_run_version_id"]
    assert completed_run["state"] == work_unit["state"] == attempt["state"] == "succeeded"
    assert started_run["work_unit_id"] == work_unit["work_unit_id"]
    assert started_run["attempt_id"] == attempt["attempt_id"]
    assert started_run["execution_profile_version_ref"] == FIN01_DETERMINISTIC_PROFILE_REF
    assert tuple(started_run["input_refs"]) == tuple(work_unit["input_version_refs"])
    assert started_run["input_refs_digest"] == canonical_digest(tuple(started_run["input_refs"]))
    assert artifact["producer_attempt_id"] == attempt["attempt_id"]
    assert tuple(artifact["input_refs"]) == (
        started_run["research_run_version_id"],
        *tuple(work_unit["input_version_refs"]),
    )
    assert artifact["input_refs_digest"] == canonical_digest(tuple(artifact["input_refs"]))
    assert len(artifacts) == 4
    assert set(attempt["output_refs"]) == {
        row["artifact_version_id"] for row in artifacts
    }
    payload = facade.object_store.get_json(
        artifact["object_key"], expected_digest=artifact["object_digest"]
    )
    assert payload["execution_profile_version_ref"] == FIN01_DETERMINISTIC_PROFILE_REF
    assert payload["adapter_direct_canonical_writes"] == 0
    assert payload["result"]["hard_boundaries"]["case_mutations"] == 0
    run_id = started_run["research_run_id"]
    s3_plan = payload["s3_runtime_plan"]
    assert s3_plan["runtime_family_ref"] == (
        "apps.workbench.backend.application.research_runtime:Fin01ResearchRuntime"
    )
    assert s3_plan["research_run_id"] == run_id
    assert len(s3_plan["cell_branches"]) == 3
    assert {row["research_run_id"] for row in s3_plan["cell_branches"]} == {run_id}
    receipts = payload["s3_context_consumption_receipts"]
    assert len(receipts) == 9
    assert {row["target_node"] for row in receipts} == {
        "research_lead",
        "domain_specialist",
        "evidence_operator",
        "memo_writer",
        "verifier",
    }
    assert all(row["model_calls"] == row["network_calls"] == 0 for row in receipts)

    events = facade.store.list_events(run_id)
    assert [event["sequence_no"] for event in events] == list(range(1, 12))
    assert [event["event_type"] for event in events] == [
        "WORK_UNIT_STARTED",
        "ATTEMPT_STARTED",
        "SCHEDULER_LEASE_ACQUIRED",
        "RESEARCH_RUN_STARTED",
        "ARTIFACT_VERSION_CREATED",
        "ARTIFACT_VERSION_CREATED",
        "ARTIFACT_VERSION_CREATED",
        "ARTIFACT_VERSION_CREATED",
        "RESEARCH_RUN_COMPLETED",
        "ATTEMPT_COMPLETED",
        "WORK_UNIT_COMPLETED",
    ]
    assert all(event["task_run_id"] == run_id for event in events)
    assert all(event["work_unit_id"] == work_unit["work_unit_id"] for event in events)
    assert all(event["attempt_id"] == attempt["attempt_id"] for event in events)
    replay = facade.replay_projection(run_id)
    assert replay["research_runs"][run_id]["state"] == "succeeded"
    assert set(replay["attempts"][attempt["attempt_id"]]["output_refs"]) == {
        row["artifact_version_id"] for row in artifacts
    }
    assert replay["external_call_count"] == 0
    assert _business_snapshot(facade) == business_before
    assert len(completed_commands) == 1
    replayed_completion = complete_research_run(completed_commands[0])
    assert replayed_completion.reused_idempotent_result is True
    assert len(
        facade.store.list_versions(
            "canonical_artifact_versions", case_id=case["case_id"]
        )
    ) == 4


def test_deterministic_profile_failure_is_terminal_without_artifact_or_fallback(tmp_path: Path) -> None:
    fixture_root = tmp_path / "canonical-runtime"
    case_service = CaseService.for_fixture_root(fixture_root, repo_root=REPO_ROOT)
    spy = DeterministicPreviewSpy(case_service._facade, fail=True)
    app = create_app(
        tmp_path / "workbench.sqlite",
        p02_case_service=case_service,
        p36_local_research_service=spy,
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="failure")
        response = _create_work_unit(client, case, plan, key="failure-execute")
        assert response.status_code == 202, response.text
    facade = case_service._facade
    work_unit = facade.store.list_latest("canonical_work_units", case_id=case["case_id"])[0]
    attempt = facade.store.list_latest("canonical_attempts", case_id=case["case_id"])[0]
    research_run = facade.store.list_latest(
        "canonical_research_run_versions", case_id=case["case_id"]
    )[0]
    assert work_unit["state"] == attempt["state"] == research_run["state"] == "failed"
    assert attempt["retryable"] is False
    assert research_run["terminal_reason"] == "deterministic_profile_error:RuntimeError"
    assert facade.store.list_latest("canonical_artifact_versions", case_id=case["case_id"]) == []
    assert facade.store.list_latest("canonical_work_units", case_id=case["case_id"])[0].get(
        "forked_from_work_unit_id"
    ) is None
    events = facade.store.list_events(research_run["research_run_id"])
    assert [event["event_type"] for event in events[-3:]] == [
        "RESEARCH_RUN_FAILED",
        "ATTEMPT_FAILED",
        "WORK_UNIT_FAILED",
    ]
    assert facade.replay_projection(research_run["research_run_id"])["research_runs"][
        research_run["research_run_id"]
    ]["state"] == "failed"


def test_current_materialized_p36_analysis_runs_through_fin01_runtime(tmp_path: Path) -> None:
    fixture_root = tmp_path / "canonical-runtime"
    case_service = CaseService.for_fixture_root(fixture_root, repo_root=REPO_ROOT)
    app = create_app(tmp_path / "workbench.sqlite", p02_case_service=case_service)
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="materialized-p36")
        response = _create_work_unit(client, case, plan, key="materialized-p36-execute")
        assert response.status_code == 202, response.text
    facade = case_service._facade
    artifact = facade.store.list_latest("canonical_artifact_versions", case_id=case["case_id"])[0]
    payload = facade.object_store.get_json(
        artifact["object_key"], expected_digest=artifact["object_digest"]
    )
    preview = payload["result"]
    assert preview["status"] == "internal_analysis_preview_ready"
    assert preview["analysis_mode"] == "bounded_local_deterministic_preview"
    assert preview["hard_boundaries"]["case_mutations"] == 0
    assert preview["hard_boundaries"]["canonical_store_writes"] == 0
    assert preview["execution_counts"]["network_calls"] == 0
    assert preview["execution_counts"]["model_calls"] == 0
    assert len(payload["s3_runtime_plan"]["cell_branches"]) == 3
    assert len(payload["s3_context_consumption_receipts"]) == 9
    assert facade.store.list_latest("canonical_research_run_versions", case_id=case["case_id"])[
        0
    ]["state"] == "succeeded"
