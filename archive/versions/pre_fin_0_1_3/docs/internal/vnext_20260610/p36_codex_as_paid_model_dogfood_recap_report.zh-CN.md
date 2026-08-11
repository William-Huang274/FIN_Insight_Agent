# P36 Codex-as-Paid-Model Dogfood 复盘报告

日期：2026-07-09

## 边界

P36 是 Codex 手工扮演 paid model 的 full-chain dogfood。它不是 paid DeepSeek API run，不是 true runtime full-chain，不是 runtime fix，也不是 release eval。

本轮到 Node10 为止，完成了 Research Lead、Retrieval/RAG/SQL、Parser/Evidence Operator、Graph、Fundamental、Product/Industry、Market/Capital、Risk、Aggregate/JudgmentPlanner、Writer/Report Generation 的手工节点记录。

## 最核心结论

FIN_Insight_Agent 不是“没有能力”，而是能力没有被编译成用户题面的决策表面。

底层资产包括：

- RAG / ObjectBM25 / SEC exact-value ledgers。
- market snapshot、ownership / capital rows、P33 capital feedback。
- ProductIntelligenceGraph、Research Graph Store、relationship graph。
- Fundamental、Product/Industry、Market、Risk skills。
- Aggregate/JudgmentPlanner、MemoLogicPlan、writer forbidden-tools gate。

这些资产分散存在，但没有形成：

```text
DecisionSurfaceContract
  -> SourceHunterLoop
  -> parser / evidence promotion
  -> specialist decision-cell packs
  -> DecisionSurfaceAdjudicator
  -> DecisionSurfacePack
  -> MemoLogicPlan
  -> Writer
  -> Verifier / Workbench cell review
```

所以系统能证明“我有治理和边界”，但还不能稳定证明“我能比联网 single-agent 更快产出可读、可审、可复跑的投研判断”。

## Multi-agent 是否有增益

有增益，但增益主要在治理层，还没有完全转成用户可见报告层。

真实增益：

- Research Lead 能在有 decision surface 时形成较好的 thesis path 和 required items。
- Evidence / parser 层能证明基础财务 exact rows 存在，并保留 source boundary。
- ProductIntelligenceGraph 是真实差异化资产，能给 13 个 case tickers 加载产品、KPI、relationship、deployment、gap rows。
- Risk skill 和 Aggregate/JudgmentPlanner 能保留 unsupported / conflict，并阻止 writer 用未支持 claim。
- MemoLogicPlan 的 writer 禁工具边界正确，能防止 writer 自己补源。

未兑现的增益：

- RAG / SQL / graph 没有按 five-chain x decision cells 取数。
- Specialists 接到的是 bounded rows，不是 cell-ready packs。
- Market / capital / ownership / price-in 被拆散，没有进入同一个 price-in surface。
- Aggregate 把 case-specific chain dimensions 折叠回 generic dimensions。
- Writer 收到的不是 report-first matrix，而是通用 memo plan + gaps。

## 哪些节点有效

| 节点 | 有效性 | 说明 |
|---|---|---|
| Research Lead | 有效但需 runtime 化 | 有 P35 surface 注入时能规划；问题是 surface 不是原生 contract。 |
| Retrieval/RAG/SQL | 有资产但缺 supervisor loop | 能召回候选，但不是 decision-cell-driven。 |
| Parser/Evidence Operator | 有基础但需 promotion/sanity | 基础财务 rows 有用，业务线经济性和 numeric sanity 不足。 |
| ProductIntelligenceGraph / Graph | 高潜力 | 资产丰富，但还不是 value-capture graph。 |
| Fundamental Specialist | 节点本身可用 | 缺上游 cell-ready financial pack。 |
| Product/Industry Specialist | 节点方向对 | 缺五链条 selector / pack compacting。 |
| Market/Capital Specialist | 设计不足 | 实际像 market snapshot specialist，不是 price-in analyst。 |
| Risk Specialist | 高潜力 | 缺 RiskMatrixPack 和 risk-specific projection。 |
| Aggregate/JudgmentPlanner | 有真实价值 | 强在 writer safety，弱在 case-specific adjudication。 |
| Writer | 边界正确 | 不该补源；但没有 DecisionSurfacePack 就只能 bounded。 |

