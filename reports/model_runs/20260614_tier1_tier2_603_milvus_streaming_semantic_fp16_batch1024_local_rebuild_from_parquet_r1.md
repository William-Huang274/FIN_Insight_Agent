# Model Run: 20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_local_rebuild_from_parquet_r1

## Summary
- Purpose: Rebuild a Windows-native local Milvus Lite collection from the cloud Milvus parquet row export without re-embedding.
- Status: accepted local artifact.
- Run type: local index rebuild / retrieval smoke.
- Timestamp: 2026-06-14 Asia/Shanghai.
- Environment: local Windows, Z-drive artifact store, RTX 4060 Laptop GPU for query embedding smoke.

## Code And Command
- Entry point: `scripts/eval_retrieval/rebuild_milvus_lite_from_parquet.py`
- Source cloud build: `20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_r2`
- Command profile:
  - `--parquet-dir Z:\FIN_Insight_Agent_artifacts\milvus_exports\20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_r2_linux_parquet\data`
  - `--milvus-deps-path Z:\FIN_Insight_Agent_artifacts\python_deps\milvus_lite`
  - `--milvus-dir Z:\FIN_Insight_Agent_artifacts\milvus`
  - `--insert-batch-size 8192`
  - `--parquet-batch-size 4096`
  - `--progress-interval 65536`

## Inputs
- Parquet export: `11` data shards, `1,376,821,811` bytes.
- Source row contract: Milvus parquet rows with `vector_id`, `embedding[1024]`, evidence metadata, vector kind/role/scope, intent tags, and preview.
- Candidate boundary: SEC evidence semantic vectors from the accepted cloud run only.
- Leakage guard: no LLM call, no re-embedding, no commercial/private tracker evidence.

## Outputs
- Local Milvus DB: `Z:\FIN_Insight_Agent_artifacts\milvus\20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_local_rebuild_from_parquet_r1\milvus_lite.db`
- Local rebuild summary: `eval\sec_cases\outputs\milvus_retrieval_ab\20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_local_rebuild_from_parquet_r1\milvus_parquet_rebuild_summary.json`
- Local search smoke: `eval\sec_cases\outputs\milvus_retrieval_ab\20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_local_rebuild_from_parquet_r1\local_milvus_search_smoke.json`
- Artifact size: `26` files, `4,092,101,560` bytes.

## Results
- Rebuild:
  - rows seen / inserted: `662,908`
  - collection stats: `row_count=662,908`
  - unique tickers: `581`
  - vector kinds: narrative `231,842`, paraphrase `217,709`, relationship `106,350`, table `107,007`
  - elapsed: `734,398 ms`
  - index build: `6,658 ms`
  - sustained insert progress: about `900 rows/sec`
- Local CUDA search smoke:
  - gate: `pass`
  - elapsed: `6,829 ms`
  - collection stats: `row_count=662,908`
  - `msft_capex`, `nvda_datacenter`, `jpm_credit`, and `ai_infra_unfiltered` each returned `5` hits.
  - Representative hits matched cloud smoke: MSFT AI/cloud infrastructure and PP&E, NVDA Data Center / accelerated computing, JPM credit losses, SMCI/NVDA AI infrastructure relationship rows.

## Experiment Governance
- Hypothesis: cloud Milvus parquet shards are a portable row export even when Linux Milvus Lite directories are not safe to open directly on Windows.
- Decision target: local Windows Milvus Lite collection has exact row-count parity and passes representative CUDA query search.
- Ceiling / upper bound: no embedding quality change because embeddings are reused directly from cloud parquet rows.
- Baselines to beat: direct Linux Milvus Lite directory copy opened locally as `row_count=0` and was rejected.
- Stop conditions: row-count mismatch, insert failure, local search failure, or missing metadata fields.
- Efficiency gate: local rebuild must avoid re-embedding all rows and complete within practical local runtime.
- Decision label: proceed.
- Mainline decision: accepted local Milvus artifact for the 603-company SEC semantic collection.

## Runtime Efficiency
- Wall time: `734,398 ms`.
- Stage timing: insert dominated; deferred index build was `6,658 ms`.
- CPU/RAM/GPU: rebuild is CPU/I/O/Milvus Lite insertion; query smoke used local CUDA only for BGE query embeddings.
- Throughput: about `900 rows/sec` during rebuild.
- Bottleneck diagnosis: Windows Milvus Lite insert/manifest flush is the limiting stage; no BGE embedding bottleneck.
- Efficiency improvement: parquet row export avoids local full re-embedding on 8GB GPU.
- Serving latency implication: local vector DB can now be used by retrieval wiring; production serving still needs query-latency and concurrency testing under the backend resource scheduler.

## Caveats And Next Step
- Do not use the direct copied Linux Milvus Lite directory on Windows.
- Keep the parquet export as the cross-platform migration source until a server-side Milvus export/import path replaces it.
- The rebuild script includes a Windows-only Milvus Lite manifest `os.rename -> os.replace` monkeypatch because the local embedded runtime otherwise fails on manifest overwrite.
- Next decision: wire this accepted local DB path into retrieval config and run the planned downstream retrieval/full-chain gates.
