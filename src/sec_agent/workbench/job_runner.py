from __future__ import annotations

import os
import json
import platform
import re
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Mapping
from uuid import uuid4

from .jobs import RunJob
from .profiles import WorkbenchProfile
from .store import WorkbenchStore


TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
ALLOWED_AGENT_ASK_MODES = {
    "ask-full-source-api",
    "ask-full-source-deepseek",
    "ask-mixed-8k-api",
    "ask-mixed-8k-deepseek",
    "ask-mixed-api",
    "ask-mixed-deepseek",
    "ask-api",
    "ask-deepseek",
    "plan",
}
ALLOWED_AGENT_SESSION_MODES = {
    "session-full-source-api",
    "session-full-source-deepseek",
    "session-mixed-8k-api",
    "session-mixed-8k-deepseek",
    "session-mixed-api",
    "session-mixed-deepseek",
    "session-api",
    "session-deepseek",
}
_RUN_ROOT_PATTERNS = [
    re.compile(r"^\[artifacts\]\s+(?P<path>.+?)\s*$"),
    re.compile(r"^run_root:\s+(?P<path>.+?)\s*$"),
    re.compile(r'"run_root"\s*:\s*"(?P<path>(?:\\.|[^"\\])*)"'),
]
_STATE_PATH_PATTERNS = [
    re.compile(r"^sec_agent_state:\s+(?P<path>.+?)\s*$"),
    re.compile(r'"sec_agent_state_path"\s*:\s*"(?P<path>(?:\\.|[^"\\])*)"'),
]
_WSL_PATH_ENV_KEYS = {
    "FIN_REPO_ROOT",
    "SEC_AGENT_PROFILE_ENV",
    "SEC_AGENT_PROMPT_FILE",
    "SEC_AGENT_NATIVE_CHECKPOINT_PATH",
    "OUTPUT_ROOT",
    "BGE_MODEL",
    "MANIFEST_PATH",
    "BM25_INDEX_DIR",
    "OBJECT_BM25_INDEX_DIR",
    "SOURCE_GAP_PATH",
    "MARKET_EVIDENCE_PATH",
}
_EVAL_OUTPUT_ROOT = Path("reports") / "quality" / "workbench_eval"
_EVAL_RUNNERS = {
    "context_api_smoke": {
        "label": "Context API smoke",
        "description": "Runs the request-level ContextManager API smoke with the heuristic controller.",
        "timeout_hint_s": 60,
    },
    "context_api_load_smoke": {
        "label": "Context API small load smoke",
        "description": "Runs a small JSON-store ContextManager pressure smoke with bounded concurrency.",
        "timeout_hint_s": 120,
    },
    "closeout_quick_readiness": {
        "label": "Closeout quick readiness",
        "description": "Runs the closeout aggregator in a lightweight profile without model/API-heavy subchecks.",
        "timeout_hint_s": 180,
    },
}


@dataclass(frozen=True)
class CommandSpec:
    args: list[str]
    cwd: Path
    env_overrides: Mapping[str, str] = field(default_factory=dict)
    label: str = "command"
    cleanup_paths: list[Path] = field(default_factory=list)


def build_local_smoke_command(repo_root: str | Path) -> CommandSpec:
    code = (
        "import json, sys, time\n"
        "print('workbench smoke started', flush=True)\n"
        "time.sleep(0.05)\n"
        "print(json.dumps({'stage': 'runner', 'status': 'ok'}), flush=True)\n"
        "time.sleep(0.05)\n"
        "print('workbench smoke completed', flush=True)\n"
    )
    return CommandSpec(
        args=[sys.executable, "-u", "-c", code],
        cwd=Path(repo_root).resolve(),
        label="local_smoke",
    )


def eval_runner_catalog() -> list[dict[str, object]]:
    return [
        {"eval_id": eval_id, **metadata}
        for eval_id, metadata in _EVAL_RUNNERS.items()
    ]


def eval_output_path(repo_root: str | Path, *, eval_id: str, job_id: str) -> Path:
    safe_eval_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", eval_id).strip("_") or "eval"
    safe_job_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", job_id).strip("_") or "job"
    return Path(repo_root).resolve() / _EVAL_OUTPUT_ROOT / f"{safe_job_id}_{safe_eval_id}.json"


