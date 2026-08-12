from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from sec_agent.runtime_bridge.paths import RuntimePathRegistry, resolve_runtime_paths
from sec_agent.workbench.api_contracts import install_api_contracts
from sec_agent.workbench.store import WorkbenchStore, default_store_path

from .api.operations import build_operations_router
from .api.v1.research_evidence_packs import build_research_evidence_pack_router
from .api.v1.research_retrieval import build_research_retrieval_router
from .api.v1.research_workspace import build_research_workspace_router
from .application.research_evidence_pack_service import ResearchEvidencePackService
from .application.research_retrieval_service import ResearchRetrievalService
from .application.research_workspace_service import ResearchWorkspaceService


APP_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = APP_ROOT / "frontend"
FRONTEND_DIST_ROOT = FRONTEND_ROOT / "dist"
CODE_ROOT = Path(
    os.environ.get(
        "FINSIGHT_WORKBENCH_REPO_ROOT",
        Path(__file__).resolve().parents[3],
    )
).resolve()


def create_app(
    store_path: str | Path | None = None,
    current_research_evidence_pack_service: ResearchEvidencePackService | None = None,
    research_workspace_service: ResearchWorkspaceService | None = None,
    research_retrieval_service: ResearchRetrievalService | None = None,
    workbench_runtime_mode: Literal["current", "fixture"] = "current",
    frontend_dist_root: str | Path | None = None,
    **retired_product_services: object,
) -> FastAPI:
    """Compose the only active FIN 0.1.3 product and operator surfaces.

    Retired Point02/03, FIN 0.1.2 and r53-r60 services are deliberately not
    imported.  A stale caller may still reach this signature, but a non-null
    retired injection fails explicitly instead of silently rebuilding the old
    product graph.
    """

    if workbench_runtime_mode not in {"current", "fixture"}:
        raise ValueError("workbench_runtime_mode_invalid")
    supplied_retired = sorted(
        key for key, value in retired_product_services.items() if value is not None
    )
    if supplied_retired:
        raise ValueError(
            "retired_product_service_injection_forbidden:"
            + ",".join(supplied_retired)
        )

    runtime_paths = resolve_runtime_paths(CODE_ROOT)
    resolved_frontend_dist_root = Path(
        frontend_dist_root or FRONTEND_DIST_ROOT
    ).resolve()
    store = WorkbenchStore(
        store_path
        or default_store_path(
            CODE_ROOT,
            workbench_private_root=runtime_paths.workbench_private_root,
        )
    )
    evidence_packs = (
        current_research_evidence_pack_service
        or ResearchEvidencePackService.from_runtime_paths(CODE_ROOT, runtime_paths)
    )
    workspace = research_workspace_service
    if workspace is None and current_research_evidence_pack_service is None:
        workspace = ResearchWorkspaceService.from_runtime_paths(
            CODE_ROOT, evidence_packs
        )
    retrieval = research_retrieval_service
    if retrieval is None and current_research_evidence_pack_service is None:
        retrieval = ResearchRetrievalService.from_runtime_paths(
            CODE_ROOT,
            runtime_paths=runtime_paths,
        )

    app = FastAPI(
        title="FinSight Research Workbench API",
        version="0.1.3",
        description=(
            "Identity-bound reviewed research workspace and isolated operator API."
        ),
    )
    app.state.workbench_runtime_mode = workbench_runtime_mode
    app.state.runtime_paths = runtime_paths
    app.state.primary_product_route = "/workspace"
    app.state.operator_route = "/operations"
    app.state.retired_product_runtime_loaded = False
    install_api_contracts(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(
        build_research_evidence_pack_router(evidence_packs), prefix="/api/v1"
    )
    if workspace is not None:
        app.include_router(
            build_research_workspace_router(workspace), prefix="/api/v1"
        )
    if retrieval is not None:
        app.include_router(
            build_research_retrieval_router(retrieval), prefix="/api/v1"
        )

    def system_status() -> dict[str, Any]:
        return _system_status(
            store=store,
            runtime_paths=runtime_paths,
            evidence_packs=evidence_packs,
            fixture_mode=workbench_runtime_mode == "fixture",
            frontend_dist_root=resolved_frontend_dist_root,
        )

    app.include_router(
        build_operations_router(
            store=store,
            repository_root=CODE_ROOT,
            system_status=system_status,
        ),
        prefix="/api",
    )

    if (resolved_frontend_dist_root / "assets").exists():
        app.mount(
            "/assets",
            StaticFiles(directory=resolved_frontend_dist_root / "assets"),
            name="assets",
        )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "finsight-workbench",
            "version": "0.1.3",
            "primary_product_route": "/workspace",
            "operator_route": "/operations",
        }

    @app.get("/api/readiness")
    def readiness() -> JSONResponse:
        result = _evidence_pack_readiness(
            evidence_packs,
            fixture_mode=workbench_runtime_mode == "fixture",
        )
        return JSONResponse(
            status_code=200 if result["all_ready"] else 503,
            content={
                **result,
                "service": "finsight-workbench",
                "required_data_env": "FINSIGHT_DATA_ROOT",
            },
        )

    @app.get("/api/system/status", include_in_schema=False)
    def retired_system_status_alias() -> RedirectResponse:
        return RedirectResponse("/api/operations/status", status_code=307)

    @app.get("/", include_in_schema=False)
    def root_redirect() -> RedirectResponse:
        return RedirectResponse("/workspace", status_code=307)

    @app.get("/workspace", response_class=HTMLResponse, include_in_schema=False)
    @app.get(
        "/workspace/{frontend_path:path}",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    def workspace_entrypoint(frontend_path: str = "") -> str:
        return _frontend_index(resolved_frontend_dist_root)

    @app.get("/operations", response_class=HTMLResponse, include_in_schema=False)
    @app.get(
        "/operations/{frontend_path:path}",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    def operations_entrypoint(frontend_path: str = "") -> str:
        return _frontend_index(resolved_frontend_dist_root)

    @app.get("/legacy", include_in_schema=False)
    @app.get("/legacy/{frontend_path:path}", include_in_schema=False)
    def legacy_frontend_redirect(frontend_path: str = "") -> RedirectResponse:
        return RedirectResponse("/operations", status_code=308)

    @app.get("/current", include_in_schema=False)
    @app.get("/current/{frontend_path:path}", include_in_schema=False)
    @app.get("/next", include_in_schema=False)
    @app.get("/next/{frontend_path:path}", include_in_schema=False)
    @app.get("/tasks", include_in_schema=False)
    @app.get("/cases", include_in_schema=False)
    @app.get("/cases/{frontend_path:path}", include_in_schema=False)
    def retired_product_frontend_redirect(
        frontend_path: str = "",
    ) -> RedirectResponse:
        return RedirectResponse("/workspace", status_code=308)

    @app.api_route(
        "/api/r53-r60/{retired_path:path}",
        methods=["GET", "POST", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    def retired_r53_api(retired_path: str) -> JSONResponse:
        return _retired_api_response(
            family="r53_r60_product_surface",
            replacement="/api/v1/research-cases",
        )

    @app.api_route(
        "/api/v1/current-product/{retired_path:path}",
        methods=["GET", "POST", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    def retired_current_product_api(retired_path: str) -> JSONResponse:
        return _retired_api_response(
            family="fin_0_1_2_current_product",
            replacement="/api/v1/research-cases",
        )

    @app.api_route(
        "/api/v1/cases/{retired_path:path}",
        methods=["GET", "POST", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    def retired_fixture_case_api(retired_path: str) -> JSONResponse:
        return _retired_api_response(
            family="point02_fixture_case",
            replacement="/api/v1/research-cases",
        )

    return app


def _frontend_index(frontend_dist_root: Path) -> str:
    path = frontend_dist_root / "index.html"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    raise HTTPException(status_code=503, detail="frontend_not_built")


def _system_status(
    *,
    store: WorkbenchStore,
    runtime_paths: RuntimePathRegistry,
    evidence_packs: ResearchEvidencePackService,
    fixture_mode: bool,
    frontend_dist_root: Path,
) -> dict[str, Any]:
    store_health = store.inspect_health()
    product_readiness = _evidence_pack_readiness(
        evidence_packs,
        fixture_mode=fixture_mode,
    )
    paths = {
        "code_root": _path_status(CODE_ROOT),
        "primary_data_root": _path_status(runtime_paths.primary_data_root),
        "reviewed_evidence": _path_status(runtime_paths.reviewed_evidence_root),
        "workbench_state": _path_status(runtime_paths.workbench_private_root),
        "object_store": _path_status(runtime_paths.object_store_root),
        "company_financial_fact_mart": _path_status(
            runtime_paths.company_financial_fact_mart_path
        ),
        "frontend_dist": _path_status(frontend_dist_root),
    }
    checks = {
        "store": store_health.status,
        "frontend": (
            "available" if (frontend_dist_root / "index.html").is_file() else "missing"
        ),
        "code_root": "ok" if paths["code_root"]["exists"] else "missing",
        "workbench_state": (
            "ok" if paths["workbench_state"]["writable"] else "not_writable"
        ),
        "reviewed_evidence_objects": (
            "ready" if product_readiness["all_ready"] else "data_mount_required"
        ),
    }
    critical_ok = (
        store_health.status == "ok"
        and checks["code_root"] == "ok"
        and checks["workbench_state"] == "ok"
    )
    return {
        "status": "ok" if critical_ok else "degraded",
        "service": "finsight-workbench",
        "version": "0.1.3",
        "checks": checks,
        "store": store_health,
        "paths": paths,
        "product_runtime": {
            "primary_route": "/workspace",
            "operator_route": "/operations",
            "retired_product_runtime_loaded": False,
            "readiness": product_readiness,
        },
    }


def _evidence_pack_readiness(
    evidence_packs: object,
    *,
    fixture_mode: bool,
) -> dict[str, Any]:
    readiness = getattr(evidence_packs, "readiness", None)
    if callable(readiness):
        return dict(readiness())
    return {
        "status": "fixture_injected" if fixture_mode else "readiness_contract_missing",
        "all_ready": fixture_mode,
        "unavailable_case_keys": [],
        "cases": [],
    }


def _path_status(path: Path) -> dict[str, object]:
    target = path if path.exists() else path.parent
    if not target.exists():
        target = CODE_ROOT
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
        "writable": os.access(target, os.W_OK),
        "total_bytes": total_bytes,
        "free_bytes": free_bytes,
    }


def _retired_api_response(*, family: str, replacement: str) -> JSONResponse:
    return JSONResponse(
        status_code=410,
        content={
            "reason": "retired_product_api",
            "family": family,
            "replacement": replacement,
            "product_version": "FIN 0.1.3",
        },
    )


app = create_app()


__all__ = ["app", "create_app"]
