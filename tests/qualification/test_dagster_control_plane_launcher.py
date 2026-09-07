from __future__ import annotations

from pathlib import Path

import pytest

from sec_agent.adapters import dagster_control_plane_launcher as launcher


def test_launcher_loads_postgres_url_only_from_secret_file(tmp_path: Path) -> None:
    secret = tmp_path / "dagster-postgres-url"
    secret.write_text(
        "postgresql://qualification:ephemeral@postgres:5432/qualification\n",
        encoding="utf-8",
    )
    environment = {
        launcher.POSTGRES_URL_FILE_ENV: str(secret),
        "PATH": "qualification-path",
    }

    child = launcher.build_dagster_environment(environment)

    assert child[launcher.POSTGRES_URL_ENV].endswith("/qualification")
    assert launcher.POSTGRES_URL_FILE_ENV not in child
    assert child["PATH"] == "qualification-path"
    assert launcher.POSTGRES_URL_ENV not in environment


@pytest.mark.parametrize(
    "value,error",
    [
        ("", "is_invalid"),
        ("https://example.test/database", "is_not_a_postgres_url"),
        ("postgresql://postgres:5432", "has_no_database"),
        ("postgresql:///database", "is_not_a_postgres_url"),
    ],
)
def test_launcher_rejects_invalid_secret_without_echoing_it(
    tmp_path: Path,
    value: str,
    error: str,
) -> None:
    secret = tmp_path / "dagster-postgres-url"
    secret.write_text(value, encoding="utf-8")

    with pytest.raises(RuntimeError, match=error) as captured:
        launcher.load_postgres_url_from_secret_file(
            {launcher.POSTGRES_URL_FILE_ENV: str(secret)}
        )

    if value:
        assert value not in str(captured.value)


def test_launcher_requires_existing_bounded_secret_file(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="is_required"):
        launcher.load_postgres_url_from_secret_file({})
    with pytest.raises(RuntimeError, match="is_missing"):
        launcher.load_postgres_url_from_secret_file(
            {launcher.POSTGRES_URL_FILE_ENV: str(tmp_path / "missing")}
        )


def test_launcher_executes_only_dagster_with_scrubbed_file_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = tmp_path / "dagster-postgres-url"
    url = "postgresql://qualification:ephemeral@postgres:5432/qualification"
    secret.write_text(url, encoding="utf-8")
    called = {}

    def fake_execvpe(executable, arguments, environment):
        called.update(
            executable=executable,
            arguments=arguments,
            environment=environment,
        )
        raise RuntimeError("exec-replaced")

    monkeypatch.setattr(launcher.os, "execvpe", fake_execvpe)
    with pytest.raises(RuntimeError, match="exec-replaced"):
        launcher.exec_dagster(
            ["job", "list"],
            {
                launcher.POSTGRES_URL_FILE_ENV: str(secret),
                "PATH": "qualification-path",
            },
        )

    assert called["executable"] == "dagster"
    assert called["arguments"] == ["dagster", "job", "list"]
    assert called["environment"][launcher.POSTGRES_URL_ENV] == url
    assert launcher.POSTGRES_URL_FILE_ENV not in called["environment"]
