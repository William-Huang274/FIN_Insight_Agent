# 旧规划文档吸收与数据治理执行计划

## 背景

本文件吸收三份在 G1-G10 落地前形成的规划文档：

- `agent_graph和skill.docx`
- `数据治理结构20260612.docx`
- `投研工作流升级文档.docx`

这些文档中的一部分已经被当前 Agent Graph vNext G1-G10 和 G11 scaffold 覆盖，不应回滚；另一部分仍然有效，尤其是数据治理层、Entity Master、Claim Evidence Ledger、typed Gap Ledger、Temporal/Vintage、Reconciliation 和 Analyst View，需要作为下一阶段工程主线。

## 总体结论

可以吸收，但不是把旧文档原样并入。处理原则：

1. 已由 G1-G10 覆盖的 graph 机制，只在本文件记录映射，不重复实现。
2. 未充分落地的数据治理层，进入 D1-D11 执行序列。
3. 投研 KG 的五层图谱和行业/公司类型微调，已补入 `07_investment_research_workflow_knowledge_graph_framework.zh-CN.md`。
4. 后续实现顺序应先补 governance runtime，再让 sub-agent 消费更细的 KG 对象。

## 文档一：agent_graph和skill.docx

### 已覆盖内容

以下内容已经被 G1-G10 基本覆盖：

- 专家 agent 不直接写 memo，而是产 ClaimCard。
- 检索后进入 Evidence Fusion / evidence governance，再进入 claim adjudication 和 memo。
- Reflection 不是自由评价，而是 gate fail 后的 targeted repair controller。
- Evidence acquisition fan-out 和 specialist fan-out。
- Memo Writer 不读 raw rows，只消费 verified judgment / claim cards。
- Milvus 只做 semantic recall supplement，不做 exact-value authority。
- Bounded Answer / bounded gap 作为证据不足时的输出。
- Industry playbook 和 source-boundary prompt。

对应当前实现文档：

- G3 Evidence Fusion Selector
- G4 Reflection-driven Second Pass
- G5 Web Evidence Operator
- G6 Product / Technology Specialist
- G7 Playbook Registry
- G8 Shared Context Contract
- G9 Async Fan-out / Barrier Graph
- G10 Milvus Runtime Switch

### 仍应吸收的内容

1. `Source Capability Router` 应成为显式 runtime node 或 policy layer，而不是只存在于 Research Lead / playbook 隐式逻辑里。
2. `Exact Value Subgraph` 应成为所有 numeric claim 的 sidecar，而不是只在 focused lookup 场景触发。
3. graph state 里的 evidence、claim、gap、gate result 应坚持 append-only。
4. Checkpointer / store / vector store / object store 的职责要拆清：
   - checkpointer：thread-scoped graph state。
   - SQL store：evidence ledger、claim cards、gap registry、run audit、research memory。
   - Milvus：typed semantic recall supplement。
   - object store：raw PDF、HTML、XBRL、CSV、snapshot。
5. Interrupt 只用于 scope unclear、commercial data required、unsupported core thesis 但用户可能接受 bounded answer。
6. Runtime event audit 应显式记录 retrieval、gate、repair、claim、verifier 和 bounded answer 事件。

## 文档二：数据治理结构20260612.docx

这份文档是三份里最应该直接转成下一阶段执行序列的部分。它指出当前不是缺更多数据源，而是缺 evidence-governed runtime 的数据层。

### D1 Claim Evidence Ledger

现状：当前有 ClaimCard / Judgment Plan 运行时结构，但还不是 durable ledger。

2026-06-12 v0.1 落地状态：

- 已新增 runtime projection：`sec_agent_claim_evidence_ledger_v0.1`。
- graph 会从 `verified_judgment_plan` / `judgment_plan` 投影 supported / weakly_supported / contradicted / gap_exposed claim。
- persist 节点会写出 `claim_evidence_ledger.json`，并把路径登记到 `artifact_refs.claim_evidence_ledger`。
- summary artifact 会暴露 claim count、status 分布、source strength 分布、Memo Writer eligible count 和 validation status。
- 当前是 artifact-backed ledger，不是 SQL-backed append-only store；跨 run 查询、去重和 research memory 仍留给 D11 / SQL store。