## 哪些节点冗余或应重构

不是简单删除某个 specialist，而是要重构职责边界。

1. Retrieval、parser、source route 应合并到 `SourceHunterLoop` 控制下。
   - 现在像多个工具入口。
   - 目标应是按 missing / weak cells 自动取源、抽表、晋升、记录 typed gap。

2. Market 和 Risk 要重新切分。
   - Market snapshot 负责 price action。
   - Capital positioning 负责 ownership / capital structure / crowding。
   - Price-in risk 负责 valuation / event reaction / derivative / short / borrow。
   - Risk specialist 负责把这些投进 counter-thesis，而不是重新看一遍 market rows。

3. Graph 节点要从 relationship recall 改成 value-capture projection。
   - 边必须带 bottleneck rent、pass-through、capex lag、export risk、source grade。
   - 否则图谱只会增加上下文噪声。

4. Aggregate 后必须新增 `DecisionSurfaceAdjudicator`。
   - 现有 aggregate 适合安全治理。
   - 用户需要的是 report-first matrix。
   - 这不应交给 writer 自己推断。

## 为什么 WorkBuddy 看起来更好

WorkBuddy 的优势是它默认以用户可见 artifact 为目标：先拆表，边搜边补，最后产出 HTML / 图表 / decision surface。它不一定更严谨，但更符合前台用户第一眼比较的形态。

FIN 的优势应该是：

- 同样先给 decision surface。
- 每个 cell 有 source grade、lineage、numeric sanity、official / estimate / inference / gap。
- 每个 cell 可 review、accept、reject、补源。
- 复跑时能知道哪个源或 parser 变化导致哪个判断变化。

当前 FIN 只兑现了后半部分的一部分，前半部分不够强，所以用户看到的是边界和治理，而不是清晰判断。

## Runtime repair backlog

优先级应按 writer 前断点排序：

1. `DecisionSurfaceContract`
   - Research Lead 第一输出必须是 five-chain x decision cells。

2. `SourceHunterLoop`
   - 对 missing / weak cells official-first 补源。
   - 补不到写 attempt-backed typed gap。

3. Parser / Evidence promotion
   - 把 official press / IR PDF / presentation table 抽成 value / unit / period / segment / source rows。
   - 加 headline selector、unit sanity、period role、row-label sanity。

4. `ProductIndustryDecisionSurfaceProjection`
   - PIG rows 不能只按 source family 预算。
   - 要按 Accelerator / Server OEM / Foundry-Packaging / HBM / Semicap 平衡。

5. `MarketCapitalDecisionSurfaceProjection`
   - market snapshot、valuation、ownership、capital feedback、derivatives/short/borrow 都要进入 price-in cells。

6. `RiskMatrixPack`
   - 风险不是 gap list。
   - 每个链条要有 falsifier、unsupported claim、what-would-change。

7. `DecisionSurfaceAdjudicator / DecisionSurfacePack`
   - 位置在 aggregate 和 MemoLogicPlan 之间。
   - MemoLogicPlan 应消费 matrix rows，而不是只消费 generic dimensions。

8. Workbench cell-level review
   - 每个 cell 可 accepted / rejected / needs_source / needs_parser / estimate_only / commercial_gap。

## 对下一次 paid/run 的约束

在上述链路至少有 deterministic fixture 前，不应跑 broad full-chain、模型对比或 release eval。

允许的下一步是 no-paid / deterministic：

- decision surface fixture
- source hunter fixture
- official PDF/table parser fixture
- five-chain selector fixture
- market/capital projection fixture
- risk matrix fixture
- DecisionSurfacePack to MemoLogicPlan projection test
- Workbench cell review replay

如果用户要求继续 P36 Node11，Verifier 应验证两个对象：

1. runtime-only writer：应判为 bounded partial，不能通过完整研究报告。
2. supervisor-augmented report：可评价报告质量，但必须确认 supplement rows 没被伪装为 runtime accepted rows。
