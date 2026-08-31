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
    validate_qualification_root,
    validate_result_digest,
)


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
