# 21. R16 Product-KPI 与 Source Adapter 深修执行记录

更新时间：2026-06-21

## 目标

R15 已经把公开源 gap 收口为 `final_public_boundary` / `rerouted` / `not_applicable`，但其中仍有一批 Product-KPI 和 source-role 细分项不能笼统视为“公开源不可得”。R16 的目标是继续逐项深修：

- 能从公司披露表格中确认 `value/unit/period/product/citation` 的产品、品类、产品线指标，提权为 L1 exact runtime rows。
- 能支持基本面或经营判断、但不能证明 SKU / product-family 销售的业务段、经营义务、backlog 类指标，重路由为 business / operating metric。
- 仍缺 credential、assignee resolver、local filing parser 或公开披露本身没有 exact row 的项，保留 attempt-backed boundary，不伪装成补齐。

## 本轮实现

新增脚本：

- `scripts/data_expansion/build_r16_product_kpi_deep_repair_rows.py`

新增/刷新产物：

- `data/manifests/r16_product_kpi_deep_repair_runtime_rows_v0_1.jsonl`
- `data/manifests/r16_product_kpi_deep_repair_attempts_v0_1.jsonl`
- `data/manifests/r16_product_kpi_deep_repair_summary_v0_1.json`
- `docs/internal/vnext_20260610/vertical_lanes/r16_product_kpi_deep_repair.zh-CN.md`

接入入口：

- `scripts/data_expansion/build_exact_slot_coverage_matrix.py`
- `scripts/data_expansion/build_exact_slot_gap_closeout_ledger.py`
- `scripts/data_expansion/build_product_kpi_deep_gap_diagnostic.py`
- `src/sec_agent/runtime_source_context_store.py`

## Gate 规则

Product-KPI exact 只允许：

- 公司披露来源；
- 有 `value`、`unit`、`period`、`product_or_segment/row_label` 和 citation；
- 产品、品类、产品线标签明确，例如 CF fertilizer products、EL product categories、DLTR merchandise categories、CAG food categories、PTC service/product lines；
- 不是 total、geography、external-customer、percentage/change、margin、currency mismatch、non-operating 或无法绑定的句子。

Business / operating reroute 只允许：

- MET 这类 insurance premiums / fees / business-line financial metric；
- AEP 这类 future performance obligation / contracted obligation 表；
- 只进入基本面、业务 mix、经营义务分析，不允许当产品销量、ASP、份额、sell-through、SKU economics。

Boundary only：

- `PatentsView` 缺 API key 或 assignee/topic resolver 不可用；
- 非美 local disclosure parser 找到的只是 geography / mix / stale / no exact product value；
- sentence relation、column group、period/version 仍无法安全验证的候选。

## 最新结果

R16 strict：

- `runtime_row_count=76`
- `runtime_ticker_count=8`
- `product_kpi_exact_repair_row_count=52`
- `business_segment_metric_repair_row_count=12`
- `operating_metric_repair_row_count=12`
- `attempt_row_count=1088`
- `unclassified_attempt_count=0`

下游矩阵刷新：

- `exact_slot_coverage_matrix` validation `pass`
- `all_required_exact_ready_company_count=503`
- `partial_exact_ready_company_count=100`
- `no_exact_ready_company_count=0`
- `exact_slot_gap_count=108`

Product-KPI closeout：

- `product_kpi_exact_ready_ticker_count=172`
- `business_segment_metric_ready_ticker_count=52`
- `product_or_business_kpi_ready_ticker_count=224`
- `product_kpi_gap_count=369`
- `unclassified_closeout_count=0`

Product-KPI deep diagnostic：

- `product_family_exact_ready_ticker_count=134`
- `business_or_segment_exact_ready_ticker_count=90`
- `product_or_business_kpi_ready_ticker_count=224`
- `no_candidate_gap_ticker_count=105`
- `strict_candidate_gap_ticker_count=264`
- `unclassified_count=0`

两个 Product-KPI 口径差异保留：closeout 按 exact-slot / runtime summary 综合判断；deep diagnostic 按产品 family exact 与 business/segment 分桶做细分审计。后续报告应优先用 closeout 判断“是否有可用披露”，用 diagnostic 判断“具体缺口类型”。

## 仍不能提权的主要原因

- 公司公开披露没有产品级 exact row：只有产品页、taxonomy、业务描述、region-only、percentage/change 或 generic segment row。
- 有候选但不能安全绑定：column group 未能确认、sentence local relation 未验证、period/version 与当前期指标冲突。
- 需要行业 operating slot 而不是 Product-KPI：AUM、deposit、loan balance、capacity、utilization、contracted obligation、MW、patient volume 等应进入行业经营指标层。
- 需要 credential / 更细 resolver：PatentsView key、assignee/topic resolver、部分 local exchange / IR PDF table parser。

## 验收

已运行：

```powershell
python scripts/data_expansion/build_r16_product_kpi_deep_repair_rows.py --strict
python scripts/data_expansion/build_exact_slot_coverage_matrix.py
python scripts/data_expansion/build_exact_slot_gap_closeout_ledger.py --strict
python scripts/data_expansion/build_product_kpi_deep_gap_diagnostic.py --strict
python -m pytest tests/test_r16_product_kpi_deep_repair_rows.py -q
python -m py_compile scripts/data_expansion/build_r16_product_kpi_deep_repair_rows.py scripts/data_expansion/build_exact_slot_coverage_matrix.py scripts/data_expansion/build_exact_slot_gap_closeout_ledger.py scripts/data_expansion/build_product_kpi_deep_gap_diagnostic.py src/sec_agent/runtime_source_context_store.py
```

通过条件：

- R16 `unclassified_attempt_count=0`
- Exact-slot validation `pass`
- Closeout strict `pass`
- Product-KPI diagnostic strict `pass`
- R16 deterministic tests `4 passed`

## 后续

R16 后仍不是“所有公司都有产品级披露 KPI”。下一阶段如果继续补，只应从三类真实边界推进：

- company IR deck / annual report / local exchange PDF table parser 深挖；
- industry operating metric slot 继续完善，把非 product revenue 的 disclosed operating facts 纳入基本面模型；
- PatentsView / official patent API credential 与 assignee resolver 建成后补技术 proxy，但仍不得支持收入、订单、销量或份额 claim。
