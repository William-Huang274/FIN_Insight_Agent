# R51b Research-to-Quant Lab PRD Addendum

日期：2026-06-28

## Prompt

用户确认未来面向有量化交易需求的金融机构，系统可以在内部使用场景下把投研底稿、观点和多源信息总结转化为量化模型因子，并自动执行回测、模拟交易、模型训练/验证/测试。用户强调不做真实资金操盘，不向外部用户提供交易建议；同时要求该部分补充进 B 端 PRD，主 PRD 不能写死 AI 行业，且 quant 节点接入必须增加 human-in-the-loop，让人能选择自动接入还是手动调整。

## Decision

将该能力定义为通用 B 端模块 `Research-to-Quant Lab`，定位为研究到量化验证的过渡层，而不是自动交易系统。

产品边界：

- 支持 thesis driver -> factor hypothesis -> dataset -> backtest -> risk attribution -> paper trading -> factor card。
- 不连接真实资金交易。
- 不面向外部用户输出交易建议。
- 不默认自动接入回测或模拟交易，必须提供 human approval 和 manual / assisted / auto candidate mode。

## Work Completed

- 更新 `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`：
  - 在主流程中加入 `Research-to-Quant Lab`。
  - 在任务类型中加入 `投研观点到量化因子验证`。
  - 在 Workpaper 模板中加入 `Research-to-Quant Workpaper`。
  - 新增 `6.7 Research-to-Quant Lab`，定义 ThesisDriver、FactorHypothesis、FeatureSpec、LabelSpec、UniverseSpec、DatasetBuildPlan、BacktestPlan、BacktestResult、RiskAttribution、PaperTradingRun、FactorCard、PromotionDecision。
  - 增加 manual mode / assisted mode / auto candidate mode 和 human approval 要求。
  - 增加 point-in-time、leakage、survivorship、交易成本、流动性、风险归因、promotion gate 等硬门控。
  - 新增 `8.7 B6：Research-to-Quant Lab` MVP 切片。
  - 新增 `9.6 量化验证验收`。
  - 更新指标、非目标、后续技术文档和开放问题。

## Result And Evidence

- PRD 已明确该模块是通用能力，不写死 AI/Semis 行业。
- PRD 已明确用户可以手动调整，也可以选择 assisted / auto candidate，但 dataset build、backtest、paper trading 进入下一阶段前都需要人工批准。
- PRD 已明确 paper trading 不能连接真实资金账户或真实订单。

## Verification

- `git diff --check` 已通过。
- 本轮未运行 runtime、agent graph、LLM、parser、DB、frontend、backtest 或 full-chain 测试，因为变更范围是产品 PRD。

## Follow-up

后续技术拆分至少包括：

1. Research-to-Quant artifact schema。
2. Point-in-time dataset builder 和 leakage guard。
3. Backtest runner / risk attribution / paper trading monitor。
4. Quant human-in-the-loop approval flow。
5. Factor lifecycle：candidate、validated、paper_trading、monitored、rejected、retired。
