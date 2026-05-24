from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if not os.environ.get("OMP_NUM_THREADS", "").isdigit():
    os.environ["OMP_NUM_THREADS"] = "1"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import vllm_hardware_profiles  # noqa: E402
from retrieval.bm25_retriever import BM25Retriever  # noqa: E402
from retrieval.dense_retriever import DenseRetriever  # noqa: E402


FACET_VALUES = [
    "revenue_growth",
    "margin_cost",
    "capex",
    "risk",
    "liquidity",
    "rpo",
    "customer_metric",
    "segment_mix",
    "business_context",
    "other",
]

FACET_QUERY_HINTS = {
    "capex": [
        "capital expenditures technical infrastructure servers network equipment data centers",
        "AI infrastructure operating costs depreciation energy equipment margins",
    ],
    "customer_metric": [
        "concentration of revenue direct customers",
        "major customers revenue percentage",
    ],
    "risk": [
        "risk factors demand supply manufacturing third-party suppliers customers concentration",
    ],
    "business_context": [
        "cloud service providers indirect customers demand",
        "hyperscale cloud enterprise customer demand",
    ],
    "revenue_growth": [
        "revenue increased growth segment revenue",
    ],
    "segment_mix": [
        "segment revenue table net sales",
    ],
    "margin_cost": [
        "gross margin percentage operating costs",
    ],
}

PLANNER_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tasks"],
    "properties": {
        "tasks": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "task_id",
                    "question",
                    "search_query",
                    "facet",
                    "ticker",
                    "fiscal_year",
                    "section_hints",
                    "evidence_type_hints",
                    "must_find",
                    "needs_table",
                ],
                "properties": {
                    "task_id": {"type": "string"},
                    "question": {"type": "string"},
                    "search_query": {"type": "string"},
                    "facet": {"type": "string", "enum": FACET_VALUES},
                    "ticker": {"type": "string"},
                    "fiscal_year": {"type": "integer"},
                    "section_hints": {
                        "type": "array",
                        "maxItems": 3,
                        "items": {"type": "string"},
                    },
                    "evidence_type_hints": {
                        "type": "array",
                        "maxItems": 3,
                        "items": {"type": "string"},
                    },
                    "must_find": {
                        "type": "array",
                        "maxItems": 3,
                        "items": {"type": "string"},
                    },
                    "needs_table": {"type": "boolean"},
                },
            },
        }
    },
}

VERIFIER_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["label", "reason", "key_facts"],
    "properties": {
        "label": {"type": "string", "enum": ["direct", "partial", "false"]},
        "reason": {"type": "string"},
        "key_facts": {
            "type": "array",
            "maxItems": 4,
            "items": {"type": "string"},
        },
    },
}

SYNTHESIS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer", "key_findings", "missing_or_uncertain", "evidence_pack_quality"],
    "properties": {
        "answer": {"type": "string"},
        "key_findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["claim", "evidence_ids"],
                "properties": {
                    "claim": {"type": "string"},
                    "evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "missing_or_uncertain": {
            "type": "array",
            "items": {"type": "string"},
        },
        "evidence_pack_quality": {"type": "string", "enum": ["good", "mixed", "weak"]},
    },
}


@dataclass
class SearchTask:
    task_id: str
    question: str
    search_query: str
    facet: str
    ticker: str | None = None
    fiscal_year: int | None = None
    section_hints: list[str] = field(default_factory=list)
    evidence_type_hints: list[str] = field(default_factory=list)
    must_find: list[str] = field(default_factory=list)
    needs_table: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a resident Qwen planner-to-synthesis demo over SEC evidence."
    )
    parser.add_argument(
        "--model-path",
        default="data/models_private/modelscope/Qwen/Qwen3.5-9B",
    )
    parser.add_argument("--queries", default="eval_sets/sec_tech_10k_demo_queries.jsonl")
    parser.add_argument("--evidence-path", default="data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl")
    parser.add_argument("--bm25-index-dir", default="data/indexes/bm25/sec_tech_10k")
    parser.add_argument(
        "--dense-index-dir",
        default="data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs16",
    )
    parser.add_argument("--output", default="reports/demo/qwen9b_planner_evidence_pack_demo.json")
    parser.add_argument("--retrieval-mode", choices=["bm25", "hybrid"], default="hybrid")
    parser.add_argument("--candidate-k", type=int, default=6)
    parser.add_argument("--verify-k", type=int, default=2)
    parser.add_argument("--adaptive-verify-k", type=int, default=6)
    parser.add_argument("--adaptive-min-direct", type=int, default=1)
    parser.add_argument("--table-rescue-k", type=int, default=0)
    parser.add_argument("--selected-per-task", type=int, default=2)
    parser.add_argument("--evidence-card-preview-chars", type=int, default=700)
    parser.add_argument("--task-synthesis-budget-chars", type=int, default=4500)
    parser.add_argument("--task-query-variants", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-query-variants", type=int, default=4)
    parser.add_argument("--variant-original-quota", type=int, default=2)
    parser.add_argument("--max-task-count", type=int, default=4)
    parser.add_argument("--max-model-len", type=int, default=8192)
    parser.add_argument("--cpu-offload-gb", type=float, default=0.0)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.86)
    parser.add_argument("--dtype", default="float16")
    parser.add_argument("--quantization", default="none")
    parser.add_argument("--max-num-seqs", type=int, default=2)
    parser.add_argument("--language-model-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--skip-mm-profiling", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--structured-json", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--allow-fallback-planner", action="store_true")
    parser.add_argument("--planner-max-tokens", type=int, default=1024)
    parser.add_argument("--verifier-max-tokens", type=int, default=120)
    parser.add_argument("--synthesis-max-tokens", type=int, default=650)
    parser.add_argument("--disable-vllm", action="store_true")
    parser.add_argument("--device", default="cpu", help="Embedding retriever device for hybrid mode.")
    vllm_hardware_profiles.add_hardware_profile_arg(parser)
    args = parser.parse_args()
    vllm_hardware_profiles.apply_hardware_profile(args, workload="planner_evidence_demo")
    return args


