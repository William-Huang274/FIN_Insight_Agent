# P28 / B04 Acceptance Session Readiness

## 背景

P24/P27 已经把真实 reviewer evidence 的写入入口、Workbench 面板和 reviewer 执行包补齐，但 reviewer 仍需要自己判断同一个 session 是否已经覆盖五类必需证据、是否有 accepted deliverable、是否关闭了所有 P24 defect source ids。这个缺口不是外部数据问题，而是产品验收操作链路的可解释性不足：如果不补，真实 reviewer 很容易提交几条 evidence 后仍不知道为什么 B04 不能关闭。

本轮目标是补 `session-level readiness`，只作为真实 reviewer 的操作闭环和 P24/P21 的可解释输入，不放宽 B04 关闭条件，不伪造真实验收。

## 完成内容

- `src/sec_agent/r53_r60_product_acceptance_b04_gate.py`
  - 新增 `session_readiness_rows`。
  - 按 `session_id` 聚合真实 reviewer evidence，检查：
    - `reviewer_session`
    - `deliverable_acceptance`
    - `defect_closeout`
    - `visual_acceptance`
    - `audit_replay`
  - 额外要求同一 session 至少有 accepted deliverable，并覆盖当前 P24 defect source ids。
  - `get_product_acceptance_evidence_status` 现在返回：
    - `counts.session_count`
    - `counts.ready_session_count`
    - `pending.human_requirements` 完整 requirement rows
    - `pending.human_requirement_ids`
    - `session_readiness.sessions`
    - `session_readiness.ready_sessions`
  - 收紧 `acceptance_decision_rows`：B04 acceptance decision 必须来自同一个 `ready_for_p24_p21_rerun` session 的 accepted deliverable，不能用多个不同 session 的证据拼出全局 complete。
  - 修复前端读取 `pending.human_requirements` 时拿到 ID 列表而不是对象行的问题。
- `src/sec_agent/r53_r60_b04_reviewer_acceptance_package.py`
  - P27 package counts 增加 `reviewer_session_count` 和 `ready_reviewer_session_count`。
- `apps/workbench/frontend/vite/src/main.tsx`
  - `Product acceptance evidence` 面板新增 `Ready sessions` 指标。
  - 新增 `Session readiness` 表格，显示 session、reviewer role、closeout status、缺失 evidence 类型和未关闭缺陷数。
  - `Recent evidence rows` 改用真实 `status` 字段，避免显示不存在的 `evidence_status`。
  - pending human requirements 现在展示 requirement id 和 evidence type。
- `tests/test_r53_r60_product_acceptance_b04_gate.py`
  - 新增不完整 session 的 readiness 回归。
  - 新增完整五类 evidence + defect coverage 后 session ready 的回归。
  - 新增跨 session evidence mix 不得关闭 B04 的回归。
- `tests/test_workbench_backend.py`
  - 后端 GET evidence API 回归新增 session readiness 字段断言。

## 验证

- `python -m pytest tests/test_r53_r60_product_acceptance_b04_gate.py -q`
  - `9 passed`
- `python -m pytest tests/test_workbench_backend.py -q -k "product_acceptance_evidence"`
  - `1 passed, 32 deselected`
- `python -m py_compile src/sec_agent/r53_r60_product_acceptance_b04_gate.py apps/workbench/backend/app.py`
  - pass
- frontend TypeScript:
  - `node node_modules/typescript/bin/tsc -p tsconfig.json`
  - pass
- frontend Vite build:
  - `node node_modules/vite/bin/vite.js build --config vite.config.ts`
  - pass

## 当前边界

P28 不关闭 B04。它只把“真实 reviewer 已提交哪些证据、同一 session 还缺什么、是否可以重跑 P24/P21”做成机器可读状态。

当前仓库仍没有真实 reviewer evidence ledger：

- `data/manifests/r53_r60_p24_b04_real_reviewer_acceptance_evidence_v0_1.jsonl` 不存在；
- `B04=open_product_acceptance_required`；
- 后续仍需要真实 reviewer 完成 Workbench review session、accepted/rejected deliverable、defect closeout、visual acceptance 和 audit replay，再重跑 P24/P21。
