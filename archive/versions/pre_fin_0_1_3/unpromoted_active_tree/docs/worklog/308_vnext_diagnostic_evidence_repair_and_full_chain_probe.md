# 308 vNext Diagnostic Evidence Repair And Full-Chain Probe

Date: 2026-06-13

## Context

用户复盘 2 个 full-chain diagnostic case 后指出：AI infrastructure case 的 DELL 8-K 数据截断/不可读、产品与产线 section 近乎空白，投融资 section 信息密度不足；同时怀疑问题不只在 Memo Writer，可能包括上游任务理解、检索、联网/公开数据调用和 ClaimCard 选择。目标是在不降低图一方向、不用弱 proxy 兜底的前提下，先修数据和门控，再用 2 个重新设计的 full-chain diagnostic case 验证。

## Implemented

- 修复 DELL 产品证据进入 runtime ledger。
  - `query_contract.focus_tickers` 和 case companies 即使未出现在 decomposed task binding 中，也会进入 scoped ledger query。
  - DELL `AI-optimized servers`、`Traditional servers and networking`、`Storage`、`Total ISG net revenue` 等 8-K 行规范化为 `product_revenue`，并允许 product line label 作为高置信产品收入信号。
  - 去除 product revenue percent/RPO/corporate debt/gross-margin 噪声，避免把非产品收入或非 backlog 行提升为产品事实。

- 修复 pre-memo fact 到 ClaimCard / memo surface 的丢失问题。
  - `pre_memo_fact_selector` 生成 deterministic ClaimCard 时按维度保底：`product_and_production`、`capital_and_financing`、`fundamentals` 都能进入 judgment plan，不再被 capex/revenue 数字挤掉。
  - Memo Writer 的 supported claim selection 保留关键维度 claim，避免产品事实被基本面和资本开支 facts 挤出 prompt。
  - 产品 facts 使用 `memo_slot=product_technology`、`analysis_dimension=product_and_production`，和 Product / Technology Specialist 的 slot 合同对齐。

- 修复 memo surface / verifier 的质量门。
  - 去掉 deterministic salvage action item 中的通用模板句，改为按维度、ticker、metric 生成行动项。
  - numeric parser 支持 `usd_millions` / `usd_billions` / `usd_thousands` 与中文“亿美元”等单位转换，避免 DELL `29009 usd_millions` 被误判为 memo 中 `290.09 亿美元` 的数值漂移。
  - 收紧 diagnostic scoring：`required_deterministic_claim_dimensions` 只认 pre-memo deterministic ClaimCard；`required_product_fact_terms` 必须出现在 supported claim 或 memo surface 中，不能只藏在 approved facts 里。

- 新增 2-case vNext diagnostic probe fixture 和 Workbench runner。
  - AI infrastructure / DELL product-capex case：验证 DELL 产品收入、AI server product fact、MSFT/AMZN/GOOGL capex 需求背景、供应链关系边界和竞争/商业 tracker gap。
  - Healthcare product / regulatory gap case：验证 LLY/AMGN/BMY/VRTX 产品/临床/监管公开证据边界、医药商业 tracker gap 和资本融资缺口暴露。

## Full-Chain Results

Workbench backend runs:

- `20260613_vnext_diagnostic_probe_r5`
  - Result: `0/2 pass`
  - Root cause: deterministic salvage 输出仍含通用模板句，被 `analyst_depth_generic_template_language` 拦截。

- `20260613_vnext_diagnostic_probe_r6`
  - Result: `2/2 pass`
  - Audit finding: gate 形式通过，但 AI infrastructure memo 的 `product_and_production` 仍是 gap-only section；approved facts 里有 DELL 产品收入，未晋升为 product ClaimCard。这一轮判定为不可接受的误通过。

- `20260613_vnext_diagnostic_probe_r7`
  - Result: `2/2 pass`
  - Summary path: `reports/quality/workbench_eval/20260613_vnext_diagnostic_probe_r7_agent_graph_vnext_diagnostic_probe.json`
  - Source summary: `eval/sec_cases/outputs/multi_agent_vnext_diagnostic_probe_eval/20260613_vnext_diagnostic_probe_r7/real_chain_eval_summary.json`

R7 case-level checks:

- `fin_diag_ai_infra_dell_product_capex_zh`
  - Gate: pass
  - Diagnostic checks all pass: required approved metrics, deterministic dimensions, product terms, numeric sanity, no internal synthesis dimension, capital-financing signal.
  - Product deterministic ClaimCards now include:
    - DELL `Total ISG net revenue` = `29009.0 usd_millions`
    - DELL `Traditional servers and networking` = `8543.0 usd_millions`
    - DELL `AI-optimized servers` = `16132.0 usd_millions`
  - Capital deterministic ClaimCards include AMZN、ANET、DELL、GOOGL、MSFT、VRT capex rows.
  - Memo product section is supported, not blank.

- `fin_diag_healthcare_product_regulatory_gap_zh`
  - Gate: pass
  - Product deterministic ClaimCards include BMY product revenue and VRTX product revenue; LLY product/pipeline specifics remain bounded by public disclosure gap.
  - Capital/financing remains gap-only because no case-relevant verified capex/debt/offering/cash-flow fact was available under the current public evidence boundary.

## Verification

- `pytest tests/test_d_series_fact_selection.py::test_pre_memo_fact_selection_keeps_product_claim_when_financial_facts_crowd_budget tests/test_d_series_fact_selection.py::test_pre_memo_fact_selection_adds_deterministic_claim_cards_for_approved_financial_facts tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_diagnostic_quality_accepts_product_and_capex_facts tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_diagnostic_quality_rejects_product_fact_not_promoted_to_claim -q`
  - Result: `4 passed`

- `pytest tests/test_d_series_fact_selection.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_contracts.py tests/test_sec_agent_ledger_store.py tests/test_cloud_interactive_ledger_rules.py tests/test_metric_product_ontology_reconciliation.py tests/test_workbench_job_runner.py tests/test_workbench_backend.py tests/test_multi_agent_specialist_llm.py -q`
  - Result: `227 passed`

## Boundary And Follow-Up

- 本轮不把 approved facts 里存在但未进入 ClaimCard/memo 的数据视为可用研报证据；必须通过 ClaimCard 和 memo dimension surface。
- AI infrastructure 的 DELL 产品事实已经可用，但 NVDA-DELL 实际采购/attach rate、ANET/VRT 真实 AI 订单、电力设备份额、竞品 AI server share 仍缺商业或公司级强证据。
- Healthcare case 中处方量、销量、渠道库存、具体产品市占率仍需要 IQVIA/Symphony 等商业 tracker；当前只能暴露为 bounded gap。
- Generated Workbench outputs、eval outputs、private SQLite/log artifacts 不进入 git。