目标字段：

```yaml
claim_id: string
run_id: string
ticker: string
claim_text: string
claim_type: string
supporting_evidence_ids: list[string]
contradicting_evidence_ids: list[string]
source_strength: string
confidence: string
as_of_date: date
claim_status: supported | weakly_supported | contradicted | gap_exposed
required_gate_results: list[string]
```

通过条件：

- Memo Writer 只能消费 ledger 中 `supported` 或明确 bounded 的 claim。
- 每条核心 claim 能反查 evidence、contradiction、gap 和 gate result。

### D2 Typed Gap Ledger

目标 gap 类型：

```text
not_disclosed
not_found
parser_failed
source_boundary_blocked
period_gap
unit_gap
alias_gap
commercial_gap
conflict_gap
staleness_gap
coverage_gap
```

2026-06-12 v0.1 落地状态：

- 已新增 runtime projection：`sec_agent_typed_gap_ledger_v0.1`。
- graph 会从 `source_gaps`、bounded gap register、second-pass hard gate candidates 和 quality gaps 归一化 typed gaps。
- `commercial_tracker_gap` / `commercial_market_tracker_gap` 统一归到 `commercial_gap`，处理动作固定为 `expose_commercial_gap_do_not_proxy`。
- `region_schema_gap` / `parser_schema_gap` 等归到 `parser_failed`，为 targeted repair 保留可处理边界。
- persist 节点会写出 `typed_gap_ledger.json`，并把路径登记到 `artifact_refs.typed_gap_ledger`。
- 当前仍未接 D6 reconciliation ledger；`conflict_gap` 只能被分类和暴露，不能自动解决。

通过条件：

- commercial_gap 不触发弱 proxy fallback。
- parser_failed 进入 targeted repair。
- conflict_gap 进入 reconciliation。
- not_disclosed 直接暴露，不浪费检索。

### D3 Entity / Security Master

目标：统一 ticker、issuer、legal entity、brand、subsidiary、product owner、CIK、LEI、FIGI、ISIN、CUSIP、SEDOL。

2026-06-12 v0.1 落地状态：

- 已新增 runtime projection：`sec_agent_entity_security_master_v0.1`。
- `project_inventory.companies` 会保留 `cik`、`issuer_id`、`lei`、`figi`、`isin`、`cusip`、`sedol`、`legal_name`、`aliases`。
- graph 会从 `project_inventory` 和 query scope 投影 per-run Entity / Security Master。
- persist 节点会写出 `entity_security_master.json`，并把路径登记到 `artifact_refs.entity_security_master`。
- 当前只做 per-run conservative resolver，不做跨 run entity warehouse；品牌、子公司、product owner、ADR/common share、ticker change 仍需 D3.1 扩展。

通过条件：

- Research Lead 和 Evidence Operators 使用统一 `entity_id`。
- 品牌官网、子公司披露、ADR/ordinary share、ticker 变更不会被错误归因。
- GLEIF、OpenFIGI、SEC submissions、company IR、Wikidata 只按 resolver 权限进入。

### D4 Raw Source / Provenance Store

目标：每个 evidence 能反查原始 artifact。

字段：

```yaml
source_id: string
raw_url: string | null
local_path: string | null
file_type: html | pdf | xbrl | json | csv
retrieved_at: datetime
source_as_of_date: date | null
checksum: string
parser_version: string
license_policy: string | null
robots_policy: string | null
access_method: string
document_id: string | null
```

通过条件：

- fact -> object -> filing/source -> raw document -> citation span 可逆。
- parser 重跑后可以比较 before/after。

当前状态（2026-06-12 v0.1 已落地）：

