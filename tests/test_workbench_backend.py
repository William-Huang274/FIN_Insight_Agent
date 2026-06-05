from __future__ import annotations

import json
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from apps.workbench.backend.app import create_app
from sec_agent.workbench.job_runner import CommandSpec, start_command_job
from sec_agent.workbench.jobs import new_local_smoke_job
from sec_agent.workbench.store import WorkbenchStore


def test_workbench_backend_health() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["frontend"] == "available"
    assert response.headers["x-trace-id"].startswith("trace_")
    assert response.headers["x-elapsed-time-ms"].isdigit()


def test_workbench_backend_system_status_reports_store_and_paths(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    response = client.get("/api/system/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["docker_required"] is False
    assert payload["checks"]["store"] == "ok"
    assert payload["store"]["status"] == "ok"
    assert payload["store"]["db_parent_writable"] is True
    assert payload["store"]["journal_mode"].lower() == "wal"
    assert payload["store"]["schema_version"] >= 3
    assert payload["store"]["migration_count"] >= 3
    assert payload["paths"]["repo_root"]["exists"] is True
    assert payload["runtime_preflight"]["status"] == "ok"
    assert payload["runtime_limits"]["max_active_jobs"] >= 1
    assert payload["path_policy"]["allow_external_paths"] is False
    assert payload["job_recovery"]["status"] == "ok"
    assert isinstance(payload["paths"]["repo_root"]["free_bytes"], int)
    assert "runtime-secret" not in json.dumps(payload, ensure_ascii=False)


def test_workbench_backend_exposes_readiness_preflight_and_contracts(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    live = client.get("/api/health/live")
    ready = client.get("/api/health/ready")
    preflight = client.get("/api/system/runtime/preflight")
    contracts = client.get("/api/system/contracts")

    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["checks"]["runtime_preflight"] == "ok"
    assert preflight.status_code == 200
    assert "fastapi" in {item["name"] for item in preflight.json()["control_plane_modules"]}
    assert contracts.status_code == 200
    assert "interrupted" in contracts.json()["run_statuses"]["terminal"]
    assert contracts.json()["runtime_limits"]["max_active_jobs"] >= 1


def test_workbench_store_concurrent_event_appends_keep_monotonic_sequences(tmp_path: Path) -> None:
    store = WorkbenchStore(tmp_path / "workbench.sqlite")
    job = new_local_smoke_job(job_id="concurrent_fixture", trace_id="trace_concurrent")
    store.upsert_run_job(job)

    def append_event(index: int) -> int:
        event = store.append_run_event(
            "concurrent_fixture",
            stream="stdout",
            message=f"line {index}",
        )
        return event.sequence

    with ThreadPoolExecutor(max_workers=8) as executor:
        sequences = list(executor.map(append_event, range(20)))

    events = store.list_run_events("concurrent_fixture", limit=100)
    assert sorted(sequences) == list(range(1, 21))
    assert [event.sequence for event in events] == list(range(1, 21))
    assert len(events) == 20
    assert {event.trace_id for event in events} == {"trace_concurrent"}
    assert store.inspect_health().run_event_count == 20


def test_workbench_store_backfills_legacy_run_trace_ids_stably(tmp_path: Path) -> None:
    db_path = tmp_path / "workbench.sqlite"
    legacy_payload = {
        "job_id": "legacy_job",
        "job_type": "local_smoke",
        "status": "completed",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        "metadata": {},
    }
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            create table run_jobs (
                job_id text primary key,
                job_type text not null,
                status text not null,
                profile_id text,
                run_dir text,
                payload_json text not null,
                created_at text not null,
                updated_at text not null
            )
            """
        )
        conn.execute(
            """
            create table run_job_events (
                job_id text not null,
                sequence integer not null,
                stream text not null,
                message text not null,
                created_at text not null,
                primary key (job_id, sequence)
            )
            """
        )
        conn.execute(
            """
            insert into run_jobs (job_id, job_type, status, profile_id, run_dir, payload_json, created_at, updated_at)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy_job",
                "local_smoke",
                "completed",
                None,
                None,
                json.dumps(legacy_payload, ensure_ascii=False),
                "2026-01-01T00:00:00",
                "2026-01-01T00:00:00",
            ),
        )
        conn.execute(
            """
            insert into run_job_events (job_id, sequence, stream, message, created_at)
            values (?, ?, ?, ?, ?)
            """,
            ("legacy_job", 1, "system", "legacy event", "2026-01-01T00:00:00"),
        )

    store = WorkbenchStore(db_path)
    first = store.get_run_job("legacy_job")
    second = store.get_run_job("legacy_job")
    summary = store.list_run_jobs()[0]
    event = store.list_run_events("legacy_job")[0]

    assert first is not None
    assert second is not None
    assert first.trace_id == second.trace_id
    assert first.trace_id.startswith("trace_legacy_")
    assert summary.trace_id == first.trace_id
    assert event.trace_id == first.trace_id
    assert store.inspect_health().schema_version >= 3


def test_workbench_backend_marks_stale_active_jobs_on_startup(tmp_path: Path) -> None:
    db_path = tmp_path / "workbench.sqlite"
    store = WorkbenchStore(db_path)
    for job_id, status in (("queued_fixture", "queued"), ("running_fixture", "running")):
        store.upsert_run_job(new_local_smoke_job(job_id=job_id, trace_id=f"trace_{job_id}").model_copy(update={"status": status}))

    client = TestClient(create_app(store_path=db_path))

    queued_status = client.get("/api/runs/queued_fixture/status").json()
    running_status = client.get("/api/runs/running_fixture/status").json()
    system = client.get("/api/system/status").json()
    assert queued_status["status"] == "interrupted"
    assert queued_status["is_terminal"] is True
    assert running_status["status"] == "interrupted"
    assert system["job_recovery"]["interrupted_job_count"] == 2
    messages = [event["message"] for event in client.get("/api/runs/running_fixture/events").json()["events"]]
    assert "workbench service restarted" in messages


def test_workbench_backend_rejects_paths_outside_policy(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))
    outside = tmp_path.parent / f"outside_{tmp_path.name}" / "run"

    inspect_response = client.post("/api/runs/inspect", json={"run_dir": str(outside)})
    data_build_response = client.post(
        "/api/data-build/preview",
        json={
            "step_id": "sec_build_manifest",
            "values": {"output": str(outside / "manifest.jsonl")},
        },
    )

    assert inspect_response.status_code == 400
    assert inspect_response.json()["detail"]["reason"] == "path_not_allowed"
    assert data_build_response.status_code == 400
    assert data_build_response.json()["detail"]["reason"] == "path_not_allowed"


