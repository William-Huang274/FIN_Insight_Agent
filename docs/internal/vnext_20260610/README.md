# 2026-06-10 vNext 规划吸收

## 状态

- 状态：内部规划已吸收，运行时代码未改动。
- 当前优先级：先完成公开/免费数据源覆盖检查，再决定 Agent Graph 和 Skill 的升级顺序。
- 付费策略：当前阶段不采购商业 API；商业数据源只记录为缺口或延后项。

## 用户决策

1. 先把外部 10 份规划文档吸收到现有系统，落成内部文档。
2. 先做数据源覆盖检查，明确公开可得 API 能提供哪些数据。
3. 在数据覆盖边界明确后，再考虑下一步 Agent Graph 和 Skill 升级。

## 内部文档

- [源文件清单与吸收映射](source_package_manifest.zh-CN.md)
- [P33 P32 Closeout -> AI/Semis Gold Workpaper Execution Program](p33_p32_closeout_to_ai_semis_gold_workpaper_program.zh-CN.md)
- [P33-1.1 Enterprise RAG / Data Pipeline Fixture Report](p33_enterprise_rag_data_pipeline_fixture_report.zh-CN.md)
- [P33-1.2 Sandbox / Resource Scheduler Fixture Report](p33_sandbox_resource_scheduler_fixture_report.zh-CN.md)
- [P33-1.3 Capital Market Feedback Fixture Report](p33_capital_market_feedback_fixture_report.zh-CN.md)
- [P33-1.4 Workbench Artifact Review Surface Fixture Report](p33_workbench_artifact_review_surface_fixture_report.zh-CN.md)
- [P33-1.5 Research-to-Quant Factor Handoff Fixture Report](p33_research_to_quant_factor_handoff_fixture_report.zh-CN.md)
- [P33-2 Runtime Assimilation Fixture Report](p33_runtime_assimilation_fixture_report.zh-CN.md)
- [P33-3 AI/Semis Gold Workpaper Preflight Report](p33_ai_semis_gold_workpaper_preflight_report.zh-CN.md)
- [P34 Lane Quality-First Source Runtime Program](p34_lane_quality_first_source_runtime_program.zh-CN.md)
- [P34 AI/Semis Quality Artifacts v0.1](p34_ai_semis_quality_artifacts_v0_1.zh-CN.md)
- [P34 AI/Semis Source Route Plan v0.1](p34_ai_semis_source_route_plan_v0_1.zh-CN.md)
- [P34 AI/Semis Adapter Fixture Report v0.1](p34_ai_semis_adapter_fixture_report_v0_1.zh-CN.md)
- [P34 AI/Semis Live Route Attempt Report v0.1](p34_ai_semis_live_route_attempt_report_v0_1.zh-CN.md)
- [P34 AI/Semis No-paid Quality Audit v0.1](p34_ai_semis_no_paid_quality_audit_v0_1.zh-CN.md)
- [P34 Fact-table Projection Preview v0.1](p34_fact_table_projection_preview_v0_1.zh-CN.md)
- [P34 AI/Semis Goldcase 与当前 RAG/Route 可得性对齐 v0.1](p34_ai_semis_goldcase_rag_availability_alignment_v0_1.zh-CN.md)
- [P35 AI Infra Supervisor Dogfood Framework](p35_ai_infra_supervisor_dogfood_framework.zh-CN.md)
- [P35 AI Infra Supervisor Dogfood Report](p35_ai_infra_supervisor_dogfood_report.zh-CN.md)
- [P36 Codex-as-Paid-Model Manual Full-Chain Dogfood Execution](p36_codex_as_paid_model_manual_full_chain_dogfood_execution.zh-CN.md)
- [P36 Node 01 Research Lead Manual Run](p36_node_01_research_lead_manual_run.zh-CN.md)
- [P36 Node 02 Retrieval / RAG / SQL / Source Route Manual Run](p36_node_02_retrieval_rag_sql_source_route_manual_run.zh-CN.md)
- [P36 Node 03 Parser / Evidence Operator Manual Run](p36_node_03_parser_evidence_operator_manual_run.zh-CN.md)
- [P36 Node 04 Graph / Relationship / Value-Capture Manual Run](p36_node_04_graph_relationship_value_capture_manual_run.zh-CN.md)
- [P36 Node 05 Fundamental Specialist Manual Run](p36_node_05_fundamental_specialist_manual_run.zh-CN.md)
- [P36 Node 06 Product / Industry Specialist Manual Run](p36_node_06_industry_product_specialist_manual_run.zh-CN.md)
- [P36 Node 07 Market / Capital / Price-in Specialist Manual Run](p36_node_07_market_capital_price_in_specialist_manual_run.zh-CN.md)
- [P36 Node 08 Risk / Counterevidence Specialist Manual Run](p36_node_08_risk_counterevidence_specialist_manual_run.zh-CN.md)
- [P36 Node 09 Aggregate / Judgment Planner Manual Run](p36_node_09_aggregate_judgment_planner_manual_run.zh-CN.md)
- [P36 Node 10 Writer / Report Generation Manual Run](p36_node_10_writer_report_generation_manual_run.zh-CN.md)
- [P36 Node 11 Verifier / Workbench Review Manual Run](p36_node_11_verifier_workbench_review_manual_run.zh-CN.md)
- [P36 AI Infra Manual Writer Research Report](p36_ai_infra_manual_writer_research_report.zh-CN.md)
- [P36 Codex-as-Paid-Model Dogfood Recap Report](p36_codex_as_paid_model_dogfood_recap_report.zh-CN.md)
- [Skill / Playbook / Eval Gate 内部合同](skill_playbook_eval_contract.zh-CN.md)
- [Agent Graph vNext 内部合同](agent_graph_contract.zh-CN.md)
- [公开/免费数据源覆盖审计](public_data_source_coverage_audit.zh-CN.md)
- 机器可读覆盖 registry 草案：`configs/data_sources/public_source_coverage_v0_1.yaml`
- 公开源信息强度与 no-commercial 研报上限：`configs/data_sources/public_source_information_strength_v0_1.yaml`、[报告](no_commercial_public_source_research_ceiling.zh-CN.md)
- 公开源 S5-S0 物化状态：`data/manifests/public_source_strength_materialization_matrix_v0_1.jsonl`、`data/manifests/public_source_strength_materialization_summary_v0_1.json`、[报告](public_source_strength_materialization.zh-CN.md)
- P0-P3 接入脚本：
  - `scripts/data_expansion/build_public_source_access_plan.py`
  - `scripts/data_expansion/probe_public_source_access.py`
  - `scripts/data_expansion/download_public_source_normalized_snapshots.py`
  - `scripts/data_expansion/audit_public_source_full_availability.py`
  - `scripts/data_expansion/build_public_source_mapping_endpoint_gates.py`
  - `scripts/data_expansion/build_public_source_inventory_adapter.py`
  - `scripts/data_expansion/build_public_source_information_strength_report.py`
  - `scripts/data_expansion/build_public_source_strength_materialization_report.py`
  - `scripts/data_expansion/download_non_us_portal_public_disclosures.py`
  - `scripts/data_expansion/build_non_us_supply_chain_disclosure_coverage_summary.py`
