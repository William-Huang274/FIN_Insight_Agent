from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import time
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from sec_agent.workbench.api_contracts import request_trace_id
from sec_agent.workbench.artifacts import inspect_run_artifacts
from sec_agent.workbench.data_build import (
    build_data_build_command,
    data_build_catalog,
)
from sec_agent.workbench.jobs import (
    RunCancelReport,
    RunInspectionReport,
    RunStatusReport,
    new_data_build_job,
    new_eval_run_job,
    new_local_smoke_job,
    new_saved_run_inspection_job,
)
from sec_agent.workbench.process_runner import (
    build_active_baseline_verification_command,
    build_local_smoke_command,
    cancel_command_job,
    start_command_job,
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
from sec_agent.runtime_resource_registry import read_registered_runtime_json


ACTIVE_BASELINE_EVAL_ID = "active_baseline_import_graph"
CURRENT_S1_VS2_COMPLEX_PDF_RESOURCE_ID = (
    "application.result.current_s1_vs2_complex_pdf_vertical"
)
CURRENT_S1_VS3_RETRIEVAL_RESOURCE_ID = (
    "application.result.current_s1_vs3_retrieval_vertical"
)
CURRENT_S1_VS4_SUPPLEMENT_RESOURCE_ID = (
    "application.result.current_s1_vs4_supplement_vertical"
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


class StartBaselineEvalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eval_id: str = ACTIVE_BASELINE_EVAL_ID
    job_id: str | None = None


class CancelRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = "cancelled by operator"


class PruneRunHistoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keep_latest: int = Field(default=200, ge=0, le=10000)
    max_age_days: int | None = Field(default=None, ge=0, le=3650)
    terminal_only: bool = True
    dry_run: bool = True


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

    @router.get(
        "/s1/complex-document-quality",
        operation_id="getS1ComplexDocumentQuality",
    )
    def get_s1_complex_document_quality() -> dict[str, Any]:
        result = read_registered_runtime_json(
            root, CURRENT_S1_VS2_COMPLEX_PDF_RESOURCE_ID
        )
        evaluation = result.get("evaluation") or {}
        projection = evaluation.get("workbench_projection") or {}
        return {
            **dict(projection),
            "result_digest": result.get("result_digest"),
            "stage_acceptance": deepcopy(result.get("stage_acceptance") or {}),
            "business_result": deepcopy(result.get("business_result") or {}),
        }

    @router.get(
        "/s1/retrieval-quality",
        operation_id="getS1RetrievalQuality",
    )
    def get_s1_retrieval_quality() -> dict[str, Any]:
        result = read_registered_runtime_json(
            root, CURRENT_S1_VS3_RETRIEVAL_RESOURCE_ID
        )
        return {
            "schema_version": result.get("schema_version"),
            "status": result.get("status"),
            "slice_id": result.get("slice_id"),
            "summary": deepcopy(result.get("summary") or {}),
            "gate_results": deepcopy(result.get("gate_results") or {}),
            "atom_summaries": deepcopy(result.get("atom_summaries") or []),
            "decision": deepcopy(result.get("decision") or {}),
            "business_findings": deepcopy(result.get("business_findings") or []),
            "authority": deepcopy(result.get("authority") or {}),
            "result_digest": result.get("result_digest"),
        }

    @router.get(
        "/s1/supplement-quality",
        operation_id="getS1SupplementQuality",
    )
    def get_s1_supplement_quality() -> dict[str, Any]:
        result = read_registered_runtime_json(
            root, CURRENT_S1_VS4_SUPPLEMENT_RESOURCE_ID
        )
        raw_case_summaries = result.get("case_summaries")
        if isinstance(raw_case_summaries, dict):
            ordered_keys = [
                key
                for key in ("DELL", "MU", "NVDA")
                if key in raw_case_summaries
            ] + sorted(
                key
                for key in raw_case_summaries
                if key not in {"DELL", "MU", "NVDA"}
            )
            case_summaries = []
            for case_key in ordered_keys:
                summary = dict(raw_case_summaries[case_key])
                projection = dict(summary.get("workbench_projection") or {})
                case_summaries.append(
                    {
                        "case_key": case_key,
                        "slice_id": summary.get("slice_id"),
                        "coverage_delta": deepcopy(
                            summary.get("coverage_delta") or {}
                        ),
                        "proposition_rows": deepcopy(
                            summary.get("proposition_rows")
                            or projection.get("propositions")
                            or []
                        ),
                        "gate_results": deepcopy(
                            summary.get("gate_results") or {}
                        ),
                        "decision": deepcopy(summary.get("decision") or {}),
                        "business_findings": deepcopy(
                            summary.get("business_findings") or []
                        ),
                        "authority": deepcopy(summary.get("authority") or {}),
                        "result_digest": summary.get("result_digest"),
                    }
                )
            return {
                "schema_version": result.get("schema_version"),
                "status": result.get("status"),
                "case_summaries": case_summaries,
                "decision": deepcopy(result.get("decision") or {}),
                "summary_set_digest": result.get("summary_set_digest"),
            }
        return {
            "schema_version": result.get("schema_version"),
            "status": result.get("status"),
            "case_summaries": [
                {
                    "case_key": "DELL",
                    "slice_id": result.get("slice_id"),
                    "coverage_delta": deepcopy(
                        result.get("coverage_delta") or {}
                    ),
                    "proposition_rows": deepcopy(
                        result.get("proposition_rows") or []
                    ),
                    "gate_results": deepcopy(
                        result.get("gate_results") or {}
                    ),
                    "decision": deepcopy(result.get("decision") or {}),
                    "business_findings": deepcopy(
                        result.get("business_findings") or []
                    ),
                    "authority": deepcopy(result.get("authority") or {}),
                    "result_digest": result.get("result_digest"),
                }
            ],
            "decision": deepcopy(result.get("decision") or {}),
            "summary_set_digest": result.get("result_digest"),
        }

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
        return {
            "bundle": bundle,
            "summary": store.upsert_source_bundle(bundle),
            "readiness": readiness,
        }

    @router.post("/source-bundles/validate")
    def validate_source_bundle(payload: ValidateSourceBundleRequest) -> dict[str, Any]:
        bundle = payload.bundle
        if bundle is None and payload.bundle_id:
            bundle = store.get_source_bundle(payload.bundle_id)
        if bundle is None:
            raise HTTPException(
                404 if payload.bundle_id else 400,
                "source_bundle_not_found",
            )
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
            "artifact_index": (
                inspect_run_artifacts(job.run_dir) if job.run_dir else None
            ),
        }

    @router.get("/runs/{job_id}/status")
    def get_run_status(job_id: str) -> RunStatusReport:
        report = store.get_run_status(job_id)
        if report is None:
            raise HTTPException(404, f"job_not_found: {job_id}")
        return report

    @router.post("/runs/{job_id}/cancel")
    def cancel_run(
        job_id: str, payload: CancelRunRequest
    ) -> RunCancelReport:
        report = cancel_command_job(
            store,
            job_id,
            reason=payload.reason.strip() or "cancelled by operator",
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
                job_id,
                after_sequence=after_sequence,
                limit=limit,
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
    def inspect_run(
        payload: InspectRunRequest, request: Request
    ) -> RunInspectionReport:
        run_dir = _rooted_path(root, payload.run_dir)
        artifact_index = inspect_run_artifacts(run_dir)
        job = new_saved_run_inspection_job(
            run_dir=run_dir,
            artifact_index=artifact_index,
            job_id=payload.job_id,
            profile_id=payload.profile_id,
            trace_id=request_trace_id(request),
        )
        if payload.persist:
            store.upsert_run_job(job)
        return RunInspectionReport(job=job, artifact_index=artifact_index)

    @router.post("/runs/smoke")
    def start_smoke_run(
        payload: StartSmokeRunRequest, request: Request
    ) -> dict[str, Any]:
        job = new_local_smoke_job(
            job_id=payload.job_id,
            profile_id=payload.profile_id,
            trace_id=request_trace_id(request),
        )
        start_command_job(store, job, build_local_smoke_command(root))
        return {"job": job}

    @router.get("/evals")
    def list_evals() -> dict[str, Any]:
        return {
            "evals": [
                {
                    "eval_id": ACTIVE_BASELINE_EVAL_ID,
                    "label": "Active baseline import graph",
                    "description": (
                        "Proves that current backend, frontend and runtime "
                        "resources have no old product consumer."
                    ),
                    "runner": "scripts/engineering/verify_active_baseline.py",
                }
            ]
        }

    @router.post("/evals/run")
    def start_baseline_eval(
        payload: StartBaselineEvalRequest, request: Request
    ) -> dict[str, Any]:
        if payload.eval_id != ACTIVE_BASELINE_EVAL_ID:
            raise HTTPException(400, f"unsupported_eval_id: {payload.eval_id}")
        job = new_eval_run_job(
            eval_id=payload.eval_id,
            output_path="",
            job_id=payload.job_id,
            trace_id=request_trace_id(request),
        )
        start_command_job(
            store,
            job,
            build_active_baseline_verification_command(root),
        )
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
    def run_data_build(
        payload: DataBuildRunRequest, request: Request
    ) -> dict[str, Any]:
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
                raise HTTPException(
                    404,
                    f"source_bundle_not_found: {payload.bundle_id}",
                )
        job = new_data_build_job(
            step_id=preview.step_id,
            step_label=preview.label,
            command_preview=preview.args,
            bundle_id=(
                payload.bundle_id
                if payload.update_bundle and not payload.dry_run
                else None
            ),
            bundle_artifact_updates=(
                preview.bundle_artifact_updates
                if payload.update_bundle and not payload.dry_run
                else {}
            ),
            bundle_field_updates=(
                preview.bundle_field_updates
                if payload.update_bundle and not payload.dry_run
                else {}
            ),
            job_id=payload.job_id,
            profile_id=profile.profile_id if profile else None,
            trace_id=request_trace_id(request),
        )
        start_command_job(store, job, spec)
        return {"job": job, "preview": preview}

    @router.api_route(
        "/{retired_family:path}",
        methods=["DELETE", "PATCH"],
        include_in_schema=False,
    )
    def unsupported_mutation(retired_family: str) -> JSONResponse:
        return _retired_operations_response(retired_family)

    for retired_path in (
        "/runs/ask",
        "/sessions",
        "/sessions/{retired_path:path}",
        "/native-checkpoints/{retired_path:path}",
        "/evals/agent-information-economy",
    ):
        router.add_api_route(
            retired_path,
            _retired_operations_response,
            methods=["GET", "POST", "PATCH"],
            include_in_schema=False,
        )

    return router


def _retired_operations_response(
    retired_path: str = "",
) -> JSONResponse:
    return JSONResponse(
        status_code=410,
        content={
            "reason": "operation_not_admitted_in_current_baseline",
            "retired_path": retired_path,
            "replacement": (
                "Promote the capability through the current Runtime contract, "
                "active import graph and product acceptance before exposing it."
            ),
        },
    )


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
        path,
        profile_id=profile_id,
        display_name=display_name,
    )


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
            env_path,
            profile_id=profile_id,
            display_name=display_name,
        )
    if profile_id:
        saved = store.get_profile(profile_id)
        if saved is None:
            raise HTTPException(404, f"profile_not_found: {profile_id}")
        return saved
    raise HTTPException(400, "profile_or_env_path_or_profile_id_required")


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


def _rooted_path(repository_root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (repository_root / path).resolve()


def _event_stream(
    store: WorkbenchStore,
    job_id: str,
    *,
    after_sequence: int,
):
    cursor = after_sequence
    while True:
        events = store.list_run_events(
            job_id,
            after_sequence=cursor,
            limit=100,
        )
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


__all__ = ["ACTIVE_BASELINE_EVAL_ID", "build_operations_router"]
