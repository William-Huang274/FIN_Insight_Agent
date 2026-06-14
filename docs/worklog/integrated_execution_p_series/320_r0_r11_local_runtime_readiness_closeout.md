# 320 - R0-R11 Local Runtime Readiness Closeout

日期：2026-06-14

## 背景

用户要求按 `13_09_11_remaining_full_completion_plan.zh-CN.md` 执行 `R0-R11`，目标不是最小闭环，而是本地可验收的落地版本；云端暂不开，因云端和 Milvus 没有而暴露出来的缺口需要单独返回。

## 本轮完成

- 新增 `scripts/runtime_bridge/run_r0_r11_readiness_gate.py` 和 `src/sec_agent/runtime_readiness.py`，把 R0-R11 变成可执行 readiness gate。
- R1 run audit store 从 8 张表扩到 19 张表，覆盖 retrieval、tool、reflection、repair、resource、report、context、upload、parsed input 等运行审计对象。
- R2 eval store 增加 registry / membership / eval_run / annotation / judge / dashboard snapshot，并支持 failure/gold 生命周期记录。
- R3 增加 data-processing、index asset、retrieval quality gates；Milvus 云端 parity 保持显式 cloud gap。
- R4 新增 `ContextEngine` 和 memory governance，支持 replayable context injection。
- R5 增加 scheduler audit、CUDA BGE queue / CPU spillover / queue position，以及 agent coalescer。
- R6 新增 tool capability registry、writer permission gate、user input artifact pipeline。
- R7 新增 ResearchObjectiveContract、LeadReviewCheckpoint、TargetedRepairPlan。
- R8 新增 role-specific evidence selector，覆盖 fundamental、product/technology、market、capital/macro、risk。
- R9 新增 MemoLogicPlan 和 writer-no-new-facts validation。
- R10 补 Java gateway resume/SSE；resume 会清空旧 memo/evidence/error 并重置 progress；smoke 覆盖 requeue 和 SSE。
- R11 新增 Workbench eval dashboard endpoint 与 React `EvalDashboardPanel`；补 Vite React entry，使前端生产 build 可跑。

## 验证

- `pytest tests/test_runtime_bridge_contracts.py tests/test_run_audit_store.py tests/test_runtime_bridge_java_python_smoke.py tests/test_workbench_backend.py -q`
  - result: `42 passed`
- `python scripts/runtime_bridge/smoke_java_python_bridge.py --task-mode local_smoke --store-mode file --queue-mode file --check-resume-sse`
  - result: pass，包含 Java create/status/events/resume、file queue、Python worker callback、SSE heartbeat。
- `python scripts/runtime_bridge/run_r0_r11_readiness_gate.py --output-dir reports/quality/r0_r11_readiness_local`
  - result: `pass_with_cloud_gaps`
  - summary: `gate_count=12`、`failed_gate_count=0`、`cloud_gap_count=1`
- `node node_modules/typescript/bin/tsc -p tsconfig.json && node node_modules/vite/bin/vite.js build --config vite.config.ts`
  - result: pass

## 生成但不入库的产物

- `reports/quality/r0_r11_readiness_local/r0_r11_readiness_report.json`
- `reports/quality/r0_r11_readiness_local/run_audit.sqlite`
- `reports/quality/r0_r11_readiness_local/eval_store.sqlite`
- `apps/workbench/frontend/dist/`

这些路径被 `.gitignore` 覆盖，作为本地验收产物保留，不提交。

## Cloud / Milvus 缺口

唯一 R0-R11 cloud gap：

- `R3.cloud_milvus_parity`
  - reason: Milvus cloud collection 未打开/未绑定。
  - 云端打开后必须补：`collection_stats`、`schema_parity`、`603_company_coverage`、`query_smoke`。

这不是本地 fallback，也不是用 BM25/ObjectBM25 替代 Milvus；当前语义向量层仍按 `unbound_cloud_deferred` 登记。

## 仍不属于本轮

- R12 full-chain regression / online eval / release readiness report 尚未执行。
- 高并发 GPU BGE / worker pool / SLA 压测需要云端资源后执行。
- Milvus 仍只允许 typed semantic recall supplement，不能支持 exact-value authority。

## 下一步

用户开云端后先跑 R3 cloud Milvus parity 和 R5 GPU scheduler smoke；通过后再进入 R12 的 1-2 个 full-chain 激活 case，然后按 failure/gold lifecycle 扩到 12case 与 10-20case。