- P0-P3 接入产物：
  - `data/manifests/public_source_access_plan_v0_1.jsonl`
  - `data/manifests/public_source_access_plan_summary_v0_1.json`
  - `data/manifests/public_source_access_probe_v0_1.jsonl`
  - `data/manifests/public_source_access_probe_summary_v0_1.json`
  - `data/manifests/public_source_access_probe_p2_v0_1.jsonl`
  - `data/manifests/public_source_access_probe_p2_summary_v0_1.json`
  - `data/manifests/public_source_access_probe_optional_keys_v0_1.jsonl`
  - `data/manifests/public_source_access_probe_optional_keys_summary_v0_1.json`
  - `data/manifests/public_source_normalized_snapshot_summary_v0_1.json`
  - `data/manifests/public_source_full_availability_audit_v0_1.jsonl`
  - `data/manifests/public_source_full_availability_audit_summary_v0_1.json`
  - `data/manifests/public_source_mapping_endpoint_gate_v0_1.jsonl`
  - `data/manifests/public_source_mapping_endpoint_gate_summary_v0_1.json`
  - `data/manifests/public_source_inventory_adapter_v0_1.jsonl`
  - `data/manifests/public_source_inventory_adapter_summary_v0_1.json`
  - `data/manifests/public_source_information_strength_matrix_v0_1.jsonl`
  - `data/manifests/public_source_information_strength_summary_v0_1.json`
  - `data/manifests/public_source_strength_materialization_matrix_v0_1.jsonl`
  - `data/manifests/public_source_strength_materialization_summary_v0_1.json`
  - `data/manifests/public_source_portal_validation_tasks_v0_1.jsonl`
  - `data/manifests/tier2_global_public_disclosure_kr_dart_download_clean_v0_1.jsonl`
  - `data/manifests/tier2_global_public_disclosure_kr_dart_download_clean_summary_v0_1.json`
  - `data/manifests/tier2_global_public_disclosure_eu_ifx_download_clean_v0_1.jsonl`
  - `data/manifests/tier2_global_public_disclosure_eu_ifx_download_clean_summary_v0_1.json`
  - `data/manifests/tier2_global_public_disclosure_tw_mops_portal_download_clean_v0_1.jsonl`
  - `data/manifests/tier2_global_public_disclosure_tw_mops_portal_download_clean_summary_v0_1.json`
  - `data/manifests/tier2_global_public_disclosure_hkex_cninfo_portal_download_clean_v0_1.jsonl`
  - `data/manifests/tier2_global_public_disclosure_hkex_cninfo_portal_download_clean_summary_v0_1.json`
  - `data/manifests/tier2_global_public_disclosure_jp_company_ir_fallback_download_clean_v0_1.jsonl`
  - `data/manifests/tier2_global_public_disclosure_jp_company_ir_fallback_download_clean_summary_v0_1.json`
  - `data/manifests/non_us_supply_chain_primary_disclosure_coverage_v0_1.jsonl`
  - `data/manifests/non_us_supply_chain_primary_disclosure_coverage_summary_v0_1.json`

