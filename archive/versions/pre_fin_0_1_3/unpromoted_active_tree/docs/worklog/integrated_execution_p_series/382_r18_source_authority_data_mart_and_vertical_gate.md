# 382 R18 Source Authority Data Mart and Vertical Gate

日期：2026-06-23

## 背景

用户本轮明确关心数据源和数据基座，而不是先跑 DeepSeek/full-chain。此前 R18 已完成 SourceAuthorityCoverage、Research Lead 读取和 AI/Semis first-tranche source-route gate，但全行业仍缺一个 canonical 数据源台账，用于回答：

- 每家公司有哪些 source-role / source-id 已有 parser-backed runtime rows；
- 哪些 row 可以进入 evidence bundle，哪些只能进 planning / targeted repair / gap ledger；
- L2/L3 非财务信号能支撑什么 thesis driver，不能支撑什么 exact claim；
- 603 公司跨行业 lane-required source role 还剩哪些真实 action-required 缺口。

## 本轮交付

新增脚本：

- `scripts/data_expansion/build_r18_source_authority_data_mart.py`
- `scripts/data_expansion/build_r18_vertical_source_route_gate.py`

新增 tests：

- `tests/test_r18_source_authority_data_mart.py`
- `tests/test_r18_vertical_source_route_gate.py`

新增/刷新数据产物：

- `data/manifests/r18_source_authority_data_mart_rows_v0_1.jsonl`
- `data/manifests/r18_source_authority_data_mart_summary_v0_1.json`
- `docs/internal/vnext_20260610/r18_source_authority_data_mart.zh-CN.md`
- `data/manifests/r18_vertical_source_route_gate_rows_v0_1.jsonl`
- `data/manifests/r18_vertical_source_route_gate_summary_v0_1.json`
- `docs/internal/vnext_20260610/r18_vertical_source_route_gate.zh-CN.md`

文档更新：

- `docs/architecture/agent_graph_vnext/23_non_financial_signal_authority_and_multidimensional_research_basis.zh-CN.md`
- `docs/worklog/00_internal_master_checklist.md`
- `docs/worklog/README.md`

## Data Mart 结果

命令：

```powershell
python scripts\data_expansion\build_r18_source_authority_data_mart.py --strict
```

结果：

- `status=pass`
- `company_count=603`
- `row_count=7,884`
- `evidence_bundle_allowed_count=7,752`
- `planning_or_gap_only_count=132`
- hard gate：`flag_count=0`

Authority 分层：

- `exact_company_fact_authority=2,643`
- `bounded_thesis_driver_authority=5,109`
- `route_or_parser_debt=52`
- `attempt_backed_public_boundary=80`

Source layer：

- `L1=2,971`
- `L2=4,189`
- `L3=724`

解释：

- Data mart 是 Research Lead / eval / frontend trace 共享的 canonical source authority view。
- `can_enter_evidence_bundle=true` 的 row 才能进入 ClaimCard / Memo 证据。
- `can_enter_evidence_bundle=false` 的 row 只能进入 planning、targeted repair、gap ledger。
- L2/L3 准入 row 只能按 `claim_boundary` 支撑 bounded thesis driver，不能冒充产品收入、销量、ASP、份额、sell-through、inventory、backlog 或 order value。

## Cross-lane Gate 结果

命令：

```powershell
python scripts\data_expansion\build_r18_vertical_source_route_gate.py
```

结果：

- `status=action_required`
- `company_count=603`
- `pass_company_count=503`
- `action_required_company_count=100`
- `requirement_count=2,708`
- `passed_requirement_count=2,601`
- `missing_requirement_count=107`
- hard gate：`flag_count=0`

剩余 missing source roles：

- `hiring_capacity_proxy=36`
- `public_order_proxy=25`
- `technology_research_proxy=17`
- `developer_ecosystem_proxy=13`
- `channel_offer_proxy=8`
- `app_rank_store_proxy=4`
- `platform_review_proxy=3`
- `auto_product_identity_context=1`

Root cause：

- `source_or_adapter_gap=73`
- `route_or_parser_debt=34`

解释：

- 这不是全行业 gate fail；这是 release 前的数据基座诊断 gate。
- 相比旧的 company coverage `365` 家 gap，新的 gate 已经把问题缩到 `100` 家、`107` 个 source-role requirement。
- 当前没有 coverage matrix 与 data mart 的同步硬错误：`coverage_matrix_pass_without_data_mart_evidence=0`。
- 后续应从这 107 个 requirement 继续做 source-route / parser / resolver 深挖，不能用 URL/snippet/seed/attempt-only 伪装补齐。

## 验证

