from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from evidence import read_evidence_jsonl
from retrieval.text import evidence_search_text


def build_dense_index(
    evidence_path: str | Path,
    output_dir: str | Path,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    batch_size: int = 64,
    device: str | None = None,
) -> dict:
    from sentence_transformers import SentenceTransformer

    evidence_objects = read_evidence_jsonl(evidence_path)
    records = [obj.model_dump(mode="json") for obj in evidence_objects]
    texts = [evidence_search_text(record) for record in records]

    model = SentenceTransformer(model_name, device=device)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    ).astype("float32")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    np.save(output_path / "embeddings.npy", embeddings)
    with (output_path / "records.jsonl").open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False))
            f.write("\n")
    metadata = {
        "evidence_path": str(evidence_path),
        "records": len(records),
        "index_type": "dense_numpy_cosine",
        "model_name": model_name,
        "embedding_dim": int(embeddings.shape[1]) if embeddings.size else 0,
        "normalized": True,
    }
    (output_path / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return metadata
