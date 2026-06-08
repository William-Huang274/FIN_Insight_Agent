# 分层数据源扩容执行文档

> 归档说明：本文是数据源扩容阶段的内部执行文档，保留阶段计划、资产构建和门控过程。当前公开架构请以 [总体架构](fin_sight_agent_architecture.zh-CN.md)、[数据与工具权限模型](data_and_tool_access_model.zh-CN.md) 和 [公开评测摘要](../eval/fin_agent_public_eval_summary.zh-CN.md) 为准。

本文档是 `layered_data_source_expansion_plan.zh-CN.md` 的执行层版本。它回答三个问题：

- 下一阶段先做什么、后做什么。
- 每一步产出哪些脚本、配置、数据合同和测试。
- 如何把上一阶段未完成的关系图谱任务收口，避免扩容后把未验证关系、行业暴露和真实客户/供应商混在一起。

## 执行原则

1. 数据扩容可以先启动，但不能直接进入主线向量库。
2. 新数据进入 BM25 / ObjectBM25 / BGE / Milvus 前，必须先完成关系边、实体归一、关系校验和数据源分级合同。
3. 关系型证据必须区分“真实客户/供应商”“合作伙伴”“合同关系”“新闻线索”“运输线索”“行业暴露”。
4. Milvus 只作为 typed semantic recall layer，不替代 BM25、ObjectBM25 和 exact-value ledger。
5. 每一层数据都必须有 `source_tier`、`confidence`、`as_of_date` 或等价字段。

## 阶段总览

| 阶段 | 目标 | 是否允许并行 | 主门控 |
| --- | --- | --- | --- |
| E0 | 冻结当前主线和执行合同 | 否 | staged scope 清楚、无敏感信息 |
| E1 | 建数据源配置和公司池合同 | 是 | Tier 0/Tier 1/Tier 2 universe 可复现 |
| E2 | 扩 SEC / 全球公开年报 / 8-K / earnings 主证据 | 是 | chunk S0 和 exact-value ledger 不退化 |
| R1 | 建 `relationship_edges` schema 和置信度规则 | 可与 E2 并行 | edge schema 单测通过 |
| R2 | 从当前 238 家 SEC evidence 抽高置信关系边 | 可与 E2 并行 | direct edge precision gate |
| R3 | 做实体归一：别名、子公司、ticker、CIK | 可与 R2 并行 | entity resolution gate |
| R4 | 加关系 Verifier，阻止 exposure 写成 customer/supplier | 否 | verifier hard gate |
| R5 | 接入 Relationship Router 和 Industry Specialist | 否 | runtime ledger 和 Specialist 引用 gate |
| V1 | 重建 typed vector / BM25 / ObjectBM25 | 依赖 R1-R5 | typed vector gate |
| F1 | 小批 full-chain 和 S1-S8 回归 | 依赖 V1 | memo quality gate |
| X1 | 评估新闻、网页、商业供应链等非主披露数据是否补覆盖率 | 依赖 R1-R5 | source value / legal boundary gate |

## 2026-06-05 首轮执行结果

已完成：

- E1：新增公司池和数据源合同配置，Tier 0 当前 238 家 manifest 构建 smoke 通过；随后下载当前 S&P 500 成分股并生成真正的 Tier 1 去重 manifest。
- R1：新增 `relationship_edges` schema、置信度规则、实体归一基础合同和单测。
- R2：新增 SEC evidence 关系候选抽取、确定性 verifier、关系边质量 audit 脚本。

当前真实运行结果：

- 输入：`sector_depth_full238_us_v0_5_mixed_with_8k_evidence_fy2023_2027.jsonl`，共 `91,708` 条 evidence rows。
- 目标池标记：`target_company_count=500`。
- 实际关系边抽取覆盖：当前本地只有 full238 SEC evidence；虽然 Tier 1 公司池已经生成，但尚未下载 Tier 1 SEC 文件，所以本轮不是完整 500 家关系边抽取。
- 候选抽取：`818` 条 candidates。
- verifier 后：`768` 条 verified，`50` 条 rejected。
- verified 分布：`contractual_relationship=320`、`partner_channel=440`、`direct_customer_supplier=8`。
- 置信度：`high=38`、`medium=730`。当前 direct customer/supplier 全部为 medium，因为目标多为未映射的外部客户或供应商。
- 已修复的误抽：地区列表、`U.S`、`China-based`、`Table of Contents Online sales`、`Major customer One of our end customers`、`Certain Key` 等泛称不能进入 verified direct edge。

本轮结论：

