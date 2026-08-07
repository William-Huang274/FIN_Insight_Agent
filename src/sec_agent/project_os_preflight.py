from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping


PROJECT_OS_DIR = Path("docs") / "project_os"
RUN_SCOPE_REGISTRY_PATH = (
    Path("configs") / "runtime" / "fin_ia_project_os_run_scope_registry_v1_0.json"
)

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

DEFAULT_RUN_SCOPE = "broad_full_chain"
PREFLIGHT_SCHEMA = "fin_insight_project_os_full_chain_preflight_v0_2"
PREFLIGHT_POLICY = "typed_blocker_state_and_registered_run_scope_fail_closed_v0_2"
REGISTRY_SCHEMA = "fin_insight_project_os_run_scope_registry_v1_0"
REQUIRED_BLOCKER_STATES = {
    "open": True,
    "mitigated_open": True,
    "blocked_external": True,
    "closed": False,
    "superseded": False,
}
_SEQUENCE_RE = re.compile(r"^v(?P<major>\d+)_(?P<ordinal>\d+)$")

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
    registry_path = root / RUN_SCOPE_REGISTRY_PATH

    errors: list[str] = []
    contract_errors: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    missing_capabilities: list[str] = []
    capability_count = 0
    issue_count = 0
    checklist_count = 0

    registry: dict[str, Any] = {}
    registry_errors: list[dict[str, Any]] = []
    if not registry_path.is_file():
        registry_errors.append(
            _contract_error("run_scope_registry_missing", path=str(RUN_SCOPE_REGISTRY_PATH))
        )
    else:
        try:
            registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            registry_errors.append(
                _contract_error("run_scope_registry_unreadable", detail=str(exc))
            )
        else:
            if not isinstance(registry_payload, dict):
                registry_errors.append(_contract_error("run_scope_registry_not_object"))
            else:
                registry = registry_payload
                registry_errors.extend(_validate_run_scope_registry(registry))
    contract_errors.extend(registry_errors)

    scope_resolution = _resolve_requested_scope(scope, registry)
    if scope_resolution["status"] != "registered":
        contract_errors.append(
            _contract_error("unknown_or_non_executable_run_scope", run_scope=scope)
        )

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

        projection_errors = _validate_issue_projection_contract(issue_rows, registry)
        contract_errors.extend(projection_errors)
        latest_issues = _latest_rows_by_id(issue_rows, "issue_id")

        for row in latest_issues.values():
            canonical_state, state_source = _canonical_blocker_state(row, registry)
            is_open = _state_is_open(canonical_state, registry)
            if (
                bool(row.get("full_chain_blocker"))
                and is_open
                and scope_resolution["status"] == "registered"
                and _issue_blocks_run_scope(row, scope, registry)
            ):
                blockers.append(
                    {
                        "issue_id": row.get("issue_id"),
                        "status": row.get("status"),
                        "blocker_state": canonical_state,
                        "blocker_state_source": state_source,
                        "severity": row.get("severity"),
                        "layer": row.get("layer"),
                        "symptom": row.get("symptom"),
                        "required_fix": row.get("required_fix"),
                        "run_scope": scope,
                        "blocking_run_scopes": _string_list(row.get("blocking_run_scopes")),
                        "allowed_run_scopes": _string_list(row.get("allowed_run_scopes")),
                        "matched_blocking_scope_refs": _matched_scope_refs(
                            row, scope, registry
                        ),
                    }
                )
    if contract_errors:
        errors.append("project_os_contract_invalid")
    if blockers and not allow_open_blockers:
        errors.append("open_full_chain_blockers")

    hard_errors = [error for error in errors if error != "open_full_chain_blockers"]
    if hard_errors:
        status = "blocked"
    elif blockers and allow_open_blockers:
        status = "diagnostic_override"
        errors = [error for error in errors if error != "open_full_chain_blockers"]
    elif blockers:
        status = "blocked"
    else:
        status = "pass"

    return {
        "schema_version": PREFLIGHT_SCHEMA,
        "status": status,
        "policy": PREFLIGHT_POLICY,
        "project_root": str(root),
        "project_os_dir": str(project_os_dir),
        "run_scope": scope,
        "scope_resolution": scope_resolution,
        "run_scope_registry": {
            "path": str(RUN_SCOPE_REGISTRY_PATH),
            "schema_version": registry.get("schema_version"),
            "registry_id": registry.get("registry_id"),
            "registry_version": registry.get("registry_version"),
            "adoption_sequence_after_projection": registry.get(
                "adoption_sequence_after_projection"
            ),
        },
        "allow_open_blockers": bool(allow_open_blockers),
        "missing_files": missing_files,
        "missing_capabilities": missing_capabilities,
        "open_full_chain_blocker_count": len(blockers),
        "open_full_chain_blockers": blockers,
        "capability_count": capability_count,
        "root_cause_issue_count": issue_count,
        "checklist_count": checklist_count,
        "contract_errors": contract_errors,
        "errors": errors,
        "next_action": _next_action(errors, blockers, contract_errors),
    }


