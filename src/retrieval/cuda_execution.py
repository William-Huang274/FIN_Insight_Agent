from __future__ import annotations

from typing import Any


def required_cuda_fp16_receipt(*, purpose: str) -> dict[str, Any]:
    """Fail closed unless learned retrieval can execute on CUDA in FP16.

    CPU remains valid for deterministic retrieval work such as BM25, SQL and
    hard filters.  This receipt is specifically for embedding and reranking.
    """

    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("learned_retrieval_cuda_runtime_missing") from exc
    if not torch.cuda.is_available():
        raise RuntimeError("learned_retrieval_cuda_required")

    device_index = int(torch.cuda.current_device())
    device = torch.device(f"cuda:{device_index}")
    properties = torch.cuda.get_device_properties(device_index)
    left = torch.tensor([[1.0, 2.0]], device=device, dtype=torch.float16)
    right = torch.tensor([[3.0], [4.0]], device=device, dtype=torch.float16)
    smoke = left @ right
    if smoke.device.type != "cuda" or smoke.dtype != torch.float16:
        raise RuntimeError("learned_retrieval_cuda_fp16_smoke_invalid")
    if not bool(torch.isfinite(smoke).all().item()):
        raise RuntimeError("learned_retrieval_cuda_fp16_smoke_nonfinite")

    return {
        "purpose": purpose,
        "execution_device": str(device),
        "device_name": str(properties.name),
        "compute_capability": [int(properties.major), int(properties.minor)],
        "total_memory_bytes": int(properties.total_memory),
        "torch_version": str(torch.__version__),
        "cuda_runtime_version": str(torch.version.cuda or ""),
        "embedding_precision": "fp16",
        "reranker_precision": "fp16",
        "fp16_smoke_device": str(smoke.device),
        "fp16_smoke_dtype": str(smoke.dtype).replace("torch.", ""),
        "fp16_smoke_value": float(smoke.item()),
        "cpu_fallback_allowed": False,
        "failure_policy": "fail_closed_before_model_load",
    }


__all__ = ["required_cuda_fp16_receipt"]
