# B04 Product Acceptance Manifest Hardening

## 背景

P24 已经有真实浏览器 E2E、reviewer acceptance protocol、human evidence requirements 和 defect closeout requirements，但原先 P21 关闭 B04 的测试路径允许“只写 P24 summary 字段”来模拟真实人工验收。这不符合 root-cause-first 规则：summary 是派生结果，不应该成为关闭产品验收 blocker 的唯一证据。

本轮目标是修掉这个上游合同缺口，而不是再加一个外层 gate 兜底。

## 完成内容

### P24 reviewer evidence ledger

- 在 `src/sec_agent/r53_r60_product_acceptance_b04_gate.py` 中新增 reviewer evidence input：
  - `data/manifests/r53_r60_p24_b04_real_reviewer_acceptance_evidence_v0_1.jsonl`
- B04 real acceptance 只接受 `action_source=real_human` 且 `reviewer_role` 属于允许角色：
  - `lead_analyst`
  - `portfolio_manager`
  - `senior_research_reviewer`
  - `product_owner`
- P24 现在从 evidence ledger 推导：
  - `reviewer_session`
  - `deliverable_acceptance`
  - `defect_closeout`
  - `visual_acceptance`
  - `audit_replay`
- 缺陷关闭必须逐条覆盖 `source_id` / `covered_source_ids`，不能一句话声明“所有缺陷已关”。

### P24 summary derivation

- 默认无真实 evidence ledger 时行为不变：
  - `status=pass_with_real_human_acceptance_blocked`
  - `product_acceptance_status=pending_real_human_acceptance`
  - `b04_status_after_p24=open_product_acceptance_required`
- 只有当 human evidence 全 complete、defect closeout 全 closed、且存在 accepted deliverable decision 时，P24 才会生成：
  - `status=pass`
  - `release_decision=P24_b04_real_human_product_acceptance_complete`
  - `closeout_level=L4_scope_pass_for_real_human_product_acceptance`
  - `product_acceptance_status=accepted_by_real_human_review`
  - `b04_status_after_p24=closed_by_real_human_product_acceptance`

### P21 manifest-backed closure

- `src/sec_agent/r53_r60_pre_full_chain_blocker_gate.py` 新增 `p24_manifest_acceptance` 校验。
- P21 关闭 B04 时不再只检查 P24 summary，还必须读取并校验：
  - `r53_r60_p24_b04_human_evidence_requirements_v0_1.jsonl`
  - `r53_r60_p24_b04_defect_closeout_requirements_v0_1.jsonl`
  - `r53_r60_p24_b04_acceptance_decision_rows_v0_1.jsonl`
  - `r53_r60_p24_b04_product_acceptance_gate_rows_v0_1.jsonl`
- 如果有人手写 summary，但没有行级 evidence，P21 保持 `B04=open_product_acceptance_required`。

## 当前真实结果

在当前仓库没有真实 reviewer evidence ledger 的情况下，重建 P24/P21 后结果符合预期：

- P24:
  - `browser_e2e_status=pass`
  - `real_reviewer_evidence_row_count=0`
  - `human_evidence_pending_count=5`
  - `defect_closeout_pending_count=8`
  - `b04_status_after_p24=open_product_acceptance_required`
- P21:
  - `blocker_count_open=1`
  - B04 status: `open_product_acceptance_required`
  - `p24_manifest_acceptance.valid=false`

## 验证

- `python -m pytest tests/test_r53_r60_product_acceptance_b04_gate.py tests/test_r53_r60_pre_full_chain_blocker_gate.py -q`
  - `10 passed`
- `python -m pytest tests/test_r53_r60_deliverable_studio_dashboard.py tests/test_r53_r60_data_ingestion_retrieval_control_plane.py tests/test_r53_r60_pack_depth_b05_gate.py tests/test_r53_r60_pre_full_chain_blocker_gate.py tests/test_r53_r60_product_acceptance_b04_gate.py -q`
  - `24 passed`
- `python -m py_compile src/sec_agent/r53_r60_product_acceptance_b04_gate.py src/sec_agent/r53_r60_pre_full_chain_blocker_gate.py scripts/engineering/build_r53_r60_p24_b04_product_acceptance_gate.py tests/test_r53_r60_product_acceptance_b04_gate.py`
  - pass
- `python scripts/engineering/build_r53_r60_p24_b04_product_acceptance_gate.py --root .`
  - `status=pass_with_real_human_acceptance_blocked`
  - `gate_fail_count=0`
- `python scripts/engineering/build_r53_r60_p21_pre_full_chain_blocker_gate.py --root .`
  - `blocker_count_open=1`

## 边界

这轮没有伪造真实人工验收，也不关闭 B04。它修的是 B04 closing contract 的根因缺口：以后 B04 只能由真实 reviewer evidence ledger 和派生行级 evidence 关闭，不能靠手工 summary 或自动化 E2E 冒充。

2026-07-01 follow-up：未来 UI/API action ledger 已落地为正式入口：

- Python function: `sec_agent.r53_r60_product_acceptance_b04_gate.append_real_reviewer_acceptance_evidence`
- Workbench API:
  - `GET /api/r53-r60/product-acceptance/evidence`
  - `POST /api/r53-r60/product-acceptance/evidence`
- CLI: `scripts/engineering/record_r53_r60_p24_b04_reviewer_acceptance_evidence.py`

下一步如果要真正关闭 B04，需要用户或指定 reviewer 完成真实 Workbench review session，并通过上述入口写入 `reviewer_session`、`deliverable_acceptance`、`defect_closeout`、`visual_acceptance`、`audit_replay` 五类证据。当前没有伪造这些 evidence，所以 B04 仍保持打开。
