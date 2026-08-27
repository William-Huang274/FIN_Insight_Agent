# Model Run: FIN013-S1-DELL-03B-INTERNAL-CHAIN-CEILING-R11

## 摘要

- 目的：在冻结的 R11 ClauseOwnershipDecision v2、PriceAttachmentProof v1 与 proof-aware transformation compiler 上执行一次 current candidate retrieval，验证5个DELL请求的真实候选边界。
- 状态：`executed_success / raw_capture_preserved / exact_saved_formal_replay_pass / fresh_independent_dual_audit_pending`。
- 类型：本地 batch inference；不是训练、Provider generation、外源capture、4B/reranker或Evidence promotion。
- 时间：attempt receipt `2026-08-27T13:14:53+00:00`；receipt→raw≈`194s`，raw→private/public≈`99s`，saved replay≈`90s`。
- 环境：Windows local，NVIDIA GeForce RTX 4060 Laptop GPU 8GB；D盘formal preflight free=`999,346,176 bytes`。

## Code And Command

- entry point：`scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r11.py`。
- formal：`python scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r11.py --mode formal`。
- replay：`python scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r11.py --mode replay`。
- implementation commit/tree：`23014238f8a0cb03968daefe23de7de71c48e2e9` / `a909ff19ee11e911f2e6094a52e90f9e92e26089`。
- authority commit/tree：`9522cceea210c026b77289cf9b0bc4fd23fd6226` / `f269b808b25dbb25aaba5d1d3681a68ecfeba965`；formal启动时clean/synced，唯一parent为implementation，唯一changed path为v2.0 policy。
- policy：`configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v2_0.json`，digest/SHA=`38461e69…90ba` / `f32688cc…23cd`。

## Inputs And Model

- source records=`1,888`；compiled objects=`34,199`；5 requests，每request精确`96 union / 16 final`，跨请求去重`338 / 80`，target-union occurrence=`794`。
- model=`Qwen/Qwen3-Embedding-0.6B`，executor=`qwen3_embedding_0_6b_dense_cuda_fp16`；使用既有object dense cache，只做一次fresh query batch。
- deterministic admission：ClauseOwnershipDecision v2、affirmative PriceAttachmentProof v1、proof-aware semantic/provenance transformation；embedding只排序，不决定owner、relation或Evidence。
- leakage guard：candidate only；无Evidence/NumericFact promotion、外源、current mutation、4B或reranker。

## Outputs

- private：`data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/dell-rsq-03b-internal-chain-r11/full_result.json`，digest/SHA=`b99ebb9c…f2e0` / `a4e20e99…901b`。
- raw capture：同attempt下`raw_execution_capture.json`，digest/file SHA=`1bfa05ca…c6a7` / `0436afb1…6d8e`；raw execution SHA=`0e9e4456…7458`。
- receipt：同attempt下`attempt_consumption_receipt.json`，digest/SHA=`902b7800…dddf` / `6b87e3cf…5c21`。
- public：`configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v2_0.json`，digest/SHA=`1002829c…3578` / `75edb850…1786`。
- terminal failure：absent。

## Results

- material-set complete requests=`5/5`；local embedding batches=`1`；network/provider/generation/external/4B/reranker/retry=`0`。
- complete target counts：supplier=`3/3/2/1 rank2`；ASP、capacity release、yield/utilization、HBM→Dell、Dell units均=`0/0/0/0`。
- transformation=`1,614 total / 1,284 accepted / 330 failed`；6/6 complete coverage，failed complete、unbound complete、compiled-complete-without-source均为0；unbound partial=`385`。
- partial source/compiled：ASP=`844/951`、capacity=`388/353`、yield=`5/8`、HBM=`17/19`、supplier=`80/73`、units=`332/295`。
- residual 03C external targets=`5`；当前池4B/reranker challenger eligibility=`0/0`。
- exact replay：`private_dict_and_bytes_equal=true`，private digest=`b99ebb9c…f2e0`。
- post-result direct regression：`93 passed in 21.21s`；T4 trigger=false。

## Experiment Governance

- hypothesis：R11可在不改变冻结retrieval ranking或任何complete family的前提下关闭R10两个P2，以可证明的clause ownership和price attachment替代prefix/co-presence启发式，并在source→compiled中保留proof。
- observed：raw execution SHA与R10一致，complete family/count/rank/downstream disposition全部稳定；proof schema只重分类partial diagnostics，和zero-call preview一致。作者期首次preview曾因把`non_clause_continuation`误当business semantic导致supplier coverage false；同阶段修正为representation-only后，6/6 complete coverage恢复，且未放宽material ownership或price proof。
- decision label：`proceed_to_reviewed_result_freeze_fixed_manifest_and_fresh_readonly_dual_audit`；不是`03B independent pass`。
- stop condition：任何identity/request/rank/counter/schema/raw-first/replay、complete family/rank/downstream或proof transformation不一致均停止；同attempt不重试。正式门均未触发停止条件。

## Caveats And Next Step

- 未补五条外源，未运行changed-pool 4B/reranker，未做admission、S2或新报告。
- R17仍为reader URL=0、claim-passage=0/18、WWC=0/6、human=0/16的`FAIL_GATE_OPEN_NOT_ASSESSABLE`。
- 下一步只允许冻结result、建立fixed manifest并交给fresh author-separated read-only reviewer同时审R11工程与R17研报质量。
