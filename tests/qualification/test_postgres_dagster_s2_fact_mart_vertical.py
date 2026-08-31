from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from scripts.qualification.run_postgres_dagster_s2_fact_mart_vertical import (
    docker_absence_confirmed,
    docker_object_owned_by_attempt,
    fact_mart_semantic_projection,
    locked_environment_check,
    redact_sensitive_text,
    secret_persistence_scan,
    sensitive_text_scan,
    sha256_json,
    validate_interpreter_location,
    validate_module_origin,
    validate_postgres_container_network_contract,
    validate_postgres_effective_port_binding,
    validate_qualification_host_port,
    validate_qualification_network,
    validate_qualification_root,
    validate_result_digest,
)


def test_qualification_host_port_rejects_privileged_or_out_of_range_values() -> None:
    assert validate_qualification_host_port(55432) == 55432
    for invalid in (True, 0, 1023, 65536):
        with pytest.raises(
            ValueError,
            match="qualification_host_port_must_be_between_1024_and_65535",
        ):
            validate_qualification_host_port(invalid)


def test_qualification_network_requires_dedicated_loopback_bridge() -> None:
    receipt = validate_qualification_network(
        {
            "Driver": "bridge",
            "Internal": False,
            "Options": {
                "com.docker.network.bridge.host_binding_ipv4": "127.0.0.1",
            },
            "Labels": {"com.finsight.qualification.attempt": "attempt-a"},
        },
        attempt_id="attempt-a",
    )

    assert receipt["driver"] == "bridge"
    assert receipt["internal"] is False
    assert receipt["default_host_binding_ipv4"] == "127.0.0.1"
    assert receipt["attempt_label_match"] is True
    assert receipt["postgres_container_egress_blocked_by_network"] is False
    assert receipt["host_runner_egress_blocked_by_network"] is False
    assert receipt["pass"] is True


@pytest.mark.parametrize(
    "payload",
    [
        {
            "Driver": "bridge",
            "Internal": True,
            "Options": {
                "com.docker.network.bridge.host_binding_ipv4": "127.0.0.1",
            },
            "Labels": {"com.finsight.qualification.attempt": "attempt-a"},
        },
        {
            "Driver": "overlay",
            "Internal": False,
            "Options": {
                "com.docker.network.bridge.host_binding_ipv4": "127.0.0.1",
            },
            "Labels": {"com.finsight.qualification.attempt": "attempt-a"},
        },
        {
            "Driver": "bridge",
            "Internal": False,
            "Options": {},
            "Labels": {"com.finsight.qualification.attempt": "attempt-a"},
        },
        {
            "Driver": "bridge",
            "Internal": False,
            "Options": {
                "com.docker.network.bridge.host_binding_ipv4": "0.0.0.0",
            },
            "Labels": {"com.finsight.qualification.attempt": "attempt-a"},
        },
        {
            "Driver": "bridge",
            "Internal": False,
            "Options": {
                "com.docker.network.bridge.host_binding_ipv4": "127.0.0.1",
            },
            "Labels": {"com.finsight.qualification.attempt": "attempt-b"},
        },
    ],
)
def test_qualification_network_rejects_unreachable_or_unowned_profiles(
    payload: dict[str, object],
) -> None:
    with pytest.raises(
        AssertionError,
        match="qualification_network_loopback_bridge_contract_failed",
    ):
        validate_qualification_network(payload, attempt_id="attempt-a")


def _postgres_container_inspect_payload() -> dict[str, object]:
    return {
        "Config": {
            "Labels": {"com.finsight.qualification.attempt": "attempt-a"},
            "Env": [
                "POSTGRES_USER=finsight_qualification",
                "POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password",
            ],
        },
        "HostConfig": {
            "NetworkMode": "attempt-network",
            "PortBindings": {
                "5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "55432"}],
            },
        },
        "NetworkSettings": {"Networks": {"attempt-network": {}}},
        "Mounts": [
            {"Destination": "/run/secrets/postgres_password", "RW": False},
            {"Destination": "/var/lib/postgresql/data", "RW": True},
        ],
    }


