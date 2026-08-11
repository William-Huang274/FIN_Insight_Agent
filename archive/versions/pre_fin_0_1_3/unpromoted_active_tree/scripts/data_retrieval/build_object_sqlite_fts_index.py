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

from indexing.build_object_sqlite_fts_index import build_object_sqlite_fts_index  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a SQLite FTS5 structured object index.")
    parser.add_argument("--structured-dir", default="data/processed_private/structured_objects")
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--cpu-workers", type=int, default=0, help="Use up to this many CPU workers when --workers is not set.")
    parser.add_argument("--batch-bytes", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--insert-batch-size", type=int, default=5000)
    parser.add_argument("--progress-every", type=int, default=100000)
    parser.add_argument(
        "--sqlite-journal-mode",
        default="WAL",
        choices=["DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"],
        help="SQLite journal mode. Use MEMORY/OFF only for disposable temp builds.",
    )
    parser.add_argument(
        "--sqlite-synchronous",
        default="NORMAL",
        choices=["OFF", "NORMAL", "FULL", "EXTRA"],
        help="SQLite synchronous pragma. Use OFF only for disposable temp builds.",
    )
    parser.add_argument("--skip-fts-optimize", action="store_true", help="Skip final FTS5 optimize for faster temp builds.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workers = args.workers
    if args.cpu_workers and args.workers == 1:
        workers = max(1, min(int(args.cpu_workers), os.cpu_count() or 1))
    metadata = build_object_sqlite_fts_index(
        REPO_ROOT / args.structured_dir,
        REPO_ROOT / args.output_dir,
        prefix=args.prefix,
        workers=workers,
        batch_bytes=args.batch_bytes,
        insert_batch_size=args.insert_batch_size,
        progress_every=args.progress_every,
        journal_mode=args.sqlite_journal_mode,
        synchronous=args.sqlite_synchronous,
        optimize_fts=not args.skip_fts_optimize,
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
