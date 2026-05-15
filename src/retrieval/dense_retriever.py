from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


class DenseRetriever:
    def __init__(self, index_dir: str | Path, device: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        path = Path(index_dir)
        self.metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
        self.records = [
            json.loads(line)
            for line in (path / "records.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.embeddings = np.load(path / "embeddings.npy")
        self.model = SentenceTransformer(self.metadata["model_name"], device=device)
        if self.metadata.get("max_seq_length") is not None:
            self.model.max_seq_length = int(self.metadata["max_seq_length"])
        self.query_prompt_name = self.metadata.get("query_prompt_name")

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        encode_kwargs = {
            "convert_to_numpy": True,
            "normalize_embeddings": True,
            "show_progress_bar": False,
        }
        if self.query_prompt_name:
            encode_kwargs["prompt_name"] = self.query_prompt_name
        query_embedding = self.model.encode([query], **encode_kwargs).astype("float32")[0]
        scores = self.embeddings @ query_embedding

        candidate_indices = self._filtered_indices(filters)
        if candidate_indices is None:
            candidate_indices = range(len(self.records))

        ranked = sorted(
            ((idx, float(scores[idx])) for idx in candidate_indices),
            key=lambda item: item[1],
            reverse=True,
        )[:top_k]
        return [self._format_result(idx, score, rank) for rank, (idx, score) in enumerate(ranked, start=1)]

    def _filtered_indices(self, filters: dict[str, Any] | None):
        if not filters:
            return None
        indices = []
        for idx, record in enumerate(self.records):
            if _record_matches(record, filters):
                indices.append(idx)
        return indices

    def _format_result(self, idx: int, score: float, rank: int) -> dict[str, Any]:
        record = self.records[idx]
        return {
            "rank": rank,
            "score": score,
            "evidence_id": record["evidence_id"],
            "ticker": record["ticker"],
            "fiscal_year": record.get("fiscal_year"),
            "section": record.get("section"),
            "subsection": record.get("subsection"),
            "evidence_type": record.get("evidence_type"),
            "contains_table": record.get("metadata", {}).get("contains_table", False),
            "text_preview": _preview(record.get("text", "")),
            "record": record,
        }


def _record_matches(record: dict[str, Any], filters: dict[str, Any]) -> bool:
    metadata = record.get("metadata", {})
    for key, expected in filters.items():
        actual = metadata.get(key, record.get(key))
        if isinstance(expected, (list, tuple, set)):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def _preview(text: str, max_chars: int = 280) -> str:
    text = " ".join(text.split())
    return text[:max_chars] + ("..." if len(text) > max_chars else "")
