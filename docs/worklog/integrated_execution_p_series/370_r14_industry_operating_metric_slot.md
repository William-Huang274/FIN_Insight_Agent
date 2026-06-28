# 370 R14 Industry Operating Metric Slot

日期：2026-06-19

## Prompt

按用户给定 1-6 顺序执行第 2 步：修行业 `operating metric slot`。对金融、能源、公用事业、地产、SaaS、医疗服务等行业，不硬套 `product_revenue`，而是定义行业 KPI exact slot，例如 AUM、deposits、loan balance、capacity、utilization、MW、contracts、ARR/subscribers、patient volume 等。

## Decision

本步不放宽 Product-KPI exact gate。新增独立 `industry_operating_metric_exact_slot`：

- 可支持基本面 / 行业经营指标分析；
- 不能支持 product revenue、market share、ASP、sell-through、channel inventory、commercial tracker estimate；
- 只接受 company-disclosed value/unit/period/citation/source rows；
- 对 AUM / deposit / loan balance 使用行级口径校验，拒绝 net flows、inflows/outflows、service charges on deposit accounts 等活动或收入行。

## Work Completed

- 新增 `scripts/data_expansion/build_industry_operating_metric_slot_rows.py`。
- 新增 `tests/test_industry_operating_metric_slot_rows.py`。
- 生成：
  - `data/manifests/industry_operating_metric_slot_rows_v0_1.jsonl`
  - `data/manifests/industry_operating_metric_slot_rejections_v0_1.jsonl`
  - `data/manifests/industry_operating_metric_slot_summary_v0_1.json`
  - `docs/internal/vnext_20260610/vertical_lanes/industry_operating_metric_slot.zh-CN.md`
- 更新 `docs/architecture/agent_graph_vnext/19_source_role_product_kpi_exact_slot_deep_repair.zh-CN.md`、`docs/worklog/README.md`、`docs/worklog/00_internal_master_checklist.md`。

## Result

最新 summary：

- `runtime_row_count=1,719`
- `runtime_ticker_count=171`
- `unclassified_rejection_count=0`
- `rejection_count=7,981`

Slot counts：

- `business_segment_revenue=1,577`
- `capacity_utilization_or_production_volume=65`
- `same_store_sales_growth=34`
- `backlog_or_orders=23`
- `shipments=11`
- `unit_sales_or_deliveries=7`
- `aum=2`

样本审计发现并修复：

- `service charges on deposit accounts` 原本会误入 `deposits` 或 business segment revenue；现在拒绝。
- `net flows / inflows` 原本会因 citation 中有 AUM 表标题误入 `aum`；现在拒绝。
- 当前 `deposits=0`、`loan_balance=0` 是 strict gate 后的真实结果：当前候选里没有安全的 deposit balance / loan balance direct row。

## Verification

已运行：

```powershell
python -m pytest tests\test_industry_operating_metric_slot_rows.py -q
python -m py_compile scripts\data_expansion\build_industry_operating_metric_slot_rows.py
python scripts\data_expansion\build_industry_operating_metric_slot_rows.py --strict
```

后续合并回归在进入第 3 步前继续执行。

## Follow-Up

第 3 步开始前，运行 Step 1 + Step 2 + docket 组合回归。第 3 步为非美 local disclosure parser：DART、TWSE/MOPS、HKEX、TDnet/JP IR、深交所/上交所或公司 IR PDF 表格。
