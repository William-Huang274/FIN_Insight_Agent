# 182 A/B 投研任务与产业链范围独立执行计划

Date: 2026-05-29

## 结论

阶段 A/B 应该单独拿出来做成 v0.2-alpha 的第一条主线。原因很简单：A/B 不是“多加几个能力”，而是在定义这个 Agent 到底要像什么样的投研系统工作。后面的 LangGraph、多 Agent、MCP、上下文压缩、外网搜索和 Workbench 产品化，都应该围绕 A/B 形成的投研任务合同、数据合同和评测合同展开。

方向修正：本文件上一版在 B 阶段举例时偏向 AI 产业链。后续主扩容不应围绕 AI 单一行业，而应覆盖主流行业。跨行业公司扩容、下载/处理流程和 20-F/6-K/40-F 等新披露格式接入计划以 `183_cross_industry_data_expansion_and_source_format_plan.md` 为准；AI supply chain 只保留为一个高价值 eval/pilot case。

这一阶段的核心不是马上写更多模型调用，而是先确认三件事：

1. 当前要支持哪些投研问题，至少需要覆盖多少家公司和哪些行业。
2. 这些问题需要哪些数据、文件和证据来源，哪些已经可得，哪些存在结构性缺口。
3. A/B 中的投研标准如何进入模型调用、规则约束和 eval，而不是只停留在文档里。

## 当前数据基线

当前 full78 已经比 v0.1 的 full30 更接近投研覆盖版样本。它覆盖科技、通信服务、可选消费、必需消费、能源、金融、医疗、工业、材料、房地产和公用事业。

当前 full78 公司范围：

```text
MSFT, AAPL, NVDA, GOOGL, META, AMZN, AVGO, CSCO, INTC, AMD,
QCOM, TXN, AMAT, MU, INTU, ADP, ADBE, PANW, CRWD, SNOW,
JPM, V, JNJ, LLY, CAT, GE, WMT, PG, XOM, CVX,
NFLX, DIS, TMUS, TSLA, HD, LOW, MCD, BKNG, COST, KO,
PEP, PM, COP, SLB, EOG, BAC, MS, BLK, SPGI, PGR,
AXP, UNH, MRK, ABBV, TMO, ISRG, HON, RTX, UPS, UNP,
DE, LIN, SHW, FCX, NEM, APD, PLD, AMT, EQIX, WELL,
SPG, NEE, SO, DUK, AEP, CEG, ORCL, CRM
```

本地现有数据产物状态：

| 数据层 | 当前状态 | 说明 |
| --- | --- | --- |
| 10-K manifest | 233 条 | 目标是 78 家 × FY2023-FY2025，理论上最多 234 条；需要确认 1 条缺口是公司披露现实还是下载/manifest 问题 |
| latest 10-Q manifest | 77 条 | full78 中 77/78 有最新 10-Q；LOW 当前记录为 `no_10q_after_latest_selected_10k`，需要 source-gap 审计 |
| mixed 10-K + latest 10-Q | 310 条 | 233 annual + 77 interim |
| 8-K earnings release | 78 条 | full78 均有 2026/2027 earnings-release 8-K evidence |
| mixed with 8-K manifest | 388 条 | 10-K、latest 10-Q、8-K 已进入同一 source policy |
| market evidence pack | 78 条 | 6 个月 bars 重建后，3M return 和相对 QQQ 3M return 对 78/78 可用 |
| BM25 / ObjectBM25 index | 已构建 | `sec_investment_coverage_mixed_with_8k_fy2023_2027` 与 objects index 已存在 |

判断：

- 阶段 A 的跨行业投研任务可以先基于 full78 做，不需要马上扩容公司；先把任务标准、prompt skill、证据需求和 eval 固化。
- 阶段 B 的产业链任务不能只靠 full78。full78 对 AI 基础设施已有核心公司，但供应链验证还缺服务器、光模块、EDA、半导体设备扩展、电力/散热、数据中心 REIT，以及若干非美国发行人。
- 非美国发行人是结构性缺口。TSM、ASML、ARM 等关键节点通常不是 10-K/10-Q 口径，需要 20-F/6-K、公司年报、IR 材料或外部 web snapshot 支持。在当前 10-K/10-Q-only 主披露 parser 没扩展前，不能声称完整覆盖这些节点。

