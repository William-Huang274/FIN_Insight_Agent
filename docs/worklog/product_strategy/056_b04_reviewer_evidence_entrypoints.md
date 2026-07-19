# B04 Reviewer Evidence Entrypoints

## 背景

055 已经把 B04 从“summary 字段可被手写关闭”修成 manifest-backed closeout，但还留下一个操作性缺口：真实 reviewer 如果要提交验收证据，只能手工编辑 `r53_r60_p24_b04_real_reviewer_acceptance_evidence_v0_1.jsonl`。这不符合企业级验收流程，也容易造成证据格式不一致。

本轮目标是补正式写入入口，同时保持 B04 的严边界：入口可以记录真实证据，但不能由 automation 冒充人工验收，也不能用不完整证据关闭 B04。

## 完成内容

### Runtime contract

- `src/sec_agent/r53_r60_product_acceptance_b04_gate.py`
  - 新增 `validate_real_reviewer_acceptance_evidence`。
  - 新增 `append_real_reviewer_acceptance_evidence`。
  - 新增 `get_product_acceptance_evidence_status`。
  - `p24_schema_contract` 新增 reviewer evidence entrypoints。
  - `render_p24_report` 改为按 accepted / pending 状态动态写边界说明，避免未来真实验收通过后 report 仍显示“P24 不关闭 B04”的静态错误。

入口只接受：

- `action_source=real_human`。
- reviewer role 属于 `lead_analyst` / `portfolio_manager` / `senior_research_reviewer` / `product_owner`。
- evidence type 属于 `reviewer_session` / `deliverable_acceptance` / `defect_closeout` / `visual_acceptance` / `audit_replay`。
- `defect_closeout` 必须逐条覆盖 `source_id` 或 `covered_source_ids`。
- `deliverable_acceptance` 必须有 `accepted/rejected`、deliverable ref、artifact ref 和 reviewer comment。

### Workbench API

- `apps/workbench/backend/app.py`
  - 新增 `GET /api/r53-r60/product-acceptance/evidence`。
  - 新增 `POST /api/r53-r60/product-acceptance/evidence`。

API 返回当前 evidence ledger、P24 summary、pending human requirements、pending defect source ids 和可接受的 role/status/type 列表。

### CLI

- 新增 `scripts/engineering/record_r53_r60_p24_b04_reviewer_acceptance_evidence.py`。

这个 CLI 写入同一个 reviewer evidence ledger，适合没有前端 UI 时的真实 reviewer / product owner 操作。

### Workbench UI follow-up

057 已把同一个 evidence API 接入 R53-R60 Workbench：

- 新增 `Product acceptance evidence` 面板。
- 页面加载时读取当前 B04 evidence ledger / pending requirements。
- 表单按 evidence type 只提交相关字段，再由后端 runtime contract 做最终校验。
- P24 browser label gate 已新增 `Product acceptance evidence`，避免 API 已有但页面无入口时误判。

## 验证

- `python -m pytest tests/test_r53_r60_product_acceptance_b04_gate.py tests/test_r53_r60_pre_full_chain_blocker_gate.py -q`
  - `10 passed`
- `python -m pytest tests/test_workbench_backend.py::test_workbench_backend_records_b04_product_acceptance_evidence -q`
  - `1 passed`
- `python -m py_compile src/sec_agent/r53_r60_product_acceptance_b04_gate.py apps/workbench/backend/app.py scripts/engineering/record_r53_r60_p24_b04_reviewer_acceptance_evidence.py tests/test_r53_r60_product_acceptance_b04_gate.py tests/test_workbench_backend.py`
  - pass
- `python scripts/engineering/record_r53_r60_p24_b04_reviewer_acceptance_evidence.py --help`
  - pass
- `python scripts/engineering/build_r53_r60_p24_b04_product_acceptance_gate.py --root .`
  - `status=pass_with_real_human_acceptance_blocked`
  - `browser_e2e_count=10`
  - `gate_fail_count=0`
  - `real_reviewer_evidence_row_count=0`
- `python scripts/engineering/build_r53_r60_p21_pre_full_chain_blocker_gate.py --root .`
  - `blocker_count_open=1`
  - `full_chain_broad_eval_allowed=false`

## 当前边界

这轮不关闭 B04。当前仓库仍没有真实 reviewer evidence ledger，因此 P24/P21 的实际状态仍应保持：

- P24: `pass_with_real_human_acceptance_blocked`
- B04: `open_product_acceptance_required`

如果后续 reviewer 通过 API/CLI 提交完整五类 evidence，再重建 P24/P21，B04 才允许关闭。

2026-07-01 follow-up：后续 reviewer 也可以直接通过 Workbench `Product acceptance evidence` 面板提交同一类证据；这仍不代表 B04 已关闭。
