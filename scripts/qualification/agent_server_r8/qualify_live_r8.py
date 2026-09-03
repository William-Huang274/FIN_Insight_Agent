"""Host orchestrator for the bounded Dell Agent Server r8 qualification.

The orchestrator creates one fresh Compose project and one immutable attempt
directory.  It delegates all runtime assertions to ``live_phase.py`` inside
the API container, performs only the approved restart sequence, and never
removes a container, volume, or prior attempt.

No model credential is passed to Agent Server.  The local PostgreSQL secret is
used only as key material: three distinct URL-safe role passwords are derived
in memory with separate labels.  Neither source nor derived values are printed,
written back to ``.env``, or stored in receipts.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Any, Mapping
from uuid import uuid4

from sec_agent.agent_runtime.dell_agent_server_identity import (
    IDENTITY_SCHEMA_SHA256,
)
from sec_agent.agent_runtime.dell_reference_vertical_contracts import (
    canonical_sha256,
)
from sec_agent.agent_runtime.dell_zero_model_graph_qualification import (
    ZERO_MODEL_EXECUTION_PROFILE,
)
from sec_agent.agent_runtime.dell_agent_server_data_composition import (
    DELL_APPROVED_DATA_SNAPSHOT_ID,
    DELL_APPROVED_RESEARCH_AS_OF,
)
from sec_agent.agent_runtime.dell_owner_data_gate import (
    DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_DIGEST,
)
from sec_agent.canonical_runtime.contracts_v1_2 import (
    canonical_json_sha256,
    create_agent_session_v1_2,
    create_research_run,
    create_run_invocation,
)
from sec_agent.research_foundation.contracts import (
    load_dell_reference_vertical_foundation,
)


ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = ROOT / "deploy/dell_agent_server/compose.yaml"
QUALIFICATION_OVERRIDE = (
    ROOT / "deploy/dell_agent_server/compose.zero-model-qualification.yaml"
)
DOTENV_FILE = ROOT / ".env"
FOUNDATION_PATH = (
    ROOT
    / "configs/research/"
    "fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json"
)
ATTEMPTS_ROOT = Path(
    "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/"
    "agent_server_control_plane/attempts"
)
COMPOSE_PROJECT = "finsight-dell-qualification-20260904-r8"
HOST_PORT = 18128
MANIFEST_SCHEMA_VERSION = "fin_ia_dell_agent_server_live_r8_manifest_v1_0"
RECEIPT_SCHEMA_VERSION = "fin_ia_dell_agent_server_live_r8_receipt_v1_0"
FAILURE_SCHEMA_VERSION = "fin_ia_dell_agent_server_live_r8_failure_v1_0"
EXPECTED_BRANCH = "codex/fin013-dell-s1-s2-product-bridge"
PHASE_SCRIPT = "/opt/fin-insight-qualification/r8/live_phase.py"
_REQUIRED_ENV_NAMES = (
    "FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD",
    "LANGSMITH_API_KEY",
)


class QualificationError(RuntimeError):
    """Stable, secret-free host orchestration failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class QualificationSubprocessError(QualificationError):
    """Failed child process with content-minimised diagnostic evidence."""

    def __init__(
        self,
        code: str,
        *,
        observation: Mapping[str, Any],
        parsed: Mapping[str, Any] | None,
    ) -> None:
        self.observation = dict(observation)
        self.parsed = None if parsed is None else dict(parsed)
        super().__init__(code)


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise QualificationError("r8_host_non_json_value") from None