- R1/R2 baseline 可以继续往 R3/R4 推进。
- 现在的关系边基线以高精度为主，覆盖率偏保守。
- 真正 500 家抽取必须先完成 Tier 1 SEC evidence 下载/清洗；否则只能对当前 full238 资产抽边。
- 下一步要做 R3 实体归一增强，把 `WT Microelectronics Co., Ltd`、`ODP`、`Janssen Biotech, Inc`、`Genentech, Inc` 等外部实体纳入 alias registry，再决定哪些 medium edge 可升级。

Tier 1 公司池结果：

- S&P 500 source rows：`503` 个股票代码。
- S&P 500 去重后：`500` 个唯一 CIK / 公司。
- 与 current full238 合并去重后：`505` 家公司。
- current-only retained：`CE`、`CTRA`、`LNG`、`MRVL`、`SNOW`。
- share-class / ticker alias 保留在 `alternate_tickers`，例如 `GOOGL <- GOOG`、`FOXA <- FOX`、`NWSA <- NWS`。
- Tier 1 audit：`505` 家、`0` missing CIK、`505` SEC-download eligible。

Tier 2 供应链补充池结果：

- Tier 2 新增：`98` 家。
- 其中 SEC / EDGAR 可拉取：`83` 家。
- 其中非美公开披露主证据公司：`15` 家，覆盖 Samsung Electronics、SK hynix、Hon Hai / Foxconn、Quanta、CATL、BYD、LG Energy Solution、Panasonic、Tokyo Electron、Advantest、DISCO、Infineon、Renesas 等关键链条节点。
- Tier 1 + Tier 2 合并后：`603` 家；`588` 家可走 SEC 下载，`15` 家走全球公开披露下载。
- Tier 2 audit：`98` 家 pass；合并池 audit：`603` 家 pass。
- 结论：非美上市公司的官方年报、交易所公告、监管披露不再作为 source gap，而是与 SEC 主披露同优先级处理，只保留来源边界和下载路径差异。

全球公开披露 source-plan 结果：

- 输入：Tier 2 中 `global_public_download_eligible=true` 的 `15` 家非美主披露公司。
- 输出：`69` 条年度类披露计划行。
- 年份：`2023`、`2024`、`2025`。
- 默认纳入报告类型：`annual_report`、`business_report`、`annual_securities_report`、`integrated_report`。
- 默认不纳入季度/中期报告；需要时用 `--include-interim` 另行生成，避免下载面失控。
- profile 分布：`kr_dart_business_report=18`、`tw_mops_annual_report=12`、`jp_edinet_annual_securities_report=30`、`hkex_annual_report=3`、`szse_cninfo_annual_report=3`、`eu_regulated_annual_report=3`。
- 报告类型来源：`disclosure_profile=69`，不从公司行写死报告组合。
- source-plan audit：`pass`，阻断公司级 `target_reports` 回流。
- dry-run 下载任务：`69` 条，`document_downloaded_count=0`，按 profile strategy 分发。
- download strategy 分布：`official_locator_then_disclosure_search=18`、`mops_company_report_lookup=12`、`edinet_document_search=30`、`hkexnews_issuer_report_search=3`、`cninfo_security_report_search=3`、`company_ir_official_report_download=3`。
- 真实下载 smoke：已实现 profile 层通用 `company_ir_official_report_download`，Infineon `eu_regulated_annual_report` 2023-2025 年报下载 `3/3` pass，写入 checksum metadata；DART/MOPS/EDINET/HKEX/CNINFO 仍待 profile-specific downloader。
- 新增显式 company IR fallback gate：默认关闭；只有 `--allow-company-ir-fallback` 且任务允许 `company_ir` 时才使用官网 IR 作为 staging-only 兜底，不把它伪装成监管/交易所下载器。
- Samsung fallback smoke：v0.1 暴露半年度 interim PDF 误选，已通过 annual-like hard term gate 修复；v0.3 正确输出 `no_matching_document_candidate`，并覆盖 metadata，避免旧错误下载状态被误读。
- 非美 profile-specific downloader/parser 状态已显式写入 profile 和下载 metadata：DART / EDINET 标记为 `blocked_requires_official_api_key`，分别需要 `DART_API_KEY` / `EDINET_API_KEY`；MOPS / HKEX / CNINFO 标记为 `profile_specific_scaffold_pending`，原因分别是表单参数和报告类型校验、issuer-code/headline category 映射、security-code/org-id 和过期公告过滤尚未落地。
- 不允许 fallback 的 profile-specific smoke：`69` 个任务中 `3` 个 EU company IR 真实下载，`48` 个 DART/EDINET 任务按官方 API key 阻塞写入 metadata，`18` 个 MOPS/HKEX/CNINFO 任务按 profile scaffold 未完成写入 metadata。该 smoke 的 `status=fail` 是正确门控结果，表示这些路径不能被误当作已接入。
- 产物：
  - `data/manifests/tier2_global_public_disclosure_source_plan_v0_1.jsonl`
  - `data/manifests/tier2_global_public_disclosure_source_plan_summary_v0_1.json`
  - `data/manifests/tier2_global_public_disclosure_source_plan_audit_v0_1.json`
  - `data/manifests/tier2_global_public_disclosure_download_tasks_v0_1.jsonl`
  - `data/manifests/tier2_global_public_disclosure_download_tasks_summary_v0_1.json`
  - `data/manifests/tier2_global_public_disclosure_eu_ifx_profile_download_smoke_v0_1.jsonl`
  - `data/manifests/tier2_global_public_disclosure_eu_ifx_profile_download_smoke_summary_v0_1.json`