## 阶段 A：投研任务标准如何落地

阶段 A 的目标不是扩公司，而是把“什么叫有质量的投研回答”变成模型和程序都能执行的合同。

### A1. 公司范围

阶段 A 使用当前 full78 作为 v0.2-alpha baseline，不新增公司。原因：

- full78 已经覆盖 11 个主要行业，足够测试通用投研问题框架。
- 如果此时继续扩容公司，容易把核心问题从“投研任务定义”转移到“数据下载和索引构建”。
- 当前 full78 仍有 10-K/10-Q 缺口需要审计，先修覆盖边界比盲目扩容更重要。

需要先确认的事项：

1. 10-K 233/234 的缺口来源。
2. LOW latest 10-Q 缺口是否为真实披露缺口。
3. full78 每个行业至少 2 家公司能形成横向比较；如果某行业只有单点样本，要标记为 `thin_peer_coverage`。
4. 市场快照中的 FMP 估值字段是否 78/78 完整；缺口必须进入 market source gap。

### A2. 数据和文件要求

阶段 A 每个 case 至少需要这些证据层：

| 证据层 | 用途 | 是否当前可得 |
| --- | --- | --- |
| FY2023-FY2025 10-K | 审计年报、业务描述、风险、MD&A、年度财务事实 | 基本可得，需审计 1 条 annual gap |
| 最新 10-Q | 最新季度或年初至今变化、期间口径 | 77/78 可得，LOW gap 待确认 |
| 8-K earnings release | 管理层解释、guidance、业务动量、需求和订单口径 | 78/78 可得 |
| Exact-Value Ledger | 可比财务值、口径、单位、来源 object id | 已有，需继续加强行业特定指标 |
| Market snapshot | 近期市场反应、相对收益、估值语境、事件窗口 | 78/78 可得 |
| Source gap report | 明确不能支持哪些结论 | 需要系统化输出 |

### A3. 如何进入模型调用

A/B 文档本身不应该整篇塞进 prompt。正确做法是提炼成一个短的、版本化的投研 skill，由 planner、reflection 和 synthesis 分别引用。

建议新增：

```text
src/sec_agent/prompts/investment_research_skill_v1.md
src/sec_agent/prompts/evidence_requirement_planner_v1.md
src/sec_agent/prompts/research_memo_synthesis_v1.md
```

模型调用分三层注入：

1. Planner 注入精简投研 skill。
   - 目标：让模型识别用户问题属于增长、利润率、现金流、周期、估值、竞争、产业链、催化剂还是反证。
   - 输出：结构化 `EvidenceRequirementPlan`，不是直接写答案。

2. Reflection / coverage 注入证据充足性标准。
   - 目标：判断当前证据是否能支撑每类 claim。
   - 输出：是否需要二次检索、需要补查哪些公司/年份/文件/指标/来源。

3. Synthesis 注入投研 memo 写作框架。
   - 目标：只在证据和判断计划内写 memo。
   - 输出：基本面、管理层解释、市场反应、估值语境、分歧、风险、反证和边界。

Planner 目标 schema：

```json
{
  "analysis_intent": "peer_comparison | single_company_change | supply_chain_validation | valuation_divergence | market_reaction | risk_review",
  "investment_question_type": ["growth", "margin", "cash_flow", "cycle", "valuation", "competition", "catalyst", "counterevidence"],
  "claim_types": ["financial_fact", "management_explanation", "market_reaction", "valuation_context", "supply_chain_hypothesis", "risk_claim"],
  "evidence_requirements": [
    {
      "requirement_id": "req_1",
      "tickers_or_universe": ["NVDA", "AMD"],
      "years": [2023, 2024, 2025, 2026],
      "filing_types": ["10-K", "10-Q", "8-K"],
      "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot"],
      "metric_families": ["revenue", "gross_margin", "capex"],
      "period_roles": ["annual", "qtd", "ytd", "ttm"],
      "needed_for_claim_type": "financial_fact"
    }
  ],
  "second_pass_policy": {
    "trigger_if_missing": ["primary_metric", "management_explanation", "market_snapshot", "peer_context"],
    "max_second_passes": 1
  },
  "answer_contract": {
    "must_include": ["evidence_strength", "counterarguments", "source_boundaries"],
    "must_not_include": ["unsupported_current_claim", "price_target_without_valuation_support"]
  }
}
```

