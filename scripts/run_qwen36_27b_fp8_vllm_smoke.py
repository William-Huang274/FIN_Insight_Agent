from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _gpu_snapshot() -> list[dict[str, str]]:
    query = "name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu"
    cmd = ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"]
    try:
        proc = subprocess.run(cmd, check=True, text=True, capture_output=True)
    except Exception as exc:  # pragma: no cover - depends on cloud GPU host.
        return [{"error": repr(exc)}]

    fields = [
        "name",
        "memory_total_mib",
        "memory_used_mib",
        "memory_free_mib",
        "utilization_gpu_percent",
        "temperature_gpu_c",
    ]
    rows: list[dict[str, str]] = []
    for line in proc.stdout.splitlines():
        values = [part.strip() for part in line.split(",")]
        rows.append(dict(zip(fields, values)))
    return rows


def _read_model_config(model_path: Path) -> dict[str, Any]:
    config_path = model_path / "config.json"
    if not config_path.exists():
        return {"config_path": str(config_path), "exists": False}
    config = json.loads(config_path.read_text(encoding="utf-8"))
    quant = config.get("quantization_config") or {}
    return {
        "config_path": str(config_path),
        "exists": True,
        "model_type": config.get("model_type"),
        "architectures": config.get("architectures"),
        "torch_dtype": config.get("torch_dtype"),
        "max_position_embeddings": config.get("max_position_embeddings"),
        "quantization_method": quant.get("quant_method"),
        "quantization_fmt": quant.get("fmt"),
        "activation_scheme": quant.get("activation_scheme"),
    }


def _package_versions() -> dict[str, Any]:
    versions: dict[str, Any] = {"python": sys.version.split()[0]}
    try:
        import torch

        versions.update(
            {
                "torch": torch.__version__,
                "cuda": torch.version.cuda,
                "cuda_available": torch.cuda.is_available(),
                "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                "gpu_capability": torch.cuda.get_device_capability(0) if torch.cuda.is_available() else None,
            }
        )
    except Exception as exc:  # pragma: no cover
        versions["torch_error"] = repr(exc)
    try:
        import transformers

        versions["transformers"] = transformers.__version__
    except Exception as exc:  # pragma: no cover
        versions["transformers_error"] = repr(exc)
    try:
        import vllm

        versions["vllm"] = getattr(vllm, "__version__", None)
    except Exception as exc:  # pragma: no cover
        versions["vllm_error"] = repr(exc)
    return versions


def _build_prompt(prompt: str) -> str:
    return prompt


def run(args: argparse.Namespace) -> dict[str, Any]:
    os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
    os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")

    model_path = Path(args.model_path)
    if not model_path.is_absolute():
        model_path = (REPO_ROOT / model_path).resolve()

    report: dict[str, Any] = {
        "run_id": args.run_id,
        "status": "started",
        "started_at_utc": _utc_now(),
        "model_path": str(model_path),
        "model_config": _read_model_config(model_path),
        "environment": {
            "cwd": str(Path.cwd()),
            "env": {
                "TORCHDYNAMO_DISABLE": os.environ.get("TORCHDYNAMO_DISABLE"),
                "VLLM_USE_FLASHINFER_SAMPLER": os.environ.get("VLLM_USE_FLASHINFER_SAMPLER"),
            },
            "packages": _package_versions(),
        },
        "gpu_before": _gpu_snapshot(),
        "vllm_args": {
            "dtype": args.dtype,
            "quantization": args.quantization,
            "max_model_len": args.max_model_len,
            "max_num_seqs": args.max_num_seqs,
            "gpu_memory_utilization": args.gpu_memory_utilization,
            "cpu_offload_gb": args.cpu_offload_gb,
            "enforce_eager": args.enforce_eager,
            "language_model_only": args.language_model_only,
            "skip_mm_profiling": args.skip_mm_profiling,
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
            "enable_thinking_template": args.enable_thinking_template,
        },
    }

    started = time.perf_counter()
    try:
        from transformers import AutoTokenizer
        from vllm import LLM, SamplingParams

        python_bin = str(Path(sys.executable).resolve().parent)
        os.environ["PATH"] = python_bin + os.pathsep + os.environ.get("PATH", "")

        tokenizer_started = time.perf_counter()
        tokenizer = AutoTokenizer.from_pretrained(str(model_path), trust_remote_code=True)
        report["tokenizer_seconds"] = round(time.perf_counter() - tokenizer_started, 4)

        llm_kwargs: dict[str, Any] = {
            "model": str(model_path),
            "tokenizer": str(model_path),
            "trust_remote_code": True,
            "dtype": args.dtype,
            "max_model_len": args.max_model_len,
            "max_num_seqs": args.max_num_seqs,
            "gpu_memory_utilization": args.gpu_memory_utilization,
            "cpu_offload_gb": args.cpu_offload_gb,
            "enforce_eager": args.enforce_eager,
        }
        if args.quantization and args.quantization.lower() not in {"auto", "none", "null"}:
            llm_kwargs["quantization"] = args.quantization
        if args.language_model_only:
            llm_kwargs["language_model_only"] = True
        if args.skip_mm_profiling:
            llm_kwargs["skip_mm_profiling"] = True

        load_started = time.perf_counter()
        llm = LLM(**llm_kwargs)
        report["load_seconds"] = round(time.perf_counter() - load_started, 4)
        report["gpu_after_load"] = _gpu_snapshot()

        prompt = _build_prompt(args.prompt)
        if getattr(tokenizer, "chat_template", None):
            prompt = tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=args.enable_thinking_template,
            )
        sampling = SamplingParams(
            temperature=args.temperature,
            top_p=1.0,
            max_tokens=args.max_tokens,
        )

        generation_started = time.perf_counter()
        outputs = llm.generate([prompt], sampling)
        generation_seconds = time.perf_counter() - generation_started
        completion = outputs[0].outputs[0]
        token_count = len(getattr(completion, "token_ids", []) or [])

        report.update(
            {
                "status": "success",
                "generate_seconds": round(generation_seconds, 4),
                "output_tokens": token_count,
                "tokens_per_second": round(token_count / generation_seconds, 4)
                if generation_seconds and token_count
                else None,
                "finish_reason": getattr(completion, "finish_reason", None),
                "output_text": completion.text.strip(),
                "gpu_after_generate": _gpu_snapshot(),
            }
        )
    except Exception as exc:
        report.update(
            {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "gpu_after_failure": _gpu_snapshot(),
            }
        )
    finally:
        report["ended_at_utc"] = _utc_now()
        report["wall_seconds"] = round(time.perf_counter() - started, 4)

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="20260520_qwen36_27b_fp8_5090_vllm_smoke_4k_r0")
    parser.add_argument(
        "--model-path",
        default="data/models_private/modelscope/Qwen/Qwen3___6-27B-FP8",
    )
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--dtype", default="auto")
    parser.add_argument("--quantization", default="fp8")
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--max-num-seqs", type=int, default=1)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.88)
    parser.add_argument("--cpu-offload-gb", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--prompt",
        default=(
            "You are a careful financial analysis assistant. "
            "Answer in one concise English sentence: what does gross margin measure?"
        ),
    )
    parser.add_argument("--enable-thinking-template", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--enforce-eager", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--language-model-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--skip-mm-profiling", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run(args)
    output_path = Path(args.output_path)
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