Tier 1 美国 10-K staging 结果：

- 下载配置：`configs/data_sources/tier1_sp500_us_annual_10k_fy2023_2025.yaml`。
- Staging dataset registry：`configs/data_sources/layered_staging_datasets_v0_1.yaml`。
- 请求任务：`1515` 条，覆盖 `505` 家 SEC-download eligible 公司、2023-2025 年 10-K。
- 真实下载成功：`1500` 份。
- 下载缺口：`15` 条，主要是新上市、拆分、ticker 变更或 fiscal-year 口径不可得：BLK 2023、FDXF 2023-2025、GEV 2023、KR 2023、PSKY 2023-2024、Q 2023-2024、SNDK 2023-2024、SOLV 2023、SW 2023、CRWD 2025。
- Manifest：`1500` records。
- Chunks：`161455` records；核心 item 分布为 Item 1 `24014`、Item 1A `44738`、Item 7 `34475`、Item 7A `3581`、Item 8 `54647`。
- EvidenceObject：`161455` records，streaming 构建；`table_evidence=70243`。
- Structured objects：`166025` tables、`3896142` metrics、`1223646` claims。
- Evidence BM25：`161455` records，staging path `data/indexes/staging/bm25/tier1_sp500_us_annual_10k_fy2023_2025_v0_1`。
- Structured object database：`5285809` records，使用 SQLite FTS staging path `data/indexes/staging/sqlite_fts/tier1_sp500_us_annual_10k_objects_fy2023_2025_v0_1`。
- Legacy full ObjectBM25：不构建。原因是旧 `rank_bm25` object builder 会把 528 万结构化对象 token corpus 全部放入内存；本阶段用 SQLite FTS 作为可扩展结构化对象后端。
- Exact-value ledger：本地 core ledger 已完成，扫描 `4062164` 个 metrics+tables 源对象，生成 `908586` 条核心数值事实，覆盖 banking、capex、provision、revenue、margin、cash flow、R&D 和主要分部收入类指标。云端 full ledger 已完成，扫描 `4062160` 个 metrics+tables 源对象，生成 `4810839` 条数值事实，DuckDB 约 `990.76MB`，MSFT capex、JPM provision、NVDA revenue 查询 smoke 通过。旧 `duckdb_executemany` 写入路径 2 小时后仍未完成；新 `csv_copy` 写入路径约 `240.58` 秒完成。
- Milvus：云端 build-only 已通过；只构建 evidence semantic typed vectors，不向量化 528 万结构化对象。当前 typed vector 总量为 `460988`，包含 narrative、paraphrase、relationship、table_chunk；BGE-M3 走 CUDA。NVDA query smoke 能命中 NVDA Item 1A / Item 7 evidence。
- Tracked summary：`data/manifests/tier1_sp500_us_annual_staging_assets_summary_v0_1.json`。
- Promotion status：`staging_only`。R1-R5 和非美 disclosure shard 完成前，不允许覆盖主线 index。

Tier 2 SEC 年度主披露 staging 结果：