```powershell
python -m py_compile scripts\data_expansion\build_r18_source_authority_data_mart.py scripts\data_expansion\build_r18_vertical_source_route_gate.py
python -m pytest tests\test_r18_source_authority_data_mart.py tests\test_r18_vertical_source_route_gate.py tests\test_r18_ai_semis_source_route_gate.py tests\test_r18_data_source_admission_ledger.py -q
python scripts\data_expansion\build_r18_source_authority_data_mart.py --strict
python scripts\data_expansion\build_r18_vertical_source_route_gate.py
```

结果：

- 新增 tests：`6 passed`
- R18 targeted regression：`13 passed`
- `py_compile`：通过
- Data mart strict：通过
- Cross-lane gate：诊断性 `action_required`，hard gate 0

## 后续

1. 从 `r18_vertical_source_route_gate_rows_v0_1.jsonl` 中抽取 107 个 action-required requirement，按 source role 分批修复。
2. 优先修 `hiring_capacity_proxy`、`public_order_proxy`、`technology_research_proxy`，因为它们占 `78/107`。
3. 每修一批都重跑：
   - source-specific adapter/parser
   - company public source coverage matrix
   - R18 data source admission ledger strict
   - R18 source authority data mart strict
   - R18 vertical source route gate
4. 修到公开源理论不可得时，必须写 attempt-backed public boundary / commercial tracker / manual primary research gap，不能直接从缺口变成 evidence。

## 边界

- 本轮没有跑 DeepSeek / full-chain。
- 本轮没有改 memo writer 或 agent graph 行为，只新增 canonical data mart 和 cross-lane diagnostic gate。
- Cross-lane gate 当前不应作为 release pass 使用；它是 source-route repair 队列生成器。待 107 个 action-required requirement 完成或 closeout 后，再把它升级为 release hard gate。

## 2026-06-23 R18 Cross-lane Repair Tranche

问题：

- 用户要求继续把 L1/L2/L3 数据基座补实，尤其不能把 URL、seed、attempt-only 或弱 proxy 伪装成可提权 evidence。
- 基线 gate 为 `100` 家 / `107` 个 action-required source-role requirement。

决策：

- 先修可以明确归因于 route/parser/resolver 的缺口。
- 对仍没有 parser-backed exact/context row 的源保持缺口，不用 official page URL、搜索结果、GitHub blind search 或 careers landing page 兜底。

完成：

- `technology_research_proxy`
  - 修复 `build_v1_openalex_technology_research_context_rows.py`：
    - 新增 issuer alias override：`GOOGL -> Google`、`CRM -> Salesforce.com`、`CSCO -> Cisco Systems`、`1211.HK -> BYD`、`300750.SZ -> CATL`、`373220.KS -> LGES` 等。
    - 新增 ticker-level topic override：`TER -> semiconductor test / ATE`、`ADI -> analog / signal processing`、`CSCO -> networking/security`、`TSLA -> battery/autopilot/supercharger`、`1211.HK -> Blade Battery` 等，避免 family route 误把 Teradyne 映射成 lithography/etch。
  - 补测试：`test_openalex_family_plan_uses_company_alias_overrides_for_issuer_binding`、`test_openalex_family_plan_uses_ticker_topic_overrides_for_misclassified_routes`。
  - 真实 OpenAlex batch 后，technology missing 从 `17` 降到 `4`。
- `public_order_proxy`
  - 修复 `build_r18_vertical_source_route_gate.py`：允许 `supply_chain_official_relationship` 作为 `public_order_proxy` 的同域更强/同级 alternate evidence。
  - 边界：只满足官方客户/供应链关系验证，不证明订单金额、backlog、收入、份额或 sell-through。
  - 补测试：`test_vertical_gate_allows_official_supply_chain_relationship_for_public_order_requirement`。
- `hiring_capacity_proxy`
  - 修复 `build_broad_hiring_capacity_context_rows.py`：新增 `HUBS -> greenhouse/hubspotjobs` verified board token。
  - 修复 `build_broad_official_careers_context_rows.py`：新增 `CRWD -> https://crowdstrike.wd5.myworkdayjobs.com/crowdstrikecareers` verified Workday CXS site。
  - 补测试：HubSpot board token 与 CRWD direct ATS candidate。
  - 真实 ingestion 后，hiring missing 从 `36` 降到 `34`。
- `auto_product_identity_context`
  - 实测 XPEV：NHTSA `GetModelsForMake/Xpeng` 返回 `Count=0`。
  - 结论：不能用当前 official product surface contract row 代替 NHTSA，因为 XPEV 的 official product rows 仍不是 parser-backed 车型 row；后续需要 official product page parser。

