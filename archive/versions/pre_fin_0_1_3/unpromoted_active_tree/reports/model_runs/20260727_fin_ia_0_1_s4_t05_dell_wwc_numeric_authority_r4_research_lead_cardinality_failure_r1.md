# Model Run: 20260727 FIN 0.1 S4-T05 DELL R4 Research Lead cardinality failure r1

## Summary

- Purpose: 验证修复后的 `fin01.s3.what_would_change_authority_policy:v1` DELL R4 exact-live，并只在 coherent success 后做 paired assessment。
- Status: terminal failed；admission 已 exact-once 消费；paired assessment 未执行。
- Run type: exact-live inference。
- Environment: Windows local，supervision-v2。

## Exact Identity

- Admission: `fin01-s4-t05-dell-wwc-numeric-authority-fresh-exact-admission-r4`
- Admission digest: `45eef7b1150ee54b3680e69d98b0d8ba3db577dc1b4464649ff561a4e8354b8b`
- WorkUnit: `wu_p02_5_d85b3ee8e94cd729074fc272`
- Attempt: `attempt_fin01_3c963494980cb5a28a467832`
- ResearchRun: `research_run_fin01_9f2cc1412a2fd495db65b8b4`
- Retry/fallback/replay/relaunch/rerun: `0/0/0/0/0`

## Results

- WorkUnit / Attempt / Run: `failed / failed / failed`
- Artifact: `0`
- Orphan: `false`
- Runner exit: `0`
- Calls: model/provider/network=`10/10/10`
- Tokens: input/output/total=`48,397/6,589/54,986`
- Cost: `USD 0.02004878`
- Provider latency sum: `93,011 ms`
- Capture/readback: `10/10`
- Finish reason: 10 个均为 `stop`

三个 Cell 的九个 Specialist segment 全部完成并通过本地校验，Research Lead 也返回完整 `ok/stop` response。Memo Writer 与 Verifier 未到达。

## Repaired Policy Observation

R4 已越过 RC-P36-060 的旧阻塞点：

- 三个 WWC segment 都完成；
- `TaskClaimLinkPolicy` 与共享 `WhatWouldChangeAuthorityPolicy` 保持绑定；
- 没有再次出现 WWC Numeric authority rejection；
- 因此 RC-P36-060 可登记为在新失败前获得 R4 live positive evidence。

这不等于 DELL R2，因为 Research Lead 后续失败且没有业务 Artifact。

## First Credible Failure

Research Lead 的 Provider response 是合法 JSON、`finish_reason=stop`，输出 965/1800 tokens。首个失败为：

`s3_bounded_research_lead_v3_cardinality_above_maximum`

闭合遥测记录：

- field: `remaining_gaps`
- contract: `closed_research_lead_output:v3`
- request-visible cardinality: `1..4`
- local validator cardinality: `1..4`
- excess count: `4`

因此可从闭合合同安全推断 Provider 返回 8 个 `remaining_gaps`，比上限 4 多 4 个。原始文本没有写入 runtime result，本报告也不披露受限 assistant output。

## Root Cause And Governance

- Immediate owner: direct model output contract conformance。
- Request-validator schema drift: false。
- Direct model output contract nonconformance: true。
- New issue: `RC-P36-061-s4-research-lead-remaining-gaps-cardinality-nonconformance`。
- Paired assessment: success-only 条件不成立，未执行。
- DELL R2: 未证明。

本轮不能静默丢弃四项、自动重排、修改合同、切换模型或重跑。下一项零调用 disposition 需要在保留 hard cardinality、确定性组装/排序、按 layered acceptance 重分类和 blocked closeout 之间做显式选择。

## Next

`S4-T05-DELL-WWC-NUMERIC-AUTHORITY-SURFACE-R4-FIRST-CREDIBLE-FAILURE-ROOT-CAUSE-DISPOSITION-DECISION`
