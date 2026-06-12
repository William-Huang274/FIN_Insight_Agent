from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from env_loader import load_env_file


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "fin_agent_public_source_access_plan_v0.1"

REQUIRED_SOURCE_FIELDS = {
    "source_id",
    "provider",
    "official_url",
    "auth_status",
    "source_families",
    "claim_scope",
    "current_repo_status",
    "collector_status",
    "parser_status",
    "priority",
    "gap_type",
    "boundary_notes",
}

SUPPORTED_LIVE_PROBES = {
    "bea_data_api",
    "bls_public_api",
    "census_data_api",
    "clinicaltrials_api",
    "eia_open_data",
    "fdic_bankfind_api",
    "fred_api",
    "fred_graph_csv",
    "gdelt",
    "gleif_api",
    "kr_dart_openapi",
    "openfda_api",
    "openfigi_api",
    "nhtsa_vpic_api",
    "openalex_api",
    "common_crawl_index",
    "patentsview_api",
    "sec_edgar_apis",
    "wikidata",
    "yahoo_chart",
}

OPTIONAL_KEY_ENVS = {
    "bls_public_api": "BLS_API_KEY",
    "openfda_api": "OPENFDA_API_KEY",
    "openfigi_api": "OPENFIGI_API_KEY",
}

PORTAL_VALIDATION_CHECKS = {
    "tw_mops_portal": [
        "Validate company-code and fiscal-year form parameters.",
        "Validate annual/interim report type filters and language handling.",
        "Preserve official report URL, checksum, publication date, and stale-result guard.",
    ],
    "hkexnews_portal": [
        "Validate issuer-code mapping and headline category filters.",
        "Validate date-window search behavior and bilingual PDF handling.",
        "Preserve announcement URL, PDF URL, checksum, and publication date.",
    ],
    "cninfo_portal": [
        "Validate security-code and org-id mapping.",
        "Validate announcement category and anti-stale-result checks.",
        "Preserve announcement ID, official download URL, checksum, and report title.",
    ],
    "usitc_dataweb_and_trade": [
        "Validate official endpoint or download workflow for HS trade statistics.",
        "Validate parameter contract for period, reporter/partner, HS code, and measure.",
        "Keep trade data as industry/manufacturing context, not company relationship proof.",
    ],
    "patentsview_api": [
        "Validate current USPTO Open Data Portal endpoint replacing legacy PatentsView APIs.",
        "Check whether API key registration is required for selected patent/application data routes.",
        "Keep patent data as technology/IP signal, not product sales or revenue proof.",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate public source coverage and build P0-P3 access plans.")
    parser.add_argument("--coverage-registry", default="configs/data_sources/public_source_coverage_v0_1.yaml")
    parser.add_argument("--source-families", default="configs/data_sources/source_families.yaml")
    parser.add_argument("--output", default="data/manifests/public_source_access_plan_v0_1.jsonl")
    parser.add_argument("--summary-output", default="data/manifests/public_source_access_plan_summary_v0_1.json")
    parser.add_argument("--portal-tasks-output", default="data/manifests/public_source_portal_validation_tasks_v0_1.jsonl")
    parser.add_argument("--env-file", default=".env")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    coverage_path = _resolve(args.coverage_registry)
    families_path = _resolve(args.source_families)
    loaded_env_keys = load_env_file(_resolve(args.env_file))
    registry = _load_yaml(coverage_path)
    source_families = _load_yaml(families_path).get("source_families") or {}

    validation = validate_registry(registry=registry, source_families=source_families)
    if validation["error_count"]:
        print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))
        return 2

    rows = build_access_plan_rows(registry)
    portal_tasks = build_portal_validation_tasks(rows)
    output_path = _resolve(args.output)
    summary_path = _resolve(args.summary_output)
    portal_tasks_path = _resolve(args.portal_tasks_output)
    _write_jsonl(output_path, rows)
    _write_jsonl(portal_tasks_path, portal_tasks)
    summary = summarize_plan(
        rows=rows,
        portal_tasks=portal_tasks,
        validation=validation,
        coverage_path=coverage_path,
        families_path=families_path,
        loaded_env_keys=loaded_env_keys,
        output_path=output_path,
        summary_path=summary_path,
        portal_tasks_path=portal_tasks_path,
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def validate_registry(*, registry: dict[str, Any], source_families: dict[str, Any]) -> dict[str, Any]:
    auth_statuses = set((registry.get("auth_status_definitions") or {}).keys())
    gap_types = set((registry.get("gap_type_definitions") or {}).keys())
    source_family_ids = set(source_families.keys())
    sources = registry.get("sources") or []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, source in enumerate(sources, start=1):
        source_id = str(source.get("source_id") or "")
        missing = sorted(REQUIRED_SOURCE_FIELDS - set(source))
        if missing:
            errors.append({"source_id": source_id or f"row_{index}", "type": "missing_required_fields", "fields": missing})
        if not source_id:
            errors.append({"row": index, "type": "missing_source_id"})
        elif source_id in seen_ids:
            errors.append({"source_id": source_id, "type": "duplicate_source_id"})
        seen_ids.add(source_id)
        auth_status = source.get("auth_status")
        if auth_status not in auth_statuses:
            errors.append({"source_id": source_id, "type": "unknown_auth_status", "auth_status": auth_status})
        gap_type = source.get("gap_type")
        if gap_type not in gap_types:
            errors.append({"source_id": source_id, "type": "unknown_gap_type", "gap_type": gap_type})
        for family in source.get("source_families") or []:
            if family not in source_family_ids:
                errors.append({"source_id": source_id, "type": "unknown_source_family", "source_family": family})
        if auth_status == "free_key" and not source.get("env_var"):
            errors.append({"source_id": source_id, "type": "free_key_source_missing_env_var"})
        if auth_status == "commercial_deferred" and source.get("collector_status") not in {"not_applicable", "deferred"}:
            warnings.append({"source_id": source_id, "type": "commercial_source_has_non_deferred_collector_status"})
    return {
        "schema_version": "fin_agent_public_source_registry_validation_v0.1",
        "source_count": len(sources),
        "unique_source_id_count": len(seen_ids),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def build_access_plan_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    generated_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for source in registry.get("sources") or []:
        source_id = str(source.get("source_id") or "")
        phase = classify_phase(source)
        env_var = str(source.get("env_var") or "")
        optional_key_env = OPTIONAL_KEY_ENVS.get(source_id, "")
        env_present = bool(env_var and os.environ.get(env_var, "").strip())
        optional_key_present = bool(optional_key_env and os.environ.get(optional_key_env, "").strip())
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
                "source_id": source_id,
                "provider": source.get("provider"),
                "phase": phase,
                "auth_status": source.get("auth_status"),
                "env_var": env_var or None,
                "env_present": env_present,
                "optional_key_env": optional_key_env or None,
                "optional_key_present": optional_key_present,
                "source_families": source.get("source_families") or [],
                "claim_scope": source.get("claim_scope"),
                "current_repo_status": source.get("current_repo_status"),
                "collector_status": source.get("collector_status"),
                "parser_status": source.get("parser_status"),
                "gap_type": source.get("gap_type"),
                "priority": source.get("priority"),
                "official_url": source.get("official_url"),
                "live_probe_supported": source_id in SUPPORTED_LIVE_PROBES,
                "action_status": action_status(source, phase=phase, env_present=env_present),
                "next_action": next_action(source, phase=phase, env_present=env_present),
                "boundary_notes": source.get("boundary_notes"),
            }
        )
    return sorted(rows, key=lambda row: (_phase_sort_key(str(row["phase"])), str(row["source_id"])))


