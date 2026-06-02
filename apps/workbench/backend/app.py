from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from sec_agent.workbench import (
    RunInspectionReport,
    SourceBundle,
    WorkbenchProfile,
    WorkbenchStore,
    build_data_build_command,
    build_agent_ask_command,
    build_agent_session_turn_command,
    build_eval_command,
    build_local_smoke_command,
    build_native_checkpoint_resume_command,
    default_store_path,
    data_build_catalog,
    eval_output_path,
    eval_runner_catalog,
    inspect_run_artifacts,
    new_agent_ask_job,
    new_agent_session_turn_job,
    new_data_build_job,
    new_eval_run_job,
    new_local_smoke_job,
    new_native_checkpoint_resume_job,
    new_saved_run_inspection_job,
    profile_from_env_file,
    profile_from_source_bundle,
    source_bundle_from_profile,
    start_command_job,
    validate_profile_sources,
)
from sec_agent.langgraph_orchestrator import inspect_node_checkpoint_artifact


APP_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = APP_ROOT / "frontend"
FRONTEND_DIST_ROOT = FRONTEND_ROOT / "dist"
REPO_ROOT = Path(__file__).resolve().parents[3]


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


class DataBuildRunRequest(DataBuildPreviewRequest):
    job_id: str | None = None
    bundle_id: str | None = None
    update_bundle: bool = False


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


