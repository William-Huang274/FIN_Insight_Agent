# K5/K6 Source Adapter And D Hardening

日期：2026-06-13

## 触发

用户明确要求先把 K5/K6 能力做足：把 SEC debt footnote、offering、13F、13D/G、Form 3/4/5、proxy，以及 FRED/EIA/Census/FDIC/ClinicalTrials/openFDA/NHTSA/PatentsView/OpenAlex 等公开源按正确边界接入，之后再补 D3/D4/D5/D11，最后再跑 K8 真实 case。

## 决策

本轮不降低 gate，不把公开 proxy 兜成公司结论。K5/K6 的目标是把可得 raw/materialized rows 变成 gated pack inputs；raw material 不存在或绑定不足时只暴露缺口。

## 已完成

- 新增 `CapitalMacroSourceAdapter v0.1`：
  - SEC 10-K/10-Q annual chunks 扫描 debt / credit candidate，并用 local relation gate 解析 `DebtInstrument` / `CreditFacility`。
  - Debt 只接受局部窗口内 `issued + principal amount + coupon + maturity`；过滤发行价百分比和跨句混拼。
  - Credit facility 只接受 `provides/access/commitment/credit facility/term loan` 近邻金额；排除 available-under / outstanding 口径混入 facility size。
  - SEC 13F bulk zip 映射为 lagged `OwnershipPosition`，保留 report period、filing date、lag days、not realtime policy。
  - SEC FSD zip 映射为 `CapitalStructure`，同时标记 FSD 无法提供 maturity/coupon/rate 的 source gap。
  - FRED/EIA/Census/FDIC/ClinicalTrials/openFDA/NHTSA/PatentsView/OpenAlex 等公开源按 source family 映射为 `MacroDriver`、`CompanyExposureToDriver`、`VerticalOfficialObject` 或 source gap；宏观/垂直对象保持 context-only。
- 新增 backfill CLI：
  - `scripts/data_expansion/build_capital_macro_source_adapters.py`
  - 默认输出在 `Z:/FIN_Insight_Agent_data/processed_private/capital_macro_source_adapters/capital_macro_source_adapter_v0_1/`
  - repo 内只保留小型 manifest：`data/manifests/capital_macro_source_adapter_summary_v0_1.json`
- D3/D4/D5/D11 hardening slice：
  - D3 Entity Master 纳入 capital/macro pack 的 `company_id`，并把 13F manager / insider 等非公司实体作为 unresolved context entity 暴露。
  - D4 Raw Source / Provenance Store flatten `capital_macro_source_adapter` 与 `capital_macro_pack`，并为 capital/macro rows 生成 evidence-ref 级稳定 source id，避免 DB primary key 覆盖。
  - D5 As-of / Vintage Layer 接入 13F report period、SEC filing date、macro observation date / vintage、official object observed_at。
  - D11 Analyst View 增加 `capital_macro_context_view`，只索引 gated pack object ids，不携带 raw source refs。
  - D-series SQLite materialization / reader parity 增加 K5/K6 integration test。

## 真实 backfill 结果

- Target companies：`603`
- SEC capital text candidates：`13,883`
- Pack validation：`pass`
- Pack summary：
  - `CapitalStructure`: `386`
  - `DebtInstrument`: `855`
  - `CreditFacility`: `1,715`
  - `OwnershipPosition`: `5,000`
  - `MacroDriver`: `155`
  - `CompanyExposureToDriver`: `2,525`
  - `VerticalOfficialObject`: `1,979`
  - `EquityOffering`: `0`
  - `InsiderTransaction`: `0`
- Known source-family gaps：
  - `sec_offering_forms_s1_s3_424b_8k_exhibits`: parser gate exists, but no configured local S-1/S-3/424B/8-K exhibit source text or structured offering rows were found.
  - `sec_form_3_4_5_insider_transactions`: parser gate exists, but no configured local Form 3/4/5 XML or structured insider transaction rows were found.

## 通过条件与验证

- K5/K6 不允许 weak proxy promotion：通过。
- 13F 必须 lagged/context-only：通过。
- Macro/vertical official objects 不得直连公司收入、销量、份额结论：通过。
- D3/D4/D5/D11 SQLite parity：通过。
- Targeted regression：
  - `pytest tests/test_capital_macro_source_adapters.py tests/test_capital_macro_pack.py tests/test_capital_macro_d_series_integration.py tests/test_d_series_database_store.py tests/test_d_series_database_closeout.py tests/test_kg_matrix_registry.py tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_specialist_llm.py -q`
  - 结果：`97 passed`
- `git diff --check`：pass

## 剩余边界

- K8 真实 10-20 case 暂未跑，按用户要求等 K5/K6 与 D hardening 稳定后再跑。
- Offering / insider / 13D/G / proxy ownership 需要后续物化真实 SEC source text/XML/structured rows；当前不能从 10-K 普通描述或新闻/宏观 proxy 兜底。
- D3 true cross-run resolver、D4 object-store provenance / before-after diff、D5 full vintage-history stores、D11 vector/graph memory parity 仍是后续完整 DB hardening，不在本轮冒充完成。
