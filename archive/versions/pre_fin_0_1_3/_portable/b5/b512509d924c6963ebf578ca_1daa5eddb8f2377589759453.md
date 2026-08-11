# 425｜FIN 0.1 S4-T05 Research Lead gap-atom 确定性投影最小零调用实现

日期：2026-07-27
状态：`implementation_fixture_proven / fresh_agent_proof_pending`

## 1. 权限与范围

用户以“继续”授权执行 RC-P36-061 已冻结的最小 runtime implementation。

本轮只允许：

- `remaining_gap_atoms` Provider 合同；
- 全候选本地校验；
- 确定性 Top-4 投影；
- typed L2 overflow finding；
- fake Provider 正负矩阵、完整链回归、Project OS 与交接记录。

本轮没有模型、Provider、网络、Source、Tool 调用，没有签发或消费 admission，没有创建 WorkUnit、Attempt、ResearchRun 或业务 Artifact，没有重跑 DELL、paired assessment、Human Review、S4-T06 或 release/production 动作。

## 2. Runtime 结果

新增 Research Lead transport：

`fin01.s3.bounded_agent.research_lead_owner_grade:v6`

共享 policy：

`fin01.s3.research_lead_gap_atom_deterministic_projection:v1`

Provider 只输出：

- `statement`
- `claim_ids`
- `what_would_change_task_ids`

Provider 不输出 gap ID、rank、score 或 canonical position。候选没有独立语义数量上限，仍受既有 raw-wire UTF-8 bytes 与 node output-token hard envelope。

runtime 必须先验证全部候选的 exact shape、text、alias membership/kind、authority、identity、semantic 与 hard capacity。任一 overflow 候选非法时整条响应 fail-closed，不得静默丢弃。

全部候选通过后按冻结 tuple 排序：

1. non-empty WWC task；
2. linked Claim 最大不确定性；
3. distinct program Cell count；
4. distinct Claim count；
5. canonical atom digest；
6. Provider ordinal。

随后本地选择最多 4 项、生成 gap IDs、扩展 typed scoped refs，并向 Writer/Verifier 暴露既有 canonical `remaining_gaps`。

## 3. L2 finding

当有效候选超过 4 项时，新增：

`research_lead_gap_atom_overflow_deterministically_projected`

layer=`L2_recoverable_protocol`，terminal=false。

finding 只持久化 candidate/selected/overflow counts、policy ref、selected ordinals 与 digests，不持久化 statement 或 ref 原文，并同时进入：

- `bounded_agent_manifest.recoverable_protocol_findings`
- `bounded_agent_judgment.recoverable_protocol_findings`

这保留 Provider nonconformance 事实，但不把可安全恢复的 overflow terminalize。

## 4. 历史兼容与硬边界

- v1–v5 transport request、validator 与失败行为不改；
- v5 的 5 项 `remaining_gaps` 继续 hard cardinality failure；
- 1–4 个有效 v6 candidates 正常通过且无 overflow finding；
- 8 个有效 candidates 确定性输出 4 项；
- 非法第 8 项在投影前硬失败；
- unknown/wrong-kind/out-of-surface ref、invalid JSON、truncation、真实容量耗尽继续 hard/unrecoverable；
- 历史 R4 `failed/failed/failed`、Artifact=0、capture 与 Run 不改写、不重新分类。

## 5. 验证

- focused gap-atom contract、projection、negative matrix 与 full fake Provider：
  - `9 passed`
- 完整 S4-T05：
  - `141 passed`
- 完整 S4：
  - `178 passed`
- Python compile：
  - `pass`
- 下一 fresh-proof scope Project OS preflight：
  - `pass`
  - `open_full_chain_blocker_count=0`
- fake Provider：
  - `12 callbacks`
  - `9 logical Artifacts`
  - canonical gap count=`4`
  - manifest/JudgmentSet L2 finding parity=`true`

机器 implementation record：

`configs/releases/fin_ia_0_1_s4_t05_research_lead_gap_atom_deterministic_projection_minimum_zero_call_implementation_v1_0.json`

## 6. 后传

以下不扩入当前单任务序列：

- dependency/conflict/variant 与 all-node atom framework；
- cross-provider strict server-schema capability matrix；
- cross-stage gap identity 与 semantic deduplication。

前两项后传 S4-T10→S5，第三项后传 S5 或更晚。

## 7. 下一项

`S4-T05-DELL-RESEARCH-LEAD-GAP-ATOM-DETERMINISTIC-PROJECTION-FRESH-AGENT-PROOF-DECISION`

该项需独立零调用授权，只能重新计算当前 code/policy/transport、fresh identity 与 prospective admission；不得签发或消费 admission、执行第五次 DELL exact-live、paired assessment 或 S4-T06。
