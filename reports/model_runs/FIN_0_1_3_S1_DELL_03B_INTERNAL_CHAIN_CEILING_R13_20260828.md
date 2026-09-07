# Model Run: FIN013-S1-DELL-03B-INTERNAL-CHAIN-CEILING-R13

## 摘要

- 目的：以immutable R12 raw successor做一次零新增调用的R13 semantic/reconciliation successor，验证persisted-population whole-summary、event-local unknown-head barrier、participial/relative governing price head与public projection合同。
- 状态：`executed_success / immutable_R12_raw_reuse_capture_preserved / exact_saved_formal_replay_pass / fresh_independent_dual_audit_pending`。
- 类型：确定性零模型编译；不是训练、推理、Provider generation、外源capture、0.6B/4B embedding、reranker或Evidence promotion。
- 时间：attempt receipt=`2026-08-27T23:01:35+00:00`；formal与saved replay各约30秒。

## Code And Authority

- entry point：`scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r13.py`。
- formal：`python scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r13.py --mode formal`。
- replay：`python scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r13.py --mode replay`。
- implementation commit/tree=`11caf389fdea3c96554dd4176c571c1bf12e14be` / `382f02cae8c0b6545bdfa7d08a00c3e79c5700c9`。
- authority commit/tree=`492218a9237678f2d2cf63b6a77f1249dc9f1f55` / `54e598569bf9d3aec1a5104f6c6669ea26669f60`；formal启动时clean/synced，唯一parent为implementation，唯一changed path为v2.2 policy。
- policy digest/SHA=`cc84d3a…a61427` / `ae519358…b0cb`；绑定15 inputs、41 implementation files与零模型task-specific `TokenBudgetBasis`。

## Inputs And Execution Profile

- immutable R12 raw execution SHA=`0e9e4456ba75ecd07bc2e3bd6d5deddafc1972ba19700b029b2e6793e99f7458`；5 requests、`338 unique union / 80 final`。
- corpus=`1,888 source / 34,199 compiled objects`；target-union occurrence=`794`。
- R13 changed stage只包括post-candidate semantic compiler、persisted reconciliation和public projection；query payload、inventory、vector、union和raw ranks均未变。
- R13新增local embedding/model/provider/generation/network/external/4B/reranker/retry/mutation/promotion/closure全部为0；没有token生成、截断或fallback。

## Outputs

- receipt digest/SHA=`19d10cb1…b346` / `536a06f9…b3ab`。
- raw successor digest/file SHA=`45bc59c6…34a6` / `5c9cece6…74d8`；精确绑定R12 raw capture。
- private digest/SHA=`0d58e3ea…a055` / `9502e498…e94c`。
- public digest/SHA=`d186be68…be8d` / `b841be68…d63`。
- terminal failure=absent；exact replay=`private_dict_and_bytes_equal=true`；public projector rebuild dict exact=true。

## Results

- complete target counts：supplier=`3/3/2/1 rank2`；ASP、capacity release、yield/utilization、HBM→Dell、Dell units均=`0/0/0/0`。
- transformation=`1,596 total / 1,273 accepted / 323 failed`；6/6 persisted-summary reconciliation exact；6/6 complete coverage；failed-complete、unbound-complete、compiled-complete-without-source、proof-rebind均为0；unbound partial=`379`。
- five external-required targets保留exact active IDs，ASP为2个frozen 03A-R2 route IDs；supplier未误开external。
- current frozen pool 4B/reranker challenger eligibility=`0/0`；这不取消后续changed-pool mixed shadow设计。
- post-result direct regression=`162 passed in 56.52s`；T4 trigger=false。

## Experiment Governance

- hypothesis：在candidate generation完全不变时，R13可以只重编译语义与持久化reconciliation，关闭R12的一项P1、两项P2，并保持complete family/count/rank、route和nonroute disposition。
- observed：raw dict/SHA与R12相同；六target的persisted summary 6/6独立重算相等；完整结果与preview预期一致；public可由private精确重建；exact replay字节相同。
- decision label：`proceed_to_reviewed_result_freeze_case_correct_manifest_and_fresh_readonly_dual_audit`；不是`03B independent pass`。
- stop condition：任何Git/input/raw/rank/counter/summary/projection/replay漂移均应停止；正式门均未触发。same attempt不得重试。

## Caveats And Next Step

- 五条外源、changed-pool 0.6B/4B、conditional reranker、admission、S2、S3与新报告均未执行。
- R17仍为reader URL=0、claim-passage=0/18、WWC=0/6、human=0/16的`FAIL_GATE_OPEN_NOT_ASSESSABLE`。
- 下一步只允许冻结reviewed result、建立case-correct fixed manifest，并交给全新author-separated read-only reviewer同时审R13工程与R17研报质量。
