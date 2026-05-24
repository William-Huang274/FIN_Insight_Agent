from __future__ import annotations

import argparse
import inspect
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from eval.object_verifier import load_structured_object_map, read_jsonl  # noqa: E402
from evidence.structured_text import structured_object_preview, structured_object_search_text  # noqa: E402


LABEL_GAIN = {"direct": 2.0, "partial": 1.0, "false": 0.0, "unlabeled": 0.0}
LABEL_RELEVANT = {"direct", "partial"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a cross-encoder reranker on object BM25 candidates."
    )
    parser.add_argument(
        "--mode",
        choices=["bm25", "cross-encoder", "qwen-reranker"],
        default="cross-encoder",
    )
    parser.add_argument(
        "--model-name",
        default="BAAI/bge-reranker-v2-m3",
        help="Sentence-Transformers CrossEncoder model name when mode=cross-encoder.",
    )
    parser.add_argument(
        "--model-alias",
        default=None,
        help="Short name used in output mode fields.",
    )
    parser.add_argument(
        "--predictions-path",
        default="reports/retrieval_eval/sec_tech_10k_object_bm25_variant_predictions.jsonl",
    )
    parser.add_argument(
        "--labels-path",
        default="eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates_codex_labeled.jsonl",
    )
    parser.add_argument(
        "--structured-dir",
        default="data/processed_private/structured_objects",
    )
    parser.add_argument("--prefix", default="sec_tech_10k")
    parser.add_argument(
        "--output-predictions-path",
        default="reports/retrieval_eval/sec_tech_10k_object_reranker_predictions.jsonl",
    )
    parser.add_argument(
        "--report-path",
        default="reports/retrieval_eval/sec_tech_10k_object_reranker_eval.json",
    )
    parser.add_argument("--candidate-top-k", type=int, default=25)
    parser.add_argument("--selected-top-k", type=int, default=5)
    parser.add_argument("--metric-k", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--doc-max-chars", type=int, default=6000)
    parser.add_argument("--device", default=None)
    parser.add_argument(
        "--instruction",
        default=(
            "Given a financial research sub-question, retrieve SEC 10-K "
            "structured evidence that directly supports the requested metric, "
            "claim, caveat, company, fiscal year, and segment."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start = time.perf_counter()
    predictions = list(read_jsonl(REPO_ROOT / args.predictions_path))
    labels = _load_labels(REPO_ROOT / args.labels_path) if args.labels_path else {}
    object_map = load_structured_object_map(REPO_ROOT / args.structured_dir, args.prefix)
    model_alias = args.model_alias or _safe_alias(args.model_name if args.mode == "cross-encoder" else "bm25")
    model = _load_model(args) if args.mode in {"cross-encoder", "qwen-reranker"} else None

    output_rows = []
    facet_reports = []
    scored_pairs = 0
    scoring_seconds = 0.0
    for row in predictions:
        output_row, reports, pair_count, score_time = _rerank_query(row, labels, object_map, model, args)
        output_rows.append(output_row)
        facet_reports.extend(reports)
        scored_pairs += pair_count
        scoring_seconds += score_time

    report = _summarize(facet_reports)
    report.update(
        {
            "mode": f"object_reranker_{model_alias}",
            "reranker_mode": args.mode,
            "model_name": args.model_name if args.mode in {"cross-encoder", "qwen-reranker"} else "bm25_candidate_order",
            "model_alias": model_alias,
            "candidate_top_k": args.candidate_top_k,
            "selected_top_k": args.selected_top_k,
            "metric_k": args.metric_k,
            "batch_size": args.batch_size,
            "max_length": args.max_length,
            "doc_max_chars": args.doc_max_chars,
            "device": args.device,
            "scored_pairs": scored_pairs,
            "scoring_seconds": round(scoring_seconds, 4),
            "wall_seconds": round(time.perf_counter() - start, 4),
            "output_predictions_path": str(REPO_ROOT / args.output_predictions_path),
            "report_path": str(REPO_ROOT / args.report_path),
        }
    )

    output_path = REPO_ROOT / args.output_predictions_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in output_rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    report_path = REPO_ROOT / args.report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _load_model(args: argparse.Namespace) -> Any:
    if args.mode == "qwen-reranker":
        return QwenRerankerScorer(args.model_name, args.instruction, args.max_length, args.device)

    from sentence_transformers import CrossEncoder

    init_params = inspect.signature(CrossEncoder.__init__).parameters
    kwargs: dict[str, Any] = {
        "max_length": args.max_length,
    }
    if args.device:
        kwargs["device"] = args.device
    if "trust_remote_code" in init_params:
        kwargs["trust_remote_code"] = True
    if "Qwen3-Reranker" in args.model_name and "prompts" in init_params:
        kwargs["prompts"] = {"finance": args.instruction}
        kwargs["default_prompt_name"] = "finance"
    return CrossEncoder(args.model_name, **kwargs)


class QwenRerankerScorer:
    """Official Qwen3 reranker scoring via yes/no causal LM logits."""

    def __init__(
        self,
        model_name_or_path: str,
        instruction: str,
        max_length: int,
        device: str | None,
    ) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.instruction = instruction
        self.max_length = max_length
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name_or_path,
            padding_side="left",
            trust_remote_code=True,
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name_or_path,
            torch_dtype=torch.float16 if self.device.startswith("cuda") else torch.float32,
            trust_remote_code=True,
        ).to(self.device)
        self.model.eval()
        self.token_false_id = self.tokenizer.convert_tokens_to_ids("no")
        self.token_true_id = self.tokenizer.convert_tokens_to_ids("yes")
        prefix = (
            "<|im_start|>system\n"
            "Judge whether the Document meets the requirements based on the Query and the Instruct provided. "
            'Note that the answer can only be "yes" or "no".<|im_end|>\n'
            "<|im_start|>user\n"
        )
        suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
        self.prefix_tokens = self.tokenizer.encode(prefix, add_special_tokens=False)
        self.suffix_tokens = self.tokenizer.encode(suffix, add_special_tokens=False)

    def predict(
        self,
        pairs: list[tuple[str, str]],
        batch_size: int = 4,
        show_progress_bar: bool | None = None,
    ) -> list[float]:
        del show_progress_bar
        scores: list[float] = []
        for start in range(0, len(pairs), batch_size):
            batch = pairs[start : start + batch_size]
            texts = [self._format_pair(query, doc) for query, doc in batch]
            inputs = self._process_inputs(texts)
            with self.torch.no_grad():
                batch_scores = self.model(**inputs).logits[:, -1, :]
                true_scores = batch_scores[:, self.token_true_id]
                false_scores = batch_scores[:, self.token_false_id]
                yes_no_scores = self.torch.stack([false_scores, true_scores], dim=1)
                yes_probs = self.torch.nn.functional.log_softmax(yes_no_scores, dim=1)[:, 1].exp()
            scores.extend(float(item) for item in yes_probs.detach().cpu().tolist())
        return scores

    def _format_pair(self, query: str, doc: str) -> str:
        return f"<Instruct>: {self.instruction}\n<Query>: {query}\n<Document>: {doc}"

    def _process_inputs(self, texts: list[str]) -> dict[str, Any]:
        payload_max_length = self.max_length - len(self.prefix_tokens) - len(self.suffix_tokens)
        if payload_max_length <= 0:
            raise ValueError("max_length is too small for Qwen reranker prompt tokens")
        inputs = self.tokenizer(
            texts,
            padding=False,
            truncation="longest_first",
            return_attention_mask=False,
            max_length=payload_max_length,
        )
        for index, input_ids in enumerate(inputs["input_ids"]):
            inputs["input_ids"][index] = self.prefix_tokens + input_ids + self.suffix_tokens
        padded = self.tokenizer.pad(
            inputs,
            padding=True,
            return_tensors="pt",
            max_length=self.max_length,
        )
        return {key: value.to(self.device) for key, value in padded.items()}


def _rerank_query(
    row: dict[str, Any],
    labels: dict[tuple[str, str, str], str],
    object_map: dict[str, dict[str, Any]],
    model: Any,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[dict[str, Any]], int, float]:
    query_id = row.get("query_id")
    output_facets = []
    reports = []
    all_candidate_ids: list[str] = []
    all_selected_ids: list[str] = []
    scored_pairs = 0
    score_time = 0.0
    for facet_pred in row.get("facet_predictions", []):
        facet = facet_pred.get("facet")
        candidates = _candidate_records(facet_pred, object_map, args.candidate_top_k)
        rerank_query = _rerank_query_text(facet_pred)
        if args.mode in {"cross-encoder", "qwen-reranker"}:
            docs = [_object_document(item["object"], args.doc_max_chars) for item in candidates]
            pairs = [(rerank_query, doc) for doc in docs]
            pair_start = time.perf_counter()
            scores = model.predict(
                pairs,
                batch_size=args.batch_size,
                show_progress_bar=False,
            )
            score_time += time.perf_counter() - pair_start
            scored_pairs += len(pairs)
            for item, score in zip(candidates, scores):
                item["rerank_score"] = float(score)
        else:
            for item in candidates:
                item["rerank_score"] = -float(item["bm25_rank"])

        ranked = sorted(
            candidates,
            key=lambda item: (-float(item["rerank_score"]), int(item["bm25_rank"]), item["object_id"]),
        )
        selected = ranked[: args.selected_top_k]
        candidate_ids = [item["object_id"] for item in ranked]
        selected_ids = [item["object_id"] for item in selected]
        all_candidate_ids.extend(candidate_ids)
        all_selected_ids.extend(selected_ids)
        output_facets.append(
            {
                **facet_pred,
                "reranker": {
                    "mode": args.mode,
                    "model_name": args.model_name if args.mode in {"cross-encoder", "qwen-reranker"} else "bm25_candidate_order",
                    "candidate_top_k": args.candidate_top_k,
                    "selected_top_k": args.selected_top_k,
                },
                "candidate_object_ids": candidate_ids,
                "selected_object_ids": selected_ids,
                "cited_object_ids": [],
                "hits": [_hit_payload(item, rank) for rank, item in enumerate(ranked, start=1)],
            }
        )
        reports.append(_facet_metrics(query_id, facet, ranked, labels, args.metric_k))

    return (
        {
            "query_id": query_id,
            "cohort": row.get("cohort"),
            "mode": row.get("mode"),
            "difficulty": row.get("difficulty"),
            "scoring_profile": row.get("scoring_profile"),
            "query": row.get("query"),
            "query_en": row.get("query_en"),
            "query_zh": row.get("query_zh"),
            "ticker": row.get("ticker"),
            "tickers": row.get("tickers"),
            "fiscal_year": row.get("fiscal_year"),
            "fiscal_years": row.get("fiscal_years"),
            "ideal_facets": row.get("ideal_facets", []),
            "candidate_object_ids": list(dict.fromkeys(all_candidate_ids)),
            "selected_object_ids": list(dict.fromkeys(all_selected_ids)),
            "cited_object_ids": [],
            "facet_predictions": output_facets,
        },
        reports,
        scored_pairs,
        score_time,
    )


def _candidate_records(
    facet_pred: dict[str, Any],
    object_map: dict[str, dict[str, Any]],
    candidate_top_k: int,
) -> list[dict[str, Any]]:
    hit_by_id = {
        hit.get("object_id"): hit
        for hit in facet_pred.get("hits", [])
        if hit.get("object_id")
    }
    records = []
    for rank, object_id in enumerate(facet_pred.get("candidate_object_ids", [])[:candidate_top_k], start=1):
        obj = object_map.get(object_id)
        if not obj:
            continue
        hit = hit_by_id.get(object_id, {})
        records.append(
            {
                "object_id": object_id,
                "object": obj,
                "bm25_rank": hit.get("rank", rank),
                "bm25_score": hit.get("score"),
            }
        )
    return records


def _rerank_query_text(facet_pred: dict[str, Any]) -> str:
    variants = [str(item) for item in facet_pred.get("query_variants", []) if str(item).strip()]
    if len(variants) >= 2:
        return variants[1]
    return str(facet_pred.get("query") or "")


def _object_document(obj: dict[str, Any], max_chars: int) -> str:
    text = structured_object_search_text(obj)
    return text[:max_chars]


def _hit_payload(item: dict[str, Any], rank: int) -> dict[str, Any]:
    obj = item["object"]
    return {
        "rank": rank,
        "score": item["rerank_score"],
        "rerank_score": item["rerank_score"],
        "bm25_rank": item.get("bm25_rank"),
        "bm25_score": item.get("bm25_score"),
        "object_id": item["object_id"],
        "object_type": obj.get("object_type"),
        "source_evidence_id": obj.get("source_evidence_id"),
        "preview": structured_object_preview(obj),
    }


def _facet_metrics(
    query_id: str,
    facet: str,
    ranked: list[dict[str, Any]],
    labels: dict[tuple[str, str, str], str],
    k: int,
) -> dict[str, Any]:
    top_items = ranked[:k]
    all_labels = [_label_for(query_id, facet, item["object_id"], labels) for item in ranked]
    top_labels = all_labels[:k]
    gains = [LABEL_GAIN[label] for label in all_labels]
    return {
        "query_id": query_id,
        "facet": facet,
        "candidate_count": len(ranked),
        f"precision_relevant_at_{k}": _ratio(sum(label in LABEL_RELEVANT for label in top_labels), k),
        f"precision_direct_at_{k}": _ratio(sum(label == "direct" for label in top_labels), k),
        f"false_at_{k}": sum(label == "false" for label in top_labels),
        f"ndcg_at_{k}": _ndcg(gains, k),
        "mrr_direct": _mrr(all_labels, "direct"),
        "mrr_relevant": _mrr_relevant(all_labels),
        "direct_hit_at_k": any(label == "direct" for label in top_labels),
        "relevant_hit_at_k": any(label in LABEL_RELEVANT for label in top_labels),
        "top_ids": [item["object_id"] for item in top_items],
        "top_labels": top_labels,
    }


def _summarize(facet_reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not facet_reports:
        return {"facet_count": 0}
    metric_keys = [
        key
        for key in facet_reports[0].keys()
        if key.startswith("precision_") or key.startswith("false_at_") or key.startswith("ndcg_")
    ]
    summary: dict[str, Any] = {
        "facet_count": len(facet_reports),
        "direct_hit_facet_coverage_at_k": _ratio(
            sum(item["direct_hit_at_k"] for item in facet_reports),
            len(facet_reports),
        ),
        "relevant_hit_facet_coverage_at_k": _ratio(
            sum(item["relevant_hit_at_k"] for item in facet_reports),
            len(facet_reports),
        ),
        "mean_mrr_direct": round(
            sum(item["mrr_direct"] for item in facet_reports) / len(facet_reports),
            4,
        ),
        "mean_mrr_relevant": round(
            sum(item["mrr_relevant"] for item in facet_reports) / len(facet_reports),
            4,
        ),
        "facets": facet_reports,
    }
    for key in metric_keys:
        summary[f"mean_{key}"] = round(
            sum(float(item[key]) for item in facet_reports) / len(facet_reports),
            4,
        )
    return summary


def _load_labels(path: Path) -> dict[tuple[str, str, str], str]:
    return {
        (row["query_id"], row["facet"], row["object_id"]): row.get("human_label", "unlabeled")
        for row in read_jsonl(path)
    }


def _label_for(
    query_id: str,
    facet: str,
    object_id: str,
    labels: dict[tuple[str, str, str], str],
) -> str:
    return labels.get((query_id, facet, object_id), "unlabeled")


def _dcg(gains: list[float], k: int) -> float:
    return sum((2.0**gain - 1.0) / math.log2(index + 2.0) for index, gain in enumerate(gains[:k]))


def _ndcg(gains: list[float], k: int) -> float:
    ideal = sorted(gains, reverse=True)
    ideal_dcg = _dcg(ideal, k)
    if ideal_dcg == 0:
        return 0.0
    return round(_dcg(gains, k) / ideal_dcg, 4)


def _mrr(labels: list[str], positive_label: str) -> float:
    for index, label in enumerate(labels, start=1):
        if label == positive_label:
            return round(1.0 / index, 4)
    return 0.0


def _mrr_relevant(labels: list[str]) -> float:
    for index, label in enumerate(labels, start=1):
        if label in LABEL_RELEVANT:
            return round(1.0 / index, 4)
    return 0.0


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def _safe_alias(value: str) -> str:
    return (
        value.lower()
        .replace("/", "_")
        .replace("-", "_")
        .replace(".", "_")
    )


if __name__ == "__main__":
    main()