def test_postgres_container_network_contract_reads_back_exact_loopback_scope() -> None:
    receipt = validate_postgres_container_network_contract(
        _postgres_container_inspect_payload(),
        attempt_id="attempt-a",
        network_name="attempt-network",
        host_port=55432,
    )

    assert receipt["postgres_port_bindings"] == [
        {"HostIp": "127.0.0.1", "HostPort": "55432"}
    ]
    assert receipt["attached_networks"] == ["attempt-network"]
    assert receipt["provider_or_proxy_environment_present"] is False
    assert receipt["private_captures_mounted"] is False
    assert receipt["container_egress_possible"] is True
    assert receipt["pass"] is True


@pytest.mark.parametrize(
    ("mutation_path", "replacement"),
    [
        (("HostConfig", "PortBindings", "5432/tcp", 0, "HostIp"), "0.0.0.0"),
        (("HostConfig", "PortBindings", "5432/tcp", 0, "HostPort"), "55433"),
        (("HostConfig", "NetworkMode"), "other-network"),
        (("Config", "Labels", "com.finsight.qualification.attempt"), "attempt-b"),
        (("Config", "Env", 0), "EIA_API_KEY=forbidden"),
        (("Config", "Env", 0), "HTTPS_PROXY=http://local-proxy.invalid"),
        (("Config", "Env", 0), "AWS_SECRET_ACCESS_KEY=forbidden"),
        (("Config", "Env", 0), "POSTGRES_PASSWORD=forbidden"),
        (("Mounts", 0, "Destination"), "/app/data/raw_private"),
    ],
)
def test_postgres_container_network_contract_rejects_scope_drift(
    mutation_path: tuple[object, ...],
    replacement: object,
) -> None:
    payload = _postgres_container_inspect_payload()
    target: object = payload
    for key in mutation_path[:-1]:
        target = target[key]  # type: ignore[index]
    target[mutation_path[-1]] = replacement  # type: ignore[index]

    with pytest.raises(
        AssertionError,
        match="postgres_container_network_contract_failed",
    ):
        validate_postgres_container_network_contract(
            payload,
            attempt_id="attempt-a",
            network_name="attempt-network",
            host_port=55432,
        )


def test_postgres_effective_port_binding_requires_one_loopback_mapping() -> None:
    receipt = validate_postgres_effective_port_binding(
        {
            "NetworkSettings": {
                "Ports": {
                    "5432/tcp": [
                        {"HostIp": "127.0.0.1", "HostPort": "55432"},
                    ],
                },
            },
        },
        host_port=55432,
    )

    assert receipt["effective_postgres_port_bindings"] == [
        {"HostIp": "127.0.0.1", "HostPort": "55432"}
    ]
    assert receipt["pass"] is True


@pytest.mark.parametrize(
    "ports",
    [
        {"5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "55432"}]},
        {"5432/tcp": [{"HostIp": "::", "HostPort": "55432"}]},
        {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "55433"}]},
        {
            "5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "55432"}],
            "80/tcp": [{"HostIp": "127.0.0.1", "HostPort": "55433"}],
        },
    ],
)
def test_postgres_effective_port_binding_rejects_runtime_exposure_drift(
    ports: dict[str, object],
) -> None:
    with pytest.raises(
        AssertionError,
        match="postgres_effective_port_binding_contract_failed",
    ):
        validate_postgres_effective_port_binding(
            {"NetworkSettings": {"Ports": ports}},
            host_port=55432,
        )


def test_container_to_container_ci_keeps_internal_network() -> None:
    workflow = (
        Path(__file__).resolve().parents[2] / ".github/workflows/docker-smoke.yml"
    ).read_text(encoding="utf-8")
    step = workflow.split(
        "      - name: Boot the PostgreSQL-backed Dagster UI on an internal network",
        maxsplit=1,
    )[1].split("      - name: Start container", maxsplit=1)[0]
    postgres_run = step.split("--name finsight-postgres-ci", maxsplit=1)[1].split(
        "postgres@sha256:",
        maxsplit=1,
    )[0]
    control_plane_run = step.split(
        "--name finsight-control-plane-ci",
        maxsplit=1,
    )[1].split("finsight-control-plane:ci", maxsplit=1)[0]

    assert step.count("docker network create --internal finsight-control-plane-ci") == 1
    assert "--network finsight-control-plane-ci" in postgres_run
    assert "--publish" not in postgres_run
    assert "\n            -p " not in postgres_run
    assert "--network finsight-control-plane-ci" in control_plane_run


