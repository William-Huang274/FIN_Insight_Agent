"""Host launcher for one fail-closed Dell Q1 Specialist paid shadow."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
from typing import Any

from sec_agent.agent_runtime.dell_specialist_paid_shadow import (
    DellQ1SpecialistPaidShadowAuthority,
    file_sha256,
    load_dell_q1_paid_shadow_authority,
)


ROOT = Path(__file__).resolve().parents[3]
BASE_COMPOSE = ROOT / "deploy/dell_agent_server/compose.yaml"
PAID_OVERLAY = ROOT / "deploy/dell_agent_server/compose.q1-specialist-paid-shadow.yaml"
DOTENV_FILE = ROOT / ".env"
DEFAULT_AUTHORITY = ROOT / "configs/research/evals/fin_ia_0_1_3_s3_dell_q1_specialist_paid_shadow_authority_v1_0.json"
ATTEMPTS_ROOT = Path("Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts")
CONTAINER_SCRIPT = "/opt/fin-insight-qualification/dell-q1-specialist-paid-shadow/container_once.py"
EXPECTED_BRANCH = "codex/fin013-dell-s1-s2-product-bridge"
_EXECUTION_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{7,159}$")
_SECRETS = (
    "FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD",
    "LANGSMITH_API_KEY",
    "DEEPSEEK_API_KEY",
)


class HostRunError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise HostRunError("paid_shadow_non_json_value") from None


def _digest(value: Any) -> str:
    return sha256(_bytes(value)).hexdigest()


def _write_new(path: Path, value: Any) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError:
        raise HostRunError("paid_shadow_receipt_exists") from None


def _dotenv() -> dict[str, str]:
    if not DOTENV_FILE.is_file():
        raise HostRunError("paid_shadow_dotenv_missing")
    try:
        lines = DOTENV_FILE.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        raise HostRunError("paid_shadow_dotenv_unreadable") from None
    values: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) > 1 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _git(*args: str) -> str:
    run = subprocess.run(
        ["git", *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    if run.returncode:
        raise HostRunError("paid_shadow_git_check_failed")
    return run.stdout.decode("utf-8").strip()


def _preflight_git(authority: DellQ1SpecialistPaidShadowAuthority, path: Path) -> str:
    if Path(_git("rev-parse", "--show-toplevel")).resolve() != ROOT.resolve():
        raise HostRunError("paid_shadow_repository_mismatch")
    if _git("branch", "--show-current") != EXPECTED_BRANCH:
        raise HostRunError("paid_shadow_branch_mismatch")
    if _git("status", "--porcelain"):
        raise HostRunError("paid_shadow_worktree_not_clean")
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{u}"):
        raise HostRunError("paid_shadow_head_not_pushed")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", authority.implementation_commit, head],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    relative = path.relative_to(ROOT).as_posix()
    changed = _git(
        "diff", "--name-only", f"{authority.implementation_commit}..{head}", "--"
    ).splitlines()
    if (
        ancestor.returncode
        or relative not in changed
        or any(item != relative and not item.startswith("docs/") for item in changed)
    ):
        raise HostRunError("paid_shadow_implementation_boundary_invalid")
    return head


def _environment(
    authority: DellQ1SpecialistPaidShadowAuthority,
    authority_path: Path,
    attempt: Path,
    port: int,
) -> dict[str, str]:
    saved = _dotenv()
    env = dict(os.environ)
    for name in _SECRETS:
        value = env.get(name) or saved.get(name)
        if not value:
            raise HostRunError(f"paid_shadow_secret_missing:{name}")
        env[name] = value
    seed = env["FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD"]

    def derived(label: str) -> str:
        return sha256(f"fin-q1-shadow:{label}\0{seed}".encode("utf-8")).hexdigest()

    env.update(
        {
            "FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD": derived("bootstrap"),
            "FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD": derived("langgraph"),
            "FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD": derived("fin-runtime"),
            "FINSIGHT_FIN_RUNTIME_OPERATOR_POSTGRES_PASSWORD": derived("operator"),
            "FINSIGHT_AGENT_SERVER_HOST_PORT": str(port),
            "FINSIGHT_DELL_IMPLEMENTATION_COMMIT": authority.implementation_commit,
            "FINSIGHT_DELL_PAID_SHADOW_AUTHORITY_HOST_PATH": authority_path.as_posix(),
            "FINSIGHT_DELL_PAID_SHADOW_ARTIFACT_HOST_PATH": attempt.as_posix(),
            "FINSIGHT_DELL_PAID_SHADOW_ARTIFACT_CONTAINER_PATH": authority.artifact_root_container,
        }
    )
    return env


def _compose(project: str) -> list[str]:
    return [
        "docker", "compose", "--project-name", project, "--env-file", str(DOTENV_FILE),
        "-f", str(BASE_COMPOSE), "-f", str(PAID_OVERLAY),
    ]


def _containers(project: str, env: Mapping[str, str]) -> list[str]:
    run = subprocess.run(
        [
            "docker", "ps", "-a", "--filter",
            f"label=com.docker.compose.project={project}", "--format", "{{.ID}}",
        ],
        cwd=ROOT,
        env=dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if run.returncode:
        raise HostRunError("paid_shadow_docker_probe_failed")
    return run.stdout.decode("utf-8").splitlines()


def _volume_exists(project: str, env: Mapping[str, str]) -> bool:
    return subprocess.run(
        ["docker", "volume", "inspect", f"{project}_langgraph-data"],
        cwd=ROOT,
        env=dict(env),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def _port_free(port: int) -> bool:
    probe = socket.socket()
    try:
        probe.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def _command(
    args: Sequence[str], env: Mapping[str, str], timeout: int, *, json_result: bool = False
) -> tuple[dict[str, Any], Mapping[str, Any] | None]:
    started = time.monotonic()
    try:
        run = subprocess.run(
            list(args), cwd=ROOT, env=dict(env), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        raise HostRunError("paid_shadow_subprocess_timeout") from None
    observation = {
        "argv_sha256": _digest(list(args)),
        "returncode": run.returncode,
        "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
        "stdout_sha256": sha256(run.stdout).hexdigest(),
        "stderr_sha256": sha256(run.stderr).hexdigest(),
    }
    parsed: Mapping[str, Any] | None = None
    if json_result:
        try:
            parsed = json.loads(
                [line for line in run.stdout.decode("utf-8").splitlines() if line][-1]
            )
        except (UnicodeError, json.JSONDecodeError, IndexError):
            raise HostRunError("paid_shadow_container_result_invalid") from None
    if run.returncode:
        error = HostRunError(
            str(parsed.get("failure_code") if isinstance(parsed, Mapping) else "paid_shadow_subprocess_failed")
        )
        error.observation = observation
        error.parsed = parsed
        raise error
    return observation, parsed


def _wait_healthy(project: str, env: Mapping[str, str]) -> tuple[str, list[str]]:
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        ids = _containers(project, env)
        if len(ids) == 3:
            raw = subprocess.run(
                ["docker", "inspect", *ids], cwd=ROOT, env=dict(env),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            if not raw.returncode:
                rows = json.loads(raw.stdout)
                if all(
                    row.get("State", {}).get("Health", {}).get("Status") == "healthy"
                    for row in rows
                ):
                    api = next(
                        row for row in rows
                        if row.get("Config", {}).get("Labels", {}).get(
                            "com.docker.compose.service"
                        ) == "langgraph-api"
                    )
                    return str(api["Image"]), sorted(ids)
        time.sleep(3)
    raise HostRunError("paid_shadow_stack_not_healthy")


def run_once(authority_path: Path) -> None:
    attempt: Path | None = None
    attempt_created = False
    commands: list[dict[str, Any]] = []
    project: str | None = None
    port: int | None = None
    try:
        authority_path = authority_path.resolve()
        authority = load_dell_q1_paid_shadow_authority(authority_path)
        if (
            authority_path.parent != (ROOT / "configs/research/evals").resolve()
            or not _EXECUTION_ID.fullmatch(authority.paid_full_chain_execution_id)
        ):
            raise HostRunError("paid_shadow_authority_scope_invalid")
        head = _preflight_git(authority, authority_path)
        project = f"finsight-dell-q1-paid-{authority.decision_digest[:12]}"
        port = 18140 + int(authority.decision_digest[:8], 16) % 40
        attempt = ATTEMPTS_ROOT / authority.paid_full_chain_execution_id
        if attempt.exists() or not _port_free(port):
            raise HostRunError("paid_shadow_attempt_or_port_not_fresh")
        env = _environment(authority, authority_path, attempt, port)
        if _containers(project, env) or _volume_exists(project, env):
            raise HostRunError("paid_shadow_project_or_volume_not_fresh")
        attempt.parent.mkdir(parents=True, exist_ok=True)
        attempt.mkdir(exist_ok=False)
        attempt_created = True
        compose = _compose(project)
        observation, _ = _command([*compose, "config", "--quiet"], env, 120)
        commands.append({"step": "compose_config", **observation})
        observation, _ = _command([*compose, "up", "-d", "--build"], env, 1800)
        commands.append({"step": "compose_up", **observation})
        image_id, container_ids = _wait_healthy(project, env)
        observation, result = _command(
            [
                *compose, "exec", "-T", "langgraph-api", "python",
                CONTAINER_SCRIPT,
            ],
            env,
            3600,
            json_result=True,
        )
        commands.append({"step": "single_specialist_run", **observation})
        if not isinstance(result, Mapping) or result.get("status") not in {
            "pass", "bounded_handoff",
        }:
            raise HostRunError("paid_shadow_container_result_invalid")
        expected = (
            authority.agent_session_id,
            authority.fin_thread_id,
            authority.research_run_id,
            authority.run_invocation_id,
        )
        observed = tuple(
            result.get(key)
            for key in (
                "agent_session_id", "fin_thread_id", "research_run_id", "run_invocation_id"
            )
        )
        if observed != expected or _git("rev-parse", "HEAD") != head or _git("status", "--porcelain"):
            raise HostRunError("paid_shadow_final_binding_invalid")
        receipt = {
            "schema_version": "fin_ia_dell_q1_specialist_paid_shadow_receipt_v1_0",
            "status": result["status"],
            "paid_execution_id": authority.paid_full_chain_execution_id,
            "identity": {
                key: result[key]
                for key in (
                    "agent_session_id", "fin_thread_id", "research_run_id",
                    "run_invocation_id", "server_thread_id", "server_run_id",
                )
            },
            "git": {
                "branch": EXPECTED_BRANCH,
                "implementation_commit": authority.implementation_commit,
                "authority_commit": head,
                "clean_and_pushed": True,
            },
            "authority": {
                "decision_id": authority.decision_id,
                "decision_digest": authority.decision_digest,
                "file_sha256": file_sha256(authority_path),
            },
            "deployment": {
                "compose_project": project,
                "host_port": port,
                "postgres_volume": f"{project}_langgraph-data",
                "container_ids": container_ids,
                "image_id": image_id,
            },
            "trace_ids": {
                "agent_server": result["server_run_id"],
                "langsmith": result["langsmith"]["trace_id"],
            },
            "graph_input_digest": result["graph_input_digest"],
            "terminal": result["terminal"],
            "stream": result["stream"],
            "private_state": result["private_state"],
            "model_audit": result["model_audit"],
            "langsmith": result["langsmith"],
            "commands": commands,
            "no_retry_resume_or_fallback": True,
            "cleanup_performed": False,
        }
        receipt["receipt_digest"] = _digest(receipt)
        receipt_path = attempt / "terminal-receipt.json"
        _write_new(receipt_path, receipt)
        print(json.dumps({
            "status": receipt["status"],
            "receipt": str(receipt_path),
            "receipt_digest": receipt["receipt_digest"],
            "receipt_file_sha256": file_sha256(receipt_path),
        }, ensure_ascii=False, sort_keys=True), flush=True)
    except Exception as exc:
        if hasattr(exc, "observation"):
            commands.append({"step": "failed", **exc.observation})
        failure = {
            "schema_version": "fin_ia_dell_q1_specialist_paid_shadow_failure_v1_0",
            "status": "failed",
            "failure_code": str(getattr(exc, "code", "paid_shadow_host_failed")),
            "project": project,
            "port": port,
            "commands": commands,
            "container_result": getattr(exc, "parsed", None),
            "no_retry_resume_or_fallback": True,
            "cleanup_performed": False,
            "human_review_required": True,
        }
        if attempt is not None and attempt_created:
            try:
                _write_new(attempt / "failed-receipt.json", failure)
            except (HostRunError, OSError):
                pass
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True), flush=True)
        raise SystemExit(2) from None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", type=Path, default=DEFAULT_AUTHORITY)
    run_once(parser.parse_args().authority)


if __name__ == "__main__":
    main()
