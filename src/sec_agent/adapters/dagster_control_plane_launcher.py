from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Mapping, NoReturn, Sequence
from urllib.parse import urlsplit


POSTGRES_URL_FILE_ENV = "DAGSTER_POSTGRES_URL_FILE"
POSTGRES_URL_ENV = "DAGSTER_POSTGRES_URL"
MAX_SECRET_BYTES = 16 * 1024


def load_postgres_url_from_secret_file(environment: Mapping[str, str]) -> str:
    """Load the Dagster database URL without putting it in Compose interpolation."""

    configured = environment.get(POSTGRES_URL_FILE_ENV, "").strip()
    if not configured:
        raise RuntimeError("dagster_postgres_url_secret_file_is_required")
    path = Path(configured)
    if not path.is_file():
        raise RuntimeError("dagster_postgres_url_secret_file_is_missing")
    if path.stat().st_size > MAX_SECRET_BYTES:
        raise RuntimeError("dagster_postgres_url_secret_file_is_too_large")
    value = path.read_text(encoding="utf-8").strip()
    if not value or "\x00" in value or "\n" in value or "\r" in value:
        raise RuntimeError("dagster_postgres_url_secret_file_is_invalid")
    parsed = urlsplit(value)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        raise RuntimeError("dagster_postgres_url_secret_file_is_not_a_postgres_url")
    if not parsed.path or parsed.path == "/":
        raise RuntimeError("dagster_postgres_url_secret_file_has_no_database")
    return value


def build_dagster_environment(environment: Mapping[str, str]) -> dict[str, str]:
    value = load_postgres_url_from_secret_file(environment)
    child = dict(environment)
    child[POSTGRES_URL_ENV] = value
    child.pop(POSTGRES_URL_FILE_ENV, None)
    return child


def exec_dagster(arguments: Sequence[str], environment: Mapping[str, str]) -> NoReturn:
    if not arguments:
        raise RuntimeError("dagster_command_is_required")
    child = build_dagster_environment(environment)
    os.execvpe("dagster", ["dagster", *arguments], child)
    raise AssertionError("os.execvpe returned unexpectedly")


def main() -> int:
    exec_dagster(sys.argv[1:], os.environ)


if __name__ == "__main__":
    raise SystemExit(main())
