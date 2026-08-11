# Fin Agent S1-S8 Agent Quality Case Matrix v0.2

日期：2026-06-01

状态：分层测试执行合同；不替代 `fin_agent_investment_research_quality_framework_v0_1.md`，用于把 S1-S8 每个 agent 的激活、工具、上下游解析、输出质量和成本门控落到具体用例。

## 1. 本轮修复目标

本轮不跑 full-chain 作为首要目标，而是修复并验证四个上游质量问题：

1. 比较型 case 下，Fundamental / Risk Specialist 的 bounded rows 必须按 focus ticker 均衡保留，不能被某一个 ticker 的 ledger rows 挤占。
2. Specialist route artifact 必须持久化 prompt row 的 ticker/source/form/metric 分布，便于判断“模型没看到”还是“看到了但没消费”。
3. Comparative / sector-depth gate 必须区分 route 成功、真实 evidence 可见、ClaimCard 引用质量和下游可用性。
4. Evidence Operator 如果发现某个 ticker 有 primary filing context 但没有对应 exact-value ledger rows，必须记录 `ledger_missing_despite_context`，不能让下游误以为 filing 完全不存在。

## 2. Case 分层矩阵

| Case ID | 行业 / 问题层级 | 目标能力 | 必须激活 | 必须不激活 | 关键工具 / 数据 | 质量门控 |
| --- | --- | --- | --- | --- | --- | --- |
| `ma_msft_capex_lookup` | Tech / exact lookup / L1 | 单指标查询，不扩展 universe | `sec_operator`, `renderer` | Specialist、Universe、Memo | `sec_query_exact_value_ledger` | 数值必须来自 ledger 或明确 source gap；总工具调用 <= 2 |
| `ma_amzn_margin_focused` | Consumer/Tech / focused answer / L2 | 单公司利润率 + 管理层解释 | Lead, SEC, 8-K, Coverage, Memo, Verifier | Universe、Specialists | `sec_search_filings`, 8-K route | 不激活全 specialist；8-K 不能写成审计事实 |
| `ma_nvda_amd_market_standard` | Semiconductor / standard memo / L3 | 两家公司基本面、市场、风险比较 | Fundamental, Market, Risk | Universe、Industry | SEC BM25/ObjectBM25/BGE, ledger, market | Fundamental / Risk 必须看到 NVDA 和 AMD 的 primary rows，或记录 ticker-level source gap |
| `ma_ai_capex_supply_chain_deep` | AI infra / sector-depth / L4 | 产业链传导、relationship、行业、市场、风险 | Universe, SEC, 8-K, Market, Industry, all Specialists | none | relationship graph, SEC, market, industry | Industry 必须看到并引用 relationship evidence；relationship 只能作为 hypothesis |
| `ma_banking_deposit_credit_standard` | Banking / standard memo / L3 | 银行专属指标、信用、存款、市场 | Fundamental, Market, Risk | Industry unless explicit sector-depth | ledger, SEC, 8-K, market | 不能把通用 revenue 当银行核心指标；JPM/BAC primary rows 都要可见 |
| `ma_healthcare_product_cycle_focused` | Healthcare / focused answer / L2 | 产品周期、R&D、监管/支付方风险 | Lead, SEC, 8-K, Coverage, Memo, Verifier | Universe、Specialists unless upgraded to standard/deep | SEC, 8-K | 医疗行业缺外部临床/监管数据时必须记录 data limitation |
| `ma_energy_capex_commodity_standard` | Energy / standard memo / L3 | capex、commodity exposure、cash-flow、market reaction | Fundamental, Industry, Market, Risk | Universe / relationship graph unless cross-entity transmission is requested | SEC, 8-K, market, industry snapshot | commodity/production 外源数据缺口不能被 SEC 文本替代 |
| `ma_utilities_power_load_deep` | Utilities / sector-depth / L4 | AI/data-center power load 传导、公用事业投资 | Universe, Industry, Fundamental, Risk, Market | none | relationship graph, industry, SEC, market | 必须区分 power-load hypothesis 与确认客户/供应合同事实 |
| `ma_run_coverage_inspect` | Run artifact / deterministic / L1 | 已有 run inspect，不重新检索 | Coverage, Renderer | all retrieval/specialists/memo | run artifact summary only | 不触发 SEC / market / industry tool |

