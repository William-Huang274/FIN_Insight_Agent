from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sec_agent.entities.entity_resolution import build_entity_alias_registry
from sec_agent.relationships.sec_edge_extractor import extract_relationship_edges_from_evidence

DEFAULT_EVIDENCE_PATH = Path(
    "Z:/FIN_Insight_Agent_artifacts/evidence_objects/"
    "sector_depth_full238_us_v0_5_mixed_with_8k_evidence_fy2023_2027.jsonl"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "staging" / "relationships"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract deterministic relationship edge candidates from SEC evidence rows.")
    parser.add_argument("--evidence-path", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--universe-manifest", type=Path, default=None)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_DIR / "full238_relationship_edge_candidates_v0_1.jsonl")
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_OUTPUT_DIR / "full238_relationship_edge_candidates_summary_v0_1.json")
    parser.add_argument("--ticker", action="append", default=[], help="Optional source ticker filter. Repeatable.")
    parser.add_argument("--target-company-count", type=int, default=238, help="Diagnostic label only; extraction follows available evidence rows.")
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--max-candidates", type=int, default=0)
    parser.add_argument("--progress-every", type=int, default=50000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    evidence_path = _resolve(args.evidence_path)
    output_path = _resolve(args.output_path)
    summary_path = _resolve(args.summary_output)
    registry = _load_entity_registry(args.universe_manifest)
    ticker_filter = {ticker.upper().strip() for ticker in args.ticker if str(ticker).strip()}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    seen_rows = 0
    scanned_rows = 0
    written = 0
    source_tickers: Counter[str] = Counter()
    relation_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    with evidence_path.open("r", encoding="utf-8") as source, output_path.open("w", encoding="utf-8", newline="\n") as sink:
        for line in source:
            if not line.strip():
                continue
            seen_rows += 1
            row = json.loads(line)
            ticker = str(row.get("ticker") or "").upper().strip()
            if ticker_filter and ticker not in ticker_filter:
                continue
            scanned_rows += 1
            for edge in extract_relationship_edges_from_evidence(row, entity_registry=registry):
                sink.write(json.dumps(edge, ensure_ascii=False, sort_keys=True) + "\n")
                written += 1
                source_tickers[edge.get("source_ticker") or ""] += 1
                relation_counts[edge.get("relation_type") or "unknown"] += 1
                confidence_counts[edge.get("confidence") or "unknown"] += 1
                if args.max_candidates and written >= args.max_candidates:
                    break
            if args.max_candidates and written >= args.max_candidates:
                break
            if args.max_rows and scanned_rows >= args.max_rows:
                break
            if args.progress_every > 0 and scanned_rows and scanned_rows % args.progress_every == 0:
                print(json.dumps({"scanned_rows": scanned_rows, "candidates": written}, ensure_ascii=False))

    summary = {
        "schema_version": "fin_agent_relationship_edge_extraction_summary_v0.1",
        "status": "completed",
        "evidence_path": str(evidence_path),
        "output_path": str(output_path),
        "target_company_count": args.target_company_count,
        "available_evidence_rows_seen": seen_rows,
        "scanned_rows": scanned_rows,
        "candidate_count": written,
        "ticker_filter": sorted(ticker_filter),
        "entity_registry_rows": len(registry),
        "relation_type_counts": dict(sorted(relation_counts.items())),
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "top_source_tickers": source_tickers.most_common(25),
        "scope_note": "Target company count is a pool label; extraction only covers rows present in evidence_path.",
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _load_entity_registry(path: Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    resolved = _resolve(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Universe manifest not found: {resolved}")
    companies: list[Mapping[str, Any]] = []
    with resolved.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                companies.append(json.loads(line))
    return build_entity_alias_registry(companies)


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
