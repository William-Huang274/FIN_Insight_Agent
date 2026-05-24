from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build seed Gold Context candidates for SEC benchmark v1.")
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument("--evidence-path", default="data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl")
    parser.add_argument("--bm25-index-dir", default="data/indexes/bm25/sec_tech_10k")
    parser.add_argument("--object-bm25-index-dir", default="data/indexes/bm25/sec_tech_10k_objects")
    parser.add_argument("--gold-context-dir", default="eval/sec_cases/gold_context")
    parser.add_argument("--gold-facts-dir", default="eval/sec_cases/gold_facts")
    parser.add_argument("--report-path", default="reports/quality/sec_benchmark_v1_gold_context_seed_report.json")
    parser.add_argument("--evidence-top-k", type=int, default=4)
    parser.add_argument("--object-top-k", type=int, default=3)
    parser.add_argument("--max-text-chars", type=int, default=3500)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing seed files. Reviewed files should not be overwritten.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    from retrieval.bm25_retriever import BM25Retriever
    from retrieval.object_bm25_retriever import ObjectBM25Retriever

    cases = _read_jsonl(REPO_ROOT / args.cases_path)
    evidence_rows = _read_jsonl(REPO_ROOT / args.evidence_path)
    evidence_by_id = {str(row.get("evidence_id")): row for row in evidence_rows}
    bm25 = BM25Retriever(REPO_ROOT / args.bm25_index_dir)
    object_bm25 = ObjectBM25Retriever(REPO_ROOT / args.object_bm25_index_dir)

    gold_context_dir = REPO_ROOT / args.gold_context_dir
    gold_facts_dir = REPO_ROOT / args.gold_facts_dir
    gold_context_dir.mkdir(parents=True, exist_ok=True)
    gold_facts_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for case in cases:
        case_id = str(case.get("case_id") or "")
        if str(case.get("gold_context_status")) != "needs_annotation":
            results.append(
                {
                    "case_id": case_id,
                    "status": "skipped",
                    "reason": str(case.get("gold_context_status")),
                    "context_rows": 0,
                    "fact_rows": 0,
                }
            )
            continue

        context_path = gold_context_dir / f"{case_id}.jsonl"
        facts_path = gold_facts_dir / f"{case_id}.json"
        if not args.overwrite and (context_path.exists() or facts_path.exists()):
            results.append(
                {
                    "case_id": case_id,
                    "status": "skipped_existing",
                    "context_path": str(context_path),
                    "facts_path": str(facts_path),
                }
            )
            continue

        context_rows = _build_context_rows(
            case,
            bm25,
            object_bm25,
            evidence_by_id,
            evidence_top_k=args.evidence_top_k,
            object_top_k=args.object_top_k,
            max_text_chars=args.max_text_chars,
        )
        fact_payload = _build_fact_payload(case, context_rows)
        _write_jsonl(context_path, context_rows)
        facts_path.write_text(json.dumps(fact_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append(
            {
                "case_id": case_id,
                "status": "created",
                "context_path": str(context_path),
                "facts_path": str(facts_path),
                "context_rows": len(context_rows),
                "fact_rows": len(fact_payload.get("facts") or []),
                "evidence_rows": sum(row.get("source_kind") == "evidence_object" for row in context_rows),
                "structured_rows": sum(row.get("source_kind") == "structured_object" for row in context_rows),
                "companies": case.get("companies"),
                "years": case.get("years"),
            }
        )

    status_counts = Counter(result.get("status") for result in results)
    report = {
        "schema_version": "sec_gold_context_seed_report_v0.1",
        "cases_path": str((REPO_ROOT / args.cases_path).resolve()),
        "gold_context_dir": str(gold_context_dir.resolve()),
        "gold_facts_dir": str(gold_facts_dir.resolve()),
        "review_status": "seed_needs_human_review",
        "selection_policy": {
            "evidence_top_k": args.evidence_top_k,
            "object_top_k": args.object_top_k,
            "max_text_chars": args.max_text_chars,
            "method": "filtered BM25 over EvidenceObject plus ObjectBM25 over structured metric/table objects",
        },
        "summary": {
            "case_count": len(cases),
            "created_count": status_counts.get("created", 0),
            "skipped_count": status_counts.get("skipped", 0),
            "skipped_existing_count": status_counts.get("skipped_existing", 0),
            "context_row_count": sum(int(result.get("context_rows") or 0) for result in results),
            "fact_row_count": sum(int(result.get("fact_rows") or 0) for result in results),
        },
        "results": results,
    }
    report_path = REPO_ROOT / args.report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                **report["summary"],
                "report_path": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _build_context_rows(
    case: dict[str, Any],
    bm25: Any,
    object_bm25: Any,
    evidence_by_id: dict[str, dict[str, Any]],
    evidence_top_k: int,
    object_top_k: int,
    max_text_chars: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_evidence_ids: set[str] = set()
    seen_object_ids: set[str] = set()
    case_id = str(case.get("case_id") or "")
    companies = [str(ticker).upper() for ticker in case.get("companies") or []]
    years = [int(year) for year in case.get("years") or []]

    for ticker in companies:
        for year in years:
            for query in _evidence_queries(case):
                hits = bm25.search(query, top_k=evidence_top_k, filters={"ticker": ticker, "fiscal_year": year})
                for hit in hits:
                    evidence_id = str(hit.get("evidence_id") or "")
                    if not evidence_id or evidence_id in seen_evidence_ids:
                        continue
                    source = evidence_by_id.get(evidence_id) or hit.get("record") or {}
                    rows.append(
                        _context_row_from_evidence(
                            case_id=case_id,
                            hit=hit,
                            source=source,
                            query=query,
                            selection_method="evidence_bm25_seed",
                            max_text_chars=max_text_chars,
                        )
                    )
                    seen_evidence_ids.add(evidence_id)

    for check in case.get("numeric_checks") or []:
        metric = str(check.get("metric") or "")
        check_companies = [str(ticker).upper() for ticker in check.get("companies") or companies]
        check_years = [int(year) for year in check.get("years") or years]
        for ticker in check_companies:
            for year in check_years:
                hits = object_bm25.search(
                    metric,
                    top_k=object_top_k,
                    filters={"ticker": [ticker], "fiscal_year": year, "object_type": ["metric", "table"]},
                )
                for hit in hits:
                    object_id = str(hit.get("object_id") or "")
                    if not object_id or object_id in seen_object_ids:
                        continue
                    rows.append(
                        _context_row_from_structured_object(
                            case_id=case_id,
                            hit=hit,
                            metric_query=metric,
                            selection_method="structured_object_bm25_seed",
                            max_text_chars=max_text_chars,
                        )
                    )
                    seen_object_ids.add(object_id)
                    source_evidence_id = str(hit.get("source_evidence_id") or "")
                    if source_evidence_id and source_evidence_id not in seen_evidence_ids:
                        source = evidence_by_id.get(source_evidence_id)
                        if source:
                            rows.append(
                                _context_row_from_evidence(
                                    case_id=case_id,
                                    hit={
                                        "rank": None,
                                        "score": None,
                                        "evidence_id": source_evidence_id,
                                        "ticker": source.get("ticker"),
                                        "fiscal_year": source.get("fiscal_year"),
                                        "section": source.get("section"),
                                    },
                                    source=source,
                                    query=metric,
                                    selection_method="structured_object_source_evidence_seed",
                                    max_text_chars=max_text_chars,
                                )
                            )
                            seen_evidence_ids.add(source_evidence_id)
    rows.sort(key=lambda row: _row_sort_key(row))
    return rows


def _evidence_queries(case: dict[str, Any]) -> list[str]:
    queries: list[str] = []
    prompt = str(case.get("prompt") or "").strip()
    if prompt:
        queries.append(prompt)
    for section in case.get("expected_sections") or []:
        query = f"{section} {case.get('task_type', '')} {' '.join(str(point) for point in (case.get('gold_points') or [])[:2])}"
        queries.append(query)
    if not queries:
        queries.append(" ".join(str(point) for point in case.get("gold_points") or []))
    return _dedupe(queries)


def _context_row_from_evidence(
    case_id: str,
    hit: dict[str, Any],
    source: dict[str, Any],
    query: str,
    selection_method: str,
    max_text_chars: int,
) -> dict[str, Any]:
    text = str(source.get("text") or "")
    return {
        "schema_version": "sec_gold_context_seed_v0.1",
        "case_id": case_id,
        "review_status": "seed_needs_review",
        "source_kind": "evidence_object",
        "selection_method": selection_method,
        "selection_query": query,
        "rank": hit.get("rank"),
        "score": hit.get("score"),
        "evidence_id": source.get("evidence_id") or hit.get("evidence_id"),
        "ticker": source.get("ticker") or hit.get("ticker"),
        "fiscal_year": source.get("fiscal_year") or hit.get("fiscal_year"),
        "source_type": source.get("source_type"),
        "section": source.get("section") or hit.get("section"),
        "subsection": source.get("subsection"),
        "source_url": source.get("source_url"),
        "local_path": source.get("local_path"),
        "text": _truncate(text, max_text_chars),
        "text_truncated": len(text) > max_text_chars,
    }


def _context_row_from_structured_object(
    case_id: str,
    hit: dict[str, Any],
    metric_query: str,
    selection_method: str,
    max_text_chars: int,
) -> dict[str, Any]:
    record = hit.get("record") or {}
    text = _structured_text(record)
    return {
        "schema_version": "sec_gold_context_seed_v0.1",
        "case_id": case_id,
        "review_status": "seed_needs_review",
        "source_kind": "structured_object",
        "selection_method": selection_method,
        "selection_query": metric_query,
        "rank": hit.get("rank"),
        "score": hit.get("score"),
        "object_id": record.get("object_id") or hit.get("object_id"),
        "object_type": record.get("object_type") or hit.get("object_type"),
        "source_evidence_id": record.get("source_evidence_id") or hit.get("source_evidence_id"),
        "ticker": record.get("ticker") or hit.get("ticker"),
        "fiscal_year": record.get("fiscal_year") or hit.get("fiscal_year"),
        "section": record.get("section") or hit.get("section"),
        "subsection": record.get("subsection") or hit.get("subsection"),
        "metric_name": record.get("metric_name"),
        "raw_value": record.get("raw_value"),
        "value": record.get("value"),
        "unit": record.get("unit"),
        "period": record.get("period"),
        "row_label": record.get("row_label"),
        "column_label": record.get("column_label"),
        "context": _truncate(str(record.get("context") or ""), max_text_chars),
        "text": _truncate(text, max_text_chars),
        "text_truncated": len(text) > max_text_chars,
    }


def _build_fact_payload(case: dict[str, Any], context_rows: list[dict[str, Any]]) -> dict[str, Any]:
    facts = []
    fact_index = 1
    for row in context_rows:
        if row.get("source_kind") != "structured_object":
            continue
        if row.get("object_type") != "metric":
            continue
        facts.append(
            {
                "fact_id": f"{case.get('case_id')}_FACT_{fact_index:04d}",
                "review_status": "seed_needs_review",
                "selection_method": row.get("selection_method"),
                "selection_query": row.get("selection_query"),
                "ticker": row.get("ticker"),
                "fiscal_year": row.get("fiscal_year"),
                "metric_name": row.get("metric_name"),
                "raw_value": row.get("raw_value"),
                "value": row.get("value"),
                "unit": row.get("unit"),
                "period": row.get("period"),
                "object_id": row.get("object_id"),
                "source_evidence_id": row.get("source_evidence_id"),
                "section": row.get("section"),
                "row_label": row.get("row_label"),
                "column_label": row.get("column_label"),
            }
        )
        fact_index += 1
    return {
        "schema_version": "sec_gold_facts_seed_v0.1",
        "case_id": case.get("case_id"),
        "benchmark_version": case.get("benchmark_version"),
        "review_status": "seed_needs_review",
        "numeric_checks": case.get("numeric_checks") or [],
        "facts": facts,
    }


def _structured_text(record: dict[str, Any]) -> str:
    parts = []
    for key in (
        "object_type",
        "metric_name",
        "raw_value",
        "unit",
        "period",
        "row_label",
        "column_label",
        "context",
        "claim_text",
    ):
        value = record.get(key)
        if value not in (None, ""):
            parts.append(f"{key}: {value}")
    return "\n".join(parts)


def _row_sort_key(row: dict[str, Any]) -> tuple[str, int, str, str, int]:
    return (
        str(row.get("ticker") or ""),
        int(row.get("fiscal_year") or 0),
        str(row.get("source_kind") or ""),
        str(row.get("selection_method") or ""),
        int(row.get("rank") or 9999),
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n[TRUNCATED]"


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


if __name__ == "__main__":
    main()
