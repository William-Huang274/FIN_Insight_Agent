from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Sequence

from .financial_objects import sha256_file
from .query_plan import canonical_digest


def _required_cuda_device(torch: Any) -> Any:
    """Fail closed instead of silently moving financial reranking to CPU."""

    if not torch.cuda.is_available():
        raise RuntimeError("local_cross_encoder_cuda_required")
    return torch.device("cuda")


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

    device = _required_cuda_device(torch)
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(model_dir),
        local_files_only=True,
        dtype=torch.float16,
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


def load_local_qwen3_reranker(
    model_dir: Path,
    *,
    maximum_sequence_length: int,
    instruction: str,
) -> Any:
    """Load Qwen3 Reranker through its official yes/no causal-LM surface."""

    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = _required_cuda_device(torch)
    tokenizer = AutoTokenizer.from_pretrained(
        str(model_dir),
        padding_side="left",
        local_files_only=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        str(model_dir),
        local_files_only=True,
        dtype=torch.float16,
    )
    model.to(device)
    model.eval()
    false_token_id = tokenizer.convert_tokens_to_ids("no")
    true_token_id = tokenizer.convert_tokens_to_ids("yes")
    prefix = (
        '<|im_start|>system\nJudge whether the Document meets the requirements '
        'based on the Query and the Instruct provided. Note that the answer can '
        'only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
    )
    suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    prefix_tokens = tokenizer.encode(prefix, add_special_tokens=False)
    suffix_tokens = tokenizer.encode(suffix, add_special_tokens=False)
    if maximum_sequence_length <= len(prefix_tokens) + len(suffix_tokens) + 32:
        raise ValueError("qwen3_reranker_sequence_budget_invalid")
    return (
        tokenizer,
        model,
        device,
        maximum_sequence_length,
        instruction.strip(),
        false_token_id,
        true_token_id,
        prefix_tokens,
        suffix_tokens,
    )


def score_qwen3_reranker_pairs(
    runtime: Any,
    pairs: Sequence[tuple[str, str]],
    *,
    batch_size: int,
) -> list[float]:
    import torch

    if not pairs:
        return []
    (
        tokenizer,
        model,
        device,
        maximum_sequence_length,
        instruction,
        false_token_id,
        true_token_id,
        prefix_tokens,
        suffix_tokens,
    ) = runtime
    formatted = [
        f"<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {document}"
        for query, document in pairs
    ]
    scores: list[float] = []
    content_budget = maximum_sequence_length - len(prefix_tokens) - len(suffix_tokens)
    for start in range(0, len(formatted), batch_size):
        tokenized = tokenizer(
            formatted[start : start + batch_size],
            padding=False,
            truncation="longest_first",
            return_attention_mask=False,
            max_length=content_budget,
        )
        tokenized["input_ids"] = [
            prefix_tokens + row + suffix_tokens for row in tokenized["input_ids"]
        ]
        encoded = tokenizer.pad(tokenized, padding=True, return_tensors="pt")
        encoded = {key: value.to(device) for key, value in encoded.items()}
        with torch.inference_mode():
            logits = model(**encoded).logits[:, -1, :]
            values = logits[:, true_token_id] - logits[:, false_token_id]
        scores.extend(float(value) for value in values.float().cpu().tolist())
    return scores


__all__ = [
    "cross_encoder_model_identity",
    "load_local_cross_encoder",
    "load_local_qwen3_reranker",
    "score_cross_encoder_pairs",
    "score_qwen3_reranker_pairs",
]
