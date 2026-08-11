# 行业 Playbook 与 Agent Skill 合同

## Research Lead 不做行业专家

Research Lead 的职责是 meta-planning：

- 判断问题类型。
- 识别公司/行业/universe。
- 选择 industry schema 和 playbook。
- 选择 source family。
- 激活 specialist roster。
- 生成 evidence requirements。
- 指定 gap policy 和 reflection policy。

Research Lead 不应学习所有行业细节，也不应产出行业结论。

## Playbook 分层

Playbook 使用机器可读 YAML，按层继承：

```text
common_public_research_policy
 -> sector_playbook
 -> subindustry_playbook
 -> company_override
```

优先实现 8-12 个高频 playbook：

- semiconductors
- consumer_electronics
- software_saas
- internet_platform_app
- banks
- energy_oil_gas
- regulated_utilities
- pharma_biotech
- medtech
- autos_ev
- retail_cpg
- industrials_supply_chain

## Playbook 最小 Schema

```yaml
schema_version: fin_agent_industry_playbook_v0.1
industry_schema: consumer_electronics
aliases: [hardware, smartphone, PC, device]

business_model_drivers:
  - shipments
  - ASP
  - mix
  - channel_inventory
  - component_cost

core_metric_families:
  reported_financials: [revenue, gross_margin, operating_margin, capex, inventory]
  product_kpis: [units, shipments, ASP, installed_base]
  operating_metrics: [sell_through, channel_inventory, production]

source_family_policy:
  primary_sec_filing:
    allowed_claims: [reported_financial_fact, segment_fact, management_commentary]
  company_product_evidence_graph:
    allowed_claims: [product_taxonomy, company_disclosed_product_kpi]
    requires: [runtime_fact_allowed_for_kpi]
  public_source_context:
    allowed_claims: [context, resolver, lead]
    forbidden_claims: [company_product_sales, market_share, profitability]
  live_public_web_context:
    allowed_source_classes:
      - company_official_product_surface
      - commerce_product_surface
      - major_financial_news

commercial_gap_policy:
  shipments: [IDC, Counterpoint]
  market_share: [IDC, Counterpoint]
  channel_inventory: [commercial_tracker]

common_failure_modes:
  - ecommerce_reviews_as_demand_fact
  - search_interest_as_shipment_proxy
  - product_launch_as_revenue_acceleration

specialist_routing:
  fundamental_analyst: high
  product_technology_analyst: high
  industry_supply_chain_analyst: medium
  market_valuation_analyst: conditional
  risk_counterevidence_analyst: high
```

## Specialist Skill 写法

Specialist skill 不写百科，而写：

- 输入字段。
- 可用 source families。
- allowed claim types。
- forbidden claim scopes。
- claim card 输出 schema。
- gap 暴露方式。
- 常见误用。

### Fundamental Specialist

负责：

- reported financial facts
- segment / margin / cash flow / capex
- management commentary
- company-disclosed operating facts

禁止：

- 用 market / industry / public context 证明公司财务事实。
- 自行估算销量、市占率、利润贡献。

### Product / Technology Specialist

负责：

- product taxonomy
- product KPI facts
- official product surface
- regulatory / developer / ecommerce proxy context
- product claim validation
- commercial gap exposure

禁止：

- 用电商/热度/proxy 替代 sell-through、market share、channel inventory。
- 把 public-source context 提权为 company product sales fact。

### Industry / Supply Chain Specialist

负责：

- industry cycle
- macro / commodity / regulatory context
- upstream / downstream transmission
- relationship hypothesis

禁止：

- 把 relationship / industry context 写成 confirmed customer / supplier / revenue exposure fact。

### Market Specialist

负责：

- market reaction
- valuation context
- relative performance
- event window

禁止：

- 用股价或估值变化证明基本面事实。

### Risk / Counterevidence Specialist

负责：

- counter-thesis
- evidence conflict
- source-boundary misuse
- unsupported claim
- missing commercial data / parser gap

禁止：

- 新增事实或补写 memo。

## Claim Card 输出

所有 specialist 输出 ClaimCard：

```json
{
  "claim_id": "string",
  "agent_id": "product_technology_analyst",
  "ticker": "AAPL",
  "claim_type": "company_disclosed_product_kpi | product_taxonomy | industry_context_only | risk_counterclaim",
  "claim": "short bounded claim",
  "support_level": "supported | partial | hypothesis | unsupported",
  "source_family": "company_product_evidence_graph",
  "authority_tier": "company_disclosed_context",
  "evidence_refs": ["..."],
  "allowed_claim_scope": ["..."],
  "forbidden_scope_checked": true,
  "gap_refs": ["..."],
  "verifier_status": "pending"
}
```

Memo Writer 不消费 raw specialist prose，只消费 verified claim cards / judgment plan。
