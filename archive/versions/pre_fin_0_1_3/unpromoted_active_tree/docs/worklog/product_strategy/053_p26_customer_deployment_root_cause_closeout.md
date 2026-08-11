# P26 CustomerDeployment Root-Cause Closeout

## 背景

P26 初始分层后，Product Profile / Spec / Relationship 已可用，Product-KPI exact `160` 被正确限定为 exact-claim scope，CapitalMarketDetail `2` 被转入 capital/funding pack；真正阻断 ProductEvidence broad-quality 的只剩 CustomerDeployment `72`。按 root-cause-first 规则，本轮不能用 full-chain case 或弱 gate 隐藏这个缺口，而要先检查是不是 parser/source-route 没吃到公开可得数据。

## 修复内容

### 1. Non-US operating footprint route

- 将 `non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl` 纳入 CustomerDeployment depth 输入。
- Gate 仍然只接受经营 footprint：orders/backlog、capacity/production、shipments、delivery、AUM、customer count 等。
- Product revenue、segment revenue、gross margin、ordinary financial rows 仍不进入 CustomerDeployment。

### 2. Filing operating-footprint parser

- 新增 `scripts/data_expansion/build_filing_operating_footprint_context_rows.py`。
- 对剩余 SEC/FPI 缺口抽取 issuer-bound operating footprint rows：
  - `LNT`: IPL/WPL electric/gas retail customer counts。
  - `STLD`: sheet steel production and division shipment rows。
  - `BHP`: copper / iron ore production rows。
- 输出：
  - `data/manifests/filing_operating_footprint_context_rows_v0_1.jsonl`
  - `data/manifests/filing_operating_footprint_context_rejections_v0_1.jsonl`
  - `data/manifests/filing_operating_footprint_context_summary_v0_1.json`

### 3. Verified official customer/deployment seeds

- 在 `build_official_customer_deployment_surface_context_rows.py` 中补 verified official seeds：
  - `000660.KS`: SK hynix official newsroom NVIDIA multi-year technology partnership。
  - `300750.SZ`: CATL official Stellantis LFP battery plant JV。
  - `300750.SZ`: CATL official AITO embedded manufacturing / local supply。
- 保持 official-host verification，不允许 manual seed 绕过 issuer official-domain gate。
- 修复 `_extract_counterparty()`，对官方新闻标题/正文提取 `NVIDIA`、`Stellantis`、`AITO` 等 counterparty。
- 修复 `_dedupe_rows()`，同一 issuer/source/role 下优先保留 counterparty binding 更完整的 row，避免旧空绑定 row 遮蔽新证据。

## 最新真实结果

Depth matrix:

- ProductSpec depth: `603/603`
- Product/Business-KPI exact depth: `443/603`
- CustomerDeployment depth: `603/603`
- CapitalMarketDetail depth: `601/603`
- MarketLiquidity depth: `603/603`

P26:

- `status=pass`
- `product_pack_readiness_status=ready`
- `broad_full_chain_product_pack_ready=true`
- `blocking_gap_count=0`
- `blocking_gap_ids=[]`
- Remaining Product-KPI exact `160` is exact-claim scope only.
- Remaining CapitalMarketDetail `2` is capital/funding pack scope only.

P25 at this P26 closeout checkpoint:

- `status=pass_with_pack_depth_blockers_registered`
- `ready_pack_count=3`
- `blocked_pack_count=3`
- ProductEvidence all-universe pack is now `ready`.
- At this checkpoint, B05 remained open because three non-product packs were still blocked:
  - `secondary_market_capital_feedback_pack`
  - `deliverable_studio_pack`
  - `retrieval_data_refresh_pack`

2026-07-01 supersession: the later B05 closeout repaired those three non-product blockers at root cause. Current P25 is `status=pass`, `ready_pack_count=6`, `blocked_pack_count=0`, `b05_status_after_p25=closed_by_p25_pack_depth_ready`; current P21 has only B04 open.

## 验证

- `python scripts\data_expansion\build_filing_operating_footprint_context_rows.py --ticker 000660.KS,300750.SZ,373220.KS,BHP,LNT,STLD`
  - `runtime_row_count=10`
  - covered `BHP`, `LNT`, `STLD`
- `python scripts\data_expansion\build_official_customer_deployment_surface_context_rows.py --tickers 000660.KS 300750.SZ --max-candidates-per-ticker 2 --workers 2 --timeout-s 20`
  - official rows verified for SK hynix / NVIDIA, CATL / Stellantis, CATL / AITO.
- `python scripts\data_expansion\build_second_third_layer_depth_parity_matrix.py`
  - CustomerDeployment `603/603`
- `python scripts\engineering\build_r53_r60_p26_product_evidence_all_universe_depth_gate.py`
  - P26 pass
- `python scripts\engineering\build_r53_r60_p25_b05_pack_depth_gate.py`
  - At this checkpoint, P25 blocked only three non-product packs. Later B05 closeout rerun made P25 `blocked_pack_count=0`.

## 当前边界

1. Product-KPI exact remains strict. Product specs、architecture、customer adoption、operating footprint can support bounded product thesis, but cannot be rewritten as product revenue、shipment、ASP、market share、sell-through、backlog, or order value unless value/unit/period/product/citation exists.
2. CustomerDeployment closeout is not based on ordinary revenue/segment rows. It is based on issuer-bound official deployment/adoption/partnership rows and operating-footprint rows.
3. At this checkpoint, broad full-chain quality eval was still blocked at B05 by secondary-market capital feedback, deliverable editorial acceptance, and retrieval/data refresh. Supersession: those blockers were later closed in `054_b05_deliverable_retrieval_pack_closeout.md`; current broad full-chain product pass is blocked by B04 only.

## 下一步

This checkpoint is superseded for B05 by `054_b05_deliverable_retrieval_pack_closeout.md`. Do not rerun broad 20-50 case full-chain quality evaluation as a full product pass until B04 real product acceptance closes.

1. `secondary_market_capital_feedback_pack`: credit funding, derivatives, valuation price-in, positioning/fund-flow role coverage or explicit public/commercial boundary.
2. `deliverable_studio_pack`: real customer-ready editorial accept/reject evidence and defect closeout.
3. `retrieval_data_refresh_pack`: production-like crawler/parser/index refresh with lineage, qrels, recall/rerank probes, and performance metrics.