def test_semantic_projection_ignores_path_specific_receipt_fields() -> None:
    common = {
        "status": "s2_company_financial_fact_mart_engineering_pass",
        "counts": {"observations": 1319},
        "source_summary": {"source_count": 3},
        "qrel_evaluation": {"exact_match_count": 24, "qrel_count": 24},
        "mutation_evaluation": {"all_pass": True},
        "acceptance": {"all_qrels_exact": True},
        "policy_digest": "a" * 64,
        "known_boundary": "bounded",
    }
    first = {
        **common,
        "storage": {
            "sqlite_ref": "legacy.sqlite",
            "sqlite_sha256": "b" * 64,
            "observation_digest": "c" * 64,
        },
        "result_digest": "d" * 64,
    }
    second = {
        **common,
        "storage": {
            "sqlite_ref": "dagster.sqlite",
            "sqlite_sha256": "f" * 64,
            "observation_digest": "c" * 64,
        },
        "result_digest": "e" * 64,
    }

    assert fact_mart_semantic_projection(first) == fact_mart_semantic_projection(second)


def test_canonical_json_digest_is_order_independent() -> None:
    assert sha256_json({"a": 1, "b": 2}) == sha256_json({"b": 2, "a": 1})


def test_qualification_root_requires_path_containment() -> None:
    allowed = Path("Z:/FIN_Insight_Agent_qualification")

    assert validate_qualification_root(
        allowed / "20260831_dependency_vertical_v1",
        allowed_root=allowed,
    ) == (allowed / "20260831_dependency_vertical_v1").resolve()

    with pytest.raises(
        RuntimeError,
        match="qualification_root_must_be_under_Z_fin_insight_qualification",
    ):
        validate_qualification_root(
            Path("Z:/FIN_Insight_Agent_qualification_evil"),
            allowed_root=allowed,
        )


def test_result_digest_tamper_is_rejected() -> None:
    unsigned = {"status": "bounded", "counts": {"observations": 1}}
    valid = {**unsigned, "result_digest": sha256_json(unsigned)}

    assert validate_result_digest(valid) == valid["result_digest"]
    with pytest.raises(AssertionError, match="tracked_s2_result_self_digest_invalid"):
        validate_result_digest({**valid, "counts": {"observations": 2}})


def test_secret_scan_and_error_redaction_do_not_persist_plaintext(tmp_path: Path) -> None:
    secret = "ephemeral-password-value"
    (tmp_path / "safe.txt").write_text("no credential here", encoding="utf-8")

    assert secret_persistence_scan(tmp_path, secret=secret)["pass"]
    assert redact_sensitive_text(
        f"connection failed for password={secret}",
        (secret,),
    ) == "connection failed for password=[REDACTED]"

    (tmp_path / "unsafe.bin").write_bytes(b"prefix" + secret.encode() + b"suffix")
    receipt = secret_persistence_scan(tmp_path, secret=secret)
    assert not receipt["pass"]
    assert receipt["matching_files"] == ["unsafe.bin"]


def test_serialized_summary_secret_scan_reports_only_counts() -> None:
    secret = "ephemeral-password-value"
    database_url = f"postgresql://user:{secret}@127.0.0.1:5432/database"
    unsafe = sensitive_text_scan(
        f'{{"database_url":"{database_url}"}}',
        sensitive_values=(secret, secret, database_url),
    )

    assert unsafe == {
        "checked_distinct_value_count": 2,
        "matching_value_count": 2,
        "pass": False,
    }
    assert secret not in repr(unsafe)
    redacted = redact_sensitive_text(database_url, (secret, database_url))
    assert sensitive_text_scan(
        redacted,
        sensitive_values=(secret, database_url),
    )["pass"]


def test_secret_scan_handles_single_byte_boundary_and_rejects_empty_secret(
    tmp_path: Path,
) -> None:
    (tmp_path / "single-byte.bin").write_bytes(b"safe")

    assert not secret_persistence_scan(tmp_path, secret="a")["pass"]
    with pytest.raises(ValueError, match="requires_nonempty_secret"):
        secret_persistence_scan(tmp_path, secret="")


