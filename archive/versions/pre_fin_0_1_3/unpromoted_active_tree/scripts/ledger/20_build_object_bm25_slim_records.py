from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from indexing.build_object_bm25_index import compact_structured_object_record  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build slim ObjectBM25 records companion file without rebuilding bm25.pkl.")
    parser.add_argument("--index-dir", required=True, help="ObjectBM25 index directory containing records.jsonl.")
    parser.add_argument("--output-name", default="records.slim.pkl")
    parser.add_argument("--write-jsonl", action="store_true", help="Also write records.slim.jsonl for debugging.")
    parser.add_argument("--max-records", type=int, default=0, help="Optional diagnostic cap.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.perf_counter()
    index_dir = _repo_path(args.index_dir)
    source_path = index_dir / "records.jsonl"
    output_path = index_dir / args.output_name
    jsonl_path = index_dir / "records.slim.jsonl"
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    count = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_handle = jsonl_path.open("w", encoding="utf-8") if args.write_jsonl else None
    with output_path.open("wb") as out:
        for record in _iter_jsonl(source_path):
            compact = compact_structured_object_record(record)
            pickle.dump(compact, out, protocol=pickle.HIGHEST_PROTOCOL)
            if jsonl_handle is not None:
                jsonl_handle.write(json.dumps(compact, ensure_ascii=False))
                jsonl_handle.write("\n")
            count += 1
            if args.max_records and count >= args.max_records:
                break
    if jsonl_handle is not None:
        jsonl_handle.close()
    summary = {
        "status": "completed",
        "source_path": str(source_path),
        "output_path": str(output_path),
        "jsonl_path": str(jsonl_path) if args.write_jsonl else "",
        "records": count,
        "source_bytes": source_path.stat().st_size,
        "output_bytes": output_path.stat().st_size,
        "jsonl_bytes": jsonl_path.stat().st_size if args.write_jsonl and jsonl_path.exists() else 0,
        "elapsed_sec": round(time.perf_counter() - started, 3),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
