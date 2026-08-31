from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
from importlib import metadata as importlib_metadata
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence
from urllib.parse import quote
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
QUALIFICATION_BASE_ROOT = Path("Z:/FIN_Insight_Agent_qualification")
POSTGRES_IMAGE = (
    "postgres@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685"
)
POSTGRES_VERSION = "16.15"
REQUIRED_UV_VERSION = "0.10.7"
DOCKER_ATTEMPT_LABEL = "com.finsight.qualification.attempt"
QUALIFICATION_NETWORK_DRIVER = "bridge"
QUALIFICATION_NETWORK_HOST_BINDING_OPTION = (
    "com.docker.network.bridge.host_binding_ipv4"
)
QUALIFICATION_NETWORK_HOST_BINDING_ADDRESS = "127.0.0.1"
POLICY_REF = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_company_financial_fact_mart_policy_v1_0.json"
)
TRACKED_RESULT_REF = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_company_financial_fact_mart_result_v1_1.json"
)
EXPECTED_TRACKED_RESULT_DIGEST = (
    "0c25c917f08e4e14b30d481d0dbb2724b951797c052e52b0ff940b2971f595a1"
)
EXPECTED_OBSERVATION_DIGEST = (
    "8bb7b9f452e9ad5d1da4f50b565aba8397a05f40d7ecd3a5b09e5a438af3ed97"
)
IMPLEMENTATION_REFS = (
    "scripts/qualification/run_postgres_dagster_s2_fact_mart_vertical.py",
    "src/sec_agent/adapters/dagster_control_plane_launcher.py",
    "src/sec_agent/adapters/dagster_s2_fact_mart.py",
    "scripts/data_retrieval/build_s2_company_financial_fact_mart.py",
    POLICY_REF,
    TRACKED_RESULT_REF,
    "pyproject.toml",
    "uv.lock",
    "Dockerfile",
    "compose.yaml",
    "configs/control_plane/dagster.postgres.yaml",
    "configs/control_plane/s2_fact_mart_shadow.run_config.example.yaml",
)
REQUIRED_DAGSTER_EVENT_TYPES = frozenset(
    {"PIPELINE_START", "STEP_START", "STEP_SUCCESS", "PIPELINE_SUCCESS"}
)
REQUIRED_RUNTIME_VERSIONS = {
    "dagster": "1.13.20",
    "dagster-postgres": "0.29.20",
    "dagster-webserver": "1.13.20",
    "filelock": "3.32.4",
    "psycopg": "3.3.4",
    "psycopg-binary": "3.3.4",
}


class ExpectedRollback(RuntimeError):
    pass


def validate_qualification_root(
    path: Path,
    *,
    allowed_root: Path = QUALIFICATION_BASE_ROOT,
) -> Path:
    """Resolve and contain qualification output inside the approved Z: lab root."""

    qualification_root = path.resolve()
    approved_root = allowed_root.resolve()
    try:
        qualification_root.relative_to(approved_root)
    except ValueError as exc:
        raise RuntimeError(
            "qualification_root_must_be_under_Z_fin_insight_qualification"
        ) from exc
    return qualification_root


def validate_qualification_host_port(value: int) -> int:
    """Keep the host-runner qualification on an explicit unprivileged TCP port."""

    if isinstance(value, bool) or not 1024 <= value <= 65535:
        raise ValueError("qualification_host_port_must_be_between_1024_and_65535")
    return value


def validate_qualification_network(
    payload: Mapping[str, Any],
    *,
    attempt_id: str,
) -> dict[str, Any]:
    """Validate the Windows host-runner loopback bridge contract.

    The financial builder and Dagster process run on the host in this qualification,
    so a Docker ``--internal`` network cannot isolate those processes. On Docker
    Desktop it also makes the explicitly published PostgreSQL port unreachable from
    the host. This profile limits PostgreSQL exposure to host loopback; it does not
    claim container or host-runner egress isolation.
    """

    driver = str(payload.get("Driver") or "")
    internal = bool(payload.get("Internal"))
    options = payload.get("Options")
    if not isinstance(options, Mapping):
        options = {}
    labels = payload.get("Labels")
    if not isinstance(labels, Mapping):
        labels = {}
    host_binding = str(
        options.get(QUALIFICATION_NETWORK_HOST_BINDING_OPTION) or ""
    )
    attempt_label_match = labels.get(DOCKER_ATTEMPT_LABEL) == attempt_id
    receipt = {
        "driver": driver,
        "internal": internal,
        "default_host_binding_ipv4": host_binding,
        "attempt_label_match": attempt_label_match,
        "postgres_host_exposure": "loopback_only",
        "postgres_container_egress_blocked_by_network": False,
        "host_runner_egress_blocked_by_network": False,
        "isolation_claim": "loopback_host_exposure_only_not_egress_isolation",
    }
    if (
        driver != QUALIFICATION_NETWORK_DRIVER
        or internal
        or host_binding != QUALIFICATION_NETWORK_HOST_BINDING_ADDRESS
        or not attempt_label_match
    ):
        raise AssertionError(
            "qualification_network_loopback_bridge_contract_failed:"
            + canonical_json(receipt)
        )
    receipt["pass"] = True
    return receipt