### A4. 哪些交给规则和 eval

模型负责理解问题、选择研究框架、提出证据需求和写解释。规则和 eval 不应该替模型做投研判断，但必须限制边界：

- Source tier：SEC、8-K、market snapshot、future web source 不能混权。
- Period role：QTD、YTD、TTM、annual 不能混成一个数。
- Ledger grounding：财务事实必须来自 ledger 或结构化证据。
- Market as-of date：所有市场快照结论必须标注 `as_of_date`。
- Evidence coverage：每类 claim 至少要有对应证据或明确 source gap。
- Confidence calibration：证据不足时不能给强结论。
- Second-pass retrieval：如果缺口在现有数据内可查，应触发二次检索，而不是直接列“建议补查”给用户。
- Memo completeness：答案至少覆盖结论依据、核心假设、证据强度、反证条件和来源边界。

Eval 应该从“答案看起来是否合理”升级为：

1. planner 是否识别正确任务类型。
2. EvidenceRequirementPlan 是否选对公司、文件、年份、指标族和来源层。
3. retrieval 是否拿到足够证据，且没有无关候选膨胀。
4. coverage 是否正确触发二次检索或降级。
5. synthesis 是否按投研框架输出，并保留证据边界。
6. gates 是否拦住 unsupported claim、source mixing、period mixing 和 market-as-current。

## 阶段 B：产业链范围如何落地

阶段 B 的目标是让 Agent 不孤立研究一家公司，而是能自动把公司放回上下游、客户、供应商、替代品和资本开支链条中。

### B1. 公司范围分层

不要一次性把所有可能相关公司塞进 full universe。公司范围分层需要服务主流行业覆盖，而不是只服务 AI 产业链。详细扩容公司清单、下载处理流程和新 source-family 计划见 `183_cross_industry_data_expansion_and_source_format_plan.md`。

#### Layer 0：当前 full78 基础覆盖

当前 full78 已经能支持跨行业 baseline：

- 科技/软件/半导体：MSFT、AAPL、NVDA、GOOGL、META、AMZN、AVGO、CSCO、INTC、AMD、QCOM、TXN、AMAT、MU、INTU、ADP、ADBE、PANW、CRWD、SNOW、ORCL、CRM。
- 金融：JPM、V、BAC、MS、BLK、SPGI、PGR、AXP。
- 医疗：JNJ、LLY、UNH、MRK、ABBV、TMO、ISRG。
- 消费：WMT、PG、NFLX、DIS、TMUS、TSLA、HD、LOW、MCD、BKNG、COST、KO、PEP、PM。
- 能源/材料/工业/地产/公用事业：XOM、CVX、COP、SLB、EOG、CAT、GE、HON、RTX、UPS、UNP、DE、LIN、SHW、FCX、NEM、APD、PLD、AMT、EQIX、WELL、SPG、NEE、SO、DUK、AEP、CEG。

这足够做 A 阶段投研 skill、数据可得性和跨行业 eval baseline，但不足以作为长期主流行业覆盖面。

#### Layer 1：跨主流行业美国 SEC filer 扩容

为了让 B 阶段不偏 AI，建议下一轮以 `full128_us` 为目标，新增约 50 家美国 SEC filer。它们多数可以沿用当前 10-K、10-Q、8-K 和 market snapshot 标准。第一轮候选见 `183`，覆盖信息技术、通信服务、可选消费、必需消费、能源、金融、医疗和工业。

AI 基础设施新增公司仍然可以保留为一个垂直 pilot，但不能作为 B 阶段唯一扩容路线。

#### Layer 2：新披露格式和非美国发行人

关键但当前主披露链路还不能完整同口径处理的公司：

```text
TSM, ASML, ARM
```

