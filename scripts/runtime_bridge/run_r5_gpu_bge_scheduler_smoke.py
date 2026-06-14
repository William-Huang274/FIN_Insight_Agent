from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.runtime_bridge.resource_scheduler import InferenceTask, schedule_inference_tasks_with_audit


DEFAULT_MODEL = Path("D:/hf_cache/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181")


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report = run_smoke(args)
    out = output_dir / "r5_gpu_bge_scheduler_smoke_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    started = time.monotonic()
    tasks = [
        InferenceTask(f"bge_task_{idx:02d}", route="retrieval", priority=idx, requires_cuda_bge=True, can_spill_to_cpu=args.cpu_spillover_allowed)
        for idx in range(1, args.task_count + 1)
    ]
    tasks.append(InferenceTask("lead_review", route="deterministic_gate", priority=args.task_count + 1))
    tasks.append(InferenceTask("memo_writer", route="memo_writer", priority=args.task_count + 2, model_tier="pro"))
    audit = schedule_inference_tasks_with_audit(
        tasks,
        cuda_bge_slots=args.cuda_slots,
        cpu_spillover_allowed=args.cpu_spillover_allowed,
        token_budget_pressure=args.token_budget_pressure,
        per_cuda_task_wait_ms=args.per_cuda_task_wait_ms,
    )
    cuda_info = _cuda_info()
    model_run: dict[str, Any] = {"status": "skipped", "reason": "model_smoke_disabled"}
    if args.run_model_smoke:
        model_run = _run_model_smoke(args, cuda_info=cuda_info)
    errors = []
    lane_counts = audit.lane_counts
    if lane_counts.get("bge_cuda", 0) != min(args.cuda_slots, args.task_count):
        errors.append({"type": "cuda_slot_assignment_mismatch", "lane_counts": lane_counts})
    if args.task_count > args.cuda_slots and args.cpu_spillover_allowed and lane_counts.get("bge_cpu_spillover", 0) <= 0:
        errors.append({"type": "cpu_spillover_not_recorded", "lane_counts": lane_counts})
    if args.run_model_smoke and model_run.get("status") != "pass":
        errors.append({"type": "model_smoke_failed", "model_run": model_run})
    if args.require_cuda and not cuda_info.get("cuda_available"):
        errors.append({"type": "cuda_required_but_unavailable", "cuda_info": cuda_info})
    return {
        "schema_version": "finsight_r5_gpu_bge_scheduler_smoke_v0_1",
        "status": "fail" if errors else "pass",
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "policy": {
            "cuda_slots": args.cuda_slots,
            "task_count": args.task_count,
            "cpu_spillover_allowed": args.cpu_spillover_allowed,
            "token_budget_pressure": args.token_budget_pressure,
            "resident_model_cache_policy": "single_process_lru_model_cache_smoke_v0_1",
        },
        "cuda_info": cuda_info,
        "scheduler_audit": audit.__dict__,
        "model_run": model_run,
        "errors": errors,
    }


def _run_model_smoke(args: argparse.Namespace, *, cuda_info: dict[str, Any]) -> dict[str, Any]:
    model_path = args.model.resolve()
    device = args.device
    if device == "auto":
        device = "cuda" if cuda_info.get("cuda_available") else "cpu"
    if device == "cuda" and not cuda_info.get("cuda_available"):
        return {"status": "fail", "error": "cuda_requested_but_unavailable", "device": device}
    if not model_path.exists():
        return {"status": "fail", "error": "model_path_missing", "model_path": str(model_path)}
    try:
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("TQDM_DISABLE", "1")
        from sentence_transformers import SentenceTransformer
        import torch
    except Exception as exc:  # noqa: BLE001
        return {"status": "fail", "error": f"dependency_import_failed:{type(exc).__name__}:{exc}"}

    load_started = time.monotonic()
    before = _cuda_memory()
    model = SentenceTransformer(str(model_path), device=device)
    load_ms = int((time.monotonic() - load_started) * 1000)
    first_started = time.monotonic()
    first = model.encode(
        ["AI infrastructure capex demand signal", "cloud data center GPU server supply chain"],
        batch_size=2,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    first_ms = int((time.monotonic() - first_started) * 1000)
    second_started = time.monotonic()
    second = model.encode(
        ["AI infrastructure capex demand signal", "cloud data center GPU server supply chain"],
        batch_size=2,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    second_ms = int((time.monotonic() - second_started) * 1000)
    after = _cuda_memory()
    if device == "cuda":
        torch.cuda.synchronize()
    return {
        "status": "pass" if len(first) == 2 and len(second) == 2 else "fail",
        "model_path": str(model_path),
        "device": device,
        "load_ms": load_ms,
        "first_encode_ms": first_ms,
        "second_encode_ms": second_ms,
        "cache_hit_proxy": second_ms <= max(first_ms * 2, first_ms + 250),
        "embedding_dim": int(first.shape[1]) if hasattr(first, "shape") and len(first.shape) > 1 else 0,
        "cuda_memory_before": before,
        "cuda_memory_after": after,
    }


def _cuda_info() -> dict[str, Any]:
    try:
        import torch

        info: dict[str, Any] = {"cuda_available": bool(torch.cuda.is_available()), "torch_version": str(torch.__version__)}
        if torch.cuda.is_available():
            info.update(
                {
                    "device_count": int(torch.cuda.device_count()),
                    "device_name": torch.cuda.get_device_name(0),
                    "memory": _cuda_memory(),
                }
            )
        return info
    except Exception as exc:  # noqa: BLE001
        return {"cuda_available": False, "error": f"{type(exc).__name__}: {exc}"}


def _cuda_memory() -> dict[str, Any]:
    try:
        import torch

        if not torch.cuda.is_available():
            return {}
        return {
            "allocated_mb": round(torch.cuda.memory_allocated() / 1024 / 1024, 2),
            "reserved_mb": round(torch.cuda.memory_reserved() / 1024 / 1024, 2),
            "max_allocated_mb": round(torch.cuda.max_memory_allocated() / 1024 / 1024, 2),
            "max_reserved_mb": round(torch.cuda.max_memory_reserved() / 1024 / 1024, 2),
        }
    except Exception:
        return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run R5 GPU BGE queue/scheduler smoke.")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "reports" / "quality" / "r5_gpu_bge_scheduler_smoke")
    parser.add_argument("--model", type=Path, default=Path(os.environ.get("MILVUS_EMBEDDING_MODEL", str(DEFAULT_MODEL))))
    parser.add_argument("--device", default=os.environ.get("MILVUS_EMBEDDING_DEVICE", "auto"), choices=("auto", "cuda", "cpu"))
    parser.add_argument("--cuda-slots", type=int, default=3)
    parser.add_argument("--task-count", type=int, default=6)
    parser.add_argument("--per-cuda-task-wait-ms", type=int, default=250)
    parser.add_argument("--cpu-spillover-allowed", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--token-budget-pressure", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--run-model-smoke", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--require-cuda", action=argparse.BooleanOptionalAction, default=False)
    return parser.parse_args()


if __name__ == "__main__":
    main()
