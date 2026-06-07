from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAN = REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_source_plan_v0_1.jsonl"
DEFAULT_PROFILES = REPO_ROOT / "configs" / "data_sources" / "global_public_disclosure_profiles_v0_1.yaml"
DEFAULT_MANIFEST = REPO_ROOT / "data" / "manifests" / "tier2_supply_chain_supplement_manifest.jsonl"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit global public disclosure source-plan contracts.")
    parser.add_argument("--source-plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--expected-count", type=int, default=0)
    parser.add_argument("--summary-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan_rows = _load_jsonl(_resolve(args.source_plan))
    profiles_config = _load_yaml(_resolve(args.profiles))
    manifest_rows = _load_jsonl(_resolve(args.manifest)) if args.manifest else []
    summary = audit_global_public_disclosure_source_plan(
        plan_rows=plan_rows,
        profiles_config=profiles_config,
        manifest_rows=manifest_rows,
        expected_count=args.expected_count,
    )
    if args.summary_output:
        path = _resolve(args.summary_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "pass" else 1


def audit_global_public_disclosure_source_plan(
    *,
    plan_rows: Iterable[Mapping[str, Any]],
    profiles_config: Mapping[str, Any],
    manifest_rows: Iterable[Mapping[str, Any]] = (),
    expected_count: int = 0,
) -> dict[str, Any]:
    rows = list(plan_rows)
    profiles = profiles_config.get("profiles") or {}
    errors: list[dict[str, Any]] = []
    plan_ids = [str(row.get("plan_id") or "").strip() for row in rows]
    duplicate_ids = sorted([plan_id for plan_id, count in Counter(plan_ids).items() if plan_id and count > 1])
    if expected_count and len(rows) != expected_count:
        errors.append({"type": "plan_row_count_mismatch", "actual": len(rows), "expected": expected_count})
    if duplicate_ids:
        errors.append({"type": "duplicate_plan_ids", "plan_ids": duplicate_ids[:50]})

    global_manifest_rows = [row for row in manifest_rows if row.get("global_public_download_eligible")]
    for row in global_manifest_rows:
        if row.get("target_reports"):
            errors.append(
                {
                    "type": "company_level_target_reports_not_allowed",
                    "ticker": row.get("ticker"),
                    "target_reports": row.get("target_reports"),
                }
            )

    for index, row in enumerate(rows):
        ticker = str(row.get("ticker") or "").strip()
        profile_name = str(row.get("disclosure_profile") or "").strip()
        profile = profiles.get(profile_name)
        for field in (
            "plan_id",
            "ticker",
            "issuer_id",
            "company_name",
            "source_family",
            "source_tier",
            "disclosure_profile",
            "fiscal_year",
            "report_type",
            "source_locator_urls",
            "cache_dir",
            "parser_profile",
        ):
            if not row.get(field):
                errors.append({"type": "required_field_missing", "index": index, "ticker": ticker, "field": field})
        if not profile:
            errors.append({"type": "missing_profile", "index": index, "ticker": ticker, "disclosure_profile": profile_name})
            continue
        report_type = str(row.get("report_type") or "").strip()
        allowed_reports = set(_string_list(profile.get("annual_report_types"))) | set(_string_list(profile.get("interim_report_types")))
        include_overrides = set(_string_list(row.get("report_type_include_overrides")))
        if report_type not in allowed_reports and report_type not in include_overrides:
            errors.append(
                {
                    "type": "report_type_not_allowed_by_profile",
                    "index": index,
                    "ticker": ticker,
                    "disclosure_profile": profile_name,
                    "report_type": report_type,
                }
            )
        if str(row.get("report_type_rule_source") or "") != "disclosure_profile":
            errors.append({"type": "report_type_rule_source_not_profile", "index": index, "ticker": ticker})
        if (include_overrides or set(_string_list(row.get("report_type_exclude_overrides")))) and not row.get("report_type_override_reason"):
            errors.append({"type": "report_type_override_reason_required", "index": index, "ticker": ticker})
        if str(row.get("source_tier") or "") != str(profile.get("source_tier") or ""):
            errors.append({"type": "source_tier_profile_mismatch", "index": index, "ticker": ticker})
        if str(row.get("parser_profile") or "") != str(profile.get("parser_profile") or ""):
            errors.append({"type": "parser_profile_mismatch", "index": index, "ticker": ticker})

    return {
        "schema_version": "fin_agent_global_public_disclosure_source_plan_audit_v0.1",
        "status": "fail" if errors else "pass",
        "plan_row_count": len(rows),
        "company_count": len({str(row.get("ticker") or "") for row in rows}),
        "profile_counts": dict(sorted(Counter(str(row.get("disclosure_profile") or "unknown") for row in rows).items())),
        "report_type_counts": dict(sorted(Counter(str(row.get("report_type") or "unknown") for row in rows).items())),
        "errors": errors,
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    return [str(value).strip()]


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