def main() -> None:
    args = parse_args()
    timings: dict[str, float] = {}
    t0 = time.time()
    records = _load_evidence(REPO_ROOT / args.evidence_path)
    by_id = {record["evidence_id"]: record for record in records}
    by_block = _group_by_block(records)
    queries = _load_jsonl(REPO_ROOT / args.queries)
    timings["load_data_sec"] = time.time() - t0

    retrieval = TaskRetriever(args)

    llm = None
    tokenizer = None
    if not args.disable_vllm:
        t_model = time.time()
        llm, tokenizer = _load_vllm(args)
        timings["load_resident_model_sec"] = time.time() - t_model

    results = []
    for query_record in queries:
        print(f"[demo] start query_id={query_record['query_id']} mode={query_record['mode']}", flush=True)
        query_started = time.time()
        tasks, planner_raw, planner_error = plan_tasks(
            query_record,
            llm=llm,
            tokenizer=tokenizer,
            max_task_count=args.max_task_count,
            planner_max_tokens=args.planner_max_tokens,
            allow_fallback_planner=args.allow_fallback_planner,
            structured_json=args.structured_json,
        )
        print(
            f"[demo] planned query_id={query_record['query_id']} tasks={len(tasks)} parse_error={planner_error}",
            flush=True,
        )
        evidence_pack = build_evidence_pack(
            query_record,
            tasks,
            retrieval,
            by_id,
            by_block,
            llm=llm,
            tokenizer=tokenizer,
            candidate_k=args.candidate_k,
            verify_k=args.verify_k,
            adaptive_verify_k=args.adaptive_verify_k,
            adaptive_min_direct=args.adaptive_min_direct,
            table_rescue_k=args.table_rescue_k,
            selected_per_task=args.selected_per_task,
            evidence_card_preview_chars=args.evidence_card_preview_chars,
            verifier_max_tokens=args.verifier_max_tokens,
            structured_json=args.structured_json,
        )
        print(f"[demo] built evidence query_id={query_record['query_id']} task_packs={len(evidence_pack)}", flush=True)
        synthesis, synthesis_raw, synthesis_input_audit = synthesize_answer(
            query_record,
            evidence_pack,
            llm=llm,
            tokenizer=tokenizer,
            synthesis_max_tokens=args.synthesis_max_tokens,
            task_synthesis_budget_chars=args.task_synthesis_budget_chars,
            max_model_len=args.max_model_len,
            structured_json=args.structured_json,
        )
        print(f"[demo] synthesized query_id={query_record['query_id']}", flush=True)
        results.append(
            {
                "query_id": query_record["query_id"],
                "mode": query_record["mode"],
                "query": query_record["query"],
                "ideal_facets": query_record.get("ideal_facets", []),
                "ideal_output": query_record.get("ideal_output"),
                "planner": {
                    "raw": planner_raw,
                    "parse_error": planner_error,
                    "tasks": [task.__dict__ for task in tasks],
                },
                "evidence_pack": evidence_pack,
                "synthesis": synthesis,
                "synthesis_raw": synthesis_raw,
                "synthesis_input_audit": synthesis_input_audit,
                "elapsed_sec": round(time.time() - query_started, 3),
            }
        )

    report = {
        "run_profile": {
            "model_path": args.model_path,
            "hardware_profile": getattr(args, "hardware_profile_metadata", {}),
            "retrieval_mode": args.retrieval_mode,
            "candidate_k": args.candidate_k,
            "verify_k": args.verify_k,
            "adaptive_verify_k": args.adaptive_verify_k,
            "adaptive_min_direct": args.adaptive_min_direct,
            "table_rescue_k": args.table_rescue_k,
            "selected_per_task": args.selected_per_task,
            "evidence_card_preview_chars": args.evidence_card_preview_chars,
            "task_synthesis_budget_chars": args.task_synthesis_budget_chars,
            "task_query_variants": args.task_query_variants,
            "max_query_variants": args.max_query_variants,
            "variant_original_quota": args.variant_original_quota,
            "max_model_len": args.max_model_len,
            "cpu_offload_gb": args.cpu_offload_gb,
            "gpu_memory_utilization": args.gpu_memory_utilization,
            "dtype": args.dtype,
            "quantization": args.quantization,
            "max_num_seqs": args.max_num_seqs,
            "language_model_only": args.language_model_only,
            "skip_mm_profiling": args.skip_mm_profiling,
            "structured_json": args.structured_json,
            "allow_fallback_planner": args.allow_fallback_planner,
            "planner_max_tokens": args.planner_max_tokens,
            "verifier_max_tokens": args.verifier_max_tokens,
            "synthesis_max_tokens": args.synthesis_max_tokens,
            "resident_model_enabled": llm is not None,
        },
        "summary": _summarize_results(results),
        "timings": timings | {"total_sec": time.time() - t0},
        "results": results,
    }
    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output_path), "query_count": len(results)}, ensure_ascii=False))


