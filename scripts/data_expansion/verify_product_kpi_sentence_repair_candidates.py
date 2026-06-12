from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]

SUMMARY_SCHEMA_VERSION = "fin_agent_product_kpi_sentence_verifier_summary_v0.1"
REJECTION_SCHEMA_VERSION = "fin_agent_product_kpi_sentence_verifier_rejection_v0.1"
VERIFIER_GATE_VERSION = "strict_local_product_revenue_sentence_verifier_v0_1"

DEFAULT_BASE_FACTS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_with_quality_operating_repair_v0_1.jsonl"
)
DEFAULT_REPAIR_FACTS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_targeted_repair_strict_sentence_v0_1.jsonl"
)
DEFAULT_REVENUE_REJECTIONS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_monotonic_repair_rejections_v0_4.jsonl"
)
DEFAULT_OUTPUT_DIR = Path("Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1")
DEFAULT_COMBINED_FACTS_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_kpi_facts_parser_verified_final_public_repair_v0_1.jsonl"
DEFAULT_PROMOTED_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_kpi_sentence_repair_promoted_v0_1.jsonl"
DEFAULT_REJECTIONS_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_kpi_sentence_repair_rejections_v0_1.jsonl"
DEFAULT_SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_kpi_sentence_repair_summary_v0_1.json"
DEFAULT_REPORT_OUTPUT = Path(
    "Z:/FIN_Insight_Agent/docs/internal/vnext_20260610/product_kpi_sentence_repair_v0_1_execution.zh-CN.md"
)