## 3. S1-S8 Gate

### S1 Research Lead

- `mode_match=true`。
- required agents 全部激活，forbidden agents 全部不激活。
- 对 `standard_memo` 和 `deep_research` 必须输出 primary/supporting/conditional priority，不能粗暴全员同级。
- 工具预算符合 case 难度；focused answer 不能因为“分析”二字激活 Universe。

### S2 Universe / Relationship

- 只有 relationship / sector-depth / cross-sector transmission case 激活。
- lookup rows、plan relationships、economic link map 均存在。
- 所有 relationship edge 必须有 `inference_level`、`confirmation_status`、`evidence_refs`、`missing_confirmations`。
- `sector_inferred` / `category_inferred` 必须是 `no_confirmed_direct_edge`，不能写成真实客户/供应商事实。

### S3 Evidence Operators / RAG

- expected tools 被实际调用，`sec_search_filings` 触发 BM25/ObjectBM25/BGE rerank。
- CUDA 可用且 `BGE_DEVICE=auto` 时，BGE policy 必须为 `cuda`。
- 比较型 case 记录 context/runtime ledger row distribution：by ticker、source family、form、metric。
- 对每个 focus ticker：如果有 primary context rows 但没有 exact-value ledger rows，记录 `ledger_missing_despite_context`。
- exact lookup / numeric-heavy case 若 runtime ledger 为 0，fail；text-heavy sector-depth case 可 bounded pass，但必须记录 source gap。

### S4 Coverage / Reflection

- source gap 分为 searchable / unsearchable / product-boundary / ledger-context-gap。
- second-pass 只能由 Reflection request 经 compiler 执行；无增益必须中止。
- 不允许把上游数据覆盖不足直接压给 Memo Writer。

### S5 Specialists

- Specialist 是否 route 成功与 real-evidence quality 分开计分。
- route artifact 必须包含 `prompt_row_distribution`，至少包括 `by_ticker`、`by_source_family`、`by_ticker_source_family`。
- Comparative fundamental/risk case 下，每个 focus ticker 必须有可见 primary rows，或有 ticker-level source gap。
- Industry relationship case 下必须看到并引用 relationship rows / relationship_summary。
- ClaimCard 必须有 `claim`、`ticker_scope`、`metric_scope`、`memo_slot`、`materiality`、`direction`、`evidence_refs`、`source_families`、`confidence`。

### S6 Judgment Aggregator

- 支持的 ClaimCard 必须被 rank，unsupported/conflicts 不能进入 memo slots。
- 形成 `memo_thesis_pack` / `memo_thesis_plan`，包含 stance、core thesis、key debate、entity ranking、risk hierarchy、watch items。
- 不引入 Specialist 未提供的新事实。

### S7 Memo Writer

- 只消费 verified thesis plan / selected ClaimCards，不读取 raw rows，不检索。
- 输出必须是自然语言投研 memo，而不是 schema 填空。
- 比较型 case 必须体现 entity ranking 或差异化判断；sector-depth 必须体现 transmission mechanism。
- 不新增 refs、tickers 或 unsupported facts。
- 中文 query 或显式 `response_language=zh-CN` 时，`direct_answer`、`memo_claims.claim`、action fields、caveats、source boundary 必须为中文；ticker、metric id、evidence ref、数字和单位保持原样。
- 中文数值表达必须通过 numeric fidelity：如 `$57.0B` / `570亿美元`、`$14.5-$15.5B` / `145-155亿美元`、`22.1x` / `22.1倍`、`133.5 percentage points` / `133.5个百分点`。

### S8 Verifier / Repair

- Verifier 只做检查和定点 repair instruction，不生成新观点。
- repair 后 failures 必须减少；不能超过预算。
- 对 indirect / hypothesis relationship 误写成 confirmed direct edge 必须 fail。
- 对缺数据导致的 bounded memo，必须保留 data limitation，不强行改写成完整报告。

## 4. 成本与质量门控