def validate_postgres_container_network_contract(
    payload: Mapping[str, Any],
    *,
    attempt_id: str,
    network_name: str,
    host_port: int,
) -> dict[str, Any]:
    """Read back loopback publication, ownership, mounts, and network attachment."""

    config = payload.get("Config")
    host_config = payload.get("HostConfig")
    network_settings = payload.get("NetworkSettings")
    mounts = payload.get("Mounts")
    if not isinstance(config, Mapping):
        config = {}
    if not isinstance(host_config, Mapping):
        host_config = {}
    if not isinstance(network_settings, Mapping):
        network_settings = {}
    if not isinstance(mounts, list):
        mounts = []

    labels = config.get("Labels")
    if not isinstance(labels, Mapping):
        labels = {}
    attempt_label_match = labels.get(DOCKER_ATTEMPT_LABEL) == attempt_id

    port_bindings = host_config.get("PortBindings")
    if not isinstance(port_bindings, Mapping):
        port_bindings = {}
    postgres_bindings = port_bindings.get("5432/tcp")
    expected_bindings = [
        {
            "HostIp": QUALIFICATION_NETWORK_HOST_BINDING_ADDRESS,
            "HostPort": str(host_port),
        }
    ]

    networks = network_settings.get("Networks")
    if not isinstance(networks, Mapping):
        networks = {}
    attached_networks = sorted(str(name) for name in networks)

    mount_receipt: dict[str, bool] = {}
    mount_destinations: list[str] = []
    for mount in mounts:
        if not isinstance(mount, Mapping):
            continue
        destination = str(mount.get("Destination") or "")
        mount_destinations.append(destination)
        mount_receipt[destination] = bool(mount.get("RW"))

    environment = config.get("Env")
    if not isinstance(environment, list):
        environment = []
    environment_names = {
        str(item).partition("=")[0] for item in environment if isinstance(item, str)
    }
    forbidden_credential_or_proxy_environment_names = sorted(
        name
        for name in environment_names
        if (
            name.upper().endswith(
                ("_API_KEY", "_CREDENTIAL", "_CREDENTIALS", "_PASSWORD", "_SECRET", "_TOKEN")
            )
            or "_SECRET_" in name.upper()
            or name.upper()
            in {
                "ALL_PROXY",
                "AWS_ACCESS_KEY_ID",
                "DATABASE_URL",
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "NO_PROXY",
                "POSTGRES_PASSWORD",
            }
        )
        and name.upper() != "POSTGRES_PASSWORD_FILE"
    )

    network_mode = str(host_config.get("NetworkMode") or "")
    expected_mounts = {
        "/run/secrets/postgres_password": False,
        "/var/lib/postgresql/data": True,
    }
    receipt = {
        "attempt_label_match": attempt_label_match,
        "network_mode": network_mode,
        "attached_networks": attached_networks,
        "postgres_port_bindings": postgres_bindings,
        "mount_destinations": sorted(mount_destinations),
        "provider_or_proxy_environment_present": bool(
            forbidden_credential_or_proxy_environment_names
        ),
        "private_captures_mounted": any(
            "raw_private" in destination.lower()
            or "capture" in destination.lower()
            for destination in mount_destinations
        ),
        "container_egress_possible": True,
    }
    if (
        not attempt_label_match
        or network_mode != network_name
        or attached_networks != [network_name]
        or set(port_bindings) != {"5432/tcp"}
        or postgres_bindings != expected_bindings
        or mount_receipt != expected_mounts
        or forbidden_credential_or_proxy_environment_names
        or receipt["private_captures_mounted"]
    ):
        raise AssertionError(
            "postgres_container_network_contract_failed:" + canonical_json(receipt)
        )
    receipt["pass"] = True
    return receipt


def validate_postgres_effective_port_binding(
    payload: Mapping[str, Any],
    *,
    host_port: int,
) -> dict[str, Any]:
    """Confirm the running container exposes PostgreSQL only on host loopback."""

    network_settings = payload.get("NetworkSettings")
    if not isinstance(network_settings, Mapping):
        network_settings = {}
    ports = network_settings.get("Ports")
    if not isinstance(ports, Mapping):
        ports = {}
    bindings = ports.get("5432/tcp")
    expected = [
        {
            "HostIp": QUALIFICATION_NETWORK_HOST_BINDING_ADDRESS,
            "HostPort": str(host_port),
        }
    ]
    receipt = {"effective_postgres_port_bindings": bindings}
    if set(ports) != {"5432/tcp"} or bindings != expected:
        raise AssertionError(
            "postgres_effective_port_binding_contract_failed:"
            + canonical_json(receipt)
        )
    receipt["pass"] = True
    return receipt


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def redact_sensitive_text(value: str, sensitive_values: Sequence[str]) -> str:
    redacted = value
    for sensitive in sorted(
        (item for item in sensitive_values if item),
        key=len,
        reverse=True,
    ):
        redacted = redacted.replace(sensitive, "[REDACTED]")
    return redacted


def sensitive_text_scan(
    value: str,
    *,
    sensitive_values: Sequence[str],
) -> dict[str, Any]:
    """Check serialized output without returning any matched sensitive value."""

    active_values = tuple(dict.fromkeys(item for item in sensitive_values if item))
    matching_value_count = sum(item in value for item in active_values)
    return {
        "checked_distinct_value_count": len(active_values),
        "matching_value_count": matching_value_count,
        "pass": matching_value_count == 0,
    }


def secret_persistence_scan(root: Path, *, secret: str) -> dict[str, Any]:
    """Prove that the ephemeral plaintext credential did not enter artifacts."""

    if not secret:
        raise ValueError("secret_persistence_scan_requires_nonempty_secret")
    needle = secret.encode("utf-8")
    overlap_size = len(needle) - 1
    matches: list[str] = []
    scanned = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        scanned += 1
        overlap = b""
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                candidate = overlap + block
                if needle in candidate:
                    matches.append(path.relative_to(root).as_posix())
                    break
                overlap = candidate[-overlap_size:] if overlap_size else b""
    return {
        "files_scanned": scanned,
        "matching_file_count": len(matches),
        "matching_files": matches,
        "pass": not matches,
    }


def validate_result_digest(payload: Mapping[str, Any]) -> str:
    claimed = payload.get("result_digest")
    unsigned = {key: value for key, value in payload.items() if key != "result_digest"}
    actual = sha256_json(unsigned)
    if not isinstance(claimed, str) or claimed != actual:
        raise AssertionError("tracked_s2_result_self_digest_invalid")
    return actual


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def run_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    environment: Mapping[str, str] | None = None,
    check: bool = True,
    timeout_seconds: int = 300,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd) if cwd else None,
            env=dict(environment) if environment is not None else None,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout if isinstance(error.stdout, str) else ""
        stderr = error.stderr if isinstance(error.stderr, str) else ""
        if check:
            raise RuntimeError(
                "command_timeout:"
                + canonical_json(
                    {"command": list(command), "timeout_seconds": timeout_seconds}
                )
            ) from error
        completed = subprocess.CompletedProcess(
            list(command),
            124,
            stdout=stdout,
            stderr=stderr + f"\ncommand_timeout_after_{timeout_seconds}_seconds",
        )
    if check and completed.returncode != 0:
        raise RuntimeError(
            "command_failed:"
            + canonical_json(
                {
                    "command": list(command),
                    "returncode": completed.returncode,
                    "stdout_tail": completed.stdout[-4000:],
                    "stderr_tail": completed.stderr[-4000:],
                }
            )
        )
    return completed


def implementation_binding() -> dict[str, Any]:
    repository_head = run_command(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
    ).stdout.strip()
    repository_branch = run_command(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=ROOT,
    ).stdout.strip()
    status = run_command(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
    ).stdout
    diff = run_command(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--", *IMPLEMENTATION_REFS],
        cwd=ROOT,
    ).stdout
    files = {}
    for ref in IMPLEMENTATION_REFS:
        path = ROOT / ref
        if not path.is_file():
            raise RuntimeError(f"implementation_binding_file_missing:{ref}")
        files[ref] = sha256_file(path)
    return {
        "repository_head": repository_head,
        "repository_branch": repository_branch,
        "git_status_clean": not bool(status.strip()),
        "git_status_porcelain_sha256": sha256_text(status),
        "tracked_diff_sha256": sha256_text(diff),
        "files_sha256": files,
    }


