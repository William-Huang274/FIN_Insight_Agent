# vNext 50-Case Eval Catalog v0.1

日期：2026-06-14

## 目的

本文把 R12 后续评测从“临时挑 case”升级为可长期维护的 50-case catalog。它同时服务四件事：

1. 投研质量评测：覆盖基本面、产品/产线、资本/投融资、行业供应链、竞争位置、风险反证和缺口边界。
2. Agent graph 评测：覆盖 Research Lead、LeadReviewCheckpoint、targeted repair、role-specific selector、Specialist packs、JudgmentState、MemoLogicPlan、Verifier。
3. 后端产品化评测：同一批 case 可以走 Java gateway、Redis queue、Python worker、SSE、cancel/resume、Eval Store、Workbench trace。
4. 压测设计：从 catalog 中抽取 light / medium / heavy / stress 组合，避免压测和质量评测使用两套不可比样本。

机器可读 catalog 已落在：

- `tests/fixtures/fin_agent_vnext_50_case_catalog_v0_1.json`

结构测试：

- `tests/test_vnext_50_case_catalog.py`

## 设计原则

第一版不追求把 50 个 case 全部一次性跑完，而是先把用例边界和评测合同固化。

核心原则：

- 每个 case 必须有行业 schema、focus tickers、search scope、metric families、expected gap types、eval focus 和 backend profile。
- 每个 case 默认启用 vNext 合同：ResearchObjectiveContract、LeadReviewCheckpoint、TargetedRepairPlan、run audit store、eval store、real retrieval、role-visible audit、ClaimCards、JudgmentState、MemoLogicPlan、writer no-new-facts、Workbench trace。
- Deep research case 必须能触发 full-chain 的关键节点，不允许只测写作器。
- Gap/boundary case 的目标不是“补齐”，而是验证系统不会把低强度 proxy 伪装成强证据。
- Backend stress case 不要求产出最深 memo，而要求验证队列、SSE、cancel/resume、checkpoint、trace、eval store 和 artifact parity。

## 分层

| 层级 | 数量 | 作用 |
| --- | ---: | --- |
| L1 basic focused | 10 | 单公司 focused answer / exact-value / 财务科目 / 产品线基础链路 |
| L2 standard memo | 12 | 多公司标准 memo，强调同行比较和行业财务指标 |
| L3 deep research | 12 | R12 successor 主体，覆盖全链路激活 |
| L4 gap boundary | 8 | commercial/bounded/public source boundary gate |
| L5 non-US supply chain | 4 | 非美披露与跨境供应链覆盖 |
| L6 backend runtime stress | 4 | 后端队列、SSE、cancel/resume、replay、eval store、压测 |

## Release Subsets

`r12_successor_12`：

- 12 个 L3 deep research case。
- 用来替代当前 2-case diagnostic probe，验证真正 full-chain 深研能力。

`broader_release_20`：

- 12 个 L3 deep research + 8 个 L4 gap boundary。
- 用来做 release 前更宽口径 gate，尤其检查商业缺口和 proxy 噪声。

`load_mix_15`：

- 10 个 L1 focused + 1 个 L3 AI infra + 4 个 L6 backend stress。
- 用来做 Java gateway / queue / worker / SSE / Eval Store / Workbench trace 级别压测。

`full_catalog_50`：

- 后续作为长期回归集，按成本可切成 nightly / weekly / release gate。

## Case Catalog

