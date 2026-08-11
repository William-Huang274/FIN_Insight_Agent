from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Callable, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from sec_agent.workbench.agent_information_economy_projection import (
    build_agent_information_economy_projection,
)
from sec_agent.workbench.api_contracts import request_trace_id
from sec_agent.workbench.artifacts import inspect_run_artifacts
from sec_agent.workbench.data_build import (
    build_data_build_command,
    data_build_catalog,
)
from sec_agent.workbench.job_runner import (
    build_agent_ask_command,
    build_agent_session_turn_command,
    build_eval_command,
    build_local_smoke_command,
    build_native_checkpoint_resume_command,
    cancel_command_job,
    eval_output_path,
    eval_runner_catalog,
    start_command_job,
)
from sec_agent.workbench.jobs import (
    RunCancelReport,
    RunInspectionReport,
    RunStatusReport,
    new_agent_ask_job,
    new_agent_session_turn_job,
    new_data_build_job,
    new_eval_run_job,
    new_local_smoke_job,
    new_native_checkpoint_resume_job,
    new_saved_run_inspection_job,
)
from sec_agent.workbench.native_checkpoint_inspection import (
    inspect_native_checkpoint_artifact,
)
from sec_agent.workbench.profiles import WorkbenchProfile, profile_from_env_file
from sec_agent.workbench.source_bundles import (
    SourceBundle,
    profile_from_source_bundle,
    source_bundle_from_profile,
)
from sec_agent.workbench.source_readiness import validate_profile_sources
from sec_agent.workbench.store import (
    RunPruneReport,
    TraceInspectionReport,
    WorkbenchStore,
)


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
    require_full_source: bool | None = None


class ValidateSourceBundleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bundle: SourceBundle | None = None
    bundle_id: str | None = None
    require_full_source: bool | None = None


class ImportSourceBundleRequest(ValidateProfileRequest):
    bundle_id: str | None = None
    bundle_display_name: str | None = None


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


class CancelRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = "cancelled by operator"


class PruneRunHistoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keep_latest: int = Field(default=200, ge=0, le=10000)
    max_age_days: int | None = Field(default=None, ge=0, le=3650)
    terminal_only: bool = True
    dry_run: bool = True


class NativeCheckpointInspectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_dir: str


class NativeCheckpointResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_dir: str
    profile: WorkbenchProfile | None = None
    profile_id: str | None = None
    job_id: str | None = None
    include_synthesis: bool = True
    stop_after_node: str | None = None
    checkpoint_mode: Literal["memory", "sqlite", "none"] = "sqlite"


