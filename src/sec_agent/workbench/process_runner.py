from __future__ import annotations

import json
import os
import platform
import queue
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Mapping

from .jobs import RunCancelReport, RunJob, TERMINAL_RUN_STATUSES
from .runtime_config import runtime_limits_from_env
from .store import WorkbenchStore


_ACTIVE_PROCESSES: dict[str, subprocess.Popen[str]] = {}
_CANCEL_REQUESTED: set[str] = set()
_ACTIVE_PROCESSES_LOCK = threading.Lock()
_JOB_SEMAPHORE: threading.BoundedSemaphore | None = None
_JOB_SEMAPHORE_LIMIT = 0
_JOB_SEMAPHORE_LOCK = threading.Lock()


@dataclass(frozen=True)
class CommandSpec:
    args: list[str]
    cwd: Path
    env_overrides: Mapping[str, str] = field(default_factory=dict)
    label: str = "command"
    timeout_s: int | None = None


def build_local_smoke_command(repo_root: str | Path) -> CommandSpec:
    code = (
        "import json, time\n"
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
        timeout_s=30,
    )


def build_active_baseline_verification_command(
    repo_root: str | Path,
) -> CommandSpec:
    return CommandSpec(
        args=[
            sys.executable,
            "-u",
            "scripts/engineering/verify_active_baseline.py",
        ],
        cwd=Path(repo_root).resolve(),
        label="active_baseline_verification",
        timeout_s=120,
    )


def start_command_job(
    store: WorkbenchStore, job: RunJob, spec: CommandSpec
) -> RunJob:
    store.upsert_run_job(job)
    store.append_run_event(
        job.job_id,
        stream="system",
        message=f"queued {spec.label}",
        trace_id=job.trace_id,
    )
    threading.Thread(
        target=_run_command_job,
        args=(store, job, spec),
        name=f"workbench-job-{job.job_id}",
        daemon=True,
    ).start()
    return job


def cancel_command_job(
    store: WorkbenchStore,
    job_id: str,
    *,
    reason: str = "cancelled by operator",
) -> RunCancelReport:
    job = store.get_run_job(job_id)
    if job is None:
        return RunCancelReport(
            job_id=job_id,
            status="missing",
            cancelled=False,
            message=f"job_not_found: {job_id}",
        )
    if job.status in TERMINAL_RUN_STATUSES:
        return RunCancelReport(
            job_id=job_id,
            status=job.status,
            cancelled=False,
            message="job_already_terminal",
            job=job,
        )
    with _ACTIVE_PROCESSES_LOCK:
        _CANCEL_REQUESTED.add(job_id)
        process = _ACTIVE_PROCESSES.get(job_id)
    if process is not None and process.poll() is None:
        _terminate_process_tree(
            process,
            grace_s=runtime_limits_from_env().cancel_grace_s,
        )
    cancelled = _job_update(
        job,
        status="cancelled",
        finished_at=_now(),
        error=reason,
    )
    store.append_run_event(
        job_id,
        stream="system",
        message=reason,
        trace_id=cancelled.trace_id,
    )
    store.upsert_run_job(cancelled)
    return RunCancelReport(
        job_id=job_id,
        status="cancelled",
        cancelled=True,
        message=reason,
        job=cancelled,
    )


