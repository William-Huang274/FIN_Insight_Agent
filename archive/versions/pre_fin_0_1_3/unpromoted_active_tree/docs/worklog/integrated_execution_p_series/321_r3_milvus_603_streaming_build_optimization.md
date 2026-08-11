# R3 Milvus 603 Streaming Build Optimization

## Prompt
用户打开云端后要求补建最新 603 家公司 Milvus 库，并在发现全量构建过慢后要求先盘点效率问题，再直接重新开始构建；云端资源充足，允许更积极使用显存。

## Efficiency Audit
- 旧全量构建入口：`scripts/eval_retrieval/eval_milvus_retrieval_ab.py`。
- 旧 full build run：`20260614_tier1_tier2_603_milvus_evidence_semantic_fy2023_2027_v0_1`。
- 旧构建输入：`231,842` evidence rows，展开为 `662,908` typed vectors。
- 旧构建观测：约 `41 min` 时只到 `180,224 / 662,908` vectors，GPU utilization `100%` 但显存约 `4.9GB`，batch `64`，insert batch `1024`，progress log 每 `512` vectors 刷一次；停止前最新 tail 为 `201,728 / 662,908`。
- 主要瓶颈：
  - `embedding_batch_size=64` 过保守，4090D 显存没有充分使用。
  - `insert_batch_size=1024` 过小，Milvus insert call 频率偏高。
  - 旧脚本在 full build 前先把 evidence rows 和所有 typed vector rows 全量物化；优化后重启仍在 `1m51s` 时 CPU `~102%`、RSS `~5.2GB`、GPU `0%`，说明预物化本身成为前置瓶颈。
  - 建 collection 时同步声明 FLAT index，可能导致插入期间持续维护 index；全量构建更适合先 insert 后建 index。
  - embedding 转 Milvus payload 时逐元素 `float()` 转换，有不必要 Python 循环。
  - progress log 过密，不影响主瓶颈但会放大长任务 I/O 噪声。

## Changes
- 扩展 `scripts/eval_retrieval/eval_milvus_retrieval_ab.py`：
  - 新增 `--fp16`、`--defer-index-build`、`--progress-interval`。
  - 支持先插入后创建 FLAT index。
  - 去掉 embedding 逐元素 `float()` 转换。
  - 报告中记录 fp16 / defer index / batch / insert batch / progress interval。
- 新增 `scripts/eval_retrieval/build_milvus_semantic_collection.py`：
  - 专用 streaming full-scale builder。
  - 复用原 retrieval A/B vector text contract，不改变 evidence 到 typed vectors 的语义展开。
  - 边读 JSONL、边展开 typed vectors、边 batch encode、边 insert，避免全量预物化。
  - 输出 `milvus_streaming_build_summary.json/md`。

## Smokes
- Non-stream optimized smoke：`20260614_tier1_tier2_603_milvus_optimized_smoke_1k_r0`
  - `512` evidence rows -> `1,500` vectors，`29,077 ms`，fp16/defer index pass。
- Streaming smoke：`20260614_tier1_tier2_603_milvus_streaming_smoke_1k_r0`
  - `512` evidence rows -> `1,527` vectors，`16,851 ms`，fp16/defer index pass。
- Streaming batch512 smoke：`20260614_tier1_tier2_603_milvus_streaming_smoke_batch512_r0`
  - `768` evidence rows -> `2,310` vectors，`20,823 ms`，fp16/defer index pass。
- Streaming batch1024 long smoke：`20260614_tier1_tier2_603_milvus_streaming_smoke_batch1024_10k_r0`
  - `10,000` evidence rows -> `29,697` vectors，`161,211 ms`，peak CUDA allocated `12,652 MB`，peak CUDA reserved `20,660 MB`，pass。
- Streaming batch1536 smoke：`20260614_tier1_tier2_603_milvus_streaming_smoke_batch1536_4k_r0`
  - 第一个 batch 后进入第二个大 batch 时 CUDA OOM；当前 4090D/max-seq 512/vector-text 1800 合同下不作为 full build 参数。

