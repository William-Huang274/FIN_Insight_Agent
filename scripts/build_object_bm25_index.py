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

from indexing.build_object_bm25_index import build_object_bm25_index  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build BM25 index from structured object JSONL.")
    parser.add_argument(
        "--structured-dir",
        default="data/processed_private/structured_objects",
    )
    parser.add_argument("--prefix", default="sec_tech_10k")
    parser.add_argument("--output-dir", default="data/indexes/bm25/sec_tech_10k_objects")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata = build_object_bm25_index(
        REPO_ROOT / args.structured_dir,
        REPO_ROOT / args.output_dir,
        prefix=args.prefix,
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