- 新增 `sec_agent_raw_source_provenance_store_v0.1` per-run artifact。
- graph persist 会写出 `raw_source_provenance_store.json`，并在 `artifact_refs`、summary 和 checkpoint summary 暴露。
- 输入覆盖 runtime ledger rows、context rows、market / industry / product / public context rows、tool observations、project inventory filings 和本轮 run artifact refs。
- validation 当前只做结构级 fail-closed：`source_id` 必填、duplicate / raw locator missing / SEC document id missing / URL access method missing 出 warning。
- D4.1 仍需把 per-run JSON 升级为 SQL / object-store backed provenance table，补全 checksum materialization、license/robots registry、parser run lineage 和跨 run before/after diff。

### D5 As-of / Vintage Layer

目标：解决时间错配。

必须区分：

- fiscal_period_end
- filing_date
- accepted_date
- reported_date
- observation_date
- retrieved_at
- source_updated_at
- market_as_of_date
- macro_vintage_date
- parser_run_at

通过条件：

- 不用 2026 年修订后的宏观数据解释 2024 年当时判断。
- 不把 filing date 和 fiscal period end 混用。
- 不把 market snapshot as_of_date 和基本面 period 混用。

当前状态（2026-06-12 v0.1 已落地）：

- 新增 `sec_agent_asof_vintage_layer_v0.1` per-run artifact。
- graph persist 会写出 `asof_vintage_layer.json`，并在 `artifact_refs`、summary 和 checkpoint summary 暴露。
- records 保留 fiscal period、filing / accepted / reported date、observation date、retrieved/source updated date、market as-of、macro vintage 和 parser run time。
- `time_basis` 当前区分 `fiscal_period`、`filing`、`market_as_of`、`macro_vintage`、`source_observation`。
- D5.1 仍需接宏观/行业真实 vintage 数据库、market snapshot as-of table、filing amendment lineage，并把 stale / time-mismatch gate 接入 D9。

### D6 Reconciliation Ledger

目标：解决 SEC exact ledger、SEC Object FTS、SEC FSD / CompanyFacts、Product KPI fact、company IR 之间的冲突。

冲突类型：

```text
unit_conflict
period_conflict
taxonomy_conflict
amendment_conflict
segment_conflict
source_priority_conflict
rounding_conflict
```

通过条件：

- 同一 metric / ticker / period 的候选值进入 reconciliation。
- preferred_value 必须有 resolution_rule 和 confidence。
- conflict_gap 不直接进入 Memo。

当前状态（2026-06-12 v0.1 已落地）：

- 新增 `sec_agent_reconciliation_ledger_v0.1` per-run artifact。
- graph persist 会写出 `reconciliation_ledger.json`，并在 `artifact_refs`、summary 和 checkpoint summary 暴露。
- 当前候选来自 runtime ledger rows、product evidence rows、context/public rows 中带 value 且具备 exact-value authority 的行；context-only / public proxy 会被排除。
- 当前已支持 `unit_conflict`、`period_conflict`、`taxonomy_conflict`、`segment_conflict`、`amendment_conflict`、`source_priority_conflict`、`rounding_conflict` 的确定性分类。
- `source_priority_conflict`、`amendment_conflict`、`rounding_conflict` 只有在规则唯一时生成 `preferred_value`；`unit_conflict`、`period_conflict`、`taxonomy_conflict`、`segment_conflict` fail closed，写入 `conflict_gaps`。
- D6.1 仍需把 reconciliation 结果前移到 Memo Writer 前的事实层选择，并与 D2 typed gap ledger、D9 gate history、D12 database closeout 联动。

### D7 Metric / Product Ontology

分两层：

- Financial Metric Ontology：revenue、gross_profit、operating_income、net_income、FCF、capex、debt、cash、shares、EPS。
- Product KPI Ontology：deliveries、shipments、subscribers、MAU、DAU、ARPU、ASP、bookings、backlog、installed base、production、capacity、utilization、take_rate、GMV。

