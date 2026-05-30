from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from indexing.build_object_bm25_index import build_object_bm25_index  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build BM25 index from structured object JSONL.")
    parser.add_argument(
        "--structured-dir",
        default="data/processed_private/structured_objects",
    )
    parser.add_argument("--prefix", default="sec_tech_10k")
    parser.add_argument("--output-dir", default="data/indexes/bm25/sec_tech_10k_objects")
    parser.add_argument(
        "--record-mode",
        choices=["full", "compact"],
        default="full",
        help="full writes legacy records.jsonl; compact writes only slim records for DuckDB-backed runtime.",
    )
    parser.add_argument(
        "--no-slim-jsonl",
        action="store_true",
        help="Skip records.slim.jsonl and write only records.slim.pkl.",
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--cpu-workers", type=int, default=0, help="Use up to this many CPU workers when --workers is not set.")
    parser.add_argument("--batch-bytes", type=int, default=32 * 1024 * 1024)
    parser.add_argument("--progress-every", type=int, default=100000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workers = args.workers
    if args.cpu_workers and args.workers == 1:
        workers = max(1, min(int(args.cpu_workers), os.cpu_count() or 1))
    metadata = build_object_bm25_index(
        REPO_ROOT / args.structured_dir,
        REPO_ROOT / args.output_dir,
        prefix=args.prefix,
        record_mode=args.record_mode,
        write_slim_jsonl=not args.no_slim_jsonl,
        workers=workers,
        batch_bytes=args.batch_bytes,
        progress_every=args.progress_every,
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