def validate_interpreter_location(*, executable: Path, qualification_root: Path) -> Path:
    resolved_executable = executable.resolve()
    try:
        resolved_executable.relative_to(qualification_root.resolve())
    except ValueError as exc:
        raise RuntimeError(
            "qualification_interpreter_must_be_under_qualification_root"
        ) from exc
    return resolved_executable


def locked_environment_check(
    *,
    project_root: Path,
    environment_prefix: Path,
    command_runner: Any | None = None,
) -> dict[str, Any]:
    """Require uv to prove that the selected locked profile needs no changes."""

    runner = command_runner or run_command
    uv_version_output = runner(["uv", "--version"], cwd=project_root).stdout.strip()
    uv_version_parts = uv_version_output.split()
    if (
        len(uv_version_parts) < 2
        or uv_version_parts[0] != "uv"
        or uv_version_parts[1] != REQUIRED_UV_VERSION
    ):
        raise RuntimeError(
            "qualification_uv_version_mismatch:"
            + canonical_json(
                {
                    "expected": REQUIRED_UV_VERSION,
                    "actual_output": uv_version_output,
                }
            )
        )
    command = [
        "uv",
        "--project",
        str(project_root),
        "sync",
        "--locked",
        "--check",
        "--no-dev",
        "--extra",
        "control-plane",
        "--extra",
        "qualification",
        "--no-install-project",
    ]
    environment = dict(os.environ)
    environment["UV_PROJECT_ENVIRONMENT"] = str(environment_prefix.resolve())
    completed = runner(
        command,
        cwd=project_root,
        environment=environment,
    )
    return {
        "pass": completed.returncode == 0,
        "uv_version": REQUIRED_UV_VERSION,
        "profile": "core+control-plane+qualification_without_dev_or_first_party",
        "environment_prefix": str(environment_prefix.resolve()),
        "stdout_sha256": sha256_text(completed.stdout),
        "stderr_sha256": sha256_text(completed.stderr),
    }


def runtime_environment_receipt(qualification_root: Path) -> dict[str, Any]:
    """Bind the attempt to the exact clean, locked interpreter environment."""

    executable = validate_interpreter_location(
        executable=Path(sys.executable),
        qualification_root=qualification_root,
    )
    environment_prefix = Path(sys.prefix).resolve()
    locked_check = locked_environment_check(
        project_root=ROOT,
        environment_prefix=environment_prefix,
    )
    inventory = sorted(
        (
            {
                "name": str(distribution.metadata.get("Name", "")).lower(),
                "version": distribution.version,
            }
            for distribution in importlib_metadata.distributions()
            if distribution.metadata.get("Name")
        ),
        key=lambda row: (row["name"], row["version"]),
    )
    installed = {row["name"]: row["version"] for row in inventory}
    mismatches = {
        name: {"expected": expected, "actual": installed.get(name)}
        for name, expected in REQUIRED_RUNTIME_VERSIONS.items()
        if installed.get(name) != expected
    }
    if mismatches:
        raise RuntimeError(
            "qualification_runtime_version_mismatch:" + canonical_json(mismatches)
        )
    if "finsight-agent" in installed:
        raise RuntimeError("qualification_environment_must_not_install_first_party_project")
    return {
        "python_executable": str(executable),
        "python_version": sys.version,
        "python_prefix": str(environment_prefix),
        "locked_environment_check": locked_check,
        "required_direct_versions": REQUIRED_RUNTIME_VERSIONS,
        "installed_distribution_count": len(inventory),
        "installed_distributions": inventory,
        "installed_distributions_sha256": sha256_json(inventory),
        "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
        "pyproject_sha256": sha256_file(ROOT / "pyproject.toml"),
    }


def validate_module_origin(module: Any, *, expected_path: Path) -> str:
    origin_value = getattr(module, "__file__", None)
    if not origin_value:
        raise RuntimeError("qualification_runtime_module_origin_missing")
    origin = Path(origin_value).resolve()
    expected = expected_path.resolve()
    if origin != expected:
        raise RuntimeError(
            "qualification_runtime_module_origin_mismatch:"
            + canonical_json({"expected": str(expected), "actual": str(origin)})
        )
    return str(origin)


def restrict_path_access(path: Path, *, mode: int) -> dict[str, Any]:
    os.chmod(path, mode)
    receipt: dict[str, Any] = {
        "mode_requested": format(mode, "04o"),
        "acl_restricted": False,
    }
    if os.name == "nt":
        identity = run_command(["whoami"]).stdout.strip()
        acl = run_command(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"{identity}:(F)",
                "*S-1-5-18:(F)",
                "*S-1-5-32-544:(F)",
            ]
        )
        verification = run_command(["icacls", str(path)])
        receipt.update(
            {
                "acl_restricted": True,
                "acl_command_sha256": sha256_text(acl.stdout + acl.stderr),
                "acl_verification_sha256": sha256_text(
                    verification.stdout + verification.stderr
                ),
            }
        )
    return receipt


def prepare_restricted_secret_directory(path: Path) -> dict[str, Any]:
    path.mkdir(exist_ok=False)
    return restrict_path_access(path, mode=0o700)


def write_restricted_secret(path: Path, value: str) -> dict[str, Any]:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(value)
    return restrict_path_access(path, mode=0o600)


def dagster_event_receipt(entries: Sequence[Any]) -> dict[str, Any]:
    projection = []
    event_type_counts: dict[str, int] = {}
    for entry in entries:
        event_type = getattr(entry, "dagster_event_type", None)
        event_type_value = (
            str(getattr(event_type, "value", event_type)) if event_type else None
        )
        if event_type_value:
            event_type_counts[event_type_value] = event_type_counts.get(event_type_value, 0) + 1
        projection.append(
            {
                "run_id": str(getattr(entry, "run_id", "")),
                "timestamp": float(getattr(entry, "timestamp", 0.0)),
                "level": str(getattr(entry, "level", "")),
                "step_key": getattr(entry, "step_key", None),
                "event_type": event_type_value,
                "message": str(getattr(entry, "message", "")),
            }
        )
    return {
        "event_count": len(projection),
        "event_type_counts": dict(sorted(event_type_counts.items())),
        "events_sha256": sha256_json(projection),
    }


def validate_dagster_event_receipt(receipt: Mapping[str, Any]) -> None:
    counts = receipt.get("event_type_counts")
    observed = set(counts) if isinstance(counts, Mapping) else set()
    missing = sorted(REQUIRED_DAGSTER_EVENT_TYPES - observed)
    if int(receipt.get("event_count") or 0) <= 0 or missing:
        raise AssertionError(
            "dagster_postgres_required_events_missing:" + canonical_json(missing)
        )