通过条件：

- 每个 metric / KPI 有 canonical id、accepted aliases、rejected aliases、unit、period rule、allowed source type、cannot_infer_from。
- 产品规格和 operating KPI 不靠字符串相似直接入库。

当前状态（2026-06-12 v0.1 已落地）：

- 新增 `sec_agent_metric_product_ontology_v0.1` per-run artifact。
- graph persist 会写出 `metric_product_ontology_snapshot.json`，并在 `artifact_refs`、summary 和 checkpoint summary 暴露。
- 内置 Financial Metric Ontology 覆盖 revenue、gross_profit、operating_income、net_income、FCF、capex、debt、cash、shares、EPS。
- Product KPI Ontology 吸收既有 `company_product_operating_metric_ontology_v0_1.yaml` 的边界，但不把 grouped positive examples 直接提升为 canonical alias；当前覆盖 product_revenue、deliveries、shipments、subscribers、MAU、DAU、ARPU、ASP、bookings、backlog、installed_base、production、capacity、utilization、take_rate、GMV、same_store_sales。
- 每个 metric/KPI 保留 accepted aliases、rejected aliases、unit_family、period_rule、allowed / exact-authority source families、cannot_infer_from 和 required gates。
- D7.1 仍需迁移到可维护 registry / DB ontology，补行业 playbook 细分 KPI、product spec ontology、manual alias review queue 和 D8.1 source policy table。

### D8 Source Capability Router

目标：把 source matrix 变成 runtime 决策。

输入：

```yaml
query_intent: string
ticker: string
industry: string
metric_type: string
claim_type: string
required_authority: string
```

输出：

```yaml
primary_sources: list[string]
secondary_sources: list[string]
context_sources: list[string]
forbidden_sources: list[string]
required_gates: list[string]
gap_policy: string
```

2026-06-12 v0.1 落地状态：

- 已新增 runtime projection：`sec_agent_source_capability_router_v0.1`。
- graph 会在 evidence requirement / retrieval plan 编译后，把每条 route 映射到 source family capability decision。
- decision 显式区分 `allowed`、`blocked`、`gap`，并带上 `claim_authority`、`context_only`、`exact_value_authority`、`allowed_claim_scope` 和 gap type。
- context-only source family 不能被标成 exact authority；unavailable source 不能被标成 allowed。
- persist 节点会写出 `source_capability_router.json`，并把路径登记到 `artifact_refs.source_capability_router`。
- 当前仍是 route/source-family 层，不是完整 query_intent/industry/metric_type/claim_type policy table；行业和 metric 细粒度 policy 留给 D8.1 与 D7 ontology 联动。

通过条件：

- 查询 iPhone shipments 时，FRED/GDELT/Milvus-only 永远不能作为 claim source。
- 找不到 company-disclosed 或 commercial tracker 时，输出 commercial_gap。

### D9 Gate Registry / Gate History / Eval Matrix

核心 gates：

- source_boundary_gate
- citation_span_gate
- period_alignment_gate
- unit_normalization_gate
- numeric_consistency_gate
- metric_mapping_gate
- segment_mapping_gate
- entity_resolution_gate
- claim_support_gate
- contradiction_gate
- staleness_gate
- commercial_gap_gate

通过条件：

- 每次 gate run 有 target_object_id、status、score、reason、repair_action、before_value、after_value。
- eval case matrix 能覆盖 source-boundary violation 和 weak proxy fallback。

### D10 Derived Metric Layer

目标：保存派生指标和 lineage。

示例：

- YoY / QoQ growth
- gross margin
- operating margin
- FCF margin
- net debt
- ROIC
- inventory days
- revenue per shipment
- ASP / ARPU / take rate

通过条件：

- 每个 derived metric 保存 formula、input_fact_ids、calculation_version、value、unit、gate_status、explainability_trace。

### D11 Analyst View / Research Memory

目标：让 Research Lead 先读结构化 analyst view，再 drill down 到 evidence。

