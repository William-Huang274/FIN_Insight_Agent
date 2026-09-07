# Model Run: FIN013-S1-DELL-03B-INTERNAL-CHAIN-CEILING-R10

## 摘要

- 目的：在冻结的 R10 open-vocabulary boundary 与 product-price relational transformation compiler 上执行一次 current candidate retrieval，验证 5 个 DELL 请求的真实候选边界。
- 状态：`executed_success / raw_capture_preserved / exact_saved_formal_replay_pass / fresh_independent_dual_audit_pending`。
- 类型：本地 batch inference；不是训练、Provider generation、外源 capture、4B/reranker 或 Evidence promotion。
- 时间：attempt receipt `2026-08-27T08:25:24+00:00`；receipt→raw≈`65s`，raw→private/public≈`40s`，saved replay≈`68s`。
- 环境：Windows local，NVIDIA GeForce RTX 4060 Laptop GPU 8GB；preflight free VRAM=`6,376 MiB`，D盘 free=`1,109,819,392 bytes`。

## Code And Command

- entry point：`scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r10.py`。
- formal：`python scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r10.py --mode formal`。
- replay：`python scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r10.py --mode replay`。
- implementation commit/tree：`70015d11310e760fc7f46a50cf2ed230907ff388` / `b0a26558eba970c5964cee2e057c157d78ef1e9a`。
- authority commit/tree：`d3ab245643e03c6b580c4a0cb9110562b0d86b7a` / `c4cd179229b4c7858610d081274026f09a996fc8`；formal启动时 clean/synced。
- policy：`configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_9.json`，digest=`470631cf…1491`。

## Inputs And Model

- source records=`1,888`；compiled objects=`34,199`；5 requests，每 request精确 `96 union / 16 final`，跨请求去重 `338 / 80`。
- model=`Qwen/Qwen3-Embedding-0.6B`，executor=`qwen3_embedding_0_6b_dense_cuda_fp16`，1024 dimensions/FP16；使用既有 object dense cache，只做一次 fresh query batch。
- leakage guard：candidate only；无 Evidence/NumericFact promotion、外源、current mutation、4B 或 reranker。

## Outputs

- private：`data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/dell-rsq-03b-internal-chain-r10/full_result.json`，digest/SHA=`46517a69…54c2` / `f1473922…e176`。
- raw capture：同 attempt 下 `raw_execution_capture.json`，digest/file SHA=`81fe7d7b…5357` / `a1cb0cba…b4d6`；raw execution SHA=`0e9e4456…7458`。
- receipt：同 attempt 下 `attempt_consumption_receipt.json`，digest/SHA=`8b93aef0…f8a3` / `2c1ef23f…65a9`。
- public：`configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_9.json`，digest/SHA=`d9e2bc2e…4e8c` / `9bef5725…9313`。
- terminal failure：absent。

## Results

- material-set complete requests=`5/5`；local embedding batches=`1`；network/provider/generation/external/4B/reranker/retry=`0`。
- complete target counts：supplier=`3/3/2/1 rank2`；ASP、capacity release、yield/utilization、HBM→Dell、Dell units均=`0/0/0/0`。
- transformation=`1,609 total / 1,358 accepted / 251 failed`；6/6 complete coverage，failed complete、unbound complete、compiled-complete-without-source均为0。
- residual 03C external targets=`5`；当前池 4B/reranker challenger eligibility=`0/0`。
- exact replay：`private_dict_and_bytes_equal=true`，private digest=`46517a69…54c2`。
- post-result direct regression：`66 passed in 18.10s`；Project OS=`82 passed in 28.65s`；secret scan=`8,199/0`；T4 trigger=false。

## Experiment Governance

- hypothesis：R10 可在不改变冻结 retrieval ranking 的前提下关闭 R9 两个 P2，并把 generic-hardware ASP false complete正确降为 partial。
- observed：raw execution SHA与R9一致，supplier稳定；ASP由R9 `1/1/1/1` 降至R10 `0/0/0/0`，与零调用 preview完全一致，无其他未解释 target delta。
- decision label：`proceed_to_fixed_manifest_and_fresh_readonly_dual_audit`；不是 `03B independent pass`。
- stop condition：任何 identity/request/rank/counter/schema/raw-first/replay不一致均停止；同 attempt 不重试。所有 stop condition均未触发。

## Caveats And Next Step

- 未补五条外源，未运行changed-pool 4B/reranker，未做 admission、S2或新报告。
- R17仍为reader URL=0、claim-passage=0/18、WWC=0/6、human=0/16的 `FAIL_GATE_OPEN_NOT_ASSESSABLE`。
- 下一步只允许冻结result、建立fixed manifest并交给fresh author-separated read-only reviewer同时审R10工程与R17研报质量。
