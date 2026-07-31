# FIN 0.1 S4-T06：审计证据 v2 与 material-numeric classifier 零调用实现

日期：2026-07-30<br>
状态：运行时注入与三案例 fixture 证明完成；fresh-agent proof 待独立决策；no R5

## 本轮目标

按 483 冻结的结构性方案，完成唯一零调用实现包：

- 原子保留模型实际可见请求、assistant 最终输出和 allowlisted 非敏感推理参数；
- 让 telemetry 只保存安全索引，并绑定 capture ref、digest、字段路径和语义类别；
- 把报告期或请求内标识符与金额、百分比、计量值等 material numeric surface 分开；
- 失败输出可审计，但不能自动重放或晋升为业务 Artifact。

## 实现结果

新增 versioned runtime contracts：

- `fin01.runtime.provider_interaction_audit_capture:v2`
- `fin01.s4.case_numeric_authority_projection_and_deterministic_rendering:v2`

v2 capture 保存 exact system/user request、assistant final output、allowlisted inference arguments、Provider/model/route、内容 digest 与安全 validator match index。它显式拒绝凭据、Authorization、Bearer、Cookie、密码和高置信 secret surface；不保存 raw Provider envelope 或私有推理。

v2 classifier 将本案绑定报告期和 request-local identifier 归为 non-authoritative/nonterminal；金额、百分比、计量值、未知报告期和其他未分类数字保持 L1 terminal。v1 合同和历史 R4 事实均未改写。

## 确定性证明

- 新增定向测试：`15 passed`；
- DELL、MU、NVDA 正向 full fake 各达到 `6 nodes / 12 callbacks / 12 captures / 9 Artifacts`；
- 三案 material numeric 负向 fixture 均在第一份 capture 后原子终止；
- R4 两个路径 `$.fact_layer[0].statement`、`$.explanation_layer[0]` 均识别为 `reporting_period_label`，不再误判为 material numeric；
- v1 历史 blanket numeric 行为保持；
- credential-bearing request 在写入 terminal capture 前被拒绝；
- failed capture 可按内容寻址回放，业务 Artifact 数为 0；
- 完整 S4-T06 contract regression：`223 passed / 1771 deselected`。
- Project OS broad full-chain preflight 按预期 fail-closed，保留 RC-P36-067、068、080、081 四个 open blocker；fresh proof scope 仍可执行。

## 运行与边界

- model/provider/network/source/tool calls：0；
- admission、WorkUnit、Attempt、ResearchRun、业务 Artifact：0；
- paired assessment、owner acceptance、T07、R5：0；
- 唯一零调用实现包：`1/1` 已消费；
- MU R4 继续保持 immutable failed / 0 Artifact。

这轮证明的是当前运行时和确定性 fixture，不是 fresh-agent proof、DeepSeek live 行为、最终九 Artifact L1、paired quality 或 owner acceptance。

## 下一步

`S4-T06-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-CLASSIFIER-FRESH-AGENT-PROOF-DECISION`

下一步只允许零调用独立证明决策；不得自动签发 R5 admission 或执行 paid exact-live。
