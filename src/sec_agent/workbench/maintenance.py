from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .data_build import data_build_catalog
from .job_runner import CommandSpec
from .runtime_preflight import REQUIRED_SCRIPTS, inspect_runtime_preflight


MAINTENANCE_SCHEMA_VERSION = "finsight_workbench_maintenance_actions_v0.1"


class MaintenanceAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    category: str
    label: str
    description: str
    enabled: bool
    status: str
    timeout_hint_s: int = 60
    requires_full_runtime: bool = False
    command_preview: list[str] = Field(default_factory=list)
    output_contract: str = "json_stdout"


class MaintenanceActionCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = MAINTENANCE_SCHEMA_VERSION
    actions: list[MaintenanceAction]


def maintenance_action_catalog(repo_root: str | Path) -> MaintenanceActionCatalog:
    return MaintenanceActionCatalog(actions=list(_actions(Path(repo_root).resolve()).values()))


def get_maintenance_action(repo_root: str | Path, action_id: str) -> MaintenanceAction | None:
    return _actions(Path(repo_root).resolve()).get(action_id.strip())


def build_maintenance_command(
    *,
    repo_root: str | Path,
    action_id: str,
    parameters: dict[str, Any] | None = None,
) -> CommandSpec:
    root = Path(repo_root).resolve()
    action = get_maintenance_action(root, action_id)
    if action is None:
        raise ValueError(f"unsupported_maintenance_action: {action_id}")
    if not action.enabled:
        raise PermissionError(f"maintenance_action_disabled: {action_id}")
    if parameters:
        raise ValueError(f"maintenance_action_parameters_not_supported: {action_id}")
    return CommandSpec(
        args=list(action.command_preview),
        cwd=root,
        label=f"maintenance:{action.action_id}",
        timeout_s=action.timeout_hint_s,
    )


def run_runtime_preflight(repo_root: str | Path) -> dict[str, Any]:
    return inspect_runtime_preflight(repo_root).model_dump(mode="json")


def run_script_catalog_check(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    script_paths = sorted(
        {
            *REQUIRED_SCRIPTS,
            *(step.script for step in data_build_catalog()),
        }
    )
    scripts = [
        {
            "path": script,
            "exists": (root / script).exists(),
        }
        for script in script_paths
    ]
    missing = [item["path"] for item in scripts if not item["exists"]]
    return {
        "schema_version": "finsight_workbench_script_catalog_check_v0.1",
        "status": "ok" if not missing else "degraded",
        "script_count": len(scripts),
        "missing_scripts": missing,
        "scripts": scripts,
    }


def run_data_build_catalog_check(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    steps = data_build_catalog()
    rows = [
        {
            "step_id": step.step_id,
            "family": step.family,
            "script": step.script,
            "script_exists": (root / step.script).exists(),
            "parameter_count": len(step.parameters),
            "output_parameters": list(step.output_parameters),
            "timeout_hint_s": step.timeout_hint_s,
        }
        for step in steps
    ]
    missing = [row["step_id"] for row in rows if not row["script_exists"]]
    return {
        "schema_version": "finsight_workbench_data_build_catalog_check_v0.1",
        "status": "ok" if not missing else "degraded",
        "step_count": len(rows),
        "missing_step_scripts": missing,
        "steps": rows,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else ""
    repo_root = Path(args[1]).resolve() if len(args) > 1 else Path.cwd()
    if command == "runtime-preflight":
        payload = run_runtime_preflight(repo_root)
    elif command == "script-catalog":
        payload = run_script_catalog_check(repo_root)
    elif command == "data-build-catalog":
        payload = run_data_build_catalog_check(repo_root)
    else:
        payload = {
            "schema_version": "finsight_workbench_maintenance_error_v0.1",
            "status": "fail",
            "error": f"unsupported_maintenance_cli_command: {command or '<missing>'}",
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def _actions(repo_root: Path) -> dict[str, MaintenanceAction]:
    script = "scripts/workbench/runtime_maintenance.py"
    return {
        "runtime_preflight": MaintenanceAction(
            action_id="runtime_preflight",
            category="runtime",
            label="Runtime preflight",
            description="Run the same runtime dependency and script preflight used by readiness.",
            enabled=True,
            status="available",
            timeout_hint_s=60,
            command_preview=[sys.executable, "-u", script, "runtime-preflight", str(repo_root)],
        ),
        "script_catalog_validate": MaintenanceAction(
            action_id="script_catalog_validate",
            category="scripts",
            label="Script catalog validation",
            description="Validate required runtime scripts and whitelisted data-build script paths.",
            enabled=True,
            status="available",
            timeout_hint_s=60,
            command_preview=[sys.executable, "-u", script, "script-catalog", str(repo_root)],
        ),
        "data_build_catalog_validate": MaintenanceAction(
            action_id="data_build_catalog_validate",
            category="data",
            label="Data-build catalog validation",
            description="Validate the data-build update catalog and its script entrypoints.",
            enabled=True,
            status="available",
            timeout_hint_s=60,
            command_preview=[sys.executable, "-u", script, "data-build-catalog", str(repo_root)],
        ),
        "script_update_reserved": MaintenanceAction(
            action_id="script_update_reserved",
            category="scripts",
            label="Script update reserved hook",
            description="Reserved for future signed script bundles or image-rebuild orchestration; disabled by default.",
            enabled=False,
            status="reserved",
            timeout_hint_s=300,
            command_preview=[],
        ),
    }


if __name__ == "__main__":
    raise SystemExit(main())