| 层 | 预算策略 | 不达标处理 |
| --- | --- | --- |
| S1/S2 | 单 case one-pass 优先；repair > 1 需查 prompt/schema | 不进入下游 |
| S3 | 工具调用按 agent 权限和 case 难度上限 | 重复/无增益中止 |
| S5 | primary specialist 可用完整预算，supporting/conditional 使用窄 payload | 若 tokens 高但 ClaimCard 密度低，先调 selection/prompt，不加 max_tokens |
| S6-S8 | 复用 S5 artifact，禁止上游重跑 | 若 memo 不自然，优先修 thesis projection 与 writer skill |

## 5. 知识库限制记录规则

如果失败来自数据覆盖，而不是 agent 能力，artifact 必须写明：

- `source_gap.reason_code`。
- 影响的 `ticker/year/form/source_family/metric_family`。
- 当前是否有 text context 可替代 exact ledger。
- 是否需要外源数据：consensus、transcripts、news、customer/supplier confirmation、industry regulatory/commodity/provider data。
- 下游允许的处理：bounded answer、watch item、manual follow-up，还是 stop。

## 6. 本轮执行顺序

1. 更新本文件和 worklog。
2. 修 S3/S5 observability 与 ticker-balanced selection。
3. 跑 targeted unit tests。
4. 用既有 S1-S4 artifacts 先跑 `ma_nvda_amd_market_standard` S5，确认 NVDA/AMD primary rows 均可见。
5. 扩展 fixture 后跑 S1-S3/S5/S6-S8 分层 gates；任一层不通过，复用上游 artifact 修该层。
6. 全部通过后再进入 S9/S10 full-chain replay。

## 7. 2026-06-01 Layered Run Results

本轮按“先分层、后 full-chain”的顺序执行，未启动 full-chain replay。

| Layer | Run ID | 范围 | 结果 | 备注 |
| --- | --- | --- | --- | --- |
| S1 Research Lead | `20260601_fin_agent_s1_agent_quality_matrix_v0_2_deepseek_v0_2` | 9 cases | pass 9/9 | activation 精准；Universe 只在 AI infra / utilities deep case 激活；energy commodity 允许 industry context 但不激活 Universe |
| S2 Universe / Relationship | `20260601_fin_agent_s2_agent_quality_matrix_v0_2_deepseek_v0_1` | 2 relationship cases | pass 2/2 | relationship edges 保持 `sector_inferred` / `no_confirmed_direct_edge`，用于研究范围和传导假设，不写成客户/供应商事实 |
| S3 Evidence Operators | `20260601_fin_agent_s3_agent_quality_matrix_v0_2_real_retrieval_v0_1` | 8 retrieval cases | pass 8/8 | SEC search / BM25 / ObjectBM25 / BGE rerank / ledger / market / industry / relationship row gates 通过；记录 row distribution 和 ledger-context gaps |
| S4 Coverage / Reflection | `20260601_fin_agent_s4_agent_quality_matrix_v0_2_v0_1` | 8 cases | pass 8/8 | 3 cases 触发 second-pass，新增 rows 为 0；记录为当前 inventory/source 边界 |
| S5 Specialists | `20260601_fin_agent_s5_temporal_gate_nvda_amd_deepseek_v0_5` | NVDA/AMD comparative | pass 1/1 | Fundamental/Risk prompt 同时覆盖双 ticker、metric diversity 和 temporal-claim gate |
| S5 Specialists | `20260601_fin_agent_s5_agent_quality_matrix_selected_deepseek_v0_2` + targeted energy reruns | banking/utilities/energy selected | selected pass after fixes | 修复 Risk 对 market/industry rows 的消费；energy final run `20260601_fin_agent_s5_energy_risk_industry_prompt_floor_deepseek_v0_5` pass |
| S6-S8 Judgment/Memo/Verifier | `20260601_fin_agent_s6_s8_nvda_amd_deepseek_v0_1` | NVDA/AMD | pass 1/1 | 无 memo repair；Verifier pass |
| S6-S8 Judgment/Memo/Verifier | `20260601_fin_agent_s6_s8_energy_deepseek_v0_1` | energy | pass 1/1 | memo repair 1 次，需后续降成本 |
| S6-S8 Judgment/Memo/Verifier | `20260601_fin_agent_s6_s8_selected_banking_utilities_deepseek_v0_1` | banking/utilities | pass 2/2 | memo repair 2 次，需后续降成本 |
| S6-S8 Memo Profile v0.6 | `20260601_fin_agent_s6_s8_memo_profile_v0_6_nvda_amd_deepseek_v0_4` | semiconductors / comparative standard | pass 1/1 | profile=`expanded`；direct `1126` chars；5 claims；0 repair |
| S6-S8 Memo Profile v0.6 | `20260601_fin_agent_s6_s8_memo_profile_v0_6_energy_deepseek_v0_2` | energy / standard with coverage gaps | pass 1/1 | profile=`expanded`；direct `1186` chars；5 claims；0 repair |
| S6-S8 Memo Profile v0.6 | `20260601_fin_agent_s6_s8_memo_profile_v0_6_banking_deepseek_v0_2` | banking / standard | pass 1/1 | profile=`expanded`；direct `1142` chars；5 claims；0 repair |
| S6-S8 Memo Profile v0.6 | `20260601_fin_agent_s6_s8_memo_profile_v0_6_utilities_deepseek_v0_5` | utilities / sector-depth | pass 1/1 | profile=`deep_research`；direct `1754` chars；8 claims；0 repair |
| S6-S8 Memo Language v0.7 | `20260601_fin_agent_s6_s8_memo_language_v0_7_nvda_amd_deepseek_v0_4` | semiconductors / Chinese comparative standard | pass 1/1 | response_language=`zh-CN`；profile=`expanded`；0 repair |
| S6-S8 Memo Language v0.7 | `20260601_fin_agent_s6_s8_memo_language_v0_7_utilities_deepseek_v0_1` | utilities / Chinese sector-depth | pass 1/1 | response_language=`zh-CN`；profile=`deep_research`；0 repair |
| S6-S8 Memo Language v0.7 | `20260601_fin_agent_s6_s8_memo_language_v0_7_banking_deepseek_v0_1` | banking / Chinese standard | pass 1/1 | response_language=`zh-CN`；profile=`expanded`；0 repair |
| S6-S8 Memo Language v0.7 | `20260601_fin_agent_s6_s8_memo_language_v0_7_energy_deepseek_v0_3` | energy / Chinese standard | pass 1/1 | response_language=`zh-CN`；profile=`expanded`；0 repair |