def dagster_run_readback(instance: Any, run_id: str) -> dict[str, Any]:
    run = instance.get_run_by_id(run_id)
    if run is None:
        return {"run_found": False, "run_status": None, "event_count": 0, "events_sha256": None}
    event_receipt = dagster_event_receipt(instance.all_logs(run_id))
    return {
        "run_found": True,
        "run_status": str(run.status.value),
        **event_receipt,
    }


def docker_absence_confirmed(
    completed: subprocess.CompletedProcess[str],
    *,
    kind: str,
    name: str,
) -> bool:
    if completed.returncode == 0:
        return False
    message = (completed.stdout + completed.stderr).lower()
    if kind == "container":
        return f"no such container: {name}".lower() in message
    if kind == "network":
        return f"network {name} not found".lower() in message
    raise ValueError(f"unsupported_docker_object_kind:{kind}")


def docker_object_owned_by_attempt(
    completed: subprocess.CompletedProcess[str],
    *,
    kind: str,
    attempt_id: str,
) -> bool:
    if completed.returncode != 0:
        return False
    try:
        payload = json.loads(completed.stdout)
        row = payload[0]
        labels = (
            row.get("Config", {}).get("Labels", {})
            if kind == "container"
            else row.get("Labels", {})
        )
    except (IndexError, KeyError, TypeError, json.JSONDecodeError):
        return False
    if not isinstance(labels, Mapping):
        return False
    return labels.get(DOCKER_ATTEMPT_LABEL) == attempt_id


def fact_mart_semantic_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Compare business output while excluding output-path-specific receipt fields."""

    storage = payload.get("storage") or {}
    return {
        "status": payload.get("status"),
        "counts": payload.get("counts"),
        "observation_digest": storage.get("observation_digest"),
        "source_summary": payload.get("source_summary"),
        "qrel_evaluation": payload.get("qrel_evaluation"),
        "mutation_evaluation": payload.get("mutation_evaluation"),
        "acceptance": payload.get("acceptance"),
        "policy_digest": payload.get("policy_digest"),
        "known_boundary": payload.get("known_boundary"),
    }


def run_fact_mart_builder(
    *,
    policy_path: Path,
    sqlite_path: Path,
    result_path: Path,
) -> dict[str, Any]:
    completed = run_command(
        [
            sys.executable,
            "-m",
            "scripts.data_retrieval.build_s2_company_financial_fact_mart",
            "--policy",
            str(policy_path),
            "--sqlite",
            str(sqlite_path),
            "--output",
            str(result_path),
        ],
        cwd=ROOT,
    )
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("fact_mart_result_object_required")
    payload["qualification_cli_stdout"] = completed.stdout.strip()
    return payload


def wait_for_postgres(container_name: str, *, timeout_seconds: int = 90) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        # The official image briefly starts a temporary server during initdb.
        # pg_isready can report that server as ready before the requested
        # database exists, immediately before the entrypoint stops it.  Require
        # PID 1 to have exec'd the final postgres process and then run a real
        # query against the requested database.
        final_process = run_command(
            [
                "docker",
                "exec",
                container_name,
                "sh",
                "-c",
                'test "$(cat /proc/1/comm)" = postgres',
            ],
            check=False,
        )
        ready = run_command(
            [
                "docker",
                "exec",
                container_name,
                "psql",
                "--username",
                "finsight_qualification",
                "--dbname",
                "finsight_qualification",
                "--tuples-only",
                "--no-align",
                "--command",
                "SELECT 1",
            ],
            check=False,
        )
        if (
            final_process.returncode == 0
            and ready.returncode == 0
            and ready.stdout.strip() == "1"
        ):
            return
        time.sleep(1)
    raise RuntimeError("postgres_readiness_timeout")


def qualification_rows(connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT ticker, metric_id, period_end::text, accepted_at::text,
               value_decimal::text, unit, source_digest
        FROM qualification_fin_facts
        ORDER BY ticker, metric_id, period_end, accepted_at
        """
    ).fetchall()
    keys = (
        "ticker",
        "metric_id",
        "period_end",
        "accepted_at",
        "value_decimal",
        "unit",
        "source_digest",
    )
    return [dict(zip(keys, row, strict=True)) for row in rows]


def exercise_postgres_contract(postgres_url: str) -> dict[str, Any]:
    import psycopg
    from psycopg import errors

    with psycopg.connect(postgres_url, autocommit=True) as connection:
        version = connection.execute(
            "SELECT current_setting('server_version'), version()"
        ).fetchone()
        connection.execute(
            """
            CREATE TABLE qualification_fin_facts (
                fact_id text PRIMARY KEY,
                ticker text NOT NULL,
                metric_id text NOT NULL,
                period_end date NOT NULL,
                accepted_at timestamptz NOT NULL,
                value_decimal numeric NOT NULL,
                unit text NOT NULL,
                source_digest text NOT NULL CHECK (length(source_digest) = 64),
                UNIQUE (ticker, metric_id, period_end, accepted_at)
            )
            """
        )
        try:
            with connection.transaction():
                connection.execute(
                    """
                    INSERT INTO qualification_fin_facts VALUES
                    ('ROLLBACK', 'DELL', 'revenue', '2026-05-01',
                     '2026-06-09T20:11:41+00:00', 43842000000, 'USD', %s)
                    """,
                    ("f" * 64,),
                )
                raise ExpectedRollback()
        except ExpectedRollback:
            pass
        rollback_count = connection.execute(
            "SELECT count(*) FROM qualification_fin_facts WHERE fact_id='ROLLBACK'"
        ).fetchone()[0]
        if rollback_count != 0:
            raise AssertionError("transaction_rollback_failed")

        rows = (
            (
                "DELL-REV-Q1FY27",
                "DELL",
                "revenue",
                "2026-05-01",
                "2026-06-09T20:11:41+00:00",
                "43842000000",
                "USD",
                "a" * 64,
            ),
            (
                "MU-REV-Q3FY26",
                "MU",
                "revenue",
                "2026-05-28",
                "2026-06-25T20:15:00+00:00",
                "9630000000",
                "USD",
                "b" * 64,
            ),
            (
                "NVDA-REV-Q2FY27",
                "NVDA",
                "revenue",
                "2026-07-26",
                "2026-08-26T20:05:00+00:00",
                "46743000000",
                "USD",
                "c" * 64,
            ),
        )
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO qualification_fin_facts(
                        fact_id, ticker, metric_id, period_end, accepted_at,
                        value_decimal, unit, source_digest
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    rows,
                )
        duplicate_rejected = False
        try:
            with connection.transaction():
                connection.execute(
                    """
                    INSERT INTO qualification_fin_facts VALUES
                    ('DELL-DUPLICATE', 'DELL', 'revenue', '2026-05-01',
                     '2026-06-09T20:11:41+00:00', 1, 'USD', %s)
                    """,
                    ("d" * 64,),
                )
        except errors.UniqueViolation:
            duplicate_rejected = True
        if not duplicate_rejected:
            raise AssertionError("native_unique_constraint_did_not_reject_duplicate")

        stored_rows = qualification_rows(connection)

    lock_key = 130013
    with (
        psycopg.connect(postgres_url) as first,
        psycopg.connect(postgres_url) as second,
    ):
        first.execute("BEGIN")
        second.execute("BEGIN")
        first_lock = first.execute(
            "SELECT pg_try_advisory_xact_lock(%s)", (lock_key,)
        ).fetchone()[0]
        second_while_held = second.execute(
            "SELECT pg_try_advisory_xact_lock(%s)", (lock_key,)
        ).fetchone()[0]
        second.rollback()
        first.commit()
        second.execute("BEGIN")
        second_after_release = second.execute(
            "SELECT pg_try_advisory_xact_lock(%s)", (lock_key,)
        ).fetchone()[0]
        second.commit()
    if not first_lock or second_while_held or not second_after_release:
        raise AssertionError("postgres_advisory_lock_contract_failed")

    return {
        "server_version": version[0],
        "server_version_banner": version[1],
        "transaction_rollback": "pass",
        "native_unique_constraint": "pass",
        "advisory_lock": {
            "first_acquired": first_lock,
            "second_while_held": second_while_held,
            "second_after_release": second_after_release,
        },
        "row_count": len(stored_rows),
        "rows_sha256": sha256_json(stored_rows),
        "rows": stored_rows,
    }