## Build Lineage
- `20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch512_r1` 已停止 / superseded：
  - r1 最新观测：`57,466` vectors encoded，`57,344` inserted，`19,864` evidence rows seen，约 `191.8 vectors/sec`，GPU memory 约 `9.3GB`。
  - 停止原因：batch1024 smoke 证明可以更接近云端显存上限；r1 不作为可拉取或可推广 artifact。

## Active Build
- Active cloud build run id: `20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_r2`
- Remote script: `/root/autodl-tmp/fin_agent_sp500_stage/run_20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_r2.sh`
- Remote logs:
  - stdout: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/data/logs/20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_r2.stdout.log`
  - stderr/progress: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/data/logs/20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_r2.stderr.log`
- Remote output root: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/data/indexes/staging/milvus/20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_r2`
- Parameters:
  - `--embedding-batch-size 1024`
  - `--insert-batch-size 8192`
  - `--fp16`
  - `--defer-index-build`
  - `--progress-interval 8192`
  - `--vector-text-max-chars 1800`
  - `--embedding-max-seq-length 512`
  - `OMP_NUM_THREADS=8`
  - `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
- First r2 stable observation:
  - `24,607` vectors encoded，`24,576` inserted.
  - `8,193` evidence rows seen.
  - elapsed `129.666 sec`，throughput `189.772 vectors/sec`.
  - sampled GPU utilization `100%`，GPU memory about `17.5GB`.
- Final r2 cloud result:
  - `231,842` evidence rows -> `662,908` vectors，`581` tickers.
  - vector kinds：`narrative_chunk 231,842`，`paraphrase_context 217,709`，`relationship_context 106,350`，`table_chunk 107,007`。
  - elapsed `3,390,310 ms`，deferred FLAT index build `5,322 ms`。
  - peak CUDA allocated `12,652 MB`，peak CUDA reserved `17,044 MB`。
  - cloud Milvus search smoke pass：collection `row_count=662,908`；MSFT capex、NVDA datacenter、JPM credit、AI infra unfiltered 四个查询均返回 `5` hits。

## Local Artifact
- Direct Linux Milvus Lite directory copy to Windows was rejected:
  - First local open returned collection `row_count=0` and `0` hits.
  - Local Milvus Lite also removed copied data parquet shards, proving the Linux directory should not be treated as a portable Windows artifact.
  - The corrupted direct-copy directory and failed local rebuild `r0` were removed from `Z:\FIN_Insight_Agent_artifacts\milvus`.
- Accepted local migration path:
  - Pulled cloud data parquet shards to `Z:\FIN_Insight_Agent_artifacts\milvus_exports\20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_r2_linux_parquet\data` (`11` files，`1,376,821,811` bytes).
  - Added `scripts/eval_retrieval/rebuild_milvus_lite_from_parquet.py` to rebuild a Windows-native Milvus Lite collection from parquet rows without re-embedding.
  - Local rebuild run: `20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_local_rebuild_from_parquet_r1`.
  - Local accepted DB: `Z:\FIN_Insight_Agent_artifacts\milvus\20260614_tier1_tier2_603_milvus_streaming_semantic_fp16_batch1024_local_rebuild_from_parquet_r1\milvus_lite.db`.
  - Local rebuild summary: `662,908` rows inserted，collection `row_count=662,908`，elapsed `734,398 ms`，index build `6,658 ms`。
  - Local CUDA search smoke pass：same four representative queries all returned `5` hits.

## Decision
- `proceed`: streaming builder is the current main build path for the 603 Milvus semantic collection.
- `batch1024` 是当前最高稳定 GPU profile；`batch1536` 已被 OOM gate 拦截。
- The old A/B script remains valid for retrieval diagnostics and small builds, but full-scale collection building should use the streaming builder unless a later parity test shows semantic contract drift.
- For Windows local use, do not open copied Linux Milvus Lite directories directly. Use parquet export -> local rebuild until a server-side Milvus import/export path replaces this workflow.

## Follow-Up
- Wire accepted local DB path into retrieval config / runtime resolver.
- Use the local rebuild artifact for downstream retrieval and full-chain gates.
- Keep cloud r2 and parquet export as rebuild lineage; do not promote direct Linux directory copy for Windows local runs.
