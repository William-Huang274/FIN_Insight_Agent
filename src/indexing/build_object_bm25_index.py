from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from evidence.structured_text import structured_object_search_text
from retrieval.text import tokenize


def build_object_bm25_index(
    structured_dir: str | Path,
    output_dir: str | Path,
    prefix: str = "sec_tech_10k",
) -> dict[str, Any]:
    structured_path = Path(structured_dir)
    records = []
    for suffix in ("tables", "metrics", "claims"):
        path = structured_path / f"{prefix}_{suffix}.jsonl"
        records.extend(_read_jsonl(path))

    tokenized_corpus = [tokenize(structured_object_search_text(record)) for record in records]
    bm25 = BM25Okapi(tokenized_corpus)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    with (output_path / "bm25.pkl").open("wb") as f:
        pickle.dump(bm25, f)
    with (output_path / "records.jsonl").open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False))
            f.write("\n")

    counts: dict[str, int] = {"table": 0, "metric": 0, "claim": 0}
    for record in records:
        object_type = record.get("object_type")
        if object_type in counts:
            counts[object_type] += 1

    metadata = {
        "structured_dir": str(structured_path),
        "prefix": prefix,
        "records": len(records),
        "object_counts": counts,
        "index_type": "rank_bm25",
    }
    (output_path / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return metadata


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
    return rows
