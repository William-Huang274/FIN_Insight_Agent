# 060 P29 B04 Reviewer Package Workbench Surface

## 背景

B04 的真实人工验收不能由自动化、summary 字段或 template 行替代。P27 已经生成真实 reviewer 所需的执行包，包括 reviewer steps、template-only evidence rows、task/artifact/trace candidate refs 和人读报告；P28 又补了 session readiness，能告诉 reviewer 同一 session 还缺哪些证据。

但在 P28 之后，P27 执行包主要仍停留在文件系统里。真实 reviewer 在 Workbench 中只能看到 evidence 表单和 session readiness，看不到“应该按什么步骤审、用哪些模板、有哪些候选任务/产物/trace 可以引用”。这会让 B04 的真实验收仍然依赖人工翻文件，不符合企业级可操作验收入口。

## 决策

P29 不写入真实 reviewer evidence，也不关闭 B04。它只把 P27 package 作为只读运行面暴露到 Workbench/API，让真实 reviewer 可以从同一产品验收面板读取：

- reviewer execution steps；
- evidence templates；
- runtime task/artifact/trace candidate refs；
- P27 report path 和 package status。

B04 关闭条件不变：必须由真实 reviewer 提交完整 evidence，P24 从同一 ready session 派生 accepted deliverable / defect closeout / audit evidence，随后 P21 验证 manifest acceptance 后才允许关闭。

## 完成内容

- `src/sec_agent/r53_r60_b04_reviewer_acceptance_package.py`
  - 新增 `get_b04_reviewer_acceptance_package(root)`。
  - 读取 P27 package、step rows、evidence template rows、candidate refs 和 report path。
  - 返回 `package_exists`，避免 UI 把缺失包误读成 B04 关闭。

- `apps/workbench/backend/app.py`
  - 新增 `GET /api/r53-r60/product-acceptance/reviewer-package`。
  - 该接口只读 P27 执行包，不写 evidence ledger。

- `apps/workbench/frontend/vite/src/main.tsx`
  - `loadR53R60Workbench` 和 `loadR53R60ProductAcceptanceEvidence` 同步读取 reviewer package。
  - `Product acceptance evidence` 面板新增 reviewer package summary、candidate refs、reviewer execution steps、evidence templates 和 candidate refs 表。
  - evidence 表单仍保留真实 reviewer 写入入口；package rows 仍是 template/candidate，不被当成 acceptance evidence。

- `tests/test_r53_r60_b04_reviewer_acceptance_package.py`
  - 覆盖 runtime helper 能读取 P27 包和行级 artifact。

- `tests/test_workbench_backend.py`
  - 覆盖 Workbench reviewer package API 返回 package、step rows、template rows、candidate refs。

## 验证

- `python -m pytest tests/test_r53_r60_b04_reviewer_acceptance_package.py tests/test_workbench_backend.py -q -k "reviewer_acceptance_package or product_acceptance"`：`3 passed, 32 deselected`。
- `C:\Users\hht13\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe node_modules/typescript/bin/tsc -p tsconfig.json`：通过。
- `C:\Users\hht13\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe node_modules/vite/bin/vite.js build --config vite.config.ts`：通过。
- `python -m pytest tests/test_r53_r60_product_dogfood_frontend_e2e.py -q`：`4 passed`。

## 当前状态

- B04：仍为 `open_product_acceptance_required`。
- P27 package：可通过 Workbench API / 前端读取。
- 真实 reviewer evidence：仍为 `0`，未伪造。
- P21：仍应保持 broad full-chain product pass blocked，直到真实 reviewer evidence 完整提交并由 P24/P21 重跑关闭。

## 后续

下一步如果继续推进 B04，只能进入真实人工 dogfood / reviewer acceptance：

1. 真实 reviewer 通过 Workbench 查看 P27 package 和候选 refs。
2. 对至少一个 session 提交 `reviewer_session`、`deliverable_acceptance`、`visual_acceptance`、`audit_replay` 和全部 P24 defect closeout evidence。
3. 重跑 P24 / P21，确认 B04 只从同一 ready session 的 manifest-backed evidence 关闭。
