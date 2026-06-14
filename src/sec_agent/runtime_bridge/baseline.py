from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import runtime_bridge_registry
from .paths import resolve_runtime_paths


def build_runtime_baseline_report(*, repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root or Path.cwd()).resolve()
    paths = resolve_runtime_paths(root)
    env_keys = sorted(
        key
        for key in os.environ
        if key.startswith(("FINSIGHT_", "SEC_AGENT_", "BGE_", "LLM_", "MODEL_", "API_KEY_ENV"))
    )
    report = {
        "schema_version": "finsight_runtime_baseline_report_v0_1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(root),
        "code_commit": _git(root, "rev-parse", "--short=12", "HEAD"),
        "git_status_short": _git(root, "status", "--short"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "runtime_paths": paths.as_dict(),
        "env_key_names": env_keys,
        "runtime_bridge_registry": runtime_bridge_registry(repo_root=str(root)),
        "cloud_handoff": {
            "milvus_mode": paths.milvus_mode,
            "milvus_required_for_r3_cloud_parity": paths.milvus_mode in {"unbound_cloud_deferred", "unavailable", ""},
            "gpu_scheduler_required_for_r5_cloud_smoke": True,
            "full_chain_large_gate_deferred_until_cloud": True,
        },
        "secret_policy": "env_key_names_only_values_never_persisted_v0_1",
    }
    return report


def write_runtime_baseline_report(path: str | Path, *, repo_root: str | Path | None = None) -> dict[str, Any]:
    report = build_runtime_baseline_report(repo_root=repo_root)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""