def _digest(value: Any) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _dotenv_values() -> dict[str, str]:
    if not DOTENV_FILE.is_file():
        raise QualificationError("r8_dotenv_missing")
    values: dict[str, str] = {}
    try:
        lines = DOTENV_FILE.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        raise QualificationError("r8_dotenv_unreadable") from None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def _credential_environment() -> dict[str, str]:
    dotenv = _dotenv_values()
    child = dict(os.environ)
    for name in _REQUIRED_ENV_NAMES:
        value = child.get(name) or dotenv.get(name)
        if not value:
            raise QualificationError(f"r8_required_environment_missing:{name}")
        child[name] = value
    credential_seed = child["FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD"]

    def derived(label: str) -> str:
        return sha256(
            f"fin-r8:{label}\0{credential_seed}".encode("utf-8")
        ).hexdigest()

    bootstrap = derived("postgres-bootstrap-admin")
    langgraph_password = derived("langgraph-runtime")
    fin_password = derived("fin-runtime")
    if len({bootstrap, langgraph_password, fin_password}) != 3:
        raise QualificationError("r8_postgres_passwords_not_distinct")
    if any(
        len(value) < 16
        or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._~-" for char in value)
        for value in (bootstrap, langgraph_password, fin_password)
    ):
        raise QualificationError("r8_postgres_password_contract_invalid")
    child["FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD"] = langgraph_password
    child["FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD"] = fin_password
    child["FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD"] = bootstrap
    child["FINSIGHT_AGENT_SERVER_HOST_PORT"] = str(HOST_PORT)
    return child


def _run(
    args: list[str],
    *,
    environment: Mapping[str, str],
    input_bytes: bytes | None = None,
    timeout: int = 900,
    phase_json: bool = False,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    label = " ".join(args[:3]) if len(args) >= 3 else args[0]
    print(f"r8: running {label}", flush=True)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            args,
            cwd=ROOT,
            env=dict(environment),
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = round((time.monotonic() - started) * 1000, 3)
        stdout = exc.stdout if isinstance(exc.stdout, bytes) else b""
        stderr = exc.stderr if isinstance(exc.stderr, bytes) else b""
        raise QualificationSubprocessError(
            "r8_subprocess_timeout",
            observation={
                "argv_sha256": _digest(args),
                "returncode": None,
                "timed_out": True,
                "elapsed_ms": elapsed_ms,
                "stdout_bytes": len(stdout),
                "stdout_sha256": sha256(stdout).hexdigest(),
                "stderr_bytes": len(stderr),
                "stderr_sha256": sha256(stderr).hexdigest(),
            },
            parsed=None,
        ) from None
    elapsed_ms = round((time.monotonic() - started) * 1000, 3)
    observation = {
        "argv_sha256": _digest(args),
        "returncode": completed.returncode,
        "elapsed_ms": elapsed_ms,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256": sha256(completed.stdout).hexdigest(),
        "stderr_bytes": len(completed.stderr),
        "stderr_sha256": sha256(completed.stderr).hexdigest(),
    }
    parsed: dict[str, Any] | None = None
    if phase_json:
        try:
            nonempty = [
                line for line in completed.stdout.decode("utf-8").splitlines() if line
            ]
            parsed_value = json.loads(nonempty[-1])
        except (UnicodeError, json.JSONDecodeError, IndexError):
            raise QualificationSubprocessError(
                "r8_phase_output_invalid",
                observation=observation,
                parsed=None,
            ) from None
        if not isinstance(parsed_value, dict):
            raise QualificationSubprocessError(
                "r8_phase_output_invalid",
                observation=observation,
                parsed=None,
            )
        parsed = parsed_value
    if completed.returncode != 0:
        code = (
            str(parsed["failure_code"])
            if parsed and isinstance(parsed.get("failure_code"), str)
            else "r8_subprocess_failed"
        )
        raise QualificationSubprocessError(
            code,
            observation=observation,
            parsed=parsed,
        )
    return observation, parsed


def _git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise QualificationError("r8_git_preflight_failed")
    try:
        return completed.stdout.decode("utf-8").strip()
    except UnicodeError:
        raise QualificationError("r8_git_output_invalid") from None


def _port_is_available() -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", HOST_PORT))
    except OSError:
        return False
    finally:
        probe.close()
    return True


def _docker_json(
    args: list[str],
    *,
    environment: Mapping[str, str],
) -> Any:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        env=dict(environment),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise QualificationError("r8_docker_inspection_failed")
    try:
        return json.loads(completed.stdout)
    except (UnicodeError, json.JSONDecodeError):
        raise QualificationError("r8_docker_inspection_invalid") from None


def _compose_prefix() -> list[str]:
    return [
        "docker",
        "compose",
        "--project-name",
        COMPOSE_PROJECT,
        "--env-file",
        str(DOTENV_FILE),
        "-f",
        str(COMPOSE_FILE),
        "-f",
        str(QUALIFICATION_OVERRIDE),
    ]


def _project_container_ids(environment: Mapping[str, str]) -> list[str]:
    completed = subprocess.run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label=com.docker.compose.project={COMPOSE_PROJECT}",
            "--format",
            "{{.ID}}",
        ],
        cwd=ROOT,
        env=dict(environment),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise QualificationError("r8_docker_project_preflight_failed")
    return [line for line in completed.stdout.decode("utf-8").splitlines() if line]


