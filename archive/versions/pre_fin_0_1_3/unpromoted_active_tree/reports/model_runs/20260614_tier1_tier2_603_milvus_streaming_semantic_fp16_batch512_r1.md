# Model Run: 20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch512_r1

## Summary
- Purpose: Build the latest Tier1+Tier2 603-company SEC evidence semantic Milvus Lite collection on cloud GPU.
- Status: stopped / superseded by `20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_r2`.
- Run type: embedding/index build.
- Timestamp: 2026-06-14 Asia/Shanghai.
- Environment: cloud AutoDL/SeeTa container, NVIDIA GeForce RTX 4090 D 24GB, `/root/autodl-tmp` data volume.

## Code And Command
- Entry point: `scripts/eval_retrieval/build_milvus_semantic_collection.py`
- Git state at launch: local branch `codex/layered-data-source-expansion`, source changes dirty and synced to cloud for the run.
- Remote script: `/root/autodl-tmp/fin_agent_sp500_stage/run_20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch512_r1.sh`
- Command profile:
  - `--embedding-model /root/autodl-tmp/modelscope_cache/BAAI/bge-m3`
  - `--device cuda`
  - `--fp16`
  - `--defer-index-build`
  - `--embedding-batch-size 512`
  - `--insert-batch-size 8192`
  - `--progress-interval 8192`
  - `--vector-text-max-chars 1800`
  - `--embedding-max-seq-length 512`

## Inputs
- Evidence JSONL: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/data/staging/tier1_tier2_full_source_v0_1/merged/tier1_tier2_sec_full_source_mixed_evidence_fy2023_2027_v0_1.jsonl`
- Input profile from preflight:
  - evidence rows: `231,842`
  - unique tickers: `581`
  - forms: `10-K 176,304`, `10-Q 32,146`, `8-K 7,641`, `20-F 13,316`, `40-F 2,435`
  - source tiers: `primary_sec_filing 224,201`, `company_authored_unaudited_sec_filing 7,641`
- Candidate boundary: audited SEC evidence rows only; object vectors disabled for this semantic evidence collection build.
- Leakage guard: no LLM call, no target labels, no commercial/private tracker evidence.

## Outputs
- Remote Milvus output root: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/data/indexes/staging/milvus/20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch512_r1`
- stdout log: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/data/logs/20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch512_r1.stdout.log`
- stderr/progress log: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/data/logs/20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch512_r1.stderr.log`
- Final summary expected after completion: `milvus_streaming_build_summary.json`.

## Results
- First stable observation:
  - vectors encoded: `8,210`
  - vectors inserted: `8,192`
  - evidence rows seen: `2,766`
  - elapsed: `46.452 sec`
  - throughput: `176.741 vectors/sec`
  - GPU memory: about `9.3GB`
  - disk free on `/root/autodl-tmp`: about `30GB`
- Baseline comparison:
  - old full build observed about `180,224 / 662,908` vectors after about `41 min`, roughly `~70 vectors/sec`, with `embedding_batch_size=64`, `insert_batch_size=1024`, and no fp16/deferred index.
  - non-stream optimized path still spent `1m51s` in pre-materialization with GPU idle and RSS about `5.2GB`.
  - streaming smoke improved `512` evidence-row build from `29,077 ms` to `16,851 ms`.

## Experiment Governance
- Hypothesis: streaming evidence expansion plus fp16, larger embedding batch, larger insert batch, and deferred index build should reduce wall time without changing the semantic vector contract.
- Decision target: complete full 603 evidence semantic collection with all `662,908` expected typed vectors, pass Milvus manifest/summary parity, and support retrieval smoke before local pull.
- Ceiling / upper bound: cloud disk and GPU are sufficient; current bottleneck is software pipeline efficiency, not data reachability.
- Baselines to beat: old batch64 non-stream full build and 1k smoke timings.
- Stop conditions: OOM, missing final summary, inserted vector count mismatch, collection load/search failure, or semantic contract drift against the existing vector-kind counts.
- Efficiency gate: sustained throughput materially above old `~70 vectors/sec`; first observed stable throughput is `176.741 vectors/sec`.
- Decision label: proceed.
- Mainline decision: active build is the current Milvus 603 semantic build candidate; do not promote until completion and smoke retrieval pass.

## Runtime Efficiency
- Wall time: running.
- Stage timing: model load completed; streaming encode/insert underway; deferred index build pending.
- CPU/RAM: first non-stream path proved pre-materialization bottleneck; streaming active process RSS observed lower than non-stream pre-materialization.
- GPU utilization / memory: first stable run used about `9.3GB`; utilization sampled variably because insert and encode alternate.
- Throughput: `176.741 vectors/sec` at first stable observation.
- Bottleneck diagnosis: old path was dominated by full vector pre-materialization plus conservative batch/insert settings.
- Efficiency improvement: streaming builder, fp16 CUDA, batch `512`, insert batch `8192`, deferred FLAT index.
- Serving latency implication: this is offline index build only; online retrieval latency must be tested after collection load/search and local CUDA smoke.

## Stop Decision
- r1 was intentionally stopped after a follow-up batch audit showed `embedding_batch_size=1024` is stable and uses cloud GPU memory more fully.
- Latest r1 observation before stop: `57,466` vectors encoded / `57,344` inserted, `19,864` evidence rows seen, about `191.8 vectors/sec`.
- This run is not a promoted artifact and should not be pulled locally.

## Caveats And Next Step
- Not run for r1: final collection parity, retrieval smoke against completed collection, local pull, local CUDA retrieval smoke.
- Known risks: incomplete Milvus directory remains a partial cloud artifact only.
- Reproduce: use the remote script path above if the batch512 profile is needed for debugging; no credentials are stored in this ledger.
- Next decision: use `20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_r2` as the current build candidate.
