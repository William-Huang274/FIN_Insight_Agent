from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
RUNNER = (
    ROOT
    / "scripts"
    / "releases"
    / "run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py"
)
SUPERVISION_CONTRACT_REF = "fin01.s3.exact_run_supervision:v2"
TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled"})
STILL_ACTIVE = 259
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _digest_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65_536), b""):
            byte_count += len(block)
            digest.update(block)
    return digest.hexdigest(), byte_count


def _windows_process_snapshot(pid: int) -> dict[str, Any]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return {
            "pid": pid,
            "query_succeeded": False,
            "running": False,
            "windows_error": ctypes.get_last_error(),
        }
    try:
        exit_code = wintypes.DWORD()
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        creation_filetime_100ns = (
            int(creation.dwHighDateTime) << 32
        ) | int(creation.dwLowDateTime)
        return {
            "pid": pid,
            "query_succeeded": True,
            "running": int(exit_code.value) == STILL_ACTIVE,
            "exit_code": (
                None if int(exit_code.value) == STILL_ACTIVE else int(exit_code.value)
            ),
            "creation_filetime_100ns": creation_filetime_100ns,
            "identity_kind": "windows_pid_and_creation_filetime",
        }
    finally:
        kernel32.CloseHandle(handle)


def _posix_process_snapshot(pid: int) -> dict[str, Any]:
    running = False
    try:
        os.kill(pid, 0)
        running = True
    except OSError:
        running = False
    start_ticks: int | None = None
    stat_path = Path("/proc") / str(pid) / "stat"
    if stat_path.exists():
        try:
            fields = stat_path.read_text(encoding="utf-8").split()
            start_ticks = int(fields[21])
        except (OSError, ValueError, IndexError):
            start_ticks = None
    return {
        "pid": pid,
        "query_succeeded": running or start_ticks is not None,
        "running": running,
        "proc_start_ticks": start_ticks,
        "identity_kind": "posix_pid_and_proc_start_ticks",
    }


def process_snapshot(pid: int) -> dict[str, Any]:
    if pid <= 0:
        return {"pid": pid, "query_succeeded": False, "running": False}
    if os.name == "nt":
        return _windows_process_snapshot(pid)
    return _posix_process_snapshot(pid)


def current_process_identity() -> dict[str, Any]:
    snapshot = process_snapshot(os.getpid())
    if not snapshot.get("query_succeeded"):
        raise RuntimeError("s3_t09_current_process_identity_unavailable")
    return _identity_projection(snapshot)


