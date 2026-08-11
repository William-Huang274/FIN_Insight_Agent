# 662 — FIN 0.1.3 模型/工具二轨 Agentic Research 重排

日期：2026-08-07
类型：`product strategy / stage ownership / evaluation rebaseline`
状态：`plan_frozen / implementation_not_started`

## 1. 用户要求

用户认可以下判断并要求重新规划 FIN 0.1.3：当前主要瓶颈不只是 DeepSeek 九次调用合同，而是工具可靠性、最新外源、动态研究规划、经济机制综合和最终研究质量评价。比较必须拆成“同 Evidence Pack 的模型分析实验”和“MCP 修复后的端到端 Agentic Search/Research 实验”，避免把产品工具缺口算成模型缺口。

## 2. 本轮复盘证据

- S3 R3 已证明 `9/9` exact-once、9 natural Claim、3 Lead、3 Workpaper、L1/L2，但自然 thesis-support 与 counterevidence 选择均为 0，29 个 planned Cell 未研究；它是 minimum control，不是产品级研报证明。
- DELL、MU、NVDA 三份 Codex Gold candidate 已形成更完整的事实、机制、反方、price-in、WWC 和 typed gap。
- Gold candidate 不是当前产品的独立输出。实际研究使用产品本地数据、部分可用 MCP 和外部官方来源；stdio MCP 的 SEC search/exact-ledger 仍存在资源绑定/超时 RC-P36-140。
- 若直接把 Gold 与 DeepSeek 端到端结果比较，模型、工具和证据可得性的混杂无法归因。

## 3. 关键重排

FIN 0.1.3 保持当前版本，S0–S5 保持责任层，但后续按依赖而非机械编号执行：

1. `013-S2-04`：编译共享 Benchmark Evidence Pack、blind input、hidden Gold scoring objects；
2. `013-S2-05/06` Experiment A：同证据、零检索的 DeepSeek 分析/综合对照，并冻结 raw/correction/corrected 与模型能力边界；
3. `013-S1-06/07/08`：MCP operational truth、当前外部来源 runtime、三案 Agentic Search 质量门；
4. `013-S3-06/07`：动态 Research Lead loop 与 EvidenceRequest/targeted repair 闭环；
5. `013-S3-08/09` Experiment B：三案端到端 DeepSeek Agentic Search/Research 与隐藏 Gold 八维/人工验收；
6. `013-S4-06`：Workbench create→intervene→repair→resume→report→review dogfood；
7. `013-S5-01`：RG1–RG5 最终收口。

已完成的 S0–S3 工程资产不撤销、不重跑；Gold dogfood 新暴露的问题通过有界 successor 回到最早 owner。失败 attempt 不创建 FIN 0.1.4，FIN 0.2 定义不变。

## 4. 公平性与诚实边界

- Experiment A 的 Evidence Pack 必须含 Gold 使用的重要官方事实与 lineage，但不得含 Gold thesis、机制综合、反方结论、WWC 答案或评分。
- 工具问题不归因 DeepSeek；同证据下的分析问题也不能通过工具修复掩盖。
- raw model-only、supervisor correction、corrected candidate 分开保存；扶正结果只证明受监督可恢复。
- 不固定 9 次或 15–25 次调用。每案按 DecisionSurface 和 material gap 预注册最大预算，继续调用必须带来信息增益。
- collect-all 仅可作为预注册的 `quarantined_non_promotable` 诊断，不能成为 formal pass。

## 5. 对产品计划的修改建议

原计划把代表性合同 canary、最小 full-chain 和产品级研究证明放得过近，容易在工程链“跑通”时高估研究能力。后续规划应长期保留三层不同结论：

1. `contract/runtime proof`：能否稳定执行；
2. `same-evidence reasoning proof`：给定可信证据能否形成高质量判断；
3. `end-to-end agentic research proof`：能否自主发现、筛选、修复和综合证据。

三层不能相互替代。这个调整没有改变用户要求的产品方向，反而把 PRD 中 Agentic Search、Research Lead 和研究内容质量重新变成 release-blocking 产品能力。

## 6. 本轮执行边界与下一项

本轮仅更新规划、评测协议、Gold 范围、Project OS 和 worklog：

- 模型调用：0；
- Provider/网络/MCP 调用：0；
- Runtime/业务 Artifact 修改：0；
- 产品实现与测试：未开始。

下一项严格为 `FIN-0.1.3-013-S2-04-SHARED-BENCHMARK-EVIDENCE-PACK-BLIND-INPUT-AND-HIDDEN-GOLD-SCORING-FREEZE`。完成公平性与泄漏检查后，才签发 Experiment A 的 DeepSeek admission。