- 下载配置：`configs/data_sources/tier2_supply_chain_sec_annual_fy2023_2025.yaml`。
- Staging dataset registry：`configs/data_sources/layered_staging_datasets_v0_1.yaml`。
- 范围：Tier2 中 `83` 家 SEC-download eligible 公司，按公司 `target_forms` 选择 `10-K`、`20-F`、`40-F` 年度主表单。
- 请求任务：`249` 条，覆盖 2023-2025 年。
- 真实下载成功：`226` 份；成功表单分布为 `10-K=143`、`20-F=77`、`40-F=6`。
- 下载缺口：`23` 条，主要是新上市、表单口径或目标年度无对应年度主表单。
- Parser 修复：20-F 不再按 10-K Item 字面规则切分，而是把 `3.D/4/5/11/18` 映射到现有 `1A/1/7/7A/8` 证据语义；同时修复 `Item` 被抽成 `Ite` / `m 1. Business` 的 10-K 断行形态。
- 40-F 修复：对 CCJ / TECK 2023-2025 六份 40-F materialize `40-F.annual_package.html`，合成 Annual Information Form、audited financial statements、MD&A exhibits；40-F zero-chunk 从 `6` 降到 `0`。
- Chunks：`30600` records；其中 `10-K=14849`、`20-F=13316`、`40-F=2435`。
- EvidenceObject：`30600` records，`table_evidence=13066`。
- Structured objects：`48977` tables、`421828` metrics、`240694` claims。
- Evidence BM25：`30600` records，staging path `data/indexes/staging/bm25/tier2_supply_chain_sec_annual_fy2023_2025_v0_1`。
- Structured object database：`711499` records，SQLite FTS staging path `data/indexes/staging/sqlite_fts/tier2_supply_chain_sec_annual_objects_fy2023_2025_v0_1`。
- Exact-value ledger：本地 staging ledger 已完成，生成 `392015` 条数值事实，path `data/indexes/staging/ledger/tier2_supply_chain_sec_annual_fy2023_2025_v0_1_ledger.duckdb`。
- Chunk quality audit：`20260606_tier2_supply_chain_sec_annual_chunk_quality_v0_2` 通过。
- Remaining gaps：40-F AIF 仍有 front matter / table-of-contents 噪声；20-F/40-F ledger 排序需要补 currency/value-role gate，避免百分比行压过收入金额行；非 SEC global-public parser/chunk/index 未接入。
- Tracked summary：`data/manifests/tier2_supply_chain_sec_annual_staging_assets_summary_v0_2.json`。
- Promotion status：`staging_only`。Tier2 global-public profile downloader/parser 和 relationship R1-R5 完成前，不允许覆盖主线 index。

公司业绩材料 source-plan 结果：

- 执行边界：美股 SEC `8-K Item 2.02 / EX-99.1` earnings release 不重建新管线，复用既有 `scripts/data_sec/download_sec_8k_earnings.py`、`build_sec_8k_earnings_manifest.py`、`build_sec_8k_earnings_chunks.py`。
- 新建范围：非美公司官方 IR 的 earnings release 和 investor presentation locator rows。
- 输出：`data/manifests/company_earnings_material_source_plan_v0_1.jsonl`。
- Summary：`data/manifests/company_earnings_material_source_plan_summary_v0_1.json`。
- 计划行：`888`；公司：`603`。
- 复用 SEC 8-K earnings 管线：`588` 行。
- 非美 company IR material locator：`300` 行，来自 `15` 家非美公司、2024-2025 年、`FY/Q1/Q2/Q3/Q4`、两类材料。
- source family 分布：`sec_8k_earnings_release=588`、`company_earnings_release=150`、`company_presentation=150`。
- 门控：company-authored earnings material 只能支持管理层口径、业绩解释和事件线索；不得替代 audited/statutory filing 或 exact-value ledger fact。

结构化财务事实 source-plan 结果：

- 执行边界：此前从 SEC chunk/structured objects 建出的 ledger 可复用；新增 source plan 负责把 SEC CompanyFacts/Submissions 和非美官方报告财务表格事实分开治理。
- 输出：`data/manifests/structured_financial_fact_source_plan_v0_1.jsonl`。
- Summary：`data/manifests/structured_financial_fact_source_plan_summary_v0_1.json`。
- 计划行：`1221`；公司：`603`。
- SEC API 下载计划：`1176` 行，其中 `sec_companyfacts=588`、`sec_submissions=588`。
- 非美官方报告财务表格派生计划：`45` 行，来自 `15` 家非美公司、2023-2025 年。
- exact-value ledger candidates：`633` 行，包括 SEC CompanyFacts 和非美财务表格事实派生。
- 门控：非美结构化事实必须等官方报告下载、parser profile、source checksum 和 table-boundary audit 通过后才能进 exact-value ledger；不能把普通 narrative chunk 直接当 fact row。

SEC CompanyFacts / Submissions materialization 结果：

