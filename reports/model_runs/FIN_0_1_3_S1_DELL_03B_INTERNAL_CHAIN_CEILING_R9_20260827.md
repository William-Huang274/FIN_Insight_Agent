# Model Run: FIN013-S1-DELL-03B-INTERNAL-CHAIN-CEILING-R9

## 摘要

- 目的：在冻结的 R9 typed frame/scope/argument/transformation compiler 上执行一次 current candidate retrieval，确认 5 个 DELL 请求的真实候选边界与 source→compiled provenance。
- 状态：`executed_success / raw_capture_preserved / exact_saved_formal_replay_pass / fresh_independent_dual_audit_pending`。
- 类型：本地 batch inference；不是训练、Provider generation、外源 capture 或 Evidence promotion。
- 时间：attempt receipt `2026-08-27T04:37:07+00:00`；本地执行约 `160s`，saved-formal replay 约 `60s`。
- 环境：Windows local，NVIDIA GeForce RTX 4060 Laptop GPU 8GB；preflight free VRAM=`6,615 MiB`，D 盘 free=`1,245,532,160 bytes`。

## Code And Command

- entry point：`scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r9.py`。
- formal：`python scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r9.py --mode formal`。
- replay：`python scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r9.py --mode replay`。
- implementation commit/tree：`3b608ca63631f7c6783443eeb55cae85d111c6b1` / `8d2c65f1288e9b6d6068f38527a57e40c025d7c3`。
- authority commit/tree：`2c6d7ba526157533770c40ebdbc2f9392c00cc48` / `bda33fb2536cab12ac883c0dd47e8eb0fbc986df`；formal 启动时 clean/synced。
- policy：`configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_8.json`。
- seed：无训练随机种子；frozen current runtime、canonical ordering、exact 5×96→16 contract。

## Inputs

- source records：`1,888`；compiled objects：`34,199`。
- request count：`5`；每 request 候选边界为 `96 union / 16 final`，总去重 union=`338`、final=`80`。
- runtime binding：`configs/runtime/fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_15.json`。
- frozen predecessor：R8 policy/public/private/raw receipt；R8 fresh failure与 R17 固定 14-file report-quality bundle 全部 hash-bound。
- leakage guard：candidate only，`candidate_not_evidence`；无 label/result access，无 Evidence/NumericFact promotion，无外源或 current mutation。

## Model Parameters

- model：`Qwen/Qwen3-Embedding-0.6B`，executor=`qwen3_embedding_0_6b_dense_cuda_fp16`。
- embedding：`1024` dimensions，`float16`；existing compiled-object dense cache + one fresh query-embedding batch。
- runtime：Python `3.10.11`，PyTorch `2.10.0+cu126`，Transformers `5.2.0`，Sentence Transformers `5.2.3`，CUDA `12.6`。
- generation/loss/optimizer/epochs：不适用；0 generation model calls。
- non-default contract：5 requests、1 local batch、BM25+dense union、owner/source quota、material reservation、96→16 exact rank permutation。

## Outputs

- private：`data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/dell-rsq-03b-internal-chain-r9/full_result.json`（digest/SHA=`7531b494…61533` / `8a774e43…d8c52`）。
- raw capture：同 attempt 下 `raw_execution_capture.json`（digest/file SHA=`cad1ad51…b3657` / `2105aced…b6e3`）。
- receipt：同 attempt 下 `attempt_consumption_receipt.json`（digest/SHA=`a38f4c38…243b` / `2b60e988…fb0b`）。
- public：`configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_8.json`（digest/SHA=`b60fd484…32ae` / `8be3ea0d…07a4`）。
- terminal failure：absent。

## Results

- material-set complete requests=`5/5`；local embedding batches=`1`；network/provider/generation/external/4B/reranker/retry=`0`。
- complete target counts：ASP=`1/1/1/1 rank2`；supplier=`3/3/2/1 rank2`；capacity release、observed yield/utilization、HBM→Dell、Dell units 均=`0/0/0/0`。
- complete source→compiled transformation coverage=`6/6`；local source/object repair=`0`。
- residual 03C external targets=`4`；当前池 4B embedding challenger eligible=`0`，same-pool reranker eligible=`0`。
- exact replay：`private_dict_and_bytes_equal=true`，private digest=`7531b494…61533`。
- post-result direct regression：`56 passed in 7.66s`。
- post-result Project OS preflight：`82 passed in 30.40s`；8 JSONL / 1,324 rows parse pass。
- repository secret scan：`8,183 files / 0 findings`；diff check pass。
- active baseline：`213 Python / 8 frontend / 5 detectors / 28 resources / 0 forbidden`。

## Experiment Governance

- hypothesis：R9 typed frame/scope/argument/provenance repair 能在不改变冻结 retrieval counts 的前提下关闭 R8 工程 finding，并对 current corpus 给出完整 transformation receipt。
- decision target：5/5 request contract、全部 frozen attacks/positives、6/6 complete transformation coverage、0 unexplained count/rank delta、0 forbidden authority counters。
- ceiling：四个 target 在 source/object/pool 全为 0，因此本轮不能证明 source closure；reranker不能提高 target-not-in-pool 的 recall。
- baseline：R8 同一 raw execution，ASP 与 supplier rank2，四 residual 0；R9 preview digest=`c515f44d…2bb7b`。
- stop conditions：任一 request/counter/identity/schema 不完整、raw-before-compile失败、非零 forbidden call、replay不全等即停止；attempt 不重试。
- decision label：`proceed_to_fresh_readonly_audit`；不是 `03B independent pass`，也不允许直接进入 report/product。
- mainline：public result可作为 immutable audit target；fresh audit前不可用于 Evidence/S2/S3 authority。

## Runtime Efficiency

- formal wall time：约 `160s`；receipt→raw capture 约 `99s`，raw→private/public compile 约 `61s`。
- replay wall time：约 `60s`；0 新模型调用。
- GPU：preflight free `6,615 MiB`；未连续采样峰值，不能声称 peak VRAM。
- throughput：5 query embedding in one batch；后续全量 semantic compile 扫描 1,888 sources/34,199 objects。
- bottleneck：模型加载/一次 query batch + Python 全量 frame/transformation compile；不是网络。
- serving relevance：这是离线 bounded qualification，不是在线延迟基准。缓存 compiled embeddings 已存在；正式 product serving 仍需独立 profiling。

## Caveats And Next Step

- 未运行 4B/reranker：当前真实池 eligibility 均为 0；先补四条外源，再在 changed pool 上运行混合方案。
- 未补源、未 admission、未重编 S2、未生成新报告；R17 report quality 仍 `FAIL_GATE_OPEN_NOT_ASSESSABLE`。
- 未重复 full pytest：result 阶段没有 shared/active 代码变化，T4 trigger=false；保留 implementation freeze 的 T1/T2/T3/static证据。
- 下一步：提交 immutable result，建立 audit manifest，交给 fresh author-separated read-only reviewer 同时审 R9 工程与 R17 研报质量。
