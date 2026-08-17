from __future__ import annotations

from pathlib import Path
import sys
import time

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.app import create_app


class _FixtureEvidencePacks:
    result_digest = "a" * 64

    def list_cases(self, principal):  # pragma: no cover - product route not called
        return {"items": []}

    def get_case(self, case_key, principal):  # pragma: no cover
        raise AssertionError("unexpected fixture Evidence Pack call")


def _client(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(
            store_path=tmp_path / "operations.sqlite3",
            current_research_evidence_pack_service=_FixtureEvidencePacks(),
            workbench_runtime_mode="fixture",
            frontend_dist_root=tmp_path / "frontend-not-built",
        )
    )


def test_only_workspace_and_operations_are_canonical_frontends(tmp_path: Path) -> None:
    client = _client(tmp_path)
    workspace = client.get("/workspace")
    operations = client.get("/operations")
    assert workspace.status_code == operations.status_code == 503
    for response in (workspace, operations):
        payload = response.json()
        assert payload["detail"] == "frontend_not_built"
        assert payload["error"]["error_code"] == "frontend_not_built"

    assert client.get("/").url.path == "/workspace"
    assert client.get("/current/report").url.path == "/workspace"
    assert client.get("/next/tasks").url.path == "/workspace"
    assert client.get("/cases/fixture").url.path == "/workspace"
    assert client.get("/legacy").url.path == "/operations"


def test_retired_product_apis_are_gone_with_explicit_replacement(tmp_path: Path) -> None:
    client = _client(tmp_path)
    for path, family in (
        ("/api/r53-r60/tasks", "r53_r60_product_surface"),
        ("/api/v1/current-product/cases/DELL", "fin_0_1_2_current_product"),
        ("/api/v1/cases/fixture", "point02_fixture_case"),
    ):
        response = client.get(path)
        assert response.status_code == 410
        assert response.json()["family"] == family
        assert response.json()["replacement"] == "/api/v1/research-cases"


def test_operations_surface_reads_version_neutral_store_and_runtime(tmp_path: Path) -> None:
    client = _client(tmp_path)
    status = client.get("/api/operations/status")
    assert status.status_code == 200
    payload = status.json()
    assert payload["version"] == "0.1.3"
    assert payload["product_runtime"]["primary_route"] == "/workspace"
    assert payload["product_runtime"]["operator_route"] == "/operations"
    assert payload["product_runtime"]["retired_product_runtime_loaded"] is False
    assert payload["product_runtime"]["readiness"]["status"] == "fixture_injected"
    assert client.get("/api/operations/profiles").json() == {"profiles": []}
    assert client.get("/api/operations/source-bundles").json() == {"bundles": []}
    assert client.get("/api/operations/runs").json() == {"runs": []}
    evals = client.get("/api/operations/evals")
    assert evals.status_code == 200
    assert isinstance(evals.json()["evals"], list)
    document_quality = client.get("/api/operations/s1/complex-document-quality")
    assert document_quality.status_code == 200
    quality_payload = document_quality.json()
    assert quality_payload["product_case_enrollment"] is False
    assert quality_payload["document_quality"]["table_region_count"] == 5
    assert quality_payload["financial_objects"]["cross_page_relation_count"] == 1
    assert quality_payload["coverage_summary"]["true_public_information_gap_count"] == 0
    retrieval_quality = client.get("/api/operations/s1/retrieval-quality")
    assert retrieval_quality.status_code == 200
    retrieval_payload = retrieval_quality.json()
    assert retrieval_payload["summary"]["vs3_vertical_slice_integrated"] is True
    assert retrieval_payload["summary"]["combined_union_positive_atom_count"] == 15
    assert retrieval_payload["summary"]["financial_shortlist_positive_top10_count"] == 15
    assert retrieval_payload["summary"]["financial_shortlist_hard_negative_top10_count"] == 0
    assert retrieval_payload["authority"]["candidate_is_not_evidence"] is True
    assert retrieval_payload["authority"]["s1_qualified_stable"] is False
    supplement_quality = client.get("/api/operations/s1/supplement-quality")
    assert supplement_quality.status_code == 200
    supplement_payload = supplement_quality.json()
    assert supplement_payload["coverage_delta"]["retired_broad_or_legacy_evidence_count"] == 3
    assert supplement_payload["coverage_delta"]["added_capture_bound_claim_count"] == 5
    assert supplement_payload["coverage_delta"]["narrowed_gap_count"] == 1
    assert supplement_payload["coverage_delta"]["closed_gap_count"] == 0
    assert all(row["proposition_ready"] for row in supplement_payload["proposition_rows"])
    assert supplement_payload["authority"]["complete_s1_qualified"] is False


def test_operations_runs_real_smoke_and_current_baseline_eval(tmp_path: Path) -> None:
    client = _client(tmp_path)
    smoke = client.post("/api/operations/runs/smoke", json={})
    assert smoke.status_code == 200
    smoke_id = smoke.json()["job"]["job_id"]
    assert _wait_for_terminal(client, smoke_id) == "completed"

    evaluation = client.post(
        "/api/operations/evals/run",
        json={"eval_id": "active_baseline_import_graph"},
    )
    assert evaluation.status_code == 200
    eval_id = evaluation.json()["job"]["job_id"]
    assert _wait_for_terminal(client, eval_id) == "completed"
    events = client.get(f"/api/operations/runs/{eval_id}/events").json()[
        "events"
    ]
    assert any('"status": "pass"' in row["message"] for row in events)


def test_unmigrated_agent_operations_are_explicitly_unavailable(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    for method, path in (
        ("post", "/api/operations/runs/ask"),
        ("get", "/api/operations/sessions"),
        ("post", "/api/operations/native-checkpoints/resume"),
        ("get", "/api/operations/evals/agent-information-economy"),
    ):
        response = (
            client.post(path, json={}) if method == "post" else client.get(path)
        )
        assert response.status_code == 410
        assert response.json()["reason"] == (
            "operation_not_admitted_in_current_baseline"
        )


def test_retired_service_injection_fails_instead_of_reloading_old_graph(
    tmp_path: Path,
) -> None:
    try:
        create_app(
            store_path=tmp_path / "operations.sqlite3",
            current_research_evidence_pack_service=_FixtureEvidencePacks(),
            p36_local_research_service=object(),
            workbench_runtime_mode="fixture",
        )
    except ValueError as exc:
        assert str(exc) == (
            "retired_product_service_injection_forbidden:"
            "p36_local_research_service"
        )
    else:  # pragma: no cover
        raise AssertionError("retired service injection unexpectedly admitted")


def test_frontend_composition_root_has_no_old_product_consumer() -> None:
    main = (
        ROOT / "apps/workbench/frontend/vite/src/main.tsx"
    ).read_text(encoding="utf-8")
    assert "ResearchWorkspace" in main
    assert "OperationsConsole" in main
    for forbidden in (
        "AppShell",
        "WorkbenchNext",
        "CurrentProductWorkbench",
        "r53",
        "P36",
        "fin_0_1_2",
    ):
        assert forbidden not in main


def _wait_for_terminal(client: TestClient, job_id: str) -> str:
    # The active import-graph eval grows with admitted current modules; keep the
    # product test bounded without assuming it always finishes in five seconds.
    for _ in range(300):
        status = client.get(f"/api/operations/runs/{job_id}/status")
        assert status.status_code == 200
        payload = status.json()
        if payload["is_terminal"]:
            return str(payload["status"])
        time.sleep(0.05)
    raise AssertionError(f"job did not reach terminal state: {job_id}")
