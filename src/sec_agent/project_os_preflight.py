from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


PROJECT_OS_DIR = Path("docs") / "project_os"

REQUIRED_FILES = (
    "README.md",
    "current_context_pack.zh-CN.md",
    "capability_status_ledger.jsonl",
    "root_cause_issue_ledger.jsonl",
    "external_pattern_registry.jsonl",
    "financial_research_method_registry.jsonl",
    "full_chain_run_policy.zh-CN.md",
    "token_budget_policy.zh-CN.md",
    "done_definition_l4_scope_pass.zh-CN.md",
    "full_chain_preflight_checklist.json",
)

REQUIRED_CAPABILITY_IDS = (
    "p31_project_os_core",
    "p31_full_chain_preflight_guard",
)

OPEN_BLOCKER_STATUSES = {
    "open",
    "active",
    "blocked",
    "blocked_root_cause_unknown",
    "root_cause_repair_required",
}

DEFAULT_RUN_SCOPE = "broad_full_chain"

PASS_STATUSES = {
    "L4_scope_pass",
    "deterministic_tested",
    "component_l4",
    "component_l4_partial",
    "partial_l4_scope",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no} invalid JSONL row: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no} JSONL row must be an object")
        rows.append(row)
    return rows


def _latest_rows_by_id(rows: Iterable[Mapping[str, Any]], id_key: str) -> dict[str, Mapping[str, Any]]:
    latest: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        row_id = str(row.get(id_key) or "").strip()
        if row_id:
            latest[row_id] = row
    return latest


def run_project_os_preflight(
    project_root: Path | str,
    *,
    allow_open_blockers: bool = False,
    run_scope: str = DEFAULT_RUN_SCOPE,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    scope = str(run_scope or DEFAULT_RUN_SCOPE).strip() or DEFAULT_RUN_SCOPE
    project_os_dir = root / PROJECT_OS_DIR
    missing_files = [name for name in REQUIRED_FILES if not (project_os_dir / name).exists()]

    errors: list[str] = []
    blockers: list[dict[str, Any]] = []
    missing_capabilities: list[str] = []
    capability_count = 0
    issue_count = 0
    checklist_count = 0

    if missing_files:
        errors.append("missing_required_project_os_files")
    else:
        capability_rows = read_jsonl(project_os_dir / "capability_status_ledger.jsonl")
        issue_rows = read_jsonl(project_os_dir / "root_cause_issue_ledger.jsonl")
        checklist = json.loads((project_os_dir / "full_chain_preflight_checklist.json").read_text(encoding="utf-8"))
        if not isinstance(checklist, dict):
            raise ValueError("full_chain_preflight_checklist.json must contain an object")
        checklist_items = checklist.get("checks") or []
        if not isinstance(checklist_items, list):
            raise ValueError("full_chain_preflight_checklist.json checks must be a list")
        checklist_count = len(checklist_items)

        latest_capabilities = _latest_rows_by_id(capability_rows, "capability_id")
        capability_count = len(latest_capabilities)
        issue_count = len(issue_rows)

        for capability_id in REQUIRED_CAPABILITY_IDS:
            row = latest_capabilities.get(capability_id)
            status = str(row.get("status") if row else "").strip()
            if row is None or status not in PASS_STATUSES:
                missing_capabilities.append(capability_id)
        if missing_capabilities:
            errors.append("required_capability_not_passed")

        latest_issues = _latest_rows_by_id(issue_rows, "issue_id")

        for row in latest_issues.values():
            status = str(row.get("status") or "").strip().lower()
            if bool(row.get("full_chain_blocker")) and status in OPEN_BLOCKER_STATUSES and _issue_blocks_run_scope(row, scope):
                blockers.append(
                    {
                        "issue_id": row.get("issue_id"),
                        "status": row.get("status"),
                        "severity": row.get("severity"),
                        "layer": row.get("layer"),
                        "symptom": row.get("symptom"),
                        "required_fix": row.get("required_fix"),
                        "run_scope": scope,
                        "blocking_run_scopes": _string_list(row.get("blocking_run_scopes")),
                        "allowed_run_scopes": _string_list(row.get("allowed_run_scopes")),
                    }
                )
        if blockers and not allow_open_blockers:
            errors.append("open_full_chain_blockers")

    if errors:
        status = "blocked"
    elif blockers and allow_open_blockers:
        status = "diagnostic_override"
    else:
        status = "pass"

    return {
        "schema_version": "fin_insight_project_os_full_chain_preflight_v0_1",
        "status": status,
        "policy": "fail_closed_on_open_project_os_blockers_v0_1",
        "project_root": str(root),
        "project_os_dir": str(project_os_dir),
        "run_scope": scope,
        "allow_open_blockers": bool(allow_open_blockers),
        "missing_files": missing_files,
        "missing_capabilities": missing_capabilities,
        "open_full_chain_blockers": blockers,
        "capability_count": capability_count,
        "root_cause_issue_count": issue_count,
        "checklist_count": checklist_count,
        "errors": errors,
        "next_action": _next_action(errors, blockers),
    }


def _next_action(errors: list[str], blockers: list[Mapping[str, Any]]) -> str:
    if "missing_required_project_os_files" in errors:
        return "Create or restore docs/project_os required files before full-chain."
    if "required_capability_not_passed" in errors:
        return "Update capability_status_ledger with passed P31 Project OS capability rows after verification."
    if blockers:
        return "Close the listed root-cause blockers or ask for explicit diagnostic override before paid full-chain."
    if errors:
        return "Inspect Project OS preflight errors before running full-chain."
    return "Project OS preflight passed. Continue to token budget, provider, evidence-mode, AIE, and data-script preflights."


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    return []


def _issue_blocks_run_scope(row: Mapping[str, Any], run_scope: str) -> bool:
    blocking_scopes = set(_string_list(row.get("blocking_run_scopes")))
    allowed_scopes = set(_string_list(row.get("allowed_run_scopes")))
    if "*" in blocking_scopes:
        return run_scope not in allowed_scopes
    if blocking_scopes:
        return run_scope in blocking_scopes and run_scope not in allowed_scopes
    if allowed_scopes:
        return run_scope not in allowed_scopes
    return True


def compact_preflight_stdout(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": result.get("schema_version"),
        "status": result.get("status"),
        "policy": result.get("policy"),
        "run_scope": result.get("run_scope"),
        "allow_open_blockers": result.get("allow_open_blockers"),
        "missing_files": result.get("missing_files"),
        "missing_capabilities": result.get("missing_capabilities"),
        "open_full_chain_blocker_count": len(result.get("open_full_chain_blockers") or []),
        "open_full_chain_blockers": result.get("open_full_chain_blockers"),
        "errors": result.get("errors"),
        "next_action": result.get("next_action"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run FIN Insight Project OS full-chain preflight.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--allow-open-blockers", action="store_true")
    parser.add_argument(
        "--run-scope",
        default=DEFAULT_RUN_SCOPE,
        help=(
            "Scope for blocker evaluation. Defaults to broad_full_chain. "
            "Scoped entries in root_cause_issue_ledger can block broad eval while allowing a controlled single-case run."
        ),
    )
    parser.add_argument("--output-json", type=Path, default=None)
    args = parser.parse_args(argv)

    result = run_project_os_preflight(
        args.project_root,
        allow_open_blockers=args.allow_open_blockers,
        run_scope=args.run_scope,
    )
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(compact_preflight_stdout(result), ensure_ascii=False, indent=2), flush=True)
    return 0 if result["status"] in {"pass", "diagnostic_override"} else 4


if __name__ == "__main__":
    raise SystemExit(main())
