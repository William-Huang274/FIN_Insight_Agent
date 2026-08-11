# Model Run: 20260809 Three-case S1 Internal Ranking BGE-M3 / Sparse / Fusion R2

## Summary

- Purpose: 在 Owner 接受的 18 行 DELL／MU／NVDA research qrels 上，对同一候选边界比较 sparse RRF、BGE-M3 bilingual dense RRF 与 facet-aware fusion。
- Status: `terminal_succeeded_local_ranking_evaluation / sparse retained / fusion rejected`。
- Run type: local embedding and read-only retrieval evaluation；不是 LLM 推理，也不是 Evidence 或产品验收。
- Date: 2026-08-09。
- Execution code baseline: clean commit `207e23fb1df62798ba6d6388b2b5a2f786f16071`。

## Inputs And Controls

- Qrels: `configs/releases/fin_ia_0_1_3_s1_internal_qrels_review_packet_v1_3.json`，Owner decision digest=`6549686220698cf50a44afe2255769a964582f6098bf06a87452b3b98755c48c`，18/18 accepted，0 row modification。
- Policy: `configs/runtime/fin_ia_0_1_3_s1_internal_bge_fusion_evaluation_policy_v1_1.json`。
- Runner: `scripts/releases/run_fin_ia_0_1_3_s1_internal_bge_fusion_evaluation_attempt_r2.py`。
- Model: local `BAAI/bge-m3` successor locator，1024 dimensions；Milvus Lite collection contains 662,908 legacy vectors。
- Candidate generation completes before qrels load. Entity, reporting period, filing calendar, relationship and case filters remain deterministic and fail closed.
- Network/provider/LLM/document/rerank/Evidence calls=`0/0/0/0/0/0`；embedding=`36 vectors`，Milvus vector search=`36`。

## R1 Invalidation

R1 completed local model and Milvus execution, but its candidate canonicalizer split vector identity at the first `::`. That collapsed distinct namespaced financial evidence blocks before fusion. The immutable R1 output is therefore invalid for adoption or model-quality interpretation. Post-run audit found 18 collision records; audit digest=`72b104df8e1bfebd887536b9baeb06565a44574fec6d72a05888267cfb05b8be`。

R2 changes only identity canonicalization: it strips a final declared vector-kind suffix (`narrative_chunk`／`table_chunk`／`paraphrase_context`／`relationship_context`) and never treats a namespace prefix as evidence identity. Qrels, queries, filters, budgets and fusion weights were unchanged.

## Valid R2 Metrics

| Route | Recall@1 | Recall@5 | Recall@10 | Recall@24 | MRR@10 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Sparse RRF | 0.22222222 | 0.88888889 | 0.88888889 | 1.00000000 | 0.51111111 | 0.60703187 |
| BGE dense bilingual RRF | 0.16666667 | 0.16666667 | 0.16666667 | 0.22222222 | 0.16666667 | 0.16666667 |
| Facet-aware fusion | 0.11111111 | 0.50000000 | 0.77777778 | 0.94444444 | 0.28201058 | 0.39781676 |

All three routes have zero top-10 wrong-owner, wrong-period or cross-case promotions. Fusion nevertheless fails both adoption gates: Recall@10 is below sparse and MRR@10 is more than 0.02 below sparse. Decision=`retain_sparse_baseline_and_open_dense_or_fusion_repair`；fusion is not adopted.

## Runtime And Efficiency

- Device: CUDA, NVIDIA GeForce RTX 4060 Laptop GPU, driver 555.97, 8,188 MiB reported memory。
- PyTorch: `2.10.0+cu126`；sentence-transformers: `5.2.3`。
- Model load=`26,768.627 ms`；36-vector embedding=`1,636.639 ms`；36 Milvus searches=`60,394.569 ms`；wall=`95,120.441 ms`。
- Result digest=`980954131ee198eab6051ed420b58a0daa7475505fa8acc48cc5c1d2811b37ba`。

## Post-run Dense Index Diagnostic

A separate read-only metadata diagnostic queried the 10 unique selected target identities, without embedding or vector search. Only 5/10 unique targets physically exist in the legacy Milvus collection. Row-weighted classification across 18 qrels is:

- `8` dense-index freshness gaps；
- `3` targets retrieved in top 10；
- `1` present target retrieved at rank 16；
- `6` present targets missing from top 24。

Diagnostic digest=`092b86a288255e2c65ea42f4981cebf7036955e549bc676e2de541059706ee34`。This proves two distinct causes: the dense index has not ingested current supplemental documents, and the existing semantic query/ranking path also misses several indexed targets. It is not valid to label the whole outcome “BGE model quality failure.”

## Decision And Boundary

- Production candidate baseline remains sparse RRF.
- Build an immutable supplemental dense successor from capture-backed current documents and federate it with the historical collection; do not overwrite 662,908 legacy vectors.
- Require selected-target physical presence=`10/10 unique` before one new same-matrix dense/fusion comparison.
- Do not tune fusion weights against these qrels to manufacture a pass.
- Reranker is absent and was not evaluated; it requires separate resource, license and execution admission.
- Current-quarter exact SQL remains `0/6`; external official required-slot coverage remains `4/12` and is an independent release blocker.
- No result in this run is Evidence, downstream utilization, report quality, Workbench acceptance or release qualification.