def create_app(store_path: str | Path | None = None) -> FastAPI:
    store = WorkbenchStore(store_path or default_store_path(REPO_ROOT))
    app = FastAPI(
        title="FinSight Workbench API",
        version="0.1.0",
        description="Local API for FinSight-Agent profile import and source readiness checks.",
    )
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

    @app.post("/api/profiles/import-env")
    def import_env(request: ImportEnvRequest) -> WorkbenchProfile:
        return _load_env_profile(
            request.env_path,
            profile_id=request.profile_id,
            display_name=request.display_name,
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
        )
        repo_root = Path(request.repo_root).resolve() if request.repo_root else REPO_ROOT
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
        repo_root = Path(request.repo_root).resolve() if request.repo_root else REPO_ROOT
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
                )
            elif request.profile_id:
                profile = store.get_profile(request.profile_id)
                if profile is None:
                    raise HTTPException(status_code=404, detail=f"profile_not_found: {request.profile_id}")
            else:
                raise HTTPException(status_code=400, detail="profile_or_env_path_required")
        repo_root = Path(request.repo_root).resolve() if request.repo_root else Path.cwd().resolve()
        return validate_profile_sources(
            profile,
            repo_root=repo_root,
            require_full_source=request.require_full_source,
        )

    @app.get("/api/runs")
    def list_runs():
        return {"runs": store.list_run_jobs()}

    @app.get("/api/evals")
    def list_evals():
        return {"evals": eval_runner_catalog()}

    @app.get("/api/data-build/steps")
    def list_data_build_steps():
        return {"steps": data_build_catalog()}

    @app.post("/api/data-build/preview")
    def preview_data_build(request: DataBuildPreviewRequest):
        profile = _optional_profile(request.profile, request.profile_id, store)
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
    def run_data_build(request: DataBuildRunRequest):
        profile = _optional_profile(request.profile, request.profile_id, store)
        try:
            spec, preview = build_data_build_command(
                repo_root=REPO_ROOT,
                step_id=request.step_id,
                values=request.values,
                profile=profile,
                dry_run=request.dry_run,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if preview.missing_required:
            raise HTTPException(
                status_code=400,
                detail={"reason": "missing_required_parameters", "missing_required": preview.missing_required},
            )
        if request.update_bundle and not request.dry_run:
            if not request.bundle_id:
                raise HTTPException(status_code=400, detail="bundle_id_required_for_update")
            if store.get_source_bundle(request.bundle_id) is None:
                raise HTTPException(status_code=404, detail=f"source_bundle_not_found: {request.bundle_id}")
        job = new_data_build_job(
            step_id=preview.step_id,
            step_label=preview.label,
            command_preview=preview.args,
            bundle_id=request.bundle_id if request.update_bundle and not request.dry_run else None,
            bundle_artifact_updates=preview.bundle_artifact_updates if request.update_bundle and not request.dry_run else {},
            bundle_field_updates=preview.bundle_field_updates if request.update_bundle and not request.dry_run else {},
            job_id=request.job_id,
            profile_id=profile.profile_id if profile else None,
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

    @app.get("/api/runs/{job_id}/events")
    def get_run_events(job_id: str, after_sequence: int = 0, limit: int = 500):
        if store.get_run_job(job_id) is None:
            raise HTTPException(status_code=404, detail=f"job_not_found: {job_id}")
        return {"events": store.list_run_events(job_id, after_sequence=after_sequence, limit=limit)}

    @app.get("/api/runs/{job_id}/events/stream")
    def stream_run_events(job_id: str, after_sequence: int = 0):
        if store.get_run_job(job_id) is None:
            raise HTTPException(status_code=404, detail=f"job_not_found: {job_id}")
        return StreamingResponse(
            _event_stream(store, job_id, after_sequence=after_sequence),
            media_type="text/event-stream",
        )

    @app.post("/api/runs/inspect")
    def inspect_run(request: InspectRunRequest) -> RunInspectionReport:
        run_dir = _repo_path(request.run_dir)
        artifact_index = inspect_run_artifacts(run_dir)
        native_checkpoint = _inspect_native_checkpoint_if_available(run_dir)
        job = new_saved_run_inspection_job(
            run_dir=run_dir,
            artifact_index=artifact_index,
            job_id=request.job_id,
            profile_id=request.profile_id,
        )
        if request.persist:
            store.upsert_run_job(job)
        return RunInspectionReport(job=job, artifact_index=artifact_index, native_checkpoint=native_checkpoint)

    @app.post("/api/native-checkpoints/inspect")
    def inspect_native_checkpoint(request: NativeCheckpointInspectRequest):
        try:
            return inspect_node_checkpoint_artifact(_repo_path(request.run_dir))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/native-checkpoints/resume")
    def resume_native_checkpoint(request: NativeCheckpointResumeRequest):
        checkpoint_path = _repo_path(request.run_dir)
        try:
            inspection = inspect_node_checkpoint_artifact(checkpoint_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not inspection.get("resume_supported"):
            raise HTTPException(status_code=409, detail={"reason": "native_checkpoint_not_resumable", "inspection": inspection})
        profile = _resolve_run_profile(request.profile, request.profile_id, store)
        try:
            spec = build_native_checkpoint_resume_command(
                repo_root=REPO_ROOT,
                profile=profile,
                checkpoint_path=checkpoint_path,
                api_key_value=request.api_key_value,
                include_synthesis=request.include_synthesis,
                stop_after_node=request.stop_after_node,
                checkpoint_mode=request.checkpoint_mode,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        job = new_native_checkpoint_resume_job(
            checkpoint_path=checkpoint_path,
            profile_id=profile.profile_id,
            job_id=request.job_id,
            stop_after_node=request.stop_after_node,
            include_synthesis=request.include_synthesis,
        )
        start_command_job(store, job, spec)
        return {"job": job, "inspection": inspection}

    @app.post("/api/runs/smoke")
    def start_smoke_run(request: StartSmokeRunRequest):
        job = new_local_smoke_job(job_id=request.job_id, profile_id=request.profile_id)
        spec = build_local_smoke_command(REPO_ROOT)
        start_command_job(store, job, spec)
        return {"job": job}

    @app.post("/api/runs/ask")
    def start_agent_ask(request: StartAgentAskRequest):
        profile = _resolve_run_profile(request.profile, request.profile_id, store)
        try:
            spec = build_agent_ask_command(
                repo_root=REPO_ROOT,
                profile=profile,
                prompt=request.prompt,
                command_mode=request.command_mode,
                api_key_value=request.api_key_value,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        job = new_agent_ask_job(
            prompt=request.prompt.strip(),
            command_mode=request.command_mode,
            job_id=request.job_id,
            profile_id=profile.profile_id,
        )
        start_command_job(store, job, spec)
        return {"job": job}

    @app.post("/api/sessions/turns")
    def start_session_turn(request: StartSessionTurnRequest):
        profile = _resolve_run_profile(request.profile, request.profile_id, store)
        try:
            spec = build_agent_session_turn_command(
                repo_root=REPO_ROOT,
                profile=profile,
                prompt=request.prompt,
                session_id=request.session_id,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                command_mode=request.command_mode,
                api_key_value=request.api_key_value,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        job = new_agent_session_turn_job(
            prompt=request.prompt.strip(),
            command_mode=request.command_mode,
            session_id=request.session_id.strip(),
            tenant_id=request.tenant_id.strip() or "workbench_tenant",
            user_id=request.user_id.strip() or "workbench_user",
            job_id=request.job_id,
            profile_id=profile.profile_id,
        )
        start_command_job(store, job, spec)
        return {"job": job}

    @app.post("/api/evals/run")
    def start_eval_run(request: StartEvalRunRequest):
        profile = store.get_profile(request.profile_id) if request.profile_id else None
        if request.profile_id and profile is None:
            raise HTTPException(status_code=404, detail=f"profile_not_found: {request.profile_id}")
        job_id = request.job_id or None
        output_path = eval_output_path(REPO_ROOT, eval_id=request.eval_id, job_id=job_id or f"eval_{int(time.time())}")
        job = new_eval_run_job(
            eval_id=request.eval_id,
            output_path=output_path,
            job_id=job_id,
            profile_id=profile.profile_id if profile else None,
        )
        output_path = eval_output_path(REPO_ROOT, eval_id=request.eval_id, job_id=job.job_id)
        job = job.model_copy(update={"metadata": {**job.metadata, "output_path": str(output_path)}})
        try:
            spec = build_eval_command(
                repo_root=REPO_ROOT,
                eval_id=request.eval_id,
                job_id=job.job_id,
                profile=profile,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        start_command_job(store, job, spec)
        return {"job": job}

    return app


def _load_env_profile(env_path: str, *, profile_id: str | None, display_name: str | None) -> WorkbenchProfile:
    path = Path(env_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"env_path_not_found: {env_path}")
    if not path.is_file():
        raise HTTPException(status_code=400, detail=f"env_path_not_file: {env_path}")
    return profile_from_env_file(path, profile_id=profile_id, display_name=display_name)


def _repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


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
) -> WorkbenchProfile:
    if profile is not None:
        return profile
    if env_path:
        return _load_env_profile(env_path, profile_id=profile_id, display_name=display_name)
    if profile_id:
        saved = store.get_profile(profile_id)
        if saved is None:
            raise HTTPException(status_code=404, detail=f"profile_not_found: {profile_id}")
        return saved
    raise HTTPException(status_code=400, detail="profile_or_env_path_or_profile_id_required")


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
        if job is None or job.status in {"completed", "failed", "cancelled"}:
            yield f"event: done\ndata: {json.dumps({'job_id': job_id, 'status': job.status if job else 'missing'}, ensure_ascii=False)}\n\n"
            break
        if not events:
            yield f"event: heartbeat\ndata: {json.dumps({'job_id': job_id, 'cursor': cursor}, ensure_ascii=False)}\n\n"
            time.sleep(1)


app = create_app()
