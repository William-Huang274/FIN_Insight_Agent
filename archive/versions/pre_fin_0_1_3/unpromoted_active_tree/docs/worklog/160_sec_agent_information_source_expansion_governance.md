# SEC Agent Information Source Expansion Governance

Date: 2026-05-25

## 背景

当前 `SEC_PRIMARY_MIXED_RECENT` 链路已经能在 10-K + latest 10-Q mixed 模式下跑通真实 DeepSeek 全链路，并且能把财年、10-Q QTD/YTD、SEC 证据边界、runtime Exact-Value Ledger 和 deterministic gates 保持一致。

下一阶段目标不是简单“多抓数据”，而是面向投研分析场景扩展信息源，同时保持当前链路的证据约束能力。每引入一个新信息源之前，必须先完成接入规划，再进入实现、下载、解析、索引、测试和真实链路验证。

## 阶段原则

- 新来源必须先写接入规划，规划通过后再做代码和数据引入。
- 新来源必须带 source tier、审计/未审计属性、`as_of_date` 或 filing/report date、provider/domain、采集方式和证据边界。
- SEC 10-K/10-Q Exact-Value Ledger 继续作为精确财务数值主锚；未审计公司材料、市场快照和第三方共识不能和 SEC audited/primary ledger 混权重。
- 任何 fallback 只能作为显式产品行为或临时诊断保护，不能用来掩盖 parser、retrieval、coverage 或 gate 的根因问题。
- DeepSeek 可以做判断和综合，但事实必须来自可追溯 source artifact，不能依赖模型记忆。
- 每次新增来源都必须有小范围 pilot、质量门槛、回滚路径和 worklog 记录。

## 信息源优先级

### P1: SEC 8-K Earnings Release / Exhibit 99.1

目标：

- 补充最新季度 earnings release、管理层解释、guidance、non-GAAP 调整、业务分部叙述。
- 优先选择 SEC EDGAR 中 `8-K` 的 `Item 2.02` 和 `Exhibit 99.1`，保持官方披露来源。

接入判断：

- source tier: `company_authored_unaudited_sec_filing`
- source policy: 从 `SEC_PRIMARY_MIXED_RECENT` 扩展到类似 `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS`
- 精确财务值：默认不进入 audited exact-value ledger；如进入 ledger，必须标记 unaudited / non-GAAP / management view。
- 适合支持：季度解释、guidance、management commentary、业务趋势、非 GAAP 桥接。
- 不适合替代：10-K/10-Q audited or filed table facts。

首批 pilot 建议：

- `MSFT`, `AMZN`, `GOOGL`, `META`, `NVDA`
- 问题类型：latest quarter performance、cloud/AI capex explanation、guidance/watch items、10-Q vs earnings-release consistency。

### P2: Official IR Materials

目标：

- 接入 earnings presentation、shareholder letter、IR press release、prepared remarks，补充 SEC 表格缺少的业务叙事和管理层展望。

接入判断：

- source tier: `company_authored_unaudited_ir`
- 只从公司官网/IR 域名拉取，不先接第三方转载。
- 默认作为 qualitative evidence，不并入 Exact-Value Ledger。
- renderer 必须显示“公司材料 / 未审计 / 管理层口径”。

适合支持：

- 产品进展、订单趋势、客户结构、AI 基建解释、管理层战略表述。

风险：

- 文档格式差异大，PDF/PPT/HTML parser 需要单独验收。
- 管理层叙事可能选择性披露，不能提升为 hard financial fact。

### P3: Market Snapshot

目标：

- 为投研判断补充 `as_of_date` 明确的价格、market cap、EV、returns、估值倍数、指数/行业 benchmark。

接入判断：

- source tier: `market_snapshot`
- 每条记录必须带 `as_of_date`, provider, currency, field definition。
- 不能由 DeepSeek 凭记忆生成市场数据。
- 只支持估值、市场反应、价格表现判断，不支持公司经营事实。

首批字段建议：

- close price, market cap, enterprise value, 1M/3M/6M/YTD return, P/E, EV/Sales, EV/EBITDA when provider supports definitions。

风险：

- provider 差异和授权问题高于 SEC/IR。
- 需要固定快照，不做实时交易级 claim。

### P4: Consensus / Analyst Estimates

目标：

- 支持预期差、forward revenue/EPS/FCF、target price、rating/revision 等投研判断。

接入判断：

- source tier: `third_party_consensus_snapshot`
- 必须带 `as_of_date`, provider, field definition, sample coverage。
- 没有可靠授权/API 前不进入主线。

当前决策：

- 暂缓自动接入；仅在有可靠 provider 或用户手动提供 snapshot 时做 bounded pilot。

### P5: News / Product / Macro / Industry Research

目标：

- 补充监管、产品、客户、行业、宏观和供应链变化。

接入判断：

- source tier 按来源拆分，例如 `regulatory_news`, `company_news`, `macro_snapshot`, `industry_research_excerpt`。
- 暂不作为第一批主线，因为噪声、去重、时效和版权风险更高。

首批可控主题：

- 出口管制、重大客户/客户集中度、AI capex、云需求、监管处罚、并购。

## 每个新信息源的接入规划模板

在实现任何新 source connector / downloader / parser 之前，必须在 worklog 中写下以下内容：

```markdown
## Source Planning: <source_name>

### Purpose
- 投研问题类型：
- 预期补充的证据缺口：
- 不解决的问题：

### Source Contract
- source_tier:
- source_policy:
- audited / unaudited / third-party:
- freshness field:
- required metadata:
- allowed claim types:
- disallowed claim types:

### Acquisition
- source domain / API / SEC path:
- auth requirement:
- rate limit / retry:
- cache path:
- raw artifact path:
- privacy / license notes:

### Parsing And Schema
- parser entry point:
- output schema:
- IDs:
- date/fiscal-period handling:
- numeric value policy:
- qualitative text policy:

### Retrieval And Ledger Use
- BM25 / object-BM25 / vector path:
- whether Exact-Value Ledger may use it:
- source weighting:
- source conflict rule:

### Query Contract / Coverage / Gates
- Query Contract fields:
- Evidence Coverage Matrix changes:
- deterministic gates:
- renderer boundary labels:

### Pilot
- tickers:
- years / periods:
- prompts:
- success criteria:
- failure criteria:
- rollback:
```

## 验收门槛

每个新来源至少需要：

- 1 个 source contract 单元测试。
- 1 个 parser/schema 单元测试或 fixture 测试。
- 1 个 retrieval/coverage 测试，证明该 source 能被检索且 source tier 不混淆。
- 1 个 renderer/gate 测试，证明输出会显示证据边界。
- 1 个小范围真实链路 smoke，优先 3-5 家公司，不直接全量扩展。
- worklog 更新，记录路径、样本数、成功/失败、已知限制和下一步。

## 下一步执行建议

当前建议先做 P1：

- 设计 `8-K earnings release / Ex-99.1` source contract。
- 选 `MSFT`, `AMZN`, `GOOGL`, `META`, `NVDA` 做 pilot。
- 先只解析 text + exhibit metadata + management commentary，不急于把 non-GAAP 数字并入 ledger。
- 跑通后再决定是否把部分明确标注的 unaudited numeric facts 放入单独的 unaudited ledger 或 evidence table。

## 当前状态

- 本文档仅完成新阶段规划和接入治理。
- 尚未引入任何新信息源、下载新数据或修改 pipeline 代码。
- 无 API key、密码或云端凭据写入仓库。