class TaskRetriever:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.bm25 = BM25Retriever(REPO_ROOT / args.bm25_index_dir)
        self.dense = None
        if args.retrieval_mode == "hybrid":
            self.dense = DenseRetriever(REPO_ROOT / args.dense_index_dir, device=args.device)

    def search(self, task: SearchTask, top_k: int) -> list[dict[str, Any]]:
        filters = {}
        if task.ticker:
            filters["ticker"] = task.ticker
        if task.fiscal_year:
            filters["fiscal_year"] = task.fiscal_year
        filters = filters or None
        query_variants = (
            _task_query_variants(task, max_variants=self.args.max_query_variants)
            if self.args.task_query_variants
            else [task.search_query]
        )
        if len(query_variants) == 1:
            return self._single_search(query_variants[0], top_k=top_k, filters=filters)
        variant_results = [
            (f"variant_{idx:02d}", query_text, self._single_search(query_text, top_k=top_k * 2, filters=filters))
            for idx, query_text in enumerate(query_variants)
        ]
        return _round_robin_variant_fusion(
            variant_results,
            top_k=top_k,
            original_quota=self.args.variant_original_quota,
        )

    def _single_search(
        self,
        query: str,
        *,
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        bm25_results = self.bm25.search(query, top_k=top_k * 3, filters=filters)
        if not self.dense:
            return bm25_results[:top_k]
        dense_results = self.dense.search(query, top_k=top_k * 3, filters=filters)
        return _weighted_fusion({"dense": dense_results, "bm25": bm25_results}, {"dense": 1.0, "bm25": 0.45}, top_k=top_k)


def plan_tasks(
    query_record: dict[str, Any],
    *,
    llm,
    tokenizer,
    max_task_count: int,
    planner_max_tokens: int,
    allow_fallback_planner: bool,
    structured_json: bool,
) -> tuple[list[SearchTask], str, str | None]:
    prompt = _chat_prompt(
        tokenizer,
        system=(
            "You are a financial research query planner for SEC 10-K retrieval. "
            "Return only minified valid JSON. Split the user query into precise SearchTasks. "
            "Each task should retrieve direct evidence, not write the answer. "
            "Do not output hidden reasoning, markdown, comments, or <think> blocks. "
            "Always close the JSON object."
        ),
        user=(
            "Create SearchTasks for this SEC 10-K research question.\n"
            "Keep each field short. Arrays must contain at most 3 strings.\n"
            "Use this JSON schema exactly:\n"
            "{\"tasks\":[{\"task_id\":\"short_snake_case\",\"question\":\"...\","
            "\"search_query\":\"...\",\"facet\":\"revenue_growth|margin_cost|capex|risk|liquidity|rpo|customer_metric|segment_mix|business_context|other\","
            "\"ticker\":\"MSFT\",\"fiscal_year\":2025,"
            "\"section_hints\":[\"Item 7\"],\"evidence_type_hints\":[\"management_discussion\"],"
            "\"must_find\":[\"metric or phrase\"],\"needs_table\":false}]}\n"
            f"Known ticker field from user/test harness: {query_record.get('ticker')}\n"
            f"Known fiscal_year: {query_record.get('fiscal_year')}\n"
            f"Question mode: {query_record.get('mode')}\n"
            f"Question: {query_record['query']}\n"
            f"Return {max_task_count} or fewer tasks."
        ),
    )
    if llm is None:
        if allow_fallback_planner:
            return _fallback_tasks(query_record), "", "vllm_disabled"
        return [], "", "vllm_disabled"
    raw = _generate_one(
        llm,
        prompt,
        max_tokens=planner_max_tokens,
        temperature=0.0,
        structured_schema=PLANNER_JSON_SCHEMA if structured_json else None,
    )
    try:
        payload = _extract_json(raw)
        tasks = [_task_from_dict(item, query_record) for item in payload.get("tasks", [])]
        tasks = [task for task in tasks if task.search_query][:max_task_count]
        if not tasks:
            raise ValueError("planner returned no tasks")
        return tasks, raw, None
    except Exception as exc:
        if allow_fallback_planner:
            return _fallback_tasks(query_record), raw, f"{type(exc).__name__}: {exc}"
        return [], raw, f"{type(exc).__name__}: {exc}"


def build_evidence_pack(
    query_record: dict[str, Any],
    tasks: list[SearchTask],
    retrieval: TaskRetriever,
    by_id: dict[str, dict[str, Any]],
    by_block: dict[str, list[dict[str, Any]]],
    *,
    llm,
    tokenizer,
    candidate_k: int,
    verify_k: int,
    adaptive_verify_k: int,
    adaptive_min_direct: int,
    table_rescue_k: int,
    selected_per_task: int,
    evidence_card_preview_chars: int,
    verifier_max_tokens: int,
    structured_json: bool,
) -> list[dict[str, Any]]:
    pack = []
    for task in tasks:
        print(f"[demo] retrieve task={task.task_id} ticker={task.ticker} facet={task.facet}", flush=True)
        search_k = max(candidate_k, adaptive_verify_k)
        query_variants = (
            _task_query_variants(task, max_variants=retrieval.args.max_query_variants)
            if retrieval.args.task_query_variants
            else [task.search_query]
        )
        candidates = retrieval.search(task, search_k)
        verified = verify_candidates(
            query_record,
            task,
            candidates[:verify_k],
            llm=llm,
            tokenizer=tokenizer,
            verifier_max_tokens=verifier_max_tokens,
            structured_json=structured_json,
        )
        adaptive_checked = len(verified)
        direct_count = sum(1 for item in verified if item["verifier_label"] == "direct")
        if direct_count < adaptive_min_direct and adaptive_verify_k > verify_k:
            extra_candidates = candidates[verify_k:adaptive_verify_k]
            if extra_candidates:
                print(
                    f"[demo] adaptive verify task={task.task_id} extra={len(extra_candidates)} "
                    f"direct={direct_count}/{adaptive_min_direct}",
                    flush=True,
                )
                extra_verified = verify_candidates(
                    query_record,
                    task,
                    extra_candidates,
                    llm=llm,
                    tokenizer=tokenizer,
                    verifier_max_tokens=verifier_max_tokens,
                    structured_json=structured_json,
                )
                verified.extend(extra_verified)
                adaptive_checked = len(verified)
                direct_count = sum(1 for item in verified if item["verifier_label"] == "direct")
        if direct_count < adaptive_min_direct and table_rescue_k > 0:
            verified_ids = {item["evidence_id"] for item in verified}
            rescue_candidates = _table_rescue_candidates(
                task,
                candidates,
                verified_ids=verified_ids,
                limit=table_rescue_k,
            )
            if rescue_candidates:
                print(
                    f"[demo] table rescue task={task.task_id} extra={len(rescue_candidates)} "
                    f"direct={direct_count}/{adaptive_min_direct}",
                    flush=True,
                )
                rescue_verified = verify_candidates(
                    query_record,
                    task,
                    rescue_candidates,
                    llm=llm,
                    tokenizer=tokenizer,
                    verifier_max_tokens=verifier_max_tokens,
                    structured_json=structured_json,
                )
                verified.extend(rescue_verified)
                adaptive_checked = len(verified)
                direct_count = sum(1 for item in verified if item["verifier_label"] == "direct")
        selected = select_evidence(task, verified, selected_per_task)
        groups = [
            expand_evidence_group(item, by_id, by_block)
            for item in selected
        ]
        evidence_cards = build_evidence_cards(
            verified,
            by_id,
            preview_chars=evidence_card_preview_chars,
        )
        selected_ids = {item["direct_evidence_id"] for item in groups}
        label_counts = _verifier_label_counts(verified)
        pack.append(
            {
                "task": task.__dict__,
                "query_variants": query_variants,
                "candidate_ids": [item["evidence_id"] for item in candidates],
                "candidate_count": len(candidates),
                "initial_verify_k": verify_k,
                "adaptive_verify_k": adaptive_verify_k,
                "verified_count": adaptive_checked,
                "direct_verified_count": direct_count,
                "verified_candidates": verified,
                "evidence_cards": evidence_cards,
                "coverage_memory": {
                    "candidate_count": len(candidates),
                    "verified_count": adaptive_checked,
                    "verifier_label_counts": label_counts,
                    "direct_evidence_ids": [
                        item["evidence_id"] for item in verified if item["verifier_label"] == "direct"
                    ],
                    "partial_evidence_ids": [
                        item["evidence_id"] for item in verified if item["verifier_label"] == "partial"
                    ],
                    "false_evidence_ids": [
                        item["evidence_id"] for item in verified if item["verifier_label"] == "false"
                    ],
                    "selected_evidence_ids": sorted(selected_ids),
                    "unverified_candidate_ids": [
                        item["evidence_id"]
                        for item in candidates
                        if item["evidence_id"] not in {verified_item["evidence_id"] for verified_item in verified}
                    ],
                    "missing_direct_evidence": not any(item["verifier_label"] == "direct" for item in selected),
                },
                "selected_evidence_groups": groups,
                "missing_direct_evidence": not any(item["verifier_label"] == "direct" for item in selected),
            }
        )
    return pack


def verify_candidates(
    query_record: dict[str, Any],
    task: SearchTask,
    candidates: list[dict[str, Any]],
    *,
    llm,
    tokenizer,
    verifier_max_tokens: int,
    structured_json: bool,
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    prompts = []
    for candidate in candidates:
        record = candidate["record"]
        prompts.append(
            _chat_prompt(
                tokenizer,
                system=(
                    "You judge whether one SEC evidence chunk supports one retrieval task. "
                    "Return only valid JSON. Do not output hidden reasoning or <think> blocks."
                ),
                user=(
                    "Label this candidate as direct, partial, or false.\n"
                    "direct = contains evidence that can answer the task.\n"
                    "partial = useful context but not sufficient by itself.\n"
                    "false = same topic or noisy but does not answer the task.\n"
                    "Return schema: {\"label\":\"direct|partial|false\",\"reason\":\"...\",\"key_facts\":[\"...\"]}\n\n"
                    f"User question: {query_record['query']}\n"
                    f"Task question: {task.question}\n"
                    f"Must find: {task.must_find}\n"
                    f"Candidate metadata: evidence_id={record['evidence_id']}, ticker={record.get('ticker')}, "
                    f"year={record.get('fiscal_year')}, section={record.get('section')}, subsection={record.get('subsection')}, "
                    f"contains_table={record.get('metadata', {}).get('contains_table')}\n"
                    f"Candidate text:\n{_trim(record.get('text', ''), 1800)}"
                ),
            )
        )
    raw_outputs = (
        _generate_many(
            llm,
            prompts,
            max_tokens=verifier_max_tokens,
            temperature=0.0,
            structured_schema=VERIFIER_JSON_SCHEMA if structured_json else None,
        )
        if llm is not None
        else ["" for _ in prompts]
    )
    verified = []
    for candidate, raw in zip(candidates, raw_outputs):
        label = "partial"
        reason = "No verifier model output; retained as partial candidate."
        key_facts: list[str] = []
        if raw:
            try:
                payload = _extract_json(raw)
                label = str(payload.get("label", label)).lower()
                if label not in {"direct", "partial", "false"}:
                    label = "partial"
                reason = str(payload.get("reason", reason))
                key_facts = [str(item) for item in payload.get("key_facts", [])[:4]]
            except Exception as exc:
                reason = f"Verifier parse failed: {type(exc).__name__}: {exc}"
        verified.append(
            {
                "evidence_id": candidate["evidence_id"],
                "retrieval_rank": candidate["rank"],
                "retrieval_score": candidate["score"],
                "verifier_label": label,
                "verifier_reason": reason,
                "key_facts": key_facts,
                "verifier_raw": raw,
            }
        )
    return verified


def build_evidence_cards(
    verified: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    *,
    preview_chars: int,
) -> list[dict[str, Any]]:
    cards = []
    for item in verified:
        record = by_id.get(item["evidence_id"], {})
        cards.append(
            {
                "evidence_id": item["evidence_id"],
                "verifier_label": item["verifier_label"],
                "retrieval_rank": item.get("retrieval_rank"),
                "retrieval_score": item.get("retrieval_score"),
                "verifier_reason": _trim(str(item.get("verifier_reason", "")), 500),
                "key_facts": item.get("key_facts", []),
                "provenance": {
                    "ticker": record.get("ticker"),
                    "fiscal_year": record.get("fiscal_year"),
                    "section": record.get("section"),
                    "subsection": record.get("subsection"),
                    "block_id": record.get("metadata", {}).get("block_id"),
                    "contains_table": record.get("metadata", {}).get("contains_table", False),
                },
                "text_preview": _trim(record.get("text", ""), preview_chars),
            }
        )
    return cards


def _verifier_label_counts(verified: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"direct": 0, "partial": 0, "false": 0}
    for item in verified:
        label = item.get("verifier_label")
        if label in counts:
            counts[label] += 1
    return counts


def _table_rescue_candidates(
    task: SearchTask,
    candidates: list[dict[str, Any]],
    *,
    verified_ids: set[str],
    limit: int,
) -> list[dict[str, Any]]:
    if not _task_needs_table_rescue(task):
        return []

    scored = []
    for candidate in candidates:
        if candidate["evidence_id"] in verified_ids:
            continue
        record = candidate.get("record", {})
        section = str(candidate.get("section") or record.get("section") or "")
        contains_table = bool(candidate.get("contains_table") or record.get("metadata", {}).get("contains_table"))
        if not contains_table and "Item 8" not in section and "Item 7" not in section:
            continue
        score = _candidate_rescue_score(task, candidate)
        if score <= 0:
            continue
        scored.append((score, int(candidate.get("rank", 9999)), candidate))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [candidate for _, _, candidate in scored[:limit]]


def _task_needs_table_rescue(task: SearchTask) -> bool:
    lower_context = " ".join(
        [
            task.task_id,
            task.question,
            task.search_query,
            task.facet,
            " ".join(task.must_find),
        ]
    ).lower()
    if task.needs_table:
        return True
    if task.facet in {"revenue_growth", "margin_cost", "capex", "segment_mix", "rpo", "customer_metric"}:
        return True
    return any(
        phrase in lower_context
        for phrase in ("revenue", "sales", "gross margin", "capex", "capital", "cash flow", "segment", "backlog")
    )


def _candidate_rescue_score(task: SearchTask, candidate: dict[str, Any]) -> float:
    record = candidate.get("record", {})
    text = " ".join(
        [
            str(candidate.get("evidence_id", "")),
            str(candidate.get("section") or record.get("section") or ""),
            str(candidate.get("subsection") or record.get("subsection") or ""),
            str(record.get("metadata", {}).get("block_heading") or ""),
            str(record.get("text") or candidate.get("text_preview") or ""),
        ]
    ).lower()
    context = " ".join(
        [
            task.task_id,
            task.question,
            task.search_query,
            task.facet,
            " ".join(task.must_find),
        ]
    ).lower()
    score = 0.0
    if candidate.get("contains_table") or record.get("metadata", {}).get("contains_table"):
        score += 2.0
    if "item 8" in text:
        score += 1.5
    if "item 7" in text:
        score += 0.75
    if "[table_start" in text:
        score += 2.0

    for phrase in task.must_find:
        phrase = " ".join(str(phrase).lower().split())
        if phrase and phrase in text:
            score += 6.0

    for term in _query_terms(context):
        if term in text:
            score += 1.0

    if task.facet == "revenue_growth":
        if "note 2" in text or "disaggregated revenues" in text:
            score += 5.0
        if "segment" in text and "revenue" in text:
            score += 3.0
    if task.facet == "segment_mix" and ("note 15" in text or "segment" in text):
        score += 4.0
    if task.facet == "capex":
        if "purchases of property and equipment" in text or "cash used in investing" in text:
            score += 5.0
        if "capital expenditures" in text or "technical infrastructure" in text:
            score += 3.0
    if "cloud" in context:
        if "google cloud" in text or "microsoft cloud" in text:
            score += 4.0
    return score


def _query_terms(text: str) -> set[str]:
    stopwords = {
        "about",
        "alphabet",
        "apple",
        "based",
        "cloud",
        "does",
        "fiscal",
        "from",
        "growth",
        "microsoft",
        "nvidia",
        "pressure",
        "revenue",
        "their",
        "what",
        "year",
    }
    return {term for term in re.findall(r"[a-z0-9]+", text.lower()) if len(term) >= 4 and term not in stopwords}


def select_evidence(task: SearchTask, verified: list[dict[str, Any]], selected_per_task: int) -> list[dict[str, Any]]:
    direct = [item for item in verified if item["verifier_label"] == "direct"]
    partial = [item for item in verified if item["verifier_label"] == "partial"]
    selected = [*direct, *partial]
    return selected[:selected_per_task]


def expand_evidence_group(
    selected: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    by_block: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    record = by_id[selected["evidence_id"]]
    block_id = record.get("metadata", {}).get("block_id")
    block_records = by_block.get(block_id, [record]) if block_id else [record]
    direct_index = next(
        (idx for idx, item in enumerate(block_records) if item["evidence_id"] == record["evidence_id"]),
        0,
    )
    context_records = []
    for idx in (direct_index - 1, direct_index + 1):
        if 0 <= idx < len(block_records):
            context_records.append(block_records[idx])
    merged_ids = [record["evidence_id"], *[item["evidence_id"] for item in context_records]]
    merged_text = "\n\n".join(
        [
            f"[{record['evidence_id']}]\n{record.get('text', '')}",
            *[
                f"[context:{item['evidence_id']}]\n{item.get('text', '')}"
                for item in context_records
            ],
        ]
    )
    return {
        "evidence_group_id": block_id or record["evidence_id"],
        "direct_evidence_id": record["evidence_id"],
        "context_evidence_ids": [item["evidence_id"] for item in context_records],
        "merged_evidence_ids": merged_ids,
        "verifier_label": selected["verifier_label"],
        "verifier_reason": selected["verifier_reason"],
        "key_facts": selected.get("key_facts", []),
        "ticker": record.get("ticker"),
        "fiscal_year": record.get("fiscal_year"),
        "section": record.get("section"),
        "subsection": record.get("subsection"),
        "contains_table": record.get("metadata", {}).get("contains_table", False),
        "text_for_synthesis": _trim(merged_text, 3000),
    }


def build_task_evidence_pool(
    evidence_pack: list[dict[str, Any]],
    *,
    per_task_budget_chars: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pool = []
    task_stats = []
    for task_pack in evidence_pack:
        task_memory, stats = _fit_task_memory(task_pack, per_task_budget_chars)
        pool.append(task_memory)
        task_stats.append(stats)
    serialized_chars = len(json.dumps(pool, ensure_ascii=False))
    return pool, {
        "task_count": len(pool),
        "per_task_budget_chars": per_task_budget_chars,
        "serialized_pool_chars": serialized_chars,
        "task_stats": task_stats,
    }


def _fit_task_memory(
    task_pack: dict[str, Any],
    per_task_budget_chars: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    group_limits = [2200, 1600, 1200, 800, 500, 250, 0]
    card_limits = [700, 450, 250, 120, 0]
    card_count_limits: list[int | None] = [None, 8, 5, 3, 0]
    include_candidate_id_options = [True, False]
    best_memory: dict[str, Any] | None = None
    best_stats: dict[str, Any] | None = None
    for include_candidate_ids in include_candidate_id_options:
        for max_cards in card_count_limits:
            for group_limit in group_limits:
                for card_limit in card_limits:
                    memory = _task_memory_snapshot(
                        task_pack,
                        group_limit,
                        card_limit,
                        max_cards=max_cards,
                        include_candidate_ids=include_candidate_ids,
                    )
                    serialized_chars = len(json.dumps(memory, ensure_ascii=False))
                    stats = {
                        "task_id": task_pack["task"].get("task_id"),
                        "serialized_chars": serialized_chars,
                        "group_text_chars": group_limit,
                        "card_text_chars": card_limit,
                        "max_cards": max_cards,
                        "candidate_ids_included": include_candidate_ids,
                        "within_budget": serialized_chars <= per_task_budget_chars,
                        "selected_group_count": len(task_pack.get("selected_evidence_groups", [])),
                        "evidence_card_count": len(task_pack.get("evidence_cards", [])),
                        "evidence_card_count_in_prompt": len(memory["evidence_memory"]["cards"]),
                    }
                    best_memory = memory
                    best_stats = stats
                    if serialized_chars <= per_task_budget_chars:
                        return memory, stats
    assert best_memory is not None and best_stats is not None
    return best_memory, best_stats


def _task_memory_snapshot(
    task_pack: dict[str, Any],
    group_text_chars: int,
    card_text_chars: int,
    *,
    max_cards: int | None,
    include_candidate_ids: bool,
) -> dict[str, Any]:
    task = task_pack["task"]
    cards = _select_cards_for_memory(task_pack.get("evidence_cards", []), max_cards=max_cards)
    candidate_ids = task_pack.get("candidate_ids", [])
    verified_candidate_ids = [item.get("evidence_id") for item in task_pack.get("verified_candidates", [])]
    return {
        "planner_memory": {
            "task_id": task.get("task_id"),
            "question": task.get("question"),
            "search_query": task.get("search_query"),
            "facet": task.get("facet"),
            "ticker": task.get("ticker"),
            "fiscal_year": task.get("fiscal_year"),
            "must_find": task.get("must_find", []),
            "needs_table": task.get("needs_table"),
            "query_variants": task_pack.get("query_variants", []),
        },
        "coverage_memory": _compact_coverage_memory(
            task_pack.get("coverage_memory", {}),
            include_candidate_ids=include_candidate_ids,
        ),
        "evidence_memory": {
            "cards": [
                _compact_evidence_card(card, card_text_chars)
                for card in cards
            ],
            "selected_groups": [
                _compact_selected_group(group, group_text_chars)
                for group in task_pack.get("selected_evidence_groups", [])
            ],
        },
        "audit_memory": {
            "candidate_count": len(candidate_ids),
            "candidate_ids": candidate_ids if include_candidate_ids else [],
            "candidate_ids_omitted": not include_candidate_ids,
            "verified_candidate_count": len(verified_candidate_ids),
            "verified_candidate_ids": verified_candidate_ids if include_candidate_ids else [],
            "selected_evidence_ids": task_pack.get("coverage_memory", {}).get("selected_evidence_ids", []),
        },
    }


def _compact_coverage_memory(
    coverage: dict[str, Any],
    *,
    include_candidate_ids: bool,
) -> dict[str, Any]:
    compact = {
        "candidate_count": coverage.get("candidate_count"),
        "verified_count": coverage.get("verified_count"),
        "verifier_label_counts": coverage.get("verifier_label_counts", {}),
        "direct_evidence_ids": coverage.get("direct_evidence_ids", []),
        "selected_evidence_ids": coverage.get("selected_evidence_ids", []),
        "missing_direct_evidence": coverage.get("missing_direct_evidence"),
    }
    if include_candidate_ids:
        compact["partial_evidence_ids_sample"] = coverage.get("partial_evidence_ids", [])[:8]
        compact["false_evidence_ids_sample"] = coverage.get("false_evidence_ids", [])[:4]
        compact["unverified_candidate_ids_sample"] = coverage.get("unverified_candidate_ids", [])[:4]
    else:
        compact["id_lists_compacted"] = True
    return compact


def _select_cards_for_memory(cards: list[dict[str, Any]], *, max_cards: int | None) -> list[dict[str, Any]]:
    if max_cards is None or len(cards) <= max_cards:
        return cards
    if max_cards <= 0:
        return []
    label_priority = {"direct": 0, "partial": 1, "false": 2}
    ranked = sorted(
        cards,
        key=lambda card: (
            label_priority.get(card.get("verifier_label"), 9),
            int(card.get("retrieval_rank") or 9999),
            str(card.get("evidence_id")),
        ),
    )
    return ranked[:max_cards]


def _compact_evidence_card(card: dict[str, Any], text_chars: int) -> dict[str, Any]:
    preview_chars = text_chars
    if card.get("verifier_label") == "false":
        preview_chars = min(text_chars, 120)
    return {
        "evidence_id": card.get("evidence_id"),
        "label": card.get("verifier_label"),
        "retrieval_rank": card.get("retrieval_rank"),
        "key_facts": card.get("key_facts", []),
        "reason": _trim(str(card.get("verifier_reason", "")), 300),
        "provenance": card.get("provenance", {}),
        "text_preview": _trim(str(card.get("text_preview", "")), preview_chars) if preview_chars > 0 else "",
    }


def _compact_selected_group(group: dict[str, Any], text_chars: int) -> dict[str, Any]:
    return {
        "evidence_group_id": group.get("evidence_group_id"),
        "direct_evidence_id": group.get("direct_evidence_id"),
        "merged_evidence_ids": group.get("merged_evidence_ids", []),
        "label": group.get("verifier_label"),
        "key_facts": group.get("key_facts", []),
        "ticker": group.get("ticker"),
        "fiscal_year": group.get("fiscal_year"),
        "section": group.get("section"),
        "subsection": group.get("subsection"),
        "contains_table": group.get("contains_table"),
        "text_for_synthesis": _trim(str(group.get("text_for_synthesis", "")), text_chars) if text_chars > 0 else "",
    }


def synthesize_answer(
    query_record: dict[str, Any],
    evidence_pack: list[dict[str, Any]],
    *,
    llm,
    tokenizer,
    synthesis_max_tokens: int,
    task_synthesis_budget_chars: int,
    max_model_len: int,
    structured_json: bool,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    prompt = ""
    synthesis_input_audit: dict[str, Any] = {}
    max_input_tokens = max(512, max_model_len - synthesis_max_tokens - 128)
    attempted_budgets = _synthesis_budget_candidates(task_synthesis_budget_chars)
    for budget in attempted_budgets:
        task_evidence_pool, synthesis_input_audit = build_task_evidence_pool(
            evidence_pack,
            per_task_budget_chars=budget,
        )
        prompt = _make_synthesis_prompt(query_record, task_evidence_pool, tokenizer)
        prompt_tokens = _prompt_token_count(tokenizer, prompt)
        synthesis_input_audit["prompt_chars"] = len(prompt)
        synthesis_input_audit["prompt_tokens"] = prompt_tokens
        synthesis_input_audit["max_input_tokens"] = max_input_tokens
        synthesis_input_audit["budget_attempts"] = attempted_budgets
        synthesis_input_audit["selected_budget_chars"] = budget
        if prompt_tokens is None or prompt_tokens <= max_input_tokens:
            synthesis_input_audit["within_model_context"] = True
            break
        synthesis_input_audit["within_model_context"] = False
    if llm is None:
        return {
            "answer": "No resident model was loaded; synthesis skipped.",
            "key_findings": [],
            "missing_or_uncertain": ["resident_model_disabled"],
            "evidence_pack_quality": "weak",
        }, "", synthesis_input_audit
    raw = _generate_one(
        llm,
        prompt,
        max_tokens=synthesis_max_tokens,
        temperature=0.0,
        structured_schema=SYNTHESIS_JSON_SCHEMA if structured_json else None,
    )
    try:
        payload = _extract_json(raw)
        return payload, raw, synthesis_input_audit
    except Exception as exc:
        return {
            "answer": raw,
            "key_findings": [],
            "missing_or_uncertain": [f"synthesis_json_parse_failed: {type(exc).__name__}: {exc}"],
            "evidence_pack_quality": "mixed",
        }, raw, synthesis_input_audit


def _synthesis_budget_candidates(initial_budget: int) -> list[int]:
    candidates = [
        initial_budget,
        int(initial_budget * 0.75),
        int(initial_budget * 0.55),
        int(initial_budget * 0.4),
        1800,
        1200,
        800,
        500,
    ]
    output: list[int] = []
    for value in candidates:
        value = max(250, int(value))
        if value not in output:
            output.append(value)
    return sorted(output, reverse=True)


def _make_synthesis_prompt(
    query_record: dict[str, Any],
    task_evidence_pool: list[dict[str, Any]],
    tokenizer,
) -> str:
    return _chat_prompt(
        tokenizer,
        system=(
            "You are an evidence-grounded financial analyst. Use only the provided SEC evidence. "
            "Return valid JSON. Do not invent numbers or conclusions not supported by evidence IDs. "
            "Do not output hidden reasoning or <think> blocks."
        ),
        user=(
            "Write the final answer from this Evidence Pack.\n"
            "Return schema: {\"answer\":\"...\",\"key_findings\":[{\"claim\":\"...\",\"evidence_ids\":[\"...\"]}],"
            "\"missing_or_uncertain\":[\"...\"],\"evidence_pack_quality\":\"good|mixed|weak\"}\n\n"
            f"Question mode: {query_record.get('mode')}\n"
            f"Question: {query_record['query']}\n"
            "Task Evidence Pool JSON. Every task is present; raw evidence text is budgeted per task.\n"
            f"{json.dumps(task_evidence_pool, ensure_ascii=False)}"
        ),
    )


def _prompt_token_count(tokenizer, prompt: str) -> int | None:
    if tokenizer is None or not hasattr(tokenizer, "encode"):
        return None
    return len(tokenizer.encode(prompt, add_special_tokens=False))


def _load_vllm(args: argparse.Namespace):
    from transformers import AutoTokenizer
    from vllm import LLM

    model_path = str(REPO_ROOT / args.model_path)
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
        "enforce_eager": True,
        "max_num_seqs": args.max_num_seqs,
    }
    if args.quantization and args.quantization.lower() not in {"none", "null", "auto"}:
        llm_kwargs["quantization"] = args.quantization
    if args.language_model_only:
        llm_kwargs["language_model_only"] = True
    if args.skip_mm_profiling:
        llm_kwargs["skip_mm_profiling"] = True
    llm = LLM(**llm_kwargs)
    return llm, tokenizer


def _generate_one(
    llm,
    prompt: str,
    *,
    max_tokens: int,
    temperature: float,
    structured_schema: dict[str, Any] | None = None,
) -> str:
    return _generate_many(
        llm,
        [prompt],
        max_tokens=max_tokens,
        temperature=temperature,
        structured_schema=structured_schema,
    )[0]


def _generate_many(
    llm,
    prompts: list[str],
    *,
    max_tokens: int,
    temperature: float,
    structured_schema: dict[str, Any] | None = None,
) -> list[str]:
    from vllm import SamplingParams
    from vllm.sampling_params import StructuredOutputsParams

    sampling_kwargs: dict[str, Any] = {
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": 1.0,
    }
    if structured_schema is not None:
        sampling_kwargs["structured_outputs"] = StructuredOutputsParams(
            json=structured_schema,
            disable_additional_properties=True,
        )

    outputs = llm.generate(
        prompts,
        SamplingParams(**sampling_kwargs),
    )
    return [output.outputs[0].text.strip() for output in outputs]


def _chat_prompt(tokenizer, *, system: str, user: str) -> str:
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
            pass
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True) + "\n/no_think\n"
    return f"System:\n{system}\n\nUser:\n{user}\n/no_think\n\nAssistant:\n"


def _task_from_dict(item: dict[str, Any], query_record: dict[str, Any]) -> SearchTask:
    ticker = item.get("ticker")
    if isinstance(ticker, list):
        ticker = ticker[0] if ticker else None
    if not ticker:
        known = query_record.get("ticker")
        ticker = known if isinstance(known, str) else None
    fiscal_year = item.get("fiscal_year") or query_record.get("fiscal_year")
    return SearchTask(
        task_id=str(item.get("task_id") or item.get("facet") or "task"),
        question=str(item.get("question") or item.get("search_query") or query_record["query"]),
        search_query=str(item.get("search_query") or item.get("question") or query_record["query"]),
        facet=str(item.get("facet") or "other"),
        ticker=str(ticker) if ticker else None,
        fiscal_year=int(fiscal_year) if fiscal_year else None,
        section_hints=[str(x) for x in item.get("section_hints", [])],
        evidence_type_hints=[str(x) for x in item.get("evidence_type_hints", [])],
        must_find=[str(x) for x in item.get("must_find", [])],
        needs_table=bool(item.get("needs_table", False)),
    )


def _fallback_tasks(query_record: dict[str, Any]) -> list[SearchTask]:
    ticker = query_record.get("ticker")
    ticker = ticker if isinstance(ticker, str) else None
    fiscal_year = query_record.get("fiscal_year")
    return [
        SearchTask(
            task_id="fallback_original_query",
            question=query_record["query"],
            search_query=query_record["query"],
            facet="other",
            ticker=ticker,
            fiscal_year=int(fiscal_year) if fiscal_year else None,
        )
    ]


def _task_query_variants(task: SearchTask, *, max_variants: int) -> list[str]:
    variants: list[str] = []

    def add(text: str) -> None:
        compact = " ".join(str(text).split())
        if compact and compact.lower() not in {item.lower() for item in variants}:
            variants.append(compact)

    lower_context = " ".join(
        [
            task.task_id,
            task.question,
            task.search_query,
            task.facet,
            " ".join(task.must_find),
        ]
    ).lower()
    add(task.search_query)
    if "customer" in lower_context or "concentration" in lower_context:
        add("concentration of revenue direct customers major customers percentage")
    if "cloud" in lower_context and "revenue" in lower_context:
        add("cloud revenues segment revenues Azure Google Cloud")
        add("disaggregated revenues Google Cloud Microsoft Cloud segment revenues")
    if "capex" in lower_context or "capital expenditure" in lower_context or "infrastructure" in lower_context:
        add("capital expenditures technical infrastructure servers network equipment data centers")
        add("purchases of property and equipment cash used in investing activities capital expenditures")
    add(task.question)
    if task.must_find:
        add(" ".join(task.must_find))
    for hint in FACET_QUERY_HINTS.get(task.facet, []):
        add(hint)
    return variants[:max(1, max_variants)]


def _round_robin_variant_fusion(
    variant_results: list[tuple[str, str, list[dict[str, Any]]]],
    *,
    top_k: int,
    original_quota: int,
) -> list[dict[str, Any]]:
    positions = [0 for _ in variant_results]
    seen: set[str] = set()
    fused: list[dict[str, Any]] = []

    if variant_results and original_quota > 0:
        source, query_text, results = variant_results[0]
        for result in results[:original_quota]:
            evidence_id = result["evidence_id"]
            if evidence_id in seen:
                continue
            seen.add(evidence_id)
            base = dict(result)
            base["rank"] = len(fused) + 1
            base["query_variant_fusion"] = {
                "strategy": "original_quota_then_round_robin",
                "source": source,
                "source_query": query_text,
                "source_rank": result.get("rank"),
                "source_score": result.get("score"),
            }
            fused.append(base)
            positions[0] += 1
            if len(fused) >= top_k:
                return fused

    while len(fused) < top_k:
        appended = False
        for variant_index, (source, query_text, results) in enumerate(variant_results):
            while positions[variant_index] < len(results):
                result = results[positions[variant_index]]
                positions[variant_index] += 1
                evidence_id = result["evidence_id"]
                if evidence_id in seen:
                    continue
                seen.add(evidence_id)
                base = dict(result)
                base["rank"] = len(fused) + 1
                base["query_variant_fusion"] = {
                    "strategy": "original_quota_then_round_robin",
                    "source": source,
                    "source_query": query_text,
                    "source_rank": result.get("rank"),
                    "source_score": result.get("score"),
                }
                fused.append(base)
                appended = True
                break
            if len(fused) >= top_k:
                break
        if not appended:
            break
    return fused


def _weighted_fusion(
    ranked_lists: dict[str, list[dict[str, Any]]],
    weights: dict[str, float],
    *,
    top_k: int,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    scores: dict[str, float] = defaultdict(float)
    records: dict[str, dict[str, Any]] = {}
    features: dict[str, dict[str, Any]] = defaultdict(dict)
    for source, results in ranked_lists.items():
        for result in results:
            evidence_id = result["evidence_id"]
            rank = int(result["rank"])
            scores[evidence_id] += weights.get(source, 1.0) / (rrf_k + rank)
            records.setdefault(evidence_id, result)
            features[evidence_id][f"{source}_rank"] = rank
            features[evidence_id][f"{source}_score"] = result.get("score")
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
    output = []
    for rank, (evidence_id, score) in enumerate(ranked, start=1):
        base = dict(records[evidence_id])
        base["rank"] = rank
        base["score"] = score
        base["fusion"] = features[evidence_id]
        output.append(base)
    return output


def _summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "query_count": len(results),
        "task_count": 0,
        "tasks_with_direct_evidence": 0,
        "tasks_missing_direct_evidence": 0,
        "verified_candidates": 0,
        "verifier_labels": {"direct": 0, "partial": 0, "false": 0},
        "adaptive_verified_tasks": 0,
    }
    per_query = []
    for result in results:
        query_summary = {
            "query_id": result["query_id"],
            "task_count": len(result["evidence_pack"]),
            "tasks_with_direct_evidence": 0,
            "tasks_missing_direct_evidence": 0,
            "evidence_pack_quality": result.get("synthesis", {}).get("evidence_pack_quality"),
        }
        for task_pack in result["evidence_pack"]:
            summary["task_count"] += 1
            if task_pack.get("verified_count", 0) > task_pack.get("initial_verify_k", 0):
                summary["adaptive_verified_tasks"] += 1
            if task_pack["missing_direct_evidence"]:
                summary["tasks_missing_direct_evidence"] += 1
                query_summary["tasks_missing_direct_evidence"] += 1
            else:
                summary["tasks_with_direct_evidence"] += 1
                query_summary["tasks_with_direct_evidence"] += 1
            for candidate in task_pack["verified_candidates"]:
                summary["verified_candidates"] += 1
                label = candidate.get("verifier_label")
                if label in summary["verifier_labels"]:
                    summary["verifier_labels"][label] += 1
        per_query.append(query_summary)
    summary["per_query"] = per_query
    return summary


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


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_evidence(path: Path) -> list[dict[str, Any]]:
    return _load_jsonl(path)


def _group_by_block(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        block_id = record.get("metadata", {}).get("block_id")
        if block_id:
            groups[block_id].append(record)
    for items in groups.values():
        items.sort(
            key=lambda record: (
                record.get("metadata", {}).get("block_part_index") or 0,
                record.get("metadata", {}).get("chunk_index") or 0,
            )
        )
    return groups


def _trim(text: str, max_chars: int) -> str:
    compact = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    return compact[:max_chars] + ("\n...[truncated]" if len(compact) > max_chars else "")


if __name__ == "__main__":
    main()
