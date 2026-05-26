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

from eval.multifacet_retrieval_eval import (  # noqa: E402
    evaluate_multifacet_retriever,
    load_multifacet_gold_queries,
)
from retrieval.bm25_retriever import BM25Retriever  # noqa: E402
from retrieval.dense_retriever import DenseRetriever  # noqa: E402
from retrieval.facet_aware_retriever import (  # noqa: E402
    facet_aware_round_robin,
    facet_aware_rrf,
)
from retrieval.hybrid_rrf_retriever import HybridRRFRetriever  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate multi-facet retrieval coverage.")
    parser.add_argument("--gold-set", default="eval_sets/sec_tech_10k_complex_multifacet.jsonl")
    parser.add_argument("--bm25-index-dir", default="data/indexes/bm25/sec_tech_10k")
    parser.add_argument("--dense-index-dir", default="data/indexes/dense/sec_tech_10k")
    parser.add_argument(
        "--retrievers",
        default="dense,hybrid,facet_dense,facet_hybrid",
        help=(
            "Comma-separated retrievers to evaluate: "
            "bm25,dense,hybrid,facet_bm25,facet_dense,facet_hybrid,"
            "facet_bm25_rr,facet_dense_rr,facet_hybrid_rr."
        ),
    )
    parser.add_argument("--k-values", default="3,5,10")
    parser.add_argument(
        "--filter-mode",
        choices=["ticker_year", "none"],
        default="ticker_year",
        help="Use gold ticker/year filters or evaluate over the full corpus.",
    )
    parser.add_argument("--bm25-candidate-k", type=int, default=30)
    parser.add_argument("--dense-candidate-k", type=int, default=30)
    parser.add_argument("--facet-candidate-k", type=int, default=20)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--facet-original-weight", type=float, default=0.75)
    parser.add_argument("--facet-query-weight", type=float, default=1.0)
    parser.add_argument(
        "--facet-queries",
        choices=["with_original", "facets_only"],
        default="with_original",
    )
    parser.add_argument(
        "--facet-round-robin-original-first",
        action="store_true",
        help="For round-robin facet fusion, pull from the original query before facet queries.",
    )
    parser.add_argument("--device")
    parser.add_argument(
        "--output",
        default="reports/retrieval_eval/sec_tech_10k_complex_multifacet_eval.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    queries = load_multifacet_gold_queries(REPO_ROOT / args.gold_set)
    k_values = tuple(int(value) for value in args.k_values.split(",") if value.strip())
    if not k_values:
        raise ValueError("--k-values must contain at least one integer")
    retriever_names = [name.strip() for name in args.retrievers.split(",") if name.strip()]

    report = {
        "gold_set": args.gold_set,
        "query_count": len(queries),
        "filter_mode": args.filter_mode,
        "k_values": list(k_values),
        "facet_candidate_k": args.facet_candidate_k,
        "facet_original_weight": args.facet_original_weight,
        "facet_query_weight": args.facet_query_weight,
        "facet_queries": args.facet_queries,
        "retrievers": {},
    }

    bm25 = None
    dense = None
    hybrid = None

    def get_bm25() -> BM25Retriever:
        nonlocal bm25
        if bm25 is None:
            bm25 = BM25Retriever(REPO_ROOT / args.bm25_index_dir)
        return bm25

    def get_dense() -> DenseRetriever:
        nonlocal dense
        if dense is None:
            dense = DenseRetriever(REPO_ROOT / args.dense_index_dir, device=args.device)
        return dense

    def get_hybrid() -> HybridRRFRetriever:
        nonlocal hybrid
        if hybrid is None:
            hybrid = HybridRRFRetriever(
                REPO_ROOT / args.bm25_index_dir,
                REPO_ROOT / args.dense_index_dir,
                rrf_k=args.rrf_k,
                bm25_top_k=args.bm25_candidate_k,
                dense_top_k=args.dense_candidate_k,
                device=args.device,
            )
        return hybrid

    if "bm25" in retriever_names:
        bm25_retriever = get_bm25()
        report["retrievers"]["bm25"] = evaluate_multifacet_retriever(
            queries,
            lambda query, k: bm25_retriever.search(
                query.query,
                top_k=k,
                filters=query.filters(args.filter_mode),
            ),
            k_values=k_values,
        )

    if "dense" in retriever_names:
        dense_retriever = get_dense()
        report["retrievers"]["dense"] = evaluate_multifacet_retriever(
            queries,
            lambda query, k: dense_retriever.search(
                query.query,
                top_k=k,
                filters=query.filters(args.filter_mode),
            ),
            k_values=k_values,
        )

    if "hybrid" in retriever_names:
        hybrid_retriever = get_hybrid()
        report["retrievers"]["hybrid"] = evaluate_multifacet_retriever(
            queries,
            lambda query, k: hybrid_retriever.search(
                query.query,
                top_k=k,
                filters=query.filters(args.filter_mode),
            ),
            k_values=k_values,
        )

    if "facet_bm25" in retriever_names:
        bm25_retriever = get_bm25()
        report["retrievers"]["facet_bm25"] = evaluate_multifacet_retriever(
            queries,
            lambda query, k: _facet_search(
                query,
                lambda text, candidate_k: bm25_retriever.search(
                    text,
                    top_k=candidate_k,
                    filters=query.filters(args.filter_mode),
                ),
                top_k=k,
                args=args,
            ),
            k_values=k_values,
        )

    if "facet_bm25_rr" in retriever_names:
        bm25_retriever = get_bm25()
        report["retrievers"]["facet_bm25_rr"] = evaluate_multifacet_retriever(
            queries,
            lambda query, k: _facet_search(
                query,
                lambda text, candidate_k: bm25_retriever.search(
                    text,
                    top_k=candidate_k,
                    filters=query.filters(args.filter_mode),
                ),
                top_k=k,
                args=args,
                fusion="round_robin",
            ),
            k_values=k_values,
        )

    if "facet_dense" in retriever_names:
        dense_retriever = get_dense()
        report["retrievers"]["facet_dense"] = evaluate_multifacet_retriever(
            queries,
            lambda query, k: _facet_search(
                query,
                lambda text, candidate_k: dense_retriever.search(
                    text,
                    top_k=candidate_k,
                    filters=query.filters(args.filter_mode),
                ),
                top_k=k,
                args=args,
            ),
            k_values=k_values,
        )

    if "facet_dense_rr" in retriever_names:
        dense_retriever = get_dense()
        report["retrievers"]["facet_dense_rr"] = evaluate_multifacet_retriever(
            queries,
            lambda query, k: _facet_search(
                query,
                lambda text, candidate_k: dense_retriever.search(
                    text,
                    top_k=candidate_k,
                    filters=query.filters(args.filter_mode),
                ),
                top_k=k,
                args=args,
                fusion="round_robin",
            ),
            k_values=k_values,
        )

    if "facet_hybrid" in retriever_names:
        hybrid_retriever = get_hybrid()
        report["retrievers"]["facet_hybrid"] = evaluate_multifacet_retriever(
            queries,
            lambda query, k: _facet_search(
                query,
                lambda text, candidate_k: hybrid_retriever.search(
                    text,
                    top_k=candidate_k,
                    filters=query.filters(args.filter_mode),
                ),
                top_k=k,
                args=args,
            ),
            k_values=k_values,
        )

    if "facet_hybrid_rr" in retriever_names:
        hybrid_retriever = get_hybrid()
        report["retrievers"]["facet_hybrid_rr"] = evaluate_multifacet_retriever(
            queries,
            lambda query, k: _facet_search(
                query,
                lambda text, candidate_k: hybrid_retriever.search(
                    text,
                    top_k=candidate_k,
                    filters=query.filters(args.filter_mode),
                ),
                top_k=k,
                args=args,
                fusion="round_robin",
            ),
            k_values=k_values,
        )

    compact = {
        name: result["summary"]
        | {
            "misses_at_max_k": result["misses_at_max_k"],
            "facet_misses_at_max_k": result["facet_misses_at_max_k"],
        }
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


def _facet_search(
    query,
    search_fn,
    *,
    top_k: int,
    args: argparse.Namespace,
    fusion: str = "rrf",
) -> list[dict]:
    query_texts = query.decomposition_queries(include_original=args.facet_queries == "with_original")
    first_query_is_original = args.facet_queries == "with_original"
    if fusion == "round_robin":
        return facet_aware_round_robin(
            query_texts,
            search_fn,
            top_k=top_k,
            candidate_k=args.facet_candidate_k,
            first_query_is_original=first_query_is_original,
            original_first=args.facet_round_robin_original_first,
        )
    if fusion != "rrf":
        raise ValueError(f"Unsupported facet fusion strategy: {fusion}")
    return facet_aware_rrf(
        query_texts,
        search_fn,
        top_k=top_k,
        candidate_k=args.facet_candidate_k,
        rrf_k=args.rrf_k,
        original_query_weight=args.facet_original_weight,
        facet_query_weight=args.facet_query_weight,
        first_query_is_original=first_query_is_original,
    )


if __name__ == "__main__":
    main()