| # | Family | Case ID | Focus | 主要评测点 |
| ---: | --- | --- | --- | --- |
| 1 | L1 | `fin_focus_msft_ai_capex_cashflow_001` | MSFT | capex/FCF、Azure、三大表联动 |
| 2 | L1 | `fin_focus_aapl_services_product_margin_002` | AAPL | 产品收入、Services、商业销量缺口 |
| 3 | L1 | `fin_focus_jpm_nii_cet1_deposit_003` | JPM | 银行 NII、存款、CET1、同行口径 |
| 4 | L1 | `fin_focus_xom_cash_capex_production_004` | XOM | 产量、capex、FCF、EIA/FRED 边界 |
| 5 | L1 | `fin_focus_lly_mounjaro_product_revenue_005` | LLY | GLP-1 产品收入、临床/监管、处方缺口 |
| 6 | L1 | `fin_focus_wmt_inventory_gross_margin_006` | WMT | 库存、毛利、POS/scanner 缺口 |
| 7 | L1 | `fin_focus_tsla_auto_margin_delivery_007` | TSLA | 交付、ASP、NHTSA 边界 |
| 8 | L1 | `fin_focus_nflx_subscriber_arpu_008` | NFLX | 用户、ARPU、内容投入、观看数据缺口 |
| 9 | L1 | `fin_focus_duke_load_capex_009` | DUK | utility revenue/volume/capex 口径 |
| 10 | L1 | `fin_focus_crm_subscription_rpo_margin_010` | CRM | SaaS RPO、销售费用、产品 proxy |
| 11 | L2 | `fin_standard_aapl_msft_product_mix_011` | AAPL/MSFT | 产品组合、AI 证据、现金流 |
| 12 | L2 | `fin_standard_jpm_bac_wfc_bank_quality_012` | JPM/BAC/WFC | 银行同行科目比较 |
| 13 | L2 | `fin_standard_wmt_tgt_cost_inventory_013` | WMT/TGT/COST | 零售库存、毛利、商业 sell-through 缺口 |
| 14 | L2 | `fin_standard_tsla_gm_f_ev_profit_014` | TSLA/GM/F | EV 转型、汽车毛利、注册数据边界 |
| 15 | L2 | `fin_standard_xom_cvx_capex_cash_return_015` | XOM/CVX | 能源 capex、现金流、股东回报 |
| 16 | L2 | `fin_standard_nflx_dis_roku_streaming_016` | NFLX/DIS/ROKU | streaming 用户、ARPU、平台 proxy |
| 17 | L2 | `fin_standard_crm_now_ddog_saas_usage_017` | CRM/NOW/DDOG | SaaS 使用量缺口、RPO、销售效率 |
| 18 | L2 | `fin_standard_nee_duk_so_utility_capex_018` | NEE/DUK/SO | utility load、rate base、capex |
| 19 | L2 | `fin_standard_abt_mdt_dhr_medtech_019` | ABT/MDT/DHR | medtech 产品线、regional product revenue 边界 |
| 20 | L2 | `fin_standard_hd_low_housing_demand_020` | HD/LOW | housing demand proxy、ticket/transactions |
| 21 | L2 | `fin_standard_v_ma_adyen_payment_volume_021` | V/MA/ADYEN | 支付量、take rate、份额估计边界 |
| 22 | L2 | `fin_standard_cost_wmt_costco_membership_margin_022` | COST/WMT | 会员模式、毛利、渠道缺口 |
| 23 | L3 | `fin_deep_ai_infra_nvda_dell_capex_023` | NVDA/DELL | AI infra、capex、供应链、产品收入 |
| 24 | L3 | `fin_deep_healthcare_lly_pfe_amgn_regulatory_024` | LLY/PFE/AMGN | pharma 产品/管线、监管、处方缺口 |
| 25 | L3 | `fin_deep_semicap_asml_amat_lrcx_klac_cycle_025` | ASML/AMAT/LRCX/KLAC | 半导体设备订单、出口限制、非美披露 |
| 26 | L3 | `fin_deep_cloud_capex_msft_amzn_googl_supplier_026` | MSFT/AMZN/GOOGL | hyperscaler capex 到供应商传导 |
| 27 | L3 | `fin_deep_power_data_center_vrt_etn_pwr_vst_027` | VRT/ETN/PWR/VST | 数据中心电力需求、订单、资本结构 |
| 28 | L3 | `fin_deep_cyber_crwd_panw_zs_sentinelone_028` | CRWD/PANW/ZS/S | cyber SaaS、产品模块、安全事件 |
| 29 | L3 | `fin_deep_glp1_nvo_lly_pfe_amgn_supply_029` | NVO/LLY/PFE/AMGN | GLP-1 产能、临床、商业 tracker gap |
| 30 | L3 | `fin_deep_auto_ev_tsla_byd_gm_f_supply_030` | TSLA/BYD/GM/F | 全球 EV 产品、交付、注册数据边界 |
| 31 | L3 | `fin_deep_retail_cpg_pg_cl_kmb_pricing_031` | PG/CL/KMB | CPG price/mix、营销费用、POS 缺口 |
| 32 | L3 | `fin_deep_banks_rate_cycle_jpm_bac_c_wfc_032` | JPM/BAC/C/WFC | 利率周期、银行三大表、监管资本 |
| 33 | L3 | `fin_deep_energy_lng_xom_cvx_cop_033` | XOM/CVX/COP | LNG/上游项目、商品价格 proxy |
| 34 | L3 | `fin_deep_ai_software_msft_googl_meta_adoption_034` | MSFT/GOOGL/META | AI 产品商业化、公开使用量 proxy |
| 35 | L4 | `fin_gap_pharma_prescription_iqvia_035` | LLY/NVO | 处方量/销量/份额商业缺口 |
| 36 | L4 | `fin_gap_retail_pos_scanner_circana_036` | PG/WMT/COST | POS/scanner/channel inventory 缺口 |
| 37 | L4 | `fin_gap_auto_registration_sp_mobility_037` | TSLA/GM/F | 注册量/VIO/NHTSA 边界 |
| 38 | L4 | `fin_gap_app_download_sensor_tower_038` | NFLX/SPOT/DUOL | app downloads/revenue proxy 强度 |
| 39 | L4 | `fin_gap_consensus_revision_commercial_039` | MSFT/NVDA/JPM | consensus revision 商业缺口 |
| 40 | L4 | `fin_gap_channel_inventory_semiconductor_tracker_040` | NVDA/AMD/MU | semiconductor channel tracker 缺口 |
| 41 | L4 | `fin_gap_restaurant_traffic_card_panel_041` | MCD/SBUX/CMG | restaurant traffic/card panel 缺口 |
| 42 | L4 | `fin_gap_market_share_idc_counterpoint_042` | AAPL/SSNLF/HPQ/DELL | IDC/Counterpoint/Gartner 边界 |
| 43 | L5 | `fin_nonus_tsm_asml_nvda_supply_043` | TSM/ASML/NVDA | 非美披露、供应链、地缘风险 |
| 44 | L5 | `fin_nonus_samsung_hynix_mu_memory_cycle_044` | Samsung/SK Hynix/MU | HBM/DRAM/NAND、ASP/bit shipment gap |
| 45 | L5 | `fin_nonus_toyota_byd_tsla_ev_045` | Toyota/BYD/TSLA | 非美 auto EV、注册数据边界 |
| 46 | L5 | `fin_nonus_novo_lly_glp1_regulatory_046` | NVO/LLY | 非美 pharma 披露、监管/临床 |
| 47 | L6 | `fin_load_light_focused_20x_047` | mixed | 20 个 light focused queue/SSE 压测 |
| 48 | L6 | `fin_load_deep_research_6x_048` | mixed | 6 个 deep research BGE/LLM/ObjectStore 压测 |
| 49 | L6 | `fin_load_cancel_resume_mixed_049` | mixed | cancel/resume/checkpoint/SSE replay |
| 50 | L6 | `fin_load_replay_trace_eval_store_050` | mixed | Workbench trace / eval store / artifact parity |

