"""Audit SEC chunk quality before retrieval or multi-agent evaluation.

This script is artifact-only. It reads chunk/evidence/index files from disk and
does not call an LLM, reranker, database, or external service.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHUNKS_PATH = (
    REPO_ROOT
    / "data"
    / "processed_private"
    / "chunks"
    / "sector_depth_full238_us_v0_2_mixed_with_8k_chunks_fy2023_2027.jsonl"
)
DEFAULT_EVIDENCE_PATH = (
    REPO_ROOT
    / "data"
    / "processed_private"
    / "evidence_objects"
    / "sector_depth_full238_us_v0_2_mixed_with_8k_evidence_fy2023_2027.jsonl"
)
DEFAULT_BM25_INDEX_DIR = (
    REPO_ROOT
    / "data"
    / "indexes"
    / "bm25"
    / "sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027"
)
DEFAULT_OBJECT_BM25_INDEX_DIR = (
    REPO_ROOT
    / "data"
    / "indexes"
    / "bm25"
    / "sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_objects"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "chunk_quality_audit"
SCHEMA_VERSION = "sec_agent_chunk_quality_audit_v0.1"

TOKEN_RE = re.compile(r"\$?\d[\d,.$%/-]*|[A-Za-z][A-Za-z0-9&'./%-]*|[\u4e00-\u9fff]")
MAX_OVERLAP_TOKENS_TO_STORE = 420

PROFILE_BY_FORM = {
    "10-K": {"target_words": 900, "overlap_words": 150, "min_words": 80},
    "10-Q": {"target_words": 900, "overlap_words": 150, "min_words": 80},
    "8-K": {"target_words": 650, "overlap_words": 100, "min_words": 40},
}
REQUIRED_ITEMS_BY_FORM = {
    "10-K": {"1", "1A", "7", "8"},
    "10-Q": {"1", "2"},
    "8-K": {"exhibit_99_1"},
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit SEC chunk quality and index parity.")
    parser.add_argument("--chunks-path", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--evidence-path", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--bm25-index-dir", type=Path, default=DEFAULT_BM25_INDEX_DIR)
    parser.add_argument("--object-bm25-index-dir", type=Path, default=DEFAULT_OBJECT_BM25_INDEX_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--limit", type=int, default=0, help="Optional diagnostic row limit.")
    parser.add_argument("--max-examples", type=int, default=20)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_id = args.run_id or _default_run_id()
    output_dir = args.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    audit = audit_chunk_quality(
        chunks_path=_resolve_path(args.chunks_path),
        evidence_path=_optional_path(args.evidence_path),
        bm25_index_dir=_optional_path(args.bm25_index_dir),
        object_bm25_index_dir=_optional_path(args.object_bm25_index_dir),
        run_id=run_id,
        limit=args.limit,
        max_examples=max(1, int(args.max_examples)),
    )
    audit["elapsed_ms"] = int((time.time() - started) * 1000)
    json_path = output_dir / "chunk_quality_summary.json"
    md_path = output_dir / "chunk_quality_summary.md"
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(audit), encoding="utf-8")
    print(json.dumps(_stdout_summary(audit, json_path, md_path), ensure_ascii=False, indent=2))
    if args.strict and audit["gate_status"] != "pass":
        return 1
    return 0


def audit_chunk_quality(
    *,
    chunks_path: Path,
    evidence_path: Path | None = None,
    bm25_index_dir: Path | None = None,
    object_bm25_index_dir: Path | None = None,
    run_id: str = "",
    limit: int = 0,
    max_examples: int = 20,
) -> dict[str, Any]:
    state = _new_state(max_examples=max_examples)
    input_digest = hashlib.sha256()
    for line_number, line in _iter_jsonl_lines(chunks_path, limit=limit):
        input_digest.update(line.encode("utf-8"))
        _consume_chunk_line(state, chunks_path, line_number, line)

    chunk_stats = _finalize_chunk_stats(state)
    evidence_parity = _audit_evidence_parity(
        evidence_path=evidence_path,
        chunk_ids=state["chunk_ids"],
        max_examples=max_examples,
    )
    index_parity = _audit_index_parity(
        bm25_index_dir=bm25_index_dir,
        object_bm25_index_dir=object_bm25_index_dir,
        chunk_count=chunk_stats["chunk_count"],
        evidence_row_count=evidence_parity.get("evidence_row_count", 0),
        evidence_unique_id_count=evidence_parity.get("evidence_unique_id_count", 0),
    )
    checks = _quality_checks(chunk_stats, evidence_parity, index_parity)
    failed = [key for key, value in checks.items() if value is False]
    warnings = _quality_warnings(chunk_stats, evidence_parity, index_parity)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "gate_status": "pass" if not failed else "fail",
        "diagnostic_only": False,
        "input": {
            "chunks_path": str(chunks_path),
            "chunks_sha256": input_digest.hexdigest(),
            "evidence_path": str(evidence_path) if evidence_path else "",
            "bm25_index_dir": str(bm25_index_dir) if bm25_index_dir else "",
            "object_bm25_index_dir": str(object_bm25_index_dir) if object_bm25_index_dir else "",
            "limit": int(limit or 0),
        },
        "checks": checks,
        "failed_checks": failed,
        "warnings": warnings,
        "chunk_stats": chunk_stats,
        "evidence_parity": evidence_parity,
        "index_parity": index_parity,
        "milvus_insertion_experiment": _milvus_insertion_experiment(chunk_stats, checks, warnings),
    }


def render_markdown(audit: Mapping[str, Any]) -> str:
    stats = audit.get("chunk_stats") if isinstance(audit.get("chunk_stats"), Mapping) else {}
    length = stats.get("length_distribution") if isinstance(stats.get("length_distribution"), Mapping) else {}
    forms = stats.get("form_counts") if isinstance(stats.get("form_counts"), Mapping) else {}
    table = stats.get("table_stats") if isinstance(stats.get("table_stats"), Mapping) else {}
    overlap = stats.get("overlap_stats") if isinstance(stats.get("overlap_stats"), Mapping) else {}
    coverage = stats.get("item_coverage") if isinstance(stats.get("item_coverage"), Mapping) else {}
    evidence = audit.get("evidence_parity") if isinstance(audit.get("evidence_parity"), Mapping) else {}
    index = audit.get("index_parity") if isinstance(audit.get("index_parity"), Mapping) else {}

    lines = [
        f"# SEC Chunk Quality Audit: {audit.get('run_id') or ''}",
        "",
        f"- Gate: `{audit.get('gate_status') or ''}`",
        f"- Chunk count: `{stats.get('chunk_count') or 0}`",
        f"- Filing count: `{coverage.get('filing_count') or 0}`",
        f"- Tickers: `{stats.get('ticker_count') or 0}`",
        f"- Elapsed ms: `{audit.get('elapsed_ms') or 0}`",
        "",
        "## Hard Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for name, value in (audit.get("checks") or {}).items():
        lines.append(f"| `{name}` | `{str(bool(value)).lower()}` |")
    lines.extend(["", "## Distribution", "", "| Metric | Value |", "| --- | ---: |"])
    for key in ("min", "p05", "p25", "median", "p75", "p95", "p99", "max", "mean"):
        lines.append(f"| word_count_{key} | `{_fmt(length.get(key))}` |")
    lines.extend(["", "## Forms", "", "| Form | Chunks |", "| --- | ---: |"])
    for form, count in sorted(forms.items()):
        lines.append(f"| `{form}` | `{count}` |")
    lines.extend(["", "## Table And Overlap", "", "| Metric | Value |", "| --- | ---: |"])
    for key in (
        "contains_table_count",
        "unbalanced_table_marker_count",
        "table_chunk_too_long_count",
    ):
        lines.append(f"| `{key}` | `{table.get(key) or 0}` |")
    for key in (
        "split_block_count",
        "split_pair_count",
        "zero_overlap_pair_count",
        "overlap_p50",
        "overlap_p10",
    ):
        lines.append(f"| `{key}` | `{_fmt(overlap.get(key))}` |")
    lines.extend(["", "## Item Coverage", "", "| Metric | Value |", "| --- | ---: |"])
    for key in (
        "filing_count",
        "core_item_missing_filing_count",
        "core_item_missing_filing_rate",
        "primary_core_item_missing_filing_count",
        "primary_core_item_missing_filing_rate",
    ):
        lines.append(f"| `{key}` | `{_fmt(coverage.get(key))}` |")
    lines.extend(["", "## Evidence / Index Parity", "", "| Metric | Value |", "| --- | ---: |"])
    for key in ("evidence_row_count", "evidence_unique_id_count", "duplicate_evidence_id_count", "missing_evidence_count", "extra_evidence_count"):
        lines.append(f"| `{key}` | `{evidence.get(key) or 0}` |")
    for key in ("bm25_metadata_records", "object_bm25_records", "bm25_records_match_evidence_rows"):
        lines.append(f"| `{key}` | `{index.get(key)}` |")
    warnings = audit.get("warnings") or []
    lines.extend(["", "## Warnings", ""])
    if warnings:
        for item in warnings:
            lines.append(f"- `{item}`")
    else:
        lines.append("- none")
    experiment = audit.get("milvus_insertion_experiment") or {}
    lines.extend(["", "## Milvus Experiment Decision", ""])
    lines.append(str(experiment.get("decision") or ""))
    for item in experiment.get("next_steps") or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def _consume_chunk_line(state: dict[str, Any], path: Path, line_number: int, line: str) -> None:
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        state["parse_error_count"] += 1
        _add_example(state, "parse_errors", {"line_number": line_number})
        return
    chunk_id = str(row.get("chunk_id") or "")
    if not chunk_id:
        state["missing_chunk_id_count"] += 1
        _add_example(state, "missing_chunk_id", {"line_number": line_number})
        return
    if chunk_id in state["chunk_ids"]:
        state["duplicate_chunk_id_count"] += 1
        _add_example(state, "duplicate_chunk_ids", {"chunk_id": chunk_id, "line_number": line_number})
    state["chunk_ids"].add(chunk_id)
    state["chunk_count"] += 1

    text = str(row.get("text") or "")
    tokens = _tokens(text)
    word_count = len(tokens)
    state["word_counts"].append(word_count)
    form_type = _norm(row.get("form_type") or row.get("source_type") or "unknown")
    item_code = str(row.get("item_code") or "").strip()
    ticker = _norm(row.get("ticker") or "unknown")
    source_tier = str(row.get("source_tier") or row.get("metadata", {}).get("source_tier") or "unknown")
    profile = _profile_for_form(form_type)

    state["form_counts"][form_type] += 1
    state["item_counts"][item_code or "unknown"] += 1
    state["ticker_counts"][ticker] += 1
    state["source_tier_counts"][source_tier] += 1
    if word_count < profile["min_words"]:
        state["too_short_count"] += 1
        _add_example(state, "too_short_chunks", _chunk_example(row, line_number, word_count))
    if word_count > profile["target_words"] * 1.75:
        state["too_long_count"] += 1
        _add_example(state, "too_long_chunks", _chunk_example(row, line_number, word_count))
    if word_count > profile["target_words"] * 2.5:
        state["extreme_long_count"] += 1
        _add_example(state, "extreme_long_chunks", _chunk_example(row, line_number, word_count))

    table_starts = text.count("[TABLE_START")
    table_ends = text.count("[TABLE_END]")
    contains_table = bool(row.get("contains_table")) or table_starts > 0 or table_ends > 0
    if contains_table:
        state["contains_table_count"] += 1
    if table_starts != table_ends:
        state["unbalanced_table_marker_count"] += 1
        _add_example(state, "unbalanced_table_chunks", _chunk_example(row, line_number, word_count))
    if contains_table and word_count > profile["target_words"] * 1.75:
        state["table_chunk_too_long_count"] += 1

    _consume_char_boundary(state, row, line_number, word_count)
    _consume_overlap(state, row, tokens, word_count)
    _consume_item_coverage(state, row, form_type, item_code, path)


def _consume_char_boundary(state: dict[str, Any], row: Mapping[str, Any], line_number: int, word_count: int) -> None:
    char_start = _int_or_none(row.get("char_start"))
    char_end = _int_or_none(row.get("char_end"))
    block_start = _int_or_none(row.get("block_char_start"))
    block_end = _int_or_none(row.get("block_char_end"))
    if char_start is None or char_end is None or char_start >= char_end:
        state["invalid_char_boundary_count"] += 1
        _add_example(state, "invalid_char_boundaries", _chunk_example(row, line_number, word_count))
        return
    if block_start is not None and block_end is not None and (char_start < block_start or char_end > block_end):
        state["outside_block_boundary_count"] += 1
        _add_example(state, "outside_block_boundaries", _chunk_example(row, line_number, word_count))


def _consume_overlap(
    state: dict[str, Any],
    row: Mapping[str, Any],
    tokens: list[str],
    word_count: int,
) -> None:
    block_id = str(row.get("block_id") or "")
    if not block_id:
        return
    part_index = _int_or_none(row.get("block_part_index")) or 1
    part_count = _int_or_none(row.get("block_part_count")) or 1
    if part_count <= 1:
        return
    state["split_block_ids"].add(block_id)
    state["split_parts"][block_id].append(
        {
            "part_index": part_index,
            "part_count": part_count,
            "word_count": word_count,
            "form_type": _norm(row.get("form_type") or row.get("source_type") or "unknown"),
            "chunk_id": str(row.get("chunk_id") or ""),
            "head": tokens[:MAX_OVERLAP_TOKENS_TO_STORE],
            "tail": tokens[-MAX_OVERLAP_TOKENS_TO_STORE:],
        }
    )


def _consume_item_coverage(
    state: dict[str, Any],
    row: Mapping[str, Any],
    form_type: str,
    item_code: str,
    path: Path,
) -> None:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    accession = str(metadata.get("accession_number") or "")
    local_path = str(row.get("local_path") or "")
    filing_key = (
        _norm(row.get("ticker") or "unknown"),
        str(row.get("fiscal_year") or ""),
        form_type,
        accession or local_path or str(path),
    )
    filing = state["filings"][filing_key]
    filing["ticker"] = filing_key[0]
    filing["fiscal_year"] = filing_key[1]
    filing["form_type"] = form_type
    filing["accession_number"] = accession
    filing["source_tier"] = str(row.get("source_tier") or metadata.get("source_tier") or "")
    filing["items"].add(item_code)
    filing["chunk_count"] += 1


def _finalize_chunk_stats(state: dict[str, Any]) -> dict[str, Any]:
    word_counts = state["word_counts"]
    chunk_count = state["chunk_count"]
    split_pair_overlaps = []
    incomplete_split_blocks = 0
    for block_id, parts in state["split_parts"].items():
        parts = sorted(parts, key=lambda item: item["part_index"])
        expected = max(int(item.get("part_count") or 0) for item in parts) if parts else 0
        if expected and len(parts) != expected:
            incomplete_split_blocks += 1
            _add_example(
                state,
                "incomplete_split_blocks",
                {
                    "block_id": block_id,
                    "expected_parts": expected,
                    "observed_parts": len(parts),
                },
            )
        for left, right in zip(parts, parts[1:]):
            overlap = _common_suffix_prefix(left["tail"], right["head"])
            split_pair_overlaps.append(overlap)
            if overlap == 0:
                _add_example(
                    state,
                    "zero_overlap_pairs",
                    {
                        "left_chunk_id": left["chunk_id"],
                        "right_chunk_id": right["chunk_id"],
                    },
                )

    item_coverage = _item_coverage_stats(state)
    rates = {
        "too_short_rate": _rate(state["too_short_count"], chunk_count),
        "too_long_rate": _rate(state["too_long_count"], chunk_count),
        "extreme_long_rate": _rate(state["extreme_long_count"], chunk_count),
        "unbalanced_table_marker_rate": _rate(state["unbalanced_table_marker_count"], chunk_count),
        "invalid_char_boundary_rate": _rate(state["invalid_char_boundary_count"], chunk_count),
        "outside_block_boundary_rate": _rate(state["outside_block_boundary_count"], chunk_count),
    }
    return {
        "chunk_count": chunk_count,
        "ticker_count": len(state["ticker_counts"]),
        "form_counts": dict(sorted(state["form_counts"].items())),
        "item_counts": dict(sorted(state["item_counts"].items())),
        "source_tier_counts": dict(sorted(state["source_tier_counts"].items())),
        "top_tickers_by_chunk_count": state["ticker_counts"].most_common(20),
        "length_distribution": _distribution(word_counts),
        "quality_counts": {
            "parse_error_count": state["parse_error_count"],
            "missing_chunk_id_count": state["missing_chunk_id_count"],
            "duplicate_chunk_id_count": state["duplicate_chunk_id_count"],
            "too_short_count": state["too_short_count"],
            "too_long_count": state["too_long_count"],
            "extreme_long_count": state["extreme_long_count"],
            "invalid_char_boundary_count": state["invalid_char_boundary_count"],
            "outside_block_boundary_count": state["outside_block_boundary_count"],
            **rates,
        },
        "table_stats": {
            "contains_table_count": state["contains_table_count"],
            "contains_table_rate": _rate(state["contains_table_count"], chunk_count),
            "unbalanced_table_marker_count": state["unbalanced_table_marker_count"],
            "table_chunk_too_long_count": state["table_chunk_too_long_count"],
        },
        "overlap_stats": {
            "split_block_count": len(state["split_block_ids"]),
            "incomplete_split_block_count": incomplete_split_blocks,
            "split_pair_count": len(split_pair_overlaps),
            "zero_overlap_pair_count": sum(1 for value in split_pair_overlaps if value == 0),
            "zero_overlap_pair_rate": _rate(sum(1 for value in split_pair_overlaps if value == 0), len(split_pair_overlaps)),
            "overlap_distribution": _distribution(split_pair_overlaps),
            "overlap_p10": _quantile(split_pair_overlaps, 0.10),
            "overlap_p50": _quantile(split_pair_overlaps, 0.50),
        },
        "item_coverage": item_coverage,
        "examples": state["examples"],
    }


def _item_coverage_stats(state: dict[str, Any]) -> dict[str, Any]:
    missing = []
    primary_missing = []
    form_filing_counts = Counter()
    for filing_key, filing in state["filings"].items():
        form_type = filing["form_type"]
        required = REQUIRED_ITEMS_BY_FORM.get(form_type)
        form_filing_counts[form_type] += 1
        if not required:
            continue
        observed = {str(item) for item in filing["items"] if item}
        missing_items = sorted(required - observed)
        if not missing_items:
            continue
        example = {
            "ticker": filing["ticker"],
            "fiscal_year": filing["fiscal_year"],
            "form_type": form_type,
            "accession_number": filing.get("accession_number") or "",
            "missing_items": missing_items,
            "observed_items": sorted(observed),
            "chunk_count": filing["chunk_count"],
        }
        missing.append(example)
        if form_type in {"10-K", "10-Q"}:
            primary_missing.append(example)
    total_filings = len(state["filings"])
    return {
        "filing_count": total_filings,
        "form_filing_counts": dict(sorted(form_filing_counts.items())),
        "core_item_missing_filing_count": len(missing),
        "core_item_missing_filing_rate": _rate(len(missing), total_filings),
        "primary_core_item_missing_filing_count": len(primary_missing),
        "primary_core_item_missing_filing_rate": _rate(len(primary_missing), sum(count for form, count in form_filing_counts.items() if form in {"10-K", "10-Q"})),
        "missing_core_item_examples": missing[: state["max_examples"]],
    }


def _audit_evidence_parity(
    *,
    evidence_path: Path | None,
    chunk_ids: set[str],
    max_examples: int,
) -> dict[str, Any]:
    if not evidence_path or not evidence_path.exists():
        return {
            "status": "not_configured",
            "evidence_row_count": 0,
            "evidence_unique_id_count": 0,
            "missing_evidence_count": len(chunk_ids),
            "extra_evidence_count": 0,
            "parse_error_count": 0,
        }
    evidence_ids: set[str] = set()
    row_count = 0
    parse_errors = 0
    duplicate_count = 0
    for _, line in _iter_jsonl_lines(evidence_path, limit=0):
        row_count += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        evidence_id = str(row.get("evidence_id") or "")
        if not evidence_id:
            continue
        if evidence_id in evidence_ids:
            duplicate_count += 1
        evidence_ids.add(evidence_id)
    missing = sorted(chunk_ids - evidence_ids)[:max_examples]
    extra = sorted(evidence_ids - chunk_ids)[:max_examples]
    return {
        "status": "pass" if not parse_errors and not duplicate_count and not missing and not extra else "fail",
        "evidence_row_count": row_count,
        "evidence_unique_id_count": len(evidence_ids),
        "parse_error_count": parse_errors,
        "duplicate_evidence_id_count": duplicate_count,
        "missing_evidence_count": len(chunk_ids - evidence_ids),
        "extra_evidence_count": len(evidence_ids - chunk_ids),
        "missing_evidence_examples": missing,
        "extra_evidence_examples": extra,
    }


def _audit_index_parity(
    *,
    bm25_index_dir: Path | None,
    object_bm25_index_dir: Path | None,
    chunk_count: int,
    evidence_row_count: int,
    evidence_unique_id_count: int,
) -> dict[str, Any]:
    bm25_metadata = _read_metadata(bm25_index_dir / "metadata.json" if bm25_index_dir else None)
    object_metadata = _read_metadata(object_bm25_index_dir / "metadata.json" if object_bm25_index_dir else None)
    bm25_records = int(bm25_metadata.get("records") or 0)
    object_records = int(object_metadata.get("records") or object_metadata.get("record_count") or 0)
    return {
        "bm25_metadata_records": bm25_records,
        "bm25_index_type": bm25_metadata.get("index_type") or "",
        "bm25_records_match_evidence_rows": bm25_records == evidence_row_count if bm25_records and evidence_row_count else False,
        "bm25_records_match_unique_evidence": bm25_records == evidence_unique_id_count if bm25_records and evidence_unique_id_count else False,
        "bm25_records_match_evidence": bm25_records == evidence_row_count if bm25_records and evidence_row_count else False,
        "bm25_records_match_chunks": bm25_records == chunk_count if bm25_records and chunk_count else False,
        "object_bm25_records": object_records,
        "object_bm25_index_type": object_metadata.get("index_type") or object_metadata.get("schema_version") or "",
        "object_bm25_present": object_records > 0,
    }


def _quality_checks(
    chunk_stats: Mapping[str, Any],
    evidence_parity: Mapping[str, Any],
    index_parity: Mapping[str, Any],
) -> dict[str, bool]:
    counts = chunk_stats.get("quality_counts") if isinstance(chunk_stats.get("quality_counts"), Mapping) else {}
    table = chunk_stats.get("table_stats") if isinstance(chunk_stats.get("table_stats"), Mapping) else {}
    overlap = chunk_stats.get("overlap_stats") if isinstance(chunk_stats.get("overlap_stats"), Mapping) else {}
    coverage = chunk_stats.get("item_coverage") if isinstance(chunk_stats.get("item_coverage"), Mapping) else {}
    return {
        "chunk_rows_present": int(chunk_stats.get("chunk_count") or 0) > 0,
        "parse_errors_absent": int(counts.get("parse_error_count") or 0) == 0,
        "chunk_ids_present": int(counts.get("missing_chunk_id_count") or 0) == 0,
        "duplicate_chunk_ids_absent": int(counts.get("duplicate_chunk_id_count") or 0) == 0,
        "table_markers_balanced": int(table.get("unbalanced_table_marker_count") or 0) == 0,
        "char_boundaries_valid": int(counts.get("invalid_char_boundary_count") or 0) == 0,
        "chunk_length_extremes_bounded": float(counts.get("extreme_long_rate") or 0.0) <= 0.01,
        "short_chunk_rate_bounded": float(counts.get("too_short_rate") or 0.0) <= 0.05,
        "long_chunk_rate_bounded": float(counts.get("too_long_rate") or 0.0) <= 0.08,
        "split_block_parts_complete": int(overlap.get("incomplete_split_block_count") or 0) == 0,
        "split_overlap_present": float(overlap.get("zero_overlap_pair_rate") or 0.0) <= 0.05,
        "primary_core_item_coverage_bounded": float(coverage.get("primary_core_item_missing_filing_rate") or 0.0) <= 0.02,
        "evidence_rows_match_chunks": str(evidence_parity.get("status") or "") in {"pass", "not_configured"},
        "evidence_ids_unique": int(evidence_parity.get("duplicate_evidence_id_count") or 0) == 0,
        "bm25_records_match_evidence": bool(index_parity.get("bm25_records_match_evidence")),
        "object_bm25_present": bool(index_parity.get("object_bm25_present")),
    }


def _quality_warnings(
    chunk_stats: Mapping[str, Any],
    evidence_parity: Mapping[str, Any],
    index_parity: Mapping[str, Any],
) -> list[str]:
    warnings = []
    counts = chunk_stats.get("quality_counts") if isinstance(chunk_stats.get("quality_counts"), Mapping) else {}
    table = chunk_stats.get("table_stats") if isinstance(chunk_stats.get("table_stats"), Mapping) else {}
    overlap = chunk_stats.get("overlap_stats") if isinstance(chunk_stats.get("overlap_stats"), Mapping) else {}
    coverage = chunk_stats.get("item_coverage") if isinstance(chunk_stats.get("item_coverage"), Mapping) else {}
    if float(counts.get("too_long_rate") or 0.0) > 0.03:
        warnings.append("long_chunk_tail_review_needed")
    if int(table.get("table_chunk_too_long_count") or 0) > 0:
        warnings.append("long_table_chunks_need_table_aware_review")
    if float(overlap.get("zero_overlap_pair_rate") or 0.0) > 0:
        warnings.append("some_split_pairs_have_zero_text_overlap")
    if int(coverage.get("core_item_missing_filing_count") or 0) > 0:
        warnings.append("some_filings_missing_expected_items")
    if str(evidence_parity.get("status") or "") == "not_configured":
        warnings.append("evidence_parity_not_checked")
    if not bool(index_parity.get("bm25_records_match_evidence_rows")):
        warnings.append("bm25_metadata_record_count_mismatch")
    return warnings


def _milvus_insertion_experiment(
    chunk_stats: Mapping[str, Any],
    checks: Mapping[str, bool],
    warnings: Iterable[str],
) -> dict[str, Any]:
    pymilvus_available = importlib.util.find_spec("pymilvus") is not None
    milvus_lite_available = importlib.util.find_spec("milvus_lite") is not None
    blocking_checks = sorted(name for name, value in checks.items() if value is False)
    if blocking_checks:
        decision = (
            "暂不进入 Milvus retrieval-only 实验；先修 S0 hard checks: "
            + ", ".join(blocking_checks)
            + "。"
        )
    elif not pymilvus_available:
        decision = "S0 资产可进入 Milvus retrieval-only 实验，但本机缺少 pymilvus / Milvus Lite，需先安装实验依赖。"
    elif "long_table_chunks_need_table_aware_review" in set(warnings):
        decision = "可以做 Milvus 诊断实验，但不能只看语义召回提升；必须同时检查长表格 chunk 对 exact-value ledger 的影响。"
    else:
        decision = "可以把 Milvus 作为语义召回实验层接入，不替代 BM25/ObjectBM25/exact ledger。"
    return {
        "decision": decision,
        "dependency_probe": {
            "pymilvus_available": pymilvus_available,
            "milvus_lite_available": milvus_lite_available,
        },
        "recommended_position": "Research Lead route -> BM25/ObjectBM25 + Milvus semantic recall -> BGE rerank -> evidence ledger -> Specialist",
        "collection_contract": {
            "primary_key": "evidence_id",
            "vector_text": "ticker, fiscal_year, section, subsection, evidence_type, topics, text",
            "metadata_filters": [
                "ticker",
                "fiscal_year",
                "form_type",
                "source_tier",
                "item_code",
                "category_slug",
                "period_type",
                "contains_table",
            ],
            "version_keys": ["chunks_sha256", "evidence_path", "embedding_model", "chunk_profile"],
        },
        "experiment_cases": [
            "exact lookup: MSFT capex, JPM credit provision",
            "semantic sector-depth: AI infra, utilities power-load, healthcare product cycle",
            "multi-turn paraphrase: narrowed scope follow-up with different wording",
        ],
        "success_metrics": [
            "target_in_top20 improves over BM25-only for semantic cases",
            "exact-value cases keep ledger hit rate unchanged",
            "BGE rerank top-k contains more usable evidence rows without raising hallucination gates",
            "latency and GPU/CPU cost stay within eval budget",
        ],
        "next_steps": [
            "Build a small Milvus/Lite collection from this audited evidence file.",
            "Run retrieval-only A/B: BM25/ObjectBM25 vs Milvus vs hybrid RRF before any LLM full-chain run.",
            "Promote only hybrid retrieval if semantic recall improves sector-depth cases and exact lookup does not regress.",
        ],
    }


def _new_state(*, max_examples: int) -> dict[str, Any]:
    return {
        "max_examples": max_examples,
        "chunk_count": 0,
        "chunk_ids": set(),
        "parse_error_count": 0,
        "missing_chunk_id_count": 0,
        "duplicate_chunk_id_count": 0,
        "too_short_count": 0,
        "too_long_count": 0,
        "extreme_long_count": 0,
        "contains_table_count": 0,
        "unbalanced_table_marker_count": 0,
        "table_chunk_too_long_count": 0,
        "invalid_char_boundary_count": 0,
        "outside_block_boundary_count": 0,
        "word_counts": [],
        "form_counts": Counter(),
        "item_counts": Counter(),
        "ticker_counts": Counter(),
        "source_tier_counts": Counter(),
        "split_block_ids": set(),
        "split_parts": defaultdict(list),
        "filings": defaultdict(lambda: {"items": set(), "chunk_count": 0}),
        "examples": defaultdict(list),
    }


def _iter_jsonl_lines(path: Path, *, limit: int = 0):
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            yield line_number, stripped
            if limit and line_number >= limit:
                break


def _tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]


def _common_suffix_prefix(left_tail: list[str], right_head: list[str]) -> int:
    max_len = min(len(left_tail), len(right_head), MAX_OVERLAP_TOKENS_TO_STORE)
    for size in range(max_len, 0, -1):
        if left_tail[-size:] == right_head[:size]:
            return size
    return 0


def _distribution(values: list[int]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "min": 0, "p05": 0, "p25": 0, "median": 0, "p75": 0, "p95": 0, "p99": 0, "max": 0, "mean": 0}
    sorted_values = sorted(values)
    return {
        "count": len(values),
        "min": sorted_values[0],
        "p05": _quantile(sorted_values, 0.05, presorted=True),
        "p25": _quantile(sorted_values, 0.25, presorted=True),
        "median": _quantile(sorted_values, 0.50, presorted=True),
        "p75": _quantile(sorted_values, 0.75, presorted=True),
        "p95": _quantile(sorted_values, 0.95, presorted=True),
        "p99": _quantile(sorted_values, 0.99, presorted=True),
        "max": sorted_values[-1],
        "mean": sum(sorted_values) / len(sorted_values),
    }


def _quantile(values: list[int], q: float, *, presorted: bool = False) -> float:
    if not values:
        return 0.0
    sorted_values = values if presorted else sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = (len(sorted_values) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = position - lower
    return float(sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction)


def _rate(count: int, total: int) -> float:
    return float(count) / float(total) if total else 0.0


def _profile_for_form(form_type: str) -> dict[str, int]:
    return PROFILE_BY_FORM.get(form_type, PROFILE_BY_FORM["10-K"])


def _chunk_example(row: Mapping[str, Any], line_number: int, word_count: int) -> dict[str, Any]:
    return {
        "chunk_id": row.get("chunk_id") or "",
        "ticker": row.get("ticker") or "",
        "fiscal_year": row.get("fiscal_year"),
        "form_type": row.get("form_type") or row.get("source_type") or "",
        "item_code": row.get("item_code") or "",
        "block_id": row.get("block_id") or "",
        "word_count": word_count,
        "line_number": line_number,
    }


def _add_example(state: dict[str, Any], bucket: str, example: Mapping[str, Any]) -> None:
    examples = state["examples"][bucket]
    if len(examples) < state["max_examples"]:
        examples.append(dict(example))


def _read_metadata(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _norm(value: Any) -> str:
    return str(value or "").strip().upper()


def _resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _optional_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    resolved = _resolve_path(path)
    return resolved if str(path) else None


def _default_run_id() -> str:
    return time.strftime("%Y%m%d_sec_chunk_quality_full238_v0_1")


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _stdout_summary(audit: Mapping[str, Any], json_path: Path, md_path: Path) -> dict[str, Any]:
    stats = audit.get("chunk_stats") if isinstance(audit.get("chunk_stats"), Mapping) else {}
    quality = stats.get("quality_counts") if isinstance(stats.get("quality_counts"), Mapping) else {}
    coverage = stats.get("item_coverage") if isinstance(stats.get("item_coverage"), Mapping) else {}
    return {
        "run_id": audit.get("run_id"),
        "gate_status": audit.get("gate_status"),
        "chunk_count": stats.get("chunk_count"),
        "ticker_count": stats.get("ticker_count"),
        "too_long_rate": quality.get("too_long_rate"),
        "primary_core_item_missing_filing_rate": coverage.get("primary_core_item_missing_filing_rate"),
        "failed_checks": audit.get("failed_checks"),
        "json_path": str(json_path),
        "md_path": str(md_path),
    }


if __name__ == "__main__":
    raise SystemExit(main())
