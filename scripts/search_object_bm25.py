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

from retrieval.object_bm25_retriever import ObjectBM25Retriever  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search a BM25 structured-object index.")
    parser.add_argument("query")
    parser.add_argument("--index-dir", default="data/indexes/bm25/sec_tech_10k_objects")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--ticker", action="append")
    parser.add_argument("--year", type=int)
    parser.add_argument("--object-type", action="append", choices=["table", "metric", "claim"])
    parser.add_argument("--include-record", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    filters = {}
    if args.ticker:
        filters["ticker"] = [ticker.upper() for ticker in args.ticker]
    if args.year:
        filters["fiscal_year"] = args.year
    if args.object_type:
        filters["object_type"] = args.object_type
    retriever = ObjectBM25Retriever(REPO_ROOT / args.index_dir)
    results = retriever.search(args.query, top_k=args.top_k, filters=filters or None)
    if not args.include_record:
        for result in results:
            result.pop("record", None)
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
