# B04 Workbench Reviewer Evidence UI

## 背景

056 已经补齐 B04 真实 reviewer evidence 的 runtime / API / CLI 写入入口，但 Workbench 前端还没有面向 reviewer 的显式录入面板。这样虽然不再需要手工改 JSONL，但真实产品验收仍需要绕过工作台使用 API/CLI，不符合 B 端产品验收和审计流程。

本轮目标是把 `GET/POST /api/r53-r60/product-acceptance/evidence` 接到 R53-R60 Workbench，同时继续保持 B04 严边界：UI 可以记录真实 reviewer evidence，但不能把自动化、空字段或不完整 evidence 冒充为产品验收通过。

## 完成内容

- `apps/workbench/frontend/vite/src/main.tsx`
  - 新增 `R53R60ProductAcceptanceEvidence` / `R53R60AcceptanceEvidenceForm` 类型。
  - R53-R60 Workbench 首屏并行加载 `/api/r53-r60/product-acceptance/evidence`。
  - 新增 `Product acceptance evidence` 面板，展示 B04 状态、真实 evidence row 数、pending human requirements、pending defect source ids。
  - 新增 evidence type aware 表单：`reviewer_session`、`deliverable_acceptance`、`defect_closeout`、`visual_acceptance`、`audit_replay` 只提交当前类型相关字段。
  - 提交时统一写入后端 B04 evidence API；后端 runtime contract 继续负责最终校验。
- `apps/workbench/frontend/vite/src/workbench.css`
  - 新增产品验收面板布局和移动端折叠规则。
- `src/sec_agent/r53_r60_product_acceptance_b04_gate.py`
  - P24 browser label gate 新增 `Product acceptance evidence`，防止 API 已存在但页面没有入口时误判通过。
- `tests/test_r53_r60_product_dogfood_frontend_e2e.py`
  - 更新前端 fixture，保持 P23/P24 label contract 与真实页面一致。

## 验证

- 前端构建：
  - `node node_modules/typescript/bin/tsc -p tsconfig.json`
  - `node node_modules/vite/bin/vite.js build --config vite.config.ts`
  - pass
- `python -m pytest tests/test_r53_r60_product_dogfood_frontend_e2e.py tests/test_r53_r60_product_acceptance_b04_gate.py -q`
  - `10 passed`
- `python -m pytest tests/test_workbench_backend.py::test_workbench_backend_records_b04_product_acceptance_evidence -q`
  - `1 passed`
- `python scripts/engineering/build_r53_r60_p24_b04_product_acceptance_gate.py --root .`
  - `status=pass_with_real_human_acceptance_blocked`
  - `browser_e2e_count=10`
  - `browser_e2e_fail_count=0`
  - `gate_fail_count=0`
  - `real_reviewer_evidence_row_count=0`
- `python scripts/engineering/build_r53_r60_p21_pre_full_chain_blocker_gate.py --root .`
  - `blocker_count_open=1`
  - `full_chain_broad_eval_allowed=false`
- 浏览器截图：
  - `reports/r53_r60_p24_b04_product_acceptance_browser_e2e/p24_b04_workbench_desktop.png`
  - `reports/r53_r60_p24_b04_product_acceptance_browser_e2e/p24_b04_workbench_mobile.png`

## 当前边界

这轮仍不关闭 B04。当前状态正确保持为：

- P24: `pass_with_real_human_acceptance_blocked`
- B04: `open_product_acceptance_required`
- P21: `blocker_count_open=1`

原因是仓库仍没有真实 reviewer 通过 Workbench/API/CLI 提交完整验收证据。后续只有真实 reviewer 完成 session、deliverable 接受/拒绝、defect closeout、visual acceptance 和 audit replay 后，P24/P21 才能把 B04 关闭。
