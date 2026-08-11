from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "fin_agent_product_evidence_strategy_artifacts_v0.1"
TAXONOMY_SCHEMA_VERSION = "fin_agent_company_product_taxonomy_candidate_v0.1"
METRIC_SCHEMA_VERSION = "fin_agent_company_product_metric_candidate_balanced_v0.1"
EXTERNAL_SOURCE_SCHEMA_VERSION = "fin_agent_product_external_validation_source_plan_v0.1"

DEFAULT_STRATEGY_CONFIG = REPO_ROOT / "configs" / "data_sources" / "product_evidence_strategy_v0_1.yaml"
DEFAULT_CHUNK_INPUTS = [
    REPO_ROOT / "data" / "staging" / "sec_tier1_sp500_annual" / "chunks" / "tier1_sp500_us_annual_10k_chunks_fy2023_2025_v0_1.jsonl",
    REPO_ROOT / "data" / "staging" / "sec_tier2_supply_chain_annual" / "chunks" / "tier2_supply_chain_sec_annual_chunks_fy2023_2025_v0_1.jsonl",
]
DEFAULT_TAXONOMY_OUTPUT = REPO_ROOT / "data" / "manifests" / "company_product_taxonomy_candidates_v0_1.jsonl"
DEFAULT_METRIC_OUTPUT = REPO_ROOT / "data" / "manifests" / "company_product_metric_candidates_balanced_v0_1.jsonl"
DEFAULT_EXTERNAL_SOURCE_PLAN_OUTPUT = REPO_ROOT / "data" / "manifests" / "product_external_validation_source_plan_v0_1.jsonl"
DEFAULT_SUMMARY_OUTPUT = REPO_ROOT / "data" / "manifests" / "company_product_evidence_strategy_summary_v0_1.json"
DEFAULT_REPORT_OUTPUT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "product_evidence_strategy_execution.zh-CN.md"

PRODUCT_TAXONOMY_RULES = [
    ("reportable_segment_sentence", "reportable_segment", re.compile(r"\b(?:reportable|business|operating)\s+segments?\s+(?:are|include|comprised of|consist of|consists of)\s+(.{20,360}?)[.;]\s", re.I | re.S)),
    ("business_segments_sentence", "business_line", re.compile(r"\b(?:businesses|business units|business groups)\s+(?:are|include|comprised of|consist of|consists of)\s+(.{20,360}?)[.;]\s", re.I | re.S)),
    ("products_include_sentence", "product_or_service_family", re.compile(r"\b(?:products|solutions|offerings|services)\s+(?:include|includes|included|consist of|consists of|comprised of)\s+(.{20,360}?)[.;]\s", re.I | re.S)),
    ("we_offer_sentence", "product_or_service_family", re.compile(r"\bwe\s+(?:offer|provide|sell|develop|manufacture|market)\s+(.{20,300}?)[.;]\s", re.I | re.S)),
]

HEADING_KEYWORDS = re.compile(
    r"\b(product|products|service|services|solution|solutions|segment|segments|business|platform|software|applications?|technolog(?:y|ies)|customers?|markets?)\b",
    re.I,
)

