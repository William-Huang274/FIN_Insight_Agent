from __future__ import annotations

"""Pytest plugin used by the FIN 0.1.2 hermetic active-suite runner.

The plugin intentionally writes raw captured text only inside a disposable
runtime.  The parent runner immediately converts those values into
content-addressed objects and persists references in the durable result.
"""

import json
import os
from pathlib import Path
from typing import Any


_REPORTS: dict[str, list[dict[str, Any]]] = {}
_COLLECTION_ERRORS: list[dict[str, str]] = []


def _longrepr(report: Any) -> str:
    value = getattr(report, "longreprtext", None)
    if isinstance(value, str):
        return value
    value = getattr(report, "longrepr", None)
    return "" if value is None else str(value)


def pytest_runtest_logreport(report: Any) -> None:
    _REPORTS.setdefault(str(report.nodeid), []).append(
        {
            "phase": str(report.when),
            "outcome": str(report.outcome),
            "duration_seconds": float(getattr(report, "duration", 0.0)),
            "stdout": str(getattr(report, "capstdout", "") or ""),
            "stderr": str(getattr(report, "capstderr", "") or ""),
            "detail": _longrepr(report),
        }
    )


def pytest_collectreport(report: Any) -> None:
    if bool(getattr(report, "failed", False)):
        _COLLECTION_ERRORS.append(
            {
                "nodeid": str(getattr(report, "nodeid", "collection")),
                "detail": _longrepr(report),
            }
        )


def _terminal_outcome(phases: list[dict[str, Any]]) -> str:
    if any(row["outcome"] == "failed" for row in phases):
        return "failed"
    if any(row["phase"] == "call" and row["outcome"] == "passed" for row in phases):
        return "passed"
    if any(row["outcome"] == "skipped" for row in phases):
        return "skipped"
    return "incomplete"


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    output_value = os.environ.get("FIN_0_1_2_HERMETIC_CAPTURE_PATH")
    if not output_value:
        raise RuntimeError("FIN_0_1_2_HERMETIC_CAPTURE_PATH is required")
    output = Path(output_value)
    output.parent.mkdir(parents=True, exist_ok=True)
    tests = []
    for nodeid in sorted(_REPORTS):
        phases = _REPORTS[nodeid]
        tests.append(
            {
                "nodeid": nodeid,
                "outcome": _terminal_outcome(phases),
                "phases": phases,
                "stdout": "".join(str(row["stdout"]) for row in phases),
                "stderr": "".join(str(row["stderr"]) for row in phases),
                "detail": "\n".join(
                    str(row["detail"]) for row in phases if row["detail"]
                ),
            }
        )
    payload = {
        "schema_version": "fin_ia_pytest_raw_capture_v1_0",
        "session_exit_code": int(exitstatus),
        "tests": tests,
        "collection_errors": _COLLECTION_ERRORS,
    }
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(output)
