from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from eval.retrieval_eval import evaluate_retriever, load_gold_queries  # noqa: E402
from retrieval.bm25_retriever import BM25Retriever  # noqa: E402
from retrieval.dense_retriever import DenseRetriever  # noqa: E402
from retrieval.hybrid_rrf_retriever import HybridRRFRetriever  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate retrieval against gold evidence ids.")
    parser.add_argument("--gold-set", default="eval_sets/sec_tech_10k_seed.jsonl")
    parser.add_argument("--bm25-index-dir", default="data/indexes/bm25/sec_tech_10k")
    parser.add_argument("--dense-index-dir", default="data/indexes/dense/sec_tech_10k")
    parser.add_argument(
        "--retrievers",
        default="bm25,dense,hybrid",
        help="Comma-separated retrievers to evaluate: bm25,dense,hybrid.",
    )
    parser.add_argument("--k-values", default="1,3,5,10")
    parser.add_argument(
        "--filter-mode",
        choices=["ticker_year", "none"],
        default="ticker_year",
        help="Use gold ticker/year filters or evaluate over the full corpus.",
    )
    parser.add_argument("--bm25-candidate-k", type=int, default=30)
    parser.add_argument("--dense-candidate-k", type=int, default=30)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--device")
    parser.add_argument(
        "--output",
        default="reports/retrieval_eval/sec_tech_10k_seed_eval.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    queries = load_gold_queries(REPO_ROOT / args.gold_set)
    k_values = tuple(int(value) for value in args.k_values.split(",") if value.strip())
    if not k_values:
        raise ValueError("--k-values must contain at least one integer")
    retriever_names = [name.strip() for name in args.retrievers.split(",") if name.strip()]

    report = {
        "gold_set": args.gold_set,
        "query_count": len(queries),
        "filter_mode": args.filter_mode,
        "k_values": list(k_values),
        "retrievers": {},
    }

    if "bm25" in retriever_names:
        bm25 = BM25Retriever(REPO_ROOT / args.bm25_index_dir)
        report["retrievers"]["bm25"] = evaluate_retriever(
            queries,
            lambda query, k: bm25.search(
                query.query,
                top_k=k,
                filters=query.filters(args.filter_mode),
            ),
            k_values=k_values,
        )

    if "dense" in retriever_names:
        dense = DenseRetriever(REPO_ROOT / args.dense_index_dir, device=args.device)
        report["retrievers"]["dense"] = evaluate_retriever(
            queries,
            lambda query, k: dense.search(
                query.query,
                top_k=k,
                filters=query.filters(args.filter_mode),
            ),
            k_values=k_values,
        )

    if "hybrid" in retriever_names:
        hybrid = HybridRRFRetriever(
            REPO_ROOT / args.bm25_index_dir,
            REPO_ROOT / args.dense_index_dir,
            rrf_k=args.rrf_k,
            bm25_top_k=args.bm25_candidate_k,
            dense_top_k=args.dense_candidate_k,
            device=args.device,
        )
        report["retrievers"]["hybrid"] = evaluate_retriever(
            queries,
            lambda query, k: hybrid.search(
                query.query,
                top_k=k,
                filters=query.filters(args.filter_mode),
            ),
            k_values=k_values,
        )

    compact = {
        name: result["summary"] | {"misses_at_max_k": result["misses_at_max_k"]}
        for name, result in report["retrievers"].items()
    }
    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(compact, indent=2, ensure_ascii=False))
    print(json.dumps({"output": str(output_path), "max_k": max(k_values)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