def _volume_exists(environment: Mapping[str, str]) -> bool:
    completed = subprocess.run(
        ["docker", "volume", "inspect", f"{COMPOSE_PROJECT}_langgraph-data"],
        cwd=ROOT,
        env=dict(environment),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def _wait_healthy(environment: Mapping[str, str], *, timeout: int = 240) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ids = _project_container_ids(environment)
        if len(ids) == 3:
            rows = _docker_json(["docker", "inspect", *ids], environment=environment)
            if isinstance(rows, list) and len(rows) == 3 and all(
                row.get("State", {}).get("Running") is True
                and row.get("State", {}).get("Health", {}).get("Status")
                == "healthy"
                for row in rows
            ):
                return
        time.sleep(3)
    raise QualificationError("r8_stack_health_timeout")


def _deployment_snapshot(environment: Mapping[str, str]) -> dict[str, Any]:
    ids = _project_container_ids(environment)
    if len(ids) != 3:
        raise QualificationError("r8_container_set_invalid")
    rows = _docker_json(["docker", "inspect", *ids], environment=environment)
    services: dict[str, Any] = {}
    for row in rows:
        labels = row.get("Config", {}).get("Labels") or {}
        service = labels.get("com.docker.compose.service")
        if service not in {"langgraph-api", "langgraph-postgres", "langgraph-redis"}:
            raise QualificationError("r8_container_service_invalid")
        ports = row.get("NetworkSettings", {}).get("Ports") or {}
        if service == "langgraph-api":
            bindings = ports.get("8000/tcp")
            if bindings != [{"HostIp": "127.0.0.1", "HostPort": str(HOST_PORT)}]:
                raise QualificationError("r8_api_loopback_binding_invalid")
            env_names = {
                str(item).split("=", 1)[0]
                for item in row.get("Config", {}).get("Env") or []
            }
            if "DEEPSEEK_API_KEY" in env_names:
                raise QualificationError("r8_model_key_injected")
        elif any(value for value in ports.values() if value):
            raise QualificationError("r8_data_store_port_published")
        services[service] = {
            "container_id": str(row.get("Id")),
            "image_id": str(row.get("Image")),
            "started_at": str(row.get("State", {}).get("StartedAt")),
            "healthy": row.get("State", {}).get("Health", {}).get("Status")
            == "healthy",
        }
    volume = _docker_json(
        ["docker", "volume", "inspect", f"{COMPOSE_PROJECT}_langgraph-data"],
        environment=environment,
    )
    if not isinstance(volume, list) or len(volume) != 1:
        raise QualificationError("r8_volume_identity_invalid")
    return {
        "compose_project": COMPOSE_PROJECT,
        "host_binding": f"127.0.0.1:{HOST_PORT}",
        "services": services,
        "postgres_volume_name": volume[0].get("Name"),
        "postgres_volume_mountpoint_sha256": sha256(
            str(volume[0].get("Mountpoint", "")).encode("utf-8")
        ).hexdigest(),
    }


def _manifest(attempt_id: str, git_commit: str) -> dict[str, Any]:
    foundation = load_dell_reference_vertical_foundation(FOUNDATION_PATH)
    foundation_digest = canonical_sha256(foundation)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    token = uuid4().hex
    session_id = f"SESSION::DELL::AGENT-SERVER-R8::{token}"
    fin_thread_id = f"THREAD::DELL::AGENT-SERVER-R8::{token}"
    research_run_id = f"RUN::DELL::AGENT-SERVER-R8::{token}"
    plan = {
        "case": "DELL_AI_INFRA_REFERENCE_VERTICAL",
        "profile": ZERO_MODEL_EXECUTION_PROFILE,
        "task": "Q1 issuer truth evidence and latest revenue fact",
    }
    plan_digest = canonical_json_sha256(plan)
    session = create_agent_session_v1_2(
        session_id=session_id,
        thread_id=fin_thread_id,
        case_id=foundation.case_identity.case_id,
        case_version="FIN_0_1_3",
        as_of_date=date.fromisoformat(DELL_APPROVED_RESEARCH_AS_OF[:10]),
        objective_ref="objective://dell/live-agent-server-r8",
        objective_digest=canonical_json_sha256(
            {"question": foundation.case_identity.top_level_question_zh}
        ),
        data_snapshot_ref=(
            f"snapshot://dell/{DELL_APPROVED_DATA_SNAPSHOT_ID}"
        ),
        data_snapshot_digest=DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_DIGEST,
        runtime_policy_ref="policy://dell/zero-model-control-plane-v1",
        runtime_policy_digest=canonical_json_sha256(
            {
                "execution_profile": ZERO_MODEL_EXECUTION_PROFILE,
                "model_calls": 0,
                "live_external_research_calls": 0,
                "paid_calls": 0,
            }
        ),
        authority_refs=("authority://owner/data-gate/2026-09-03",),
        active_plan_ref="plan://dell/live-agent-server-r8/v1",
        active_plan_digest=plan_digest,
        status="ACTIVE",
        created_at=now,
        updated_at=now,
    )
    research_run = create_research_run(
        run_id=research_run_id,
        session_id=session.session_id,
        parent_run_id=None,
        origin_kind="INITIAL",
        legacy_paid_full_chain_execution_label=None,
        status="RUNNING",
        base_plan_ref=session.active_plan_ref,
        base_plan_digest=session.active_plan_digest,
        current_plan_ref=session.active_plan_ref,
        current_plan_digest=session.active_plan_digest,
        last_session_sequence=0,
        created_at=now,
        terminal_at=None,
    )
    start = create_run_invocation(
        invocation_id=f"INVOCATION::DELL::AGENT-SERVER-R8::{token}::1",
        session_id=session.session_id,
        run_id=research_run.run_id,
        ordinal=1,
        invocation_kind="START",
        status="RUNNING",
        trigger_ref=f"qualification://dell/agent-server-r8/{attempt_id}/start",
        lease_ref=f"lease://dell/agent-server-r8/{token}/1",
        started_at=now + timedelta(seconds=1),
        finished_at=None,
    )
    resume = create_run_invocation(
        invocation_id=f"INVOCATION::DELL::AGENT-SERVER-R8::{token}::2",
        session_id=session.session_id,
        run_id=research_run.run_id,
        ordinal=2,
        invocation_kind="RESUME",
        status="RUNNING",
        trigger_ref=f"qualification://dell/agent-server-r8/{attempt_id}/resume",
        lease_ref=f"lease://dell/agent-server-r8/{token}/2",
        started_at=now + timedelta(seconds=2),
        finished_at=None,
    )
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "attempt_id": attempt_id,
        "compose_project": COMPOSE_PROJECT,
        "git_commit": git_commit,
        "trace_window_start_utc": now.isoformat().replace("+00:00", "Z"),
        "agent_session": session.model_dump(mode="json"),
        "research_run": research_run.model_dump(mode="json"),
        "start_invocation": start.model_dump(mode="json"),
        "resume_invocation": resume.model_dump(mode="json"),
        "graph_input": {
            "run_id": research_run.run_id,
            "case_id": foundation.case_identity.case_id,
            "research_question": foundation.case_identity.top_level_question_zh,
            "research_as_of": DELL_APPROVED_RESEARCH_AS_OF,
            "snapshot_id": DELL_APPROVED_DATA_SNAPSHOT_ID,
            "foundation_digest": foundation_digest,
        },
        "resume_payload": {
            "action": "complete_zero_model_qualification",
            "reason": "checkpoint and restart readback passed",
        },
    }


