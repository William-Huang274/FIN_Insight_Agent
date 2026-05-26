from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build benchmark exact-value ledger from reviewed gold facts.")
    parser.add_argument(
        "--reviewed-facts-dir",
        default="eval/sec_cases/reviewed_gold_facts",
    )
    parser.add_argument(
        "--approval-path",
        default="reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json",
    )
    parser.add_argument(
        "--output-path",
        default="reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reviewed_facts_dir = REPO_ROOT / args.reviewed_facts_dir
    approval = _read_json(REPO_ROOT / args.approval_path)
    approved_case_ids = [str(item) for item in approval.get("gate", {}).get("approved_case_ids") or []]
    rows: list[dict[str, Any]] = []

    for case_id in approved_case_ids:
        facts_path = reviewed_facts_dir / f"{case_id}.json"
        if not facts_path.exists():
            continue
        payload = _read_json(facts_path)
        for fact in payload.get("facts") or []:
            if str(fact.get("review_status") or "") != "reviewed_keep":
                continue
            rows.append(
                {
                    "metric_id": _base_metric_id(case_id, fact),
                    "case_id": case_id,
                    "ticker": fact.get("ticker"),
                    "fiscal_year": fact.get("fiscal_year"),
                    "period": fact.get("period"),
                    "metric_family": fact.get("metric_family"),
                    "metric_role": fact.get("metric_role"),
                    "metric_name": fact.get("metric_name"),
                    "raw_value_text": str(fact.get("raw_value") or ""),
                    "display_value_zh": _display_value_zh(fact),
                    "value": fact.get("value"),
                    "unit": fact.get("unit"),
                    "object_id": fact.get("object_id"),
                    "source_evidence_id": fact.get("source_evidence_id"),
                    "section": fact.get("section"),
                    "row_label": fact.get("row_label"),
                    "column_label": fact.get("column_label"),
                }
            )
    _dedupe_metric_ids(rows)

    output = {
        "schema_version": "sec_benchmark_exact_value_ledger_v0.1",
        "source": "reviewed_gold_facts",
        "approval_path": str((REPO_ROOT / args.approval_path).resolve()),
        "approved_case_ids": approved_case_ids,
        "row_count": len(rows),
        "rows": rows,
    }
    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "approved_case_count": len(approved_case_ids),
                "row_count": len(rows),
                "output_path": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _base_metric_id(case_id: str, fact: dict[str, Any]) -> str:
    ticker = str(fact.get("ticker") or "UNK").upper()
    year = str(fact.get("period") or fact.get("fiscal_year") or "UNK")
    family = str(fact.get("metric_family") or "metric")
    role = str(fact.get("metric_role") or "role")
    return f"{case_id}::{ticker}::{year}::{family}::{role}"


def _dedupe_metric_ids(rows: list[dict[str, Any]]) -> None:
    counts: dict[str, int] = {}
    for row in rows:
        metric_id = str(row.get("metric_id") or "")
        counts[metric_id] = counts.get(metric_id, 0) + 1
    used: set[str] = set()
    duplicate_index: dict[str, int] = {}
    for row in rows:
        base = str(row.get("metric_id") or "")
        if counts.get(base, 0) <= 1 and base not in used:
            used.add(base)
            continue
        duplicate_index[base] = duplicate_index.get(base, 0) + 1
        suffix_source = (
            row.get("row_label")
            or row.get("segment")
            or row.get("metric_name")
            or f"row_{duplicate_index[base]}"
        )
        candidate = f"{base}::row_{_slug_part(str(suffix_source))}"
        if candidate in used:
            candidate = f"{candidate}_{duplicate_index[base]}"
        row["metric_id"] = candidate
        used.add(candidate)


def _slug_part(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "unknown"


def _display_value_zh(fact: dict[str, Any]) -> str:
    raw = str(fact.get("raw_value") or "").strip()
    unit = str(fact.get("unit") or "")
    if not raw:
        return ""
    if unit == "usd_millions":
        if "million" in raw.lower():
            return _display_currency_phrase(raw, "百万美元")
        return f"{raw}（百万美元）"
    if unit == "usd_billions":
        if "billion" in raw.lower():
            return _display_currency_phrase(raw, "十亿美元")
        return f"{raw}（十亿美元）"
    if unit == "percent":
        return raw if raw.endswith("%") else f"{raw}%"
    return raw


def _display_currency_phrase(raw: str, suffix: str) -> str:
    text = raw.strip()
    text = text.replace("$", "").replace("USD", "").replace("usd", "").strip()
    for token in ("billion", "Billion", "million", "Million"):
        text = text.replace(token, "")
    return f"{text.strip()}（{suffix}）"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
