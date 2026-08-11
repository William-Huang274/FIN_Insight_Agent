# 095 P33 AI/Semis Research Judgment Ruler

日期：2026-07-06

## 问题

用户指出 P33 后续不能继续只用工程 gate 判断节点是否通过。Codex 必须先作为“懂金融的程序员”写下自己对 AI/Semis case 的深度理解，并把这套理解作为评判 Research Lead、specialist、JudgmentCard、MemoLogicPlan 和 Memo Writer 的尺子。

核心问题不是“是否有输出”，而是节点输出是否真正逼近一个金融研究员应形成的分析链条。

## 决策

新增 P33 AI/Semis research judgment ruler，并把它接入 P33 source-of-truth：

- `docs/internal/vnext_20260610/p33_ai_semis_research_judgment_ruler.zh-CN.md`
- `docs/internal/vnext_20260610/p33_p32_closeout_to_ai_semis_gold_workpaper_program.zh-CN.md`
- `docs/project_os/current_context_pack.zh-CN.md`
- `docs/project_os/p33_execution_plan_ledger.jsonl`

该尺子明确：

- AI/Semis gold case 的核心不是泛泛判断 AI 需求，而是判断 AI 基建需求是否真实转化为 accelerator、server OEM、foundry/packaging、HBM、semicap 的高质量收入和利润。
- 合格 workpaper 必须组织出 `AI capex -> product capability / supply -> customer deployment -> OEM financial quality -> semicap read-through -> market price-in -> counter-thesis` 的链条。
- Product / Architecture、Customer Deployment、Supply Chain、Financial Quality、Market Expectation、Risk / Counter-thesis 六类 lane 均有强证据、中等证据、proxy、不能外推和失败条件。
- Research Lead、Evidence Fusion、Coverage Reflection、Specialist、Aggregate / JudgmentState、MemoLogicPlan / Memo Writer 均有节点级研究质量失败条件。

## 完成内容

1. 新增 AI/Semis 研究质量尺子文档。
2. P33 主计划的 Source of Truth 增加该文档。
3. P33 主计划新增 `8.22 AI/Semis Research Judgment Ruler`，并将下一步从“可直接 paid Memo Writer”改为必须先做 no-paid `ResearchJudgmentRulerAudit`。
4. P33 阶段状态表同步改为 `research_judgment_ruler_documented_pending_no_paid_audit`。
5. Project OS context pack 增加当前事实和禁止事项，防止后续上下文压缩后误跑 paid writer。
6. P33 machine ledger 新增 `P33-3_research_judgment_ruler` 行。

## 验证

本轮未运行 paid LLM、Memo Writer、full-chain 或模型对比。

本轮性质是 source-of-truth / governance alignment。下一步需要实现并运行 no-paid `ResearchJudgmentRulerAudit`，用该尺子审计 accepted aggregate r7 和 Memo Writer payload。

## 下一步

唯一推荐动作：

1. 实现 no-paid `ResearchJudgmentRulerAudit` runner。
2. 审计 accepted aggregate r7：
   - 哪些 gold questions 已被 JudgmentCards 支撑；
   - 哪些只有 proxy；
   - 哪些是 source/parser/runtime 缺口；
   - 哪些是 public/commercial boundary。
3. 审计 Memo Writer payload：
   - 是否真正收到判断材料；
   - 是否仍有 evidence dump；
   - prompt 约 56k chars 中哪些是低价值上下文。
4. 只有 audit 为 `pass_or_bounded_pass`，才允许单节点 paid Memo Writer rerun。

禁止动作：

- 不直接 paid Memo Writer。
- 不 broad full-chain。
- 不做模型对比。
- 不扩 20-50 case。