def _exclusive_json(path: Path, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
    except FileExistsError:
        raise QualificationError("r8_receipt_path_already_exists") from None


def _preflight(environment: Mapping[str, str]) -> str:
    if _git(["rev-parse", "--show-toplevel"]).casefold() != str(ROOT).casefold():
        raise QualificationError("r8_repo_root_mismatch")
    if _git(["branch", "--show-current"]) != EXPECTED_BRANCH:
        raise QualificationError("r8_branch_mismatch")
    if _git(["status", "--porcelain"]):
        raise QualificationError("r8_git_worktree_not_clean")
    git_commit = _git(["rev-parse", "HEAD"])
    if _project_container_ids(environment):
        raise QualificationError("r8_compose_project_not_fresh")
    if _volume_exists(environment):
        raise QualificationError("r8_compose_volume_not_fresh")
    if not _port_is_available():
        raise QualificationError("r8_host_port_unavailable")
    if not all(path.is_file() for path in (COMPOSE_FILE, QUALIFICATION_OVERRIDE)):
        raise QualificationError("r8_compose_file_missing")
    if not FOUNDATION_PATH.is_file():
        raise QualificationError("r8_foundation_missing")
    return git_commit


def _assert_cross_phase_continuity(phases: Mapping[str, Mapping[str, Any]]) -> None:
    interrupted_names = (
        "start",
        "api_readback",
        "redis_readback",
        "full_stack_readback",
    )
    required_names = {*interrupted_names, "resume", "final", "langsmith"}
    if set(phases) != required_names:
        raise QualificationError("r8_cross_phase_set_incomplete")

    interrupted_fields = (
        "assistant_uuid",
        "manifest_sha256",
        "session",
        "bindings",
        "identity",
        "remote",
        "stream",
        "state",
        "observed_calls",
    )
    start = phases["start"]
    for name in interrupted_names[1:]:
        candidate = phases[name]
        if any(
            _canonical_bytes(candidate.get(field))
            != _canonical_bytes(start.get(field))
            for field in interrupted_fields
        ):
            raise QualificationError("r8_interrupted_restart_continuity_mismatch")

    completed_fields = interrupted_fields
    resume = phases["resume"]
    final = phases["final"]
    if any(
        _canonical_bytes(final.get(field))
        != _canonical_bytes(resume.get(field))
        for field in completed_fields
    ):
        raise QualificationError("r8_completed_exact_replay_mismatch")
    if (
        resume.get("session") != start.get("session")
        or resume.get("assistant_uuid") != start.get("assistant_uuid")
        or resume.get("manifest_sha256") != start.get("manifest_sha256")
        or resume.get("bindings", {}).get("start")
        != start.get("bindings", {}).get("start")
        or resume.get("state", {}).get("qualification_summary_sha256")
        != start.get("state", {}).get("qualification_summary_sha256")
    ):
        raise QualificationError("r8_start_resume_lineage_mismatch")

    completed_bindings = resume.get("bindings")
    if not isinstance(completed_bindings, Mapping) or set(completed_bindings) != {
        "start",
        "resume",
    }:
        raise QualificationError("r8_completed_binding_set_invalid")
    expected_traces: dict[str, str] = {}
    for binding in completed_bindings.values():
        if not isinstance(binding, Mapping):
            raise QualificationError("r8_completed_binding_invalid")
        invocation_id = binding.get("run_invocation_id")
        server_run_id = binding.get("server_run_id")
        if not isinstance(invocation_id, str) or not isinstance(server_run_id, str):
            raise QualificationError("r8_completed_binding_invalid")
        expected_traces[invocation_id] = server_run_id
    if len(expected_traces) != 2 or len(set(expected_traces.values())) != 2:
        raise QualificationError("r8_completed_binding_identity_invalid")

    langsmith = phases["langsmith"]
    traces = langsmith.get("traces")
    if not isinstance(traces, list) or len(traces) != 2:
        raise QualificationError("r8_langsmith_cross_phase_trace_set_invalid")
    observed_traces: dict[str, str] = {}
    for trace in traces:
        if not isinstance(trace, Mapping):
            raise QualificationError("r8_langsmith_cross_phase_trace_invalid")
        invocation_id = trace.get("run_invocation_id")
        trace_id = trace.get("trace_id")
        root_run_id = trace.get("root_run_id")
        if (
            not isinstance(invocation_id, str)
            or not isinstance(trace_id, str)
            or root_run_id != trace_id
        ):
            raise QualificationError("r8_langsmith_cross_phase_trace_invalid")
        observed_traces[invocation_id] = trace_id
    if observed_traces != expected_traces:
        raise QualificationError("r8_langsmith_cross_phase_identity_mismatch")
    if langsmith.get("manifest_sha256") != start.get("manifest_sha256"):
        raise QualificationError("r8_langsmith_cross_phase_manifest_mismatch")


def main() -> None:
    attempt_directory: Path | None = None
    commands: list[dict[str, Any]] = []
    phases: dict[str, dict[str, Any]] = {}
    phase_failures: dict[str, dict[str, Any]] = {}
    try:
        environment = _credential_environment()
        git_commit = _preflight(environment)
        local_now = datetime.now().astimezone()
        attempt_id = (
            local_now.strftime("%Y%m%dT%H%M%S%z") + "-zero-model-r8"
        )
        attempt_directory = ATTEMPTS_ROOT / attempt_id
        try:
            attempt_directory.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            raise QualificationError("r8_attempt_directory_not_fresh") from None
        receipts = attempt_directory / "receipts"
        receipts.mkdir(exist_ok=False)
        manifest = _manifest(attempt_id, git_commit)
        manifest_path = attempt_directory / "manifest.json"
        _exclusive_json(manifest_path, manifest)
        manifest_bytes = _canonical_bytes(manifest)

        compose = _compose_prefix()
        def run_step(
            step: str,
            args: list[str],
            *,
            timeout: int,
            input_bytes: bytes | None = None,
            phase_json: bool = False,
            failure_phase: str | None = None,
        ) -> dict[str, Any] | None:
            try:
                observation, parsed = _run(
                    args,
                    environment=environment,
                    input_bytes=input_bytes,
                    timeout=timeout,
                    phase_json=phase_json,
                )
            except QualificationSubprocessError as exc:
                commands.append({"step": step, **exc.observation})
                if failure_phase is not None and exc.parsed is not None:
                    phase_failures[failure_phase] = exc.parsed
                raise QualificationError(exc.code) from None
            commands.append({"step": step, **observation})
            return parsed

        run_step(
            "compose_config",
            [*compose, "config", "--quiet"],
            timeout=120,
        )
        run_step(
            "compose_up_build",
            [*compose, "up", "-d", "--build"],
            timeout=1800,
        )
        _wait_healthy(environment)
        deployment_initial = _deployment_snapshot(environment)

        def phase(runtime_phase: str, result_key: str) -> None:
            result = run_step(
                f"phase_{result_key}",
                [
                    *compose,
                    "exec",
                    "-T",
                    "langgraph-api",
                    "python",
                    PHASE_SCRIPT,
                    "--phase",
                    runtime_phase,
                ],
                timeout=900,
                input_bytes=manifest_bytes,
                phase_json=True,
                failure_phase=result_key,
            )
            if result is None:
                raise QualificationError("r8_phase_result_missing")
            phases[result_key] = result

        phase("start", "start")

        run_step(
            "restart_api",
            [*compose, "restart", "langgraph-api"],
            timeout=240,
        )
        _wait_healthy(environment)
        phase("readback", "api_readback")

        run_step(
            "restart_redis",
            [*compose, "restart", "langgraph-redis"],
            timeout=240,
        )
        _wait_healthy(environment)
        phase("readback", "redis_readback")

        run_step(
            "compose_stop",
            [*compose, "stop"],
            timeout=240,
        )
        run_step(
            "compose_start",
            [*compose, "start"],
            timeout=240,
        )
        _wait_healthy(environment)
        phase("readback", "full_stack_readback")

        phase("resume", "resume")
        phase("final", "final")
        phase("langsmith", "langsmith")
        _assert_cross_phase_continuity(phases)

        deployment_final = _deployment_snapshot(environment)
        if (
            deployment_initial["postgres_volume_name"]
            != deployment_final["postgres_volume_name"]
            or deployment_initial["postgres_volume_mountpoint_sha256"]
            != deployment_final["postgres_volume_mountpoint_sha256"]
        ):
            raise QualificationError("r8_postgres_volume_changed")
        if _git(["rev-parse", "HEAD"]) != git_commit:
            raise QualificationError("r8_git_commit_changed_during_attempt")
        if _git(["status", "--porcelain"]):
            raise QualificationError("r8_git_worktree_changed_during_attempt")

        receipt = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "status": "pass",
            "attempt_id": attempt_id,
            "git": {
                "branch": EXPECTED_BRANCH,
                "commit": git_commit,
                "clean_before_and_after": True,
            },
            "manifest": {
                "path": str(manifest_path),
                "canonical_sha256": _digest(manifest),
                "file_sha256": _file_sha256(manifest_path),
            },
            "source_hashes": {
                "compose": _file_sha256(COMPOSE_FILE),
                "qualification_override": _file_sha256(QUALIFICATION_OVERRIDE),
                "dockerfile": _file_sha256(
                    ROOT / "deploy/dell_agent_server/Dockerfile"
                ),
                "live_phase": _file_sha256(Path(__file__).with_name("live_phase.py")),
                "host_orchestrator": _file_sha256(Path(__file__)),
                "identity_schema_normalized_sha256": IDENTITY_SCHEMA_SHA256,
            },
            "deployment_initial": deployment_initial,
            "deployment_final": deployment_final,
            "commands": commands,
            "phases": phases,
            "claims": {
                "real_agent_server": True,
                "real_fin_postgres_identity_binding": True,
                "real_local_evidence_and_finance_mcp": True,
                "native_interrupt_checkpoint_resume": True,
                "api_restart_readback": True,
                "redis_process_restart_readback": True,
                "same_project_stop_start_readback": True,
                "sse_full_and_suffix_replay": True,
                "langsmith_trace_and_payload_hiding_observed": True,
                "model_provider_calls": 0,
                "live_external_research_calls": 0,
                "research_data_provider_paid_calls": 0,
                "langsmith_observability_egress": True,
            },
            "explicit_false_boundaries": {
                "distributed_exactly_once": False,
                "automatic_retry_after_unknown_outcome": False,
                "durable_pending_orphan_reconciled_lifecycle": False,
                "cross_deployment_assistant_identity_stability": False,
                "server_side_durable_profile_binding": False,
                "redis_loss_or_replacement_recovery": False,
                "ha_failover_or_disaster_recovery": False,
                "product_multi_agent_execution": False,
                "deepseek_or_any_model_execution": False,
                "live_external_research_execution": False,
                "evidence_admission_or_s2_write": False,
                "frontend_hitl": False,
                "final_dell_report": False,
                "production_auth_or_multitenant_security": False,
            },
        }
        receipt_path = receipts / "dell-agent-server-live-r8-qualification.json"
        _exclusive_json(receipt_path, receipt)
        print(
            json.dumps(
                {
                    "status": "pass",
                    "attempt_id": attempt_id,
                    "receipt": str(receipt_path),
                    "receipt_canonical_sha256": _digest(receipt),
                    "receipt_file_sha256": _file_sha256(receipt_path),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
    except QualificationError as exc:
        failure = {
            "schema_version": FAILURE_SCHEMA_VERSION,
            "status": "failed",
            "failure_code": exc.code,
            "compose_project": COMPOSE_PROJECT,
            "host_port": HOST_PORT,
            "commands": commands,
            "completed_phase_names": sorted(phases),
            "phase_failures": phase_failures,
            "cleanup_performed": False,
            "prior_attempts_modified": False,
            "model_or_paid_call_authorized": False,
        }
        if attempt_directory is not None:
            receipts = attempt_directory / "receipts"
            receipts.mkdir(exist_ok=True)
            try:
                _exclusive_json(
                    receipts / "dell-agent-server-live-r8-failure.json",
                    failure,
                )
            except QualificationError:
                pass
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True), flush=True)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
