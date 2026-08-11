from __future__ import annotations

import importlib.util
import platform
import shutil
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict


CONTROL_PLANE_MODULES = [
    "fastapi",
    "pydantic",
    "uvicorn",
    "yaml",
    "langgraph",
    "langgraph.checkpoint.sqlite",
]
RUNTIME_MODULES = [
    "bs4",
    "duckdb",
    "lxml",
    "numpy",
    "rank_bm25",
    "requests",
    "sentence_transformers",
]
REQUIRED_SCRIPTS = [
    "scripts/workbench/start_workbench.py",
    "scripts/data_sec/build_sec_manifest.py",
    "scripts/data_retrieval/build_bm25_index.py",
    "scripts/cloud/sec_agent_interactive.sh",
]


class RuntimeModuleStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    available: bool


class RuntimeScriptStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    exists: bool


class RuntimePreflightReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    python_executable: str
    python_version: str
    platform: str
    control_plane_modules: list[RuntimeModuleStatus]
    full_runtime_modules: list[RuntimeModuleStatus]
    scripts: list[RuntimeScriptStatus]
    shell: dict[str, bool]
    missing_control_plane_modules: list[str]
    missing_full_runtime_modules: list[str]
    missing_scripts: list[str]


def inspect_runtime_preflight(repo_root: str | Path) -> RuntimePreflightReport:
    root = Path(repo_root).resolve()
    control_modules = [_module_status(name) for name in CONTROL_PLANE_MODULES]
    runtime_modules = [_module_status(name) for name in RUNTIME_MODULES]
    scripts = [
        RuntimeScriptStatus(path=path, exists=(root / path).exists())
        for path in REQUIRED_SCRIPTS
    ]
    missing_control = [item.name for item in control_modules if not item.available]
    missing_runtime = [item.name for item in runtime_modules if not item.available]
    missing_scripts = [item.path for item in scripts if not item.exists]
    status = "ok" if not missing_control and not missing_scripts else "degraded"
    return RuntimePreflightReport(
        status=status,
        python_executable=sys.executable,
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        control_plane_modules=control_modules,
        full_runtime_modules=runtime_modules,
        scripts=scripts,
        shell={
            "bash": shutil.which("bash") is not None,
            "wsl.exe": shutil.which("wsl.exe") is not None,
        },
        missing_control_plane_modules=missing_control,
        missing_full_runtime_modules=missing_runtime,
        missing_scripts=missing_scripts,
    )


def _module_status(name: str) -> RuntimeModuleStatus:
    try:
        available = importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        available = False
    return RuntimeModuleStatus(name=name, available=available)
