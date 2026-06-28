# 379 R17 SourceRouteAttemptLedger and Canary Gate

日期：2026-06-22

## 问题

R16 后仍存在两类风险：

- 公开披露或官方页面实际存在，但当前 source route / parser 没吃到，最终被误写成公开源边界。
- Product-KPI exact 合同过窄，导致 NVDA / AMD / Intel / Google TPU 这类产品规格、代际、客户部署 proxy、benchmark 和生态证据没有进入产品分析。

本轮目标是先建立 R17 审计合同，避免继续把 route/parser debt 混进 final public boundary。

## 决策

新增独立 `SourceRouteAttemptLedger`，不直接覆盖 R15/R16 closeout 产物。Ledger 作为控制面：

- 标出 source-role exact gap 的 attempt / fetch / parser / resolver 状态。
- 标出 Product-KPI diagnostic 的 ready / reroute / parser-debt / not-product-boundary 状态。
- 新增 known-public canary，防止 DECK 这类已知公开披露被误判为“公司未披露”。
- 把 NVDA product spec / deployment proxy、MSFT cloud operating metric、ASML/TEL semicap operating metric、Hon Hai business mix 标为新证据合同要求。

## 已完成

新增文档：

- `docs/architecture/agent_graph_vnext/22_source_route_attempt_ledger_and_product_family_evidence_hardening.zh-CN.md`

新增脚本：

- `scripts/data_expansion/build_r17_source_route_attempt_ledger.py`
- `scripts/data_expansion/build_r17_known_public_product_kpi_repair_rows.py`

新增产物：

- `data/manifests/source_route_attempt_ledger_v0_1.jsonl`
- `data/manifests/source_route_attempt_ledger_summary_v0_1.json`
- `data/manifests/r17_known_public_product_kpi_repair_runtime_rows_v0_1.jsonl`
- `data/manifests/r17_known_public_product_kpi_repair_summary_v0_1.json`
- `docs/internal/vnext_20260610/vertical_lanes/r17_source_route_attempt_ledger.zh-CN.md`

新增测试：

- `tests/test_r17_source_route_attempt_ledger.py`
- `tests/test_r17_known_public_product_kpi_repair_rows.py`

更新索引：

- `docs/architecture/agent_graph_vnext/README.zh-CN.md`
- `docs/worklog/README.md`
- `docs/worklog/00_internal_master_checklist.md`

## 结果

R17 baseline after DECK repair：

- `row_count=718`
- `source_role_exact_gap=108`
- `product_kpi_gap_or_ready=603`
- `known_public_canary=7`
- `unclassified_count=0`
- `action_required_count=309`
- `final_boundary_blocked_count=303`
- `known_public_current_contract_failure_count=0`
- `known_public_new_contract_required_count=6`

分类解读：

- `DECK` 已通过公司 IR 官方 FY2025 press release route 修复为 `canary_covered`。SEC archive 直接下载当前被 SEC automated-tool policy 拦截，不能把该 fetch failure 误写成源不存在。
- `NVDA` product spec / deployment proxy、`MSFT` cloud operating metric、`ASML` system units、`8035.T` semicap IR metric、`2317.TW` business mix 被标为新证据合同要求。
- 有 `fetch_failed` 的 public-source exhausted 行会被 R17 标为 `source_route_retry_required`，不允许作为 final boundary。
- Product-KPI closeout 已从 `product_kpi_exact_ready=172` / `product_kpi_gap=369` 更新为 `product_kpi_exact_ready=173` / `product_kpi_gap=368`。

已运行：

```powershell
python scripts/data_expansion/build_r17_known_public_product_kpi_repair_rows.py --strict
python scripts/data_expansion/build_exact_slot_gap_closeout_ledger.py --strict
python scripts/data_expansion/build_product_kpi_deep_gap_diagnostic.py --strict
python scripts/data_expansion/build_r17_source_route_attempt_ledger.py --strict
python -m pytest tests/test_r17_source_route_attempt_ledger.py tests/test_r17_known_public_product_kpi_repair_rows.py -q
```

结果：

- DECK repair strict：`runtime_row_count=3`
- Product-KPI closeout strict：`unclassified_closeout_count=0`
- Product-KPI diagnostic strict：`unclassified_count=0`
- R17 strict：`unclassified_count=0`
- Targeted pytest：`8 passed`

## 后续

1. 建 `ProductSpecSlot`、`ProductGenerationEdge`、`CustomerDeploymentProxy` 最小 runtime contract。
2. 用 NVDA H100/Blackwell/xAI、MSFT cloud/RPO、ASML/TEL system units、Hon Hai business mix 做 canary smoke。
3. 回灌 ProductFamilyLaneRegistry 和 RuntimeSourceContextStore，确保 full-chain 中 Product Specialist 能看到 spec/deployment/operating metrics。
4. 修 R17 标出的 `source_route_retry_required=4`，尤其 local tender / fetch failed 不能 closeout 为 exhausted。
5. 重跑 R17 ledger，要求 new-contract canary 逐步转为 covered/rerouted-ready，且不新增 unclassified。

## 安全边界

- R17 ledger 是审计/控制 artifact，不是 evidence row，不得进入 ClaimCard。
- Product spec / deployment proxy / benchmark / ecosystem proxy 不得冒充产品销量、收入、ASP、份额、库存、sell-through。
- `action_required` 代表待修入口，不代表已完成或公开源不可得。