def classify_phase(source: dict[str, Any]) -> str:
    auth_status = str(source.get("auth_status") or "")
    if auth_status == "commercial_deferred":
        return "deferred"
    if auth_status in {"official_portal_pending", "endpoint_specific_pending"}:
        return "P3"
    if auth_status == "free_key":
        return "P2"
    return "P1"


def action_status(source: dict[str, Any], *, phase: str, env_present: bool) -> str:
    if phase == "deferred":
        return "deferred_by_no_paid_api_policy"
    if phase == "P3":
        return "portal_or_endpoint_validation_required"
    if phase == "P2":
        return "key_available" if env_present else "key_missing"
    if str(source.get("source_id") or "") in SUPPORTED_LIVE_PROBES:
        return "ready_for_live_probe"
    return "source_plan_only"


def next_action(source: dict[str, Any], *, phase: str, env_present: bool) -> str:
    source_id = str(source.get("source_id") or "")
    if phase == "deferred":
        return "Keep deferred until funding policy changes."
    if phase == "P3":
        return "Build endpoint/profile validation task before collector implementation."
    if phase == "P2":
        env_var = str(source.get("env_var") or "")
        if env_present:
            return f"Run key-backed smoke with {env_var} from environment; do not persist key."
        return f"Ask user to register/configure {env_var}; record auth_gap until available."
    if source_id in SUPPORTED_LIVE_PROBES:
        return "Run no-key live probe and record only normalized smoke metadata."
    if source.get("gap_type") == "parser_gap":
        return "Define parser/ontology before collecting broad data."
    return "Keep as source-plan row until a bounded collector target is selected."


