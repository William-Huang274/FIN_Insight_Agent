from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import vllm_hardware_profiles  # noqa: E402


VALID_LABELS = {"direct", "partial", "false"}
PROMPT_VERSION = "qwen_small_object_verifier_vllm_v0.1"

SYSTEM_PROMPT = (
    "You are a strict financial evidence verifier for SEC 10-K retrieval. "
    "Classify whether one structured evidence object supports one research aspect. "
    "Use only the provided evidence object. Return valid JSON only."
)

VERIFIER_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["label", "confidence", "usable_for_synthesis"],
    "properties": {
        "label": {"type": "string", "enum": ["direct", "partial", "false"]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "usable_for_synthesis": {"type": "boolean"},
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a Qwen-style verifier with vLLM batched generation."
    )
    parser.add_argument(
        "--input-path",
        default="reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_bge_aspect_evidence_pool.jsonl",
    )
    parser.add_argument(
        "--output-path",
        default="reports/verifier/sec_tech_10k_expanded_v0_2_cell_qwen35_2b_aspect_verifier_vllm.jsonl",
    )
    parser.add_argument("--model-path", default="data/models_private/modelscope/Qwen/Qwen3___5-2B")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--max-num-seqs", type=int, default=64)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.86)
    parser.add_argument("--cpu-offload-gb", type=float, default=0.0)
    parser.add_argument("--prompt-batch-size", type=int, default=512)
    parser.add_argument("--max-new-tokens", type=int, default=48)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--object-text-chars", type=int, default=1800)
    parser.add_argument("--structured-json", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--enforce-eager", action=argparse.BooleanOptionalAction, default=False)
    vllm_hardware_profiles.add_hardware_profile_arg(parser)
    args = parser.parse_args()
    vllm_hardware_profiles.apply_hardware_profile(args, workload="small_verifier")
    return args


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    rows = list(_read_jsonl(REPO_ROOT / args.input_path))
    if args.limit > 0:
        rows = rows[: args.limit]

    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completed = _completed_keys(output_path) if args.resume else set()
    rows_to_run = [row for row in rows if _row_key(row) not in completed]

    load_started = time.perf_counter()
    llm, tokenizer = _load_vllm(args)
    load_seconds = time.perf_counter() - load_started

    mode = "a" if args.resume else "w"
    written = 0
    generation_started = time.perf_counter()
    with output_path.open(mode, encoding="utf-8") as f:
        for batch_index, batch in enumerate(_batches(rows_to_run, args.prompt_batch_size), start=1):
            prompts = [_format_prompt(row, tokenizer, object_text_chars=args.object_text_chars) for row in batch]
            raw_outputs = _generate(llm, prompts, args)
            for row, prompt, raw_output in zip(batch, prompts, raw_outputs):
                parsed = _parse_verifier_json(raw_output)
                f.write(
                    json.dumps(
                        _prediction_row(
                            row=row,
                            parsed=parsed,
                            raw_output=raw_output,
                            prompt_chars=len(prompt),
                            model_path=str((REPO_ROOT / args.model_path).resolve())
                            if not Path(args.model_path).is_absolute()
                            else args.model_path,
                        ),
                        ensure_ascii=False,
                    )
                )
                f.write("\n")
                written += 1
            f.flush()
            print(
                json.dumps(
                    {
                        "batch": batch_index,
                        "written": written,
                        "total_to_run": len(rows_to_run),
                        "elapsed_sec": round(time.perf_counter() - generation_started, 4),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

    generation_seconds = time.perf_counter() - generation_started
    report = {
        "mode": "qwen_small_object_verifier_vllm",
        "prompt_version": PROMPT_VERSION,
        "input_path": str(REPO_ROOT / args.input_path),
        "output_path": str(output_path),
        "model_path": args.model_path,
        "hardware_profile": getattr(args, "hardware_profile_metadata", {}),
        "rows_requested": len(rows),
        "rows_skipped_by_resume": len(rows) - len(rows_to_run),
        "rows_written": written,
        "dtype": args.dtype,
        "max_model_len": args.max_model_len,
        "max_num_seqs": args.max_num_seqs,
        "gpu_memory_utilization": args.gpu_memory_utilization,
        "prompt_batch_size": args.prompt_batch_size,
        "max_new_tokens": args.max_new_tokens,
        "temperature": args.temperature,
        "object_text_chars": args.object_text_chars,
        "structured_json": args.structured_json,
        "enforce_eager": args.enforce_eager,
        "load_wall_seconds": round(load_seconds, 4),
        "generation_wall_seconds": round(generation_seconds, 4),
        "rows_per_second": round(written / generation_seconds, 4) if generation_seconds else 0.0,
        "wall_seconds": round(time.perf_counter() - started, 4),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


def _load_vllm(args: argparse.Namespace) -> tuple[Any, Any]:
    from transformers import AutoTokenizer
    from vllm import LLM

    model_path = Path(args.model_path)
    resolved = str(model_path if model_path.is_absolute() else (REPO_ROOT / model_path).resolve())
    python_bin = str(Path(sys.executable).resolve().parent)
    os.environ["PATH"] = python_bin + os.pathsep + os.environ.get("PATH", "")
    tokenizer = AutoTokenizer.from_pretrained(resolved, trust_remote_code=True)
    llm = LLM(
        model=resolved,
        tokenizer=resolved,
        trust_remote_code=True,
        dtype=args.dtype,
        max_model_len=args.max_model_len,
        max_num_seqs=args.max_num_seqs,
        gpu_memory_utilization=args.gpu_memory_utilization,
        cpu_offload_gb=args.cpu_offload_gb,
        enforce_eager=args.enforce_eager,
    )
    return llm, tokenizer


def _generate(llm: Any, prompts: list[str], args: argparse.Namespace) -> list[str]:
    from vllm import SamplingParams

    sampling_kwargs: dict[str, Any] = {
        "max_tokens": args.max_new_tokens,
        "temperature": args.temperature,
        "top_p": 1.0,
    }
    if args.structured_json:
        from vllm.sampling_params import StructuredOutputsParams

        sampling_kwargs["structured_outputs"] = StructuredOutputsParams(
            json=VERIFIER_JSON_SCHEMA,
            disable_additional_properties=True,
        )
    outputs = llm.generate(prompts, SamplingParams(**sampling_kwargs))
    return [output.outputs[0].text.strip() for output in outputs]


def _format_prompt(row: dict[str, Any], tokenizer: Any, *, object_text_chars: int) -> str:
    aspect_text = str(row.get("aspect") or (row.get("must_find") or [""])[0] or "").strip()
    user_prompt = f"""Classify this SEC 10-K evidence object for one aspect.

Rubric:
- direct: the object directly supports the aspect with aligned company, fiscal year/period, metric/segment/risk topic, and number or claim.
- partial: useful context but incomplete, nearby, or missing exact company/year/metric alignment.
- false: irrelevant or mismatched by company, year, segment, metric, direction, or business meaning.

Return only this JSON shape:
{{"label":"direct|partial|false","confidence":0.0,"usable_for_synthesis":true}}

Task query:
{row.get("query") or ""}

Parent facet:
{row.get("parent_facet") or row.get("facet") or ""}

Aspect:
{aspect_text}

Must find:
{json.dumps(row.get("must_find") or [aspect_text], ensure_ascii=False)}

Evidence metadata:
{json.dumps(_metadata_for_prompt(row), ensure_ascii=False)}

Evidence object text:
{_trim(str(row.get("object_text") or row.get("preview") or ""), object_text_chars)}
"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}]
    if hasattr(tokenizer, "apply_chat_template"):
        try:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True) + "\n/no_think\n"
    return (
        f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
        f"<|im_start|>user\n{user_prompt}<|im_end|>\n"
        "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )


def _metadata_for_prompt(row: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "ticker",
        "fiscal_year",
        "object_id",
        "object_type",
        "object_ticker",
        "object_fiscal_year",
        "section",
        "subsection",
        "source_evidence_id",
        "rerank_rank",
        "rerank_score",
        "bm25_rank",
        "preview",
    ]
    return {key: row.get(key) for key in keys if row.get(key) is not None}


def _parse_verifier_json(raw_output: str) -> dict[str, Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", raw_output, flags=re.DOTALL).strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        return _invalid_parse("No JSON object found.")
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        return _invalid_parse(f"JSON parse error: {exc}")
    label = str(parsed.get("label", "")).strip().lower()
    if label not in VALID_LABELS:
        return _invalid_parse("Invalid label.")
    confidence = _safe_float(parsed.get("confidence"))
    return {
        "parse_status": "parsed",
        "label": label,
        "confidence": confidence,
        "usable_for_synthesis": bool(parsed.get("usable_for_synthesis", label != "false")),
    }


def _invalid_parse(reason: str) -> dict[str, Any]:
    return {
        "parse_status": "invalid_json",
        "label": "invalid",
        "confidence": 0.0,
        "usable_for_synthesis": False,
        "reason": reason,
    }


def _prediction_row(
    *,
    row: dict[str, Any],
    parsed: dict[str, Any],
    raw_output: str,
    prompt_chars: int,
    model_path: str,
) -> dict[str, Any]:
    passthrough_keys = [
        "query_id",
        "cohort",
        "mode",
        "difficulty",
        "scoring_profile",
        "ticker",
        "tickers",
        "fiscal_year",
        "fiscal_years",
        "query",
        "facet",
        "parent_facet",
        "aspect_label",
        "facet_must_find",
        "aspect",
        "aspect_id",
        "aspect_index",
        "aspect_reference_label",
        "aspect_reference_source",
        "must_find",
        "pool_source",
        "pool_rank",
        "rerank_rank",
        "rerank_score",
        "bm25_rank",
        "bm25_score",
        "object_id",
        "object_type",
        "source_evidence_id",
        "object_ticker",
        "object_fiscal_year",
        "section",
        "subsection",
        "preview",
    ]
    return {
        "schema_version": "small_verifier_prediction_v0.3",
        **{key: row.get(key) for key in passthrough_keys},
        "prompt_version": PROMPT_VERSION,
        "model_name": model_path,
        "resolved_model_path": model_path,
        "prompt_chars": prompt_chars,
        "debug_output_explanations": False,
        "verifier_label": parsed["label"],
        "verifier_confidence": parsed["confidence"],
        "usable_for_synthesis": parsed["usable_for_synthesis"],
        "parse_status": parsed["parse_status"],
        "raw_output": raw_output if parsed["parse_status"] != "parsed" else None,
    }


def _completed_keys(path: Path) -> set[tuple[str, str, str]]:
    if not path.exists():
        return set()
    return {_row_key(row) for row in _read_jsonl(path)}


def _row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("query_id") or ""),
        str(row.get("facet") or ""),
        str(row.get("object_id") or ""),
    )


def _safe_float(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _trim(text: str, max_chars: int) -> str:
    compact = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    return compact[:max_chars] + ("\n...[truncated]" if len(compact) > max_chars else "")


def _batches(rows: list[dict[str, Any]], batch_size: int) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(rows), batch_size):
        yield rows[start : start + batch_size]


def _read_jsonl(path: str | Path) -> Iterable[dict[str, Any]]:
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {input_path}:{line_number}") from exc


if __name__ == "__main__":
    main()