def _identity_projection(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if snapshot.get("identity_kind") == "windows_pid_and_creation_filetime":
        return {
            "pid": int(snapshot["pid"]),
            "identity_kind": str(snapshot["identity_kind"]),
            "creation_filetime_100ns": int(snapshot["creation_filetime_100ns"]),
        }
    return {
        "pid": int(snapshot["pid"]),
        "identity_kind": str(
            snapshot.get("identity_kind") or "posix_pid_only"
        ),
        "proc_start_ticks": snapshot.get("proc_start_ticks"),
    }


def process_identity_matches(
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> bool:
    if int(expected.get("pid") or 0) != int(observed.get("pid") or 0):
        return False
    if expected.get("identity_kind") != observed.get("identity_kind"):
        return False
    if expected.get("identity_kind") == "windows_pid_and_creation_filetime":
        return int(expected.get("creation_filetime_100ns") or 0) == int(
            observed.get("creation_filetime_100ns") or 0
        )
    expected_ticks = expected.get("proc_start_ticks")
    observed_ticks = observed.get("proc_start_ticks")
    return expected_ticks is not None and expected_ticks == observed_ticks


def _capture_process_identity(pid: int) -> dict[str, Any]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        snapshot = process_snapshot(pid)
        if snapshot.get("query_succeeded"):
            return _identity_projection(snapshot)
        time.sleep(0.02)
    raise RuntimeError("s3_t09_runner_process_identity_unavailable")


def _windows_creationflags() -> int:
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    breakaway = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", None)
    if breakaway is None:
        raise RuntimeError("s3_t09_windows_breakaway_flag_unavailable")
    return flags | int(breakaway)


def _launch_detached(
    supervision_root: Path,
    command: Sequence[str],
    *,
    minimum_lifecycle_budget_seconds: int,
    exact_bindings: Mapping[str, Any] | None = None,
    host_capability_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    supervision_root = supervision_root.resolve()
    supervision_root.mkdir(parents=True, exist_ok=True)
    launch_path = supervision_root / "launch_receipt.json"
    exit_path = supervision_root / "exit_receipt.json"
    if launch_path.exists() and not exit_path.exists():
        prior = json.loads(launch_path.read_text(encoding="utf-8"))
        prior_pid = int(prior.get("runner_pid") or 0)
        observed = process_snapshot(prior_pid)
        if observed.get("running") and process_identity_matches(
            prior.get("runner_process_identity") or {},
            _identity_projection(observed),
        ):
            raise RuntimeError("s3_t09_supervised_exact_run_already_active")
        raise RuntimeError(
            "s3_t09_supervision_receipt_incomplete_manual_audit_required"
        )
    if launch_path.exists() or exit_path.exists():
        raise RuntimeError("s3_t09_supervision_identity_reuse_forbidden")
    if (
        not command
        or any(not isinstance(value, str) or not value for value in command)
        or minimum_lifecycle_budget_seconds <= 0
    ):
        raise RuntimeError("s3_t09_supervised_runner_contract_invalid")

    command_path = supervision_root / "runner_command.json"
    stdout_path = supervision_root / "runner.stdout.log"
    stderr_path = supervision_root / "runner.stderr.log"
    command_payload = {
        "contract_ref": SUPERVISION_CONTRACT_REF,
        "argv": list(command),
        "exact_bindings": dict(exact_bindings or {}),
        "automatic_retry_count": 0,
        "fallback_count": 0,
        "replay_count": 0,
        "relaunch_count": 0,
    }
    _write_json_atomic(command_path, command_payload)
    child_environment = os.environ.copy()
    child_environment["FIN_IA_S3_T09_SUPERVISION_ROOT"] = str(supervision_root)
    child_environment["FIN_IA_S3_T09_SUPERVISION_CONTRACT_REF"] = (
        SUPERVISION_CONTRACT_REF
    )
    runtime_result_ref = str(
        (exact_bindings or {}).get("runtime_result_ref") or ""
    ).strip()
    if runtime_result_ref:
        child_environment["FIN_IA_S3_T09_RUNTIME_RESULT_REF"] = runtime_result_ref
    popen_kwargs: dict[str, Any] = {
        "cwd": str(ROOT),
        "stdin": subprocess.DEVNULL,
        "env": child_environment,
        "close_fds": True,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = _windows_creationflags()
    else:
        popen_kwargs["start_new_session"] = True
    with stdout_path.open("wb") as stdout_handle, stderr_path.open(
        "wb"
    ) as stderr_handle:
        process = subprocess.Popen(
            list(command),
            stdout=stdout_handle,
            stderr=stderr_handle,
            **popen_kwargs,
        )
    runner_identity = _capture_process_identity(process.pid)
    receipt = {
        "schema_version": (
            "fin_ia_0_1_s3_t09_supervised_exact_run_launch_v2_0"
        ),
        "contract_ref": SUPERVISION_CONTRACT_REF,
        "status": "actual_runner_launched_direct_detached_no_parent_timeout",
        "process_topology": "direct_actual_runner_no_intermediate_wrapper",
        "launcher_pid": os.getpid(),
        "runner_pid": process.pid,
        "runner_process_identity": runner_identity,
        "command_digest": _canonical_digest(command_payload),
        "command_ref": str(command_path),
        "exact_bindings": dict(exact_bindings or {}),
        "host_capability_binding": dict(host_capability_binding or {}),
        "stdout_ref": str(stdout_path),
        "stderr_ref": str(stderr_path),
        "exit_receipt_ref": str(exit_path),
        "minimum_lifecycle_budget_seconds": minimum_lifecycle_budget_seconds,
        "parent_enforced_timeout_seconds": None,
        "parent_may_terminate_child": False,
        "monitoring_contract": "read_only_no_signal_no_retry_no_relaunch",
        "automatic_retry_count": 0,
        "fallback_count": 0,
        "replay_count": 0,
        "relaunch_count": 0,
    }
    _write_json_atomic(launch_path, receipt)
    return receipt


def finalize_supervised_process(
    exit_code: int,
    *,
    failure_code: str | None = None,
) -> dict[str, Any] | None:
    supervision_root_value = str(
        os.environ.get("FIN_IA_S3_T09_SUPERVISION_ROOT") or ""
    ).strip()
    contract_ref = str(
        os.environ.get("FIN_IA_S3_T09_SUPERVISION_CONTRACT_REF") or ""
    ).strip()
    if not supervision_root_value and not contract_ref:
        return None
    if not supervision_root_value or contract_ref != SUPERVISION_CONTRACT_REF:
        raise RuntimeError("s3_t09_supervision_finalizer_environment_invalid")
    supervision_root = Path(supervision_root_value).resolve()
    launch_path = supervision_root / "launch_receipt.json"
    deadline = time.monotonic() + 5
    while not launch_path.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not launch_path.exists():
        raise RuntimeError("s3_t09_supervision_launch_receipt_missing")
    launch = json.loads(launch_path.read_text(encoding="utf-8"))
    identity = current_process_identity()
    if (
        launch.get("contract_ref") != SUPERVISION_CONTRACT_REF
        or int(launch.get("runner_pid") or 0) != os.getpid()
        or not process_identity_matches(
            launch.get("runner_process_identity") or {},
            identity,
        )
    ):
        raise RuntimeError("s3_t09_supervision_runner_identity_mismatch")

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (AttributeError, OSError):
            pass

    stream_bindings: dict[str, Any] = {}
    for name in ("stdout", "stderr"):
        ref = Path(str(launch[f"{name}_ref"]))
        try:
            digest, byte_count = _digest_file(ref)
            stream_bindings.update(
                {
                    f"{name}_sha256": digest,
                    f"{name}_bytes": byte_count,
                    f"{name}_digest_available": True,
                }
            )
        except OSError:
            stream_bindings.update(
                {
                    f"{name}_sha256": None,
                    f"{name}_bytes": None,
                    f"{name}_digest_available": False,
                }
            )
    runtime_result_value = str(
        os.environ.get("FIN_IA_S3_T09_RUNTIME_RESULT_REF") or ""
    ).strip()
    runtime_result_ref = (
        str(Path(runtime_result_value).resolve())
        if runtime_result_value and Path(runtime_result_value).exists()
        else None
    )
    receipt = {
        "schema_version": (
            "fin_ia_0_1_s3_t09_supervised_exact_run_exit_v2_0"
        ),
        "contract_ref": SUPERVISION_CONTRACT_REF,
        "status": "actual_runner_self_finalized",
        "runner_pid": os.getpid(),
        "runner_process_identity": identity,
        "exit_code": int(exit_code),
        "typed_unhandled_failure_code": failure_code,
        "runtime_result_ref": runtime_result_ref,
        "stdout_ref": str(launch["stdout_ref"]),
        "stderr_ref": str(launch["stderr_ref"]),
        **stream_bindings,
        "raw_provider_body_in_receipt": False,
        "credential_value_in_receipt": False,
        "automatic_retry_count": 0,
        "fallback_count": 0,
        "replay_count": 0,
        "relaunch_count": 0,
    }
    exit_path = supervision_root / "exit_receipt.json"
    if exit_path.exists():
        existing = json.loads(exit_path.read_text(encoding="utf-8"))
        if existing != receipt:
            raise RuntimeError("s3_t09_supervision_exit_receipt_conflict")
        return existing
    _write_json_atomic(exit_path, receipt)
    return receipt


def _validate_host_capability_receipt(path: Path) -> tuple[dict[str, Any], str]:
    path = path.resolve()
    if not path.exists():
        raise RuntimeError("s3_t09_host_lifetime_capability_receipt_missing")
    raw = path.read_bytes()
    receipt = json.loads(raw.decode("utf-8"))
    if (
        receipt.get("contract_ref") != SUPERVISION_CONTRACT_REF
        or receipt.get("status")
        != "pass_direct_runner_survived_launcher_and_self_finalized"
        or receipt.get("platform") != os.name
        or receipt.get("model_provider_network_source_tool_calls")
        != [0, 0, 0, 0, 0]
        or receipt.get("signals_sent") != 0
        or receipt.get("automatic_retry_count") != 0
        or receipt.get("relaunch_count") != 0
    ):
        raise RuntimeError("s3_t09_host_lifetime_capability_receipt_invalid")
    return receipt, hashlib.sha256(raw).hexdigest()


def launch_exact_run(
    supervision_root: Path,
    *,
    runtime_root: Path,
    issuance_path: Path,
    host_capability_receipt_path: Path,
    admission_path: Path | None = None,
    output_prefix: str | None = None,
) -> dict[str, Any]:
    capability, capability_digest = _validate_host_capability_receipt(
        host_capability_receipt_path
    )
    from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
        _load_admission,
        load_execution_target,
    )

    issuance_path = issuance_path.resolve()
    target = load_execution_target(issuance_path)
    resolved_admission = (
        admission_path.resolve()
        if admission_path is not None
        else (ROOT / target.admission_ref).resolve()
    )
    admission = _load_admission(resolved_admission, target)
    minimum_lifecycle_budget_seconds = (
        admission.timeout_seconds * admission.max_provider_calls
    ) + max(120, admission.timeout_seconds)
    runtime_root = runtime_root.resolve()
    runtime_result_ref = runtime_root / (
        f"{output_prefix}_live_execution_result.json"
        if output_prefix
        else "live_execution_result.json"
    )
    exact_bindings = {
        "runtime_root": str(runtime_root),
        "runtime_result_ref": str(runtime_result_ref),
        "issuance_ref": str(issuance_path),
        "issuance_sha256": hashlib.sha256(issuance_path.read_bytes()).hexdigest(),
        "admission_id": admission.admission_id,
        "admission_ref": str(resolved_admission),
        "admission_sha256": hashlib.sha256(
            resolved_admission.read_bytes()
        ).hexdigest(),
    }
    command = [
        sys.executable,
        str(RUNNER),
        "execute",
        "--runtime-root",
        str(runtime_root),
        "--issuance",
        str(issuance_path),
        "--admission",
        str(resolved_admission),
    ]
    if output_prefix is not None:
        command.extend(["--output-prefix", output_prefix])
    return _launch_detached(
        supervision_root,
        command,
        minimum_lifecycle_budget_seconds=minimum_lifecycle_budget_seconds,
        exact_bindings=exact_bindings,
        host_capability_binding={
            "receipt_ref": str(host_capability_receipt_path.resolve()),
            "receipt_sha256": capability_digest,
            "strategy": capability["durable_process_strategy"],
        },
    )


def read_process_status(supervision_root: Path) -> dict[str, Any]:
    supervision_root = supervision_root.resolve()
    launch_path = supervision_root / "launch_receipt.json"
    if not launch_path.exists():
        raise RuntimeError("s3_t09_supervision_launch_receipt_missing")
    launch = json.loads(launch_path.read_text(encoding="utf-8"))
    if launch.get("contract_ref") != SUPERVISION_CONTRACT_REF:
        raise RuntimeError("s3_t09_supervision_launch_contract_invalid")
    exit_path = supervision_root / "exit_receipt.json"
    exit_receipt = (
        json.loads(exit_path.read_text(encoding="utf-8"))
        if exit_path.exists()
        else None
    )
    expected_identity = launch.get("runner_process_identity") or {}
    observed_snapshot = process_snapshot(int(launch["runner_pid"]))
    observed_identity = (
        _identity_projection(observed_snapshot)
        if observed_snapshot.get("query_succeeded")
        else None
    )
    identity_matches = (
        observed_identity is not None
        and process_identity_matches(expected_identity, observed_identity)
    )
    if exit_receipt is not None:
        if (
            exit_receipt.get("contract_ref") != SUPERVISION_CONTRACT_REF
            or int(exit_receipt.get("runner_pid") or 0)
            != int(launch["runner_pid"])
            or not process_identity_matches(
                expected_identity,
                exit_receipt.get("runner_process_identity") or {},
            )
        ):
            raise RuntimeError("s3_t09_supervision_exit_receipt_identity_invalid")
        status = "exited_self_finalized"
        process_alive = False
    elif identity_matches and observed_snapshot.get("running"):
        status = "running"
        process_alive = True
    elif observed_snapshot.get("query_succeeded") and not identity_matches:
        status = "pid_reused_identity_mismatch"
        process_alive = False
    else:
        status = "process_unavailable_without_exit_receipt"
        process_alive = False
    return {
        "contract_ref": SUPERVISION_CONTRACT_REF,
        "status": status,
        "runner_pid": int(launch["runner_pid"]),
        "runner_process_identity": expected_identity,
        "observed_process_identity": observed_identity,
        "process_identity_matches": identity_matches,
        "process_alive": process_alive,
        "exit_receipt": exit_receipt,
        "monitor_mutations": 0,
        "signals_sent": 0,
        "automatic_retry_count": 0,
        "fallback_count": 0,
        "replay_count": 0,
        "relaunch_count": 0,
    }


def _host_smoke_command(
    supervision_root: Path,
    *,
    delay_seconds: float,
    marker_path: Path | None,
    fail: bool,
) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "smoke-runner",
        "--supervision-root",
        str(supervision_root.resolve()),
        "--smoke-delay-seconds",
        str(delay_seconds),
    ]
    if marker_path is not None:
        command.extend(["--smoke-marker", str(marker_path.resolve())])
    if fail:
        command.append("--smoke-fail")
    return command


def launch_host_lifetime_smoke(
    supervision_root: Path,
    *,
    delay_seconds: float = 0.75,
    marker_path: Path | None = None,
    fail: bool = False,
) -> dict[str, Any]:
    if delay_seconds <= 0 or delay_seconds > 30:
        raise RuntimeError("s3_t09_host_smoke_delay_invalid")
    return _launch_detached(
        supervision_root,
        _host_smoke_command(
            supervision_root,
            delay_seconds=delay_seconds,
            marker_path=marker_path,
            fail=fail,
        ),
        minimum_lifecycle_budget_seconds=30,
        exact_bindings={
            "execution_kind": "zero_call_host_lifetime_smoke",
            "model_provider_network_source_tool_calls": [0, 0, 0, 0, 0],
        },
    )


def inspect_host_lifetime_smoke(
    supervision_root: Path,
) -> dict[str, Any]:
    supervision_root = supervision_root.resolve()
    process = read_process_status(supervision_root)
    launch = json.loads(
        (supervision_root / "launch_receipt.json").read_text(encoding="utf-8")
    )
    exit_receipt = process.get("exit_receipt")
    separate_status_command = int(launch.get("launcher_pid") or 0) != os.getpid()
    passed = (
        separate_status_command
        and process["status"] == "exited_self_finalized"
        and isinstance(exit_receipt, Mapping)
        and exit_receipt.get("exit_code") == 0
        and exit_receipt.get("typed_unhandled_failure_code") is None
        and exit_receipt.get("automatic_retry_count") == 0
        and exit_receipt.get("relaunch_count") == 0
    )
    capability_path = supervision_root / "host_capability_receipt.json"
    capability = None
    if passed:
        capability = {
            "schema_version": (
                "fin_ia_0_1_s3_t09_host_lifetime_capability_v2_0"
            ),
            "contract_ref": SUPERVISION_CONTRACT_REF,
            "status": (
                "pass_direct_runner_survived_launcher_and_self_finalized"
            ),
            "platform": os.name,
            "durable_process_strategy": (
                "windows_CREATE_BREAKAWAY_FROM_JOB_direct_runner"
                if os.name == "nt"
                else "posix_start_new_session_direct_runner"
            ),
            "launch_receipt_ref": str(
                supervision_root / "launch_receipt.json"
            ),
            "runner_pid": launch["runner_pid"],
            "runner_process_identity": launch["runner_process_identity"],
            "separate_launcher_and_status_command_invocations": True,
            "self_finalized_exit_receipt": True,
            "model_provider_network_source_tool_calls": [0, 0, 0, 0, 0],
            "signals_sent": 0,
            "automatic_retry_count": 0,
            "fallback_count": 0,
            "replay_count": 0,
            "relaunch_count": 0,
        }
        _write_json_atomic(capability_path, capability)
    return {
        "schema_version": "fin_ia_0_1_s3_t09_host_lifetime_smoke_status_v2_0",
        "contract_ref": SUPERVISION_CONTRACT_REF,
        "status": (
            "capability_proven" if passed else "capability_not_yet_proven"
        ),
        "process": process,
        "separate_launcher_and_status_command_invocations": (
            separate_status_command
        ),
        "host_capability_receipt_ref": (
            str(capability_path) if capability is not None else None
        ),
        "model_provider_network_source_tool_calls": [0, 0, 0, 0, 0],
        "signals_sent": 0,
        "automatic_retry_count": 0,
        "relaunch_count": 0,
    }


def inspect_exact_status(
    supervision_root: Path,
    *,
    runtime_root: Path,
    issuance_path: Path,
) -> dict[str, Any]:
    from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
        _read_only_execution_rows,
        load_execution_target,
    )

    process_status = read_process_status(supervision_root)
    target = load_execution_target(issuance_path.resolve())
    canonical_database = (
        runtime_root.resolve() / "canonical-runtime" / "canonical.sqlite"
    )
    rows = (
        _read_only_execution_rows(runtime_root.resolve(), target.case_id)
        if canonical_database.exists()
        else {
            "canonical_work_units": [],
            "canonical_attempts": [],
            "canonical_research_run_versions": [],
            "canonical_artifact_versions": [],
        }
    )

    def state(table: str, logical_id: str) -> str | None:
        row = next(
            (
                value
                for value in rows[table]
                if value.get("_logical_id") == logical_id
            ),
            None,
        )
        return str(row.get("state") or "") if row else None

    states = {
        "work_unit_state": state("canonical_work_units", target.work_unit_id),
        "attempt_state": state("canonical_attempts", target.attempt_id),
        "research_run_state": state(
            "canonical_research_run_versions", target.research_run_id
        ),
    }
    terminal_consistent = (
        states["research_run_state"] in TERMINAL_STATES
        and len(set(states.values())) == 1
    )
    exit_receipt = process_status.get("exit_receipt")
    complete = (
        isinstance(exit_receipt, dict)
        and exit_receipt.get("exit_code") == 0
        and terminal_consistent
    )
    return {
        "schema_version": (
            "fin_ia_0_1_s3_t09_supervised_exact_run_status_v2_0"
        ),
        "contract_ref": SUPERVISION_CONTRACT_REF,
        "status": (
            "complete_terminal_state_verified"
            if complete
            else (
                "runner_exited_without_verified_terminal_state"
                if exit_receipt is not None
                else "running_read_only_monitor"
            )
        ),
        "process": process_status,
        "canonical_terminal_truth": {
            **states,
            "terminal_consistent": terminal_consistent,
        },
        "declared_complete": complete,
        "monitor_mutations": 0,
        "signals_sent": 0,
        "automatic_retry_count": 0,
        "fallback_count": 0,
        "replay_count": 0,
        "relaunch_count": 0,
    }


def _run_smoke_child(
    *,
    delay_seconds: float,
    marker_path: Path | None,
    fail: bool,
) -> int:
    time.sleep(delay_seconds)
    if marker_path is not None:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text("finished", encoding="utf-8")
    return 7 if fail else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Launch or read-only monitor the S3-T09 actual runner without "
            "parent timeout ownership."
        )
    )
    parser.add_argument(
        "mode",
        choices=(
            "launch",
            "status",
            "host-smoke-launch",
            "host-smoke-status",
            "smoke-runner",
        ),
    )
    parser.add_argument("--supervision-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--issuance", type=Path)
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--host-capability-receipt", type=Path)
    parser.add_argument("--output-prefix")
    parser.add_argument("--smoke-delay-seconds", type=float, default=0.75)
    parser.add_argument("--smoke-marker", type=Path)
    parser.add_argument("--smoke-fail", action="store_true")
    args = parser.parse_args()
    if args.mode == "smoke-runner":
        return _run_smoke_child(
            delay_seconds=args.smoke_delay_seconds,
            marker_path=args.smoke_marker,
            fail=args.smoke_fail,
        )
    if args.mode == "host-smoke-launch":
        result = launch_host_lifetime_smoke(
            args.supervision_root,
            delay_seconds=args.smoke_delay_seconds,
            marker_path=args.smoke_marker,
            fail=args.smoke_fail,
        )
    elif args.mode == "host-smoke-status":
        result = inspect_host_lifetime_smoke(args.supervision_root)
    else:
        if args.runtime_root is None or args.issuance is None:
            parser.error("launch/status require --runtime-root and --issuance")
        if args.mode == "launch":
            if args.host_capability_receipt is None:
                parser.error("launch requires --host-capability-receipt")
            result = launch_exact_run(
                args.supervision_root,
                runtime_root=args.runtime_root,
                issuance_path=args.issuance,
                admission_path=args.admission,
                host_capability_receipt_path=args.host_capability_receipt,
                output_prefix=args.output_prefix,
            )
        else:
            result = inspect_exact_status(
                args.supervision_root,
                runtime_root=args.runtime_root,
                issuance_path=args.issuance,
            )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _entrypoint() -> int:
    exit_code = 1
    failure_code: str | None = None
    try:
        exit_code = int(main())
        return exit_code
    except BaseException as exc:
        failure_code = f"unhandled_{type(exc).__name__}"
        traceback.print_exc()
        exit_code = 1
        return exit_code
    finally:
        if str(
            os.environ.get("FIN_IA_S3_T09_SUPERVISION_CONTRACT_REF") or ""
        ).strip() == SUPERVISION_CONTRACT_REF:
            finalize_supervised_process(
                exit_code,
                failure_code=failure_code or (
                    "process_exit_nonzero" if exit_code else None
                ),
            )


if __name__ == "__main__":
    raise SystemExit(_entrypoint())