## 与当前系统的关系

这些文档只定义下一阶段方向，不改变当前已验证链路：

- 当前 SEC / 8-K / CompanyFacts / market snapshot / industry context / relationship evidence 的既有边界保持不变。
- 当前多智能体 ClaimCard、Memo Writer、Verifier 和 S1-S8/A1-A5 gate 结果仍以现有 `docs/eval/` 与 `docs/worklog/` 为准。
- 新增 Hypothesis Builder、Product/Technology Specialist、Investment/Ownership Specialist、Thesis Adjudicator、Bounded Gap Register 等节点前，必须先让 source registry 通过 collector/parser/gate 级审计，而不是只停留在 prompt 规划。

## 首轮结论

- 公开来源足以支撑下一阶段的“公司主披露 + SEC 结构化事实 + 宏观/行业上下文 + 医疗/专利/实体解析 + 新闻线索”扩容。
- 免费来源不足以可靠替代 sell-side consensus、实时估值数据库、付费供应链数据库、海关明细商业库或公司级消费交易数据。
- 因此下一阶段应优先建设 source registry、公开 API collector、parser/normalizer 和 source-gap gate；不要先扩 prompt 或增加 Graph 节点。
- 2026-06-11 P1 live probe 已扩展为 10 个无 key/低限额来源可达；P2 已配置并验证 `BEA_API_KEY`、`CENSUS_API_KEY`、`DART_API_KEY`、`EIA_API_KEY`、`FRED_API_KEY`。`EDINET_API_KEY` 已写入本地 ignored `.env`，但 EDINET v2 official smoke 返回 `401`，因此 JP EDINET 官方源仍 blocked。
- 2026-06-11 normalized collector smoke 已验证 13 个公开源，生成 `118` 条 normalized records 和 `13` 条 evidence rows；宏观/行业线为 context-only，实体/产品/披露线仅支持 identifier、regulatory/product status 或 disclosure metadata，仍不能替代公司披露的产品销量/收入事实。
- 2026-06-11 full availability audit 覆盖 32 个 source plan rows，其中 15 个 live audited、0 个 live errors；当前只有 `fred_api`、`bls_public_api`、`bea_data_api`、`sec_edgar_apis`、`openfigi_api` 可作为 feature-flag/source-boundary gate 后的候选，其余仍需 entity/product mapping、endpoint allowlist、parser、credential 或 commercial-deferred gate。
- 2026-06-11 mapping / endpoint gates 已按 603 家 target universe 下载和处理目标范围数据：`127,712` endpoint records、`1,219` mapping candidates、`213` source gaps。SEC/OpenFIGI/Census 可进入后续 adapter 设计；EIA/DART/FDIC/GLEIF/ClinicalTrials/openFDA/NHTSA 仍需 resolver confidence、alias overrides、document parser 或 source-boundary adapter。
- 2026-06-11 promotion policy / inventory adapter 已把 mapping/endpoint gate 产物收敛为 `1,103` promoted inventory rows、`220` gap rows 和 `127,828` rejected candidates；当前只允许 feature-flagged source inventory / resolver / Census context-only，不提升 primary disclosure text、exact-value authority 或 company product sales facts。
- 2026-06-11 信息强度矩阵已覆盖 `32` 个公开源，validation `0` errors / `0` warnings；当前 no-commercial 已验证上限是 US filing fundamentals 高、macro/industry context 中、consensus/目标价/实时估值/未披露产品 KPI/商业供应链交易数据低或不可替代。公开源 buildout 后，disclosed company facts 可到高质量，context/regulatory 可到中高质量。
- 2026-06-11 非美供应链主披露补下载已落地 DART、EU/company IR、MOPS、HKEX、CNINFO 和 JP company IR fallback：`47/69` plan rows downloaded/cleaned，覆盖 `12/15` companies、`38` unique documents、`24,114,298` cleaned text chars。剩余 `22` rows / `5` companies 均为 JP EDINET profile 缺口；官方 `jp_edinet_api` 仍 `30/30` rows blocked，因为 fallback 不计入官方源完成度。
- 2026-06-11 S5-S0 物化矩阵已刷新为严格“公开可得都物化”口径：`32` 个公开源中 `30` 个已有 normalized snapshot、cleaned text、bulk zip、candidate table、resolver/inventory 或既有 SEC core 物化；剩余仅 `jp_edinet_api` 官方 API 和 `commercial_market_data_and_consensus`。SEC FSD `4,522,052` bulk rows、13F `3,877,007` bulk rows、normalized snapshot `404` records、extended materialization `8,399,362` records、非美 cleaned text `24,114,298` chars 已纳入矩阵。SEC FSD/FRED API 后续作为结构化首选路径，文档抽取仅保留 citation/fallback/parity 角色。
- 2026-06-11 产品证据方向已从“继续爬官网”改为 `product_evidence_strategy`：SEC/global filings 是产品 taxonomy 和 company-disclosed KPI 的 anchor，官网/产品页只做 enrichment，public proxy 只做方向性验证，commercial tracker 在 no-commercial 策略下 blocked。真实 filings-first 扫描 `192,055` chunks / `577` tickers，生成 `13,712` product taxonomy candidates、`6,663` balanced product KPI candidates 和 `67` 行行业外部验证源计划；所有候选仍需 review/parser gate，不能直接作为产品财务事实。
- 2026-06-11 已落地产品 taxonomy normalization 与 table-aware KPI parser：正式产物写入 `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/`。最新严格 normalization 生成 `5,590` normalized product nodes、`10,817` alias rows、`2,895` review rows；structured MetricObject SQLite FTS + chunk source hydration 扫描 `488,975` structured rows，promote `6,161` structured parser-verified facts / `6,162` combined facts，覆盖 `179` tickers。direct chunk scan 仍保持 `not_promoted_to_runtime`；NVDA/MSFT 等缺口需要 taxonomy/table-header 回补，物理量单位需要表头单位增强。