- 新增 downloader / normalizer：`scripts/data_expansion/download_sec_structured_facts.py`。
- 输入：`data/manifests/structured_financial_fact_source_plan_v0_1.jsonl` 中 `588` 家 SEC-download eligible 公司。
- raw cache：`data/raw_private/structured_financial_facts/sec/<ticker>/sec_companyfacts.json` 和 `sec_submissions.json`，附 checksum metadata。
- staging fact rows：`data/staging/structured_financial_facts/sec_companyfacts_financial_fact_rows_v0_1.jsonl`。
- staging filing rows：`data/staging/structured_financial_facts/sec_submissions_filing_rows_v0_1.jsonl`。
- Summary：`data/manifests/sec_structured_facts_download_summary_v0_1.json`。
- 真实下载：CompanyFacts `588/588`、Submissions `588/588`。
- 归一化行数：CompanyFacts financial fact rows `2,790,261`；Submissions filing rows `6,605`。
- 年份和表单：`2023-2025`，`10-K / 10-Q / 20-F / 40-F`。
- 表单分布：`10-K=988,200`、`10-Q=1,752,865`、`20-F=44,890`、`40-F=4,306`。
- 当前状态：`staging_only`。这些 rows 已能作为 exact-value ledger 候选事实，但尚未 merge 到主线 ledger；后续需要做 metric ontology、period/duplicate resolution、currency/value-role gate 和 ledger query smoke。

## E0：主线冻结和分支准备

目标：确认当前 staged 主线脚本和文档能作为下一阶段起点。

执行：

- 确认当前分支：`codex/layered-data-source-expansion`。
- 确认 staged 文件列表，不使用 `git add .`。
- 对 staged 文件做敏感信息扫描。
- 如需提交，提交前只 stage 已确认的主线脚本、配置、测试、文档。

产出：

- staged 主线变更。
- 本执行文档。
- 工作日志索引更新。

门控：

- 无真实 API key、SSH 密码、private token。
- 无未暂存改动混入下一阶段。
- 当前分支和 staged scope 在 final / worklog 中说明。

## E1：数据源配置和公司池合同

目标：先让扩容对象可复现，不直接写死在脚本里。

新增或更新：

- `configs/data_sources/universe_tiers.yaml`
- `configs/data_sources/source_families.yaml`
- `configs/data_sources/ingestion_profiles.yaml`
- `configs/data_sources/global_public_disclosure_profiles_v0_1.yaml`

`universe_tiers.yaml` 应包含：

```yaml
tier0_current_full238:
  description: current 238-company regression baseline
  manifest_path: data/manifests/tier0_full238_manifest.jsonl
  promotion_role: regression_baseline

tier1_sp500_plus_current:
  description: S&P 500 plus current covered companies
  manifest_path: data/manifests/tier1_sp500_plus_current_manifest.jsonl
  promotion_role: next_main_evidence_pool

tier2_supply_chain_supplement:
  description: SEC issuers plus non-US public-reporting companies for supply-chain and sector-depth questions
  manifest_path: data/manifests/tier2_supply_chain_supplement_manifest.jsonl
  combined_manifest_path: data/manifests/tier1_plus_tier2_supply_chain_manifest.jsonl
  promotion_role: sector_depth_supply_chain_supplement
```

`source_families.yaml` 应包含：

- `sec_primary_filing`
- `global_public_annual_report`
- `global_public_interim_report`
- `sec_8k_earnings_release`
- `company_presentation`
- `market_price_snapshot`
- `macro_industry_indicator`
- `relationship_edge`
- `external_event_lead`

脚本：

- `scripts/data_expansion/build_universe_tiers.py`
- `scripts/data_expansion/build_supply_chain_supplement_manifest.py`
- `scripts/data_expansion/build_global_public_disclosure_source_plan.py`
- `scripts/data_expansion/audit_global_public_disclosure_source_plan.py`
- `scripts/data_expansion/download_global_public_disclosures.py`
- `scripts/data_expansion/audit_universe_tiers.py`

门控：

- Tier 0 公司数等于当前基线。
- Tier 1 去重后 ticker / CIK 唯一。
- Tier 2 去重后 ticker / issuer_id 唯一；SEC 子集要求 CIK 唯一。
- 每家公司必须有 ticker、company name、sector 或 source gap。
- 未能映射 CIK 的公司不能进入 SEC 下载队列。
- 非 SEC 但有可比公开披露的公司必须带 `source_family`、`disclosure_profile`、`official_sources`，并进入全球公开披露下载队列。

## E2：主证据扩容

目标：扩到 Tier 1；供应链 / 跨国上下游问题使用 Tier 1 + Tier 2。所有新证据只先进入 staging data pool，不直接替换主线索引。

执行边界更新：