REVENUE_WORD_RE = re.compile(r"\b(?:revenue|revenues|sales|net sales|product sales)\b", re.IGNORECASE)
FORBIDDEN_SENTENCE_RE = re.compile(
    r"("
    r"increase|decrease|growth|grew|decline|declined|driven|attributable|contribution|contributed|"
    r"compared|offset|foreign currency|interest expense|tax|valuation allowance|gross margin|"
    r"operating income|operating profit|expense|expenses|losses?|gains?|volume growth|price|"
    r"acquisition|acquired|divestiture|impairment"
    r")",
    re.IGNORECASE,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify sentence-derived product revenue repair candidates with a strict local relation gate.")
    parser.add_argument("--base-facts", type=Path, default=DEFAULT_BASE_FACTS)
    parser.add_argument("--repair-facts", type=Path, default=DEFAULT_REPAIR_FACTS)
    parser.add_argument("--revenue-rejections", type=Path, default=DEFAULT_REVENUE_REJECTIONS)
    parser.add_argument("--combined-facts-output", type=Path, default=DEFAULT_COMBINED_FACTS_OUTPUT)
    parser.add_argument("--promoted-output", type=Path, default=DEFAULT_PROMOTED_OUTPUT)
    parser.add_argument("--rejections-output", type=Path, default=DEFAULT_REJECTIONS_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).isoformat()
    base_rows = list(_iter_jsonl(_resolve(args.base_facts)))
    repair_rows = list(_iter_jsonl(_resolve(args.repair_facts)))
    revenue_rejection_rows = list(_iter_jsonl(_resolve(args.revenue_rejections)))
    combined_rows, promoted_rows, rejection_rows, summary = verify_sentence_candidates(
        base_rows=base_rows,
        repair_rows=repair_rows,
        revenue_rejection_rows=revenue_rejection_rows,
        generated_at=generated_at,
        paths={
            "base_facts": _repo_path(_resolve(args.base_facts)),
            "repair_facts": _repo_path(_resolve(args.repair_facts)),
            "revenue_rejections": _repo_path(_resolve(args.revenue_rejections)),
            "combined_facts": _repo_path(_resolve(args.combined_facts_output)),
            "promoted": _repo_path(_resolve(args.promoted_output)),
            "rejections": _repo_path(_resolve(args.rejections_output)),
            "summary": _repo_path(_resolve(args.summary_output)),
            "report": _repo_path(_resolve(args.report_output)),
        },
    )
    _write_jsonl(_resolve(args.combined_facts_output), combined_rows)
    _write_jsonl(_resolve(args.promoted_output), promoted_rows)
    _write_jsonl(_resolve(args.rejections_output), rejection_rows)
    _write_json(_resolve(args.summary_output), summary)
    report_output = _resolve(args.report_output)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def verify_sentence_candidates(
    *,
    base_rows: list[dict[str, Any]],
    repair_rows: list[dict[str, Any]],
    revenue_rejection_rows: list[dict[str, Any]],
    generated_at: str,
    paths: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    sentence_ids = {
        str(row.get("fact_id") or "")
        for row in revenue_rejection_rows
        if row.get("rejection_reason") == "not_structured_table_metric"
    }
    base_claims = {claim_key(row) for row in base_rows}
    candidate_rows = [row for row in repair_rows if str(row.get("fact_id") or "") in sentence_ids]
    pre_reasons = {id(row): sentence_rejection_reason(row) for row in candidate_rows}
    pre_promotable = [row for row in candidate_rows if pre_reasons[id(row)] == "pre_promote_sentence_revenue"]

    rows_by_claim: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in pre_promotable:
        rows_by_claim[claim_key(row)].append(row)
    claim_rejections: dict[tuple[Any, ...], str] = {}
    selected_fact_ids: set[str] = set()
    for key, rows in rows_by_claim.items():
        if key in base_claims:
            claim_rejections[key] = "claim_already_covered_by_accepted_fact_layer"
            continue
        values = {normalized_value(row.get("value")) for row in rows}
        if len(values) > 1:
            claim_rejections[key] = "conflicting_sentence_values_for_same_claim"
            continue
        selected_fact_ids.add(str(rows[0].get("fact_id") or ""))

    promoted_rows: list[dict[str, Any]] = []
    rejection_rows: list[dict[str, Any]] = []
    for row in candidate_rows:
        reason = pre_reasons[id(row)]
        key = claim_key(row)
        if reason == "pre_promote_sentence_revenue" and str(row.get("fact_id") or "") in selected_fact_ids:
            promoted_rows.append(promoted_sentence_row(row, generated_at))
        else:
            rejection_rows.append(rejection_row(row, claim_rejections.get(key, reason), generated_at))

    combined_rows = [*base_rows, *promoted_rows]
    summary = build_summary(
        base_rows=base_rows,
        candidate_rows=candidate_rows,
        promoted_rows=promoted_rows,
        rejection_rows=rejection_rows,
        generated_at=generated_at,
        paths=paths or {},
    )
    return combined_rows, promoted_rows, rejection_rows, summary


def sentence_rejection_reason(row: dict[str, Any]) -> str:
    if row.get("source_id") != "company_product_kpi_facts_structured_sentence_metric_parser":
        return "not_sentence_metric_parser_candidate"
    if row.get("metric_family") != "product_revenue":
        return "not_product_revenue_sentence"
    if row.get("unit") != "USD" or row.get("unit_category") != "currency":
        return "sentence_non_currency_or_percentage_not_level_revenue"
    if normalized_value(row.get("value")) <= 0:
        return "sentence_non_positive_value"
    citation = str(row.get("citation_span") or "")
    local = local_sentence_context(citation)
    product = str(row.get("product_or_segment") or "")
    raw_value = str(row.get("raw_value_text") or "")
    if not product or product.lower() not in local.lower():
        return "local_product_value_relation_not_verified"
    if raw_value and raw_value.lower() not in local.lower():
        return "local_value_not_in_verified_sentence"
    if not REVENUE_WORD_RE.search(local):
        return "local_revenue_metric_word_missing"
    if FORBIDDEN_SENTENCE_RE.search(local):
        return "change_or_financial_context_not_level_revenue_fact"
    return "pre_promote_sentence_revenue"


def local_sentence_context(citation: str) -> str:
    row_match = re.search(r"row=([^|]+)\|", citation)
    value_match = re.search(r"value=([^|]+)\|", citation)
    parts = []
    if row_match:
        parts.append(row_match.group(1).strip())
    if value_match:
        parts.append(value_match.group(1).strip())
    source_match = re.search(r"source_context=(.*)$", citation, re.IGNORECASE | re.DOTALL)
    if source_match:
        source = source_match.group(1)
        sentences = re.split(r"(?<=[.!?])\s+", source)
        parts.extend(sentences[:2])
    return " ".join(parts)[:600]


def promoted_sentence_row(row: dict[str, Any], generated_at: str) -> dict[str, Any]:
    promoted = dict(row)
    promoted["fact_id"] = stable_id("PRODUCTKPISENTENCEREPAIR", *claim_key(row), row.get("value"))
    promoted["repair_promotion_status"] = "sentence_repair_promoted"
    promoted["repair_promotion_gate"] = VERIFIER_GATE_VERSION
    promoted["repair_promotion_generated_at"] = generated_at
    promoted["repair_claim_scope"] = "company_disclosed_product_or_segment_revenue"
    promoted["runtime_use_boundary"] = (
        "May support company-disclosed product or segment revenue from a local verified sentence; "
        "does not prove market share, unit demand, channel inventory, or undisclosed product economics."
    )
    return promoted


def rejection_row(row: dict[str, Any], reason: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": REJECTION_SCHEMA_VERSION,
        "rejection_id": stable_id("PRODUCTKPISENTENCEREJECT", row.get("fact_id"), reason),
        "generated_at": generated_at,
        "rejection_reason": reason,
        "ticker": row.get("ticker"),
        "company": row.get("company"),
        "fact_id": row.get("fact_id"),
        "metric_family": row.get("metric_family"),
        "product_or_segment": row.get("product_or_segment"),
        "period": row.get("period"),
        "unit": row.get("unit"),
        "unit_category": row.get("unit_category"),
        "value": row.get("value"),
        "raw_value_text": row.get("raw_value_text"),
        "source_document_id": row.get("source_document_id"),
        "source_url": row.get("source_url"),
    }


def build_summary(
    *,
    base_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    promoted_rows: list[dict[str, Any]],
    rejection_rows: list[dict[str, Any]],
    generated_at: str,
    paths: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "pass",
        "generated_at": generated_at,
        "base_fact_count": len(base_rows),
        "base_ticker_count": count_tickers(base_rows),
        "sentence_candidate_count": len(candidate_rows),
        "sentence_candidate_ticker_count": count_tickers(candidate_rows),
        "promoted_fact_count": len(promoted_rows),
        "promoted_ticker_count": count_tickers(promoted_rows),
        "combined_fact_count": len(base_rows) + len(promoted_rows),
        "combined_ticker_count": count_tickers([*base_rows, *promoted_rows]),
        "promoted_ticker_counts": dict(sorted(Counter(str(row.get("ticker") or "") for row in promoted_rows).items())),
        "rejection_count": len(rejection_rows),
        "rejection_reason_counts": dict(
            sorted(Counter(str(row.get("rejection_reason") or "") for row in rejection_rows).items())
        ),
        "outputs": paths,
        "promotion_boundary": [
            "Sentence repair is intentionally stricter than table repair.",
            "A candidate must show product, value, and revenue relation in local sentence context.",
            "Growth attribution, volume, price, currency, expense, tax, interest, acquisition, and contribution contexts are rejected.",
            "Rejected sentence rows remain review-only and must not be used as runtime facts.",
        ],
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Product KPI Sentence Repair v0.1 执行报告",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- Sentence candidates：`{summary['sentence_candidate_count']}` / tickers `({summary['sentence_candidate_ticker_count']})`",
        f"- Promoted facts：`{summary['promoted_fact_count']}` / tickers `({summary['promoted_ticker_count']})`",
        f"- Combined facts：`{summary['combined_fact_count']}` / tickers `({summary['combined_ticker_count']})`",
        f"- Rejection reasons：`{json.dumps(summary['rejection_reason_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Boundary",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["promotion_boundary"])
    return "\n".join(lines) + "\n"


def claim_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("ticker"),
        row.get("product_node_id"),
        row.get("metric_family"),
        row.get("period"),
        row.get("unit"),
    )


def normalized_value(value: Any) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def count_tickers(rows: Iterable[dict[str, Any]]) -> int:
    return len({str(row.get("ticker") or "") for row in rows if row.get("ticker")})


def stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha1("||".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:14]
    return f"{prefix}::{digest}"


def _resolve(path: Path) -> Path:
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