def build_portal_validation_tasks(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    generated_at = datetime.now(timezone.utc).isoformat()
    tasks: list[dict[str, Any]] = []
    for row in rows:
        if row.get("phase") != "P3":
            continue
        source_id = str(row.get("source_id") or "")
        tasks.append(
            {
                "schema_version": "fin_agent_public_source_portal_validation_task_v0.1",
                "generated_at": generated_at,
                "task_id": f"PORTAL_VALIDATION::{source_id}",
                "source_id": source_id,
                "provider": row.get("provider"),
                "auth_status": row.get("auth_status"),
                "gap_type": row.get("gap_type"),
                "official_url": row.get("official_url"),
                "claim_scope": row.get("claim_scope"),
                "validation_checks": PORTAL_VALIDATION_CHECKS.get(
                    source_id,
                    [
                        "Validate official endpoint or portal access pattern.",
                        "Record query parameters, source URL, checksum policy, and parser blocker.",
                        "Keep source boundary unchanged until validation passes.",
                    ],
                ),
                "execution_status": "not_executed_profile_specific_validation_pending",
                "boundary_notes": row.get("boundary_notes"),
            }
        )
    return tasks


def summarize_plan(
    *,
    rows: list[dict[str, Any]],
    portal_tasks: list[dict[str, Any]],
    validation: dict[str, Any],
    coverage_path: Path,
    families_path: Path,
    loaded_env_keys: list[str],
    output_path: Path,
    summary_path: Path,
    portal_tasks_path: Path,
) -> dict[str, Any]:
    key_rows = [row for row in rows if row["phase"] == "P2"]
    optional_key_rows = [row for row in rows if row.get("optional_key_env")]
    return {
        "schema_version": "fin_agent_public_source_access_plan_summary_v0.1",
        "status": "pass" if validation["error_count"] == 0 else "fail",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "coverage_registry": _repo_path(coverage_path),
            "source_families": _repo_path(families_path),
            "loaded_env_key_names": sorted(loaded_env_keys),
        },
        "outputs": {
            "access_plan": _repo_path(output_path),
            "summary": _repo_path(summary_path),
            "portal_validation_tasks": _repo_path(portal_tasks_path),
        },
        "validation": validation,
        "source_count": len(rows),
        "phase_counts": dict(sorted(Counter(str(row["phase"]) for row in rows).items())),
        "action_status_counts": dict(sorted(Counter(str(row["action_status"]) for row in rows).items())),
        "live_probe_supported_count": sum(1 for row in rows if row["live_probe_supported"]),
        "p2_key_requirements": [
            {
                "source_id": row["source_id"],
                "provider": row["provider"],
                "env_var": row["env_var"],
                "env_present": row["env_present"],
                "claim_scope": row["claim_scope"],
            }
            for row in key_rows
        ],
        "missing_required_key_envs": sorted({str(row["env_var"]) for row in key_rows if row["env_var"] and not row["env_present"]}),
        "available_required_key_envs": sorted({str(row["env_var"]) for row in key_rows if row["env_var"] and row["env_present"]}),
        "optional_key_envs": [
            {
                "source_id": row["source_id"],
                "provider": row["provider"],
                "env_var": row["optional_key_env"],
                "env_present": row["optional_key_present"],
            }
            for row in optional_key_rows
        ],
        "portal_validation_task_count": len(portal_tasks),
        "portal_validation_sources": [task["source_id"] for task in portal_tasks],
    }


def _phase_sort_key(phase: str) -> int:
    order = {"P1": 1, "P2": 2, "P3": 3, "deferred": 4}
    return order.get(phase, 9)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def _repo_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
