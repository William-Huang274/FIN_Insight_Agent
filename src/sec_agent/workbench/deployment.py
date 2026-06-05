from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .path_policy import PathPolicyReport
from .runtime_config import WorkbenchDeploymentConfig, deployment_config_from_env
from .runtime_preflight import RuntimePreflightReport


DEPLOYMENT_SCHEMA_VERSION = "finsight_workbench_deployment_v0.1"


class UpdateInterfaceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interface_id: str
    category: str
    method: str
    endpoint: str
    status: str
    description: str
    action_id: str | None = None


class WorkbenchDeploymentReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = DEPLOYMENT_SCHEMA_VERSION
    service: str = "finsight-workbench"
    status: str
    runtime_profile: str
    requested_runtime_profile: str
    image_kind: str
    release_id: str
    full_runtime_ready: bool
    frontend_bundled: bool
    code_update_mode: str
    data_update_mode: str
    update_interface_version: str
    immutable_roots: list[str] = Field(default_factory=list)
    mutable_roots: list[str] = Field(default_factory=list)
    path_policy_allowed_roots: list[str] = Field(default_factory=list)
    missing_full_runtime_modules: list[str] = Field(default_factory=list)
    update_interfaces: list[UpdateInterfaceReport] = Field(default_factory=list)


def inspect_deployment(
    *,
    repo_root: str | Path,
    frontend_bundled: bool,
    path_policy: PathPolicyReport,
    runtime_preflight: RuntimePreflightReport,
    config: WorkbenchDeploymentConfig | None = None,
) -> WorkbenchDeploymentReport:
    resolved_config = config or deployment_config_from_env()
    full_runtime_ready = not runtime_preflight.missing_full_runtime_modules
    runtime_profile = _resolve_runtime_profile(
        requested=resolved_config.runtime_profile,
        full_runtime_ready=full_runtime_ready,
    )
    status = "ok"
    if runtime_profile == "integrated" and not full_runtime_ready:
        status = "degraded"
    return WorkbenchDeploymentReport(
        status=status,
        runtime_profile=runtime_profile,
        requested_runtime_profile=resolved_config.runtime_profile,
        image_kind=resolved_config.image_kind,
        release_id=resolved_config.release_id,
        full_runtime_ready=full_runtime_ready,
        frontend_bundled=frontend_bundled,
        code_update_mode=resolved_config.script_update_mode,
        data_update_mode=resolved_config.data_update_mode,
        update_interface_version=resolved_config.update_interface_version,
        immutable_roots=[str(Path(repo_root).resolve() / item) for item in ("apps", "scripts", "src")],
        mutable_roots=[str(Path(repo_root).resolve() / item) for item in ("configs", "data", "reports")],
        path_policy_allowed_roots=[str(root) for root in path_policy.allowed_roots],
        missing_full_runtime_modules=list(runtime_preflight.missing_full_runtime_modules),
        update_interfaces=_update_interfaces(),
    )


def _resolve_runtime_profile(*, requested: str, full_runtime_ready: bool) -> str:
    normalized = requested.strip().lower().replace("_", "-")
    if normalized in {"integrated", "integrated-runtime", "runtime", "full", "full-runtime"}:
        return "integrated"
    if normalized in {"control-plane", "control", "backend", "light", "lightweight"}:
        return "control-plane"
    return "integrated" if full_runtime_ready else "control-plane"


def _update_interfaces() -> list[UpdateInterfaceReport]:
    return [
        UpdateInterfaceReport(
            interface_id="data_build_catalog",
            category="data",
            method="GET",
            endpoint="/api/data-build/steps",
            status="available",
            description="List whitelisted data-build steps available for controlled data updates.",
        ),
        UpdateInterfaceReport(
            interface_id="data_build_preview",
            category="data",
            method="POST",
            endpoint="/api/data-build/preview",
            status="available",
            description="Preview a whitelisted data-build command before launching it.",
        ),
        UpdateInterfaceReport(
            interface_id="data_build_run",
            category="data",
            method="POST",
            endpoint="/api/data-build/run",
            status="available",
            description="Launch a whitelisted data-build job and optionally backfill a source bundle.",
        ),
        UpdateInterfaceReport(
            interface_id="source_bundle_validate",
            category="data",
            method="POST",
            endpoint="/api/source-bundles/validate",
            status="available",
            description="Validate updated source-bundle artifacts after data refresh jobs.",
        ),
        UpdateInterfaceReport(
            interface_id="maintenance_actions",
            category="runtime",
            method="GET",
            endpoint="/api/system/maintenance/actions",
            status="available",
            description="List safe maintenance actions and reserved future update hooks.",
        ),
        UpdateInterfaceReport(
            interface_id="maintenance_run",
            category="runtime",
            method="POST",
            endpoint="/api/system/maintenance/run",
            status="available",
            description="Run enabled maintenance actions through the Workbench job runner.",
        ),
        UpdateInterfaceReport(
            interface_id="script_update_reserved",
            category="scripts",
            method="POST",
            endpoint="/api/system/maintenance/run",
            status="reserved",
            action_id="script_update_reserved",
            description="Reserved hook for future signed script bundles or image-rebuild orchestration.",
        ),
    ]
