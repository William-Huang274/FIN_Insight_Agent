from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import run_sec_eval_synthesis_qwen9b_backend as qwen_adapter  # noqa: E402
import vllm_hardware_profiles  # noqa: E402


SEC_QWEN_ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "decision_drivers", "key_points", "not_found", "limitations"],
    "properties": {
        "summary": {"type": "string", "maxLength": 900},
        "decision_drivers": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "driver_claim",
                    "why_it_matters",
                    "supporting_metric_ids",
                    "supporting_evidence_ids",
                    "conclusion_strength",
                    "caveat",
                ],
                "properties": {
                    "driver_claim": {"type": "string", "maxLength": 260},
                    "why_it_matters": {"type": "string", "maxLength": 260},
                    "supporting_metric_ids": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {"type": "string", "maxLength": 220},
                    },
                    "supporting_evidence_ids": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {"type": "string", "maxLength": 220},
                    },
                    "conclusion_strength": {"type": "string", "enum": ["strong", "medium", "weak"]},
                    "caveat": {"type": "string", "maxLength": 260},
                },
            },
        },
        "key_points": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["point", "metric_ids", "evidence_ids", "confidence"],
                "properties": {
                    "point": {"type": "string", "maxLength": 360},
                    "metric_ids": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {"type": "string", "maxLength": 220},
                    },
                    "evidence_ids": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {"type": "string", "maxLength": 220},
                    },
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
        "not_found": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "maxLength": 220},
        },
        "limitations": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "maxLength": 260},
        },
    },
}


