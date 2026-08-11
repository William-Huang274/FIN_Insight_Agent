# 380 R17 Product Family Evidence Contracts

日期：2026-06-22

## 问题

上一轮 R17 ledger 已证明：DECK 这类 current-contract Product-KPI canary 能修，但 NVDA product spec / deployment proxy、MSFT cloud metric、ASML/TEL semicap operating metric、Hon Hai business mix 仍被标成 `new_contract_required`。这说明 Product-KPI exact 合同本身过窄，不能覆盖产品规格、代际、benchmark、客户部署、生态和行业经营指标。

## 决策

新增一组不混同 Product-KPI exact 的 runtime rows：

- `ProductSpecSlot`：官方产品参数 / 规格。
- `ProductGenerationEdge`：产品代际和架构迁移。
- `ProductBenchmarkProxy`：官方 benchmark / 性能 proxy。
- `CustomerDeploymentProxy`：官方客户部署数量或部署事实。
- `ProductEcosystemContext`：产品生态 / 互联 / 软件或部署环境。
- `IndustryOperatingMetricSlot`：公司披露的行业经营指标，例如 cloud revenue、semicap system units、field solution sales、business mix rank。

边界：

- 产品规格、benchmark、deployment、ecosystem rows 只能作为产品/竞争/需求 proxy context，不得支持产品收入、ASP、销量、份额、库存、sell-through、客户订单金额。
- Industry operating metric rows 可以支持其 citation 内的 exact 公司披露经营指标，但不是 Product-KPI exact，不能冒充 SKU/product revenue。

## 已完成

新增脚本：

- `scripts/data_expansion/build_r17_product_family_evidence_rows.py`

新增产物：

- `data/manifests/r17_product_family_evidence_runtime_rows_v0_1.jsonl`
- `data/manifests/r17_product_family_evidence_summary_v0_1.json`
- `docs/internal/vnext_20260610/vertical_lanes/r17_product_family_evidence.zh-CN.md`

更新 runtime / ledger：

- `src/sec_agent/runtime_source_context_store.py`
  - 增加 `r17_product_family_evidence` 默认 manifest。
  - 提升 `technical_product_spec` / `customer_deployment_proxy` / `product_benchmark_proxy` / `product_generation_edge` / `product_ecosystem_deployment_context` 的 public source selector 优先级，防止被普通 product page context 挤掉。
- `scripts/data_expansion/build_r17_source_route_attempt_ledger.py`
  - 增加 `--product-family-evidence` 输入。
  - 允许 new-contract canary 被 R17 product-family evidence rows 覆盖。

新增测试：

- `tests/test_r17_product_family_evidence_rows.py`
- 扩展 `tests/test_r17_source_route_attempt_ledger.py`
- 扩展 `tests/test_runtime_source_context_store.py`

## 结果

R17 product-family evidence strict：

- `runtime_row_count=24`
- `ticker_count=5`
- source family：
  - `company_product_evidence_graph=8`
  - `public_source_context=16`
- runtime contract：
  - `ProductSpecSlot=10`
  - `ProductBenchmarkProxy=2`
  - `ProductGenerationEdge=1`
  - `CustomerDeploymentProxy=2`
  - `ProductEcosystemContext=1`
  - `IndustryOperatingMetricSlot=8`

R17 ledger strict：

- `row_count=718`
- `unclassified_count=0`
- `action_required_count=303`
- `known_public_current_contract_failure_count=0`
- `known_public_new_contract_required_count=0`
- `canary_covered=7`

Runtime source context smoke：

- scope：`NVDA/MSFT/ASML/8035.T/2317.TW`
- 新 manifest 的 `24/24` 条 rows 均可进入 runtime bundle：
  - `r17_product_count=8`
  - `r17_public_count=16`
- `public_exact_authority_violation_count=0`

已运行：

```powershell
python scripts\data_expansion\build_r17_product_family_evidence_rows.py --strict
python scripts\data_expansion\build_r17_source_route_attempt_ledger.py --strict
python -m pytest tests/test_r17_product_family_evidence_rows.py tests/test_r17_source_route_attempt_ledger.py tests/test_r17_known_public_product_kpi_repair_rows.py tests/test_exact_slot_gap_closeout_ledger.py tests/test_product_kpi_deep_gap_diagnostic.py tests/test_runtime_source_context_store.py -q
```

结果：

- R17 product-family evidence strict：`pass`
- R17 ledger strict：`unclassified_count=0`
- Targeted pytest：`30 passed`

## 后续

1. 修 `source_route_retry_required=4` 的 fetch/parser retry debt，不能让 retryable failure 成为 final boundary。
2. 将 `action_required_count=303` 继续拆解为 source-route/parser/reroute backlog，而不是把它们误写成 public-source exhausted。
3. 扩展 `CloudInstanceAvailabilityProxy` / `OEMConfigurationProxy` / 更多独立 benchmark source route。
4. 在 full-chain case 中验证 Product/Technology Specialist 和 MemoLogicPlan 能实际利用 R17 产品规格、代际、部署和 operating metric rows。

## 安全边界

- R17 canary/ledger 是控制面，不是 evidence row。
- R17 product/spec/deployment rows 不得支持财务 exact claim。
- R17 industry operating metric rows 只能支持 citation 内经营指标，不得自动转成 Product-KPI exact。
