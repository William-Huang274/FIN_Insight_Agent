"""Retired direct runner for the Dell reference vertical.

The product runtime is exclusively LangGraph Agent Server with LangSmith.
This module remains as a typed tombstone so old commands fail explicitly
instead of silently recreating the former local SQLite/direct-call runtime.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import NoReturn


LEGACY_RUNTIME_RETIREMENT_CODE = (
    "dell_legacy_runtime_retired_agent_server_langsmith_required"
)
LEGACY_RUNTIME_RETIREMENT_SCHEMA = (
    "fin_ia_dell_legacy_runtime_retirement_v1"
)
LEGACY_RUNTIME_RETIREMENT_EXIT_CODE = 78


class DellReferenceVerticalCLIError(RuntimeError):
    """Typed refusal returned by the retired direct runner."""

    def __init__(self, *, command: str) -> None:
        self.code = LEGACY_RUNTIME_RETIREMENT_CODE
        self.command = command
        super().__init__(self.code)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Retired Dell direct runner. Use the official Agent Server SDK "
            "client against the LangGraph Agent Server deployment; LangSmith "
            "tracing is mandatory."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("start", "resume"):
        subparsers.add_parser(
            command,
            help=f"retired command; always returns {LEGACY_RUNTIME_RETIREMENT_CODE}",
        )
    return parser


def retirement_receipt(*, command: str) -> dict[str, object]:
    """Return the secret-free machine-readable retirement fact."""

    return {
        "schema_version": LEGACY_RUNTIME_RETIREMENT_SCHEMA,
        "status": "retired",
        "code": LEGACY_RUNTIME_RETIREMENT_CODE,
        "command": command,
        "replacement": "langgraph_agent_server_plus_langsmith",
        "fallback_available": False,
    }


def main(argv: Sequence[str] | None = None) -> NoReturn:
    args, _legacy_arguments = _parser().parse_known_args(argv)
    raise DellReferenceVerticalCLIError(command=args.command)


def _entrypoint(argv: Sequence[str] | None = None) -> int:
    try:
        main(argv)
    except DellReferenceVerticalCLIError as exc:
        print(
            json.dumps(
                retirement_receipt(command=exc.command),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return LEGACY_RUNTIME_RETIREMENT_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(_entrypoint())


__all__ = [
    "DellReferenceVerticalCLIError",
    "LEGACY_RUNTIME_RETIREMENT_CODE",
    "LEGACY_RUNTIME_RETIREMENT_EXIT_CODE",
    "LEGACY_RUNTIME_RETIREMENT_SCHEMA",
    "main",
    "retirement_receipt",
]