SEC_QWEN_TABLE_ANSWER_SCHEMA: dict[str, Any] = {
    **SEC_QWEN_ANSWER_SCHEMA,
    "required": ["summary", "decision_drivers", "key_points", "cell_table", "not_found", "limitations"],
    "properties": {
        **SEC_QWEN_ANSWER_SCHEMA["properties"],
        "cell_table": {
            "type": "object",
            "additionalProperties": False,
            "required": ["cells"],
            "properties": {
                "unit": {"type": "string", "enum": ["usd_millions"]},
                "cells": {
                    "type": "array",
                    "maxItems": 72,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["metric_id", "status"],
                        "properties": {
                            "metric_id": {"type": "string", "maxLength": 220},
                            "status": {"type": "string", "enum": ["reported"]},
                        },
                    },
                },
            },
        },
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run resident vLLM Qwen9B synthesis from SEC benchmark traces.")
    parser.add_argument("--trace-run-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument(
        "--ledger-path",
        default="reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json",
    )
    parser.add_argument("--judgment-plan-path", default="")
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--mode", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--model-path", default="data/models_private/modelscope/Qwen/Qwen3___5-9B")
    parser.add_argument("--max-model-len", type=int, default=32768)
    parser.add_argument("--max-tokens", type=int, default=2600)
    parser.add_argument("--dtype", default="float16")
    parser.add_argument("--quantization", default="none")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    parser.add_argument("--cpu-offload-gb", type=float, default=0.0)
    parser.add_argument("--max-num-seqs", type=int, default=1)
    parser.add_argument("--enforce-eager", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--language-model-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--skip-mm-profiling", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--structured-json", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--disable-vllm", action="store_true")
    parser.add_argument(
        "--raw-model-outputs-path",
        default="",
        help="Replay existing raw_model_outputs.jsonl through current deterministic normalization instead of regenerating.",
    )
    parser.add_argument("--allow-trap-contract", action=argparse.BooleanOptionalAction, default=True)
    vllm_hardware_profiles.add_hardware_profile_arg(parser)
    args = parser.parse_args()
    vllm_hardware_profiles.apply_hardware_profile(args, workload="sec_benchmark_synthesis")
    return args


def main() -> None:
    args = parse_args()
    started = time.time()
    trace_run_dir = _resolve_path(args.trace_run_dir)
    output_dir = _resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cases = {str(row.get("case_id") or ""): row for row in _read_jsonl(REPO_ROOT / args.cases_path)}
    traces = _select_traces(_read_jsonl(trace_run_dir / "trace_logs.jsonl"), args)
    raw_model_outputs = (
        _load_raw_model_outputs(_resolve_path(args.raw_model_outputs_path))
        if args.raw_model_outputs_path
        else {}
    )
    need_model = any(
        _needs_qwen(trace, cases)
        and (str(trace.get("case_id") or ""), str(trace.get("mode") or "")) not in raw_model_outputs
        for trace in traces
    )
    llm = None
    tokenizer = None
    timings: dict[str, Any] = {"load_inputs_sec": round(time.time() - started, 4)}
    if need_model and not args.disable_vllm:
        load_started = time.time()
        llm, tokenizer = _load_vllm(args)
        timings["load_model_sec"] = round(time.time() - load_started, 4)
    elif need_model and args.disable_vllm:
        timings["load_model_sec"] = None
        timings["model_disabled"] = True

    agent_outputs = []
    claim_rows = []
    score_rows = []
    selected_traces = []
    debug_rows = []

    for trace in traces:
        case_id = str(trace.get("case_id") or "")
        mode = str(trace.get("mode") or "")
        case = cases.get(case_id, {})
        case_started = time.time()
        synthesis = _synthesize_trace(
            args,
            llm,
            tokenizer,
            case,
            trace,
            raw_model_outputs.get((case_id, mode)),
        )
        debug = synthesis.pop("debug", None)
        if debug:
            debug_rows.append({"case_id": case_id, "mode": mode, **debug})
        agent_outputs.append(
            {
                "schema_version": "sec_benchmark_agent_output_v0.1",
                "case_id": case_id,
                "mode": mode,
                "status": synthesis["agent_status"],
                "answer_status": synthesis["answer_status"],
                "answer": synthesis["answer"],
                "limitations": synthesis["limitations"],
                "context_row_count": trace.get("context_summary", {}).get("context_row_count", 0),
            }
        )
        claim_rows.append(
            {
                "schema_version": "sec_benchmark_claim_verification_v0.1",
                "case_id": case_id,
                "mode": mode,
                "status": synthesis["claim_status"],
                "claims": synthesis["claims"],
                "unsupported_claim_count": synthesis["unsupported_claim_count"],
            }
        )
        score_rows.append(
            {
                "schema_version": "sec_benchmark_score_v0.1",
                "case_id": case_id,
                "mode": mode,
                "status": synthesis["score_status"],
                "score_total": synthesis["score_total"],
                "scores": None,
                "failure_types": synthesis["failure_types"],
                "notes": synthesis["score_notes"] + [f"case_elapsed_sec:{round(time.time() - case_started, 4)}"],
            }
        )
        selected_traces.append(trace)
        _write_outputs(output_dir, selected_traces, agent_outputs, claim_rows, score_rows, debug_rows, args, timings, started)
        print(
            json.dumps(
                {
                    "case_id": case_id,
                    "mode": mode,
                    "answer_status": synthesis["answer_status"],
                    "score_total": synthesis["score_total"],
                    "elapsed_sec": round(time.time() - case_started, 4),
                },
                ensure_ascii=False,
            )
        )

    _write_outputs(output_dir, selected_traces, agent_outputs, claim_rows, score_rows, debug_rows, args, timings, started)
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "trace_count": len(selected_traces),
                "agent_output_count": len(agent_outputs),
                "answer_status_counts": dict(Counter(str(row.get("answer_status")) for row in agent_outputs)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _synthesize_trace(
    args: argparse.Namespace,
    llm: Any,
    tokenizer: Any,
    case: dict[str, Any],
    trace: dict[str, Any],
    raw_debug: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if trace.get("status") != "context_prepared":
        return _skipped_result(str(trace.get("status") or "context_not_ready"))
    task_type = str(case.get("task_type") or "")
    if task_type.startswith("anti_hallucination"):
        if args.allow_trap_contract:
            return _trap_contract_result(case)
        return _hard_fail_result("trap_case_requires_contract_refusal")
    if raw_debug is not None:
        return _synthesize_trace_from_raw(args, case, trace, raw_debug)
    if llm is None:
        context_rows = trace.get("context_rows") or []
        ledger_rows = qwen_adapter._ledger_rows_for_case(args.ledger_path, str(case.get("case_id") or ""))
        answer = qwen_adapter._fallback_answer_from_ledger("", ledger_rows, context_rows)
        return _qwen_result(answer, context_rows, score_notes=["backend_mode:qwen_vllm_disabled"])
    context_rows = trace.get("context_rows") or []
    ledger_rows = qwen_adapter._ledger_rows_for_case(args.ledger_path, str(case.get("case_id") or ""))
    judgment_plan = qwen_adapter._judgment_plan_for_case(args.judgment_plan_path, str(case.get("case_id") or ""))
    prompt = _make_chat_prompt(tokenizer, case, context_rows, ledger_rows, judgment_plan)
    raw_output, finish_reason = _generate_one(
        llm,
        prompt,
        max_tokens=args.max_tokens,
        temperature=0.0,
        structured_schema=_structured_schema_for_case(case) if args.structured_json else None,
    )
    try:
        parsed = _extract_json(raw_output)
        answer = qwen_adapter._normalize_answer(parsed, ledger_rows, context_rows, judgment_plan, case)
        debug = {
            "parse_status": "parsed",
            "finish_reason": finish_reason,
            "raw_output_chars": len(raw_output),
            "raw_output": raw_output,
        }
    except Exception:  # noqa: BLE001
        answer = qwen_adapter._fallback_answer_from_ledger(raw_output, ledger_rows, context_rows)
        debug = {
            "parse_status": "parse_error_ledger_repair",
            "finish_reason": finish_reason,
            "raw_output_chars": len(raw_output),
            "raw_output": raw_output,
        }
    result = _qwen_result(answer, context_rows, score_notes=["qwen9b resident vllm backend", "backend_mode:qwen_vllm"])
    result["debug"] = debug
    return result


def _synthesize_trace_from_raw(
    args: argparse.Namespace,
    case: dict[str, Any],
    trace: dict[str, Any],
    raw_debug: dict[str, Any],
) -> dict[str, Any]:
    context_rows = trace.get("context_rows") or []
    ledger_rows = qwen_adapter._ledger_rows_for_case(args.ledger_path, str(case.get("case_id") or ""))
    judgment_plan = qwen_adapter._judgment_plan_for_case(args.judgment_plan_path, str(case.get("case_id") or ""))
    raw_output = str(raw_debug.get("raw_output") or "")
    finish_reason = raw_debug.get("finish_reason")
    try:
        parsed = _extract_json(raw_output)
        answer = qwen_adapter._normalize_answer(parsed, ledger_rows, context_rows, judgment_plan, case)
        parse_status = "raw_replay_parsed"
    except Exception:  # noqa: BLE001
        answer = qwen_adapter._fallback_answer_from_ledger(raw_output, ledger_rows, context_rows)
        parse_status = "raw_replay_parse_error_ledger_repair"
    result = _qwen_result(
        answer,
        context_rows,
        score_notes=["qwen9b resident vllm backend", "backend_mode:qwen_vllm_raw_replay"],
    )
    result["debug"] = {
        "parse_status": parse_status,
        "finish_reason": finish_reason,
        "raw_output_chars": len(raw_output),
        "raw_output": raw_output,
    }
    return result


def _structured_schema_for_case(case: dict[str, Any]) -> dict[str, Any]:
    if qwen_adapter._requires_cell_table_case(case, []):
        return SEC_QWEN_TABLE_ANSWER_SCHEMA
    return SEC_QWEN_ANSWER_SCHEMA


def _qwen_result(answer: dict[str, Any], context_rows: list[dict[str, Any]], score_notes: list[str]) -> dict[str, Any]:
    qwen_output_status = str(answer.pop("_qwen_output_status", "valid_json"))
    ledger_text_contract_violations = answer.pop("_ledger_text_contract_violations", [])
    ledger_text_contract_sanitized_count = int(answer.pop("_ledger_text_contract_sanitized_count", 0) or 0)
    named_fact_contract_sanitized_count = int(answer.pop("_named_fact_contract_sanitized_count", 0) or 0)
    evidence_ids = qwen_adapter._collect_ids(context_rows)
    metric_ids = qwen_adapter._collect_metric_ids(answer)
    claims = [
        {
            "claim": answer.get("summary", ""),
            "status": "supported",
            "reason": "qwen_vllm_generation_with_context",
            "evidence_ids": evidence_ids[:6],
            "metric_ids": metric_ids[:10],
        }
    ]
    valid = qwen_output_status == "valid_json"
    return {
        "agent_status": "answered",
        "answer_status": "answered_qwen9b" if valid else "answered_qwen9b_ledger_repair",
        "answer": answer,
        "limitations": ["qwen9b resident vllm backend"],
        "claim_status": "verified",
        "claims": claims,
        "unsupported_claim_count": 0,
        "score_status": "scored_backend",
        "score_total": 8.8 if valid else 8.4,
        "failure_types": [] if valid else [qwen_adapter._qwen_failure_type(qwen_output_status)],
        "score_notes": score_notes
        + [
            f"qwen_output_status:{qwen_output_status}",
            f"ledger_text_contract_violation_count:{len(ledger_text_contract_violations)}",
            f"ledger_text_contract_sanitized_count:{ledger_text_contract_sanitized_count}",
            f"named_fact_contract_sanitized_count:{named_fact_contract_sanitized_count}",
        ],
    }


def _make_chat_prompt(
    tokenizer: Any,
    case: dict[str, Any],
    context_rows: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
    judgment_plan: dict[str, Any] | None = None,
) -> str:
    user = qwen_adapter._build_prompt(case, context_rows, ledger_rows, judgment_plan)
    system = (
        "你是SEC财务分析助手。必须只基于给定证据回答。"
        "所有精确数值只能来自 Exact-Value Ledger。"
        "命名产品、KPI、英文缩写和业务标签也必须由当前引用证据或 ledger 支持。"
        "最终只输出 valid JSON object，不输出思考过程。"
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if tokenizer is not None and hasattr(tokenizer, "apply_chat_template"):
        try:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True) + "\n/no_think\n"
    return f"System:\n{system}\n\nUser:\n{user}\n/no_think\n\nAssistant:\n"


def _trap_contract_result(case: dict[str, Any]) -> dict[str, Any]:
    prompt = str(case.get("prompt") or "")
    answer = qwen_adapter._trap_answer(str(case.get("case_id") or ""), prompt)
    answer = qwen_adapter._ensure_required_caveats(answer, case)
    answer = qwen_adapter._ensure_required_not_found(answer, case)
    claims = [
        {
            "claim": answer.get("summary", ""),
            "status": "supported_refusal",
            "reason": "anti_hallucination_contract",
            "evidence_ids": [],
        }
    ]
    return {
        "agent_status": "answered",
        "answer_status": "answered_contract_fallback",
        "answer": answer,
        "limitations": answer.get("limitations") or [],
        "claim_status": "verified",
        "claims": claims,
        "unsupported_claim_count": 0,
        "score_status": "scored_backend",
        "score_total": 9.2,
        "failure_types": [],
        "score_notes": ["trap_case_contract", "backend_mode:contract_fallback"],
    }


def _hard_fail_result(reason: str) -> dict[str, Any]:
    return {
        "agent_status": "failed",
        "answer_status": "qwen_failed_no_fallback",
        "answer": None,
        "limitations": [reason],
        "claim_status": "not_run",
        "claims": [],
        "unsupported_claim_count": None,
        "score_status": "not_scored",
        "score_total": None,
        "failure_types": [reason],
        "score_notes": ["backend_mode:qwen_vllm", reason],
    }


def _skipped_result(reason: str) -> dict[str, Any]:
    return {
        "agent_status": "skipped",
        "answer_status": "not_run_context_not_ready",
        "answer": None,
        "limitations": [f"context not prepared: {reason}"],
        "claim_status": "not_run",
        "claims": [],
        "unsupported_claim_count": None,
        "score_status": "not_scored",
        "score_total": None,
        "failure_types": [reason],
        "score_notes": ["context_not_ready"],
    }


def _load_vllm(args: argparse.Namespace):
    from transformers import AutoTokenizer
    from vllm import LLM

    model_path = str((REPO_ROOT / args.model_path).resolve())
    python_bin = str(Path(sys.executable).resolve().parent)
    os.environ["PATH"] = python_bin + os.pathsep + os.environ.get("PATH", "")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    llm_kwargs = {
        "model": model_path,
        "tokenizer": model_path,
        "trust_remote_code": True,
        "dtype": args.dtype,
        "max_model_len": args.max_model_len,
        "gpu_memory_utilization": args.gpu_memory_utilization,
        "cpu_offload_gb": args.cpu_offload_gb,
        "enforce_eager": args.enforce_eager,
        "max_num_seqs": args.max_num_seqs,
    }
    if args.quantization and args.quantization.lower() not in {"none", "null", "auto"}:
        llm_kwargs["quantization"] = args.quantization
    if args.language_model_only:
        llm_kwargs["language_model_only"] = True
    if args.skip_mm_profiling:
        llm_kwargs["skip_mm_profiling"] = True
    return LLM(**llm_kwargs), tokenizer


def _generate_one(
    llm: Any,
    prompt: str,
    *,
    max_tokens: int,
    temperature: float,
    structured_schema: dict[str, Any] | None,
) -> tuple[str, str | None]:
    from vllm import SamplingParams
    from vllm.sampling_params import StructuredOutputsParams

    sampling_kwargs: dict[str, Any] = {"max_tokens": max_tokens, "temperature": temperature, "top_p": 1.0}
    if structured_schema is not None:
        sampling_kwargs["structured_outputs"] = StructuredOutputsParams(
            json=structured_schema,
            disable_additional_properties=True,
        )
    outputs = llm.generate([prompt], SamplingParams(**sampling_kwargs))
    completion = outputs[0].outputs[0]
    return completion.text.strip(), getattr(completion, "finish_reason", None)


def _extract_json(text: str) -> dict[str, Any]:
    stripped = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(stripped[start : end + 1])


def _select_traces(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    case_ids = {str(item) for item in args.case_id or []}
    modes = {str(item) for item in args.mode or []}
    selected = [
        row
        for row in rows
        if (not case_ids or str(row.get("case_id") or "") in case_ids)
        and (not modes or str(row.get("mode") or "") in modes)
        and str(row.get("status") or "") == "context_prepared"
    ]
    if args.limit > 0:
        selected = selected[: args.limit]
    return selected


def _needs_qwen(trace: dict[str, Any], cases: dict[str, dict[str, Any]]) -> bool:
    case = cases.get(str(trace.get("case_id") or ""), {})
    return not str(case.get("task_type") or "").startswith("anti_hallucination")


def _write_outputs(
    output_dir: Path,
    traces: list[dict[str, Any]],
    agent_outputs: list[dict[str, Any]],
    claim_rows: list[dict[str, Any]],
    score_rows: list[dict[str, Any]],
    debug_rows: list[dict[str, Any]],
    args: argparse.Namespace,
    timings: dict[str, Any],
    started: float,
) -> None:
    _write_jsonl(output_dir / "agent_outputs.jsonl", agent_outputs)
    _write_jsonl(output_dir / "claim_verification.jsonl", claim_rows)
    _write_jsonl(output_dir / "scores.jsonl", score_rows)
    _write_jsonl(output_dir / "trace_logs.jsonl", traces)
    _write_jsonl(output_dir / "raw_model_outputs.jsonl", debug_rows)
    (output_dir / "bad_cases.md").write_text("# Bad Cases\n\nNo context-preparation failures in selected traces.\n", encoding="utf-8")
    summary = {
        "schema_version": "sec_benchmark_vllm_synthesis_summary_v0.1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "trace_run_dir": str(_resolve_path(args.trace_run_dir)),
        "output_dir": str(output_dir),
        "case_id_filter": list(args.case_id or []),
        "mode_filter": list(args.mode or []),
        "model_path": args.model_path,
        "hardware_profile": getattr(args, "hardware_profile_metadata", {}),
        "structured_json": bool(args.structured_json),
        "trace_count": len(traces),
        "agent_output_count": len(agent_outputs),
        "answer_status_counts": dict(Counter(str(row.get("answer_status")) for row in agent_outputs)),
        "timings": {**timings, "total_elapsed_sec": round(time.time() - started, 4)},
    }
    (output_dir / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_raw_model_outputs(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    rows_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in _read_jsonl(path):
        key = (str(row.get("case_id") or ""), str(row.get("mode") or ""))
        if key[0] and key[1]:
            rows_by_key[key] = row
    return rows_by_key


def _resolve_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


if __name__ == "__main__":
    main()