METRIC_PATTERNS = {
    "product_revenue": [
        r"\bproduct revenue\b",
        r"\bnet sales\b",
        r"\brevenue by product\b",
        r"\brevenue by segment\b",
        r"\bfranchise revenue\b",
        r"\bsegment revenue\b",
    ],
    "unit_sales_or_deliveries": [r"\bunit sales\b", r"\bunits sold\b", r"\bdeliveries\b", r"\bdelivered\b"],
    "shipments": [r"\bshipments\b", r"\bshipped\b"],
    "backlog_or_orders": [r"\bbacklog\b", r"\border(s)?\b", r"\bbookings\b", r"\brpo\b", r"\bremaining performance obligations\b"],
    "subscribers_or_arpu": [r"\bsubscribers\b", r"\bpaid subscribers\b", r"\barpu\b", r"\baverage revenue per user\b"],
    "same_store_sales": [r"\bsame-store sales\b", r"\bcomparable sales\b", r"\bcomparable store sales\b"],
    "production_or_throughput": [r"\bproduction\b", r"\bthroughput\b", r"\bproduced\b"],
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build filings-first product evidence strategy artifacts.")
    parser.add_argument("--strategy-config", type=Path, default=DEFAULT_STRATEGY_CONFIG)
    parser.add_argument("--chunk-input", type=Path, action="append", default=[])
    parser.add_argument("--taxonomy-output", type=Path, default=DEFAULT_TAXONOMY_OUTPUT)
    parser.add_argument("--metric-output", type=Path, default=DEFAULT_METRIC_OUTPUT)
    parser.add_argument("--external-source-plan-output", type=Path, default=DEFAULT_EXTERNAL_SOURCE_PLAN_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--max-taxonomy-per-ticker-year", type=int, default=8)
    parser.add_argument("--max-metric-per-ticker-family-year", type=int, default=1)
    parser.add_argument("--max-snippet-chars", type=int, default=700)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).isoformat()
    strategy_config_path = _resolve(args.strategy_config)
    strategy = _load_yaml(strategy_config_path)
    strategy["_config_path"] = str(strategy_config_path)
    chunk_inputs = [_resolve(path) for path in (args.chunk_input or DEFAULT_CHUNK_INPUTS)]
    rows = iter_chunk_rows(chunk_inputs)
    taxonomy_rows, metric_rows, scan_stats = extract_product_evidence_candidates(
        rows,
        max_taxonomy_per_ticker_year=max(args.max_taxonomy_per_ticker_year, 0),
        max_metric_per_ticker_family_year=max(args.max_metric_per_ticker_family_year, 0),
        max_snippet_chars=max(args.max_snippet_chars, 120),
        generated_at=generated_at,
    )
    external_rows = build_external_source_plan(strategy, generated_at=generated_at)
    taxonomy_output = _resolve(args.taxonomy_output)
    metric_output = _resolve(args.metric_output)
    external_output = _resolve(args.external_source_plan_output)
    summary_output = _resolve(args.summary_output)
    report_output = _resolve(args.report_output)
    _write_jsonl(taxonomy_output, taxonomy_rows)
    _write_jsonl(metric_output, metric_rows)
    _write_jsonl(external_output, external_rows)
    summary = build_summary(
        strategy=strategy,
        chunk_inputs=chunk_inputs,
        taxonomy_rows=taxonomy_rows,
        metric_rows=metric_rows,
        external_rows=external_rows,
        scan_stats=scan_stats,
        taxonomy_output=taxonomy_output,
        metric_output=metric_output,
        external_output=external_output,
        summary_output=summary_output,
        report_output=report_output,
        generated_at=generated_at,
    )
    _write_json(summary_output, summary)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def iter_chunk_rows(paths: Iterable[Path]) -> Iterable[dict[str, Any]]:
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if isinstance(row, dict):
                    yield row


def extract_product_evidence_candidates(
    chunk_rows: Iterable[dict[str, Any]],
    *,
    max_taxonomy_per_ticker_year: int,
    max_metric_per_ticker_family_year: int,
    max_snippet_chars: int,
    generated_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    compiled_metric_patterns = {
        family: [re.compile(pattern, flags=re.IGNORECASE) for pattern in patterns] for family, patterns in METRIC_PATTERNS.items()
    }
    taxonomy_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    taxonomy_counts: Counter[tuple[str, int]] = Counter()
    metric_counts: Counter[tuple[str, int, str]] = Counter()
    seen_taxonomy_ids: set[str] = set()
    seen_metric_ids: set[str] = set()
    scanned_chunks = 0
    scanned_tickers: set[str] = set()
    for row in chunk_rows:
        scanned_chunks += 1
        ticker = str(row.get("ticker") or "").strip()
        fiscal_year = _safe_int(row.get("fiscal_year")) or 0
        if not ticker or not fiscal_year:
            continue
        scanned_tickers.add(ticker)
        text = _normalize_text(str(row.get("text") or ""))
        if not text:
            continue
        section = str(row.get("section") or "")
        if _is_taxonomy_section(section, row) and taxonomy_counts[(ticker, fiscal_year)] < max_taxonomy_per_ticker_year:
            for candidate in _taxonomy_candidates_from_row(row, text, max_snippet_chars=max_snippet_chars):
                if taxonomy_counts[(ticker, fiscal_year)] >= max_taxonomy_per_ticker_year:
                    break
                candidate_id = candidate["candidate_id"]
                if candidate_id in seen_taxonomy_ids:
                    continue
                taxonomy_rows.append({**candidate, "generated_at": generated_at})
                seen_taxonomy_ids.add(candidate_id)
                taxonomy_counts[(ticker, fiscal_year)] += 1
        for family, patterns in compiled_metric_patterns.items():
            key = (ticker, fiscal_year, family)
            if metric_counts[key] >= max_metric_per_ticker_family_year:
                continue
            matched = next((pattern.pattern for pattern in patterns if pattern.search(text)), "")
            if not matched:
                continue
            metric_row = _metric_candidate_from_row(
                row,
                metric_family=family,
                match_pattern=matched,
                max_snippet_chars=max_snippet_chars,
                generated_at=generated_at,
            )
            if metric_row["candidate_id"] in seen_metric_ids:
                continue
            metric_rows.append(metric_row)
            seen_metric_ids.add(metric_row["candidate_id"])
            metric_counts[key] += 1
            break
    scan_stats = {
        "scanned_chunk_count": scanned_chunks,
        "scanned_ticker_count": len(scanned_tickers),
    }
    return taxonomy_rows, metric_rows, scan_stats


def _taxonomy_candidates_from_row(row: dict[str, Any], text: str, *, max_snippet_chars: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    heading = _clean_label(str(row.get("block_heading") or ""))
    if heading and HEADING_KEYWORDS.search(heading) and not _is_boilerplate_label(heading):
        candidates.append(
            _taxonomy_candidate(
                row,
                label=heading,
                taxonomy_type=_taxonomy_type_from_text(heading),
                extraction_rule="block_heading_product_taxonomy",
                snippet=_snippet_around(text, heading, max_snippet_chars=max_snippet_chars),
                confidence_score=0.72,
            )
        )
    for rule_id, taxonomy_type, pattern in PRODUCT_TAXONOMY_RULES:
        for match in pattern.finditer(f"{text} "):
            phrase = _clean_phrase(match.group(1))
            for label in _split_product_phrase(phrase):
                if not label:
                    continue
                candidates.append(
                    _taxonomy_candidate(
                        row,
                        label=label,
                        taxonomy_type=taxonomy_type,
                        extraction_rule=rule_id,
                        snippet=_snippet_around(text, match.group(0), max_snippet_chars=max_snippet_chars),
                        confidence_score=0.64,
                    )
                )
    for line in text.splitlines()[:80]:
        label = _clean_label(line)
        if _looks_like_product_heading(label):
            candidates.append(
                _taxonomy_candidate(
                    row,
                    label=label,
                    taxonomy_type=_taxonomy_type_from_text(label),
                    extraction_rule="inline_product_heading",
                    snippet=_snippet_around(text, line, max_snippet_chars=max_snippet_chars),
                    confidence_score=0.58,
                )
            )
    deduped: list[dict[str, Any]] = []
    seen_labels: set[tuple[str, str]] = set()
    for candidate in candidates:
        key = (candidate["taxonomy_label"].lower(), candidate["taxonomy_type"])
        if key in seen_labels:
            continue
        seen_labels.add(key)
        deduped.append(candidate)
    return deduped


def _taxonomy_candidate(
    row: dict[str, Any],
    *,
    label: str,
    taxonomy_type: str,
    extraction_rule: str,
    snippet: str,
    confidence_score: float,
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "")
    fiscal_year = _safe_int(row.get("fiscal_year"))
    chunk_id = str(row.get("chunk_id") or "")
    digest = hashlib.sha1("||".join([ticker, str(fiscal_year), taxonomy_type, label, chunk_id]).encode("utf-8")).hexdigest()[:14]
    return {
        "schema_version": TAXONOMY_SCHEMA_VERSION,
        "candidate_id": f"PRODUCTTAX::{ticker}::{fiscal_year}::{digest}",
        "source_id": "company_product_taxonomy_candidates",
        "signal_role": "company_disclosed",
        "signal_strength": "S5_primary_authority_candidate",
        "ticker": ticker,
        "company": row.get("company"),
        "fiscal_year": fiscal_year,
        "form_type": row.get("form_type") or row.get("source_type"),
        "period_end": row.get("period_end"),
        "section": row.get("section"),
        "chunk_id": chunk_id,
        "source_url": row.get("source_url"),
        "taxonomy_label": label,
        "taxonomy_type": taxonomy_type,
        "extraction_rule": extraction_rule,
        "confidence_score": confidence_score,
        "promotion_status": "taxonomy_candidate_needs_review",
        "runtime_use_boundary": "May support product taxonomy after review; cannot prove product revenue, market share, demand, or margin.",
        "evidence_snippet": snippet,
    }


def _metric_candidate_from_row(
    row: dict[str, Any],
    *,
    metric_family: str,
    match_pattern: str,
    max_snippet_chars: int,
    generated_at: str,
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "")
    fiscal_year = _safe_int(row.get("fiscal_year"))
    chunk_id = str(row.get("chunk_id") or "")
    text = _normalize_text(str(row.get("text") or ""))
    snippet = _snippet_for_pattern(text, match_pattern, max_snippet_chars=max_snippet_chars)
    digest = hashlib.sha1("||".join([ticker, str(fiscal_year), metric_family, chunk_id, match_pattern]).encode("utf-8")).hexdigest()[:14]
    return {
        "schema_version": METRIC_SCHEMA_VERSION,
        "candidate_id": f"PRODUCTKPI::{ticker}::{fiscal_year}::{digest}",
        "source_id": "company_product_metric_candidates_balanced",
        "signal_role": "company_disclosed",
        "signal_strength": "S5_primary_authority_candidate",
        "generated_at": generated_at,
        "metric_family": metric_family,
        "match_pattern": match_pattern,
        "ticker": ticker,
        "company": row.get("company"),
        "fiscal_year": fiscal_year,
        "form_type": row.get("form_type") or row.get("source_type"),
        "period_end": row.get("period_end"),
        "section": row.get("section"),
        "chunk_id": chunk_id,
        "source_url": row.get("source_url"),
        "candidate_status": "needs_value_unit_period_product_parser",
        "runtime_use_boundary": "Keyword evidence only; cannot be used as a product KPI fact until value/unit/period/product/citation parser verifies it.",
        "snippet": snippet,
    }


def build_external_source_plan(strategy: dict[str, Any], *, generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_plan = strategy.get("industry_source_plan") or {}
    for industry_key, industry in source_plan.items():
        if not isinstance(industry, dict):
            continue
        for role in ("company_disclosed_sources", "official_product_surface_sources", "public_proxy_sources", "commercial_market_tracker_sources"):
            signal_role = role.replace("_sources", "")
            for source_name in industry.get(role) or []:
                rows.append(
                    {
                        "schema_version": EXTERNAL_SOURCE_SCHEMA_VERSION,
                        "generated_at": generated_at,
                        "industry_key": industry_key,
                        "source_name": str(source_name),
                        "signal_role": signal_role,
                        "source_strength": _role_strength(signal_role),
                        "current_policy_status": "blocked_no_commercial_policy" if signal_role == "commercial_market_tracker" else "candidate_for_mapping_or_parser_gate",
                        "allowed_use": _role_allowed_use(signal_role),
                        "runtime_gate": _role_runtime_gate(signal_role),
                        "non_degradation_guard": "Do not use weaker roles to replace company-disclosed facts or commercial tracker measurements.",
                    }
                )
    return rows


def build_summary(
    *,
    strategy: dict[str, Any],
    chunk_inputs: list[Path],
    taxonomy_rows: list[dict[str, Any]],
    metric_rows: list[dict[str, Any]],
    external_rows: list[dict[str, Any]],
    scan_stats: dict[str, Any],
    taxonomy_output: Path,
    metric_output: Path,
    external_output: Path,
    summary_output: Path,
    report_output: Path,
    generated_at: str,
) -> dict[str, Any]:
    taxonomy_tickers = {str(row.get("ticker")) for row in taxonomy_rows if row.get("ticker")}
    metric_tickers = {str(row.get("ticker")) for row in metric_rows if row.get("ticker")}
    scanned_ticker_count = int(scan_stats.get("scanned_ticker_count") or 0)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "generated_at": generated_at,
        "strategy": {
            "research_target": (strategy.get("direction_lock") or {}).get("research_target"),
            "non_degradation_rule": (strategy.get("direction_lock") or {}).get("non_degradation_rule"),
            "anchor": (strategy.get("source_architecture") or {}).get("anchor"),
            "increment": (strategy.get("source_architecture") or {}).get("increment"),
        },
        "inputs": {
            "strategy_config": _repo_path(_resolve(Path(str((strategy.get("_config_path") or DEFAULT_STRATEGY_CONFIG))))),
            "chunk_inputs": [_repo_path(path) for path in chunk_inputs],
        },
        "outputs": {
            "taxonomy_candidates": _repo_path(taxonomy_output),
            "metric_candidates": _repo_path(metric_output),
            "external_source_plan": _repo_path(external_output),
            "summary": _repo_path(summary_output),
            "report": _repo_path(report_output),
        },
        "scan_stats": scan_stats,
        "taxonomy_candidate_count": len(taxonomy_rows),
        "taxonomy_candidate_ticker_count": len(taxonomy_tickers),
        "taxonomy_candidate_ticker_coverage_pct": _pct(len(taxonomy_tickers), scanned_ticker_count),
        "taxonomy_type_counts": dict(sorted(Counter(str(row.get("taxonomy_type") or "") for row in taxonomy_rows).items())),
        "taxonomy_rule_counts": dict(sorted(Counter(str(row.get("extraction_rule") or "") for row in taxonomy_rows).items())),
        "metric_candidate_count": len(metric_rows),
        "metric_candidate_ticker_count": len(metric_tickers),
        "metric_candidate_ticker_coverage_pct": _pct(len(metric_tickers), scanned_ticker_count),
        "metric_family_counts": dict(sorted(Counter(str(row.get("metric_family") or "") for row in metric_rows).items())),
        "external_source_plan_row_count": len(external_rows),
        "external_source_role_counts": dict(sorted(Counter(str(row.get("signal_role") or "") for row in external_rows).items())),
        "commercial_tracker_source_count": sum(1 for row in external_rows if row.get("signal_role") == "commercial_market_tracker"),
        "runtime_promotion_policy": [
            "company_disclosed taxonomy is a candidate until review.",
            "company_disclosed KPI is not a fact until value/unit/period/product/citation parser passes.",
            "official_product_surface and public_proxy are context or directional verification only.",
            "commercial_market_tracker rows remain blocked under current no-commercial policy.",
        ],
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Product Evidence Strategy 执行报告",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- 扫描 ticker：`{summary['scan_stats'].get('scanned_ticker_count')}`",
        f"- 扫描 chunks：`{summary['scan_stats'].get('scanned_chunk_count')}`",
        f"- 产品 taxonomy candidates：`{summary['taxonomy_candidate_count']}`，覆盖 ticker：`{summary['taxonomy_candidate_ticker_count']}` / `{summary['taxonomy_candidate_ticker_coverage_pct']}%`",
        f"- 产品 KPI candidates：`{summary['metric_candidate_count']}`，覆盖 ticker：`{summary['metric_candidate_ticker_count']}` / `{summary['metric_candidate_ticker_coverage_pct']}%`",
        f"- 外部验证 source-plan rows：`{summary['external_source_plan_row_count']}`",
        f"- commercial tracker rows：`{summary['commercial_tracker_source_count']}`，当前策略下全部 blocked",
        "",
        "## 方向锁定",
        "",
        f"- Research target：`{summary['strategy'].get('research_target')}`",
        f"- Non-degradation rule：{summary['strategy'].get('non_degradation_rule')}",
        f"- Anchor：{summary['strategy'].get('anchor')}",
        f"- Increment：{summary['strategy'].get('increment')}",
        "",
        "## 计数",
        "",
        f"- Taxonomy type counts：`{json.dumps(summary['taxonomy_type_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Metric family counts：`{json.dumps(summary['metric_family_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- External source role counts：`{json.dumps(summary['external_source_role_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Runtime 边界",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["runtime_promotion_policy"])
    lines.append("")
    return "\n".join(lines)


def _is_taxonomy_section(section: str, row: dict[str, Any]) -> bool:
    text = " ".join([section, str(row.get("block_heading") or ""), str(row.get("item_code") or "")]).lower()
    return any(token in text for token in ("business", "item 1", "m&a", "management", "segment", "financial statements", "item 7", "item 8"))


def _taxonomy_type_from_text(text: str) -> str:
    lower = text.lower()
    if "segment" in lower:
        return "reportable_segment"
    if any(token in lower for token in ("service", "software", "platform", "solution")):
        return "product_or_service_family"
    if any(token in lower for token in ("customer", "market", "application")):
        return "customer_market_or_application"
    if "business" in lower:
        return "business_line"
    return "product_or_service_family"


def _split_product_phrase(phrase: str) -> list[str]:
    phrase = re.sub(r"\([^)]{0,80}\)", "", phrase)
    phrase = re.sub(r"\b(?:including|such as|primarily|generally)\b.*$", "", phrase, flags=re.I)
    parts: list[str] = []
    for part in re.split(r",|;|\u2022", phrase):
        parts.extend(re.split(r"\s+and\s+(?=(?:[A-Z][A-Za-z]+|[A-Z]{2,}|The\s+|the\s+Agilent|Agilent\s+))", part))
    labels: list[str] = []
    for part in parts:
        label = _clean_label(part)
        label = re.sub(r"^(?:the|our|and|or)\s+", "", label, flags=re.I).strip()
        if 3 <= len(label) <= 120 and not _is_boilerplate_label(label):
            labels.append(label)
    return labels[:8]


def _looks_like_product_heading(label: str) -> bool:
    if not (3 <= len(label) <= 90):
        return False
    if _is_boilerplate_label(label):
        return False
    if label.endswith(".") or len(label.split()) > 9:
        return False
    if HEADING_KEYWORDS.search(label):
        return True
    upper_or_title = sum(1 for token in label.split() if token[:1].isupper() or token.isupper())
    return upper_or_title >= max(1, len(label.split()) // 2) and len(label.split()) <= 6


def _is_boilerplate_label(label: str) -> bool:
    lower = label.lower().strip(":- ")
    if not lower or lower.startswith("[table_") or lower.endswith("[table_end]"):
        return True
    if "|" in lower:
        return True
    blocked = {
        "business",
        "products",
        "services",
        "our products and services",
        "overview",
        "general",
        "company background",
        "our company",
        "additional information",
        "our industry",
        "our strategy",
        "the development of our company",
        "cautionary statement regarding forward-looking statements",
        "risk factors",
        "table of contents",
        "management discussion and analysis",
        "quantitative and qualitative disclosures about market risk",
    }
    if lower in blocked:
        return True
    if bool(re.search(r"\b(item\s+\d|part\s+[ivx]+|page\s+\d)\b", lower)):
        return True
    if bool(re.search(r"^note\s+\d+\b", lower)):
        return True
    if lower in {"respectively", "today", "develop", "commercialize"}:
        return True
    if lower.startswith((
        "in a ",
        "which is ",
        "today were ",
        "and our ",
        "our long-term success",
        "forward-looking",
        "commercialize ",
        "distribute ",
        "directly to ",
        "as well as ",
        "is designed ",
        "most of our products",
        "to our consolidated",
    )):
        return True
    if "depends on our ability" in lower or "long-term success" in lower or "consolidated financial statements" in lower:
        return True
    return False


def _clean_phrase(value: str) -> str:
    return _clean_label(re.sub(r"\s+", " ", value or ""))


def _clean_label(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n:-;,.")
    text = html_unescape(text)
    text = re.sub(r"^(?:and|or)\s+", "", text, flags=re.I).strip()
    return text[:180]


def html_unescape(value: str) -> str:
    return (
        value.replace("&amp;", "&")
        .replace("&nbsp;", " ")
        .replace("&#160;", " ")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"[ \t]+", " ", value.replace("\r\n", "\n").replace("\r", "\n")).strip()


def _snippet_for_pattern(text: str, pattern: str, *, max_snippet_chars: int) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return text[:max_snippet_chars]
    return _window(text, match.start(), match.end(), max_snippet_chars=max_snippet_chars)


def _snippet_around(text: str, needle: str, *, max_snippet_chars: int) -> str:
    index = text.lower().find(str(needle or "").lower()[:80])
    if index < 0:
        return text[:max_snippet_chars]
    return _window(text, index, index + len(str(needle)), max_snippet_chars=max_snippet_chars)


def _window(text: str, start: int, end: int, *, max_snippet_chars: int) -> str:
    padding = max((max_snippet_chars - (end - start)) // 2, 40)
    left = max(0, start - padding)
    right = min(len(text), end + padding)
    snippet = re.sub(r"\s+", " ", text[left:right]).strip()
    if left > 0:
        snippet = "..." + snippet
    if right < len(text):
        snippet += "..."
    return snippet


def _role_strength(signal_role: str) -> str:
    return {
        "company_disclosed": "S5_primary_authority",
        "official_product_surface": "S4_company_authored_context",
        "public_proxy": "S2_to_S1_context_or_lead",
        "commercial_market_tracker": "S3_to_S4_external_market_measurement_blocked",
    }.get(signal_role, "unknown")


def _role_allowed_use(signal_role: str) -> str:
    return {
        "company_disclosed": "product taxonomy and parser-verified company-disclosed product KPI facts",
        "official_product_surface": "product existence, positioning, feature, launch, pricing context only",
        "public_proxy": "directional verification or industry context only",
        "commercial_market_tracker": "market share, shipments, registrations, POS, app, prescription, or tracker metrics after approval",
    }.get(signal_role, "")


def _role_runtime_gate(signal_role: str) -> str:
    return {
        "company_disclosed": "taxonomy_review_or_product_kpi_fact_parser",
        "official_product_surface": "official_origin_stale_page_and_taxonomy_gate",
        "public_proxy": "proxy_mapping_and_claim_boundary_gate",
        "commercial_market_tracker": "commercial_policy_approval_and_license_gate",
    }.get(signal_role, "")


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pct(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _repo_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