最新结果：

```powershell
python scripts\data_expansion\build_company_public_source_coverage_matrix.py
python scripts\data_expansion\build_r18_data_source_admission_ledger.py --strict
python scripts\data_expansion\build_r18_source_route_registry_v2.py --strict
python scripts\data_expansion\build_r18_source_authority_data_mart.py --strict
python scripts\data_expansion\build_r18_vertical_source_route_gate.py
```

- Data mart：`status=pass`，`company_count=603`，`row_count=7,884`，`evidence_bundle_allowed_count=7,780`，`planning_or_gap_only_count=104`，hard gate `flag_count=0`。
- Cross-lane gate：`status=action_required`，`pass_company_count=521`，`action_required_company_count=82`，`missing_requirement_count=86`，hard gate `flag_count=0`。
- 剩余 source-role split：
  - `hiring_capacity_proxy=34`
  - `public_order_proxy=19`
  - `developer_ecosystem_proxy=13`
  - `channel_offer_proxy=8`
  - `app_rank_store_proxy=4`
  - `technology_research_proxy=4`
  - `platform_review_proxy=3`
  - `auto_product_identity_context=1`
- 剩余 root cause：`source_or_adapter_gap=68`、`route_or_parser_debt=18`。

剩余边界与下一步：

- `developer_ecosystem_proxy` 剩余 `13` 家多为硬件、分销、工业、材料或控股平台；official seed locator 已尝试官方页面与 verified GitHub profile，未找到 official repo/package/model seed。下一步是 requirement recalibration 或公司特定 verified docs，不做 blind GitHub 绑定。
- `channel_offer_proxy` 剩余 `8` 家说明 CDW route 不适配零售/汽车/消费品牌；需要 AutoZone / HomeDepot / DollarGeneral / NIO / Deckers 等 official store 或 marketplace site-specific parser，不能把 CDW mismatch 或 403 页面提权。
- `public_order_proxy` 剩余 `19` 家需要非美/local tender、能源/太阳能/核能招标、或公司/客户官方合同披露 adapter；USAspending 不适用的不能硬填。
- `technology_research_proxy` 剩余 `PLTR`、`300750.SZ`、`373220.KS`、`MPWR`。OpenAlex 已做 alias/topic 修复仍无稳定 issuer-topic rows；下一步是 PatentsView/USPTO assignee resolver 或 official technical docs。

验证：

- `python -m pytest tests\test_v1_openalex_technology_research_context_rows.py -q` -> `5 passed`
- `python -m pytest tests\test_broad_hiring_capacity_context_rows.py tests\test_broad_official_careers_context_rows.py -q` -> `6 passed`
- 后续仍需统一跑 R18 regression、py_compile、`git diff --check`。

## 2026-06-23 R18 Source-role Gate Tightening and Lane Repair

问题：

- 继续修 source-role / product-family 数据基座时发现两类 root cause：
  - `channel_offer_proxy` 已有 `family_channel_distributor_context_rows_v0_1` 真实 parser-backed rows，但 company matrix / source coverage gate 没把 `channel_distributor_locator` 纳入 channel offer route。
  - `auto_product_identity_context` 与 vertical lane assignment 口径存在偏差：XPEV official product/model page 已有 parser-backed issuer/product rows，但 exact contract 只认 NHTSA；同时 V5 lane assignment 用裸 substring，把 `Automatic Data Processing`、`Autodesk`、`Rockwell Automation`、`AutoZone`、`O'Reilly Automotive` 误放进 Auto lane。
- Admission ledger 还存在 multi-source requirement 误展开：当某个 source-role 由一个真实 source_id 满足时，同组未观测 source_id 也会生成 evidence-ready 行，造成假 readiness。

修复：

- `source_coverage_gate.py`
  - `channel_offer_proxy` 增加 `channel_distributor_locator`。
  - `auto_product_identity_context` 增加 `company_product_pages`，边界限定为 vehicle/model/product identity context，不证明销量、利润、注册或份额。
- `build_company_public_source_coverage_matrix.py`
  - 默认 observed paths 加入 `family_channel_distributor_context_rows_v0_1.jsonl`。
- `build_r18_data_source_admission_ledger.py`
  - 新增 `_admission_source_ids`，pass requirement 只按 `observed_source_ids` 或 exact coverage 的 target source 发 admission row，不再展开未观测 sibling source_id。
- `exact_slot_contracts.py`
  - `auto_product_identity_context` 支持 official model/product page，但只对 explicit auto/OEM/battery ticker allowlist 和 auto-specific product page 生效，避免 `Automatic` / `Autodesk` / `Automation` 误入 auto identity。
