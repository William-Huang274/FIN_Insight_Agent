from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate first-pass TableObject, MetricObject, and ClaimObject extraction anchors."
    )
    parser.add_argument(
        "--structured-dir",
        default="data/processed_private/structured_objects",
    )
    parser.add_argument("--prefix", default="sec_tech_10k")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    structured_dir = REPO_ROOT / args.structured_dir
    metrics = list(_read_jsonl(structured_dir / f"{args.prefix}_metrics.jsonl"))
    claims = list(_read_jsonl(structured_dir / f"{args.prefix}_claims.jsonl"))
    tables = list(_read_jsonl(structured_dir / f"{args.prefix}_tables.jsonl"))

    report = {
        "input_dir": str(structured_dir),
        "counts": {
            "tables": len(tables),
            "metrics": len(metrics),
            "claims": len(claims),
        },
        "checks": {
            "aapl_services_gross_margin_value": _aapl_services_gross_margin_value(metrics),
            "aapl_services_gross_margin_percentage": _aapl_services_gross_margin_percentage(metrics),
            "aapl_gross_margin_periods_present": _aapl_gross_margin_periods_present(metrics),
            "aapl_total_gross_margin_has_no_segment": _aapl_total_gross_margin_has_no_segment(metrics),
            "snow_rpo_metrics_present": _snow_rpo_metrics_present(metrics),
            "snow_consumption_claims_present": _snow_consumption_claims_present(claims),
            "nvda_supply_risk_claims_present": _nvda_supply_risk_claims_present(claims),
        },
    }
    report["passed"] = all(check["passed"] for check in report["checks"].values())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc


def _aapl_services_gross_margin_value(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    matches = [
        metric
        for metric in metrics
        if metric.get("ticker") == "AAPL"
        and metric.get("metric_name") == "Gross margin"
        and metric.get("segment") == "services"
        and metric.get("period") == "2024"
        and metric.get("unit") == "usd_millions"
        and _near(metric.get("value"), 71050.0)
    ]
    return _check(matches, "AAPL 2024 Services gross margin should be 71,050 USD millions.")


def _aapl_services_gross_margin_percentage(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    matches = [
        metric
        for metric in metrics
        if metric.get("ticker") == "AAPL"
        and metric.get("metric_name") == "Gross margin percentage"
        and metric.get("segment") == "services"
        and metric.get("period") == "2024"
        and metric.get("unit") == "percent"
        and _near(metric.get("value"), 73.9)
    ]
    return _check(matches, "AAPL 2024 Services gross margin percentage should be 73.9%.")


def _aapl_gross_margin_periods_present(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        metric
        for metric in metrics
        if metric.get("ticker") == "AAPL"
        and metric.get("source_evidence_id") == "AAPL_2024_10K_ITEM7_BLOCK_0003_CHUNK_0001"
        and "gross margin" in str(metric.get("metric_name", "")).lower()
    ]
    missing = [metric for metric in candidates if metric.get("period") is None]
    return {
        "passed": not missing and bool(candidates),
        "message": "AAPL 2024 gross-margin rows should retain period labels.",
        "candidate_count": len(candidates),
        "missing_count": len(missing),
        "sample_object_ids": [metric.get("object_id") for metric in candidates[:5]],
    }


def _aapl_total_gross_margin_has_no_segment(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        metric
        for metric in metrics
        if metric.get("ticker") == "AAPL"
        and metric.get("source_evidence_id") == "AAPL_2024_10K_ITEM7_BLOCK_0003_CHUNK_0001"
        and str(metric.get("row_label", "")).lower().startswith("total gross margin")
    ]
    wrong = [metric for metric in candidates if metric.get("segment")]
    return {
        "passed": not wrong and bool(candidates),
        "message": "AAPL total gross-margin rows should not inherit Products/Services as segment.",
        "candidate_count": len(candidates),
        "wrong_count": len(wrong),
        "sample_object_ids": [metric.get("object_id") for metric in candidates[:5]],
    }


def _snow_rpo_metrics_present(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    matches = [
        metric
        for metric in metrics
        if metric.get("ticker") == "SNOW"
        and "remaining performance obligations" in str(metric.get("metric_name", "")).lower()
    ]
    required = [
        metric
        for metric in matches
        if metric.get("period") == "2024"
        and metric.get("unit") == "usd_millions"
        and _near(metric.get("value"), 5174.7)
    ]
    return {
        "passed": bool(required) and len(matches) >= 9,
        "message": "Snowflake RPO metrics should include table and sentence evidence.",
        "match_count": len(matches),
        "required_count": len(required),
        "sample_object_ids": [metric.get("object_id") for metric in matches[:5]],
    }


def _snow_consumption_claims_present(claims: list[dict[str, Any]]) -> dict[str, Any]:
    terms = ("remaining performance obligations", "consumption-based", "consumption patterns", "customer consumption")
    matches = [
        claim
        for claim in claims
        if claim.get("ticker") == "SNOW"
        and any(_keyword_in_text(term, str(claim.get("claim_text", "")).lower()) for term in terms)
    ]
    return _check(matches, "Snowflake consumption and RPO claims should be captured.")


def _nvda_supply_risk_claims_present(claims: list[dict[str, Any]]) -> dict[str, Any]:
    terms = ("supply", "demand", "customer", "inventory", "manufacturing", "dependency", "depend")
    matches = [
        claim
        for claim in claims
        if claim.get("ticker") == "NVDA"
        and claim.get("claim_type") == "risk"
        and any(_keyword_in_text(term, str(claim.get("claim_text", "")).lower()) for term in terms)
    ]
    return _check(matches, "NVIDIA supply/demand/manufacturing risk claims should be captured.")


def _check(matches: list[dict[str, Any]], message: str) -> dict[str, Any]:
    return {
        "passed": bool(matches),
        "message": message,
        "match_count": len(matches),
        "sample_object_ids": [match.get("object_id") for match in matches[:5]],
    }


def _near(actual: Any, expected: float, tolerance: float = 1e-6) -> bool:
    try:
        return abs(float(actual) - expected) <= tolerance
    except (TypeError, ValueError):
        return False


def _keyword_in_text(keyword: str, lower_text: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])"
    return bool(re.search(pattern, lower_text))


if __name__ == "__main__":
    main()