- 美股官方披露 `10-K / 10-Q / 8-K earnings release`、市场快照、行业快照沿用此前 full238 / RAG 审计中已经跑通的脚本、合同和门控，不重新发明下载和解析路径。
- 新开发集中在三块：非美官方披露、非美/美公司业绩材料统一合同、结构化财务事实。
- 美股业绩材料中的 SEC `8-K Item 2.02 / EX-99.1` 走现有 SEC 8-K earnings 管线；非美 earnings release / investor presentation 走公司 IR 官方材料 source plan。
- 结构化财务事实单独建 source plan：SEC 公司接 `CompanyFacts / Submissions` API；非美公司只从已下载官方年报/中报的财务表格派生，未通过 parser/checksum/table-boundary gate 前不得进入 exact-value ledger。

数据范围：

- 近 2-3 年 10-K / 10-Q。
- 非美公开披露公司的近 2-3 年年度报告、业务报告、交易所公告和中期/季度报告。
- 近 8-12 个 8-K earnings release。
- earnings / investor presentation 如有可稳定获取来源再接。
- SEC CompanyFacts / Submissions 结构化事实。

脚本：

- `scripts/data_expansion/download_sec_tier1_filings.py`
- `scripts/data_expansion/download_global_public_disclosures.py`
- `scripts/data_expansion/build_company_earnings_material_source_plan.py`
- `scripts/data_expansion/build_structured_financial_fact_source_plan.py`
- `scripts/data_expansion/download_sec_structured_facts.py`
- `scripts/data_expansion/build_tier1_sec_chunks.py`
- `scripts/data_expansion/build_global_public_disclosure_chunks.py`
- `scripts/data_expansion/build_tier1_evidence_objects.py`
- `scripts/data_expansion/build_tier1_financial_facts.py`

产出：

- `data/manifests/tier1_sp500_plus_current_manifest.jsonl`
- `data/manifests/tier2_supply_chain_supplement_manifest.jsonl`
- `data/manifests/tier1_plus_tier2_supply_chain_manifest.jsonl`
- `data/manifests/tier2_global_public_disclosure_source_plan_v0_1.jsonl`
- `data/manifests/tier2_global_public_disclosure_download_tasks_v0_1.jsonl`
- `data/manifests/tier2_global_public_disclosure_eu_ifx_profile_download_smoke_v0_1.jsonl`
- `data/manifests/company_earnings_material_source_plan_v0_1.jsonl`
- `data/manifests/structured_financial_fact_source_plan_v0_1.jsonl`
- `data/manifests/sec_structured_facts_download_summary_v0_1.json`
- `data/staging/structured_financial_facts/sec_companyfacts_financial_fact_rows_v0_1.jsonl`
- `data/staging/structured_financial_facts/sec_submissions_filing_rows_v0_1.jsonl`
- `data/staging/sec_tier1/chunks_*.jsonl`
- `data/staging/global_supply_chain_tier2/chunks_*.jsonl`
- `data/staging/sec_tier1/evidence_*.jsonl`
- `data/staging/global_supply_chain_tier2/evidence_*.jsonl`
- `data/staging/sec_tier1/financial_facts_*.jsonl`
- `data/staging/sec_tier1/source_gaps_*.jsonl`

门控：

- S0 chunk quality：重复 id 为 0，表格 marker 平衡，核心 item 缺口低于阈值。
- exact-value：核心指标 ledger hit 不低于 Tier 0 基线。
- SEC CompanyFacts/Submissions：raw JSON 必须有 checksum metadata；staging fact row 必须带 ticker、CIK、taxonomy、concept、unit、value、period、form、accession number、source family 和 `exact_value_ledger_candidate`。
- source gap：缺 filing / 缺 item / 缺 8-K earnings release 必须显式记录。
- 全球公开披露：下载成功只代表 raw/staging 原料可用；未完成 parser、chunk S0、exact-value ledger 和 source-boundary gate 前，不能进入主线 evidence/vector index。
- 只能生成 staging index，不允许覆盖当前主线 index。

## R1：`relationship_edges` Schema 和置信度规则

目标：先定义关系边合同，再抽取关系。

新增：

- `configs/relationships/relationship_edge_schema_v0_1.json`
- `configs/relationships/relationship_confidence_rubric_v0_1.json`
- `src/sec_agent/relationships/edge_schema.py`
- `tests/test_relationship_edge_schema.py`

核心字段：

```text
edge_id
source_entity_id / source_ticker / source_cik
target_entity_id / target_ticker / target_cik
target_name_raw
relation_type
direction
confidence
evidence_tier
source_doc_type
source_url_or_filing_id
fiscal_year
report_date
evidence_id
evidence_text
amount / percentage / metric_name
product_or_segment
geography
valid_from / valid_to
extraction_method
verifier_status
```

关系类型：

- `direct_customer_supplier`
- `contractual_relationship`
- `partner_channel`
- `shipment_inferred`
- `news_reported`
- `sector_exposure`