- `vertical_source_lane_registry.py`
  - 修复 primary lane overrides：`ADP/ADSK -> V3`，`ROK -> V7`，`AZO/ORLY -> V8`，`1211.HK/LI/NIO/XPEV -> V5`。
  - auto lane keyword 从裸 substring 改为更严格 auto signal，避免 `automatic/autodesk/automation` 误中。

重建：

```powershell
python scripts\data_expansion\build_vertical_source_lane_registry.py
python scripts\data_expansion\build_product_family_source_route_plan.py
python scripts\data_expansion\build_company_public_source_coverage_matrix.py
python scripts\data_expansion\build_exact_slot_coverage_matrix.py
python scripts\data_expansion\build_r18_data_source_admission_ledger.py --strict
python scripts\data_expansion\build_r18_source_route_registry_v2.py --strict
python scripts\data_expansion\build_r18_source_authority_data_mart.py --strict
python scripts\data_expansion\build_r18_vertical_source_route_gate.py
```

结果：

- Vertical lane registry：`company_count=603`，lane split `V1=43,V2=9,V3=96,V4=68,V5=14,V6=77,V7=215,V8=81`。
- Exact-slot coverage：`all_required_exact_ready_company_count=528`，`partial_exact_ready_company_count=75`，`exact_slot_gap_count=77`；`auto_product_identity_context` gap `0`，official vehicle identity rows 收紧到 `72`。
- R18 admission ledger：`status=pass`，`company_count=603`，`row_count=3,746`，`can_enter_evidence_bundle_count=3,649`，`not_evidence_ready_count=97`，hard gate 全 0。
- R18 SourceRouteRegistry v2：`status=pass`，`admission_row_count=3,746`，`evidence_bundle_allowed_count=3,649`，`observed_source_role_count=16`，`observed_source_id_count=25`，hard gate 全 0。
- R18 data mart：`status=pass`，`row_count=3,746`，`evidence_bundle_allowed_count=3,649`，`planning_or_gap_only_count=97`，`exact_company_fact_authority_count=865`，`thesis_driver_authority_count=2,784`，hard gate `flag_count=0`。
- R18 vertical gate：`status=action_required`，`pass_company_count=534`，`action_required_company_count=69`，`missing_requirement_count=71`，hard gate `flag_count=0`。
- 剩余 source-role split：
  - `hiring_capacity_proxy=27`
  - `public_order_proxy=19`
  - `developer_ecosystem_proxy=13`
  - `channel_offer_proxy=8`
  - `technology_research_proxy=4`
- 剩余 root cause：`source_or_adapter_gap=53`、`route_or_parser_debt=18`。

剩余边界：

- `channel_offer_proxy=8`：GPC/NIO/AZO/CASY/DECK/DG/HD/MNST 仍需 official store / marketplace / family-specific parser；已知 CDW route 不适配，部分站点 403/anti-bot 或无 SKU/price/availability locator，不得用 blocked URL 提权。
- `hiring_capacity_proxy=27`：主要是大型 SaaS/telecom/industrial/restaurant 的 careers site-specific parser 或 public ATS issuer-bound row 缺口；landing page 不够。
- `developer_ecosystem_proxy=13`：剩余多为硬件/分销/工业公司，缺 verified official docs/repo/package seed；不能 blind-search GitHub 后强行绑定。
- `public_order_proxy=19`：多为非美/local tender、能源/太阳能/核能或 customer official contract route；USAspending 无 recipient-bound rows 时不能硬填。
- `technology_research_proxy=4`：`PLTR/300750.SZ/373220.KS/MPWR` 仍需 PatentsView/USPTO assignee resolver 或 official technical docs；OpenAlex alias/topic 修复后仍无稳定 issuer-topic rows。

验证：

- `python -m py_compile src\sec_agent\source_coverage_gate.py src\sec_agent\company_public_source_coverage_matrix.py src\sec_agent\exact_slot_contracts.py src\sec_agent\vertical_source_lane_registry.py scripts\data_expansion\build_company_public_source_coverage_matrix.py scripts\data_expansion\build_r18_data_source_admission_ledger.py scripts\data_expansion\build_broad_official_careers_context_rows.py` -> pass
- `python -m pytest tests\test_source_coverage_gate.py tests\test_company_public_source_coverage_matrix.py tests\test_exact_slot_contracts.py tests\test_vertical_source_lane_registry.py tests\test_r18_data_source_admission_ledger.py tests\test_r18_vertical_source_route_gate.py tests\test_r18_source_authority_data_mart.py tests\test_broad_official_careers_context_rows.py -q` -> `48 passed`
- `git diff --check` -> pass