def _next_action(
    errors: list[str],
    blockers: list[Mapping[str, Any]],
    contract_errors: list[Mapping[str, Any]],
) -> str:
    if "missing_required_project_os_files" in errors:
        return "Create or restore docs/project_os required files before full-chain."
    if "required_capability_not_passed" in errors:
        return "Update capability_status_ledger with passed P31 Project OS capability rows after verification."
    if contract_errors:
        return "Repair the typed blocker-state or registered run-scope contract before any execution or diagnostic override."
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


def _issue_blocks_run_scope(
    row: Mapping[str, Any], run_scope: str, registry: Mapping[str, Any]
) -> bool:
    blocking_scopes = set(_string_list(row.get("blocking_run_scopes")))
    allowed_scopes = set(_string_list(row.get("allowed_run_scopes")))
    if "*" in blocking_scopes:
        return not any(_scope_ref_matches(item, run_scope, registry) for item in allowed_scopes)
    if blocking_scopes:
        return any(
            _scope_ref_matches(item, run_scope, registry) for item in blocking_scopes
        ) and not any(
            _scope_ref_matches(item, run_scope, registry) for item in allowed_scopes
        )
    if allowed_scopes:
        return not any(_scope_ref_matches(item, run_scope, registry) for item in allowed_scopes)
    return True


def _contract_error(code: str, **context: Any) -> dict[str, Any]:
    return {"code": code, **context}


def _sequence_number(value: Any) -> tuple[int, int] | None:
    match = _SEQUENCE_RE.fullmatch(str(value or "").strip())
    if match is None:
        return None
    return int(match.group("major")), int(match.group("ordinal"))


