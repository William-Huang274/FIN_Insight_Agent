from __future__ import annotations

from pathlib import Path

import pytest

from sec_agent.agent_runtime.runtime_foundation import (
    DellRuntimeFoundation,
    RuntimeFoundationError,
)


def test_runtime_is_disabled_by_default_and_exposes_no_secret(tmp_path: Path) -> None:
    foundation = DellRuntimeFoundation.from_environment(
        {}, default_state_root=tmp_path
    )

    assert foundation.profile == "disabled"
    assert foundation.postgres_url is None
    assert foundation.public_projection() == {
        "schema_version": "fin_ia_dell_runtime_foundation_v1",
        "profile": "disabled",
        "checkpoint_backend": "none",
        "durable_cross_process_resume": False,
        "product_pilot_eligible": False,
        "outer_lifecycle_owner": "dagster",
        "inner_agent_state_owner": "langgraph",
        "financial_fact_authority": "existing_s2_read_only_port",
        "custom_scheduler_or_retry_engine": False,
        "dsn_exposed": False,
    }


def test_postgres_pilot_reads_secret_file_without_projecting_it(
    tmp_path: Path,
) -> None:
    secret = tmp_path / "postgres-url"
    secret.write_text(
        "postgresql://runtime:do-not-project@db.example/fin\n", encoding="utf-8"
    )

    foundation = DellRuntimeFoundation.from_environment(
        {
            "FINSIGHT_DELL_RUNTIME_PROFILE": "postgres_pilot",
            "FINSIGHT_AGENT_RUNTIME_POSTGRES_URL_FILE": str(secret),
        },
        default_state_root=tmp_path,
    )

    assert foundation.postgres_url == (
        "postgresql://runtime:do-not-project@db.example/fin"
    )
    projection = foundation.public_projection()
    assert projection["checkpoint_backend"] == "langgraph_postgres_saver"
    assert projection["checkpoint_backend_status"] == "configured_unverified"
    assert projection["durable_cross_process_resume"] is False
    assert projection["product_pilot_eligible"] is False
    assert projection["outer_lifecycle_owner_status"] == "planned"
    assert "do-not-project" not in repr(projection)


def test_sqlite_is_explicitly_qualification_only(tmp_path: Path) -> None:
    foundation = DellRuntimeFoundation.from_environment(
        {"FINSIGHT_DELL_RUNTIME_PROFILE": "sqlite_qualification"},
        default_state_root=tmp_path,
    )

    assert foundation.sqlite_path == (
        tmp_path / "agent-runtime" / "dell-qualification.sqlite3"
    ).resolve()
    assert foundation.public_projection()["product_pilot_eligible"] is False


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        (
            {"FINSIGHT_DELL_RUNTIME_PROFILE": "postgres_pilot"},
            "postgres_pilot_url_required",
        ),
        (
            {
                "FINSIGHT_DELL_RUNTIME_PROFILE": "postgres_pilot",
                "FINSIGHT_AGENT_RUNTIME_POSTGRES_URL": "sqlite:///wrong",
            },
            "postgres_pilot_url_scheme_invalid",
        ),
        (
            {
                "FINSIGHT_DELL_RUNTIME_PROFILE": "disabled",
                "FINSIGHT_AGENT_RUNTIME_SQLITE_PATH": "state.sqlite3",
            },
            "disabled_runtime_has_state_backend",
        ),
        (
            {
                "FINSIGHT_DELL_RUNTIME_PROFILE": "postgres_pilot",
                "FINSIGHT_AGENT_RUNTIME_POSTGRES_URL": "postgresql://one/db",
                "FINSIGHT_AGENT_RUNTIME_POSTGRES_URL_FILE": "secret-file",
            },
            "postgres_url_sources_conflict",
        ),
        (
            {
                "FINSIGHT_DELL_RUNTIME_PROFILE": "postgres_pilot",
                "FINSIGHT_AGENT_RUNTIME_POSTGRES_URL": "postgresql:///fin",
            },
            "postgres_pilot_url_host_required",
        ),
        (
            {
                "FINSIGHT_DELL_RUNTIME_PROFILE": "postgres_pilot",
                "FINSIGHT_AGENT_RUNTIME_POSTGRES_URL": (
                    "postgresql://db.example"
                ),
            },
            "postgres_pilot_url_database_required",
        ),
        (
            {
                "FINSIGHT_DELL_RUNTIME_PROFILE": "postgres_pilot",
                "FINSIGHT_AGENT_RUNTIME_POSTGRES_URL": (
                    "postgresql://db.example:invalid/fin"
                ),
            },
            "postgres_pilot_url_port_invalid",
        ),
    ],
)
def test_invalid_or_ambiguous_runtime_state_is_rejected(
    tmp_path: Path,
    environment: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(RuntimeFoundationError, match=message):
        DellRuntimeFoundation.from_environment(
            environment, default_state_root=tmp_path
        )
