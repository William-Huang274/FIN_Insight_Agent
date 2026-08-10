# FIN 0.1.3 six-case retrieval R1

- Attempt: `20260810_s1_six_case_candidate_bundle_exact_object_bm25_bge_m3_fusion_r1`
- Terminal: `terminal_succeeded_six_case_retrieval_business_evaluation`
- Result digest: `dfc2e69a444db1b011d0cf61d02b592f84e7c6da6524accfc3abc6e56bc3914a`
- Population: `93` CandidateBundle objects shared by ObjectBM25 and BGE-M3/Milvus
- Queries: `72` (`18` Owner qrels + `54` canonical Slot diagnostics)
- Calls: BGE load `1`, encode `1/72 vectors`, ObjectBM25 `72`, Milvus `6/72 vectors`, network/provider/LLM/fetch/rerank/Evidence `0`
- Timing: BGE load `3.617s`, embedding `24.835s`, wall `38.818s`

| Route | Recall@10 | MRR@10 | nDCG@10 |
|---|---:|---:|---:|
| ObjectBM25 | 1.0000 | 0.7948 | 0.8321 |
| BGE-M3 | 0.8750 | 0.7902 | 0.7972 |
| 1:1 RRF | 1.0000 | 0.8038 | 0.8356 |

ObjectBM25 remains the primary candidate baseline; BGE-M3 remains a shadow/candidate-expansion route; fusion is not admitted as a global default because its small aggregate gain is not stable by case and it degrades DELL, NVDA and canonical-Slot ordering relative to sparse. Candidate content and Evidence usefulness remain unaccepted.
