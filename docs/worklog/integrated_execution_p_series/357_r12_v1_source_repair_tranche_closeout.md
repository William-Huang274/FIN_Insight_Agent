# R12 V1 Source Repair Tranche Closeout

## Prompt / Problem

继续推进 16 文档规划，把 V1 Semiconductors / AI Infrastructure source closeout 中剩余的 source gaps 修完或显式暴露，不能用弱 fallback 隐藏缺口。

## Decision

按 root-cause 修复，不把公开 proxy 提权为商业 tracker 或公司 exact facts：

- `public_order_proxy` / `supply_chain_official_relationship` 的根因是 USAspending probes 只覆盖 secondary/adjacent tickers，未覆盖 V1 primary tickers。
- `hiring_capacity_proxy` 的根因是 ATS builder 只支持 Greenhouse/Lever，V1 主公司常用 Workday。
- `technology_research_proxy` 的根因是 OpenAlex/PatentsView 只有泛化 projection，缺少 issuer/topic 双绑定 rows。
- `trusted_external_context` 的根因是行业协会 L2 页面未进入 parser-backed runtime rows。
- `macro_official_context` 的根因是 FRED/EIA driver rows 没有显式 company/lane exposure bridge，不能直接贴给公司。

## Work Completed

- 扩展 `scripts/data_expansion/build_public_contract_award_context_rows.py`：
  - 新增 DELL、HPE、NVDA、INTC、AMD、QCOM USAspending probes；
  - 真实重建 `public_contract_award_context_rows_v0_1.jsonl`，得到 `34` 条 rows / `12` tickers。
- 扩展 `scripts/data_expansion/build_hiring_capacity_context_rows.py`：
  - 新增 Workday CXS provider；
  - 接入 NVDA / HPE 官方 Workday jobs，真实重建 `hiring_capacity_context_rows_v0_1.jsonl`，得到 `55` 条 rows / `11` tickers。
- 新增 `scripts/data_expansion/build_v1_openalex_technology_research_context_rows.py`：
  - 对 NVDA、AMD、QCOM、ASML、TSM 运行 OpenAlex works search；
  - 只有 issuer term 和 technology topic 同时出现在快照中才 materialize；
  - 生成 `13` 条 L3 research/IP proxy rows。
- 扩展 `src/sec_agent/public_web_context_parser.py` 并新增 `scripts/data_expansion/build_v1_trusted_external_context_rows.py`：
  - 支持 `industry_association_dataset` 解析；
  - 真实抓取 SIA / SEMI 官方页面，生成 `30` 条 L2 trusted industry context rows；
  - ticker 仅为 `v1_lane_context_routed_to_representative_ticker`，不是 issuer-specific fact。
- 新增 `scripts/data_expansion/build_v1_macro_official_exposure_context_rows.py`：
  - 从 `public_official_api_context_rows_v0_1.jsonl` 中选择 FRED/EIA 最新 macro driver rows；
  - 生成 `16` 条 `v1_company_exposure_to_macro_driver_bridge` rows；
  - 明确不支持 issuer revenue / sales / shipment / share / margin claims。
- 更新 `scripts/data_expansion/build_v1_source_coverage_closeout.py` observed paths，纳入 V1 OpenAlex / trusted external / macro exposure rows。

## Result / Evidence

- V1 source closeout:
  - `status=pass`
  - `requirement_count=10`
  - `pass_requirement_count=10`
  - `source_gap_requirement_count=0`
  - `observed_runtime_row_count=475`
  - `commercial_gap_count=15`
- 生成 / 更新：
  - `data/manifests/v1_semiconductors_ai_infrastructure_source_closeout_v0_1.json`
  - `docs/internal/vnext_20260610/vertical_lanes/v1_source_coverage_closeout.zh-CN.md`
  - `data/manifests/v1_openalex_technology_research_context_rows_v0_1.jsonl`
  - `data/manifests/v1_trusted_external_context_rows_v0_1.jsonl`
  - `data/manifests/v1_macro_official_exposure_context_rows_v0_1.jsonl`

## Tests / Gates

- `python -m pytest tests/test_public_contract_award_context_rows.py -q` -> `4 passed`
- `python -m pytest tests/test_hiring_capacity_context_rows.py -q` -> `5 passed`
- `python -m pytest tests/test_v1_openalex_technology_research_context_rows.py tests/test_v1_source_coverage_closeout.py -q` -> `4 passed`
- `python -m pytest tests/test_v1_trusted_external_context_rows.py tests/test_source_coverage_gate.py -q` -> `9 passed`
- `python -m pytest tests/test_v1_macro_official_exposure_context_rows.py -q` -> `2 passed`
- `python scripts/data_expansion/build_v1_source_coverage_closeout.py` -> `10/10` requirement pass

## Boundaries / Follow-up

- `15` commercial gaps remain. They are not public-source source gaps and must stay exposed unless licensed tracker / channel / consensus data is added.
- V1 lane now has enough public-source runtime coverage for source-layer representative cases, but this does not prove full report quality. Next gates should test role-specific selector visibility and then R12 successor cases on the latest V1 source baseline.
