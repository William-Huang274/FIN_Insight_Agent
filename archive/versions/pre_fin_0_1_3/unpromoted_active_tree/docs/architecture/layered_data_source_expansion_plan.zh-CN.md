# 分层数据源扩容计划

本文档说明 FinSight-Agent 下一阶段如何扩充数据底座。目标不是把数据源堆多，而是让每类数据进入链路后都有清楚的来源、可引用边界、置信度和质量门控。

具体实施顺序、脚本、产物和门控见：[分层数据源扩容执行文档](layered_data_source_expansion_execution_plan.zh-CN.md)。

## 目标

当前系统已经能围绕 SEC、8-K、BM25、ObjectBM25、BGE 和多智能体链路做投研式回答。下一阶段要补齐五层数据：

1. SEC / earnings / transcript：主证据。
2. 市场数据和一致预期：补估值和预期差。
3. 行业数据：补行业深挖。
4. 供应链 / 客户 / 供应商数据：补关系图谱。
5. 新闻 / 公告 / GDELT / Common Crawl：做线索发现。

扩容后的系统要能回答更多公司、更多行业、更多问题深度的金融问题，同时保持证据可追溯，避免把线索、推断和事实混在一起。

## 公司池扩容

公司池分层推进：

| 层级 | 公司范围 | 主要用途 | 推进状态 |
| --- | --- | --- | --- |
| Tier 0 | 当前 238 家 | 回归测试和链路稳定性基线 | 保留 |
| Tier 1 | S&P 500 与当前 238 去重后集合 | 扩大主证据覆盖、行业比较和基础投研问题覆盖 | 下一阶段优先 |
| Tier 2 | 每个核心行业补关键同行、客户、供应商、上下游公开公司；包含 SEC 公司和有可比公开年报/交易所公告的非美公司 | 做行业深挖和关系图谱 | 已先建补充池，下载和解析分流推进 |
| Tier 3 | Russell 1000 / 2000 中高相关公司 | 扩展中小盘覆盖 | 暂缓 |

第一阶段主线建议先扩到 Tier 1。供应链和跨国上下游问题必须额外启用 Tier 2，因为 S&P 500 不能覆盖 Samsung、SK hynix、Foxconn、CATL、Tokyo Electron、Quanta 等全球关键链条节点。Tier 2 不替代 Tier 1，只在用户明确问供应链、客户/供应商、跨行业传导或全球价值链时启用。

## 第一层：主证据

主证据来自公司公开披露，是所有投研输出的基础。

数据范围：

- SEC 10-K / 10-Q。
- 非美上市公司可比公开披露：年度报告、业务报告、交易所公告、监管披露。
- 8-K earnings release。
- earnings presentation / investor presentation。
- SEC CompanyFacts / Submissions 结构化事实。
- transcript 先预留接口；没有合法稳定来源前不作为主线依赖。

落地方式：

- 增加 `issuer_event_documents` 数据表或等价 JSONL 合同。
- 将 SEC filing、海外公开年报、earnings release、presentation 分开建 source type，不能混成一种文本证据。
- 将 XBRL 指标落到 `financial_fact_rows`，保留 `ticker / cik / fiscal_period / metric_name / unit / value / accession_number`。
- 保持 BM25、ObjectBM25、BGE 三条召回路径，但每条 evidence 都要能回到原始文件。

门控：

- chunk 不重复、表格边界完整、核心 item 覆盖率达标。
- exact-value ledger 对 revenue、capex、RPO、provision、cash flow 等核心指标命中。
- Memo 引用必须能追溯到 filing、release 或 presentation。
- 海外公开披露必须能追溯到官方 IR、交易所公告或监管披露入口；不能因为不是 SEC 文件就降级成新闻线索。

## 第二层：市场数据和一致预期

市场数据用于估值、价格反应和预期差。一致预期是高价值数据，但免费来源质量有限。

MVP 数据：

- 日线价格、成交量、基本估值字段。
- 指数、利率、汇率、商品价格。
- 事件窗口收益和波动。
- 宏观数据：利率、通胀、就业、GDP、行业价格。

