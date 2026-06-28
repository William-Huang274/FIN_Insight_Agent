# 423 R49 Secondary Market Capital Feedback Layer Into 25

日期：2026-06-28

## Prompt

用户要求先把刚刚讨论的二级市场资金面、预期面、信用融资、资本动作、期权/期货、宏观政策和跨资产反馈层合并进 25 文档，后续再考虑是否拆分或融合成可执行顺序；当前先作为草稿。

## Reasoning And Decision

当前项目的基本面、产品、行业证据层已经较强，但如果目标是二级市场投研，仅回答“公司值不值钱”不够，还需要回答：

- 市场是否已经 price in；
- 资金是否拥挤；
- 信用/融资成本是否比股票更早反映风险；
- 股价和融资窗口是否反过来改变公司资本结构、稀释、回购、并购能力；
- 宏观流动性、政策、期权/期货、跨资产信号是否改变估值和风险偏好。

本轮不拆执行计划，只把方向合并到 25 文档，作为后续讨论草案。

## Work Completed

- 更新 `docs/architecture/agent_graph_vnext/25_agent_runtime_reference_stack_and_harness_context_engine_draft.zh-CN.md`：
  - 新增 `Secondary Market / Capital Feedback Layer 草案`。
  - 新增 11 个 pack：
    - `SecondaryMarketCapitalFlowPack`
    - `OwnershipAndHolderPack`
    - `CreditFundingPack`
    - `CorporateActionPack`
    - `LiquidityAndPositioningPack`
    - `ValuationPriceInPack`
    - `ExpectationNarrativePack`
    - `EventCatalystPack`
    - `PolicyRegulatoryPack`
    - `CrossAssetReadThroughPack`
    - `DerivativesMarketSignalPack`
  - 写明当前项目已有基础和缺口。
  - 写明公开源优先方向和不可公开稳定支持的数据边界。
  - 写明二级市场/衍生品 authority boundary 和 forbidden claims。
  - 新增 graph edge 草案。
  - 写明与 `FundamentalStatementPack`、`ProductIntelligenceGraph`、`DimensionEvidencePortfolio`、Research Lead 和 Memo Writer 的关系。
  - 新增初步实施优先级，但保留为讨论草案。

## Current Project Facts Recorded

- 已有 `market_liquidity_driver_context_rows_v0_1`：603/603 price/volume/return/volatility/drawdown。
- 已有 `capital_funding_ownership_context_rows_v0_1`：13,185 rows，包括 capital structure、working capital liquidity、lagged 13F ownership context。
- 已有 `sec_capital_market_event_context_rows_v0_1`：17,485 rows / 588 tickers，包括 offering、Form 3/4/5、proxy、13D/G filing-event metadata。
- 当前缺口集中在 valuation/share/EV、short interest、borrow cost、ETF/N-PORT 权重、Form 3/4/5 XML、13D/G schedules、offering terms、buyback details、OCC/CFTC/CME 衍生品和 futures proxy。

## Result And Evidence

25 文档现在已经把二级市场资金面作为独立草案层纳入 runtime / data / graph 讨论，不再只停留在基本面和产品图谱。该层明确：

- 二级市场和衍生品信号是 market expectation / positioning / price-in / capital feedback，不是基本面 exact fact。
- 公开源支持滞后持仓、filing event、延迟/日频价格、COT、options volume/open interest、公司披露资本动作。
- 实时资金流、dealer gamma、borrow cost、实时 OPRA、实时 ETF creation/redemption、consensus revision 等应保留为 commercial data gap 或低权重 proxy。

## Follow-up

后续讨论可决定：

1. 是否把 `SecondaryMarketCapitalFeedback` 作为 `DimensionEvidencePortfolio` 新维度。
2. 是否先补 SEC capital action source-specific parser，再补 FINRA / 13F / N-PORT / OCC / CFTC / CME。
3. 是否把二级市场相关 eval 加入 11 文档的 full-chain/gold/failure lifecycle。

## Verification

- 本轮未跑模型、pipeline、full-chain 或 runtime tests。
- `git diff --check` 已通过。
