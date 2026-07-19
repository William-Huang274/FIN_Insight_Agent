"""Workbench projection for Agent Information Economy artifacts.

This module is intentionally read-only. It scans compact AIE JSON artifacts
instead of raw prompts or full memo payloads, so Workbench can explain token
budget blocks and token-to-insight failures without loading expensive run
materials into the browser.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "finsight_workbench_agent_information_economy_projection_v0_1"
DEFAULT_SEARCH_ROOTS = (
    Path("reports") / "r53_r60_p30_full_chain_ai_semis",
    Path("reports") / "quality" / "workbench_eval",
    Path("eval") / "sec_cases" / "outputs",
)
AIE_FILENAMES = {
    "agent_information_economy_preflight.json": "preflight",
    "agent_information_economy_audit.json": "audit",
}


def build_agent_information_economy_projection(root: str | Path, *, limit: int = 12) -> dict[str, Any]:
    """Return a compact Workbench-ready view of saved AIE artifacts."""

    repo_root = Path(root).resolve()
    artifacts = _find_aie_artifacts(repo_root)
    rows: list[dict[str, Any]] = []
    for path in artifacts[: max(limit, 1)]:
        rows.append(_artifact_row(repo_root, path))

    valid_rows = [row for row in rows if row.get("read_status") == "ok"]
    issue_counts: Counter[str] = Counter()
    for row in valid_rows:
        issue_counts.update(row.get("issue_counts") or {})

    latest = valid_rows[0] if valid_rows else None
    blocked_rows = [
        row
        for row in valid_rows
        if str(row.get("plan_status") or "").startswith("blocked")
        or str(row.get("status") or "") == "fail"
    ]
    highest_estimated_tokens = max([_as_int(row.get("estimated_total_tokens")) for row in valid_rows] or [0])
    highest_estimated_paid_calls = max([_as_int(row.get("estimated_paid_call_count")) for row in valid_rows] or [0])
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "missing" if not artifacts else ("fail" if latest and latest.get("status") == "fail" else "pass"),
        "artifact_count": len(artifacts),
        "visible_artifact_count": len(rows),
        "latest_artifact": latest,
        "summary": {
            "latest_run_id": latest.get("run_id") if latest else "",
            "latest_status": latest.get("status") if latest else "missing",
            "latest_plan_status": latest.get("plan_status") if latest else "",
            "budget_block_count": len(blocked_rows),
            "highest_estimated_total_tokens": highest_estimated_tokens,
            "highest_estimated_paid_call_count": highest_estimated_paid_calls,
            "issue_counts": dict(sorted(issue_counts.items())),
        },
        "artifacts": rows,
        "policy": "workbench_reads_compact_aie_json_without_raw_prompt_or_paid_model_calls_v0_1",
    }


def _find_aie_artifacts(repo_root: Path) -> list[Path]:
    paths: list[Path] = []
    for rel_root in DEFAULT_SEARCH_ROOTS:
        search_root = repo_root / rel_root
        if not search_root.exists():
            continue
        for filename in AIE_FILENAMES:
            paths.extend(search_root.rglob(filename))
    return sorted({path.resolve() for path in paths}, key=lambda item: item.stat().st_mtime, reverse=True)


def _artifact_row(repo_root: Path, path: Path) -> dict[str, Any]:
    artifact_type = AIE_FILENAMES.get(path.name, "unknown")
    base = {
        "artifact_type": artifact_type,
        "rel_path": _rel_path(repo_root, path),
        "updated_at": _mtime_iso(path),
    }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            **base,
            "read_status": "error",
            "status": "fail",
            "run_id": "",
            "error": str(exc),
            "issue_counts": {"artifact_read_error": 1},
            "cases": [],
        }
    if not isinstance(payload, Mapping):
        return {
            **base,
            "read_status": "error",
            "status": "fail",
            "run_id": "",
            "error": "artifact_payload_not_object",
            "issue_counts": {"artifact_payload_not_object": 1},
            "cases": [],
        }
    cases = [_case_row(case) for case in payload.get("cases") or [] if isinstance(case, Mapping)]
    return {
        **base,
        "read_status": "ok",
        "run_id": str(payload.get("run_id") or ""),
        "status": str(payload.get("status") or ""),
        "plan_status": str(payload.get("plan_status") or ""),
        "preflight_only": bool(payload.get("preflight_only")),
        "diagnostic_only": bool(payload.get("diagnostic_only")),
        "estimated_total_tokens": _as_int(payload.get("estimated_total_tokens")),
        "estimated_paid_call_count": _as_int(payload.get("estimated_paid_call_count")),
        "case_count": _as_int(payload.get("case_count")) or len(cases),
        "failed_case_ids": [str(item) for item in payload.get("failed_case_ids") or []],
        "issue_counts": dict(payload.get("issue_counts") or {}),
        "aggregate_metrics": dict(payload.get("aggregate_metrics") or {}),
        "scheduler_advice": dict(payload.get("scheduler_advice") or {})
        if isinstance(payload.get("scheduler_advice"), Mapping)
        else {},
        "root_cause_candidates": sorted({item for case in cases for item in case.get("root_cause_candidates", [])}),
        "cases": cases[:6],
    }


def _case_row(case: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_id": str(case.get("case_id") or ""),
        "status": str(case.get("status") or case.get("gate_status") or ""),
        "estimated_total_tokens": _as_int(case.get("estimated_total_tokens")),
        "estimated_paid_call_count": _as_int(case.get("estimated_paid_call_count")),
        "estimated_specialist_count": _as_int(case.get("estimated_specialist_count")),
        "active_specialist_count": _as_int((case.get("specialists") or {}).get("active_count"))
        if isinstance(case.get("specialists"), Mapping)
        else 0,
        "issues": [str(item) for item in case.get("issues") or []],
        "prunable_specialist_agents": [str(item) for item in case.get("prunable_specialist_agents") or []],
        "root_cause_candidates": [str(item) for item in case.get("root_cause_candidates") or []],
    }


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _rel_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