def _run_command_job(
    store: WorkbenchStore, job: RunJob, spec: CommandSpec
) -> None:
    limits = runtime_limits_from_env()
    semaphore = _semaphore_for_limit(limits.max_active_jobs)
    acquired = False
    process: subprocess.Popen[str] | None = None
    try:
        while not acquired:
            if _cancel_requested(job.job_id):
                _finish_cancelled(store, job, "cancelled before start")
                return
            acquired = semaphore.acquire(timeout=0.2)
        latest = store.get_run_job(job.job_id)
        if latest is not None and latest.status in TERMINAL_RUN_STATUSES:
            return
        running = _job_update(job, status="running", started_at=_now())
        store.upsert_run_job(running)
        store.append_run_event(
            job.job_id,
            stream="system",
            message=f"started {spec.label} in {spec.cwd}",
            trace_id=running.trace_id,
        )
        env = os.environ.copy()
        env.update(
            {
                key: str(value)
                for key, value in spec.env_overrides.items()
                if value is not None
            }
        )
        env["SEC_AGENT_TRACE_ID"] = running.trace_id
        env["SEC_AGENT_WORKBENCH_JOB_ID"] = running.job_id
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
            **_process_group_kwargs(),
        )
        with _ACTIVE_PROCESSES_LOCK:
            _ACTIVE_PROCESSES[job.job_id] = process
        assert process.stdout is not None
        line_queue: queue.Queue[str | None] = queue.Queue()
        threading.Thread(
            target=_read_stdout,
            args=(process.stdout, line_queue),
            name=f"workbench-job-reader-{job.job_id}",
            daemon=True,
        ).start()
        started = time.monotonic()
        timeout_s = spec.timeout_s or limits.default_timeout_s
        timed_out = False
        reader_done = False
        while not reader_done:
            if _cancel_requested(job.job_id):
                _terminate_process_tree(process, grace_s=limits.cancel_grace_s)
                break
            if timeout_s and time.monotonic() - started > timeout_s:
                timed_out = True
                _terminate_process_tree(process, grace_s=limits.cancel_grace_s)
                break
            try:
                line = line_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if line is None:
                reader_done = True
            else:
                _record_stdout(store, running, line)
        while True:
            try:
                line = line_queue.get_nowait()
            except queue.Empty:
                break
            if line is not None:
                _record_stdout(store, running, line)
        return_code = process.wait(timeout=limits.cancel_grace_s)
        latest = store.get_run_job(job.job_id) or running
        if timed_out:
            completed = _job_update(
                latest,
                status="timed_out",
                finished_at=_now(),
                error=f"process timed out after {timeout_s}s",
            )
        elif _cancel_requested(job.job_id) or latest.status == "cancelled":
            completed = _job_update(
                latest,
                status="cancelled",
                finished_at=_now(),
                error=latest.error_message or "cancelled by operator",
            )
        elif return_code == 0:
            completed = _job_update(
                latest,
                status="completed",
                finished_at=_now(),
                error="",
            )
            bundle_update = _apply_data_build_bundle_update(store, completed)
            if bundle_update:
                completed = completed.model_copy(
                    update={
                        "metadata": {
                            **completed.metadata,
                            "bundle_update": bundle_update,
                        }
                    }
                )
        else:
            completed = _job_update(
                latest,
                status="failed",
                finished_at=_now(),
                error=f"process exited with code {return_code}",
            )
        store.upsert_run_job(completed)
        store.append_run_event(
            job.job_id,
            stream="system",
            message=f"process terminal: {completed.status} ({return_code})",
            trace_id=completed.trace_id,
        )
    except Exception as exc:  # pragma: no cover - persistence safety net.
        if process is not None and process.poll() is None:
            _terminate_process_tree(process, grace_s=limits.cancel_grace_s)
        latest = store.get_run_job(job.job_id) or job
        failed = _job_update(
            latest,
            status="cancelled" if _cancel_requested(job.job_id) else "failed",
            finished_at=_now(),
            error=str(exc),
        )
        store.upsert_run_job(failed)
        store.append_run_event(
            job.job_id,
            stream="system",
            message=f"runner terminalization: {exc}",
            trace_id=failed.trace_id,
        )
    finally:
        with _ACTIVE_PROCESSES_LOCK:
            _ACTIVE_PROCESSES.pop(job.job_id, None)
            _CANCEL_REQUESTED.discard(job.job_id)
        if acquired:
            semaphore.release()


def _finish_cancelled(
    store: WorkbenchStore, job: RunJob, message: str
) -> None:
    cancelled = _job_update(
        job,
        status="cancelled",
        finished_at=_now(),
        error=message,
    )
    store.upsert_run_job(cancelled)
    store.append_run_event(
        job.job_id,
        stream="system",
        message=message,
        trace_id=job.trace_id,
    )


