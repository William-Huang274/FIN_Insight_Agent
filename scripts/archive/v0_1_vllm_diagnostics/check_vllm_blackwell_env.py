from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPO_ROOT / "scripts" / "eval_sec_benchmark"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import vllm_hardware_profiles  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether the current host can run the Blackwell vLLM profile.")
    vllm_hardware_profiles.add_hardware_profile_arg(parser)
    parser.add_argument("--expected-profile", default="rtx5090_32gb")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on-incompatible", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile_name = args.hardware_profile or args.expected_profile
    payload = json.loads(vllm_hardware_profiles.CONFIG_PATH.read_text(encoding="utf-8"))
    profile = (payload.get("profiles") or {}).get(profile_name) or {}
    status = {
        "profile": profile_name,
        "profile_hardware": profile.get("hardware") or {},
        "python": sys.version.split()[0],
        "nvidia_smi": _run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version,compute_cap", "--format=csv,noheader"]),
        "torch": _torch_status(),
        "vllm": _module_version("vllm"),
        "vllm_llm_import": _vllm_llm_import_status(),
        "vllm_llm_import_torchdynamo_disabled": _vllm_llm_import_status(
            env_overrides={"TORCHDYNAMO_DISABLE": "1"}
        ),
        "vllm_llm_import_optimized_diagnostic": _vllm_llm_import_status(optimized=True),
        "transformers": _module_version("transformers"),
        "recommendations": [],
        "compatible": None,
    }
    status["compatible"] = _judge(status)
    if not status["compatible"]:
        status["recommendations"].append("Install or activate a CUDA 12.8+ PyTorch/vLLM environment before running the 5090 profile.")
    elif not (status.get("vllm_llm_import") or {}).get("ok"):
        status["recommendations"].append("Run vLLM entrypoints with TORCHDYNAMO_DISABLE=1 on this torch/vLLM stack; do not use python -O/PYTHONOPTIMIZE because vLLM relies on asserts for hybrid KV-cache grouping.")
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(_format_text(status))
    if args.fail_on_incompatible and not status["compatible"]:
        raise SystemExit(2)


def _run(cmd: list[str], *, env_overrides: dict[str, str] | None = None) -> dict[str, Any]:
    env = None
    if env_overrides:
        env = os.environ.copy()
        env.update(env_overrides)
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=20, env=env)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def _module_version(name: str) -> dict[str, Any]:
    try:
        module = __import__(name)
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"available": True, "version": str(getattr(module, "__version__", "unknown"))}


def _vllm_llm_import_status(
    *,
    optimized: bool = False,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    cmd = [sys.executable]
    if optimized:
        cmd.append("-O")
    cmd.extend(["-c", "from vllm import LLM; print('ok')"])
    completed = _run(cmd, env_overrides=env_overrides)
    return {
        "ok": bool(completed.get("ok")),
        "optimized": optimized,
        "env_overrides": env_overrides or {},
        "stdout": completed.get("stdout"),
        "stderr_tail": str(completed.get("stderr") or "")[-1200:],
    }


def _torch_status() -> dict[str, Any]:
    try:
        import torch  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}
    status: dict[str, Any] = {
        "available": True,
        "version": str(getattr(torch, "__version__", "unknown")),
        "cuda_build": str(getattr(torch.version, "cuda", "") or ""),
        "cuda_available": bool(torch.cuda.is_available()),
        "device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
        "devices": [],
    }
    if torch.cuda.is_available():
        for index in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(index)
            status["devices"].append(
                {
                    "index": index,
                    "name": torch.cuda.get_device_name(index),
                    "total_memory_gib": round(props.total_memory / (1024**3), 2),
                    "compute_capability": f"sm_{props.major}{props.minor}",
                }
            )
    return status


def _judge(status: dict[str, Any]) -> bool:
    torch_status = status.get("torch") or {}
    if not torch_status.get("available") or not torch_status.get("cuda_available"):
        return False
    if not (status.get("vllm") or {}).get("available"):
        return False
    llm_import = status.get("vllm_llm_import") or {}
    llm_import_torchdynamo_disabled = status.get("vllm_llm_import_torchdynamo_disabled") or {}
    if not llm_import.get("ok") and not llm_import_torchdynamo_disabled.get("ok"):
        return False
    devices = torch_status.get("devices") or []
    expected_cc = str((status.get("profile_hardware") or {}).get("compute_capability") or "")
    if expected_cc and not any(str(device.get("compute_capability")) == expected_cc for device in devices):
        return False
    has_blackwell = any(str(device.get("compute_capability")) == "sm_120" for device in devices)
    if not has_blackwell:
        return True
    cuda_build = str(torch_status.get("cuda_build") or "")
    try:
        major, minor = [int(part) for part in cuda_build.split(".")[:2]]
    except ValueError:
        return False
    if (major, minor) < (12, 8):
        return False
    return True


def _format_text(status: dict[str, Any]) -> str:
    lines = [
        f"profile: {status['profile']}",
        f"compatible: {status['compatible']}",
        f"nvidia-smi: {(status.get('nvidia_smi') or {}).get('stdout') or (status.get('nvidia_smi') or {}).get('error')}",
        f"torch: {status.get('torch')}",
        f"vllm: {status.get('vllm')}",
        f"vllm_llm_import: {status.get('vllm_llm_import')}",
        f"vllm_llm_import_torchdynamo_disabled: {status.get('vllm_llm_import_torchdynamo_disabled')}",
        f"vllm_llm_import_optimized_diagnostic: {status.get('vllm_llm_import_optimized_diagnostic')}",
        f"transformers: {status.get('transformers')}",
    ]
    for recommendation in status.get("recommendations") or []:
        lines.append(f"recommendation: {recommendation}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
