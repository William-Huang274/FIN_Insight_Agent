from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest


adapter = pytest.importorskip("sec_agent.adapters.dagster_s2_fact_mart")
dagster = pytest.importorskip("dagster")
filelock = pytest.importorskip("filelock")


def _roots(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repository_root = tmp_path / "repository"
    builder = repository_root / adapter.BUILDER_RELATIVE_PATH
    builder.parent.mkdir(parents=True)
    builder.write_text("# qualification fixture\n", encoding="utf-8")
    policy_root = repository_root / "configs" / "financial_facts"
    policy_root.mkdir(parents=True)
    policy = policy_root / "policy.json"
    policy.write_text("{}\n", encoding="utf-8")
    output_root = tmp_path / "outputs"
    output_root.mkdir()
    return repository_root, policy_root, policy, output_root


def _fake_success(command, **kwargs):
    output = Path(command[command.index("--output") + 1])
    sqlite = Path(command[command.index("--sqlite") + 1])
    sqlite.write_bytes(b"sqlite-fixture")
    unsigned = {
        "status": "qualification-fixture",
        "storage": {"sqlite_sha256": adapter.sha256_file(sqlite)},
    }
    output.write_text(
        json.dumps(
            {**unsigned, "result_digest": adapter.canonical_digest(unsigned)},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")


def test_adapter_resolves_relative_paths_against_declared_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_root, policy_root, _policy, output_root = _roots(tmp_path)
    unrelated_cwd = tmp_path / "unrelated-cwd"
    unrelated_cwd.mkdir()
    monkeypatch.chdir(unrelated_cwd)
    calls = []

    def capture(command, **kwargs):
        calls.append((command, kwargs))
        return _fake_success(command, **kwargs)

    monkeypatch.setattr(adapter.subprocess, "run", capture)
    payload = adapter.execute_existing_s2_fact_mart_entrypoint(
        policy_path=Path("policy.json"),
        sqlite_path=Path("shadow.sqlite"),
        result_path=Path("result.json"),
        repository_root=repository_root,
        policy_root=policy_root,
        output_root=output_root,
    )

    assert payload["status"] == "qualification-fixture"
    command, kwargs = calls[0]
    assert kwargs["cwd"] == repository_root.resolve()
    assert Path(command[command.index("--output") + 1]) == (
        output_root / "result.json"
    ).resolve()


def test_adapter_rejects_output_escape(tmp_path: Path) -> None:
    repository_root, policy_root, policy, output_root = _roots(tmp_path)

    with pytest.raises(dagster.Failure, match="result_path must stay inside"):
        adapter.execute_existing_s2_fact_mart_entrypoint(
            policy_path=policy,
            sqlite_path=output_root / "shadow.sqlite",
            result_path=output_root.parent / "escaped.json",
            repository_root=repository_root,
            policy_root=policy_root,
            output_root=output_root,
        )


def test_adapter_fails_closed_when_same_output_lock_is_held(tmp_path: Path) -> None:
    repository_root, policy_root, policy, output_root = _roots(tmp_path)
    sqlite = (output_root / "shadow.sqlite").resolve()
    result = (output_root / "result.json").resolve()

    with filelock.FileLock(output_root / ".finsight-s2-shadow.lock"):
        with pytest.raises(dagster.Failure, match="owns the same output target"):
            adapter.execute_existing_s2_fact_mart_entrypoint(
                policy_path=policy,
                sqlite_path=sqlite,
                result_path=result,
                repository_root=repository_root,
                policy_root=policy_root,
                output_root=output_root,
            )


def test_run_scoped_outputs_are_unique_and_replay_safe(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs"
    output_root.mkdir()

    first_sqlite, first_result, approved = adapter.create_run_scoped_output_paths(
        run_id="attempt-a",
        output_root=output_root,
    )
    second_sqlite, second_result, _ = adapter.create_run_scoped_output_paths(
        run_id="attempt-b",
        output_root=output_root,
    )

    assert approved == output_root.resolve()
    assert first_sqlite.parent != second_sqlite.parent
    assert first_result.parent == first_sqlite.parent
    assert second_result.parent == second_sqlite.parent
    with pytest.raises(dagster.Failure, match="already exists"):
        adapter.create_run_scoped_output_paths(
            run_id="attempt-a",
            output_root=output_root,
        )


def test_run_scoped_outputs_reject_unsafe_run_id(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs"
    output_root.mkdir()

    with pytest.raises(dagster.Failure, match="not safe"):
        adapter.create_run_scoped_output_paths(
            run_id="../escape",
            output_root=output_root,
        )


def test_adapter_timeout_is_a_typed_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_root, policy_root, policy, output_root = _roots(tmp_path)

    def time_out(command, **kwargs):
        raise subprocess.TimeoutExpired(command, timeout=kwargs["timeout"])

    monkeypatch.setattr(adapter.subprocess, "run", time_out)
    with pytest.raises(dagster.Failure, match="timed out"):
        adapter.execute_existing_s2_fact_mart_entrypoint(
            policy_path=policy,
            sqlite_path=output_root / "shadow.sqlite",
            result_path=output_root / "result.json",
            repository_root=repository_root,
            policy_root=policy_root,
            output_root=output_root,
            timeout_seconds=1,
        )


def test_adapter_rejects_timeout_above_deployment_ceiling(tmp_path: Path) -> None:
    repository_root, policy_root, policy, output_root = _roots(tmp_path)

    with pytest.raises(dagster.Failure, match="must be between 1 and 900"):
        adapter.execute_existing_s2_fact_mart_entrypoint(
            policy_path=policy,
            sqlite_path=output_root / "shadow.sqlite",
            result_path=output_root / "result.json",
            repository_root=repository_root,
            policy_root=policy_root,
            output_root=output_root,
            timeout_seconds=adapter.MAX_TIMEOUT_SECONDS + 1,
        )


def test_adapter_rejects_tampered_result_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_root, policy_root, policy, output_root = _roots(tmp_path)

    def write_tampered(command, **kwargs):
        output = Path(command[command.index("--output") + 1])
        sqlite = Path(command[command.index("--sqlite") + 1])
        sqlite.write_bytes(b"sqlite-fixture")
        output.write_text(
            json.dumps({"status": "tampered", "result_digest": "0" * 64}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(adapter.subprocess, "run", write_tampered)
    with pytest.raises(dagster.Failure, match="result_digest is invalid"):
        adapter.execute_existing_s2_fact_mart_entrypoint(
            policy_path=policy,
            sqlite_path=output_root / "shadow.sqlite",
            result_path=output_root / "result.json",
            repository_root=repository_root,
            policy_root=policy_root,
            output_root=output_root,
        )


def test_adapter_rejects_missing_sqlite_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_root, policy_root, policy, output_root = _roots(tmp_path)

    def omit_sqlite(command, **kwargs):
        output = Path(command[command.index("--output") + 1])
        unsigned = {"storage": {"sqlite_sha256": "0" * 64}}
        output.write_text(
            json.dumps({**unsigned, "result_digest": adapter.canonical_digest(unsigned)}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(adapter.subprocess, "run", omit_sqlite)
    with pytest.raises(dagster.Failure, match="did not create its SQLite object"):
        adapter.execute_existing_s2_fact_mart_entrypoint(
            policy_path=policy,
            sqlite_path=output_root / "shadow.sqlite",
            result_path=output_root / "result.json",
            repository_root=repository_root,
            policy_root=policy_root,
            output_root=output_root,
        )


def test_adapter_rejects_sqlite_digest_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_root, policy_root, policy, output_root = _roots(tmp_path)

    def write_mismatch(command, **kwargs):
        output = Path(command[command.index("--output") + 1])
        sqlite = Path(command[command.index("--sqlite") + 1])
        sqlite.write_bytes(b"sqlite-fixture")
        unsigned = {"storage": {"sqlite_sha256": "0" * 64}}
        output.write_text(
            json.dumps({**unsigned, "result_digest": adapter.canonical_digest(unsigned)}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(adapter.subprocess, "run", write_mismatch)
    with pytest.raises(dagster.Failure, match="SQLite digest is invalid"):
        adapter.execute_existing_s2_fact_mart_entrypoint(
            policy_path=policy,
            sqlite_path=output_root / "shadow.sqlite",
            result_path=output_root / "result.json",
            repository_root=repository_root,
            policy_root=policy_root,
            output_root=output_root,
        )


def test_adapter_does_not_pass_parent_credentials_to_builder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_root, policy_root, policy, output_root = _roots(tmp_path)
    monkeypatch.setenv("DAGSTER_POSTGRES_URL", "postgresql://user:secret@example/db")
    monkeypatch.setenv("FMP_API_KEY", "secret-fmp-key")
    child_environments = []

    def capture_environment(command, **kwargs):
        child_environments.append(kwargs["env"])
        return _fake_success(command, **kwargs)

    monkeypatch.setattr(adapter.subprocess, "run", capture_environment)
    adapter.execute_existing_s2_fact_mart_entrypoint(
        policy_path=policy,
        sqlite_path=output_root / "shadow.sqlite",
        result_path=output_root / "result.json",
        repository_root=repository_root,
        policy_root=policy_root,
        output_root=output_root,
    )

    child_environment = child_environments[0]
    assert "DAGSTER_POSTGRES_URL" not in child_environment
    assert "FMP_API_KEY" not in child_environment
    assert "PATH" in child_environment