可接来源：

- Alpha Vantage / Nasdaq Data Link 等市场数据 API。
- FRED、BLS、BEA 等宏观公开数据。
- 商业一致预期源预留接口：FactSet、Visible Alpha、Refinitiv、Bloomberg。

没有商业一致预期前，使用 `expectation_proxy`：

- 管理层 guidance。
- 上次实际值。
- 股价和估值变化。
- 新闻中的 analyst revision 线索。

门控：

- 市场数据必须带 `as_of_date`，不能混用不同日期。
- 免费行情源不得写成专业实时行情。
- 没有真实 consensus 数据时，系统不得写“市场一致预期认为”，只能写“预期代理显示”或“从公开数据可见”。

## 第三层：行业数据

行业数据用于支持 sector-depth，不直接替代公司证据。

优先行业：

- 银行：FDIC、Fed、监管数据。
- 能源和电力：EIA、公开电力负荷、发电、燃料价格。
- 医疗：ClinicalTrials.gov、CMS、FDA 公开数据。
- 消费：零售销售、库存、价格、客流的公开或可授权数据。
- 制造和贸易：Census、USITC、UN Comtrade。

落地方式：

- 建 `industry_indicator_series`：
  - `series_id`
  - `sector`
  - `metric_name`
  - `period`
  - `value`
  - `unit`
  - `source`
  - `source_url`
  - `relevant_tickers`
- 每个行业先选 5-15 个高价值指标，不做低质量全量堆叠。
- Industry Specialist 的 prompt 中显式区分公司证据和行业指标。

门控：

- 只有看到行业指标，Specialist 才能写行业趋势判断。
- 行业指标只能支持行业趋势和外部环境，不能直接证明单家公司业绩。
- 指标必须有时间粒度和单位，不能只存文字摘要。

## 第四层：关系图谱

关系图谱用于供应链、客户、供应商、合作伙伴和经济传导分析。这一层必须严格分级，避免把推断写成事实。

边类型：

| 类型 | 含义 | 能否写成真实客户/供应商 |
| --- | --- | --- |
| `direct_customer_supplier` | 公司或合同明确披露客户/供应商 | 可以 |
| `contractual_relationship` | 8-K、exhibit、官网公告中有合同或采购协议 | 可以，但要引用合同/公告 |
| `partner_channel` | 合作伙伴、渠道、OEM、技术合作 | 不能等同客户/供应商 |
| `shipment_inferred` | 提单或海运数据推断 | 只能写成运输/交易线索 |
| `news_reported` | 新闻报道关系 | 需要二次验证 |
| `sector_exposure` | 行业传导或经济暴露 | 不能写成真实客户/供应商 |

落地方式：

- 建 `relationship_edges`：
  - `edge_id`
  - `source_entity_id / source_ticker / source_cik`
  - `target_entity_id / target_ticker / target_cik`
  - `target_name_raw`
  - `relation_type`
  - `direction`
  - `confidence`
  - `evidence_tier`
  - `source_doc_type`
  - `source_url_or_filing_id`
  - `fiscal_year`
  - `report_date`
  - `evidence_id`
  - `evidence_text`
  - `amount / percentage / metric_name`
  - `product_or_segment`
  - `geography`
  - `valid_from / valid_to`
  - `extraction_method`
  - `verifier_status`
- 先从 SEC、海外公开年报、8-K、exhibit、官网公告抽高置信边。
- 再用 GDELT、Common Crawl、ImportYeti 等作为线索源，不直接升级为高置信边。
- GLEIF / Wikidata 只做实体归一，不当作供应链事实源。

门控：

- Memo 只有高置信 `direct_customer_supplier` 和 `contractual_relationship` 能写“客户/供应商”。
- `sector_exposure` 只能写“需求传导”“经济暴露”“潜在受益链条”。
- 每条关系边必须有证据文本和来源。
- Verifier 必须检查实体方向、关系类型和证据是否匹配。

## 第五层：新闻和线索发现

新闻、官网页面和开放网页用于发现新事件，不作为默认主证据。

数据源：

