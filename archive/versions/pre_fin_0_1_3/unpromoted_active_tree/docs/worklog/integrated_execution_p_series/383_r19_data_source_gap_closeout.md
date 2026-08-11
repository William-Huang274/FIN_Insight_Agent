# R19 Data Source Gap Closeout

## Prompt

用户要求继续补 source-role 更细缺口和 Product-KPI / L1-L3 数据源缺口，目标是公开源能补的都补到 parser-backed exact / bounded runtime row；实在无法从公开免费源获取、需要凭证、site-specific adapter、商业 tracker 或人工调研的，再暴露为 gap。不得把 URL、snippet、seed 或 attempt-only 行提权为 evidence。

## Decision

本轮以 `r18_vertical_source_route_gate_v0_1` 和 `r18_source_authority_data_mart_v0_1` 为 canonical gate，而不是只看公司/行业 lane pass。修复优先级：

1. 可确定的 route/parser debt 先修：官方 ATS、官方 careers 表格、官方 channel locator 反爬/browser fallback、品牌域名绑定。
2. 明确不适用的 source role 要落成 not-applicable-after-source-probe，而不是继续要求错误的 GitHub/npm/package seed。
3. 对公共订单、技术研究、招聘、渠道剩余缺口保留 attempt-backed boundary；只有 parser-backed issuer-bound rows 才能进入 evidence bundle。

## Work Completed

- `hiring_capacity_proxy`
  - 在 `scripts/data_expansion/build_broad_official_careers_context_rows.py` 中新增 Oracle HCM Candidate Experience adapter。
  - 新增官方 ATS direct routes：`AKAM/FTNT/HON/ORCL/VRT/YUM` 等。
  - 新增 generic careers search-table parser，覆盖 `CHTR/PCOR` 等静态职位列表。
  - 真实 smoke：Oracle HCM / Workday / generic table 均能返回 title/location parser-backed rows。
- `developer_ecosystem_proxy`
  - 在 `src/sec_agent/company_public_source_coverage_matrix.py` 中对 `APH/CDW/COHR/DIOD/FN/GLW/IT/LITE/MTSI/Q/RMBS/ROP/WOLF` 增加 `not_applicable_after_source_probe`。
  - 原因：已做 official docs/package/repo seed probe，未找到 verified issuer-bound developer seed；这些 issuer 多为硬件、分销、制造、材料或研究服务公司，不应 blind-search GitHub/npm 后强行绑定。
- `channel_offer_proxy`
  - 在 `build_family_channel_distributor_context_rows.py` 中新增 `DECK` 品牌域名 override：`deckers.com/hoka.com/ugg.com/teva.com`。
  - 新增 `AZO/CASY/DG/GPC/MNST` 域名 override，防止 manual official locator seed 被缺失 domain cache 误过滤。
  - 修复 browser fallback 触发顺序：manual verified channel seed 若普通 HTTP 返回 403/blocked/empty，现在会先尝试 Playwright，再决定是否暴露为 unusable response。
  - 真实重跑后 `DECK` 和 `NIO` 进入 `channel_distributor_locator` runtime rows；这些 rows 只支持 official channel/store/locator presence，不支持价格、ASP、库存、sell-through、销量、销售额、需求或份额。
- 重建 canonical artifacts：
  - `company_public_source_coverage_matrix_v0_1`
  - `exact_slot_coverage_matrix_v0_1`
  - `r18_data_source_admission_ledger_v0_1`
  - `r18_source_route_registry_v2`
  - `r18_source_authority_data_mart_v0_1`
  - `r18_vertical_source_route_gate_v0_1`

## Results

- `r18_source_authority_data_mart_v0_1`
  - `status=pass`
  - `company_count=603`
  - `row_count=3,729`
  - `evidence_bundle_allowed_count=3,660`
  - `planning_or_gap_only_count=69`
  - hard gate `flag_count=0`
- `exact_slot_coverage_matrix_v0_1`
  - validation `status=pass`
  - `all_required_exact_ready_company_count=551`
  - `partial_exact_ready_company_count=52`
  - `exact_slot_gap_count=53`
  - `channel_offer_proxy`: `ready_count=56`, `gap_count=6`
  - `hiring_capacity_proxy`: `ready_count=48`, `gap_count=18`
  - `technology_research_proxy`: `ready_count=74`, `gap_count=4`
- `r18_vertical_source_route_gate_v0_1`
  - `status=action_required`
  - `pass_company_count=557`
  - `action_required_company_count=46`
  - `missing_requirement_count=47`
  - hard gate `flag_count=0`

## Remaining Action-Required Boundary

- `public_order_proxy=19`
  - Tickers: `CRDO/PCAR/BILL/CSIQ/JKS/SEDG/SHOP/1211.HK/6752.T/CCJ/DNN/DQ/ENLT/ENPH/NXT/OKLO/SMR/UROY/RUN`
  - Current boundary: USAspending / local tender attempts did not yield recipient-bound order or award rows. Next real work is jurisdiction-specific tender/status parser, customer-contract adapter, or issuer/customer official relationship route. Search-result URL or news mention cannot fill order/backlog/value.
- `hiring_capacity_proxy=18`
  - Tickers: `SE/ADP/CTSH/IBM/MSFT/ROP/S/SHOP/TEAM/VZ/EME/ETN/FIX/LII/PWR/DRI/MELI/SBUX`
  - Current boundary: official careers pages generally exist, but current parser does not yet extract stable issuer-bound title/location rows from Eightfold, Jibe/protected official careers, site-specific APIs, or dynamic pages. Careers landing page is not an exact job row.
- `channel_offer_proxy=6`
  - Tickers: `GPC/AZO/CASY/DG/HD/MNST`
  - Current boundary: official store locator / e-commerce pages either block ordinary/browser fetch, require site-specific store APIs, or do not expose issuer-bound locator rows in parseable HTML. Monster Beverage has no verified official locator. URL existence remains attempt-only.
- `technology_research_proxy=4`
  - Tickers: `PLTR/300750.SZ/373220.KS/MPWR`
  - Current boundary: OpenAlex did not return stable issuer-topic-bound rows. Local environment still lacks PatentsView / USPTO assignee resolver credentials. Generic paper/patent keyword results cannot be promoted.

## Verification

- `python -m py_compile scripts\data_expansion\build_broad_official_careers_context_rows.py`
- `python -m py_compile src\sec_agent\company_public_source_coverage_matrix.py scripts\data_expansion\build_broad_official_careers_context_rows.py`
- `python -m pytest tests\test_broad_official_careers_context_rows.py -q` -> `7 passed`
- `python -m pytest tests\test_company_public_source_coverage_matrix.py tests\test_broad_official_careers_context_rows.py -q` -> `14 passed`
- `python -m pytest tests\test_family_channel_distributor_context_rows.py -q` -> `17 passed`

Final combined regression and `git diff --check` are recorded in the turn summary after this worklog update.

## Safety Notes

- No secrets were written to docs.
- URL/snippet/seed/attempt-only rows remain blocked from evidence bundle by R18 hard gates.
- `requirement_results` contains wider planning gaps; release blocking source-role gaps should be read from `missing_source_roles` and `r18_vertical_source_route_gate_summary_v0_1`.
