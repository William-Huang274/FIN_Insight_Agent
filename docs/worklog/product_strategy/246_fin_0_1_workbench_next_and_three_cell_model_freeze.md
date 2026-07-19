# FIN 0.1 Workbench Next 与三-cell 模型纵向冻结

日期：2026-07-19

## 问题与目标

用户确认新的 agent-first Workbench 蓝图后，要求先把可持续运行的前端落到现有产品，再执行：真实本地 RAG/SQL/Graph/official retrieval -> parser/numeric -> Evidence Gate -> Domain Judgment -> Repair/LeadReview -> Writer no-source -> Workbench -> Human Senior Review。

本轮先完成前端产品化和模型执行前冻结。付费 DeepSeek 调用仍需显式确认，没有在普通测试或页面加载中自动触发。

## 决策

1. 不创建第二套后端。新界面沿用现有 React/Vite 与 `/api/v1`，通过 `/next` 独立路由提供迁移、对照和回滚边界。
2. 前端显示结构化 agent event stream，不展示或持久化模型隐藏思维链。
3. 真实本地 retrieval/parser/numeric/Evidence Gate 继续作为确定性上游；只用 DeepSeek 替换三-cell Domain Judgment、LeadReview/一次 bounded repair、Writer no-source。
4. DeepSeek 采用当前官方 `deepseek-v4-pro`，不再使用 2026-07-24 将停用的 `deepseek-chat/reasoner` 别名。
5. paid model vertical 固定为 1 次极小 provider preflight + 3 次语义调用；每次最多一次 transport attempt，总费用硬上限 USD 0.05。Provider 失败时不得进入 Domain；Writer 输入采用白名单投影，不含原始 cells/candidates/excerpts/citation URLs。
6. 输出仅写 `.codex_runtime/fin0.1-real-run/<run_id>`；canonical Case、Evidence promotion、真实业务 Case mutation和 release admission 均为 0。

## 已完成

### 可运行前端

- 新增 `apps/workbench/frontend/vite/src/app/WorkbenchNext.tsx`。
- 新增 `apps/workbench/frontend/vite/src/app/workbench-next.css`。
- `AppShell.tsx` 增加 `/next` 路由入口，旧产品路径不移除。
- 可用路由：`/next/tasks`、`/next/cases/:id/run`、`evidence`、`workpaper`、`report`、`review`、`inspect`。
- 页面接入当前 Case、local research、local analysis、Evidence、Numeric、Workpaper、Deliverable、Trace 与 Human Baseline 读模型；缺失的可选对象以 typed empty state 呈现。
- Run composer 保持未准入；Human Review 写入只在用户明确点击时发生。

### 三-cell 模型纵向冻结

- 当前合同：`configs/releases/fin_ia_0_1_p36_three_cell_deepseek_vertical_contract_v1_1.json`；v1.0 保留为没有单列 provider preflight 的历史冻结版本。
- Runner：`scripts/releases/run_fin_ia_0_1_p36_three_cell_deepseek_vertical.py`。
- 合同测试：`tests/contract/test_fin_0_1_p36_three_cell_deepseek_vertical.py`。
- 当前 freeze artifact：`.codex_runtime/fin0.1-real-run/20260719T061323Z_p36_three_cell_deepseek_v4_pro_internal_r1/`。
- 当前 contract digest：`0b532c336376ef8ecfe6f774b5854000a96f26f079dabe8f276817a127da47e1`。
- exact binding：research digest `aa792b86fa5aed152ba38352eec54b08b8ad5a3603a553c57a66260eb389b093`；analysis digest `9d47aa3b29db35839dd6aea10974747777dbf72177e7e54db5c4c9fb4311ee50`；input digest `737080b114fd8f9368238f711c8ea224035af13e4f4fee5e9e45e9b4ae66730b`。
- frozen scope：`demand_signal`、`revenue_capture`、`thesis_counterevidence`，共 10 条候选证据、3 个 exact facts 和 2 个 derived metrics。
- freeze execution counts：model/network model/canonical Case write/evidence promotion/business Case mutation 均为 0。

### 运行前检查适用性

- Project OS scoped preflight：`pass`，artifact 为 `.codex_runtime/fin0.1-real-run/p36_three_cell_project_os_preflight_v1_1.json`，open full-chain blockers=0。
- token/cost preflight：Runner 在每次调用前以 UTF-8 bytes 作为保守 input-token 上界，并把已发生费用与最大输出费用一并对照 USD 0.05 cap；不满足时调用前停止。
- provider preflight：属于获批运行的一部分，只允许 1 次 24-token DeepSeek 连通性调用；失败后不进入三次语义调用。
- evidence-mode preflight：freeze-only 要求 Case、research digest、analysis digest、三-cell roles、候选未 promotion 和 zero-write boundary 全部精确匹配。
- AIE / data-script preflight：本执行包没有 AIE scoring、数据脚本或新数据处理阶段，记为 `not_applicable_to_this_three_stage_model_vertical`，不得借机扩为 broad full-chain。

## 验证

- TypeScript strict：pass。
- Vite production build：pass，1695 modules；chunk-size warning 作为 P3 code-splitting debt。
- Next、durable frontend 与三-cell模型合同联合回归：14 passed。
- 三-cell模型合同单独：6 passed；包含成功时严格 1+3 调用、provider 失败时只记 1 次并停止的模拟回归。
- Chrome 1600x1000 与 390x844：无页面级横向溢出；Task、Run、Evidence、Workpaper、Report、Review、Inspect 路由与中英文切换通过；console errors=0。
- `git diff --check`：pass，现有 `AppShell.tsx` 仅有 line-ending warning。

## 当前状态与下一步

- `workbench_next=implemented_internal_alpha`。
- `three_cell_model_vertical=frozen_pending_explicit_paid_llm_approval`。
- `human_senior_review=not_started_for_model_vertical`。
- `RG1/RG3/RG4/P07.5` 状态未改变，`production_readiness=not_admitted`。

显式批准后，Runner 将进行且仅进行 1 次 provider preflight 与 3 次语义 DeepSeek 调用，写入非 canonical artifact；每次调用后都会持久记录调用数、费用和停止点。完成后需把 exact model artifact 投影到 `/next` 并由用户完成 Human Senior Review。任何调用失败都停止，不自动重试或扩展为 full-chain。
