# Model Run: 20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_r2

## Summary
- Purpose: Build the latest Tier1+Tier2 603-company SEC evidence semantic Milvus Lite collection on cloud GPU after efficiency audit and batch tuning.
- Status: accepted cloud build; direct Windows directory copy rejected; local use should go through the accepted parquet rebuild artifact.
- Run type: embedding/index build.
- Timestamp: 2026-06-14 Asia/Shanghai.
- Environment: cloud AutoDL/SeeTa container, NVIDIA GeForce RTX 4090 D 24GB, `/root/autodl-tmp` data volume.

## Code And Command
- Entry point: `scripts/eval_retrieval/build_milvus_semantic_collection.py`
- Git state at launch: local branch `codex/layered-data-source-expansion`, source changes dirty and synced to cloud for the run.
- Remote script: `/root/autodl-tmp/fin_agent_sp500_stage/run_20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_r2.sh`
- Command profile:
  - `--embedding-model /root/autodl-tmp/modelscope_cache/BAAI/bge-m3`
  - `--device cuda`
  - `--fp16`
  - `--defer-index-build`
  - `--embedding-batch-size 1024`
  - `--insert-batch-size 8192`
  - `--progress-interval 8192`
  - `--vector-text-max-chars 1800`
  - `--embedding-max-seq-length 512`
  - `OMP_NUM_THREADS=8`
  - `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`

## Inputs
- Evidence JSONL: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/data/staging/tier1_tier2_full_source_v0_1/merged/tier1_tier2_sec_full_source_mixed_evidence_fy2023_2027_v0_1.jsonl`
- Input profile from preflight:
  - evidence rows: `231,842`
  - expected typed vectors: `662,908`
  - unique tickers: `581`
  - forms: `10-K 176,304`, `10-Q 32,146`, `8-K 7,641`, `20-F 13,316`, `40-F 2,435`
  - source tiers: `primary_sec_filing 224,201`, `company_authored_unaudited_sec_filing 7,641`
- Candidate boundary: audited SEC evidence rows only; object vectors disabled for this semantic evidence collection build.
- Leakage guard: no LLM call, no target labels, no commercial/private tracker evidence.

## Outputs
- Remote Milvus output root: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/data/indexes/staging/milvus/20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_r2`
- stdout log: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/data/logs/20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_r2.stdout.log`
- stderr/progress log: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/data/logs/20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_r2.stderr.log`
- Final summary expected after completion: `milvus_streaming_build_summary.json`.

## Results
- Pre-run tuning:
  - batch512 r1 reached about `191.8 vectors/sec`, but used only about `9.3GB` GPU memory.
  - batch1024 10k-row smoke passed: `10,000` evidence rows -> `29,697` vectors, `161,211 ms`, peak CUDA allocated `12,652 MB`, peak CUDA reserved `20,660 MB`.
  - batch1536 4k-row smoke failed with CUDA OOM after first batch, so it is not used for the full build.
- First r2 stable observation:
  - vectors encoded: `24,607`
  - vectors inserted: `24,576`
  - evidence rows seen: `8,193`
  - elapsed: `129.666 sec`
  - throughput: `189.772 vectors/sec`
  - sampled GPU utilization: `100%`
  - sampled GPU memory: about `17.5GB`
- Final cloud build:
  - evidence rows seen: `231,842`
  - vectors built / encoded / inserted: `662,908`
  - unique tickers: `581`
  - vector kinds: narrative `231,842`, paraphrase `217,709`, relationship `106,350`, table `107,007`
  - forms: `10-K 176,304`, `10-Q 32,146`, `8-K 7,641`, `20-F 13,316`, `40-F 2,435`
  - elapsed: `3,390,310 ms`
  - deferred FLAT index build: `5,322 ms`
  - peak CUDA allocated: `12,652 MB`
  - peak CUDA reserved: `17,044 MB`
- Cloud search smoke:
  - collection stats: `row_count=662,908`
  - `msft_capex`, `nvda_datacenter`, `jpm_credit`, and `ai_infra_unfiltered` each returned `5` hits.
  - Representative top hits included MSFT AI/cloud infrastructure risk and PP&E table, NVDA data center revenue, JPM provision/charge-off rows, and SMCI/NVDA AI infrastructure relationship rows.
- Local transfer finding:
  - Directly copying the Linux Milvus Lite directory to Windows is not a valid promoted artifact. Local Milvus Lite opened the copied directory as `row_count=0` and removed data parquet shards.
  - Accepted local path is the separate parquet rebuild run `20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_local_rebuild_from_parquet_r1`.

## Experiment Governance
- Hypothesis: streaming evidence expansion plus fp16, deferred index build, and the highest stable embedding batch should reduce wall time without changing the semantic vector contract.
- Decision target: complete full 603 evidence semantic collection with all `662,908` expected typed vectors, pass Milvus manifest/summary parity, and support retrieval smoke before local pull.
- Ceiling / upper bound: batch1536 exceeds 4090D memory under the current max-seq/vector-text contract; batch1024 is the highest verified stable profile.
- Baselines to beat: old batch64 non-stream full build and batch512 streaming r1 candidate.
- Stop conditions: OOM, missing final summary, inserted vector count mismatch, collection load/search failure, or semantic contract drift against expected vector-kind counts.
- Efficiency gate: sustained throughput materially above old `~70 vectors/sec` and no full pre-materialization stall.
- Decision label: proceed.
- Mainline decision: r2 is the current Milvus 603 semantic build candidate; do not promote until completion and smoke retrieval pass.

## Runtime Efficiency
- Wall time: `3,390,310 ms`.
- Stage timing: streaming encode/insert completed; deferred index build took `5,322 ms`.
- CPU/RAM: streaming path avoids the old full vector-row pre-materialization stall.
- GPU utilization / memory: batch1024 uses peak reserved memory around `20.66GB` in smoke; batch1536 OOMs.
- Throughput: smoke throughput about `184 vectors/sec` including startup and index build; full-build progress stabilized around `195-196 vectors/sec`.
- Bottleneck diagnosis: remaining bottleneck is likely BGE-M3 encode at max sequence length plus synchronous Milvus Lite insert stages; higher batch is memory-bound.
- Efficiency improvement: streaming builder, fp16 CUDA, batch `1024`, insert batch `8192`, deferred FLAT index, peak CUDA memory reporting.
- Serving latency implication: this is offline index build only; online retrieval latency must be tested after collection load/search and local CUDA smoke.

## Caveats And Next Step
- Not promoted for local direct use: copied Linux Milvus Lite directory on Windows.
- Known risks: cloud Milvus Lite directories should be treated as Linux-runtime artifacts; for Windows local use, rebuild from parquet export.
- Reproduce: use the remote script path above; no credentials are stored in this ledger.
- Next decision: use the local parquet rebuild artifact for local retrieval wiring and keep the cloud build as the source-of-truth embedding/index build record.