## 评测维度

每个 case 至少落到以下维度之一；deep research case 默认要求六维同时出现：

- `fundamentals`：三大表、会计科目、派生指标、同行口径。
- `product_and_production`：产品线、产品规格/参数、segment/product KPI、产能、订单或销量边界。
- `capital_and_financing`：capex、债务、融资、股东回报、所有权/insider/holder。
- `industry_supply_chain`：供应链、行业周期、宏观/官方 proxy。
- `competition_and_market_position`：份额、渠道、用户、竞品，但必须区分公开 proxy 与商业 tracker。
- `risk_and_counterevidence`：反证、监管、召回、地缘、source boundary、commercial gap。

## 后端/压测复用

每个 case 都带 `backend_profile`，默认要求：

- `expected_sse=true`
- `cancel_resume_safe=true`
- `artifact_trace_required=true`
- `sla_target_ms_p95` 按 light/medium/heavy/stress 分层

L6 额外带 `load_scenario`：

- 并发数
- task 数
- cancel/resume 数
- worker pool 目标

后续 R10/R12 压测不再临时写样本，而是从 `load_mix_15` 或 L6 读取。

## 通过门控

Catalog 层通过门控：

- `tests/test_vnext_50_case_catalog.py` 必须通过。
- case 数量固定为 50，ID 不重复，ordinal 为 1-50。
- case family 配额必须是 `10/12/12/8/4/4`。
- `r12_successor_12` 必须全部来自 L3。
- `broader_release_20` 必须是 L3 12 个 + L4 8 个。
- L6 必须具备 `load_multiplex`、`stress` backend profile 和 `load_scenario`。

Runner 层通过门控（下一步）：

- 可以把 catalog 展开成当前 runner 可消费的 JSONL case。
- 可以按 subset 选择 `r12_successor_12`、`broader_release_20`、`load_mix_15`。
- Eval Store 记录 catalog id、case id、subset id、criteria version、code commit、data snapshot id。
- Workbench trace 能从 case result 下钻到 node、retrieval audit、ClaimCards、typed gaps、gate matrix、memo、rendered report。

## 下一步

1. 给 R12 runner 增加 catalog loader 和 subset selector。
2. 把当前 2-case diagnostic probe 映射到 catalog 的 #23/#24，保留旧 fixture 作为 diagnostic-only。
3. 先跑 `r12_successor_12` 的 artifact-reuse / node replay gate，确认不消耗过多 token。
4. 再跑 2-3 个新增 full-chain live case，观察 LeadReview、role-visible retrieval、product/capital selector、MemoLogicPlan 和 Verifier 是否有新瓶颈。
5. 最后再讨论 full50 的 nightly/release 分层和 50-case gold/failure 生命周期。
