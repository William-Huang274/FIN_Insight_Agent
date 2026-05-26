from __future__ import annotations

import json
import pickle
from pathlib import Path

from rank_bm25 import BM25Okapi

from evidence import read_evidence_jsonl
from retrieval.text import evidence_search_text, tokenize


def build_bm25_index(
    evidence_path: str | Path,
    output_dir: str | Path,
) -> dict:
    evidence_objects = read_evidence_jsonl(evidence_path)
    records = [obj.model_dump(mode="json") for obj in evidence_objects]
    tokenized_corpus = [tokenize(evidence_search_text(record)) for record in records]
    bm25 = BM25Okapi(tokenized_corpus)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    with (output_path / "bm25.pkl").open("wb") as f:
        pickle.dump(bm25, f)
    with (output_path / "records.jsonl").open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False))
            f.write("\n")
    metadata = {
        "evidence_path": str(evidence_path),
        "records": len(records),
        "index_type": "rank_bm25",
    }
    (output_path / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return metadata
