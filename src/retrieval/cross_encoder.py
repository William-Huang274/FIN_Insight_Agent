from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Sequence

from .financial_objects import sha256_file
from .query_plan import canonical_digest


def cross_encoder_model_identity(
    model_dir: Path, *, model_id: str = "BAAI/bge-reranker-v2-m3"
) -> dict[str, Any]:
    files = [model_dir / "config.json", model_dir / "model.safetensors"]
    if not all(path.is_file() for path in files):
        raise ValueError("cross_encoder_model_files_missing")
    rows = [
        {"name": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in files
    ]
    body = {
        "model_id": model_id,
        "local_directory_name": model_dir.name,
        "files": rows,
    }
    return {**body, "model_digest": canonical_digest(body)}


def load_local_cross_encoder(
    model_dir: Path, *, maximum_sequence_length: int
) -> Any:
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(model_dir),
        local_files_only=True,
        dtype=torch.float16 if device.type == "cuda" else torch.float32,
    )
    model.to(device)
    model.eval()
    return tokenizer, model, device, maximum_sequence_length


def score_cross_encoder_pairs(
    runtime: Any,
    pairs: Sequence[tuple[str, str]],
    *,
    batch_size: int,
    progress_every: int | None = 100,
) -> list[float]:
    import torch

    tokenizer, model, device, maximum_sequence_length = runtime
    scores: list[float] = []
    for start in range(0, len(pairs), batch_size):
        batch = pairs[start : start + batch_size]
        encoded = tokenizer(
            [pair[0] for pair in batch],
            [pair[1] for pair in batch],
            padding=True,
            truncation=True,
            max_length=maximum_sequence_length,
            return_tensors="pt",
        )
        encoded = {key: value.to(device) for key, value in encoded.items()}
        with torch.inference_mode():
            logits = model(**encoded).logits.reshape(-1).float().cpu().tolist()
        scores.extend(float(value) for value in logits)
        if progress_every and start and start % progress_every == 0:
            print(f"scored_pairs={start}/{len(pairs)}", flush=True)
    return scores


__all__ = [
    "cross_encoder_model_identity",
    "load_local_cross_encoder",
    "score_cross_encoder_pairs",
]
