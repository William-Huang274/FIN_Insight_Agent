# 2026-08-13 S3 proposal／execution 预算分层与 S1-C 交接

## 为什么要做

DELL Planner R1 返回 10 条结构和业务语义均合法的 atoms，但旧合同把模型提案上限与实际 EvidenceRequest 执行预算都写成 8，导致整轮在进入 S1/S2 前失败。R1 永久保持 failed，本轮不重试、不调用模型，也不手工改写它的输出。

## 实现

- 当前 planning policy 升级为 v1.1：模型最多提出 12 条 atoms，objective 中历史字段 `max_evidence_requests=8` 明确只表示执行预算。
- 本地 selector 先为每个 required slot 选出一个高优先级 atom，再按 provider-neutral facet priority 填充剩余预算。
- 所有提案都先经过身份、scope、metric、family、来源和 intent budget 校验；即使最终会 deferred，非法 atom 仍然硬失败。
- `CompiledResearchPlan` 同时保存 `proposed_atoms`、实际执行的 `planner_atoms`、`deferred_atoms`、稳定理由和 selection policy digest。
- Workbench 受控计划投影显示 proposed／selected／deferred 数量；只有 selected atoms 会编译成 EvidenceRequest。

## 保存的 R1 回放

- proposed=`10`，selected=`8`，deferred=`2`；5/5 required slot 保留。
- 执行：`orders_and_backlog`、`conversion_and_durability`、`reported_results`、`margin_and_incremental_profit`、`cash_generation`、`working_capital_risk`、`issuer_counterevidence`、`upstream_or_demand_counterevidence`。
- 延后：`guidance_and_outlook`、`pricing_and_mix`；理由均为 required-slot 和 provider-neutral priority 选择后执行预算耗尽。
- 打乱 atoms 输入顺序后 plan digest、选择和舍弃理由不变。
- proposal 超过 12、deferred atom 中含非法 metric、重复、跨案或 scope expansion 继续 fail closed。

## 当前真实 Runtime successor

- 8/8 narrative lane 非空；Qwen＋BM25 共返回 128 个候选位置。
- S2 共接收 25 个 typed fact request：18 resolved、7 typed gap、0 conflict、44 NumericFact。
- 7 个 gap 均为公司事实 mart 尚无 `backlog / orders / customer_count / shipments`；它们保留为 S2 typed gap，叙事 Evidence lane 可继续取公司披露，但系统不伪造精确数字。
- 网络调用 0、生成模型调用 0。

## 验证

- 全量 Python：`151 passed`。
- active baseline：97 Python／7 frontend／9 Runtime resources，0 failure／0 forbidden reference。
- Python compileall 和 `git diff --check` 通过。

## 结论与下一步

`RC-S3-001` 已由共享合同分层关闭，但这不是 S3 产品通过。保存的 R1 10 条自然 atoms 现在成为 S1-C 产品输入；下一项先做 v2 qrel successor、结构化 QueryFacetPlan 约束消费、候选排序与 Evidence Role／abstain。只有这些完成后，真实 residual gap 才进入 S1-D；随后才回到 S3 消费合格 Evidence Pack 与 NumericFact。