def _validate_run_scope_registry(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if registry.get("schema_version") != REGISTRY_SCHEMA:
        errors.append(_contract_error("run_scope_registry_schema_invalid"))
    if not str(registry.get("registry_version") or "").strip():
        errors.append(_contract_error("run_scope_registry_version_missing"))
    if _sequence_number(registry.get("adoption_sequence_after_projection")) is None:
        errors.append(_contract_error("run_scope_registry_adoption_sequence_invalid"))

    states = registry.get("blocker_states")
    if not isinstance(states, dict):
        errors.append(_contract_error("blocker_state_registry_missing"))
    else:
        for state, expected_open in REQUIRED_BLOCKER_STATES.items():
            metadata = states.get(state)
            if not isinstance(metadata, dict) or metadata.get("is_open") is not expected_open:
                errors.append(
                    _contract_error("required_blocker_state_invalid", blocker_state=state)
                )
        compatibility = registry.get("legacy_compatibility") or {}
        if compatibility.get("through_sequence_after_projection") != registry.get(
            "adoption_sequence_after_projection"
        ):
            errors.append(_contract_error("legacy_compatibility_cutoff_mismatch"))
        aliases = compatibility.get("status_aliases") or {}
        for legacy_status, canonical_state in aliases.items():
            if canonical_state not in states:
                errors.append(
                    _contract_error(
                        "legacy_status_alias_target_unknown",
                        legacy_status=legacy_status,
                        blocker_state=canonical_state,
                    )
                )

    owner_stages = set(_string_list(registry.get("owner_stages")))
    operation_classes = set(_string_list(registry.get("operation_classes")))
    scopes = registry.get("scopes")
    if not isinstance(scopes, dict) or not scopes:
        errors.append(_contract_error("run_scope_registry_scopes_missing"))
        return errors

    for scope_id, metadata in scopes.items():
        if not isinstance(metadata, dict):
            errors.append(_contract_error("run_scope_metadata_invalid", run_scope=scope_id))
            continue
        owner = str(metadata.get("owner_stage") or "")
        operation = str(metadata.get("operation_class") or "")
        parent = metadata.get("parent_scope_id")
        if owner not in owner_stages:
            errors.append(
                _contract_error("run_scope_owner_unknown", run_scope=scope_id, owner_stage=owner)
            )
        if operation not in operation_classes:
            errors.append(
                _contract_error(
                    "run_scope_operation_unknown",
                    run_scope=scope_id,
                    operation_class=operation,
                )
            )
        if metadata.get("executable") not in {True, False}:
            errors.append(_contract_error("run_scope_executable_flag_invalid", run_scope=scope_id))
        if parent is not None and parent not in scopes:
            errors.append(
                _contract_error("run_scope_parent_unknown", run_scope=scope_id, parent=parent)
            )
        if parent in scopes:
            parent_owner = str((scopes.get(parent) or {}).get("owner_stage") or "")
            if parent_owner not in {"shared", owner}:
                errors.append(
                    _contract_error(
                        "run_scope_parent_owner_mismatch",
                        run_scope=scope_id,
                        owner_stage=owner,
                        parent_scope_id=parent,
                        parent_owner_stage=parent_owner,
                    )
                )
        projection_owners = set(_string_list(metadata.get("allowed_projection_owner_stages")))
        if not projection_owners or not projection_owners.issubset(owner_stages):
            errors.append(
                _contract_error("run_scope_projection_owners_invalid", run_scope=scope_id)
            )

    for scope_id in scopes:
        visited: set[str] = set()
        cursor: Any = scope_id
        while cursor is not None and cursor in scopes:
            if cursor in visited:
                errors.append(_contract_error("run_scope_parent_cycle", run_scope=scope_id))
                break
            visited.add(cursor)
            cursor = (scopes[cursor] or {}).get("parent_scope_id")
    return errors


def _resolve_requested_scope(scope: str, registry: Mapping[str, Any]) -> dict[str, Any]:
    scopes = registry.get("scopes") or {}
    metadata = scopes.get(scope) if isinstance(scopes, dict) else None
    if not isinstance(metadata, dict) or metadata.get("executable") is not True:
        return {
            "status": "unknown_or_non_executable",
            "canonical_scope_id": None,
            "owner_stage": None,
            "operation_class": None,
            "parent_scope_id": None,
        }
    return {
        "status": "registered",
        "canonical_scope_id": scope,
        "owner_stage": metadata.get("owner_stage"),
        "operation_class": metadata.get("operation_class"),
        "parent_scope_id": metadata.get("parent_scope_id"),
    }


def _validate_issue_projection_contract(
    rows: Iterable[Mapping[str, Any]], registry: Mapping[str, Any]
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    adoption = _sequence_number(registry.get("adoption_sequence_after_projection"))
    if adoption is None:
        return errors
    registry_version = str(registry.get("registry_version") or "")
    states = registry.get("blocker_states") or {}
    scopes = registry.get("scopes") or {}
    owners = set(_string_list(registry.get("owner_stages")))
    previous_by_issue: dict[str, str | None] = {}
    previous_global: tuple[int, int] | None = None

    for row in rows:
        issue_id = str(row.get("issue_id") or "").strip()
        sequence_raw = str(row.get("sequence_after_projection") or "").strip()
        sequence = _sequence_number(sequence_raw)
        prior_for_issue = previous_by_issue.get(issue_id)
        is_post_adoption = sequence is not None and sequence > adoption
        if is_post_adoption:
            if previous_global is not None and sequence <= previous_global:
                errors.append(
                    _contract_error(
                        "projection_sequence_not_append_only",
                        issue_id=issue_id,
                        sequence_after_projection=sequence_raw,
                    )
                )
            blocker_state = str(row.get("blocker_state") or "").strip()
            owner_stage = str(row.get("owner_stage") or "").strip()
            if blocker_state not in states:
                errors.append(
                    _contract_error(
                        "projection_blocker_state_unknown",
                        issue_id=issue_id,
                        blocker_state=blocker_state,
                    )
                )
            if row.get("run_scope_registry_version") != registry_version:
                errors.append(
                    _contract_error(
                        "projection_registry_version_mismatch", issue_id=issue_id
                    )
                )
            if owner_stage not in owners:
                errors.append(
                    _contract_error(
                        "projection_owner_stage_unknown",
                        issue_id=issue_id,
                        owner_stage=owner_stage,
                    )
                )
            if row.get("previous_projection_sequence") != prior_for_issue:
                errors.append(
                    _contract_error(
                        "projection_lineage_mismatch",
                        issue_id=issue_id,
                        expected_previous_projection_sequence=prior_for_issue,
                    )
                )
            is_open = _state_is_open(blocker_state, registry)
            if is_open != bool(row.get("full_chain_blocker")):
                errors.append(
                    _contract_error(
                        "projection_blocker_flag_state_mismatch", issue_id=issue_id
                    )
                )
            for field in ("blocking_run_scopes", "allowed_run_scopes"):
                for scope_ref in _string_list(row.get(field)):
                    if scope_ref == "*":
                        if field != "blocking_run_scopes":
                            errors.append(
                                _contract_error(
                                    "wildcard_allowed_scope_forbidden", issue_id=issue_id
                                )
                            )
                        continue
                    metadata = scopes.get(scope_ref) if isinstance(scopes, dict) else None
                    if not isinstance(metadata, dict):
                        errors.append(
                            _contract_error(
                                "projection_scope_unregistered",
                                issue_id=issue_id,
                                run_scope_ref=scope_ref,
                            )
                        )
                        continue
                    allowed_owners = set(
                        _string_list(metadata.get("allowed_projection_owner_stages"))
                    )
                    if owner_stage not in allowed_owners:
                        errors.append(
                            _contract_error(
                                "projection_scope_owner_mismatch",
                                issue_id=issue_id,
                                run_scope_ref=scope_ref,
                                owner_stage=owner_stage,
                            )
                        )
        if issue_id:
            previous_by_issue[issue_id] = sequence_raw or None
        if sequence is not None:
            previous_global = sequence
    return errors


def _canonical_blocker_state(
    row: Mapping[str, Any], registry: Mapping[str, Any]
) -> tuple[str, str]:
    adoption = _sequence_number(registry.get("adoption_sequence_after_projection"))
    sequence = _sequence_number(row.get("sequence_after_projection"))
    if adoption is not None and sequence is not None and sequence > adoption:
        return str(row.get("blocker_state") or "").strip(), "typed_projection"
    compatibility = registry.get("legacy_compatibility") or {}
    aliases = compatibility.get("status_aliases") or {}
    status = str(row.get("status") or "").strip()
    canonical = aliases.get(status) if isinstance(aliases, dict) else None
    if canonical:
        return str(canonical), "legacy_exact_alias"
    if bool(row.get("full_chain_blocker")):
        return str(compatibility.get("unknown_full_chain_blocker_state") or ""), (
            "legacy_unknown_fail_closed"
        )
    return str(compatibility.get("unknown_non_blocker_state") or ""), (
        "legacy_non_blocker_compatibility"
    )


def _state_is_open(state: str, registry: Mapping[str, Any]) -> bool:
    metadata = (registry.get("blocker_states") or {}).get(state) or {}
    return metadata.get("is_open") is True


def _scope_ancestors(scope: str, registry: Mapping[str, Any]) -> set[str]:
    scopes = registry.get("scopes") or {}
    ancestors = {scope}
    cursor = scope
    while isinstance(scopes, dict) and cursor in scopes:
        parent = (scopes.get(cursor) or {}).get("parent_scope_id")
        if parent is None or parent in ancestors:
            break
        ancestors.add(str(parent))
        cursor = str(parent)
    return ancestors


def _scope_ref_matches(
    scope_ref: str, requested_scope: str, registry: Mapping[str, Any]
) -> bool:
    return scope_ref == requested_scope or scope_ref in _scope_ancestors(
        requested_scope, registry
    )


def _matched_scope_refs(
    row: Mapping[str, Any], requested_scope: str, registry: Mapping[str, Any]
) -> list[str]:
    blocking = _string_list(row.get("blocking_run_scopes"))
    if "*" in blocking:
        return ["*"]
    return [
        ref for ref in blocking if _scope_ref_matches(ref, requested_scope, registry)
    ]


def compact_preflight_stdout(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": result.get("schema_version"),
        "status": result.get("status"),
        "policy": result.get("policy"),
        "run_scope": result.get("run_scope"),
        "scope_resolution": result.get("scope_resolution"),
        "run_scope_registry": result.get("run_scope_registry"),
        "allow_open_blockers": result.get("allow_open_blockers"),
        "missing_files": result.get("missing_files"),
        "missing_capabilities": result.get("missing_capabilities"),
        "open_full_chain_blocker_count": result.get(
            "open_full_chain_blocker_count",
            len(result.get("open_full_chain_blockers") or []),
        ),
        "open_full_chain_blockers": result.get("open_full_chain_blockers"),
        "contract_errors": result.get("contract_errors"),
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
