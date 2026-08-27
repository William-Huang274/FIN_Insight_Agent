# Model Run: FIN013-S1-DELL-03B-INTERNAL-CHAIN-CEILING-R12

## 摘要

- 目的：以 immutable R11 raw candidates 做一次零新增调用的 R12 route/semantic/provenance successor，验证恒常 route identity、结构化 clause ownership、governing price head、connector proof与持久化/public projection合同。
- 状态：`executed_success / immutable_R11_raw_reuse_capture_preserved / exact_saved_formal_replay_pass / fresh_independent_dual_audit_pending`。
- 类型：确定性零模型编译；不是训练、推理、Provider generation、外源capture、0.6B/4B embedding、reranker或Evidence promotion。
- 时间：attempt receipt=`2026-08-27T19:43:42+00:00`；receipt/raw→private/public约27秒；saved replay约30秒。

## Code And Authority

- entry point：`scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r12.py`。
- formal：`python scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r12.py --mode formal`。
- replay：`python scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r12.py --mode replay`。
- implementation commit/tree=`e86d4a1d7a52911b25d31034d202ae29e6dfd314` / `3f160e82d955d249d2696e96c8b8478c9d13cf27`。
- authority commit/tree=`e1aeefa3431dcf3e46cadc0f67472cee89f22422` / `fb8433baab63eddba04912e77b3320f130f7a510`；formal启动时 clean/synced，唯一 parent为implementation，唯一changed path为v2.1 policy。
- policy digest/SHA=`4dfae14f69bfa2c2e62bdec64239456f0813931d5b947254c7dedde9c2d79440` / `5ed3b60ef0154a9a835175b75396b7496e7e18daaba80f0ef39a9a380c075656`；绑定15 inputs、37 implementation files与零模型 task-specific `TokenBudgetBasis`。

## Inputs And Execution Profile

- immutable R11 raw execution SHA=`0e9e4456ba75ecd07bc2e3bd6d5deddafc1972ba19700b029b2e6793e99f7458`；5 requests、`338 unique union / 80 final`。
- corpus=`1,888 source / 34,199 compiled objects`；target-union occurrence=`794`。
- R12 changed stage只包括 post-candidate route projection、semantic compiler和source→compiled provenance；query payload、inventory、vector、union和raw ranks均未变。
- R12新增 local embedding/model/provider/generation/network/external/4B/reranker/retry/mutation/promotion/closure全部为0；没有 token生成或截断。

## Outputs

- receipt digest/SHA=`d1c738a1…f81a` / `5e0bfa6b…f186`。
- raw successor digest/file SHA=`eb4c50e8…57e5` / `7b8410d8…bd3`；精确绑定R11 raw capture。
- private digest/SHA=`5b478654…c1cd` / `489c87dc…c56`。
- public digest/SHA=`7302201a…7fdc` / `25e873a7…a3bb`。
- terminal failure=absent；exact replay=`private_dict_and_bytes_equal=true`。

## Results

- complete target counts：supplier=`3/3/2/1 rank2`；ASP、capacity release、yield/utilization、HBM→Dell、Dell units均=`0/0/0/0`。
- transformation=`1,601 total / 1,277 accepted / 324 failed`；6/6 complete coverage；failed-complete、unbound-complete、compiled-complete-without-source、proof-rebind均为0；unbound partial=`380`。
- five external-required targets保留 exact active IDs，ASP恢复2个 frozen 03A-R2 route IDs；supplier未误开external。
- current pool 4B/reranker challenger eligibility=`0/0`；这不取消后续 changed-pool mixed shadow设计。
- post-result direct regression=`130 passed in 22.17s`；T4 trigger=false。

## Experiment Governance

- hypothesis：在 candidate generation完全不变时，R12可以只重编译 route identity与语义/provenance合同，关闭 R11 的一项P1、三项P2及冻结前四个完整性边界，同时保持 complete family/count/rank和非route disposition。
- observed：raw SHA与R11相同；完整结果与 preview digest所预期的六target状态一致；ASP exact routes恢复；public→private、policy、raw与implementation lineage闭合；exact replay字节相同。
- decision label：`proceed_to_reviewed_result_freeze_fixed_manifest_and_fresh_readonly_dual_audit`；不是 `03B independent pass`。
- stop condition：任何Git/input/raw/rank/counter/route/proof/public/replay漂移均应停止；正式门均未触发。same attempt不得重试。

## Caveats And Next Step

- 五条外源、changed-pool 0.6B/4B、conditional reranker、admission、S2、S3与新报告均未执行。
- R17仍为reader URL=0、claim-passage=0/18、WWC=0/6、human=0/16的 `FAIL_GATE_OPEN_NOT_ASSESSABLE`。
- 下一步只允许冻结 reviewed result、建立 fixed manifest，并交给全新 author-separated read-only reviewer同时审 R12工程与 R17研报质量。
