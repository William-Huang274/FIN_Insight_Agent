from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from indexing.build_bm25_index import build_bm25_index  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build BM25 index from EvidenceObject JSONL.")
    parser.add_argument(
        "--evidence",
        default="data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl",
    )
    parser.add_argument("--output-dir", default="data/indexes/bm25/sec_tech_10k")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--progress-every", type=int, default=50000)
    parser.add_argument(
        "--validate-schema",
        action="store_true",
        help="Validate EvidenceObject schema while indexing. Slower; upstream evidence build usually owns validation.",
    )
    parser.add_argument("--cpu-workers", type=int, default=0, help="Use up to this many CPU workers when --workers is not set.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workers = args.workers
    if args.cpu_workers and args.workers == 1:
        workers = max(1, min(int(args.cpu_workers), os.cpu_count() or 1))
    metadata = build_bm25_index(
        REPO_ROOT / args.evidence,
        REPO_ROOT / args.output_dir,
        workers=workers,
        batch_size=args.batch_size,
        progress_every=args.progress_every,
        validate_schema=args.validate_schema,
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
