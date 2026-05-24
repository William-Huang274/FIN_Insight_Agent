from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic facet-level evidence memory from a calibrated evidence pool."
    )
    parser.add_argument(
        "--grouped-pool-path",
        default="reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json",
    )
    parser.add_argument(
        "--metrics-path",
        default="data/processed_private/structured_objects/sec_tech_10k_metrics.jsonl",
    )
    parser.add_argument(
        "--tables-path",
        default="data/processed_private/structured_objects/sec_tech_10k_tables.jsonl",
    )
    parser.add_argument(
        "--claims-path",
        default="data/processed_private/structured_objects/sec_tech_10k_claims.jsonl",
    )
    parser.add_argument(
        "--output-path",
        default="reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory.json",
    )
    parser.add_argument(
        "--report-path",
        default="reports/metrics/sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_report.json",
    )
    parser.add_argument("--max-citations-per-aspect", type=int, default=1)
    parser.add_argument("--max-facet-citations", type=int, default=36)
    parser.add_argument("--max-facet-background", type=int, default=6)
    parser.add_argument("--fact-chars", type=int, default=420)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    grouped = _read_json(REPO_ROOT / args.grouped_pool_path)
    object_index = _load_structured_index(
        REPO_ROOT / args.metrics_path,
        REPO_ROOT / args.tables_path,
        REPO_ROOT / args.claims_path,
    )
    memory = _build_memory(
        grouped,
        object_index,
        max_citations_per_aspect=args.max_citations_per_aspect,
        max_facet_citations=args.max_facet_citations,
        max_facet_background=args.max_facet_background,
        fact_chars=args.fact_chars,
    )
    report = _report(memory, grouped, args)

    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(memory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_path = REPO_ROOT / args.report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _build_memory(
    grouped: dict[str, Any],
    object_index: dict[str, dict[str, Any]],
    *,
    max_citations_per_aspect: int,
    max_facet_citations: int,
    max_facet_background: int,
    fact_chars: int,
) -> dict[str, Any]:
    queries = []
    for query in grouped.get("queries") or []:
        facets = [
            _memory_facet(
                facet,
                object_index,
                max_citations_per_aspect=max_citations_per_aspect,
                max_facet_citations=max_facet_citations,
                max_facet_background=max_facet_background,
                fact_chars=fact_chars,
            )
            for facet in query.get("facets") or []
        ]
        query_memory = {
            "memory_type": "facet_evidence_memory",
            "query_id": query.get("query_id"),
            "cohort": query.get("cohort"),
            "mode": query.get("mode"),
            "difficulty": query.get("difficulty"),
            "scoring_profile": query.get("scoring_profile"),
            "ticker": query.get("ticker"),
            "tickers": query.get("tickers") or query.get("ticker"),
            "fiscal_year": query.get("fiscal_year"),
            "fiscal_years": query.get("fiscal_years") or query.get("fiscal_year"),
            "query": query.get("query"),
            "table_requirements": query.get("table_requirements") or {},
            "facets": facets,
            "memory_summary": _query_memory_summary(facets),
        }
        queries.append(query_memory)
    return {
        "schema_version": "facet_evidence_memory_v0.1",
        "source_grouped_pool_schema": grouped.get("schema_version"),
        "queries": queries,
    }


def _memory_facet(
    facet: dict[str, Any],
    object_index: dict[str, dict[str, Any]],
    *,
    max_citations_per_aspect: int,
    max_facet_citations: int,
    max_facet_background: int,
    fact_chars: int,
) -> dict[str, Any]:
    aspect_status = []
    citations = []
    background = []
    missing_aspects = []
    object_type_counts: Counter[str] = Counter()
    source_ids = set()

    for aspect in facet.get("aspects") or []:
        aspect_text = str(aspect.get("aspect") or "")
        ranked_candidates = _ranked_evidence(
            list(aspect.get("citation_evidence") or []) + list(aspect.get("background_evidence") or []),
            aspect_text=aspect_text,
            object_index=object_index,
        )
        aspect_citations = ranked_candidates[:max_citations_per_aspect]
        selected_ids = {evidence.get("object_id") for evidence in aspect_citations}
        aspect_background = [
            evidence
            for evidence in _ranked_evidence(
                list(aspect.get("citation_evidence") or []) + list(aspect.get("background_evidence") or []),
                aspect_text=aspect_text,
                object_index=object_index,
            )
            if evidence.get("object_id") not in selected_ids
        ][:1]
        status = "missing" if aspect.get("missing_aspect") else ("covered" if aspect_citations else "partial")
        if aspect.get("missing_aspect"):
            missing_aspects.append(
                {
                    "aspect_id": aspect.get("aspect_id"),
                    "aspect": aspect.get("aspect"),
                    "missing_reason": aspect.get("missing_reason"),
                }
            )
        aspect_status.append(
            {
                "aspect_id": aspect.get("aspect_id"),
                "aspect": aspect.get("aspect"),
                "status": status,
                "citation_object_ids": [evidence.get("object_id") for evidence in aspect_citations],
            }
        )
        for evidence in aspect_citations:
            record = _memory_evidence(evidence, aspect, object_index, fact_chars=fact_chars)
            citations.append(record)
            object_type_counts.update([str(record.get("object_type"))])
            if record.get("source_evidence_id"):
                source_ids.add(str(record["source_evidence_id"]))
        for evidence in aspect_background:
            record = _memory_evidence(evidence, aspect, object_index, fact_chars=max(120, fact_chars // 2))
            background.append(record)

    citations = _dedupe_by_object_id(citations)[:max_facet_citations]
    background = [
        item for item in _dedupe_by_object_id(background) if item.get("object_id") not in {e.get("object_id") for e in citations}
    ][:max_facet_background]
    covered_count = sum(1 for item in aspect_status if item.get("status") == "covered")
    partial_count = sum(1 for item in aspect_status if item.get("status") == "partial")
    missing_count = sum(1 for item in aspect_status if item.get("status") == "missing")
    return {
        "facet": facet.get("facet"),
        "facet_must_find": facet.get("facet_must_find") or [],
        "coverage": {
            "aspect_count": len(aspect_status),
            "covered_aspects": covered_count,
            "partial_aspects": partial_count,
            "missing_aspects": missing_count,
            "citation_evidence_count": len(citations),
            "background_evidence_count": len(background),
            "source_evidence_count": len(source_ids),
            "object_type_counts": dict(sorted(object_type_counts.items())),
        },
        "aspect_status": aspect_status,
        "citation_evidence": citations,
        "background_evidence": background,
        "missing_aspects": missing_aspects,
        "facet_note": _facet_note(facet.get("facet"), aspect_status, citations, missing_aspects),
    }


def _memory_evidence(
    evidence: dict[str, Any],
    aspect: dict[str, Any],
    object_index: dict[str, dict[str, Any]],
    *,
    fact_chars: int,
) -> dict[str, Any]:
    object_id = str(evidence.get("object_id") or "")
    structured = object_index.get(object_id, {})
    fact = _fact_text(evidence, structured, aspect_text=str(aspect.get("aspect") or ""))
    return {
        "object_id": object_id,
        "object_type": evidence.get("object_type"),
        "source_evidence_id": evidence.get("source_evidence_id"),
        "ticker": structured.get("ticker") or evidence.get("object_ticker") or _ticker_from_id(object_id),
        "fiscal_year": structured.get("fiscal_year") or evidence.get("object_fiscal_year") or _year_from_id(object_id),
        "verifier_label": evidence.get("verifier_label"),
        "verifier_confidence": evidence.get("verifier_confidence"),
        "rerank_score": evidence.get("rerank_score"),
        "aspect": aspect.get("aspect"),
        "fact": _trim(fact, fact_chars),
        "metric": _metric_payload(structured),
        "source_url": evidence.get("source_url"),
    }


def _fact_text(evidence: dict[str, Any], structured: dict[str, Any], *, aspect_text: str) -> str:
    object_type = structured.get("object_type") or evidence.get("object_type")
    if object_type == "metric":
        parts = [
            structured.get("ticker"),
            f"FY{structured.get('fiscal_year')}" if structured.get("fiscal_year") else None,
            structured.get("metric_name"),
            structured.get("segment"),
            structured.get("period"),
            structured.get("row_label"),
            structured.get("column_label"),
            structured.get("raw_value"),
            _value_unit(structured),
        ]
        return " | ".join(str(part) for part in parts if part not in (None, ""))
    if object_type == "table":
        cells = _matching_cells(structured.get("cells") or [], aspect_text, limit=6)
        if cells:
            cell_text = "; ".join(
                " | ".join(
                    str(part)
                    for part in [
                        cell.get("row_label"),
                        cell.get("column_label"),
                        cell.get("period"),
                        cell.get("raw_value"),
                        _value_unit(cell),
                    ]
                    if part not in (None, "")
                )
                for cell in cells
            )
            return f"{structured.get('title') or evidence.get('preview') or 'table'} :: {cell_text}"
        return str(evidence.get("preview") or structured.get("title") or evidence.get("object_text") or "")
    if object_type == "claim":
        return str(structured.get("claim_text") or evidence.get("preview") or evidence.get("object_text") or "")
    return str(evidence.get("preview") or evidence.get("object_text") or "")


def _matching_cells(cells: list[dict[str, Any]], aspect_text: str, *, limit: int) -> list[dict[str, Any]]:
    tokens = set(_tokens(aspect_text))
    scored = []
    for cell in cells:
        text = " ".join(
            str(part)
            for part in [cell.get("row_label"), cell.get("column_label"), cell.get("period"), cell.get("raw_value")]
            if part
        ).lower()
        score = sum(1 for token in tokens if token in text)
        if score:
            scored.append((score, cell))
    if not scored:
        return cells[:limit]
    return [cell for _, cell in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]]


def _metric_payload(structured: dict[str, Any]) -> dict[str, Any] | None:
    if structured.get("object_type") != "metric":
        return None
    return {
        "metric_name": structured.get("metric_name"),
        "raw_value": structured.get("raw_value"),
        "value": structured.get("value"),
        "unit": structured.get("unit"),
        "period": structured.get("period"),
        "segment": structured.get("segment"),
        "row_label": structured.get("row_label"),
        "column_label": structured.get("column_label"),
        "table_object_id": structured.get("table_object_id"),
    }


def _facet_note(
    facet_name: str | None,
    aspect_status: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    missing_aspects: list[dict[str, Any]],
) -> str:
    covered = sum(1 for item in aspect_status if item.get("status") == "covered")
    missing = len(missing_aspects)
    types = Counter(str(item.get("object_type")) for item in citations)
    return (
        f"{facet_name or 'facet'}: covered {covered}/{len(aspect_status)} aspects, "
        f"missing {missing}, citations {len(citations)} ({dict(types)})."
    )


def _query_memory_summary(facets: list[dict[str, Any]]) -> dict[str, Any]:
    totals = Counter()
    object_types = Counter()
    for facet in facets:
        coverage = facet.get("coverage") or {}
        totals["facets"] += 1
        totals["aspects"] += int(coverage.get("aspect_count") or 0)
        totals["covered_aspects"] += int(coverage.get("covered_aspects") or 0)
        totals["partial_aspects"] += int(coverage.get("partial_aspects") or 0)
        totals["missing_aspects"] += int(coverage.get("missing_aspects") or 0)
        totals["citation_evidence"] += int(coverage.get("citation_evidence_count") or 0)
        totals["background_evidence"] += int(coverage.get("background_evidence_count") or 0)
        object_types.update(coverage.get("object_type_counts") or {})
    return dict(totals) | {"object_type_counts": dict(sorted(object_types.items()))}


def _report(memory: dict[str, Any], grouped: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    totals = Counter()
    object_types = Counter()
    for query in memory.get("queries") or []:
        summary = query.get("memory_summary") or {}
        for key, value in summary.items():
            if key == "object_type_counts":
                object_types.update(value or {})
            elif isinstance(value, (int, float)):
                totals[key] += value
    return {
        "mode": "facet_evidence_memory_build",
        "schema_version": memory.get("schema_version"),
        "grouped_pool_path": str(REPO_ROOT / args.grouped_pool_path),
        "output_path": str(REPO_ROOT / args.output_path),
        "query_count": len(memory.get("queries") or []),
        "source_query_count": len(grouped.get("queries") or []),
        "totals": dict(totals) | {"object_type_counts": dict(sorted(object_types.items()))},
        "settings": {
            "max_citations_per_aspect": args.max_citations_per_aspect,
            "max_facet_citations": args.max_facet_citations,
            "max_facet_background": args.max_facet_background,
            "fact_chars": args.fact_chars,
        },
    }


def _ranked_evidence(
    rows: list[dict[str, Any]],
    *,
    aspect_text: str = "",
    object_index: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    object_index = object_index or {}
    return sorted(
        rows,
        key=lambda row: (
            _aspect_fit_score(row, aspect_text, object_index.get(str(row.get("object_id") or ""), {})),
            _label_priority(row),
            float(row.get("verifier_confidence") or 0.0),
            float(row.get("rerank_score") or 0.0),
            -int(row.get("pool_rank") or 9999),
        ),
        reverse=True,
    )


def _label_priority(row: dict[str, Any]) -> int:
    label = str(row.get("verifier_label") or "")
    if label == "direct":
        return 2
    if label == "partial":
        return 1
    return 0


def _aspect_fit_score(row: dict[str, Any], aspect_text: str, structured: dict[str, Any]) -> float:
    aspect = aspect_text.lower()
    text = " ".join(
        str(part or "")
        for part in [
            aspect_text,
            row.get("preview"),
            structured.get("metric_name"),
            structured.get("raw_value"),
            structured.get("unit"),
            structured.get("row_label"),
            structured.get("column_label"),
            structured.get("claim_type"),
            structured.get("claim_text"),
            structured.get("context"),
        ]
    ).lower()
    raw_unit_text = " ".join(str(part or "") for part in [structured.get("raw_value"), structured.get("unit")]).lower()
    score = 0.0
    if _aspect_mentions_growth(aspect):
        if "%" in raw_unit_text or "percent" in raw_unit_text:
            score += 8.0
        elif "%" in text or "percent" in text:
            score += 1.0
        if "$" in raw_unit_text or " usd" in raw_unit_text or "billion" in raw_unit_text or "million" in raw_unit_text:
            score -= 3.0
        if (structured.get("object_type") or row.get("object_type")) == "metric":
            score += 1.0
        if (structured.get("object_type") or row.get("object_type")) == "claim":
            score -= 0.5
        if "growth" in text or "grew" in text or "increased" in text:
            score += 0.8
    elif "revenue" in aspect:
        if "$" in text or "usd" in text or "billion" in text or "million" in text:
            score += 2.0
        if "%" in text or "percent" in text:
            score -= 0.8
    if any(term in aspect for term in ("risk", "caveat", "customer concentration", "supply", "pressure")):
        if (structured.get("object_type") or row.get("object_type")) == "claim":
            score += 2.0
        if str(structured.get("claim_type") or "") == "risk":
            score += 1.0
    ticker = str(structured.get("ticker") or row.get("object_ticker") or "").lower()
    if ticker and ticker in aspect:
        score += 0.5
    year = str(structured.get("fiscal_year") or row.get("object_fiscal_year") or "")
    if year and year in aspect:
        score += 0.5
    return score


def _aspect_mentions_growth(aspect_text: str) -> bool:
    return any(term in aspect_text for term in ("yoy", "growth", "year over year", "同比"))


def _dedupe_by_object_id(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for row in rows:
        object_id = row.get("object_id")
        if not object_id or object_id in seen:
            continue
        seen.add(object_id)
        out.append(row)
    return out


def _load_structured_index(*paths: Path) -> dict[str, dict[str, Any]]:
    index = {}
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                row = json.loads(stripped)
                index[str(row.get("object_id"))] = row
    return index


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1]


def _value_unit(record: dict[str, Any]) -> str | None:
    value = record.get("value")
    unit = record.get("unit")
    if value is None and not unit:
        return None
    return f"{value} {unit or ''}".strip()


def _ticker_from_id(object_id: str) -> str | None:
    return object_id.split("_", 1)[0] if "_" in object_id else None


def _year_from_id(object_id: str) -> int | None:
    match = re.search(r"_(20\d{2})_", object_id)
    return int(match.group(1)) if match else None


def _trim(text: str, max_chars: int) -> str:
    compact = " ".join(str(text).split())
    if max_chars <= 0:
        return ""
    return compact[:max_chars] + ("..." if len(compact) > max_chars else "")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
