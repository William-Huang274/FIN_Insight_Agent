# R12 R1-R5 Exact-Slot Materialization And Closeout

日期：2026-06-18

## Prompt

用户要求把 R1-R5 做完，验收标准是 R5 后所有公司的 L1/L2/L3 都必须有真实测试过、能爬的 exact-slot 数据；实在做不了、爬不了、解析不了的再返回缺口。

## Decision

本轮把验收口径拆成两层：

1. 可提权数据必须是 source-specific parser-backed exact slot，且通过 `ExactSlotContractRegistry`。
2. 公开免费源无法填满的 slot 必须有 attempt / resolver / parser / source-profile closeout，不能用 `context_only`、官网描述、招聘、渠道、宏观或新闻 proxy 伪装成公司强事实。

这意味着 R1-R5 的完成口径不是“每家公司每个 L1/L2/L3 requirement 都 ready”，而是“ready row 可验证，未 ready row 有审计账本且不能被误提权”。

## Work Completed

- R1:
  - 新增/扩展 `src/sec_agent/exact_slot_contracts.py`；
  - 新增 `primary_company_disclosure` / `company_reported_financial_statement_metric` exact-slot contract；
  - 让 `source_coverage_gate` 识别 `company_reported_structured_financial_fact` -> `sec_financial_statement_data_sets`。
- R2:
  - 新增 `scripts/data_expansion/build_sec_financial_statement_metric_runtime_rows.py`；
  - 从 `sec_companyfacts_financial_fact_rows_v0_1.jsonl` 投影 SEC CompanyFacts/FSD 三表科目 rows；
  - 用 canonical concept allowlist 修复早期基于 `metric_family` 的误分类风险，避免 RPO 等非收入项被当作 revenue。
- R3/R4:
  - 把 SEC financial rows、official/API rows、trusted external、regulated/auto、app、hiring、public contract、channel rows 纳入 exact-slot coverage matrix；
  - 修复 `build_broad_hiring_capacity_context_rows.py` 的 Ashby / SmartRecruiters adapter 和 issuer binding，未验证 board-token 只写 `issuer_locator_candidate_unverified`，不允许 promotion；
  - 修复 R5 closeout 对 CDW channel attempts 的 provider/source alias 关联，否则 `channel_offer_proxy` 会被错误标成未分类。
- R5:
  - 新增 `scripts/data_expansion/build_exact_slot_gap_closeout_ledger.py`；
  - 生成：
    - `data/manifests/exact_slot_gap_closeout_v0_1.jsonl`
    - `data/manifests/product_kpi_exact_slot_closeout_v0_1.jsonl`
    - `data/manifests/exact_slot_gap_closeout_summary_v0_1.json`
    - `docs/internal/vnext_20260610/vertical_lanes/exact_slot_gap_closeout.zh-CN.md`
  - 更新 `docs/architecture/agent_graph_vnext/16_l4_weak_signal_and_vertical_source_lane_framework.zh-CN.md` 和 `18_exact_slot_data_layer_completion_plan.zh-CN.md`。

## Result

Exact-slot matrix:

- company_count: `603`
- all_required_exact_ready_company_count: `85`
- partial_exact_ready_company_count: `518`
- no_exact_ready_company_count: `0`
- exact_slot_row_count: `27,276`
- exact_slot_gap_count: `1,131`
- exact rows by layer: `L1=20,523`、`L2=4,195`、`L3=2,541`
- companies with any exact row by layer: `L1=587`、`L2=603`、`L3=420`

Source-role readiness:

- `primary_company_disclosure`: ready `587/603`
- `official_product_surface`: ready `310/310`
- `trusted_external_context`: ready `603/603`
- `macro_official_context`: ready `603/603`
- `energy_utility_context`: ready `216/216`
- `financial_regulatory_context`: ready `77/77`
- `technology_research_proxy`: ready `111/111`
- `public_order_proxy`: ready `299/438`
- `supply_chain_official_relationship`: ready `183/276`
- `app_rank_store_proxy`: ready `75/103`
- `platform_review_proxy`: ready `129/182`
- `hiring_capacity_proxy`: ready `43/526`
- `channel_offer_proxy`: ready `4/148`
- `developer_ecosystem_proxy`: ready `5/137`
- `regulated_product_context`: ready `32/68`
- `auto_product_identity_context`: ready `10/17`

R5 closeout:

- `status=pass`
- closeout rows: `1,131`
- `unclassified_closeout_count=0`
- closeout classes:
  - `public_source_exhausted_gap=957`
  - `resolver_gap=151`
  - `parser_or_source_profile_gap=16`
  - `not_applicable_or_source_gap=7`
- product KPI closeout:
  - `product_kpi_exact_ready=77`
  - `product_kpi_exact_gap=526`

## Remaining Gaps

- L1: `16` 家非美 / 非 SEC CompanyFacts 覆盖公司仍需当地交易所、company IR 或年报表格 parser，不能用官网或 proxy row 兜底。
- L3: `183` 家没有任何可提权 L3 proxy exact row；主要原因是公开 ATS/channel/developer/app/award/regulatory route 跑过后没有 issuer/product-bound structured row。
- Product KPI: `526` 家公司没有 company-disclosed product KPI exact slot；official surface / taxonomy / proxy context 只能支持产品存在、规格、检索规划或方向性验证，不能写成产品表现数据。

## Verification

- `python scripts/data_expansion/build_exact_slot_coverage_matrix.py` -> validation `pass`, `error_count=0`.
- `python scripts/data_expansion/build_exact_slot_gap_closeout_ledger.py --strict` -> status `pass`, `unclassified_closeout_count=0`.
- `python -m pytest tests/test_exact_slot_contracts.py tests/test_sec_financial_statement_metric_runtime_rows.py tests/test_broad_hiring_capacity_context_rows.py tests/test_exact_slot_gap_closeout_ledger.py -q` -> `16 passed`.
- `python -m py_compile src/sec_agent/exact_slot_contracts.py src/sec_agent/source_coverage_gate.py scripts/data_expansion/build_sec_financial_statement_metric_runtime_rows.py scripts/data_expansion/build_broad_hiring_capacity_context_rows.py scripts/data_expansion/build_exact_slot_coverage_matrix.py scripts/data_expansion/build_company_public_source_coverage_matrix.py scripts/data_expansion/build_exact_slot_gap_closeout_ledger.py` -> pass.
- `git diff --check` -> pass.

## Safety Notes

- Closeout rows are not evidence rows. Research Lead / Specialist / Memo Writer / Verifier 只能把它们用于缺口解释和 targeted repair，不得把 closeout reason 写成支持结论的证据。
- 未提交 Git；本轮只记录工作树状态和验证结果。