def read_qualification_rows(postgres_url: str) -> dict[str, Any]:
    import psycopg

    with psycopg.connect(postgres_url, autocommit=True) as connection:
        rows = qualification_rows(connection)
    return {"row_count": len(rows), "rows_sha256": sha256_json(rows), "rows": rows}


def database_url(*, password: str, database: str, host_port: int) -> str:
    return (
        "postgresql://finsight_qualification:"
        + quote(password, safe="")
        + f"@127.0.0.1:{host_port}/{database}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-root", type=Path, required=True)
    parser.add_argument("--host-port", type=int, default=55432)
    args = parser.parse_args()

    qualification_root = validate_qualification_root(args.qualification_root)
    host_port = validate_qualification_host_port(args.host_port)
    runtime_receipt = runtime_environment_receipt(qualification_root)
    binding_start = implementation_binding()
    if not binding_start["git_status_clean"]:
        raise RuntimeError("qualification_requires_clean_repository_worktree")
    attempt_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    attempt_root = qualification_root / "artifacts" / "postgres-dagster-s2" / attempt_id
    postgres_data = attempt_root / "postgres-data"
    backup_root = attempt_root / "backups"
    dagster_home = attempt_root / "dagster-home"
    shadow_root = attempt_root / "shadow"
    for path in (postgres_data, backup_root, dagster_home, shadow_root):
        path.mkdir(parents=True, exist_ok=False)

    suffix = uuid4().hex
    container_name = f"fin013-postgres16-qualification-{suffix}"
    network_name = f"fin013-qualification-net-{suffix}"
    secret_root = attempt_root / "runtime-secrets"
    secret_path = secret_root / ".postgres-password"
    password = secrets.token_urlsafe(32)
    image = POSTGRES_IMAGE
    postgres_url = database_url(
        password=password,
        database="finsight_qualification",
        host_port=host_port,
    )
    summary: dict[str, Any] = {
        "schema_version": "fin_ia_postgres_dagster_s2_vertical_qualification_v1_1",
        "attempt_id": attempt_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "repository_head": binding_start["repository_head"],
        "repository_branch": binding_start["repository_branch"],
        "implementation_binding": {"start": binding_start},
        "runtime_environment": runtime_receipt,
        "postgres": {
            "image": image,
            "expected_version": POSTGRES_VERSION,
            "container_name": container_name,
            "network_name": network_name,
            "client_location": "windows_host_process",
            "host_binding": (
                f"{QUALIFICATION_NETWORK_HOST_BINDING_ADDRESS}:{host_port}"
            ),
            "data_directory": str(postgres_data),
            "credential_persisted_in_result": False,
        },
        "authority": {
            "product_promotion": False,
            "s2_authority_changed": False,
            "r14_changed": False,
            "source_admission": False,
            "network_calls_for_financial_sources": 0,
            "model_calls": 0,
            "orchestrator_business_logic_rewrite": False,
        },
    }
    container_created = False
    network_created = False
    qualification_error: Exception | None = None
    result_path = attempt_root / "qualification-result.json"
    try:
        summary["postgres"]["secret_directory_security"] = (
            prepare_restricted_secret_directory(secret_root)
        )
        summary["postgres"]["password_file_security"] = write_restricted_secret(
            secret_path,
            password,
        )
        run_command(
            [
                "docker",
                "network",
                "create",
                "--driver",
                QUALIFICATION_NETWORK_DRIVER,
                "--opt",
                (
                    f"{QUALIFICATION_NETWORK_HOST_BINDING_OPTION}="
                    f"{QUALIFICATION_NETWORK_HOST_BINDING_ADDRESS}"
                ),
                "--label",
                f"{DOCKER_ATTEMPT_LABEL}={attempt_id}",
                network_name,
            ]
        )
        network_created = True
        network_inspect = run_command(
            ["docker", "network", "inspect", network_name]
        )
        network_payload = json.loads(network_inspect.stdout)[0]
        summary["postgres"]["network_profile"] = validate_qualification_network(
            network_payload,
            attempt_id=attempt_id,
        )
        run_command(
            [
                "docker",
                "create",
                "--name",
                container_name,
                "--label",
                f"{DOCKER_ATTEMPT_LABEL}={attempt_id}",
                "--network",
                network_name,
                "--restart",
                "no",
                "--pull",
                "never",
                "--publish",
                (
                    f"{QUALIFICATION_NETWORK_HOST_BINDING_ADDRESS}:"
                    f"{host_port}:5432"
                ),
                "--env",
                "POSTGRES_USER=finsight_qualification",
                "--env",
                "POSTGRES_DB=finsight_qualification",
                "--env",
                "POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password",
                "--volume",
                f"{secret_path}:/run/secrets/postgres_password:ro",
                "--volume",
                f"{postgres_data}:/var/lib/postgresql/data",
                image,
            ]
        )
        container_created = True
        container_inspect = run_command(
            ["docker", "container", "inspect", container_name]
        )
        container_payload = json.loads(container_inspect.stdout)[0]
        summary["postgres"]["container_network_contract"] = (
            validate_postgres_container_network_contract(
                container_payload,
                attempt_id=attempt_id,
                network_name=network_name,
                host_port=host_port,
            )
        )
        run_command(["docker", "start", container_name])
        running_container_inspect = run_command(
            ["docker", "container", "inspect", container_name]
        )
        running_container_payload = json.loads(running_container_inspect.stdout)[0]
        summary["postgres"]["effective_port_binding"] = (
            validate_postgres_effective_port_binding(
                running_container_payload,
                host_port=host_port,
            )
        )
        wait_for_postgres(container_name)
        contract = exercise_postgres_contract(postgres_url)
        if contract["server_version"] != POSTGRES_VERSION:
            raise AssertionError(
                f"postgres_version_mismatch:{contract['server_version']}"
            )
        summary["postgres"]["contract"] = contract

        pre_restart = read_qualification_rows(postgres_url)
        run_command(["docker", "stop", container_name])
        run_command(["docker", "start", container_name])
        wait_for_postgres(container_name)
        post_restart = read_qualification_rows(postgres_url)
        restart_pass = pre_restart == post_restart
        if not restart_pass:
            raise AssertionError("postgres_restart_readback_mismatch")
        summary["postgres"]["restart_readback"] = {
            "pass": restart_pass,
            "row_count": post_restart["row_count"],
            "rows_sha256": post_restart["rows_sha256"],
        }

        policy_path = ROOT / POLICY_REF
        tracked_result = json.loads((ROOT / TRACKED_RESULT_REF).read_text(encoding="utf-8"))
        tracked_result_digest = validate_result_digest(tracked_result)
        if tracked_result_digest != EXPECTED_TRACKED_RESULT_DIGEST:
            raise AssertionError("tracked_s2_result_digest_drift")
        legacy_sqlite = shadow_root / "legacy-company-financial-facts.sqlite"
        legacy_result_path = shadow_root / "legacy-result.json"
        legacy_result = run_fact_mart_builder(
            policy_path=policy_path,
            sqlite_path=legacy_sqlite,
            result_path=legacy_result_path,
        )

        dagster_yaml = dagster_home / "dagster.yaml"
        dagster_yaml.write_text(
            "storage:\n"
            "  postgres:\n"
            "    postgres_url:\n"
            "      env: FIN_QUAL_POSTGRES_URL\n"
            "telemetry:\n"
            "  enabled: false\n",
            encoding="utf-8",
        )
        qualification_environment = {
            "FIN_QUAL_POSTGRES_URL": postgres_url,
            "FINSIGHT_REPOSITORY_ROOT": str(ROOT),
            "FINSIGHT_S2_POLICY_ROOT": str(policy_path.parent),
            "FINSIGHT_S2_OUTPUT_ROOT": str(shadow_root),
        }
        previous_environment = {
            key: os.environ.get(key) for key in qualification_environment
        }
        os.environ.update(qualification_environment)
        try:
            from dagster import DagsterInstance

            adapter_module = importlib.import_module(
                "sec_agent.adapters.dagster_s2_fact_mart"
            )
            adapter_origin = validate_module_origin(
                adapter_module,
                expected_path=(
                    ROOT / "src/sec_agent/adapters/dagster_s2_fact_mart.py"
                ),
            )
            summary["runtime_environment"]["import_origins"] = {
                "sec_agent.adapters.dagster_s2_fact_mart": adapter_origin,
            }
            s2_company_fact_mart_shadow = (
                adapter_module.s2_company_fact_mart_shadow
            )

            with DagsterInstance.from_config(str(dagster_home)) as instance:
                execution = s2_company_fact_mart_shadow.execute_in_process(
                    instance=instance,
                    run_config={
                        "ops": {
                            "materialize_existing_s2_company_fact_mart": {
                                "config": {
                                    "policy_path": str(policy_path),
                                }
                            }
                        }
                    },
                )
                if not execution.success:
                    raise RuntimeError("dagster_vertical_execution_failed")
                dagster_run_id = execution.run_id
                dagster_run_root = shadow_root / dagster_run_id
                dagster_sqlite = (
                    dagster_run_root / "company-financial-facts.sqlite"
                )
                dagster_result_path = (
                    dagster_run_root / "company-financial-facts-result.json"
                )
                dagster_result = execution.output_for_node(
                    "materialize_existing_s2_company_fact_mart"
                )
                if not dagster_result_path.is_file():
                    raise RuntimeError("dagster_run_scoped_result_missing")
                execution_event_receipt = dagster_event_receipt(
                    instance.all_logs(dagster_run_id)
                )
                validate_dagster_event_receipt(execution_event_receipt)
            with DagsterInstance.from_config(str(dagster_home)) as readback_instance:
                initial_readback = dagster_run_readback(
                    readback_instance,
                    dagster_run_id,
                )
        finally:
            for key, previous_value in previous_environment.items():
                if previous_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = previous_value

        legacy_projection = fact_mart_semantic_projection(legacy_result)
        dagster_projection = fact_mart_semantic_projection(dagster_result)
        tracked_projection = fact_mart_semantic_projection(tracked_result)
        parity = {
            "legacy_vs_dagster_semantic_exact": legacy_projection == dagster_projection,
            "legacy_vs_tracked_semantic_exact": legacy_projection == tracked_projection,
            "legacy_vs_dagster_sqlite_sha256_exact": (
                sha256_file(legacy_sqlite) == sha256_file(dagster_sqlite)
            ),
            # SQLite file bytes can change across SQLite library versions even
            # when every table row and business acceptance check is identical.
            # Keep the tracked-file comparison visible, but do not mistake it
            # for the cross-runtime semantic contract.
            "legacy_vs_tracked_sqlite_sha256_exact": (
                sha256_file(legacy_sqlite)
                == tracked_result["storage"]["sqlite_sha256"]
            ),
            "legacy_observation_digest_expected": (
                legacy_result["storage"]["observation_digest"]
                == EXPECTED_OBSERVATION_DIGEST
            ),
            "dagster_status": dagster_result.get("status"),
            "legacy_status": legacy_result.get("status"),
        }
        required_parity_checks = (
            "legacy_vs_dagster_semantic_exact",
            "legacy_vs_tracked_semantic_exact",
            "legacy_vs_dagster_sqlite_sha256_exact",
            "legacy_observation_digest_expected",
        )
        if not all(parity[key] is True for key in required_parity_checks):
            raise AssertionError("s2_fact_mart_shadow_parity_failed:" + canonical_json(parity))
        if initial_readback["run_status"] != "SUCCESS":
            raise AssertionError(
                f"dagster_postgres_run_readback_failed:{initial_readback['run_status']}"
            )
        validate_dagster_event_receipt(initial_readback)
        if initial_readback["event_count"] != execution_event_receipt["event_count"]:
            raise AssertionError("dagster_postgres_event_count_readback_mismatch")
        if initial_readback["events_sha256"] != execution_event_receipt["events_sha256"]:
            raise AssertionError("dagster_postgres_event_digest_readback_mismatch")
        summary["dagster_vertical"] = {
            "job_name": "fin013_s2_fact_mart_shadow",
            "run_id": dagster_run_id,
            "run_readback_status": initial_readback["run_status"],
            "event_count": initial_readback["event_count"],
            "events_sha256": initial_readback["events_sha256"],
            "new_instance_readback": initial_readback,
            "storage_backend": "dagster-postgres",
            "legacy_entrypoint_reused": (
                "scripts.data_retrieval.build_s2_company_financial_fact_mart"
            ),
            "real_source_bound_local_capture_replay": True,
            "observation_count": dagster_result["counts"]["observations"],
            "qrel_exact": dagster_result["qrel_evaluation"]["exact_match_count"],
            "qrel_total": dagster_result["qrel_evaluation"]["qrel_count"],
            "parity": parity,
            "legacy_projection_sha256": sha256_json(legacy_projection),
            "dagster_projection_sha256": sha256_json(dagster_projection),
            "tracked_projection_sha256": sha256_json(tracked_projection),
            "legacy_sqlite_sha256": sha256_file(legacy_sqlite),
            "dagster_sqlite_sha256": sha256_file(dagster_sqlite),
            "schedule_storage_user_write_read": (
                "not_exercised_no_schedule_or_sensor_in_this_vertical"
            ),
        }

        run_command(["docker", "stop", container_name])
        run_command(["docker", "start", container_name])
        wait_for_postgres(container_name)
        post_dagster_restart_rows = read_qualification_rows(postgres_url)
        if post_dagster_restart_rows != post_restart:
            raise AssertionError("postgres_second_restart_row_readback_mismatch")
        previous_url = os.environ.get("FIN_QUAL_POSTGRES_URL")
        os.environ["FIN_QUAL_POSTGRES_URL"] = postgres_url
        try:
            with DagsterInstance.from_config(str(dagster_home)) as restart_instance:
                restart_readback = dagster_run_readback(
                    restart_instance,
                    dagster_run_id,
                )
        finally:
            if previous_url is None:
                os.environ.pop("FIN_QUAL_POSTGRES_URL", None)
            else:
                os.environ["FIN_QUAL_POSTGRES_URL"] = previous_url
        if restart_readback != initial_readback:
            raise AssertionError("dagster_postgres_restart_readback_mismatch")
        summary["postgres"]["dagster_storage_restart_readback"] = {
            "pass": True,
            **restart_readback,
        }

        dump_inside_container = "/tmp/finsight-qualification.dump"
        run_command(
            [
                "docker",
                "exec",
                container_name,
                "pg_dump",
                "--username",
                "finsight_qualification",
                "--dbname",
                "finsight_qualification",
                "--format",
                "custom",
                "--file",
                dump_inside_container,
            ]
        )
        backup_path = backup_root / "finsight-qualification.dump"
        run_command(
            ["docker", "cp", f"{container_name}:{dump_inside_container}", str(backup_path)]
        )
        host_roundtrip_dump = "/tmp/finsight-qualification-host-roundtrip.dump"
        run_command(["docker", "exec", container_name, "rm", dump_inside_container])
        run_command(
            ["docker", "cp", str(backup_path), f"{container_name}:{host_roundtrip_dump}"]
        )
        run_command(
            [
                "docker",
                "exec",
                container_name,
                "createdb",
                "--username",
                "finsight_qualification",
                "finsight_qualification_restore",
            ]
        )
        run_command(
            [
                "docker",
                "exec",
                container_name,
                "pg_restore",
                "--username",
                "finsight_qualification",
                "--dbname",
                "finsight_qualification_restore",
                host_roundtrip_dump,
            ]
        )
        restored_url = database_url(
            password=password,
            database="finsight_qualification_restore",
            host_port=host_port,
        )
        restored_rows = read_qualification_rows(restored_url)
        restore_pass = restored_rows == post_restart
        if not restore_pass:
            raise AssertionError("postgres_backup_restore_readback_mismatch")
        restore_dagster_home = attempt_root / "dagster-home-restore"
        restore_dagster_home.mkdir()
        (restore_dagster_home / "dagster.yaml").write_text(
            "storage:\n"
            "  postgres:\n"
            "    postgres_url:\n"
            "      env: FIN_QUAL_RESTORE_POSTGRES_URL\n"
            "telemetry:\n"
            "  enabled: false\n",
            encoding="utf-8",
        )
        previous_restore_url = os.environ.get("FIN_QUAL_RESTORE_POSTGRES_URL")
        os.environ["FIN_QUAL_RESTORE_POSTGRES_URL"] = restored_url
        try:
            with DagsterInstance.from_config(str(restore_dagster_home)) as restore_instance:
                restored_dagster_readback = dagster_run_readback(
                    restore_instance,
                    dagster_run_id,
                )
        finally:
            if previous_restore_url is None:
                os.environ.pop("FIN_QUAL_RESTORE_POSTGRES_URL", None)
            else:
                os.environ["FIN_QUAL_RESTORE_POSTGRES_URL"] = previous_restore_url
        if restored_dagster_readback != initial_readback:
            raise AssertionError("dagster_postgres_backup_restore_readback_mismatch")
        summary["postgres"]["backup_restore"] = {
            "pass": restore_pass,
            "format": "pg_dump_custom",
            "backup_path": str(backup_path),
            "backup_bytes": backup_path.stat().st_size,
            "backup_sha256": sha256_file(backup_path),
            "restored_row_count": restored_rows["row_count"],
            "restored_rows_sha256": restored_rows["rows_sha256"],
            "dagster_run_event_readback_pass": True,
            "dagster_readback": restored_dagster_readback,
        }

        summary["product_delta"] = 0
        summary["langgraph_decision"] = {
            "decision": "hold_not_tested",
            "reason": (
                "This vertical is a deterministic outer data materialization job. "
                "It has no model-state checkpoint, human-in-the-loop pause, or agent graph."
            ),
        }
    except Exception as error:
        qualification_error = error
    finally:
        cleanup: dict[str, Any] = {
            "container_created_by_attempt": container_created,
            "network_created_by_attempt": network_created,
        }

        container_before = run_command(
            ["docker", "container", "inspect", container_name],
            check=False,
            timeout_seconds=30,
        )
        cleanup["container_present_before_cleanup"] = container_before.returncode == 0
        cleanup["container_owned_by_attempt"] = docker_object_owned_by_attempt(
            container_before,
            kind="container",
            attempt_id=attempt_id,
        )
        container_absent_before = docker_absence_confirmed(
            container_before,
            kind="container",
            name=container_name,
        )
        cleanup["container_remove_succeeded"] = container_absent_before
        if cleanup["container_owned_by_attempt"]:
            logs = run_command(
                ["docker", "logs", container_name],
                check=False,
                timeout_seconds=30,
            )
            try:
                (attempt_root / "postgres-container.log").write_text(
                    logs.stdout + logs.stderr,
                    encoding="utf-8",
                )
                cleanup["container_log_captured"] = True
            except Exception as log_error:
                cleanup["container_log_captured"] = False
                cleanup["container_log_error_type"] = type(log_error).__name__
            container_remove = run_command(
                ["docker", "rm", "--force", container_name],
                check=False,
                timeout_seconds=30,
            )
            cleanup["container_remove_returncode"] = container_remove.returncode
            cleanup["container_remove_succeeded"] = container_remove.returncode == 0
        container_after = run_command(
            ["docker", "container", "inspect", container_name],
            check=False,
            timeout_seconds=30,
        )
        cleanup["container_absent_after_cleanup"] = docker_absence_confirmed(
            container_after,
            kind="container",
            name=container_name,
        )

        network_before = run_command(
            ["docker", "network", "inspect", network_name],
            check=False,
            timeout_seconds=30,
        )
        cleanup["network_present_before_cleanup"] = network_before.returncode == 0
        cleanup["network_owned_by_attempt"] = docker_object_owned_by_attempt(
            network_before,
            kind="network",
            attempt_id=attempt_id,
        )
        network_absent_before = docker_absence_confirmed(
            network_before,
            kind="network",
            name=network_name,
        )
        cleanup["network_remove_succeeded"] = network_absent_before
        if cleanup["network_owned_by_attempt"]:
            network_remove = run_command(
                ["docker", "network", "rm", network_name],
                check=False,
                timeout_seconds=30,
            )
            cleanup["network_remove_returncode"] = network_remove.returncode
            cleanup["network_remove_succeeded"] = network_remove.returncode == 0
        network_after = run_command(
            ["docker", "network", "inspect", network_name],
            check=False,
            timeout_seconds=30,
        )
        cleanup["network_absent_after_cleanup"] = docker_absence_confirmed(
            network_after,
            kind="network",
            name=network_name,
        )

        secret_remove_error: Exception | None = None
        try:
            if secret_path.exists():
                secret_path.unlink()
        except Exception as error:
            secret_remove_error = error
        cleanup["secret_absent_after_cleanup"] = not secret_path.exists()
        if secret_remove_error is not None:
            cleanup["secret_remove_error_type"] = type(secret_remove_error).__name__
        secret_directory_remove_error: Exception | None = None
        try:
            if secret_root.exists():
                secret_root.rmdir()
        except Exception as error:
            secret_directory_remove_error = error
        cleanup["secret_directory_absent_after_cleanup"] = not secret_root.exists()
        if secret_directory_remove_error is not None:
            cleanup["secret_directory_remove_error_type"] = type(
                secret_directory_remove_error
            ).__name__

        cleanup["pass"] = all(
            (
                cleanup["container_absent_after_cleanup"],
                cleanup["container_remove_succeeded"],
                cleanup["network_absent_after_cleanup"],
                cleanup["network_remove_succeeded"],
                cleanup["secret_absent_after_cleanup"],
                cleanup["secret_directory_absent_after_cleanup"],
            )
        )
        summary["cleanup"] = cleanup

    try:
        secret_scan = secret_persistence_scan(attempt_root, secret=password)
        summary["secret_persistence_scan"] = secret_scan
        if not secret_scan["pass"] and qualification_error is None:
            qualification_error = RuntimeError(
                "ephemeral_postgres_password_persisted_in_qualification_artifact"
            )
    except Exception as scan_error:
        summary["secret_persistence_scan"] = {
            "pass": False,
            "error_type": type(scan_error).__name__,
        }
        if qualification_error is None:
            qualification_error = scan_error

    try:
        binding_end = implementation_binding()
        summary["implementation_binding"]["end"] = binding_end
        summary["implementation_binding"]["stable_during_execution"] = (
            summary["implementation_binding"]["start"] == binding_end
        )
        if (
            not summary["implementation_binding"]["stable_during_execution"]
            and qualification_error is None
        ):
            qualification_error = RuntimeError(
                "implementation_binding_changed_during_qualification"
            )
    except Exception as binding_error:
        summary["implementation_binding"]["end_error_type"] = type(
            binding_error
        ).__name__
        if qualification_error is None:
            qualification_error = binding_error
    if not summary["cleanup"]["pass"] and qualification_error is None:
        qualification_error = RuntimeError("qualification_resource_cleanup_failed")
    if qualification_error is None:
        summary["status"] = "bounded_engineering_pass"
    else:
        summary["status"] = "failed"
        summary["error_type"] = type(qualification_error).__name__
        summary["error"] = redact_sensitive_text(
            str(qualification_error),
            (password, quote(password, safe=""), postgres_url),
        )
    final_sensitive_values = (
        password,
        quote(password, safe=""),
        postgres_url,
    )
    prospective_scan = sensitive_text_scan(
        canonical_json(summary),
        sensitive_values=final_sensitive_values,
    )
    if not prospective_scan["pass"]:
        summary = json.loads(
            redact_sensitive_text(
                canonical_json(summary),
                final_sensitive_values,
            )
        )
        qualification_error = RuntimeError(
            "qualification_final_summary_sensitive_value_detected"
        )
        summary["status"] = "failed"
        summary["error_type"] = type(qualification_error).__name__
        summary["error"] = str(qualification_error)
    summary["final_summary_sensitive_value_scan"] = {
        **prospective_scan,
        "covers": [
            "ephemeral_password",
            "url_encoded_password",
            "complete_postgres_url",
        ],
        "unsafe_values_persisted": False,
    }
    post_redaction_scan = sensitive_text_scan(
        canonical_json(summary),
        sensitive_values=final_sensitive_values,
    )
    if not post_redaction_scan["pass"]:
        raise RuntimeError("qualification_final_summary_redaction_failed")
    summary["final_summary_sensitive_value_scan"]["post_redaction_pass"] = True
    summary.pop("result_digest", None)
    summary["result_digest"] = sha256_json(summary)
    write_json(result_path, summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if qualification_error is not None:
        raise RuntimeError(
            f"qualification_failed:{type(qualification_error).__name__}"
        ) from None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