置信度：

| 等级 | 条件 | 可否写成客户/供应商 |
| --- | --- | --- |
| high | SEC、合同、8-K、官网公告明确双方和关系 | 可以 |
| medium | 新闻或官网页面明确关系但未找到正式合同/SEC 支持 | 需要限定措辞 |
| low | 提单、行业暴露、间接推断 | 不可以 |
| rejected | 证据不支持或方向不明 | 不进入主链路 |

门控：

- `direct_customer_supplier` 必须有双方实体和原文证据。
- `sector_exposure` 永远不能被 verifier 升级为真实客户/供应商。
- `confidence=high` 必须来自 source tier allowlist。

## R2：从当前 238 家 SEC Evidence 抽关系边

目标：先用当前已稳定的 full238 资产抽高精度关系边，作为关系图谱基线。

候选证据范围：

- 10-K Item 1：customers、suppliers、distribution、partners。
- 10-K Item 1A：customer concentration、supplier concentration、single-source risk。
- notes：major customers、purchase commitments、concentration risk。
- 8-K / exhibit：supply agreement、customer agreement、strategic partnership。
- earnings release：customer win、partner announcement，只能先标为 `partner_channel` 或 `news_reported`，除非文本明确合同/客户供应商关系。

脚本：

- `scripts/relationships/extract_relationship_edge_candidates.py`
- `scripts/relationships/verify_relationship_edges.py`
- `scripts/relationships/audit_relationship_edge_quality.py`

抽取方式：

- 第一版用规则 + bounded LLM 或 deterministic parser。
- LLM 只能从给定 evidence span 抽取，不能补全未出现实体。
- 每条边必须带 `evidence_id` 和 `evidence_text`。

产出：

- `data/staging/relationships/full238_relationship_edge_candidates_v0_1.jsonl`
- `data/staging/relationships/full238_relationship_edges_verified_v0_1.jsonl`
- `eval/relationship_edges/full238_relationship_edge_quality_v0_1.json`

门控：

- direct edge 必须 precision 优先，宁可少抽，不能误抽。
- 每条 high-confidence edge 都有可回溯 evidence。
- candidate 到 verified 的 reject reason 必须统计。

## R3：实体归一

目标：把公司别名、子公司、ticker、CIK 和原始文本名称对齐，避免关系边指向混乱。

新增：

- `src/sec_agent/entities/entity_resolution.py`
- `configs/entities/entity_alias_rules_v0_1.json`
- `tests/test_entity_resolution_contract.py`

数据源：

- 当前 SEC universe manifest。
- SEC CIK / company name。
- 公司别名和常见子公司手工种子。
- GLEIF / Wikidata 只作为可选辅助，不直接作为供应链事实。

产出：

- `data/staging/entities/entity_alias_registry_v0_1.jsonl`
- `data/staging/entities/entity_resolution_audit_v0_1.json`

门控：

- ticker / CIK 一对一稳定。
- 子公司 alias 不能默认等同上市公司，必须记录 `parent_resolution_confidence`。
- 未解析目标实体的 edge 可以保留 `target_name_raw`，但不能进入 high-confidence direct edge。

## R4：关系 Verifier Gate

目标：阻止下游把 exposure、partner、news lead 写成真实 customer/supplier。

新增：

- `src/sec_agent/relationships/relationship_verifier.py`
- `tests/test_relationship_verifier_gate.py`

Verifier 检查：

- 关系类型是否被证据文本支持。
- 方向是否明确。
- direct customer / supplier 是否有明确双方。
- 是否把行业暴露误写成客户/供应商。
- 是否存在低置信边被 Memo Writer 当成事实引用。

硬门控：

- `sector_exposure` 出现在 direct customer/supplier 槽位 -> fail。
- `news_reported` 没有二次验证却写成 direct customer/supplier -> fail。
- `partner_channel` 写成 supplier/customer -> fail。
- `shipment_inferred` 写成长期供应关系 -> fail。

## R5：接入 Relationship Router 和 Industry Specialist

目标：让关系边进入主链路，而不是只停留在离线数据表。

改动点：

- Relationship Router：
  - 先查 verified `relationship_edges`。
  - 再查 sector exposure / economic link。
  - 返回 `relationship_summary` 和 `relationship_edge_rows`。
- Industry Specialist：
  - 必须看到 `relationship_summary`。
  - relationship / sector-depth case 下必须引用至少一条相关 relationship evidence 或明确写 source gap。
- Runtime ledger：
  - 增加 `relationship_edge_rows`、`relationship_edge_counts_by_type`、`relationship_confidence_counts`。

测试：