def test_workbench_backend_can_backup_store_inside_allowed_root(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    response = client.post("/api/system/store/backup", json={"backup_dir": str(tmp_path / "backups")})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert Path(payload["backup_path"]).exists()
    assert payload["backup_size_bytes"] > 0


def test_workbench_backend_error_contract_preserves_detail_and_trace(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    response = client.get("/api/profiles/missing_profile", headers={"X-Trace-Id": "trace_test_profile"})

    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"] == "profile_not_found: missing_profile"
    assert payload["error"]["schema_version"] == "finsight_workbench_api_error_v0.1"
    assert payload["error"]["error_code"] == "profile_not_found"
    assert payload["error"]["status_code"] == 404
    assert payload["error"]["trace_id"] == "trace_test_profile"
    assert response.headers["x-trace-id"] == "trace_test_profile"


def test_workbench_backend_validation_error_uses_standard_error_contract(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    response = client.post(
        "/api/runs/smoke",
        json={"unexpected": "field"},
        headers={"X-Trace-Id": "trace_test_validation"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert isinstance(payload["detail"], list)
    assert payload["error"]["error_code"] == "request_validation_error"
    assert payload["error"]["trace_id"] == "trace_test_validation"
    assert response.headers["x-trace-id"] == "trace_test_validation"


def test_workbench_backend_serves_frontend_shell() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "FinSight Workbench" in response.text
    assert "/assets/" in response.text or "/static/app.js" in response.text


def test_workbench_backend_imports_env_without_secret_value(tmp_path: Path) -> None:
    env_file = tmp_path / "demo.env"
    env_file.write_text(
        "\n".join(
            [
                "LLM_BACKEND=openai_compatible",
                "MODEL_NAME=demo-model",
                "API_KEY_ENV=DEMO_API_KEY",
                "DEMO_API_KEY=redacted-do-not-copy",
                "MANIFEST_PATH=manifest.jsonl",
                "BM25_INDEX_DIR=bm25",
                "OBJECT_BM25_INDEX_DIR=object_bm25",
            ]
        ),
        encoding="utf-8",
    )
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    response = client.post(
        "/api/profiles/import-env",
        json={"env_path": str(env_file), "profile_id": "demo"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile_id"] == "demo"
    assert payload["model_route"]["api_key_env"] == "DEMO_API_KEY"
    assert "redacted-do-not-copy" not in json.dumps(payload, ensure_ascii=False)


def test_workbench_backend_saves_and_lists_profiles(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))
    profile = {
        "profile_id": "saved_demo",
        "display_name": "Saved demo",
        "model_route": {"backend": "deepseek", "model_name": "deepseek-v4-pro"},
        "sources": {"source_policy": "SEC_PRIMARY_MIXED_RECENT"},
        "runtime": {"python": "python", "bge_device": "cpu"},
    }

    save_response = client.post("/api/profiles", json=profile)
    list_response = client.get("/api/profiles")
    get_response = client.get("/api/profiles/saved_demo")

    assert save_response.status_code == 200
    assert save_response.json()["profile_id"] == "saved_demo"
    assert list_response.status_code == 200
    assert list_response.json()["profiles"][0]["profile_id"] == "saved_demo"
    assert get_response.status_code == 200
    assert get_response.json()["display_name"] == "Saved demo"


def test_workbench_backend_imports_lists_and_validates_source_bundle(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    market = tmp_path / "market.jsonl"
    bm25 = tmp_path / "bm25"
    object_bm25 = tmp_path / "object_bm25"
    env_file = tmp_path / "demo.env"
    bm25.mkdir()
    object_bm25.mkdir()
    _write_jsonl(
        manifest,
        [
            {
                "ticker": "NVDA",
                "fiscal_year": 2025,
                "form_type": "10-K",
                "source_tier": "primary_sec_filing",
            }
        ],
    )
    _write_jsonl(
        market,
        [
            {
                "ticker": "NVDA",
                "as_of_date": "2026-05-22",
                "field_refs": [{"field_name": "close_price", "value": 1.0}],
            }
        ],
    )
    env_file.write_text(
        "\n".join(
            [
                "SEC_AGENT_SOURCE_POLICY=SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT",
                f"MANIFEST_PATH={manifest}",
                f"BM25_INDEX_DIR={bm25}",
                f"OBJECT_BM25_INDEX_DIR={object_bm25}",
                f"MARKET_EVIDENCE_PATH={market}",
                "MARKET_AS_OF_DATE=2026-05-22",
            ]
        ),
        encoding="utf-8",
    )
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    import_response = client.post(
        "/api/source-bundles/import-profile",
        json={
            "env_path": str(env_file),
            "profile_id": "demo",
            "display_name": "Demo profile",
            "bundle_id": "demo_bundle",
            "bundle_display_name": "Demo source bundle",
            "repo_root": str(tmp_path),
        },
    )
    list_response = client.get("/api/source-bundles")
    get_response = client.get("/api/source-bundles/demo_bundle")
    validate_response = client.post(
        "/api/source-bundles/validate",
        json={"bundle_id": "demo_bundle", "repo_root": str(tmp_path)},
    )

    assert import_response.status_code == 200
    payload = import_response.json()
    assert payload["bundle"]["bundle_id"] == "demo_bundle"
    assert payload["bundle"]["display_name"] == "Demo source bundle"
    assert payload["bundle"]["ticker_count"] == 1
    assert payload["readiness"]["manifest"]["row_count"] == 1
    assert list_response.status_code == 200
    assert list_response.json()["bundles"][0]["bundle_id"] == "demo_bundle"
    assert get_response.status_code == 200
    assert get_response.json()["artifacts"]["manifest_path"] == str(manifest)
    assert validate_response.status_code == 200
    assert validate_response.json()["readiness"]["manifest"]["row_count"] == 1


def test_workbench_backend_inspects_and_persists_saved_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "qwen").mkdir(parents=True)
    (run_dir / "post_gates").mkdir()
    _write_json(
        run_dir / "sec_agent_state.json",
        {"run_id": "run_a", "status": "completed", "source_policy": "SEC_PRIMARY_MIXED_RECENT", "stages": []},
    )
    (run_dir / "qwen" / "rendered_answer.md").write_text("# Answer\n\nhello", encoding="utf-8")
    _write_json(run_dir / "post_gates" / "sec_benchmark_post_gates_summary.json", {"answer_gate_pass": True})
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    inspect_response = client.post(
        "/api/runs/inspect",
        json={"run_dir": str(run_dir), "job_id": "inspect_fixture", "profile_id": "saved_demo"},
    )
    list_response = client.get("/api/runs")
    get_response = client.get("/api/runs/inspect_fixture")

    assert inspect_response.status_code == 200
    payload = inspect_response.json()
    assert payload["job"]["status"] == "completed"
    assert payload["artifact_index"]["status"] == "pass"
    assert "hello" in payload["artifact_index"]["answer_preview"]
    assert list_response.json()["runs"][0]["job_id"] == "inspect_fixture"
    assert get_response.json()["artifact_index"]["state_summary"]["run_id"] == "run_a"


def test_workbench_backend_inspects_native_checkpoint(tmp_path: Path) -> None:
    run_dir = _write_native_checkpoint_fixture(tmp_path / "native_run")
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    response = client.post("/api/native-checkpoints/inspect", json={"run_dir": str(run_dir)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["resume_supported"] is True
    assert payload["latest_completed_node"] == "build_runtime_ledger"
    assert payload["next_recoverable_node"] == "assess_evidence_coverage"


def test_workbench_backend_run_report_includes_native_checkpoint(tmp_path: Path) -> None:
    run_dir = _write_native_checkpoint_fixture(tmp_path / "native_run")
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    inspect_response = client.post(
        "/api/runs/inspect",
        json={"run_dir": str(run_dir), "job_id": "native_run_inspect"},
    )
    get_response = client.get("/api/runs/native_run_inspect")

    assert inspect_response.status_code == 200
    inspect_payload = inspect_response.json()
    assert inspect_payload["native_checkpoint"]["resume_supported"] is True
    assert inspect_payload["native_checkpoint"]["next_recoverable_node"] == "assess_evidence_coverage"
    assert get_response.status_code == 200
    get_payload = get_response.json()
    assert get_payload["native_checkpoint"]["latest_completed_node"] == "build_runtime_ledger"


def test_workbench_backend_starts_native_checkpoint_resume_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_start_command_job(store, job, spec) -> None:
        captured["job"] = job
        captured["spec"] = spec
        store.upsert_run_job(job)

    monkeypatch.setattr("apps.workbench.backend.app.start_command_job", fake_start_command_job)
    run_dir = _write_native_checkpoint_fixture(tmp_path / "native_run")
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))
    profile = {
        "profile_id": "resume_demo",
        "display_name": "Resume demo",
        "model_route": {"api_key_env": "DEMO_API_KEY"},
        "runtime": {"python": "python", "execution_shell": "local"},
    }

    response = client.post(
        "/api/native-checkpoints/resume",
        json={
            "run_dir": str(run_dir),
            "profile": profile,
            "api_key_value": "runtime-secret",
            "stop_after_node": "assess_evidence_coverage",
            "checkpoint_mode": "sqlite",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["inspection"]["resume_supported"] is True
    assert payload["job"]["job_type"] == "native_checkpoint_resume"
    assert payload["job"]["run_dir"] == str(run_dir.resolve())
    spec = captured["spec"]
    assert spec.env_overrides["DEMO_API_KEY"] == "runtime-secret"
    assert "--resume-native-checkpoint" in spec.args
    assert "--native-stop-after-node" in spec.args
    assert "runtime-secret" not in " ".join(spec.args)


def test_workbench_backend_runs_local_smoke_job_and_persists_events(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    start_response = client.post(
        "/api/runs/smoke",
        json={"job_id": "smoke_fixture"},
        headers={"X-Trace-Id": "trace_smoke_fixture"},
    )

    assert start_response.status_code == 200
    assert start_response.json()["job"]["status"] == "queued"
    assert start_response.json()["job"]["trace_id"] == "trace_smoke_fixture"
    queued_status = client.get("/api/runs/smoke_fixture/status")
    assert queued_status.status_code == 200
    assert queued_status.json()["job_id"] == "smoke_fixture"
    assert queued_status.json()["trace_id"] == "trace_smoke_fixture"
    assert isinstance(queued_status.json()["is_terminal"], bool)
    payload = _wait_for_job(client, "smoke_fixture")
    assert payload["job"]["status"] == "completed"
    assert payload["job"]["trace_id"] == "trace_smoke_fixture"
    assert payload["job"]["elapsed_ms"] is not None
    assert payload["job"]["error_message"] == ""
    events_response = client.get("/api/runs/smoke_fixture/events")
    assert events_response.status_code == 200
    events = events_response.json()["events"]
    final_status = client.get("/api/runs/smoke_fixture/status")
    assert final_status.status_code == 200
    final_status_payload = final_status.json()
    assert final_status_payload["status"] == "completed"
    assert final_status_payload["is_terminal"] is True
    assert final_status_payload["event_count"] == len(events)
    assert final_status_payload["latest_event"]["message"].startswith("process exited") or final_status_payload["latest_event"]["message"].startswith("detected run_dir")
    messages = [event["message"] for event in events]
    assert {event["trace_id"] for event in events} == {"trace_smoke_fixture"}
    assert "workbench smoke started" in messages
    assert "workbench smoke completed" in messages
    filtered_runs = client.get("/api/runs", params={"trace_id": "trace_smoke_fixture", "status": "completed"})
    trace_response = client.get("/api/traces/trace_smoke_fixture")
    assert filtered_runs.status_code == 200
    assert [item["job_id"] for item in filtered_runs.json()["runs"]] == ["smoke_fixture"]
    assert trace_response.status_code == 200
    trace_payload = trace_response.json()
    assert trace_payload["trace_id"] == "trace_smoke_fixture"
    assert trace_payload["job_count"] == 1
    assert trace_payload["event_count"] == len(events)
    assert trace_payload["status_counts"] == {"completed": 1}
    assert trace_payload["jobs"][0]["elapsed_ms"] is not None
    assert trace_payload["events"][0]["trace_id"] == "trace_smoke_fixture"


def test_workbench_backend_trace_inspection_reports_missing_trace(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    response = client.get("/api/traces/trace_missing")

    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"] == "trace_not_found: trace_missing"
    assert payload["error"]["error_code"] == "trace_not_found"


def test_workbench_backend_run_status_reports_missing_job(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    response = client.get("/api/runs/missing_job/status")

    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"] == "job_not_found: missing_job"
    assert payload["error"]["error_code"] == "job_not_found"


def test_workbench_backend_cancels_running_job(tmp_path: Path) -> None:
    db_path = tmp_path / "workbench.sqlite"
    store = WorkbenchStore(db_path)
    client = TestClient(create_app(store_path=db_path))
    job = new_local_smoke_job(job_id="long_fixture", trace_id="trace_cancel")
    code = "import time; print('started', flush=True); time.sleep(30); print('done', flush=True)"
    start_command_job(
        store,
        job,
        CommandSpec(args=[sys.executable, "-u", "-c", code], cwd=tmp_path, label="long_fixture"),
    )

    for _ in range(30):
        status = client.get("/api/runs/long_fixture/status").json()["status"]
        if status == "running":
            break
        time.sleep(0.05)
    cancel_response = client.post("/api/runs/long_fixture/cancel", json={"reason": "test cancellation"})

    assert cancel_response.status_code == 200
    payload = cancel_response.json()
    assert payload["cancelled"] is True
    assert payload["status"] == "cancelled"
    final = client.get("/api/runs/long_fixture/status").json()
    assert final["status"] == "cancelled"
    assert final["is_terminal"] is True
    messages = [event["message"] for event in client.get("/api/runs/long_fixture/events").json()["events"]]
    assert "test cancellation" in messages


def test_workbench_backend_prunes_terminal_run_history(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))
    store = WorkbenchStore(tmp_path / "workbench.sqlite")
    for job_id in ("keep_fixture", "drop_fixture"):
        job = new_local_smoke_job(job_id=job_id, trace_id=f"trace_{job_id}").model_copy(
            update={"status": "completed"}
        )
        store.upsert_run_job(job)
        store.append_run_event(job_id, stream="system", message=f"{job_id} event")

    dry_run = client.post("/api/runs/prune", json={"keep_latest": 1, "dry_run": True})
    prune = client.post("/api/runs/prune", json={"keep_latest": 1, "dry_run": False})

    assert dry_run.status_code == 200
    assert dry_run.json()["deleted_job_count"] == 0
    assert dry_run.json()["candidate_job_ids"] == ["drop_fixture"]
    assert prune.status_code == 200
    assert prune.json()["deleted_job_count"] == 1
    assert prune.json()["deleted_event_count"] == 1
    assert client.get("/api/runs/drop_fixture/status").status_code == 404
    assert client.get("/api/runs/keep_fixture/status").status_code == 200


def test_workbench_backend_prunes_history_with_filters(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))
    store = WorkbenchStore(tmp_path / "workbench.sqlite")
    keep = new_local_smoke_job(job_id="keep_failed", trace_id="trace_a").model_copy(update={"status": "failed"})
    drop = new_local_smoke_job(job_id="drop_cancelled", trace_id="trace_b").model_copy(update={"status": "cancelled"})
    store.upsert_run_job(keep)
    store.upsert_run_job(drop)

    response = client.post(
        "/api/runs/prune",
        json={"keep_latest": 0, "status": "cancelled", "dry_run": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "cancelled"
    assert payload["candidate_job_ids"] == ["drop_cancelled"]


def test_workbench_backend_streams_smoke_job_events(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))
    client.post("/api/runs/smoke", json={"job_id": "smoke_stream_fixture"}).raise_for_status()
    _wait_for_job(client, "smoke_stream_fixture")

    with client.stream("GET", "/api/runs/smoke_stream_fixture/events/stream") as response:
        assert response.status_code == 200
        stream_text = "".join(response.iter_text())

    assert "event: log" in stream_text
    assert "workbench smoke completed" in stream_text
    assert "event: done" in stream_text


def test_workbench_backend_validates_run_event_pagination_params(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    negative_cursor = client.get("/api/runs/smoke_fixture/events", params={"after_sequence": -1})
    too_large_limit = client.get("/api/runs/smoke_fixture/events", params={"limit": 5001})
    negative_stream_cursor = client.get("/api/runs/smoke_fixture/events/stream", params={"after_sequence": -1})

    assert negative_cursor.status_code == 422
    assert too_large_limit.status_code == 422
    assert negative_stream_cursor.status_code == 422


def test_workbench_backend_rejects_agent_ask_without_profile(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    response = client.post("/api/runs/ask", json={"prompt": "hello"})

    assert response.status_code == 400
    assert response.json()["detail"] == "profile_or_profile_id_required"


def test_workbench_backend_starts_session_turn_without_leaking_runtime_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_start_command_job(store, job, spec) -> None:
        captured["job"] = job
        captured["spec"] = spec
        store.upsert_run_job(job)

    monkeypatch.setattr("apps.workbench.backend.app.start_command_job", fake_start_command_job)
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))
    profile = {
        "profile_id": "session_demo",
        "display_name": "Session demo",
        "model_route": {
            "backend": "openai_compatible",
            "base_url": "https://example.invalid",
            "model_name": "demo-model",
            "api_key_env": "DEMO_API_KEY",
        },
        "runtime": {"python": "python", "execution_shell": "local"},
    }

    response = client.post(
        "/api/sessions/turns",
        json={
            "profile": profile,
            "prompt": "继续比较 NVDA 和 AMD",
            "session_id": "thread_a",
            "tenant_id": "tenant_a",
            "user_id": "user_a",
            "api_key_value": "runtime-secret",
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job"]["job_id"]
    assert response.json()["job"]["status"] == "queued"
    spec = captured["spec"]
    assert spec.env_overrides["DEMO_API_KEY"] == "runtime-secret"
    assert "runtime-secret" not in " ".join(spec.args)
    assert "--session-id" in spec.args
    assert "thread_a" in spec.args
    payload = client.get(f"/api/runs/{job_id}").json()
    assert payload["job"]["metadata"]["session_id"] == "thread_a"
    sessions_payload = client.get("/api/sessions").json()
    assert sessions_payload["sessions"][0]["session_id"] == "thread_a"
    assert sessions_payload["sessions"][0]["turn_count"] == 1
    turns_payload = client.get("/api/sessions/thread_a/turns").json()
    assert turns_payload["session_id"] == "thread_a"
    assert turns_payload["turns"][0]["job_id"] == job_id
    assert turns_payload["turns"][0]["prompt"] == "继续比较 NVDA 和 AMD"


def test_workbench_backend_lists_and_starts_controlled_eval_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_start_command_job(store, job, spec) -> None:
        captured["job"] = job
        captured["spec"] = spec
        store.upsert_run_job(job)

    monkeypatch.setattr("apps.workbench.backend.app.start_command_job", fake_start_command_job)
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    catalog_response = client.get("/api/evals")
    start_response = client.post(
        "/api/evals/run",
        json={"eval_id": "context_api_smoke", "job_id": "eval_fixture"},
    )

    assert catalog_response.status_code == 200
    assert "context_api_smoke" in {item["eval_id"] for item in catalog_response.json()["evals"]}
    assert start_response.status_code == 200
    payload = start_response.json()
    assert payload["job"]["job_type"] == "eval_run"
    assert payload["job"]["metadata"]["eval_id"] == "context_api_smoke"
    assert payload["job"]["metadata"]["output_path"].endswith("eval_fixture_context_api_smoke.json")
    spec = captured["spec"]
    assert "scripts/eval_context/evaluate_sec_agent_context_api_smoke.py" in spec.args
    assert "--output-path" in spec.args


def test_workbench_backend_rejects_unknown_eval_runner(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    response = client.post(
        "/api/evals/run",
        json={"eval_id": "not_allowed"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported_eval_id: not_allowed"


def test_workbench_backend_lists_previews_and_starts_data_build_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_start_command_job(store, job, spec) -> None:
        captured["job"] = job
        captured["spec"] = spec
        store.upsert_run_job(job)

    monkeypatch.setattr("apps.workbench.backend.app.start_command_job", fake_start_command_job)
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))
    client.post(
        "/api/source-bundles",
        json={
            "bundle_id": "bundle_a",
            "display_name": "Bundle A",
            "market": "US",
            "coverage_theme": "demo",
            "build": {"created_at": "2026-05-25T00:00:00", "status": "ready"},
        },
    ).raise_for_status()

    catalog_response = client.get("/api/data-build/steps")
    preview_response = client.post(
        "/api/data-build/preview",
        json={
            "step_id": "sec_build_manifest",
            "bundle_id": "bundle_a",
            "update_bundle": True,
            "values": {
                "output": "data/processed_private/manifests/demo.jsonl",
                "tickers": "NVDA",
            },
        },
    )
    run_response = client.post(
        "/api/data-build/run",
        json={
            "step_id": "sec_build_manifest",
            "job_id": "data_build_fixture",
            "bundle_id": "bundle_a",
            "update_bundle": True,
            "values": {
                "output": "data/processed_private/manifests/demo.jsonl",
                "tickers": "NVDA",
            },
        },
    )

    assert catalog_response.status_code == 200
    assert "sec_build_manifest" in {item["step_id"] for item in catalog_response.json()["steps"]}
    assert preview_response.status_code == 200
    assert preview_response.json()["preview"]["missing_required"] == []
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["job"]["job_type"] == "data_build"
    assert payload["job"]["metadata"]["step_id"] == "sec_build_manifest"
    assert payload["job"]["metadata"]["bundle_id"] == "bundle_a"
    assert payload["job"]["metadata"]["bundle_artifact_updates"] == {"manifest_path": "data/processed_private/manifests/demo.jsonl"}
    spec = captured["spec"]
    assert "scripts/data_sec/build_sec_manifest.py" in spec.args
    assert "--output" in spec.args


def test_workbench_backend_rejects_data_build_missing_required_params(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    response = client.post(
        "/api/data-build/run",
        json={"step_id": "sec_build_chunks", "values": {"manifest": "manifest.jsonl"}},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["reason"] == "missing_required_parameters"
    assert response.json()["detail"]["missing_required"] == ["output"]


def test_workbench_backend_validates_env_profile(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    bm25 = tmp_path / "bm25"
    object_bm25 = tmp_path / "object_bm25"
    env_file = tmp_path / "demo.env"
    bm25.mkdir()
    object_bm25.mkdir()
    _write_jsonl(
        manifest,
        [
            {
                "ticker": "NVDA",
                "fiscal_year": 2025,
                "form_type": "10-K",
                "source_tier": "primary_sec_filing",
            }
        ],
    )
    env_file.write_text(
        "\n".join(
            [
                "SEC_AGENT_SOURCE_POLICY=SEC_PRIMARY_MIXED_RECENT",
                f"MANIFEST_PATH={manifest}",
                f"BM25_INDEX_DIR={bm25}",
                f"OBJECT_BM25_INDEX_DIR={object_bm25}",
            ]
        ),
        encoding="utf-8",
    )
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    response = client.post(
        "/api/profiles/validate",
        json={"env_path": str(env_file), "profile_id": "demo", "repo_root": str(tmp_path)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass"
    assert payload["manifest"]["row_count"] == 1


def test_workbench_backend_validates_saved_profile_by_id(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    bm25 = tmp_path / "bm25"
    object_bm25 = tmp_path / "object_bm25"
    bm25.mkdir()
    object_bm25.mkdir()
    _write_jsonl(
        manifest,
        [
            {
                "ticker": "NVDA",
                "fiscal_year": 2025,
                "form_type": "10-K",
                "source_tier": "primary_sec_filing",
            }
        ],
    )
    profile = {
        "profile_id": "saved_ready",
        "display_name": "Saved ready profile",
        "sources": {
            "source_policy": "SEC_PRIMARY_MIXED_RECENT",
            "manifest_path": str(manifest),
            "bm25_index_dir": str(bm25),
            "object_bm25_index_dir": str(object_bm25),
        },
        "runtime": {"python": "python", "bge_device": "cpu"},
    }
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))
    client.post("/api/profiles", json=profile).raise_for_status()

    response = client.post(
        "/api/profiles/validate",
        json={"profile_id": "saved_ready", "repo_root": str(tmp_path)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass"
    assert payload["manifest"]["row_count"] == 1


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_native_checkpoint_fixture(run_dir: Path) -> Path:
    run_dir.mkdir(parents=True)
    context_path = run_dir / "retrieved_context.jsonl"
    ledger_path = run_dir / "runtime_exact_value_ledger.json"
    _write_jsonl(context_path, [{"evidence_id": "e1", "ticker": "NVDA"}])
    _write_json(ledger_path, {"rows": [{"metric_id": "m1", "ticker": "NVDA"}]})
    _write_json(
        run_dir / "langgraph_node_checkpoints.json",
        {
            "schema_version": "sec_agent_langgraph_node_checkpoint_artifact_v0.1",
            "run_id": "native_fixture",
            "output_dir": str(run_dir),
            "status": "stopped_after_node",
            "checkpoint_count": 1,
            "latest_completed_node": "build_runtime_ledger",
            "latest_checkpoint_id": "ckpt_1",
            "recoverable_state_summary": {"status": "stopped_after_node"},
            "artifact_refs": {
                "retrieved_context": {"path": str(context_path), "exists": True},
                "runtime_exact_value_ledger": {"path": str(ledger_path), "exists": True},
            },
            "node_checkpoints": [
                {
                    "schema_version": "sec_agent_langgraph_node_checkpoint_v0.1",
                    "node": "build_runtime_ledger",
                    "checkpoint_id": "ckpt_1",
                    "previous_checkpoint_id": "",
                    "started_at": "2026-05-29T00:00:00",
                    "finished_at": "2026-05-29T00:00:01",
                    "elapsed_ms": 1,
                    "state_summary": {"status": "stopped_after_node"},
                    "metadata": {},
                }
            ],
        },
    )
    return run_dir


def _wait_for_job(client: TestClient, job_id: str) -> dict:
    terminal = {"completed", "failed", "cancelled", "interrupted", "timed_out"}
    for _ in range(50):
        response = client.get(f"/api/runs/{job_id}")
        response.raise_for_status()
        payload = response.json()
        if payload["job"]["status"] in terminal:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {job_id}")
