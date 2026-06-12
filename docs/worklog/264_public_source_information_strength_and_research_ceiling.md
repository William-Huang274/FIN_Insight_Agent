# 264 公开数据源信息强度与 no-commercial 研报上限

## Prompt

用户要求先把公开可得数据源全部搞清楚，按信息强度确定接入方式，在不使用商业 API 的前提下先判断 agent 研报质量上限，再考虑 agent graph / skill 如何使用这些信息和边界。

## Decision

本轮不继续把公开源接进 runtime。先把 source strength 和 engineering readiness 分开：

- source strength：数据本身能证明什么。
- readiness：当前 collector / parser / mapping / adapter 是否足够进入 runtime。

这样可以避免两类错误：

- 官方强源因为 parser 未完成而被过早引用。
- 公开弱源因为 prompt 需要而被改写成公司事实。

## Work Completed

- 新增 `configs/data_sources/public_source_information_strength_v0_1.yaml`。
- 新增 `scripts/data_expansion/build_public_source_information_strength_report.py`。
- 新增 `tests/test_public_source_information_strength_report.py`。
- 生成 tracked artifacts：
  - `data/manifests/public_source_information_strength_matrix_v0_1.jsonl`
  - `data/manifests/public_source_information_strength_summary_v0_1.json`
  - `docs/internal/vnext_20260610/no_commercial_public_source_research_ceiling.zh-CN.md`
- 更新 `docs/internal/vnext_20260610/README.md`、`docs/worklog/README.md` 和 master checklist。

## Strength Tiers

- `S5_primary_authority`：公司或监管主披露，可支持公司级事实，但必须通过 parser/citation/period/unit/source-boundary gate。
- `S4_company_authored_operating_context`：公司官方产品页、运营披露或产品状态，可支持产品存在、定位和公司披露指标；不能推断销售或采用。
- `S3_official_regulatory_product_context`：官方监管、产品、ownership 或 entity context，可支持状态/登记/滞后申报事实；不能证明商业采用、销售或因果。
- `S2_official_macro_industry_context`：官方宏观、行业、贸易或 public usage context，只能做上下文和 demand proxy。
- `S1_resolver_or_lead`：resolver、discovery、technology signal 或 event lead，不是 claim evidence。
- `S0_deferred_or_unofficial`：商业延后、非官方或 discovery-only，在当前 no-commercial policy 下不能作为权威证据。

## Result

覆盖：

- source count：`32`
- validation：`0` errors / `0` warnings
- tier counts：
  - S5：`9`
  - S4：`1`
  - S3：`4`
  - S2：`9`
  - S1：`7`
  - S0：`2`
- claim-evidence source candidates after parser/gate：`11`
- current runtime candidate sources：`9`
- blocked/deferred sources：`16`

当前 no-commercial 上限：

- US filing-based fundamentals：`high`
- macro / industry context：`medium`
- non-US primary disclosure：`low_medium` current，parser 完成后可到 `high`
- company-reported product operating metrics：`low_medium` current，ontology/parser 后可到 `medium_high`
- healthcare product / regulatory：`low_medium` current，resolver 后可到 `medium_high`
- market valuation / consensus：`low_medium` current，且 no-commercial 下仍缺可靠 consensus、target price、实时估值 feed
- supply chain / customer relationship：`low_medium` current，公开源不能替代商业供应链交易库或海关微观数据

硬结论：

- 不用商业 API 也能把“公司披露 + 官方宏观行业 + 监管/产品状态 + entity resolver”做到可审计的中高质量。
- 公开源 buildout 后，研报上限可以到：disclosed company facts 高、context/regulatory 中高。
- 公开源无法突破：sell-side consensus、目标价、实时估值、未披露产品销量、渠道库存、私有客户采用、商业供应链交易数据。

## Validation

- `python -m py_compile scripts\data_expansion\build_public_source_information_strength_report.py` -> pass
- `python -m pytest tests\test_public_source_information_strength_report.py` -> `3 passed`
- `python scripts\data_expansion\build_public_source_information_strength_report.py` -> pass，validation `0` errors / `0` warnings

## Follow-up

- 在更新 agent graph / skill 前，先按上限选择工程优先级：
  1. `company_product_operating_metric` ontology/parser。
  2. DART document/package parser 和 EDINET key/API smoke。
  3. FRED/BLS/BEA/Census/EIA route allowlist 接入 `industry_snapshot`。
  4. ClinicalTrials/openFDA/NHTSA/CMS sponsor/product/entity resolver。
  5. SEC ownership / 13F investment graph。
- Agent Graph / Skill 的下一轮更新必须引用该 strength matrix，而不是直接引用 source list。
