"""Deployment boundary for the DELL reference-vertical runtime.

The current DELL graph can be exercised with SQLite during local qualification,
but a product pilot must persist LangGraph checkpoints in PostgreSQL.  This
module keeps that choice outside graph/domain code and deliberately exposes no
queue, scheduler, retry engine or application run registry.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urlsplit


RuntimeProfile = Literal["disabled", "sqlite_qualification", "postgres_pilot"]

PROFILE_ENV = "FINSIGHT_DELL_RUNTIME_PROFILE"
POSTGRES_URL_ENV = "FINSIGHT_AGENT_RUNTIME_POSTGRES_URL"
POSTGRES_URL_FILE_ENV = "FINSIGHT_AGENT_RUNTIME_POSTGRES_URL_FILE"
SQLITE_PATH_ENV = "FINSIGHT_AGENT_RUNTIME_SQLITE_PATH"


class RuntimeFoundationError(ValueError):
    """Raised when runtime state ownership is ambiguous or unsafe."""


@dataclass(frozen=True)
class DellRuntimeFoundation:
    """Resolved state-backend contract with a secret-free public projection."""

    profile: RuntimeProfile
    postgres_url: str | None = None
    sqlite_path: Path | None = None

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str],
        *,
        default_state_root: str | Path,
    ) -> "DellRuntimeFoundation":
        raw_profile = environment.get(PROFILE_ENV, "disabled").strip().lower()
        if raw_profile not in {
            "disabled",
            "sqlite_qualification",
            "postgres_pilot",
        }:
            raise RuntimeFoundationError("dell_runtime_profile_invalid")
        profile = raw_profile  # narrowed by the membership check above

        direct_url = environment.get(POSTGRES_URL_ENV, "").strip()
        url_file_value = environment.get(POSTGRES_URL_FILE_ENV, "").strip()
        if direct_url and url_file_value:
            raise RuntimeFoundationError("postgres_url_sources_conflict")

        if profile == "disabled":
            if direct_url or url_file_value or environment.get(SQLITE_PATH_ENV):
                raise RuntimeFoundationError("disabled_runtime_has_state_backend")
            return cls(profile="disabled")

        if profile == "sqlite_qualification":
            if direct_url or url_file_value:
                raise RuntimeFoundationError(
                    "sqlite_qualification_has_postgres_configuration"
                )
            configured = environment.get(SQLITE_PATH_ENV, "").strip()
            path = (
                Path(configured)
                if configured
                else Path(default_state_root)
                / "agent-runtime"
                / "dell-qualification.sqlite3"
            )
            return cls(profile="sqlite_qualification", sqlite_path=path.resolve())

        postgres_url = direct_url or _read_secret_file(url_file_value)
        if not postgres_url:
            raise RuntimeFoundationError("postgres_pilot_url_required")
        try:
            parsed_url = urlsplit(postgres_url)
            scheme = parsed_url.scheme.lower()
            hostname = parsed_url.hostname
        except ValueError as exc:
            raise RuntimeFoundationError("postgres_pilot_url_invalid") from exc
        try:
            parsed_url.port
        except ValueError as exc:
            raise RuntimeFoundationError("postgres_pilot_url_port_invalid") from exc
        if scheme not in {"postgres", "postgresql"}:
            raise RuntimeFoundationError("postgres_pilot_url_scheme_invalid")
        if not hostname or not hostname.strip():
            raise RuntimeFoundationError("postgres_pilot_url_host_required")
        database_name = unquote(parsed_url.path.removeprefix("/"))
        if not database_name or database_name.isspace() or "/" in database_name:
            raise RuntimeFoundationError("postgres_pilot_url_database_required")
        return cls(profile="postgres_pilot", postgres_url=postgres_url)

    def public_projection(self) -> dict[str, object]:
        """Return deploy/readiness metadata without ever projecting a DSN."""

        if self.profile == "postgres_pilot":
            backend = "langgraph_postgres_saver"
            durable = False
            product_pilot_eligible = False
        elif self.profile == "sqlite_qualification":
            backend = "langgraph_sqlite_saver"
            durable = False
            product_pilot_eligible = False
        else:
            backend = "none"
            durable = False
            product_pilot_eligible = False
        projection: dict[str, object] = {
            "schema_version": "fin_ia_dell_runtime_foundation_v1",
            "profile": self.profile,
            "checkpoint_backend": backend,
            "durable_cross_process_resume": durable,
            "product_pilot_eligible": product_pilot_eligible,
            "outer_lifecycle_owner": "dagster",
            "inner_agent_state_owner": "langgraph",
            "financial_fact_authority": "existing_s2_read_only_port",
            "custom_scheduler_or_retry_engine": False,
            "dsn_exposed": False,
        }
        if self.profile == "postgres_pilot":
            projection["checkpoint_backend_status"] = "configured_unverified"
            projection["outer_lifecycle_owner_status"] = "planned"
        return projection


def _read_secret_file(value: str) -> str:
    if not value:
        return ""
    path = Path(value).resolve()
    if not path.is_file():
        raise RuntimeFoundationError("postgres_url_file_unavailable")
    try:
        secret = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeFoundationError("postgres_url_file_unreadable") from exc
    if not secret:
        raise RuntimeFoundationError("postgres_url_file_empty")
    return secret


@contextmanager
def open_runtime_checkpointer(
    foundation: DellRuntimeFoundation,
    *,
    initialize_postgres_schema: bool = False,
) -> Iterator[Any]:
    """Open the selected official LangGraph checkpointer lazily.

    ``setup()`` is explicit because schema migration is a deployment action,
    not something every web request should perform.  SQLite remains an
    explicitly named qualification profile only.
    """

    if foundation.profile == "disabled":
        raise RuntimeFoundationError("dell_runtime_disabled")
    if foundation.profile == "sqlite_qualification":
        if foundation.sqlite_path is None:  # pragma: no cover - dataclass guard
            raise RuntimeFoundationError("sqlite_qualification_path_missing")
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError as exc:  # pragma: no cover - dependency profile guard
            raise RuntimeFoundationError(
                "agent_runtime_extra_required_for_sqlite"
            ) from exc
        foundation.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with SqliteSaver.from_conn_string(str(foundation.sqlite_path)) as saver:
            yield saver
        return

    if foundation.postgres_url is None:  # pragma: no cover - dataclass guard
        raise RuntimeFoundationError("postgres_pilot_url_missing")
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except ImportError as exc:  # pragma: no cover - dependency profile guard
        raise RuntimeFoundationError(
            "agent_runtime_extra_required_for_postgres"
        ) from exc
    with PostgresSaver.from_conn_string(foundation.postgres_url) as saver:
        if initialize_postgres_schema:
            saver.setup()
        yield saver


__all__ = [
    "DellRuntimeFoundation",
    "POSTGRES_URL_ENV",
    "POSTGRES_URL_FILE_ENV",
    "PROFILE_ENV",
    "RuntimeFoundationError",
    "SQLITE_PATH_ENV",
    "open_runtime_checkpointer",
]