- `tests/test_relationship_router_verified_edges.py`
- `tests/test_industry_specialist_relationship_edge_context.py`
- `tests/test_runtime_ledger_relationship_edge_counts.py`

门控：

- relationship case 必须激活 Relationship Router。
- 有 verified edge 时，Industry Specialist 必须能看到并引用。
- 无 verified direct edge 时，系统必须写“未找到可验证直接客户/供应商边”，不能让 LLM 补。

## V1：扩容数据接入向量数据库

目标：在完成 R1-R5 后，才把扩容数据接入 typed vector / Hybrid retrieval。

原则：

- 不简单扩大 top-k。
- 不把 relationship edge 当普通 narrative chunk。
- 不把新闻线索和 direct edge 混入同一个 vector kind。
- 不用 Milvus 替代 BM25/ObjectBM25/exact-value ledger。

向量类型：

| vector_kind | 来源 | 用途 |
| --- | --- | --- |
| `narrative_chunk` | SEC、全球公开年报、earnings 正文 | 通用语义召回 |
| `table_chunk` | 表格 chunk | 表格上下文 |
| `metric_row` | ObjectBM25 / financial facts | 精确数值和指标 |
| `table_row` | ObjectBM25 table object | 表格精确行 |
| `claim_object` | 结构化 claim | 可摘要叙述 |
| `relationship_context` | 经济传导文本视图 | 行业关系假设 |
| `paraphrase_context` | 口语到财务术语桥接视图 | 转述 query |
| `relationship_edge_direct` | verified direct edge | 真实客户/供应商/合同关系 |
| `relationship_edge_exposure` | sector exposure edge | 经济暴露 / 需求传导 |
| `external_event_lead` | 新闻/网页线索 | 只做线索发现 |

新增 metadata：

```text
source_family
source_tier
vector_kind
vector_role
semantic_scope
intent_tags
relationship_role
edge_id
relation_type
relationship_confidence
verifier_status
entity_resolution_status
as_of_date
```

脚本：

- `scripts/eval_retrieval/eval_milvus_retrieval_ab.py` 继续保留 v0.3 typed schema。
- 新增 `scripts/data_expansion/build_typed_vector_records.py`，统一 evidence、metric、relationship edge、event lead 的向量行构造。
- 新增 `scripts/data_expansion/audit_typed_vector_records.py`，检查各类 vector kind 是否分布合理。

门控：

- relationship case 必须命中 `relationship_edge_direct` 或 `relationship_context`。
- paraphrase case 必须命中 `paraphrase_context`。
- exact lookup case 的 `metric_row/table_row` 命中不得下降。
- external event lead 不允许进入 Memo Writer 高置信结论槽位。
- typed vector 分布异常时停止，例如 relationship edge 全部落入 narrative chunk。

## F1：分层回归和小批 Full-chain

目标：先跑分层门控，再跑 full-chain。

顺序：

1. E1/E2 数据合同测试。
2. R1-R5 关系图谱测试。
3. V1 retrieval-only A/B。
4. S1-S8 agent gate。
5. 小批 full-chain：
   - exact lookup
   - single company
   - sector-depth
   - relationship graph
   - paraphrase
   - multi-turn

通过标准：

- route 成功和 evidence 质量分开统计。
- Specialist 必须看到正确 data view。
- Memo 必须区分事实、行业趋势、市场反应、关系假设和新闻线索。
- Runtime ledger 必须能解释每个 node / agent 为什么激活、看到了什么、输出了什么。

## X1：外部供应链数据源决策

目标：在免费内部关系图谱跑通后，再决定是否接外部供应链数据源。

候选：

- GDELT：新闻线索。
- Common Crawl：官网 customer / partner / newsroom 页面发现。
- ImportYeti：内部实验海运线索。
- FactSet / Bloomberg / Panjiva：商业供应链图谱，需授权。

决策门控：

- 新源能否提高 verified edge 覆盖率。
- 新源是否能提供可引用文本或可审计来源。
- 新源是否允许公开仓库/产品使用。
- 新源是否会把低置信线索混入高置信关系图谱。

## 阶段完成定义

下一阶段不是以“下载了多少数据”完成，而以下列条件完成：

- Tier 1 主证据扩容资产通过 S0。
- 当前 238 家有 verified relationship edge 基线。
- relationship verifier 能阻止 exposure/customer 混淆。
- Relationship Router 和 Industry Specialist 能消费 relationship edge rows。
- typed vector DB 能区分 relationship edge、relationship context、paraphrase context、event lead。
- 代表性 retrieval-only 和 full-chain case 通过门控。
- 文档、脚本、配置、测试和工作日志都能复现执行顺序。
