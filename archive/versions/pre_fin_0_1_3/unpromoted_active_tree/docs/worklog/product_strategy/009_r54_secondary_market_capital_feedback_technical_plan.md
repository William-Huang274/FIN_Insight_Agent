# R54 Secondary Market / Capital Feedback Technical Plan

日期：2026-06-28

## Prompt

用户确认可以继续 R54，并指出 R54 应该做成长期维护文档，因为后续数据源会根据测试表现增加或删减，图谱和 source authority 也会变化。

## Decision

R54 不做成一次性“二级市场数据补充方案”，而定义为长期维护的 `Secondary Market / Capital Feedback` 技术计划和 source registry 草案。

核心判断：

- R54 的价值不是多接行情源，而是把二级市场、资金面、信用融资、资本动作、估值 price-in、预期叙事、事件、政策、跨资产和衍生品信号变成可审计、可边界化、可被 Research Lead / Workpaper / R53 消费的研究维度。
- R54 必须显式维护 source lifecycle：`planned`、`candidate_verified`、`parser_ready`、`runtime_ready`、`parser_debt`、`public_boundary`、`commercial_gap`、`deprecated`。
- 13F、N-PORT、COT、short interest、options、futures 等信号都有滞后、授权、覆盖或推理边界；不能冒充实时资金流或基本面事实。

## Work Completed

- 新增 `docs/architecture/agent_graph_vnext/29_r54_secondary_market_capital_feedback_technical_plan.zh-CN.md`。
- 更新 `docs/architecture/agent_graph_vnext/README.zh-CN.md`，加入 29 文档索引。
- 更新 `docs/worklog/00_internal_master_checklist.md`，记录 R54 draft 状态但保持未完成。

## Result And Evidence

R54 草稿已覆盖：

- R54 定位和长期维护原则；
- `SecondaryMarketSourceRegistry` 最小字段；
- 11 个 pack：`SecondaryMarketCapitalFlowPack`、`OwnershipAndHolderPack`、`CreditFundingPack`、`CorporateActionPack`、`LiquidityAndPositioningPack`、`ValuationPriceInPack`、`ExpectationNarrativePack`、`EventCatalystPack`、`PolicyRegulatoryPack`、`CrossAssetReadThroughPack`、`DerivativesMarketSignalPack`；
- `CapitalFeedbackSignal` schema 和 `SecondaryMarketCapitalFeedbackPack` container；
- authority boundary 和 forbidden claims；
- Capital / Market graph edges；
- Research Lead、Market/Capital Specialist、Memo/Workpaper、R53 的消费方式；
- R54.0-R54.7 实施顺序；
- 第一版 source family 台账和 eval gates。

## Verification

- 本轮是 docs-only，未运行 runtime、parser、DB、agent graph、frontend、R53 回测或 full-chain eval。
- 后续需要在 R54.1 之后运行真实 source inventory / coverage profile / parser tests。

## Follow-up

1. 拆 R54.0-R54.7 的需求单和通过门控。
2. 先做 R54.1 current asset inventory，确认当前已有 market / ownership / debt / capital rows 能覆盖哪些 pack。
3. 设计 `SecondaryMarketSourceRegistry` 和 `SecondaryMarketCapitalFeedbackCoverageProfile` 的落地 schema。
4. 决定 v0.1 是否先做 Valuation + SEC capital action + 13F/short，再进入 derivatives。