### Quality Notes

- Specialist 层当前能正确消费上游任务和 bounded evidence：比较型 rows 不再被单 ticker 挤占，Risk 能看到 market/industry rows，Industry 能引用 relationship/industry evidence。
- S6 Aggregator 能把 Specialist ClaimCards 转成 `memo_thesis_pack`，并阻止 unsupported/conflict claim 进入 memo slots。
- S7 Memo Writer v0.6 已从固定 bounded contract 改为 profile-driven contract：`compact` 保留给 focused/evidence-thin case，`expanded` 用于标准投研 memo，`deep_research` 用于 sector-depth case。
- v0.6 新增 direct-answer surface gate：阻断 internal ClaimCard label、pipe-joined claims、重复句；`expanded/deep_research` 要求 `investment_implications`、`what_would_change_view`、`monitoring_items`。
- v0.6 真实 DeepSeek 四个代表 case 均通过，memo repair 为 `0`，最终输出从约 350 字短答提升到 `1126 / 1186 / 1142 / 1754` chars。
- S8 Verifier 能守住不越界、不新增 refs、不读 raw rows；它是安全门，不负责增加深度。

### Data / Coverage Limitations

- Relationship graph 仍主要来自 sector-depth pack 和推断关系，能支持“研究范围/传导假设”，不能证明真实客户、供应商或合同事实。
- 部分 healthcare focused case 按 focused answer 路径不进入 Specialist；若要评测医疗专家能力，需要新增 standard/deep healthcare case。
- Energy case 仍暴露本地数据边界：有 commodity price snapshot 和 CVX filing rows，但 XOM hard financial rows、管理层 commodity outlook、供需/监管外部数据不足；v0.6 能输出 expanded memo，但必须保留 source-gap caveat。
- Healthcare 仍未在 S5-S8 specialist/memo profile 下覆盖；需要新增 healthcare standard/deep case 才能评估医疗产品周期、监管和商业化专题能力。
- v0.6 后 S6-S8 四个代表 case 的 memo repair 降为 `0`，但 token 成本仍需继续按 profile 做预算优化。
