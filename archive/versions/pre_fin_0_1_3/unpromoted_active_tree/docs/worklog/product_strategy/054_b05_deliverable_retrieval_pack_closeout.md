# B05 Deliverable / Retrieval Pack Root-Cause Closeout

## 背景

P26 已经把 ProductEvidencePack 修到 `ready`，S8 已经把 secondary-market / capital-feedback pack 修到 `ready`，但 P25 / B05 仍被两个非产品 pack 阻断：

- `deliverable_studio_pack`：S7 只有 render artifact，不证明输出是 reader-facing / customer-readable。
- `retrieval_data_refresh_pack`：P14 只有 representative control-plane drill，P25 仍按旧 policy 把 “not full crawler / production refresh” 当成 B05 blocker。

本轮遵循 root-cause-first 规则：不新增兜底 gate 来隐藏坏输出，而是修 S7 输出本身、修 P14 当前数据宇宙 refresh evidence，再让 P25/P21 读取真实状态。

## 完成内容

### S7 Deliverable Studio

- 修复 Markdown writer：不再输出 `section_intent`、`writer_boundary`、`claim_card_id` 等内部字段转储，不再出现 `## ClaimCards` 正文拼接。
- Markdown 改为 reader-facing Workpaper draft：
  - `Core Judgment`
  - 各 analyst section 的 claim_text 与短 evidence refs
  - open evidence boundary
  - evidence boundary appendix
  - gap appendix
- DOCX 改为写入 judgment、analyst sections 和 open evidence boundary，而不是只列 section 和 ClaimCard id。
- XLSX appendix 保留 claim/gap 审计信息，但列名改为 reader-facing `evidence_point` / `open_boundary`。
- 新增 deterministic customer-readable quality gates：
  - `customer_reader_markdown_no_internal_field_dump`
  - `customer_reader_markdown_has_issue_claim_gap_flow`
  - `office_artifacts_are_valid_packages`
  - S7 summary 输出 `customer_ready_editorial_quality_pass=true` 和 `editorial_acceptance_status=deterministic_customer_ready_pass`。
- 修复 gate 路径根因：质量 gate 之前读取 `artifact["uri"]` 相对仓库路径，在测试临时目录会误读仓库旧 artifact；现在读取 materialized `path`。

### P14 Data Ingestion / Retrieval Control Plane

- 新增 `current_universe_refresh_evidence_p14` SQL 表。
- P14 现在读取真实 manifest-backed current accepted universe evidence：
  - `company_public_source_coverage_matrix_v0_1.json`
  - `source_coverage_gate_summary_v0_1.json`
  - `r53_r60_p26_product_evidence_all_universe_depth_summary_v0_1.json`
  - `r53_r60_s8_secondary_market_capital_feedback_summary_v0_1.json`
  - `secondary_market_public_context_summary_v0_1.json`
  - `gold_fact_signal_mart_summary_v0_1.json`
  - `retrieval_index_registry_summary_v0_1.json`
  - `product_intelligence_graph_summary_v0_1.json`
- 新增 gate `p14_current_accepted_universe_refresh_evidence_ready`。
- P14 summary 输出 `current_universe_refresh_status=current_accepted_public_source_universe_ready`。
- P14 policy 改为区分：
  - 当前 accepted universe refresh runtime ready；
  - 不是无限互联网 crawler；
  - 不是实时刷新；
  - 不是生产 p95/p99 SLA。

### P25 / P21

- P25 `retrieval_data_refresh_pack` 不再因旧 `not_full_crawler_or_production_refresh` policy 阻断；改为要求 `current_universe_refresh_status=current_accepted_public_source_universe_ready`。
- P25 `deliverable_studio_pack` 要求 S7 `customer_ready_editorial_quality_pass=true`。
- 重建后 P25 结果：
  - `status=pass`
  - `ready_pack_count=6`
  - `blocked_pack_count=0`
  - `b05_status_after_p25=closed_by_p25_pack_depth_ready`
  - `broad_full_chain_quality_eval_allowed=true`
- 重建后 P21 结果：
  - B05 closed
  - `blocker_count_open=1/5`
  - 剩余 open blocker 是 B04 real product acceptance
  - broad full-chain broad eval 仍因 B04 不允许作为 full product pass

