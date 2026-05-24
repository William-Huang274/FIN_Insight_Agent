from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


VALID_LABELS = {"direct", "partial", "false"}
PROMPT_VERSION = "qwen_small_object_verifier_v0.2"


SYSTEM_PROMPT = (
    "You are a strict financial evidence verifier for SEC 10-K retrieval. "
    "Classify whether one structured evidence object supports one research facet. "
    "Use only the provided evidence object. Return valid JSON only."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a small Qwen-style instruct model as a direct/partial/false object verifier."
    )
    parser.add_argument(
        "--input-path",
        default="reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl",
    )
    parser.add_argument(
        "--output-path",
        default="reports/verifier/sec_tech_10k_qwen35_small_verifier_predictions.jsonl",
    )
    parser.add_argument(
        "--model-name",
        default="Qwen/Qwen3.5-4B-Instruct",
        help="Local model path or ModelScope model id. Pass the exact available Qwen3.5 small instruct model id/path.",
    )
    parser.add_argument(
        "--download-modelscope",
        action="store_true",
        help="Resolve --model-name with modelscope.snapshot_download before loading.",
    )
    parser.add_argument(
        "--modelscope-cache",
        default="/root/autodl-tmp/modelscope_cache",
    )
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--torch-dtype", default="auto", choices=["auto", "float16", "bfloat16", "float32"])
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=4096)
    parser.add_argument("--max-new-tokens", type=int, default=192)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--debug-output-explanations",
        action="store_true",
        help="Ask the verifier to emit reason/missing_requirements and persist raw model output for debugging.",
    )
    parser.add_argument(
        "--require-fast-path",
        action="store_true",
        help="Fail before model loading if causal-conv1d and flash-linear-attention are not usable.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip rows already present in the output file by query_id/facet/object_id.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = list(_read_jsonl(REPO_ROOT / args.input_path))
    if args.limit is not None:
        rows = rows[: args.limit]

    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completed = _completed_keys(output_path) if args.resume else set()
    rows_to_run = [
        row
        for row in rows
        if _row_key(row) not in completed
    ]

    model_path = _resolve_model_path(args)
    load_start = time.perf_counter()
    tokenizer, model, fast_path_status = _load_model(model_path, args)
    load_seconds = time.perf_counter() - load_start
    generation_start = time.perf_counter()
    written = 0
    mode = "a" if args.resume else "w"
    with output_path.open(mode, encoding="utf-8") as f:
        for batch in _batches(rows_to_run, args.batch_size):
            prompts = [_format_prompt(row, debug_explanations=args.debug_output_explanations) for row in batch]
            raw_outputs = _generate_batch(tokenizer, model, prompts, args)
            for row, prompt, raw_output in zip(batch, prompts, raw_outputs):
                parsed = _parse_verifier_json(raw_output)
                output_row = _prediction_row(
                    row=row,
                    parsed=parsed,
                    raw_output=raw_output,
                    prompt_chars=len(prompt),
                    model_name=args.model_name,
                    resolved_model_path=model_path,
                    debug_explanations=args.debug_output_explanations,
                )
                f.write(json.dumps(output_row, ensure_ascii=False))
                f.write("\n")
                written += 1
            f.flush()

    report = {
        "mode": "qwen_small_object_verifier",
        "prompt_version": PROMPT_VERSION,
        "input_path": str(REPO_ROOT / args.input_path),
        "output_path": str(output_path),
        "model_name": args.model_name,
        "resolved_model_path": model_path,
        "rows_requested": len(rows),
        "rows_skipped_by_resume": len(rows) - len(rows_to_run),
        "rows_written": written,
        "batch_size": args.batch_size,
        "max_length": args.max_length,
        "max_new_tokens": args.max_new_tokens,
        "temperature": args.temperature,
        "debug_output_explanations": args.debug_output_explanations,
        "require_fast_path": args.require_fast_path,
        "fast_path_status": fast_path_status,
        "load_wall_seconds": round(load_seconds, 4),
        "generation_wall_seconds": round(time.perf_counter() - generation_start, 4),
        "wall_seconds": round(load_seconds + time.perf_counter() - generation_start, 4),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _resolve_model_path(args: argparse.Namespace) -> str:
    model_path = Path(args.model_name)
    if model_path.exists():
        return str(model_path)
    if not args.download_modelscope:
        return args.model_name
    from modelscope import snapshot_download

    return snapshot_download(args.model_name, cache_dir=args.modelscope_cache)


def _load_model(model_path: str, args: argparse.Namespace) -> tuple[Any, Any, dict[str, Any]]:
    import torch
    import transformers
    from transformers import AutoTokenizer

    if args.require_fast_path:
        fast_path_status = _assert_fast_path(transformers)
    else:
        fast_path_status = _disable_broken_causal_conv1d(transformers)
    dtype = {
        "auto": "auto",
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }[args.torch_dtype]
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True,
        padding_side="left",
    )
    if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
        tokenizer.pad_token = tokenizer.eos_token
    model = _load_auto_model(transformers, model_path, dtype)
    model.to(args.device)
    model.eval()
    return tokenizer, model, fast_path_status


def _disable_broken_causal_conv1d(transformers_module: Any) -> dict[str, Any]:
    try:
        import causal_conv1d_cuda  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        import_utils = transformers_module.utils.import_utils
        try:
            import_utils.is_causal_conv1d_available.cache_clear()
        except AttributeError:
            pass
        import_utils.is_causal_conv1d_available = lambda: False
        return {
            "required": False,
            "causal_conv1d_cuda_import": False,
            "causal_conv1d_available": False,
            "flash_linear_attention_available": _flash_linear_attention_available(transformers_module),
            "fallback_enabled": True,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return _fast_path_status(transformers_module, required=False, fallback_enabled=False)


def _assert_fast_path(transformers_module: Any) -> dict[str, Any]:
    try:
        import causal_conv1d_cuda  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Required fast path is unavailable: causal_conv1d_cuda cannot be imported. "
            "Install a causal-conv1d wheel matching the active torch/CUDA ABI."
        ) from exc

    status = _fast_path_status(transformers_module, required=True, fallback_enabled=False)
    if not status["causal_conv1d_available"] or not status["flash_linear_attention_available"]:
        raise RuntimeError(f"Required fast path is unavailable: {status}")
    return status


def _fast_path_status(
    transformers_module: Any,
    *,
    required: bool,
    fallback_enabled: bool,
) -> dict[str, Any]:
    return {
        "required": required,
        "causal_conv1d_cuda_import": True,
        "causal_conv1d_available": _causal_conv1d_available(transformers_module),
        "flash_linear_attention_available": _flash_linear_attention_available(transformers_module),
        "fallback_enabled": fallback_enabled,
    }


def _causal_conv1d_available(transformers_module: Any) -> bool:
    import_utils = transformers_module.utils.import_utils
    try:
        import_utils.is_causal_conv1d_available.cache_clear()
    except AttributeError:
        pass
    return bool(import_utils.is_causal_conv1d_available())


def _flash_linear_attention_available(transformers_module: Any) -> bool:
    import_utils = transformers_module.utils.import_utils
    try:
        import_utils.is_flash_linear_attention_available.cache_clear()
    except AttributeError:
        pass
    return bool(import_utils.is_flash_linear_attention_available())


def _load_auto_model(transformers_module: Any, model_path: str, dtype: Any) -> Any:
    errors = []
    for class_name in (
        "AutoModelForCausalLM",
        "AutoModelForImageTextToText",
        "AutoModelForMultimodalLM",
        "AutoModel",
    ):
        model_class = getattr(transformers_module, class_name, None)
        if model_class is None:
            continue
        try:
            model = model_class.from_pretrained(
                model_path,
                torch_dtype=dtype,
                trust_remote_code=True,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{class_name}: {type(exc).__name__}: {exc}")
            continue
        if not hasattr(model, "generate"):
            errors.append(f"{class_name}: loaded model has no generate() method")
            continue
        return model
    raise RuntimeError("Could not load a generative Qwen verifier model. " + " | ".join(errors))


def _generate_batch(tokenizer: Any, model: Any, prompts: list[str], args: argparse.Namespace) -> list[str]:
    import torch

    inputs = tokenizer(
        prompts,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=args.max_length,
    )
    device = _model_device(model)
    inputs = {key: value.to(device) for key, value in inputs.items()}
    generation_kwargs: dict[str, Any] = {
        "max_new_tokens": args.max_new_tokens,
        "do_sample": args.temperature > 0,
        "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
    }
    if args.temperature > 0:
        generation_kwargs["temperature"] = args.temperature
    with torch.no_grad():
        outputs = model.generate(**inputs, **generation_kwargs)
    input_length = inputs["input_ids"].shape[1]
    return [
        tokenizer.decode(output[input_length:], skip_special_tokens=True).strip()
        for output in outputs
    ]


def _model_device(model: Any) -> Any:
    try:
        return model.device
    except AttributeError:
        return next(model.parameters()).device


def _format_prompt(row: dict[str, Any], *, debug_explanations: bool) -> str:
    output_schema = _debug_output_schema() if debug_explanations else _compact_output_schema()
    aspect_text = str(row.get("aspect") or "").strip()
    if aspect_text:
        scope_text = (
            f"Aspect to verify:\n{aspect_text}\n\n"
            "Decision scope:\n"
            "- Judge only this single aspect.\n"
            "- Do not require the evidence object to satisfy the other aspects in the same facet.\n"
            "- If the object directly proves this aspect, label direct even when it is incomplete for the full facet.\n"
        )
        must_find = [aspect_text]
    else:
        scope_text = ""
        must_find = row.get("must_find") or []
    user_prompt = f"""Classify the evidence object for the facet.

Rubric:
- direct: The evidence directly supports the facet. The company, fiscal year, metric/segment/risk topic, and required claim or number are aligned.
- partial: The evidence is useful context but incomplete. It may support only one required part, a nearby metric, a caveat/background point, or lacks the exact requested number/driver.
- false: The evidence is irrelevant or mismatched by company, year, segment, metric, direction, risk topic, or business meaning.

Return only one JSON object. No prose, no markdown, no extra keys.
{output_schema}

Task query:
{row.get("query") or ""}

Facet:
{row.get("facet") or ""}

{scope_text}
Must find / expected evidence aspects:
{json.dumps(must_find, ensure_ascii=False)}

Evidence metadata:
{json.dumps(_metadata_for_prompt(row), ensure_ascii=False)}

Evidence object text:
{row.get("object_text") or row.get("preview") or ""}
"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    return _apply_chat_template_fallback(messages)


def _compact_output_schema() -> str:
    return (
        'Schema: {"label":"direct|partial|false","confidence":0.0,'
        '"usable_for_synthesis":true}'
    )


def _debug_output_schema() -> str:
    return (
        'Schema: {"label":"direct|partial|false","confidence":0.0,'
        '"usable_for_synthesis":true,"reason":"one short sentence",'
        '"missing_requirements":["short item"]}'
    )


def _apply_chat_template_fallback(messages: list[dict[str, str]]) -> str:
    system = messages[0]["content"]
    user = messages[1]["content"]
    return (
        "<|im_start|>system\n"
        f"{system}<|im_end|>\n"
        "<|im_start|>user\n"
        f"{user}<|im_end|>\n"
        "<|im_start|>assistant\n"
        "<think>\n\n</think>\n\n"
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
    cleaned = raw_output.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        return {
            "parse_status": "invalid_json",
            "label": "invalid",
            "confidence": 0.0,
            "reason": "No JSON object found.",
            "missing_requirements": [],
            "usable_for_synthesis": False,
        }
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        return {
            "parse_status": "invalid_json",
            "label": "invalid",
            "confidence": 0.0,
            "reason": f"JSON parse error: {exc}",
            "missing_requirements": [],
            "usable_for_synthesis": False,
        }

    label = str(parsed.get("label", "")).strip().lower()
    if label not in VALID_LABELS:
        return {
            "parse_status": "invalid_label",
            "label": "invalid",
            "confidence": _safe_float(parsed.get("confidence")),
            "reason": str(parsed.get("reason") or "Invalid label."),
            "missing_requirements": _string_list(parsed.get("missing_requirements")),
            "usable_for_synthesis": False,
        }
    return {
        "parse_status": "parsed",
        "label": label,
        "confidence": _safe_float(parsed.get("confidence")),
        "reason": str(parsed.get("reason") or ""),
        "missing_requirements": _string_list(parsed.get("missing_requirements")),
        "usable_for_synthesis": bool(parsed.get("usable_for_synthesis", label != "false")),
    }


def _prediction_row(
    row: dict[str, Any],
    parsed: dict[str, Any],
    raw_output: str,
    prompt_chars: int,
    model_name: str,
    resolved_model_path: str,
    debug_explanations: bool,
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
    output = {
        "schema_version": "small_verifier_prediction_v0.2",
        **{key: row.get(key) for key in passthrough_keys},
        "prompt_version": PROMPT_VERSION,
        "model_name": model_name,
        "resolved_model_path": resolved_model_path,
        "prompt_chars": prompt_chars,
        "debug_output_explanations": debug_explanations,
        "verifier_label": parsed["label"],
        "verifier_confidence": parsed["confidence"],
        "usable_for_synthesis": parsed["usable_for_synthesis"],
        "parse_status": parsed["parse_status"],
    }
    if debug_explanations:
        output.update(
            {
                "verifier_reason": parsed["reason"],
                "verifier_missing_requirements": parsed["missing_requirements"],
                "raw_output": raw_output,
            }
        )
    return output


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


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


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