def test_qualification_interpreter_must_be_inside_attempt_lab(tmp_path: Path) -> None:
    lab = tmp_path / "lab"
    interpreter = lab / "env" / "Scripts" / "python.exe"

    assert validate_interpreter_location(
        executable=interpreter,
        qualification_root=lab,
    ) == interpreter.resolve()
    with pytest.raises(
        RuntimeError,
        match="qualification_interpreter_must_be_under_qualification_root",
    ):
        validate_interpreter_location(
            executable=tmp_path.parent / "outside" / "python.exe",
            qualification_root=lab,
        )


def test_locked_environment_check_binds_exact_uv_profile(tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        if command == ["uv", "--version"]:
            return subprocess.CompletedProcess(command, 0, "uv 0.10.7 (test)\n", "")
        return subprocess.CompletedProcess(command, 0, "Would make no changes\n", "")

    prefix = tmp_path / "qualification-env"
    receipt = locked_environment_check(
        project_root=tmp_path,
        environment_prefix=prefix,
        command_runner=fake_runner,
    )

    assert receipt["pass"] is True
    assert receipt["uv_version"] == "0.10.7"
    assert receipt["profile"] == (
        "core+control-plane+qualification_without_dev_or_first_party"
    )
    assert calls[1][0] == [
        "uv",
        "--project",
        str(tmp_path),
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
    environment = calls[1][1]["environment"]
    assert isinstance(environment, dict)
    assert environment["UV_PROJECT_ENVIRONMENT"] == str(prefix.resolve())


def test_locked_environment_check_rejects_uv_version_drift(tmp_path: Path) -> None:
    def fake_runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, "uv 0.10.8 (drift)\n", "")

    with pytest.raises(RuntimeError, match="qualification_uv_version_mismatch"):
        locked_environment_check(
            project_root=tmp_path,
            environment_prefix=tmp_path / "env",
            command_runner=fake_runner,
        )


def test_runtime_module_origin_must_match_bound_repository_file(tmp_path: Path) -> None:
    expected = tmp_path / "repo" / "adapter.py"
    expected.parent.mkdir()
    expected.write_text("# expected\n", encoding="utf-8")

    assert validate_module_origin(
        SimpleNamespace(__file__=str(expected)),
        expected_path=expected,
    ) == str(expected.resolve())
    with pytest.raises(RuntimeError, match="module_origin_mismatch"):
        validate_module_origin(
            SimpleNamespace(__file__=str(tmp_path / "other" / "adapter.py")),
            expected_path=expected,
        )


def test_docker_absence_requires_an_explicit_no_such_object_response() -> None:
    missing = subprocess.CompletedProcess(
        [],
        1,
        stdout="[]\n",
        stderr="Error response from daemon: No such container: exact-name\n",
    )
    unavailable = subprocess.CompletedProcess(
        [],
        1,
        stdout="",
        stderr="Cannot connect to the Docker daemon",
    )

    assert docker_absence_confirmed(
        missing,
        kind="container",
        name="exact-name",
    )
    assert not docker_absence_confirmed(
        unavailable,
        kind="container",
        name="exact-name",
    )


def test_docker_cleanup_ownership_requires_exact_attempt_label() -> None:
    inspected = subprocess.CompletedProcess(
        [],
        0,
        stdout=(
            '[{"Config":{"Labels":'
            '{"com.finsight.qualification.attempt":"attempt-a"}}}]'
        ),
        stderr="",
    )

    assert docker_object_owned_by_attempt(
        inspected,
        kind="container",
        attempt_id="attempt-a",
    )
    assert not docker_object_owned_by_attempt(
        inspected,
        kind="container",
        attempt_id="attempt-b",
    )


def test_docker_cleanup_ownership_rejects_null_labels() -> None:
    inspected = subprocess.CompletedProcess(
        [],
        0,
        stdout='[{"Config":{"Labels":null}}]',
        stderr="",
    )

    assert not docker_object_owned_by_attempt(
        inspected,
        kind="container",
        attempt_id="attempt-a",
    )