def _record_stdout(store: WorkbenchStore, job: RunJob, line: str) -> None:
    message = line.rstrip("\r\n")
    if message:
        store.append_run_event(
            job.job_id,
            stream="stdout",
            message=message,
            trace_id=job.trace_id,
        )


def _read_stdout(stdout, line_queue: queue.Queue[str | None]) -> None:
    try:
        for line in stdout:
            line_queue.put(line)
    finally:
        line_queue.put(None)


def _apply_data_build_bundle_update(
    store: WorkbenchStore, job: RunJob
) -> dict[str, object]:
    if job.job_type != "data_build":
        return {}
    bundle_id = str(job.metadata.get("bundle_id") or "").strip()
    if not bundle_id:
        return {}
    artifact_updates = _string_dict(
        job.metadata.get("bundle_artifact_updates")
    )
    field_updates = _string_dict(job.metadata.get("bundle_field_updates"))
    if not artifact_updates and not field_updates:
        return {}
    bundle = store.get_source_bundle(bundle_id)
    if bundle is None:
        return {"status": "missing_bundle", "bundle_id": bundle_id}
    artifacts = bundle.artifacts.model_copy(update=artifact_updates)
    scripts = list(bundle.build.scripts or [])
    step_id = str(job.metadata.get("step_id") or "").strip()
    if step_id and step_id not in scripts:
        scripts.append(step_id)
    changes: dict[str, object] = {
        "artifacts": artifacts,
        "build": bundle.build.model_copy(
            update={"scripts": scripts, "status": "updated"}
        ),
    }
    if field_updates.get("as_of_date"):
        changes["as_of_date"] = field_updates["as_of_date"]
    store.upsert_source_bundle(bundle.model_copy(update=changes))
    return {
        "status": "updated",
        "bundle_id": bundle_id,
        "artifact_updates": artifact_updates,
        "field_updates": field_updates,
    }


def _string_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): str(item)
        for key, item in value.items()
        if str(item).strip()
    }


def _job_update(job: RunJob, **changes: object) -> RunJob:
    updates = {"updated_at": _now(), **changes}
    if "error" in updates:
        updates["error_message"] = str(updates.get("error") or "")
    updated = job.model_copy(update=updates)
    if updated.started_at and updated.finished_at:
        started = datetime.fromisoformat(updated.started_at)
        finished = datetime.fromisoformat(updated.finished_at)
        updated = updated.model_copy(
            update={
                "elapsed_ms": max(
                    0,
                    int(round((finished - started).total_seconds() * 1000)),
                )
            }
        )
    return updated


def _cancel_requested(job_id: str) -> bool:
    with _ACTIVE_PROCESSES_LOCK:
        return job_id in _CANCEL_REQUESTED


def _semaphore_for_limit(limit: int) -> threading.BoundedSemaphore:
    global _JOB_SEMAPHORE, _JOB_SEMAPHORE_LIMIT
    safe_limit = max(1, int(limit))
    with _JOB_SEMAPHORE_LOCK:
        if _JOB_SEMAPHORE is None or _JOB_SEMAPHORE_LIMIT != safe_limit:
            _JOB_SEMAPHORE = threading.BoundedSemaphore(safe_limit)
            _JOB_SEMAPHORE_LIMIT = safe_limit
        return _JOB_SEMAPHORE


def _process_group_kwargs() -> dict[str, object]:
    if platform.system().lower() == "windows":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _terminate_process_tree(
    process: subprocess.Popen[str], *, grace_s: int
) -> None:
    if process.poll() is not None:
        return
    if platform.system().lower() == "windows":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except OSError:
            process.terminate()
    try:
        process.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=grace_s)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


__all__ = [
    "CommandSpec",
    "build_active_baseline_verification_command",
    "build_local_smoke_command",
    "cancel_command_job",
    "start_command_job",
]
