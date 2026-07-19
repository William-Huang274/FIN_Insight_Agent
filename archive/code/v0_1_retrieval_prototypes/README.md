# v0.1 Retrieval Prototypes

Archived: 2026-07-11.

These files had no current runtime, test, or public-entrypoint references when audited:

- `multifacet_retrieval_eval.py`: early multi-facet evaluator; current eval ownership is under `scripts/eval_retrieval/`, TECH_10, and R60.
- `object_verifier.py`: early structured-object heuristic verifier; current verification uses evidence promotion, numeric gates, claim verifier, and TECH_09.
- `build_dense_index.py`: early local NumPy dense-index builder; current vector path uses maintained BGE/Milvus builders and the index registry.
- `facet_aware_retriever.py`: early standalone facet fusion; current query planning, hybrid recall, fusion, and Evidence Gate live in active runtime modules.

The files are preserved for algorithm and history reference only and are intentionally outside `src`, so setuptools does not package them.
