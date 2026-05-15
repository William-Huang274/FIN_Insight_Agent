from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.hybrid_rrf_retriever import HybridRRFRetriever  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search BM25+dense hybrid RRF index.")
    parser.add_argument("query")
    parser.add_argument("--bm25-index-dir", default="data/indexes/bm25/sec_tech_10k")
    parser.add_argument("--dense-index-dir", default="data/indexes/dense/sec_tech_10k")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--bm25-top-k", type=int, default=30)
    parser.add_argument("--dense-top-k", type=int, default=30)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--ticker")
    parser.add_argument("--year", type=int)
    parser.add_argument("--device")
    parser.add_argument(
        "--include-record",
        action="store_true",
        help="Include the full EvidenceObject payload for each hit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    filters = {}
    if args.ticker:
        filters["ticker"] = args.ticker.upper()
    if args.year:
        filters["fiscal_year"] = args.year
    retriever = HybridRRFRetriever(
        REPO_ROOT / args.bm25_index_dir,
        REPO_ROOT / args.dense_index_dir,
        rrf_k=args.rrf_k,
        bm25_top_k=args.bm25_top_k,
        dense_top_k=args.dense_top_k,
        device=args.device,
    )
    results = retriever.search(args.query, top_k=args.top_k, filters=filters or None)
    if not args.include_record:
        for result in results:
            result.pop("record", None)
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
