# 861 — FIN 0.1.3 S3 动态研究入口审计与 scope 对账

日期：2026-08-11

状态：zero-call entry pass；formal Experiment B 仍被 3 个真实产品问题阻断

## 这次实际解决了什么

S2 关闭后，正式 S3 preflight 显示 7 个 blocker。逐条追到后续运行证据后，发现其中 4 个不是仍在发生的产品问题，而是旧 Attempt 失败后没有同步更新的 Project OS 投影：

- RC-P36-151 的 synthetic-DNS 拒绝，后来已由三案官方源 runtime 和 external recovery live 证明没有复发；
- RC-P36-152 的 Dell IR PDF timeout，后来按原决策走等价 Dell SEC HTML 官方路线并成功；
- RC-P36-154 的 candidate/query runtime missing，后来已实现统一 Query Facet 并进入真实 combined run；
- RC-P36-155 的 partial terminalization，后来已能保留完整 capture、有效查询和 typed partial terminal。

这 4 条采用追加式 `closed` 投影，旧失败没有删除或改写。关闭范围也刻意很窄：PDF 本身未宣称恢复，宽泛网络未宣称可靠，搜索质量未宣称通过。搜索覆盖不足继续由 RC-P36-157 表示，不再让同一个问题同时以“runtime 没实现”和“候选质量不够”两种形式重复阻断。

仍然真实的 3 条是：

1. RC-P36-157：外源搜索尚不能稳定补齐客户、供应、估值等 required slots；
2. RC-P36-165：当前 Evidence Pack 虽已显著改善报告，但仍缺估值及 issuer-specific supply allocation／timing／yield；
3. RC-P36-172：报告的可执行 WWC、经济机制桥、决策密度和去重复仍不达产品门。

所以正式 Experiment B 仍是 blocked；没有为了“进入 S3”把真实问题改绿。

## 为什么需要独立 zero-call scope

RC-P36-172 是 S3 要修的内容质量问题。如果只有正式 Experiment B 一个 scope，就会形成循环：因为内容质量没修好，所以不允许做内容质量修复。新 scope 只允许无外部调用的合同、Runtime、固定 Pack replay、fake／mutation 和质量包物化；它不允许 DeepSeek、网络、补源、业务 Artifact 或验收。

机器结果：

- 新 zero-call scope：`pass / 0 blocker / 0 contract error`；
- 正式 Experiment B：从 `blocked / 7` 收敛为 `blocked / 3`；
- 本轮 provider／model／network／source／retry=`0/0/0/0/0`。

## S3 后续不再怎么做

不再把既有五个组件各自跑绿后就称为研报通过，也不再把调用次数当动态研究。旧组件已经覆盖动态 cell、Claim/WWC、跨 cell、Writer 和八维评分的局部形状，下一步只做 successor 连接：

```text
开放问题
 -> 10–20 个有业务决策角色的 cells
 -> 消费当前 Evidence/Numeric
 -> 识别 material typed gaps
 -> 对可检索 gap 发一个有预算的 EvidenceRequest
 -> 接受／拒绝／保留 gap
 -> 只重裁决受影响 cells
 -> 机制、反方、可观察 WWC
 -> 去重复与决策密度检查
 -> 同输入绝对评分＋paired gain＋qualified-human acceptance
```

数值 WWC 只能来自 NumericFact、FormulaTrace 或批准的 scenario；没有权威阈值时必须说“当前无法数值化”，不能让模型随手发明一个数字。重复、边界说明过多和低决策密度进入质量 finding 与定向修订；事实、数值、引用、身份、Writer 绕源和缺失最强反方继续 hard fail。

## 下一步

实现并零调用证明 planner state、EvidenceRequest repair state、affected-cell re-adjudication、WWC authority 和 deterministic quality packet。通过后再判断是否值得做一个最小自然 planner／repair canary；不直接进入完整 DeepSeek 报告 live。

关键文件：

- `configs/runtime/fin_ia_0_1_3_s3_dynamic_research_planner_evidence_request_and_content_quality_entry_policy_v1_0.json`
- `configs/releases/fin_ia_0_1_3_s3_dynamic_research_entry_audit_and_scope_disposition_v1_0.json`
- `tests/contract/test_fin_0_1_3_s3_dynamic_research_entry_audit.py`
