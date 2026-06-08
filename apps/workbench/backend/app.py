from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from sec_agent.workbench import (
    PathPolicyViolation,
    RunCancelReport,
    RunInspectionReport,
    RunPruneReport,
    RunRecoveryReport,
    RunStatusReport,
    StoreBackupReport,
    SourceBundle,
    TraceInspectionReport,
    WorkbenchPathPolicy,
    WorkbenchProfile,
    WorkbenchStore,
    build_data_build_command,
    build_agent_ask_command,
    build_agent_session_turn_command,
    build_eval_command,
    build_local_smoke_command,
    build_maintenance_command,
    build_native_checkpoint_resume_command,
    cancel_command_job,
    default_store_path,
    data_build_catalog,
    eval_output_path,
    eval_runner_catalog,
    get_data_build_step,
    get_maintenance_action,
    inspect_deployment,
    inspect_runtime_preflight,
    inspect_run_artifacts,
    maintenance_action_catalog,
    new_agent_ask_job,
    new_agent_session_turn_job,
    new_data_build_job,
    new_eval_run_job,
    new_local_smoke_job,
    new_maintenance_job,
    new_native_checkpoint_resume_job,
    new_saved_run_inspection_job,
    profile_from_env_file,
    profile_from_source_bundle,
    runtime_limits_from_env,
    source_bundle_from_profile,
    start_command_job,
    validate_profile_sources,
)
from sec_agent.workbench.api_contracts import install_api_contracts, request_trace_id
from sec_agent.langgraph_orchestrator import inspect_node_checkpoint_artifact


APP_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = APP_ROOT / "frontend"
FRONTEND_DIST_ROOT = FRONTEND_ROOT / "dist"
REPO_ROOT = Path(__file__).resolve().parents[3]
EVENT_PAGE_MAX = runtime_limits_from_env().event_page_max


class ImportEnvRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    env_path: str
    profile_id: str | None = None
    display_name: str | None = None


class ValidateProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: WorkbenchProfile | None = None
    env_path: str | None = None
    profile_id: str | None = None
    display_name: str | None = None
    repo_root: str | None = None
    require_full_source: bool | None = None


class ImportSourceBundleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: WorkbenchProfile | None = None
    env_path: str | None = None
    profile_id: str | None = None
    display_name: str | None = None
    bundle_id: str | None = None
    bundle_display_name: str | None = None
    repo_root: str | None = None
    require_full_source: bool | None = None


class ValidateSourceBundleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle: SourceBundle | None = None
    bundle_id: str | None = None
    repo_root: str | None = None
    require_full_source: bool | None = None


class DataBuildPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    values: dict[str, object] = Field(default_factory=dict)
    profile: WorkbenchProfile | None = None
    profile_id: str | None = None
    dry_run: bool = False
    bundle_id: str | None = None
    update_bundle: bool = False


class DataBuildRunRequest(DataBuildPreviewRequest):
    job_id: str | None = None


class InspectRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_dir: str
    job_id: str | None = None
    profile_id: str | None = None
    persist: bool = True


class StartSmokeRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str | None = None
    profile_id: str | None = None


class StartAgentAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    profile: WorkbenchProfile | None = None
    profile_id: str | None = None
    job_id: str | None = None
    api_key_value: str | None = None
    command_mode: Literal[
        "ask-full-source-api",
        "ask-full-source-deepseek",
        "ask-mixed-8k-api",
        "ask-mixed-8k-deepseek",
        "ask-mixed-api",
        "ask-mixed-deepseek",
        "ask-api",
        "ask-deepseek",
        "plan",
    ] = "ask-full-source-api"


class StartSessionTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    session_id: str
    tenant_id: str = "workbench_tenant"
    user_id: str = "workbench_user"
    profile: WorkbenchProfile | None = None
    profile_id: str | None = None
    job_id: str | None = None
    api_key_value: str | None = None
    command_mode: Literal[
        "session-full-source-api",
        "session-full-source-deepseek",
        "session-mixed-8k-api",
        "session-mixed-8k-deepseek",
        "session-mixed-api",
        "session-mixed-deepseek",
        "session-api",
        "session-deepseek",
    ] = "session-full-source-api"


class StartEvalRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eval_id: str
    job_id: str | None = None
    profile_id: str | None = None
    api_key_value: str | None = None
    case_ids: list[str] = Field(default_factory=list)
    prewarm_resident_tools: bool | None = None


class CancelRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = "cancelled by user"


class PruneRunHistoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keep_latest: int = Field(default=200, ge=0, le=10000)
    max_age_days: int | None = Field(default=None, ge=0, le=3650)
    terminal_only: bool = True
    dry_run: bool = True
    trace_id: str | None = None
    status: str | None = None
    job_type: str | None = None


class StoreBackupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backup_dir: str | None = None


class MaintenanceRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    job_id: str | None = None
    parameters: dict[str, object] = Field(default_factory=dict)


class NativeCheckpointInspectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_dir: str


class NativeCheckpointResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_dir: str
    profile: WorkbenchProfile | None = None
    profile_id: str | None = None
    job_id: str | None = None
    api_key_value: str | None = None
    include_synthesis: bool = True
    stop_after_node: str | None = None
    checkpoint_mode: Literal["memory", "sqlite", "none"] = "sqlite"


def create_app(
    store_path: str | Path | None = None,
    *,
    allowed_roots: list[str | Path] | None = None,
    allow_external_paths: bool | None = None,
    recover_stale_jobs: bool = True,
) -> FastAPI:
    resolved_store_path = Path(store_path or default_store_path(REPO_ROOT))
    store = WorkbenchStore(resolved_store_path)
    path_policy = WorkbenchPathPolicy(
        repo_root=REPO_ROOT,
        extra_allowed_roots=[resolved_store_path.parent, *(allowed_roots or [])],
        allow_external_paths=allow_external_paths,
    )
    recovery_report = (
        store.interrupt_active_run_jobs(reason="workbench service restarted")
        if recover_stale_jobs
        else RunRecoveryReport(status="skipped", reason="disabled", interrupted_job_ids=[], interrupted_job_count=0)
    )
    app = FastAPI(
        title="FinSight Workbench API",
        version="0.1.0",
        description="Local API for FinSight-Agent profile import and source readiness checks.",
    )
    app.state.workbench_store = store
    app.state.workbench_path_policy = path_policy
    app.state.workbench_recovery_report = recovery_report
    install_api_contracts(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    if (FRONTEND_DIST_ROOT / "assets").exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_ROOT / "assets"), name="assets")
    if (FRONTEND_ROOT / "static").exists():
        app.mount("/static", StaticFiles(directory=FRONTEND_ROOT / "static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        index_path = FRONTEND_DIST_ROOT / "index.html" if (FRONTEND_DIST_ROOT / "index.html").exists() else FRONTEND_ROOT / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="frontend_not_built")
        return index_path.read_text(encoding="utf-8")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "finsight-workbench",
            "version": "0.1.0",
            "frontend": "available" if (FRONTEND_DIST_ROOT / "index.html").exists() or (FRONTEND_ROOT / "index.html").exists() else "missing",
        }

    @app.get("/api/health/live")
    def liveness() -> dict[str, str]:
        return {"status": "ok", "service": "finsight-workbench"}

    @app.get("/api/health/ready")
    def readiness():
        payload = _system_status_payload(store=store, path_policy=path_policy, recovery_report=recovery_report)
        if payload["status"] != "ok":
            raise HTTPException(status_code=503, detail=jsonable_encoder(payload))
        return payload

    @app.get("/api/system/status")
    def system_status():
        return _system_status_payload(store=store, path_policy=path_policy, recovery_report=recovery_report)

    @app.get("/api/system/runtime/preflight")
    def runtime_preflight():
        return inspect_runtime_preflight(REPO_ROOT)

    @app.get("/api/system/contracts")
    def system_contracts():
        return {
            "schema_version": "finsight_workbench_backend_contracts_v0.2",
            "service": "finsight-workbench",
            "run_statuses": {
                "active": ["queued", "running"],
                "terminal": ["completed", "failed", "cancelled", "interrupted", "timed_out"],
            },
            "trace_header": "X-Trace-Id",
            "elapsed_header": "X-Elapsed-Time-Ms",
            "runtime_limits": runtime_limits_from_env(),
            "path_policy": path_policy.report(),
            "deployment_schema_version": "finsight_workbench_deployment_v0.1",
            "maintenance_schema_version": "finsight_workbench_maintenance_actions_v0.1",
            "error_schema_version": "finsight_workbench_api_error_v0.1",
        }

    @app.get("/api/system/deployment")
    def system_deployment():
        runtime_preflight = inspect_runtime_preflight(REPO_ROOT)
        frontend_bundled = (FRONTEND_DIST_ROOT / "index.html").exists()
        return inspect_deployment(
            repo_root=REPO_ROOT,
            frontend_bundled=frontend_bundled,
            path_policy=path_policy.report(),
            runtime_preflight=runtime_preflight,
        )

    @app.get("/api/system/maintenance/actions")
    def list_maintenance_actions():
        return maintenance_action_catalog(REPO_ROOT)

    @app.post("/api/system/maintenance/run")
    def run_maintenance_action(payload: MaintenanceRunRequest, request: Request):
        action = get_maintenance_action(REPO_ROOT, payload.action_id)
        if action is None:
            raise HTTPException(status_code=404, detail=f"maintenance_action_not_found: {payload.action_id}")
        try:
            spec = build_maintenance_command(
                repo_root=REPO_ROOT,
                action_id=payload.action_id,
                parameters=payload.parameters,
            )
        except PermissionError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "reason": "maintenance_action_disabled",
                    "action_id": payload.action_id,
                    "status": action.status,
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        job = new_maintenance_job(
            action_id=action.action_id,
            action_label=action.label,
            category=action.category,
            job_id=payload.job_id,
            trace_id=request_trace_id(request),
        )
        start_command_job(store, job, spec)
        return {"job": job, "action": action}

    @app.post("/api/system/store/backup")
    def backup_store(payload: StoreBackupRequest) -> StoreBackupReport:
        backup_dir = _repo_path(payload.backup_dir, path_policy=path_policy) if payload.backup_dir else None
        return store.backup_database(backup_dir=backup_dir)

    @app.post("/api/profiles/import-env")
    def import_env(request: ImportEnvRequest) -> WorkbenchProfile:
        return _load_env_profile(
            request.env_path,
            profile_id=request.profile_id,
            display_name=request.display_name,
            path_policy=path_policy,
        )

    @app.get("/api/profiles")
    def list_profiles():
        return {"profiles": store.list_profiles()}

    @app.post("/api/profiles")
    def save_profile(profile: WorkbenchProfile):
        return store.upsert_profile(profile)

    @app.get("/api/profiles/{profile_id}")
    def get_profile(profile_id: str) -> WorkbenchProfile:
        profile = store.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail=f"profile_not_found: {profile_id}")
        return profile

    @app.get("/api/source-bundles")
    def list_source_bundles():
        return {"bundles": store.list_source_bundles()}

    @app.post("/api/source-bundles")
    def save_source_bundle(bundle: SourceBundle):
        return store.upsert_source_bundle(bundle)

    @app.get("/api/source-bundles/{bundle_id}")
    def get_source_bundle(bundle_id: str) -> SourceBundle:
        bundle = store.get_source_bundle(bundle_id)
        if bundle is None:
            raise HTTPException(status_code=404, detail=f"source_bundle_not_found: {bundle_id}")
        return bundle

    @app.post("/api/source-bundles/import-profile")
    def import_source_bundle(request: ImportSourceBundleRequest):
        profile = _resolve_profile_like(
            profile=request.profile,
            env_path=request.env_path,
            profile_id=request.profile_id,
            display_name=request.display_name,
            store=store,
            path_policy=path_policy,
        )
        repo_root = _repo_path(request.repo_root, path_policy=path_policy) if request.repo_root else REPO_ROOT
        readiness = validate_profile_sources(
            profile,
            repo_root=repo_root,
            require_full_source=request.require_full_source,
        )
        bundle = source_bundle_from_profile(
            profile,
            readiness=readiness,
            bundle_id=request.bundle_id,
            display_name=request.bundle_display_name,
        )
        summary = store.upsert_source_bundle(bundle)
        return {"bundle": bundle, "summary": summary, "readiness": readiness}

    @app.post("/api/source-bundles/validate")
    def validate_source_bundle(request: ValidateSourceBundleRequest):
        bundle = request.bundle
        if bundle is None:
            if not request.bundle_id:
                raise HTTPException(status_code=400, detail="bundle_or_bundle_id_required")
            bundle = store.get_source_bundle(request.bundle_id)
            if bundle is None:
                raise HTTPException(status_code=404, detail=f"source_bundle_not_found: {request.bundle_id}")
        repo_root = _repo_path(request.repo_root, path_policy=path_policy) if request.repo_root else REPO_ROOT
        profile = profile_from_source_bundle(bundle)
        readiness = validate_profile_sources(
            profile,
            repo_root=repo_root,
            require_full_source=request.require_full_source,
        )
        return {"bundle": bundle, "readiness": readiness}

    @app.post("/api/profiles/validate")
    def validate_profile(request: ValidateProfileRequest):
        profile = request.profile
        if profile is None:
            if request.env_path:
                profile = _load_env_profile(
                    request.env_path,
                    profile_id=request.profile_id,
                    display_name=request.display_name,
                    path_policy=path_policy,
                )
            elif request.profile_id:
                profile = store.get_profile(request.profile_id)
                if profile is None:
                    raise HTTPException(status_code=404, detail=f"profile_not_found: {request.profile_id}")
            else:
                raise HTTPException(status_code=400, detail="profile_or_env_path_required")
        repo_root = _repo_path(request.repo_root, path_policy=path_policy) if request.repo_root else REPO_ROOT
        return validate_profile_sources(
            profile,
            repo_root=repo_root,
            require_full_source=request.require_full_source,
        )

    @app.get("/api/runs")
    def list_runs(
        trace_id: str | None = None,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = Query(200, ge=1, le=1000),
    ):
        return {
            "runs": store.list_run_jobs(
                trace_id=trace_id,
                status=status,
                job_type=job_type,
                limit=limit,
            )
        }

    @app.get("/api/traces/{trace_id}")
    def inspect_trace(trace_id: str, event_limit: int = Query(1000, ge=1, le=EVENT_PAGE_MAX)) -> TraceInspectionReport:
        report = store.inspect_trace(trace_id, event_limit=event_limit)
        if report.job_count == 0 and report.event_count == 0:
            raise HTTPException(status_code=404, detail=f"trace_not_found: {trace_id}")
        return report

    @app.get("/api/evals")
    def list_evals():
        return {"evals": eval_runner_catalog()}

    @app.get("/api/data-build/steps")
    def list_data_build_steps():
        return {"steps": data_build_catalog()}

    @app.post("/api/data-build/preview")
    def preview_data_build(request: DataBuildPreviewRequest):
        profile = _optional_profile(request.profile, request.profile_id, store)
        _validate_data_build_paths(request.step_id, request.values, path_policy=path_policy)
        try:
            _spec, preview = build_data_build_command(
                repo_root=REPO_ROOT,
                step_id=request.step_id,
                values=request.values,
                profile=profile,
                dry_run=request.dry_run,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"preview": preview}

    @app.post("/api/data-build/run")
    def run_data_build(payload: DataBuildRunRequest, request: Request):
        profile = _optional_profile(payload.profile, payload.profile_id, store)
        _validate_data_build_paths(payload.step_id, payload.values, path_policy=path_policy)
        try:
            spec, preview = build_data_build_command(
                repo_root=REPO_ROOT,
                step_id=payload.step_id,
                values=payload.values,
                profile=profile,
                dry_run=payload.dry_run,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if preview.missing_required:
            raise HTTPException(
                status_code=400,
                detail={"reason": "missing_required_parameters", "missing_required": preview.missing_required},
            )
        if payload.update_bundle and not payload.dry_run:
            if not payload.bundle_id:
                raise HTTPException(status_code=400, detail="bundle_id_required_for_update")
            if store.get_source_bundle(payload.bundle_id) is None:
                raise HTTPException(status_code=404, detail=f"source_bundle_not_found: {payload.bundle_id}")
        job = new_data_build_job(
            step_id=preview.step_id,
            step_label=preview.label,
            command_preview=preview.args,
            bundle_id=payload.bundle_id if payload.update_bundle and not payload.dry_run else None,
            bundle_artifact_updates=preview.bundle_artifact_updates if payload.update_bundle and not payload.dry_run else {},
            bundle_field_updates=preview.bundle_field_updates if payload.update_bundle and not payload.dry_run else {},
            job_id=payload.job_id,
            profile_id=profile.profile_id if profile else None,
            trace_id=request_trace_id(request),
        )
        start_command_job(store, job, spec)
        return {"job": job, "preview": preview}

    @app.get("/api/sessions")
    def list_sessions():
        return {"sessions": store.list_sessions()}

    @app.get("/api/sessions/{session_id}/turns")
    def list_session_turns(session_id: str):
        return {
            "session_id": session_id,
            "turns": store.list_session_turn_jobs(session_id),
        }

    @app.get("/api/runs/{job_id}")
    def get_run(job_id: str):
        job = store.get_run_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"job_not_found: {job_id}")
        artifact_index = inspect_run_artifacts(job.run_dir) if job.run_dir else None
        native_checkpoint = _inspect_native_checkpoint_if_available(job.run_dir) if job.run_dir else None
        return {"job": job, "artifact_index": artifact_index, "native_checkpoint": native_checkpoint}

    @app.get("/api/runs/{job_id}/status")
    def get_run_status(job_id: str) -> RunStatusReport:
        report = store.get_run_status(job_id)
        if report is None:
            raise HTTPException(status_code=404, detail=f"job_not_found: {job_id}")
        return report

    @app.post("/api/runs/{job_id}/cancel")
    def cancel_run(job_id: str, payload: CancelRunRequest) -> RunCancelReport:
        report = cancel_command_job(store, job_id, reason=payload.reason.strip() or "cancelled by user")
        if report.status == "missing":
            raise HTTPException(status_code=404, detail=f"job_not_found: {job_id}")
        return report

    @app.post("/api/runs/prune")
    def prune_runs(payload: PruneRunHistoryRequest) -> RunPruneReport:
        return store.prune_run_jobs(
            keep_latest=payload.keep_latest,
            max_age_days=payload.max_age_days,
            terminal_only=payload.terminal_only,
            dry_run=payload.dry_run,
            trace_id=payload.trace_id,
            status=payload.status,
            job_type=payload.job_type,
        )

    @app.get("/api/runs/{job_id}/events")
    def get_run_events(
        job_id: str,
        after_sequence: int = Query(0, ge=0),
        limit: int = Query(500, ge=1, le=EVENT_PAGE_MAX),
    ):
        if store.get_run_job(job_id) is None:
            raise HTTPException(status_code=404, detail=f"job_not_found: {job_id}")
        return {"events": store.list_run_events(job_id, after_sequence=after_sequence, limit=limit)}

    @app.get("/api/runs/{job_id}/events/stream")
    def stream_run_events(job_id: str, after_sequence: int = Query(0, ge=0)):
        if store.get_run_job(job_id) is None:
            raise HTTPException(status_code=404, detail=f"job_not_found: {job_id}")
        return StreamingResponse(
            _event_stream(store, job_id, after_sequence=after_sequence),
            media_type="text/event-stream",
        )

    @app.post("/api/runs/inspect")
    def inspect_run(payload: InspectRunRequest, request: Request) -> RunInspectionReport:
        run_dir = _repo_path(payload.run_dir, path_policy=path_policy)
        artifact_index = inspect_run_artifacts(run_dir)
        native_checkpoint = _inspect_native_checkpoint_if_available(run_dir)
        job = new_saved_run_inspection_job(
            run_dir=run_dir,
            artifact_index=artifact_index,
            job_id=payload.job_id,
            profile_id=payload.profile_id,
            trace_id=request_trace_id(request),
        )
        if payload.persist:
            store.upsert_run_job(job)
        return RunInspectionReport(job=job, artifact_index=artifact_index, native_checkpoint=native_checkpoint)

    @app.post("/api/native-checkpoints/inspect")
    def inspect_native_checkpoint(request: NativeCheckpointInspectRequest):
        try:
            return inspect_node_checkpoint_artifact(_repo_path(request.run_dir, path_policy=path_policy))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/native-checkpoints/resume")
    def resume_native_checkpoint(payload: NativeCheckpointResumeRequest, request: Request):
        checkpoint_path = _repo_path(payload.run_dir, path_policy=path_policy)
        try:
            inspection = inspect_node_checkpoint_artifact(checkpoint_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not inspection.get("resume_supported"):
            raise HTTPException(status_code=409, detail={"reason": "native_checkpoint_not_resumable", "inspection": inspection})
        profile = _resolve_run_profile(payload.profile, payload.profile_id, store)
        try:
            spec = build_native_checkpoint_resume_command(
                repo_root=REPO_ROOT,
                profile=profile,
                checkpoint_path=checkpoint_path,
                api_key_value=payload.api_key_value,
                include_synthesis=payload.include_synthesis,
                stop_after_node=payload.stop_after_node,
                checkpoint_mode=payload.checkpoint_mode,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        job = new_native_checkpoint_resume_job(
            checkpoint_path=checkpoint_path,
            profile_id=profile.profile_id,
            job_id=payload.job_id,
            stop_after_node=payload.stop_after_node,
            include_synthesis=payload.include_synthesis,
            trace_id=request_trace_id(request),
        )
        start_command_job(store, job, spec)
        return {"job": job, "inspection": inspection}

    @app.post("/api/runs/smoke")
    def start_smoke_run(payload: StartSmokeRunRequest, request: Request):
        job = new_local_smoke_job(job_id=payload.job_id, profile_id=payload.profile_id, trace_id=request_trace_id(request))
        spec = build_local_smoke_command(REPO_ROOT)
        start_command_job(store, job, spec)
        return {"job": job}

    @app.post("/api/runs/ask")
    def start_agent_ask(payload: StartAgentAskRequest, request: Request):
        profile = _resolve_run_profile(payload.profile, payload.profile_id, store)
        try:
            spec = build_agent_ask_command(
                repo_root=REPO_ROOT,
                profile=profile,
                prompt=payload.prompt,
                command_mode=payload.command_mode,
                api_key_value=payload.api_key_value,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        job = new_agent_ask_job(
            prompt=payload.prompt.strip(),
            command_mode=payload.command_mode,
            job_id=payload.job_id,
            profile_id=profile.profile_id,
            trace_id=request_trace_id(request),
        )
        start_command_job(store, job, spec)
        return {"job": job}

    @app.post("/api/sessions/turns")
    def start_session_turn(payload: StartSessionTurnRequest, request: Request):
        profile = _resolve_run_profile(payload.profile, payload.profile_id, store)
        try:
            spec = build_agent_session_turn_command(
                repo_root=REPO_ROOT,
                profile=profile,
                prompt=payload.prompt,
                session_id=payload.session_id,
                tenant_id=payload.tenant_id,
                user_id=payload.user_id,
                command_mode=payload.command_mode,
                api_key_value=payload.api_key_value,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        job = new_agent_session_turn_job(
            prompt=payload.prompt.strip(),
            command_mode=payload.command_mode,
            session_id=payload.session_id.strip(),
            tenant_id=payload.tenant_id.strip() or "workbench_tenant",
            user_id=payload.user_id.strip() or "workbench_user",
            job_id=payload.job_id,
            profile_id=profile.profile_id,
            trace_id=request_trace_id(request),
        )
        start_command_job(store, job, spec)
        return {"job": job}

    @app.post("/api/evals/run")
    def start_eval_run(payload: StartEvalRunRequest, request: Request):
        profile = store.get_profile(payload.profile_id) if payload.profile_id else None
        if payload.profile_id and profile is None:
            raise HTTPException(status_code=404, detail=f"profile_not_found: {payload.profile_id}")
        job_id = payload.job_id or None
        output_path = eval_output_path(REPO_ROOT, eval_id=payload.eval_id, job_id=job_id or f"eval_{int(time.time())}")
        job = new_eval_run_job(
            eval_id=payload.eval_id,
            output_path=output_path,
            job_id=job_id,
            profile_id=profile.profile_id if profile else None,
            trace_id=request_trace_id(request),
            case_ids=payload.case_ids,
            prewarm_resident_tools=payload.prewarm_resident_tools,
        )
        output_path = eval_output_path(REPO_ROOT, eval_id=payload.eval_id, job_id=job.job_id)
        job = job.model_copy(update={"metadata": {**job.metadata, "output_path": str(output_path)}})
        try:
            spec = build_eval_command(
                repo_root=REPO_ROOT,
                eval_id=payload.eval_id,
                job_id=job.job_id,
                profile=profile,
                api_key_value=payload.api_key_value,
                case_ids=payload.case_ids,
                prewarm_resident_tools=payload.prewarm_resident_tools,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        start_command_job(store, job, spec)
        return {"job": job}

    return app


def _system_status_payload(
    *,
    store: WorkbenchStore,
    path_policy: WorkbenchPathPolicy,
    recovery_report: RunRecoveryReport,
) -> dict[str, object]:
    frontend_available = (FRONTEND_DIST_ROOT / "index.html").exists() or (FRONTEND_ROOT / "index.html").exists()
    store_health = store.inspect_health()
    runtime_preflight = inspect_runtime_preflight(REPO_ROOT)
    frontend_bundled = (FRONTEND_DIST_ROOT / "index.html").exists()
    deployment = inspect_deployment(
        repo_root=REPO_ROOT,
        frontend_bundled=frontend_bundled,
        path_policy=path_policy.report(),
        runtime_preflight=runtime_preflight,
    )
    path_status = {
        "repo_root": _path_status(REPO_ROOT),
        "data_root": _path_status(REPO_ROOT / "data"),
        "workbench_private": _path_status(REPO_ROOT / "data" / "workbench_private"),
        "frontend_root": _path_status(FRONTEND_ROOT),
        "frontend_dist": _path_status(FRONTEND_DIST_ROOT),
    }
    checks = {
        "store": store_health.status,
        "frontend": "available" if frontend_available else "missing",
        "repo_root": "ok" if path_status["repo_root"]["exists"] else "missing",
        "workbench_private": "ok" if path_status["workbench_private"]["writable"] else "not_writable",
        "runtime_preflight": runtime_preflight.status,
        "deployment": deployment.status,
    }
    critical_ok = (
        store_health.status == "ok"
        and checks["repo_root"] == "ok"
        and checks["workbench_private"] == "ok"
        and runtime_preflight.status == "ok"
        and deployment.status == "ok"
    )
    return {
        "status": "ok" if critical_ok else "degraded",
        "service": "finsight-workbench",
        "version": "0.1.0",
        "docker_required": False,
        "checks": checks,
        "store": store_health,
        "paths": path_status,
        "path_policy": path_policy.report(),
        "runtime_limits": runtime_limits_from_env(),
        "runtime_preflight": runtime_preflight,
        "deployment": deployment,
        "job_recovery": recovery_report,
    }


def _load_env_profile(
    env_path: str,
    *,
    profile_id: str | None,
    display_name: str | None,
    path_policy: WorkbenchPathPolicy,
) -> WorkbenchProfile:
    path = _repo_path(env_path, path_policy=path_policy)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"env_path_not_found: {env_path}")
    if not path.is_file():
        raise HTTPException(status_code=400, detail=f"env_path_not_file: {env_path}")
    return profile_from_env_file(path, profile_id=profile_id, display_name=display_name)


def _repo_path(value: str | Path, *, path_policy: WorkbenchPathPolicy) -> Path:
    try:
        return path_policy.resolve(value, base=REPO_ROOT)
    except PathPolicyViolation as exc:
        raise _path_policy_http_exception(exc) from exc


def _path_policy_http_exception(exc: PathPolicyViolation) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "reason": "path_not_allowed",
            "path": str(exc.path),
            "allowed_roots": [str(root) for root in exc.allowed_roots],
        },
    )


def _path_status(path: Path) -> dict[str, object]:
    target = path if path.exists() else path.parent
    if not target.exists():
        target = REPO_ROOT
    try:
        usage = shutil.disk_usage(target)
        total_bytes = int(usage.total)
        free_bytes = int(usage.free)
    except OSError:
        total_bytes = 0
        free_bytes = 0
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "writable": _path_writable(path),
        "total_bytes": total_bytes,
        "free_bytes": free_bytes,
    }


def _path_writable(path: Path) -> bool:
    target = path if path.exists() else path.parent
    if not target.exists():
        return False
    try:
        probe = target / ".workbench_api_write_check"
        probe.write_text("", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _resolve_run_profile(
    profile: WorkbenchProfile | None,
    profile_id: str | None,
    store: WorkbenchStore,
) -> WorkbenchProfile:
    if profile is not None:
        return profile
    if not profile_id:
        raise HTTPException(status_code=400, detail="profile_or_profile_id_required")
    saved = store.get_profile(profile_id)
    if saved is None:
        raise HTTPException(status_code=404, detail=f"profile_not_found: {profile_id}")
    return saved


def _optional_profile(
    profile: WorkbenchProfile | None,
    profile_id: str | None,
    store: WorkbenchStore,
) -> WorkbenchProfile | None:
    if profile is not None:
        return profile
    if not profile_id:
        return None
    saved = store.get_profile(profile_id)
    if saved is None:
        raise HTTPException(status_code=404, detail=f"profile_not_found: {profile_id}")
    return saved


def _resolve_profile_like(
    *,
    profile: WorkbenchProfile | None,
    env_path: str | None,
    profile_id: str | None,
    display_name: str | None,
    store: WorkbenchStore,
    path_policy: WorkbenchPathPolicy,
) -> WorkbenchProfile:
    if profile is not None:
        return profile
    if env_path:
        return _load_env_profile(env_path, profile_id=profile_id, display_name=display_name, path_policy=path_policy)
    if profile_id:
        saved = store.get_profile(profile_id)
        if saved is None:
            raise HTTPException(status_code=404, detail=f"profile_not_found: {profile_id}")
        return saved
    raise HTTPException(status_code=400, detail="profile_or_env_path_or_profile_id_required")


_DATA_BUILD_PATH_PARAMETERS = {
    "analytics",
    "bars",
    "cache_dir",
    "catalog_path",
    "chunks",
    "config",
    "contract",
    "events",
    "evidence",
    "gap_output",
    "input",
    "manifest",
    "manifest_paths",
    "missing_output",
    "output",
    "output_dir",
    "output_root",
    "report",
    "root",
    "snapshot",
    "structured_dir",
    "tickers_config",
}


def _validate_data_build_paths(
    step_id: str,
    values: dict[str, object],
    *,
    path_policy: WorkbenchPathPolicy,
) -> None:
    step = get_data_build_step(step_id)
    if step is None:
        return
    for parameter in step.parameters:
        if parameter.name not in _DATA_BUILD_PATH_PARAMETERS:
            continue
        value = values.get(parameter.name, parameter.default)
        for item in _iter_path_values(value):
            if _looks_like_non_file_reference(item):
                continue
            _repo_path(item, path_policy=path_policy)


def _iter_path_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _looks_like_non_file_reference(value: str) -> bool:
    text = value.strip()
    return not text or "://" in text or text.startswith("$")


def _inspect_native_checkpoint_if_available(run_dir: str | Path | None) -> dict | None:
    if not run_dir:
        return None
    root = Path(run_dir)
    checkpoint_path = root / "langgraph_node_checkpoints.json" if root.is_dir() else root
    if not checkpoint_path.exists():
        return None
    try:
        return inspect_node_checkpoint_artifact(root)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "schema_version": "sec_agent_langgraph_node_checkpoint_artifact_v0.1",
            "checkpoint_path": str(checkpoint_path),
            "run_id": "",
            "status": "invalid",
            "checkpoint_count": 0,
            "latest_checkpoint_id": "",
            "latest_completed_node": "",
            "next_recoverable_node": "",
            "required_artifacts_for_next_node": [],
            "resume_supported": False,
            "blocked_reasons": [str(exc)],
            "missing_required_artifacts": [],
            "digest_mismatch_artifacts": [],
            "recoverable_state_summary": {},
        }


def _event_stream(store: WorkbenchStore, job_id: str, *, after_sequence: int):
    cursor = after_sequence
    while True:
        events = store.list_run_events(job_id, after_sequence=cursor, limit=100)
        for event in events:
            cursor = event.sequence
            yield f"event: log\ndata: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"
        job = store.get_run_job(job_id)
        if job is None or job.status in {"completed", "failed", "cancelled", "interrupted", "timed_out"}:
            yield f"event: done\ndata: {json.dumps({'job_id': job_id, 'status': job.status if job else 'missing'}, ensure_ascii=False)}\n\n"
            break
        if not events:
            yield f"event: heartbeat\ndata: {json.dumps({'job_id': job_id, 'cursor': cursor}, ensure_ascii=False)}\n\n"
            time.sleep(1)


app = create_app()