## 验证

- `python -m pytest tests/test_r53_r60_deliverable_studio_dashboard.py -q`
  - `4 passed`
- `python -m pytest tests/test_r53_r60_data_ingestion_retrieval_control_plane.py -q`
  - `7 passed`
- `python -m pytest tests/test_r53_r60_pack_depth_b05_gate.py -q`
  - `4 passed`
- `python scripts/engineering/build_r53_r60_s7_deliverable_studio_dashboard.py --root .`
  - `status=pass`
  - `customer_ready_editorial_quality_pass=true`
- `python scripts/engineering/build_r53_r60_p14_data_ingestion_retrieval_control_plane.py --root .`
  - `status=pass`
  - `current_universe_refresh_evidence_count=8`
  - `current_universe_refresh_status=current_accepted_public_source_universe_ready`
- `python scripts/engineering/build_r53_r60_p25_b05_pack_depth_gate.py --root .`
  - `status=pass`
  - `blocked_pack_count=0`
- `python scripts/engineering/build_r53_r60_p21_pre_full_chain_blocker_gate.py --root .`
  - B05 closed; B04 remains open

## 边界

B05 现在按 pack-depth 范围关闭，但它不等于 full product / production pass：

- S7 deterministic customer-readable pass 不等于真人最终发布批准、客户签收、RBAC 或生产 SLA。
- P14 current accepted universe refresh pass 不等于全网 crawler、实时行情刷新、云端生产 p95/p99 SLA。
- S8 public secondary-market signal pass 不等于 OPRA/CME/ICE/实时资金流/商业市场数据。
- P21 仍因 B04 `open_product_acceptance_required` 禁止把 broad full-chain 结果宣传为产品级验收。

## 2026-07-01 Source-Doc Consistency Sweep

按 source-of-truth / root-cause-first 规则，本轮又回扫了 36 源计划和 P22/P23/P24/P26 worklog，避免历史 checkpoint 被误读成当前 blocker 状态。

已更新：

- `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`
  - P21/P25 段落改为 latest/current 口径：B05 已由 P25 closeout 关闭，当前 P21 只剩 B04。
  - 早期 `blocker_count_open=2/5` 保留为 checkpoint 语义，并补 supersession。
- `docs/worklog/README.md`
  - P47/P48/P46 索引改为当前状态：B05 已关闭，B04 仍待真实产品验收。
- `docs/worklog/00_internal_master_checklist.md`
  - P21/P25 行同步为 B05 closed by P25，current full-product pass blocked by B04 only。
- `docs/worklog/product_strategy/048_p22_source_doc_status_reconciliation.md`
- `docs/worklog/product_strategy/049_p23_product_dogfood_frontend_e2e_readiness.md`
- `docs/worklog/product_strategy/050_p24_b04_product_acceptance_gate.md`
- `docs/worklog/product_strategy/053_p26_customer_deployment_root_cause_closeout.md`
  - 增加或调整 supersession/checkpoint wording，避免历史数据深度 blocker 被当作当前状态。

追加验证：

- stale wording scan:
  - scanned active docs/worklogs for stale current-state phrases implying B05 was still open.
  - no actionable matches after excluding historical checkpoint rows with explicit supersession.
- combined targeted regression:
  - `python -m pytest tests/test_r53_r60_deliverable_studio_dashboard.py tests/test_r53_r60_data_ingestion_retrieval_control_plane.py tests/test_r53_r60_pack_depth_b05_gate.py tests/test_r53_r60_pre_full_chain_blocker_gate.py -q`
  - `19 passed`
- compile:
  - `python -m py_compile src/sec_agent/r53_r60_deliverable_studio_dashboard.py src/sec_agent/r53_r60_data_ingestion_retrieval_control_plane.py src/sec_agent/r53_r60_pack_depth_b05_gate.py src/sec_agent/r53_r60_pre_full_chain_blocker_gate.py tests/test_r53_r60_deliverable_studio_dashboard.py tests/test_r53_r60_data_ingestion_retrieval_control_plane.py tests/test_r53_r60_pack_depth_b05_gate.py`
  - pass
- `git diff --check`
  - pass with existing CRLF/LF warnings only