视图类型：

- company_profile_view
- segment_model_view
- product_kpi_view
- earnings_change_view
- risk_factor_view
- bull_bear_debate_view
- thesis_tracker

通过条件：

- Analyst view 只能引用 Claim Evidence Ledger 和 Gap Ledger。
- 不能把 view 当原始事实来源。

### D12 D-series Database Closeout

目标：D1-D11 可以先以 per-run JSON / artifact-backed 方式快速落地，但 D 系列收口前必须补齐需要数据库化的治理层。

必须回补：

- D1.1 Claim Evidence Ledger SQL-backed append-only store。
- D3.1 Entity / Security Master SQL-backed resolver 与跨 run entity history。
- D4.1 Raw Source / Provenance Store SQL / object-store backed provenance、checksum、license / robots、parser run lineage。
- D5.1 As-of / Vintage Layer 的 macro / industry vintage store、market snapshot as-of table、filing amendment lineage。
- D9 Gate Registry / Gate History / Eval Matrix 的持久化。
- D11 Analyst View / Research Memory 的可追溯数据库视图。

通过条件：

- 每个 per-run artifact 都有对应 SQL/DB schema 或明确的“不需要数据库化”理由。
- 有 artifact -> database backfill / migration script。
- 有 artifact 与数据库查询结果的 parity test。
- 任何 agent 读取长期记忆、跨 run claim、source lineage、vintage 或 gate history 时，默认走数据库层，不再只扫单次 run JSON。

## 文档三：投研工作流升级文档.docx

### 已吸收到 07 的内容

- 五层图谱 + workflow runtime layer。
- Layer 0 Entity / Identifier Master。
- Layer 1 Business Operating Graph。
- Layer 2 Capital & Ownership Graph。
- Layer 3 Macro / Industry Driver Graph。
- Layer 4 Evidence / Claim / Gap Layer。
- Layer 5 Workflow Runtime Layer。
- 行业微调：半导体、SaaS、消费/零售、汽车、医药、金融、能源、国防/政府 IT。
- 主营模式微调：实物产品、订阅服务、平台交易、项目制、资源/大宗商品。
- 公司规模微调：大型成熟、中小、高成长亏损、私营/Pre-IPO、非美公司。
- 公开源/商业源/gap 的边界。

### 后续需要机器化的内容

- 把行业微调从文档迁移到 `configs/industry_playbooks_v0_1.yaml` 的下一版。
- 给每个 playbook 增加 object schema、KPI ontology、source router、gate policy、gap policy。
- 给 company scale profile 增加 routing policy。
- 给 non-US profile 增加 primary disclosure parser readiness，而不是简单 IR fallback。

## 优先级

下一阶段建议顺序：

1. D1 + D2：Claim Evidence Ledger 和 Typed Gap Ledger。
2. D3 + D8：Entity / Security Master 和 Source Capability Router。
3. D4 + D5：Raw Source / Provenance Store 和 As-of / Vintage Layer。
4. D6 + D7：Reconciliation Ledger 和 Metric / Product Ontology。
5. D9：Gate Registry / Gate History / Eval Matrix。
6. D10：Derived Metric Layer。
7. D11：Analyst View / Research Memory。
8. D12：D-series Database Closeout，补齐需要 SQL/DB 化的 D1-D11 stores、migration、backfill 和 parity tests。
9. K2-K4：产品规格 ontology、public buyer observer policy、Product / Technology sub-agent upgrade。
10. K5-K8：Capital/Ownership、Macro Exposure、Verifier gates、end-to-end KG sub-agent gate。

## 不改变的边界

- 不把旧文档里的 commercial source 作为默认可用源。
- 不回滚 G1-G10 已落地的 source-boundary、reflection、web scope、Milvus、shared context 和 async barrier。
- 不把 public proxy、news、GDELT、Common Crawl、Wikidata、PatentsView、OpenAlex 直接提权到 company claim。
- 不把 analyst view 当事实来源。