它们对 AI supply chain 很重要，但这类问题不只发生在 AI 行业。很多全球行业龙头都涉及 `20-F`、`6-K`、`40-F`、本币、IFRS、ADR 或外国发行人披露。当前 10-K/10-Q parser 不应直接把它们当成同口径 SEC 10-K/10-Q 样本。正确做法：

- 在 relationship graph 中先标记为 `foreign_issuer_source_gap`。
- 暂不让它们进入 10-K/10-Q full-source 对比。
- 等 20-F/6-K parser 或受控 web/company-report source tier 支持后再纳入主链路。

### B2. 数据和文件要求

B 阶段新增的不只是公司文件，还要新增关系图数据。

| 数据/文件 | 目标路径建议 | 作用 |
| --- | --- | --- |
| universe seed config | `configs/research_universe_seed_v0_2.yaml` | 公开的公司关系 seed，不含私有数据和密钥 |
| relationship graph | `data/processed_private/relationships/company_relationship_graph_v0_2.jsonl` | 记录公司关系、方向、证据来源、置信度和可支持 claim |
| relationship source gap | `reports/quality/research_universe_source_gaps_v0_2.json` | 记录 TSM/ASML/ARM 等无法同口径覆盖的问题 |
| expanded SEC manifest | 后续 `sec_investment_coverage_full128_us_*` | 跨主流行业新增美国 SEC filer 的 10-K/10-Q/8-K |
| expanded market snapshot | 后续 `market_yahoo_chart_full128_us_*` | 跨主流行业新增公司的市场快照和估值字段 |
| relationship eval set | `eval_sets/sec_agent_research_ab_eval_v0_2.jsonl` | 验证产业链问题、证据需求、二次检索和边界表达 |

Relationship graph 每条记录至少包含：

```json
{
  "source_ticker": "NVDA",
  "target_ticker": "SMCI",
  "relation_type": "customer_or_downstream_buyer | supplier_or_capacity_provider | direct_competitor | complementary_infrastructure | substitution_risk",
  "direction": "source_affects_target | target_affects_source | bidirectional",
  "financial_link_type": ["revenue", "capex", "orders", "inventory", "margin", "valuation"],
  "time_scope": "current_quarter | next_1_4_quarters | annual | structural",
  "metrics_to_check": ["data_center_revenue", "capex", "orders", "gross_margin"],
  "evidence_source": ["sec_filing", "8k_earnings_release", "market_snapshot", "manual_seed", "future_web_snapshot"],
  "confidence": "high | medium | low",
  "caveats": ["relationship does not prove revenue magnitude"]
}
```

### B3. 如何进入模型调用

产业链不能写死在程序里。正确方式是让模型 planner 看到：

1. 用户问题。
2. 当前可用 company inventory。
3. Relationship graph 摘要。
4. 数据可用性和 source gap。
5. 投研 skill 中的产业链问题框架。

Planner 应输出：

- 是否需要 universe expansion。
- 展开哪些关系类型。
- 每个纳入公司的研究假设。
- 每个假设需要哪些证据。
- 哪些关系只是待验证假设，不能直接写成事实。

示例：

```json
{
  "universe_expansion": {
    "seed_tickers": ["NVDA"],
    "requested_relationships": ["supplier_or_capacity_provider", "customer_or_downstream_buyer", "substitution_risk"],
    "include_tickers": [
      {
        "ticker": "SMCI",
        "reason": "verify AI server demand transmission from GPU demand",
        "needed_evidence": ["10-K business segments", "latest 10-Q revenue and margin", "8-K demand commentary"]
      },
      {
        "ticker": "VRT",
        "reason": "verify data center power/cooling bottleneck and capex transmission",
        "needed_evidence": ["orders/backlog", "data center end-market commentary", "margin commentary"]
      }
    ],
    "source_gaps": [
      {
        "ticker": "TSM",
        "reason": "foreign issuer; 20-F/6-K parser not in current source policy",
        "allowed_use": "relationship hypothesis only until source tier is added"
      }
    ]
  }
}
```

### B4. 哪些交给规则和 eval

规则约束：

