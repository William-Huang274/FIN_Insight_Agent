from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "configs" / "vllm_hardware_profiles.json"
PROFILE_ENV = "FIN_VLLM_HARDWARE_PROFILE"


def add_hardware_profile_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--hardware-profile",
        default=os.environ.get(PROFILE_ENV, ""),
        help=(
            "Optional vLLM hardware profile from configs/vllm_hardware_profiles.json. "
            f"Can also be set with {PROFILE_ENV}. Explicit CLI values override profile defaults."
        ),
    )


def apply_hardware_profile(
    args: argparse.Namespace,
    *,
    workload: str,
    argv: list[str] | None = None,
) -> dict[str, Any]:
    profile_name = str(getattr(args, "hardware_profile", "") or os.environ.get(PROFILE_ENV, "")).strip()
    if not profile_name or profile_name.lower() in {"none", "off", "default"}:
        metadata = {
            "profile": "",
            "workload": workload,
            "source": str(CONFIG_PATH),
            "applied_defaults": {},
            "skipped": "no_profile_requested",
        }
        _attach(args, metadata)
        return metadata

    payload = _load_profiles()
    profiles = payload.get("profiles") or {}
    if profile_name not in profiles:
        available = ", ".join(sorted(profiles))
        raise ValueError(f"Unknown vLLM hardware profile '{profile_name}'. Available profiles: {available}")

    profile = profiles[profile_name]
    runtime_env = _runtime_env(profile, workload)
    applied_env: dict[str, str] = {}
    skipped_env: dict[str, str] = {}
    for key, value in runtime_env.items():
        value_str = str(value)
        if key in os.environ:
            skipped_env[key] = os.environ[key]
            continue
        os.environ[key] = value_str
        applied_env[key] = value_str

    defaults = _merged_defaults(profile, workload)
    cli_argv = list(sys.argv[1:] if argv is None else argv)
    applied: dict[str, Any] = {}
    skipped_cli: list[str] = []
    skipped_missing: list[str] = []
    for key, value in defaults.items():
        if not hasattr(args, key):
            skipped_missing.append(key)
            continue
        if _cli_overrode(key, cli_argv):
            skipped_cli.append(key)
            continue
        setattr(args, key, value)
        applied[key] = value

    metadata = {
        "profile": profile_name,
        "workload": workload,
        "source": str(CONFIG_PATH),
        "hardware": profile.get("hardware") or {},
        "compatibility_notes": profile.get("compatibility_notes") or [],
        "applied_runtime_env": applied_env,
        "skipped_existing_runtime_env": skipped_env,
        "applied_defaults": applied,
        "skipped_cli_overrides": skipped_cli,
        "skipped_missing_args": skipped_missing,
    }
    _attach(args, metadata)
    return metadata


def _load_profiles() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"vLLM hardware profile config not found: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _merged_defaults(profile: dict[str, Any], workload: str) -> dict[str, Any]:
    defaults = profile.get("defaults") or {}
    merged: dict[str, Any] = {}
    for section in ("common", workload):
        values = defaults.get(section) or {}
        if not isinstance(values, dict):
            raise ValueError(f"Invalid profile defaults for section '{section}'")
        merged.update(values)
    return merged


def _runtime_env(profile: dict[str, Any], workload: str) -> dict[str, Any]:
    runtime_env = profile.get("runtime_env") or {}
    if not isinstance(runtime_env, dict):
        raise ValueError("Invalid profile runtime_env; expected object")
    merged = dict(runtime_env)
    workload_env = (profile.get("workload_runtime_env") or {}).get(workload) or {}
    if not isinstance(workload_env, dict):
        raise ValueError(f"Invalid profile workload_runtime_env for '{workload}'; expected object")
    merged.update(workload_env)
    return merged


def _cli_overrode(dest: str, argv: list[str]) -> bool:
    option = "--" + dest.replace("_", "-")
    negative = "--no-" + dest.replace("_", "-")
    for item in argv:
        if item == option or item.startswith(option + "="):
            return True
        if item == negative or item.startswith(negative + "="):
            return True
    return False


def _attach(args: argparse.Namespace, metadata: dict[str, Any]) -> None:
    setattr(args, "hardware_profile_resolved", metadata.get("profile", ""))
    setattr(args, "hardware_profile_metadata", metadata)