def build_operations_router(
    *,
    store: WorkbenchStore,
    repository_root: str | Path,
    system_status: Callable[[], dict[str, Any]],
) -> APIRouter:
    root = Path(repository_root).resolve()
    router = APIRouter(prefix="/operations", tags=["operations"])

    @router.get("/status", operation_id="getOperationsStatus")
    def get_status() -> dict[str, Any]:
        return system_status()

    @router.post("/profiles/import-env")
    def import_env(payload: ImportEnvRequest) -> WorkbenchProfile:
        return _load_env_profile(
            payload.env_path,
            profile_id=payload.profile_id,
            display_name=payload.display_name,
        )

    @router.get("/profiles")
    def list_profiles() -> dict[str, Any]:
        return {"profiles": store.list_profiles()}

    @router.post("/profiles")
    def save_profile(profile: WorkbenchProfile) -> Any:
        return store.upsert_profile(profile)

    @router.get("/profiles/{profile_id}")
    def get_profile(profile_id: str) -> WorkbenchProfile:
        profile = store.get_profile(profile_id)
        if profile is None:
            raise HTTPException(404, f"profile_not_found: {profile_id}")
        return profile

    @router.post("/profiles/validate")
    def validate_profile(payload: ValidateProfileRequest) -> Any:
        profile = _resolve_profile_like(
            profile=payload.profile,
            env_path=payload.env_path,
            profile_id=payload.profile_id,
            display_name=payload.display_name,
            store=store,
        )
        return validate_profile_sources(
            profile,
            repo_root=root,
            require_full_source=payload.require_full_source,
        )

    @router.get("/source-bundles")
    def list_source_bundles() -> dict[str, Any]:
        return {"bundles": store.list_source_bundles()}

    @router.post("/source-bundles")
    def save_source_bundle(bundle: SourceBundle) -> Any:
        return store.upsert_source_bundle(bundle)

    @router.get("/source-bundles/{bundle_id}")
    def get_source_bundle(bundle_id: str) -> SourceBundle:
        bundle = store.get_source_bundle(bundle_id)
        if bundle is None:
            raise HTTPException(404, f"source_bundle_not_found: {bundle_id}")
        return bundle

    @router.post("/source-bundles/import-profile")
    def import_source_bundle(payload: ImportSourceBundleRequest) -> dict[str, Any]:
        profile = _resolve_profile_like(
            profile=payload.profile,
            env_path=payload.env_path,
            profile_id=payload.profile_id,
            display_name=payload.display_name,
            store=store,
        )
        readiness = validate_profile_sources(
            profile,
            repo_root=root,
            require_full_source=payload.require_full_source,
        )
        bundle = source_bundle_from_profile(
            profile,
            readiness=readiness,
            bundle_id=payload.bundle_id,
            display_name=payload.bundle_display_name,
        )
        summary = store.upsert_source_bundle(bundle)
        return {"bundle": bundle, "summary": summary, "readiness": readiness}

    @router.post("/source-bundles/validate")
    def validate_source_bundle(payload: ValidateSourceBundleRequest) -> dict[str, Any]:
        bundle = payload.bundle
        if bundle is None and payload.bundle_id:
            bundle = store.get_source_bundle(payload.bundle_id)
        if bundle is None:
            raise HTTPException(404 if payload.bundle_id else 400, "source_bundle_not_found")
        readiness = validate_profile_sources(
            profile_from_source_bundle(bundle),
            repo_root=root,
            require_full_source=payload.require_full_source,
        )
        return {"bundle": bundle, "readiness": readiness}

    @router.get("/runs")
    def list_runs(
        trace_id: str | None = None,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = Query(200, ge=1, le=1000),
    ) -> dict[str, Any]:
        return {
            "runs": store.list_run_jobs(
                trace_id=trace_id,
                status=status,
                job_type=job_type,
                limit=limit,
            )
        }

    @router.get("/runs/{job_id}")
    def get_run(job_id: str) -> dict[str, Any]:
        job = store.get_run_job(job_id)
        if job is None:
            raise HTTPException(404, f"job_not_found: {job_id}")
        return {
            "job": job,
            "artifact_index": inspect_run_artifacts(job.run_dir) if job.run_dir else None,
            "native_checkpoint": _inspect_native_checkpoint_if_available(job.run_dir),
        }

    @router.get("/runs/{job_id}/status")
    def get_run_status(job_id: str) -> RunStatusReport:
        report = store.get_run_status(job_id)
        if report is None:
            raise HTTPException(404, f"job_not_found: {job_id}")
        return report

    @router.post("/runs/{job_id}/cancel")
    def cancel_run(job_id: str, payload: CancelRunRequest) -> RunCancelReport:
        report = cancel_command_job(
            store, job_id, reason=payload.reason.strip() or "cancelled by operator"
        )
        if report.status == "missing":
            raise HTTPException(404, f"job_not_found: {job_id}")
        return report

    @router.post("/runs/prune")
    def prune_runs(payload: PruneRunHistoryRequest) -> RunPruneReport:
        return store.prune_run_jobs(
            keep_latest=payload.keep_latest,
            max_age_days=payload.max_age_days,
            terminal_only=payload.terminal_only,
            dry_run=payload.dry_run,
        )

    @router.get("/runs/{job_id}/events")
    def get_run_events(
        job_id: str,
        after_sequence: int = Query(0, ge=0),
        limit: int = Query(500, ge=1, le=5000),
    ) -> dict[str, Any]:
        if store.get_run_job(job_id) is None:
            raise HTTPException(404, f"job_not_found: {job_id}")
        return {
            "events": store.list_run_events(
                job_id, after_sequence=after_sequence, limit=limit
            )
        }

    @router.get("/runs/{job_id}/events/stream")
    def stream_run_events(
        job_id: str, after_sequence: int = Query(0, ge=0)
    ) -> StreamingResponse:
        if store.get_run_job(job_id) is None:
            raise HTTPException(404, f"job_not_found: {job_id}")
        return StreamingResponse(
            _event_stream(store, job_id, after_sequence=after_sequence),
            media_type="text/event-stream",
        )

    @router.get("/traces/{trace_id}")
    def inspect_trace(
        trace_id: str,
        event_limit: int = Query(1000, ge=1, le=5000),
    ) -> TraceInspectionReport:
        report = store.inspect_trace(trace_id, event_limit=event_limit)
        if report.job_count == 0 and report.event_count == 0:
            raise HTTPException(404, f"trace_not_found: {trace_id}")
        return report

    @router.post("/runs/inspect")
    def inspect_run(payload: InspectRunRequest, request: Request) -> RunInspectionReport:
        run_dir = _rooted_path(root, payload.run_dir)
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
        return RunInspectionReport(
            job=job,
            artifact_index=artifact_index,
            native_checkpoint=native_checkpoint,
        )

    @router.post("/runs/smoke")
    def start_smoke_run(payload: StartSmokeRunRequest, request: Request) -> dict[str, Any]:
        job = new_local_smoke_job(
            job_id=payload.job_id,
            profile_id=payload.profile_id,
            trace_id=request_trace_id(request),
        )
        start_command_job(store, job, build_local_smoke_command(root))
        return {"job": job}

    @router.post("/runs/ask")
    def start_agent_ask(payload: StartAgentAskRequest, request: Request) -> dict[str, Any]:
        profile = _resolve_run_profile(payload.profile, payload.profile_id, store)
        try:
            spec = build_agent_ask_command(
                repo_root=root,
                profile=profile,
                prompt=payload.prompt,
                command_mode=payload.command_mode,
                api_key_value=None,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        job = new_agent_ask_job(
            prompt=payload.prompt.strip(),
            command_mode=payload.command_mode,
            job_id=payload.job_id,
            profile_id=profile.profile_id,
            trace_id=request_trace_id(request),
        )
        start_command_job(store, job, spec)
        return {"job": job}

    @router.get("/sessions")
    def list_sessions() -> dict[str, Any]:
        return {"sessions": store.list_sessions()}

    @router.get("/sessions/{session_id}/turns")
    def list_session_turns(session_id: str) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "turns": store.list_session_turn_jobs(session_id),
        }

    @router.post("/sessions/turns")
    def start_session_turn(payload: StartSessionTurnRequest, request: Request) -> dict[str, Any]:
        profile = _resolve_run_profile(payload.profile, payload.profile_id, store)
        try:
            spec = build_agent_session_turn_command(
                repo_root=root,
                profile=profile,
                prompt=payload.prompt,
                session_id=payload.session_id,
                tenant_id=payload.tenant_id,
                user_id=payload.user_id,
                command_mode=payload.command_mode,
                api_key_value=None,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
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

    @router.get("/evals")
    def list_evals() -> dict[str, Any]:
        return {"evals": eval_runner_catalog()}

    @router.get("/evals/dashboard")
    def eval_dashboard(limit: int = Query(50, ge=1, le=500)) -> Any:
        return store.eval_dashboard(limit=limit)

    @router.get("/evals/agent-information-economy")
    def eval_information_economy(limit: int = Query(12, ge=1, le=100)) -> Any:
        return build_agent_information_economy_projection(root, limit=limit)

    @router.post("/evals/run")
    def start_eval_run(payload: StartEvalRunRequest, request: Request) -> dict[str, Any]:
        profile = store.get_profile(payload.profile_id) if payload.profile_id else None
        if payload.profile_id and profile is None:
            raise HTTPException(404, f"profile_not_found: {payload.profile_id}")
        provisional = payload.job_id or f"eval_{int(time.time())}"
        output_path = eval_output_path(root, eval_id=payload.eval_id, job_id=provisional)
        job = new_eval_run_job(
            eval_id=payload.eval_id,
            output_path=output_path,
            job_id=payload.job_id,
            profile_id=profile.profile_id if profile else None,
            trace_id=request_trace_id(request),
        )
        output_path = eval_output_path(root, eval_id=payload.eval_id, job_id=job.job_id)
        job = job.model_copy(update={"metadata": {**job.metadata, "output_path": str(output_path)}})
        try:
            spec = build_eval_command(
                repo_root=root,
                eval_id=payload.eval_id,
                job_id=job.job_id,
                profile=profile,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        start_command_job(store, job, spec)
        return {"job": job}

    @router.get("/data-build/steps")
    def list_data_build_steps() -> dict[str, Any]:
        return {"steps": data_build_catalog()}

    @router.post("/data-build/preview")
    def preview_data_build(payload: DataBuildPreviewRequest) -> dict[str, Any]:
        profile = _optional_profile(payload.profile, payload.profile_id, store)
        try:
            _spec, preview = build_data_build_command(
                repo_root=root,
                step_id=payload.step_id,
                values=payload.values,
                profile=profile,
                dry_run=payload.dry_run,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"preview": preview}

    @router.post("/data-build/run")
    def run_data_build(payload: DataBuildRunRequest, request: Request) -> dict[str, Any]:
        profile = _optional_profile(payload.profile, payload.profile_id, store)
        try:
            spec, preview = build_data_build_command(
                repo_root=root,
                step_id=payload.step_id,
                values=payload.values,
                profile=profile,
                dry_run=payload.dry_run,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if preview.missing_required:
            raise HTTPException(
                400,
                {
                    "reason": "missing_required_parameters",
                    "missing_required": preview.missing_required,
                },
            )
        if payload.update_bundle and not payload.dry_run:
            if not payload.bundle_id:
                raise HTTPException(400, "bundle_id_required_for_update")
            if store.get_source_bundle(payload.bundle_id) is None:
                raise HTTPException(404, f"source_bundle_not_found: {payload.bundle_id}")
        job = new_data_build_job(
            step_id=preview.step_id,
            step_label=preview.label,
            command_preview=preview.args,
            bundle_id=(payload.bundle_id if payload.update_bundle and not payload.dry_run else None),
            bundle_artifact_updates=(preview.bundle_artifact_updates if payload.update_bundle and not payload.dry_run else {}),
            bundle_field_updates=(preview.bundle_field_updates if payload.update_bundle and not payload.dry_run else {}),
            job_id=payload.job_id,
            profile_id=profile.profile_id if profile else None,
            trace_id=request_trace_id(request),
        )
        start_command_job(store, job, spec)
        return {"job": job, "preview": preview}

    @router.post("/native-checkpoints/inspect")
    def inspect_native_checkpoint(payload: NativeCheckpointInspectRequest) -> dict[str, Any]:
        try:
            return inspect_native_checkpoint_artifact(
                _rooted_path(root, payload.run_dir)
            )
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/native-checkpoints/resume")
    def resume_native_checkpoint(payload: NativeCheckpointResumeRequest, request: Request) -> dict[str, Any]:
        checkpoint_path = _rooted_path(root, payload.run_dir)
        try:
            inspection = inspect_native_checkpoint_artifact(checkpoint_path)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc
        if not inspection.get("resume_supported"):
            raise HTTPException(409, {"reason": "native_checkpoint_not_resumable", "inspection": inspection})
        profile = _resolve_run_profile(payload.profile, payload.profile_id, store)
        try:
            spec = build_native_checkpoint_resume_command(
                repo_root=root,
                profile=profile,
                checkpoint_path=checkpoint_path,
                api_key_value=None,
                include_synthesis=payload.include_synthesis,
                stop_after_node=payload.stop_after_node,
                checkpoint_mode=payload.checkpoint_mode,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
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

    return router


def _load_env_profile(
    env_path: str,
    *,
    profile_id: str | None,
    display_name: str | None,
) -> WorkbenchProfile:
    path = Path(env_path).resolve()
    if not path.exists():
        raise HTTPException(404, f"env_path_not_found: {env_path}")
    if not path.is_file():
        raise HTTPException(400, f"env_path_not_file: {env_path}")
    return profile_from_env_file(
        path, profile_id=profile_id, display_name=display_name
    )


def _resolve_run_profile(
    profile: WorkbenchProfile | None,
    profile_id: str | None,
    store: WorkbenchStore,
) -> WorkbenchProfile:
    if profile is not None:
        return profile
    if not profile_id:
        raise HTTPException(400, "profile_or_profile_id_required")
    saved = store.get_profile(profile_id)
    if saved is None:
        raise HTTPException(404, f"profile_not_found: {profile_id}")
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
        raise HTTPException(404, f"profile_not_found: {profile_id}")
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
        return _load_env_profile(
            env_path, profile_id=profile_id, display_name=display_name
        )
    if profile_id:
        saved = store.get_profile(profile_id)
        if saved is None:
            raise HTTPException(404, f"profile_not_found: {profile_id}")
        return saved
    raise HTTPException(400, "profile_or_env_path_or_profile_id_required")


def _rooted_path(repository_root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (repository_root / path).resolve()


def _inspect_native_checkpoint_if_available(
    run_dir: str | Path | None,
) -> dict[str, Any] | None:
    if not run_dir:
        return None
    root = Path(run_dir)
    checkpoint_path = root / "langgraph_node_checkpoints.json" if root.is_dir() else root
    if not checkpoint_path.exists():
        return None
    try:
        return inspect_native_checkpoint_artifact(root)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "schema_version": "sec_agent_langgraph_node_checkpoint_artifact_v0.1",
            "checkpoint_path": str(checkpoint_path),
            "status": "invalid",
            "resume_supported": False,
            "blocked_reasons": [str(exc)],
        }


def _event_stream(
    store: WorkbenchStore,
    job_id: str,
    *,
    after_sequence: int,
):
    cursor = after_sequence
    while True:
        events = store.list_run_events(job_id, after_sequence=cursor, limit=100)
        for event in events:
            cursor = event.sequence
            yield (
                "event: log\ndata: "
                + json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
                + "\n\n"
            )
        job = store.get_run_job(job_id)
        if job is None or job.status in {
            "completed",
            "succeeded",
            "failed",
            "cancelled",
            "timed_out",
        }:
            yield (
                "event: done\ndata: "
                + json.dumps(
                    {
                        "job_id": job_id,
                        "status": job.status if job else "missing",
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )
            break
        if not events:
            yield (
                "event: heartbeat\ndata: "
                + json.dumps({"job_id": job_id, "cursor": cursor})
                + "\n\n"
            )
            time.sleep(1)


__all__ = ["build_operations_router"]