- 关系图不能替代披露文件证据。
- 不能仅凭“供应链相关”推断收入规模、利润率或订单增速。
- 非美国发行人的缺口必须显示为 source gap。
- 产业链冲突不能被平均掉；应进入 conflict matrix 或触发二次检索。
- 如果 relationship graph 指向某个现有数据源，二次检索必须先查现有 10-K/10-Q/8-K/market，而不是把“建议补查”直接丢给用户。

Eval 指标：

- Universe expansion precision：纳入公司是否有明确关系和研究用途。
- Universe expansion recall：对核心问题是否漏掉明显关键节点。
- Evidence requirement quality：每个关系是否转成了可执行证据需求。
- Source gap accuracy：TSM/ASML/ARM 等缺口是否被正确标记。
- Answer boundary quality：最终答案是否区分直接披露、管理层口径、市场快照和产业链假设。

## 建议执行顺序

### Step 1：冻结 A/B 独立 scope

产物：

- 本文档。
- `181` 中保留总路线图，A/B 细节引用本文档。

验收：

- 明确 A 阶段先用 full78，不新增公司。
- 明确 B 阶段不再围绕 AI 单一行业扩容，下一轮以跨主流行业 `full128_us` 为主线，非美国发行人暂作 source-family canary / source gap。

### Step 2：做 full78 数据可得性审计

产物：

- `reports/quality/research_ab_full78_data_availability_v0_2.json`

检查：

- 10-K 233/234 缺口。
- latest 10-Q 77/78 缺口。
- 8-K 78/78。
- market evidence 78/78。
- FMP valuation 字段覆盖。
- 每个行业 peer coverage 是否足够。

### Step 3：实现投研 skill v1

产物：

- `src/sec_agent/prompts/investment_research_skill_v1.md`
- `src/sec_agent/prompts/evidence_requirement_planner_v1.md`
- `src/sec_agent/prompts/research_memo_synthesis_v1.md`

要求：

- skill 要短，适合进入模型上下文。
- 不能把 181/182 原文塞进 prompt。
- 每次 run 记录 skill version 和 digest。

### Step 4：扩展 planner schema

产物：

- `EvidenceRequirementPlan` schema 更新。
- planner JSON contract 更新。
- validator 更新。

要求：

- planner 输出投研任务类型、证据需求、二次检索策略和答案合同。
- 规则只校验结构和边界，不替模型做投研先验判断。

### Step 5：建立 relationship graph pilot

产物：

- `configs/research_universe_seed_v0_2.yaml`
- `data/processed_private/relationships/company_relationship_graph_v0_2.jsonl`
- source-gap report。

范围：

- 先做 NVDA/AI infrastructure。
- 同步选 2 个非 AI pilot：银行信贷周期、能源资本纪律或制药商业化。

### Step 6：设计 A/B eval set

产物：

- `eval_sets/sec_agent_research_ab_eval_v0_2.jsonl`

至少包含：

1. NVDA AI 产业链验证。
2. AMD 竞争追赶逻辑。
3. 云 capex 与半导体/基础设施传导。
4. 银行信贷质量与利率周期。
5. 制药管线/商业化。
6. 能源资本纪律。
7. 消费需求弹性。

### Step 7：再进入工程实现和 smoke

先跑小范围：

- full78 A-stage planner + coverage smoke。
- NVDA relationship graph planner smoke。
- 一个二次检索触发 case。
- 一个 source gap 正确暴露 case。

通过后再决定是否按 `183` 扩到 `full128_us`，以及是否启动 20-F/6-K/40-F source-family canary。

## 当前明确不做

- 不把 A/B 文档全文塞进模型 prompt。
- 不为了产业链完整性马上混入 20-F/6-K，除非 parser/source tier 明确支持。
- 不用手写规则替代 planner 的研究范围判断。
- 不把 relationship graph 当成财务事实来源。
- 不在 A 阶段继续盲目扩容公司。

## 最近下一步

建议下一步先做 Step 2 和 Step 3：

1. 写 full78 数据可得性审计脚本，输出 gap report。
2. 把 A/B 投研标准压缩成 `investment_research_skill_v1.md`，接入 planner 和 synthesis 前先做离线 prompt contract review。

这两步做完后，再改 planner schema 和 relationship graph。这样能先确保“投研标准如何传给模型”和“当前数据能支持什么”这两个核心问题被固定下来。
