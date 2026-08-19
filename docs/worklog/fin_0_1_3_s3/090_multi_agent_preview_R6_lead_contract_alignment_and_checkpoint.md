# FIN 0.1.3 S3 — Multi-Agent Preview R6 Lead 合同对齐与 checkpoint

日期：2026-08-20
状态：`R6_failure_immutable / Harness_root_cause_confirmed / captured_Lead_plan_checkpoint_pass / downstream_successor_pending`

## 1. R6 实际发生了什么

R6 没有重新运行六个 Specialist，也没有重新生成 Lead 分析。它复用了 R4＋R5 的完整分析 checkpoint，只执行严格交卷。两次 DeepSeek 请求均 HTTP 完成，并各返回唯一 `submit_lead_plan` Tool Call；但本地都以 `multi_agent_lead_coordination_questions_invalid` 拒绝，所以工作底稿、挑战、Evaluator 和 Writer 尚未开始。

两次提交均有 13 个协调问题、11 条信息边界和 9 条停止条件。它们不是数据、S1、网络、token 或 Provider transport 故障。旧 Tool Schema 的上限是 8／10／8，本地 Validator 却统一使用 10／10／10；失败反馈只返回一个错误码，没有告诉模型哪个字段、实际数量和允许范围。因此第二次 submission 得到的反馈不可行动，仍然返回相同数量。

## 2. 为什么不直接截断到 8／10／8

当前 Preview 拓扑有 13 个研究 facet、7 个 required Evidence Slot、6 类工具权限。逐项审阅显示：13 个问题分别处理口径、订单转收入、AI 归因、事实存在性、上下游说话者、反方路由、指引与已实现、共享事实、供给真假约束、来源缺口、独立需求证据、反证门槛和时间锚；11 条边界、9 条停止条件也各有独立职责。为了通过而截断会丢研究控制面，不符合内容质量优先和任务级 TokenBudgetBasis 规则。

现在由一份 provider-neutral 策略派生容量：

- 协调问题：最多每个 topology facet 一条，当前 13；
- 信息边界：工具权限数＋required slot 数，当前最多 13；
- 停止条件：required slot 数＋跨角色冲突／最终判断两个全案控制，当前最多 9。

同一策略同时驱动 Tool Schema、Validator、Lead 分析输入和 strict submission 输入，消除多套真相。

## 3. 可行动失败反馈

Runtime 现在在本地合同拒绝时生成结构化回执，一次列出全部违规字段、规则、实际值和允许范围；模型收到的不是一个 opaque code。反馈只允许修改结构映射，禁止改变完整分析、增加事实或扩大权限。没有可由 JSON Schema 解释的错误继续保留为本地语义／跨字段错误，不能伪造修复建议。

## 4. R6 原始 capture 回放

旧合同对两次原始 Tool Call 均稳定报告三项：`13>8`、`11>10`、`9>8`。修正后的合同无需改写业务文本即可验证两次 payload。第一次 Tool Call 的停止条件仍写着“eleven coordination questions”，与实际 13 条矛盾；第二次已改成不带错误数量的通用表述，因此只选择第二次建立新 checkpoint。

`R6_lead_plan_checkpoint_v1_0` 绑定 R6 authority／public failure、Attempt 02 请求和响应 capture、六份 Specialist 计划及新容量策略。它是新代码下的零调用 successor artifact；`R6` 的 terminal failure 没有被重写或追认为成功。

负向验证覆盖三字段 max+1、重复协调问题、未知 facet 和 checkpoint digest mutation，全部 fail closed。验证结果为：定向 Preview 测试 24 passed；全仓 857 passed；`compileall` 通过；active baseline 为 184 Python／8 frontend／27 Runtime／0 forbidden；7,396 个文件 secrets scan 为 0 findings；`git diff --check` 通过。一次性 capture 回放 runner 已移入 FIN 0.1.3 版本归档，活动主干只保留通用合同、Runtime 与回归测试。

## 5. 分层归因与下一步

| 平面 | 结论 |
|---|---|
| 数据／S1／S2 | 本轮没有新失败；研究输入未变化 |
| Harness | R6 直接根因；旧容量无任务依据、Schema／Validator 漂移、反馈不可行动 |
| Agent／模型 | 形成了完整且大体有业务意义的计划；未从 opaque code 自行猜出三项数量限制不能单独归责为研究能力失败 |
| Evaluator | 尚未开始，不能评价底稿、跨角色增益或报告内容 |

下一 attempt 只能从新 Lead checkpoint 之后继续，不再调用六个 Specialist 计划、Lead 分析或 Lead submission。它仍是有界 DELL Preview：0 外部来源网络、0 Candidate promotion、0 产品发布；S1、S3、泛化、qualified-human、Workbench 和 release 保持 false。