def build_eval_command(
    *,
    repo_root: str | Path,
    eval_id: str,
    job_id: str,
    profile: WorkbenchProfile | None = None,
) -> CommandSpec:
    if eval_id not in _EVAL_RUNNERS:
        raise ValueError(f"unsupported_eval_id: {eval_id}")
    output_path = eval_output_path(repo_root, eval_id=eval_id, job_id=job_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    env_overrides = profile.to_runtime_env() if profile else {}

    if eval_id == "context_api_smoke":
        args = [
            sys.executable,
            "-u",
            "scripts/evaluate_sec_agent_context_api_smoke.py",
            "--controller-backend",
            "heuristic",
            "--clean-fixtures",
            "--output-path",
            str(output_path),
        ]
    elif eval_id == "context_api_load_smoke":
        args = [
            sys.executable,
            "-u",
            "scripts/benchmark_sec_agent_context_api.py",
            "--controller-backend",
            "heuristic",
            "--requests",
            "20",
            "--concurrency",
            "4",
            "--warmup-requests",
            "2",
            "--clean-fixtures",
            "--output-path",
            str(output_path),
        ]
    else:
        args = [
            sys.executable,
            "-u",
            "scripts/evaluate_sec_agent_resume_closeout_readiness.py",
            "--output-path",
            str(output_path),
            "--timeout-s",
            "180",
            "--skip-pytest",
            "--skip-planner-eval",
            "--skip-main-chain-case-suite",
            "--skip-latency-profile",
            "--context-load-requests",
            "20",
            "--context-load-concurrency",
            "4",
        ]

    return CommandSpec(
        args=args,
        cwd=Path(repo_root).resolve(),
        env_overrides=env_overrides,
        label=f"eval:{eval_id}",
    )


def build_agent_ask_command(
    *,
    repo_root: str | Path,
    profile: WorkbenchProfile,
    prompt: str,
    command_mode: str = "ask-full-source-api",
    api_key_value: str | None = None,
) -> CommandSpec:
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("prompt_required")
    if command_mode not in ALLOWED_AGENT_ASK_MODES:
        raise ValueError(f"unsupported_command_mode: {command_mode}")

    env_overrides = profile.to_runtime_env()
    env_overrides["FIN_REPO_ROOT"] = str(Path(repo_root).resolve())
    if profile.env_file:
        env_overrides["SEC_AGENT_PROFILE_ENV"] = profile.env_file
    secret_env = _runtime_secret_env(profile, api_key_value)

    if _should_run_in_wsl(profile):
        prompt_file = _write_prompt_file(Path(repo_root), prompt)
        env_overrides["SEC_AGENT_PROMPT_FILE"] = str(prompt_file)
        wsl_env = _with_wsl_secret_passthrough(
            os.environ.get("WSLENV", ""),
            profile.model_route.api_key_env,
            secret_env_names=secret_env.keys(),
        )
        host_env_overrides = {**secret_env, **({"WSLENV": wsl_env} if wsl_env else {})}
        return CommandSpec(
            args=_wsl_command_args(
                repo_root=repo_root,
                profile=profile,
                env_values=env_overrides,
                script_args=_wsl_prompt_script_args(command_mode),
            ),
            cwd=Path(repo_root).resolve(),
            env_overrides=host_env_overrides,
            label=f"wsl:{command_mode}",
            cleanup_paths=[prompt_file],
        )

    return CommandSpec(
        args=["bash", "scripts/cloud/sec_agent_interactive.sh", command_mode, prompt],
        cwd=Path(repo_root).resolve(),
        env_overrides={**env_overrides, **secret_env},
        label=command_mode,
    )


def build_agent_session_turn_command(
    *,
    repo_root: str | Path,
    profile: WorkbenchProfile,
    prompt: str,
    session_id: str,
    tenant_id: str,
    user_id: str,
    command_mode: str = "session-full-source-api",
    api_key_value: str | None = None,
) -> CommandSpec:
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("prompt_required")
    if not session_id.strip():
        raise ValueError("session_id_required")
    if command_mode not in ALLOWED_AGENT_SESSION_MODES:
        raise ValueError(f"unsupported_session_command_mode: {command_mode}")

    env_overrides = profile.to_runtime_env()
    env_overrides["FIN_REPO_ROOT"] = str(Path(repo_root).resolve())
    if profile.env_file:
        env_overrides["SEC_AGENT_PROFILE_ENV"] = profile.env_file
    secret_env = _runtime_secret_env(profile, api_key_value)
    script_args = [
        "bash",
        "scripts/cloud/sec_agent_interactive.sh",
        command_mode,
        "--session-id",
        session_id.strip(),
        "--tenant-id",
        tenant_id.strip() or "workbench_tenant",
        "--user-id",
        user_id.strip() or "workbench_user",
        "--prompt",
        prompt,
    ]

    if _should_run_in_wsl(profile):
        prompt_file = _write_prompt_file(Path(repo_root), prompt)
        env_overrides["SEC_AGENT_PROMPT_FILE"] = str(prompt_file)
        env_overrides["SEC_AGENT_SESSION_ID"] = session_id.strip()
        env_overrides["SEC_AGENT_TENANT_ID"] = tenant_id.strip() or "workbench_tenant"
        env_overrides["SEC_AGENT_USER_ID"] = user_id.strip() or "workbench_user"
        wsl_env = _with_wsl_secret_passthrough(
            os.environ.get("WSLENV", ""),
            profile.model_route.api_key_env,
            secret_env_names=secret_env.keys(),
        )
        host_env_overrides = {**secret_env, **({"WSLENV": wsl_env} if wsl_env else {})}
        return CommandSpec(
            args=_wsl_command_args(
                repo_root=repo_root,
                profile=profile,
                env_values=env_overrides,
                script_args=_wsl_session_prompt_script_args(command_mode),
            ),
            cwd=Path(repo_root).resolve(),
            env_overrides=host_env_overrides,
            label=f"wsl:{command_mode}",
            cleanup_paths=[prompt_file],
        )

    return CommandSpec(
        args=script_args,
        cwd=Path(repo_root).resolve(),
        env_overrides={**env_overrides, **secret_env},
        label=command_mode,
    )


def build_native_checkpoint_resume_command(
    *,
    repo_root: str | Path,
    profile: WorkbenchProfile,
    checkpoint_path: str | Path,
    api_key_value: str | None = None,
    include_synthesis: bool = True,
    stop_after_node: str | None = None,
    checkpoint_mode: str = "sqlite",
) -> CommandSpec:
    checkpoint = Path(checkpoint_path)
    if not checkpoint.is_absolute():
        checkpoint = Path(repo_root).resolve() / checkpoint
    checkpoint = checkpoint.resolve()
    if checkpoint.is_dir():
        checkpoint = checkpoint / "langgraph_node_checkpoints.json"

    mode = checkpoint_mode.strip().lower() or "sqlite"
    if mode not in {"memory", "sqlite", "none"}:
        raise ValueError(f"unsupported_checkpoint_mode: {checkpoint_mode}")

    env_overrides = profile.to_runtime_env()
    env_overrides["FIN_REPO_ROOT"] = str(Path(repo_root).resolve())
    env_overrides["SEC_AGENT_NATIVE_CHECKPOINT_PATH"] = str(checkpoint)
    if stop_after_node:
        env_overrides["SEC_AGENT_NATIVE_STOP_AFTER_NODE"] = stop_after_node.strip()
    if profile.env_file:
        env_overrides["SEC_AGENT_PROFILE_ENV"] = profile.env_file
    secret_env = _runtime_secret_env(profile, api_key_value)

    base_args = [
        "-u",
        "scripts/cloud/sec_agent_graph_runner.py",
        "--resume-native-checkpoint",
        str(checkpoint),
        "--checkpoint-mode",
        mode,
    ]
    if include_synthesis:
        base_args.append("--native-resume-include-synthesis")
    if stop_after_node:
        base_args.extend(["--native-stop-after-node", stop_after_node.strip()])

    if _should_run_in_wsl(profile):
        wsl_env = _with_wsl_secret_passthrough(
            os.environ.get("WSLENV", ""),
            profile.model_route.api_key_env,
            secret_env_names=secret_env.keys(),
        )
        host_env_overrides = {**secret_env, **({"WSLENV": wsl_env} if wsl_env else {})}
        return CommandSpec(
            args=_wsl_command_args(
                repo_root=repo_root,
                profile=profile,
                env_values=env_overrides,
                script_args=_wsl_native_resume_script_args(
                    checkpoint_mode=mode,
                    include_synthesis=include_synthesis,
                    stop_after_node=stop_after_node,
                ),
            ),
            cwd=Path(repo_root).resolve(),
            env_overrides=host_env_overrides,
            label="wsl:native-checkpoint-resume",
        )

    return CommandSpec(
        args=[profile.runtime.python, *base_args],
        cwd=Path(repo_root).resolve(),
        env_overrides={**env_overrides, **secret_env},
        label="native-checkpoint-resume",
    )


def start_command_job(store: WorkbenchStore, job: RunJob, spec: CommandSpec) -> RunJob:
    store.upsert_run_job(job)
    store.append_run_event(job.job_id, stream="system", message=f"queued {spec.label}")
    thread = threading.Thread(
        target=_run_command_job,
        args=(store, job, spec),
        name=f"workbench-job-{job.job_id}",
        daemon=True,
    )
    thread.start()
    return job


def _run_command_job(store: WorkbenchStore, job: RunJob, spec: CommandSpec) -> None:
    running = _job_update(job, status="running", started_at=_now())
    store.upsert_run_job(running)
    store.append_run_event(job.job_id, stream="system", message=f"started {spec.label} in {spec.cwd}")

    process: subprocess.Popen[str] | None = None
    stdout_messages: list[str] = []
    try:
        env = os.environ.copy()
        env.update({key: str(value) for key, value in spec.env_overrides.items() if value is not None})
        process = subprocess.Popen(
            spec.args,
            cwd=str(spec.cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            message = line.rstrip("\r\n")
            if message:
                stdout_messages.append(message)
                store.append_run_event(job.job_id, stream="stdout", message=message)
        return_code = process.wait()
        detected_run_dir = detect_run_dir_from_output(stdout_messages, cwd=spec.cwd)
        if return_code == 0:
            completed = _job_update(running, status="completed", finished_at=_now(), error="")
            store.append_run_event(job.job_id, stream="system", message="process exited with code 0")
            bundle_update = _apply_data_build_bundle_update(store, completed)
            if bundle_update:
                completed = completed.model_copy(update={"metadata": {**completed.metadata, "bundle_update": bundle_update}})
        else:
            completed = _job_update(
                running,
                status="failed",
                finished_at=_now(),
                error=f"process exited with code {return_code}",
            )
            store.append_run_event(job.job_id, stream="system", message=completed.error)
        if detected_run_dir:
            completed = completed.model_copy(
                update={
                    "run_dir": str(detected_run_dir),
                    "metadata": {**completed.metadata, "detected_run_dir": str(detected_run_dir)},
                }
            )
            store.append_run_event(job.job_id, stream="system", message=f"detected run_dir: {detected_run_dir}")
        eval_summary = _read_eval_output_summary(completed)
        if eval_summary:
            completed = completed.model_copy(update={"metadata": {**completed.metadata, "eval_summary": eval_summary}})
            store.append_run_event(
                job.job_id,
                stream="system",
                message=f"eval summary: {json.dumps(eval_summary, ensure_ascii=False, sort_keys=True)}",
            )
        store.upsert_run_job(completed)
    except FileNotFoundError as exc:
        failed = _job_update(running, status="failed", finished_at=_now(), error=str(exc))
        store.append_run_event(job.job_id, stream="system", message=_missing_executable_message(spec.args[0], exc))
        store.upsert_run_job(failed)
    except Exception as exc:  # pragma: no cover - defensive persistence guard.
        if process and process.poll() is None:
            process.kill()
        failed = _job_update(running, status="failed", finished_at=_now(), error=str(exc))
        store.append_run_event(job.job_id, stream="system", message=f"runner failed: {exc}")
        store.upsert_run_job(failed)
    finally:
        for path in spec.cleanup_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def _job_update(job: RunJob, **changes: str) -> RunJob:
    return job.model_copy(update={"updated_at": _now(), **changes})


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _missing_executable_message(executable: str, exc: FileNotFoundError) -> str:
    if executable == "bash" and platform.system().lower() == "windows":
        return "bash executable not found; install Git Bash/WSL or run the full Agent job on Linux."
    return f"executable not found: {executable}: {exc}"


def detect_run_dir_from_output(messages: list[str], *, cwd: str | Path) -> Path | None:
    candidates: list[Path] = []
    for message in messages:
        for pattern in _RUN_ROOT_PATTERNS:
            match = pattern.search(message)
            if match:
                candidates.append(_candidate_path(match.group("path"), cwd=cwd))
        for pattern in _STATE_PATH_PATTERNS:
            match = pattern.search(message)
            if match:
                state_path = _candidate_path(match.group("path"), cwd=cwd)
                candidates.append(state_path.parent if state_path.name == "sec_agent_state.json" else state_path)
    for candidate in reversed(candidates):
        if _looks_like_agent_run_dir(candidate):
            return candidate.resolve()
    return None


def _candidate_path(raw_value: str, *, cwd: str | Path) -> Path:
    value = _decode_path_value(raw_value).strip().strip("'\"").rstrip(",")
    wsl_path = _wsl_path_to_windows_path(value)
    if wsl_path is not None:
        return wsl_path
    path = Path(value)
    return path if path.is_absolute() else Path(cwd).resolve() / path


def _decode_path_value(raw_value: str) -> str:
    if "\\\\" not in raw_value and '\\"' not in raw_value:
        return raw_value
    try:
        import json

        return str(json.loads(f'"{raw_value}"'))
    except Exception:
        return raw_value.replace("\\\\", "\\")


def _looks_like_agent_run_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    markers = [
        path / "sec_agent_state.json",
        path / "query_contract.json",
        path / "run_performance.json",
        path / "qwen" / "rendered_answer.md",
    ]
    return any(marker.exists() for marker in markers)


def _read_eval_output_summary(job: RunJob) -> dict[str, object]:
    output_path = job.metadata.get("output_path")
    if not output_path:
        return {}
    path = Path(str(output_path))
    if not path.exists() or not path.is_file():
        return {"output_path": str(path), "status": "missing"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"output_path": str(path), "status": "unreadable", "error": str(exc)}
    summary: dict[str, object] = {
        "output_path": str(path),
        "schema_version": payload.get("schema_version", ""),
        "run_id": payload.get("run_id", ""),
    }
    if "status" in payload:
        summary["status"] = payload.get("status")
    elif payload.get("all_pass") is True:
        summary["status"] = "pass"
    elif payload.get("failure_count", 0):
        summary["status"] = "fail"
    else:
        summary["status"] = "completed"
    for key in ("case_count", "pass_count", "failure_count", "warn_count", "skipped_count", "all_pass"):
        if key in payload:
            summary[key] = payload[key]
    return summary


def _apply_data_build_bundle_update(store: WorkbenchStore, job: RunJob) -> dict[str, object]:
    if job.job_type != "data_build":
        return {}
    metadata = job.metadata
    bundle_id = str(metadata.get("bundle_id") or "").strip()
    if not bundle_id:
        return {}
    artifact_updates = _string_dict(metadata.get("bundle_artifact_updates"))
    field_updates = _string_dict(metadata.get("bundle_field_updates"))
    if not artifact_updates and not field_updates:
        return {}
    bundle = store.get_source_bundle(bundle_id)
    if bundle is None:
        store.append_run_event(job.job_id, stream="system", message=f"source bundle not found for update: {bundle_id}")
        return {"status": "missing_bundle", "bundle_id": bundle_id}

    updated_artifacts = bundle.artifacts.model_copy(update=artifact_updates)
    build_scripts = list(bundle.build.scripts or [])
    step_id = str(metadata.get("step_id") or "").strip()
    if step_id and step_id not in build_scripts:
        build_scripts.append(step_id)
    updated_build = bundle.build.model_copy(update={"scripts": build_scripts, "status": "updated"})
    bundle_changes: dict[str, object] = {
        "artifacts": updated_artifacts,
        "build": updated_build,
    }
    if field_updates.get("as_of_date"):
        bundle_changes["as_of_date"] = field_updates["as_of_date"]
    updated_bundle = bundle.model_copy(update=bundle_changes)
    store.upsert_source_bundle(updated_bundle)
    store.append_run_event(
        job.job_id,
        stream="system",
        message=f"updated source bundle {bundle_id}: {json.dumps({'artifacts': artifact_updates, 'fields': field_updates}, ensure_ascii=False, sort_keys=True)}",
    )
    return {
        "status": "updated",
        "bundle_id": bundle_id,
        "artifact_updates": artifact_updates,
        "field_updates": field_updates,
    }


def _string_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items() if str(item).strip()}


def _should_run_in_wsl(profile: WorkbenchProfile) -> bool:
    mode = profile.runtime.execution_shell.lower().strip()
    return mode in {"wsl", "wsl2"}


def _wsl_command_args(
    *,
    repo_root: str | Path,
    profile: WorkbenchProfile,
    env_values: Mapping[str, str],
    script_args: list[str],
) -> list[str]:
    repo = profile.runtime.wsl_repo_root or _windows_path_to_wsl_path(repo_root)
    wsl_env_values = _normalize_wsl_env_values(env_values, wsl_repo_root=repo)
    args = ["wsl.exe"]
    if profile.runtime.wsl_distro:
        args.extend(["-d", profile.runtime.wsl_distro])
    args.extend(["--cd", repo, "--exec", "env"])
    args.extend(f"{key}={value}" for key, value in sorted(wsl_env_values.items()))
    args.extend(script_args)
    return args


def _wsl_prompt_script_args(command_mode: str) -> list[str]:
    script = (
        'prompt="$(cat "$SEC_AGENT_PROMPT_FILE")"; '
        f'exec bash scripts/cloud/sec_agent_interactive.sh {command_mode} "$prompt"'
    )
    return ["bash", "-lc", script]


def _wsl_session_prompt_script_args(command_mode: str) -> list[str]:
    script = (
        'prompt="$(cat "$SEC_AGENT_PROMPT_FILE")"; '
        f'exec bash scripts/cloud/sec_agent_interactive.sh {command_mode} '
        '--session-id "$SEC_AGENT_SESSION_ID" '
        '--tenant-id "$SEC_AGENT_TENANT_ID" '
        '--user-id "$SEC_AGENT_USER_ID" '
        '--prompt "$prompt"'
    )
    return ["bash", "-lc", script]


def _wsl_native_resume_script_args(
    *,
    checkpoint_mode: str,
    include_synthesis: bool,
    stop_after_node: str | None,
) -> list[str]:
    pieces = [
        'exec "$PY" -u scripts/cloud/sec_agent_graph_runner.py',
        '--resume-native-checkpoint "$SEC_AGENT_NATIVE_CHECKPOINT_PATH"',
        f"--checkpoint-mode {checkpoint_mode}",
    ]
    if include_synthesis:
        pieces.append("--native-resume-include-synthesis")
    if stop_after_node:
        pieces.append('--native-stop-after-node "$SEC_AGENT_NATIVE_STOP_AFTER_NODE"')
    return ["bash", "-lc", " ".join(pieces)]


def _normalize_wsl_env_values(env_values: Mapping[str, str], *, wsl_repo_root: str) -> dict[str, str]:
    normalized = dict(env_values)
    normalized["FIN_REPO_ROOT"] = wsl_repo_root
    for key in _WSL_PATH_ENV_KEYS:
        value = normalized.get(key)
        if value:
            normalized[key] = _env_path_to_wsl_path(value)
    return normalized


def _env_path_to_wsl_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    if len(normalized) >= 2 and normalized[1] == ":":
        return _windows_path_to_wsl_path(normalized)
    return normalized


def _windows_path_to_wsl_path(path: str | Path) -> str:
    text = str(path)
    normalized = text.replace("\\", "/")
    if len(normalized) >= 2 and normalized[1] == ":":
        drive = normalized[0].lower()
        rest = normalized[2:].lstrip("/")
        return f"/mnt/{drive}/{rest}" if rest else f"/mnt/{drive}"
    return normalized


def _wsl_path_to_windows_path(path: str) -> Path | None:
    normalized = path.replace("\\", "/")
    match = re.match(r"^/mnt/(?P<drive>[A-Za-z])(?:/(?P<rest>.*))?$", normalized)
    if not match:
        return None
    drive = match.group("drive").upper()
    rest = match.group("rest") or ""
    return Path(f"{drive}:/{rest}")


def _runtime_secret_env(profile: WorkbenchProfile, api_key_value: str | None) -> dict[str, str]:
    key_name = str(profile.model_route.api_key_env or "").strip()
    value = str(api_key_value or "").strip()
    if not key_name or not value:
        return {}
    return {key_name: value}


def _write_prompt_file(repo_root: Path, prompt: str) -> Path:
    path = repo_root.resolve() / "data" / "workbench_private" / "prompts" / f"prompt_{uuid4().hex}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(prompt, encoding="utf-8")
    return path


def _with_wsl_secret_passthrough(
    current_wslenv: str,
    api_key_env: str | None,
    *,
    secret_env_names: object = (),
) -> str:
    if not api_key_env:
        return current_wslenv
    explicit_names = {str(name) for name in secret_env_names}
    if api_key_env not in os.environ and api_key_env not in explicit_names:
        return current_wslenv
    entries = [entry for entry in current_wslenv.split(":") if entry]
    wanted = f"{api_key_env}/u"
    if not any(entry.split("/")[0] == api_key_env for entry in entries):
        entries.append(wanted)
    return ":".join(entries)
