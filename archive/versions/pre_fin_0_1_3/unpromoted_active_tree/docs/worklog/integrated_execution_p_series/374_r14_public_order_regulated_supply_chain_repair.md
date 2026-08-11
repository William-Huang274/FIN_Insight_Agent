# 374 R14 Public Order / Regulated / Supply-Chain Repair

## Prompt

按 1-6 顺序推进第 6 步：public order / regulated / supply-chain 小批量专修。public order 按司法辖区；regulated 先重校适用性；supply-chain 只用官方新闻、合同披露或对手方官方源。

## Reasoning And Decision

本轮不能把公开订单、监管、供应链关系混成一个弱 proxy。处理原则：

- regulated / auto 只接受 sponsor、collaborator、applicant、manufacturer、make/model 绑定的官方 API row。
- public order 必须按司法辖区分流；USAspending 只适用于 US recipient-bound award，不应覆盖 HK/TW/JP/FPI/local tender。
- supply-chain 只能从 issuer / counterparty / official news / official contract disclosure 生成关系 row；unnamed customer、宽泛新闻、公共采购 proxy 不能证明出货、订单、收入或份额。

## Work Completed

- 更新 `scripts/data_expansion/build_targeted_regulated_auto_official_api_context_rows.py`：
  - 新增 openFDA device 510(k) parser；
  - 新增 NHTSA manufacturer fallback；
  - 修正 WST / COR / HSIC / MCK / HCA 等 regulated route applicability。
- 更新 `scripts/data_expansion/build_broad_public_contract_award_context_rows.py`：
  - recipient match 从 substring 改成 token-sequence；
  - 防止 `Oklo` / `Quanta Services` 这类短 alias false positive。
- 新增 `scripts/data_expansion/build_targeted_supply_chain_official_relationship_rows.py`：
  - 物化官方供应链关系 rows；
  - 只接受 issuer alias + counterparty alias 双绑定；
  - 明确禁止订单、出货、收入、份额、backlog 推断。
- 更新 exact-slot / company coverage / route plan 默认 observed path，纳入 `targeted_supply_chain_official_relationship_context_rows_v0_1.jsonl`。
- 更新 `scripts/data_expansion/build_exact_slot_gap_closeout_ledger.py`：
  - 加入 targeted supply-chain attempt ledger；
  - supply-chain 官方关系与 public-order proxy 分开 closeout；
  - public-order closeout 按 US / HK / TW / JP / FPI / local tender 分类。
- 新增 `tests/test_targeted_supply_chain_official_relationship_rows.py`，扩展 closeout / public order / regulated tests。
- 刷新 route plan、company coverage、exact-slot matrix、gap closeout、Product-KPI diagnostic、company gap docket。
- 更新 `docs/architecture/agent_graph_vnext/19_source_role_product_kpi_exact_slot_deep_repair.zh-CN.md`。

## Result And Evidence

Regulated / auto：

- `required_ticker_count=72`
- `success_ticker_count=69`
- `row_count=151`
- remaining: `IDXX`, `ZTS`, `XPEV`

Supply-chain official relationship：

- `row_count=9`
- `attempt_count=9`
- `attempt_status_counts.materialized=9`
- materialized tickers: `2317.TW`, `2382.TW`, `3231.TW`, `8035.T`, `AMKR`, `ASML`, `CAMT`, `FORM`, `SMCI`
- `supply_chain_official_relationship.ready_count=20`
- `supply_chain_official_relationship.gap_count=1`
- remaining: `AEHR`，原因是公开材料为 unnamed customer / customer class，不能绑定 named counterparty。

Public order：

- `public_order_proxy.ready_count=106`
- `public_order_proxy.gap_count=53`
- `33` 条 US issuer 为 USAspending 无 recipient-bound award row；
- `20` 条 non-US / local issuer 被拆成 HK/TW/JP/FPI/local tender adapter required，不再误记为 USAspending gap。

最新全局矩阵：

- `exact_slot_gap_count=195`
- `all_required_exact_ready_company_count=445`
- `partial_exact_ready_company_count=158`
- `no_exact_ready_company_count=0`
- `source_role_gap_docket_count=195`
- `product_kpi_gap_docket_count=377`
- `docket_count=572`
- `unclassified_closeout_count=0`
- `unclassified_docket_count=0`

## Verification

- `python -m py_compile scripts\data_expansion\build_targeted_supply_chain_official_relationship_rows.py scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py` -> pass
- `python scripts\data_expansion\build_targeted_supply_chain_official_relationship_rows.py --replace-output --strict --timeout-s 20 --sleep-s 0.05 --tickers 2317.TW 2382.TW 3231.TW 8035.T AMKR ASML CAMT FORM SMCI` -> pass
- `python scripts\data_expansion\build_product_family_source_route_plan.py` -> pass
- `python scripts\data_expansion\build_company_public_source_coverage_matrix.py` -> pass
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation pass
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> pass
- `python scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py --strict` -> pass
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> pass
- `python -m pytest tests\test_targeted_regulated_auto_official_api_context_rows.py tests\test_broad_public_contract_award_context_rows.py tests\test_targeted_supply_chain_official_relationship_rows.py tests\test_exact_slot_contracts.py tests\test_exact_slot_gap_closeout_ledger.py tests\test_company_gap_docket.py tests\test_product_kpi_deep_gap_diagnostic.py tests\test_product_family_source_routes.py tests\test_company_public_source_coverage_matrix.py -q` -> `39 passed`

## Follow-up

- Public-order 剩余 `20` 条 non-US/local 需要独立 local tender / regulator award / exchange filing / official contract disclosure adapters；这不是 USAspending route 的继续重试问题。
- `IDXX` / `ZTS` 需要 animal-health / veterinary regulatory route，不能用普通 ClinicalTrials/openFDA drug route 硬套。
- `AEHR` supply-chain 只有 unnamed customer / unnamed AI accelerator 公开描述，除非找到 named official counterparty-bound source，否则应继续暴露 gap。
- Step 6 后 source-role gaps 已经从混合原因拆成可调度 docket；后续可继续做 channel / public-order jurisdiction / animal-health / patents / hiring site-specific adapters。