- GDELT：新闻和公告线索。
- Common Crawl：官网客户页、合作伙伴页、新闻页发现。
- 公司 IR / newsroom / RSS。
- SEC 8-K：正式事件源。

落地方式：

- 建 `external_event_evidence`：
  - `event_id`
  - `event_type`
  - `entities`
  - `relationship_candidate`
  - `source_url`
  - `publisher`
  - `publish_date`
  - `evidence_text`
  - `verification_status`
- 新闻只触发进一步召回、关系候选或研究假设。
- 未通过 SEC、官网、合同或公司公告验证的新闻，不进入高置信关系图谱。

门控：

- 新闻不能单独支撑投资结论。
- 新闻不得覆盖原始公司披露。
- 新闻事件必须有发布日期和来源 URL。

## 链路接入顺序

第一阶段：主证据扩容

- 扩到 S&P 500。
- 美股 `10-K / 10-Q / 8-K earnings release` 复用此前 full238 / RAG 审计已验证脚本，不重建一套新合同。
- 市场快照和行业快照复用此前已验证的 market / industry source-family 管线。
- 新建非美官方披露、公司 IR 业绩材料、结构化财务事实的 source plan 和门控。
- 在 staging 中重建 BM25、ObjectBM25、BGE / Milvus typed vector。
- 重新跑 chunk S0、retrieval-only S3、S1-S8 agent gate。

第二阶段：市场和行业数据

- 接市场数据 MVP 和宏观/行业开放数据。
- 增加 `market_snapshot_rows` 和 `industry_indicator_series`。
- Market Specialist 和 Industry Specialist 增加数据源可见性。
- 评测单公司、行业深挖、市场反应三类问题。

第三阶段：关系图谱

- 建 `relationship_edges` schema。
- 从 SEC、海外公开年报、8-K、exhibit、官网公告抽高置信关系边。
- 接入 Relationship Router 和 Industry Specialist。
- 关系型 case 必须看到并引用关系边。

第四阶段：线索发现

- 接 GDELT / Common Crawl / IR pages。
- 只生成待验证线索。
- 通过 Verifier 后才进入关系图谱或事件证据库。

第五阶段：商业数据预留

- 预留 FactSet、Visible Alpha、Bloomberg、Panjiva 等商业源 adapter。
- 没有授权前不在公开仓库内写入商业源数据或调用假接口。

## 评测矩阵

扩容后要新增这些评测：

| 评测层 | 目标 |
| --- | --- |
| chunk S0 | 扩容后 chunk、table、item、evidence id 合同仍稳定 |
| retrieval S3 | BM25/ObjectBM25/BGE/Milvus 对 exact、sector-depth、relationship、paraphrase 不退化 |
| market gate | 市场数据日期、价格、事件窗口收益可追溯 |
| industry gate | Specialist 能看到并正确引用行业指标 |
| relationship gate | 关系型问题必须命中可引用 edge，且不能把 exposure 写成 direct customer |
| news gate | 新闻只作为线索，不直接支撑高置信结论 |
| memo gate | 最终输出能区分公司事实、行业趋势、市场反应、关系假设和未验证线索 |

## 下一阶段交付物

- `configs/data_sources/*.yaml`：分层数据源配置。
- `src/data_sources/`：SEC、market、industry、relationship、event adapters。
- `scripts/data_expansion/`：公司池扩容、拉取、清洗、重建索引脚本。
- `tests/fixtures/data_sources/`：小规模数据源 fixture。
- `tests/test_data_source_contracts.py`：数据源 schema 和边界测试。
- `docs/architecture/data_and_tool_access_model.zh-CN.md`：工具和数据权限主文档补齐。
- `docs/eval/`：扩容后 S0-S8 门控补充。

## 风险

- 数据源越多，越容易混淆“证据、线索、推断、结论”。必须用 `source_tier` 和 `confidence` 控制。
- 免费市场和新闻数据不能替代专业投研数据。
- 一致预期和商业供应链图谱短期无法免费解决，只能先做接口预留和代理指标。
- 扩公司池会增加构建时间和索引体积，必须先做 Tier 1 回归，再推进 Tier 2。
