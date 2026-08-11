# 262 FIN 0.1 S1-T02 确定性统一 Runtime 主线

日期：2026-07-19
状态：`accepted_after_independent_review`

## 问题与决定

用户授权在已接受的 S1-T01 adapter map v1.1 边界内继续 S1-T02，不开始 T03。此前 `POST /work-units` 只创建 pending WorkUnit，现有 P36 deterministic analysis 仍由独立兼容读取入口执行；仓库没有 ResearchRun identity，也没有 WorkUnit、Attempt、Event、Artifact 的精确 Run 血缘。

本轮决定实现唯一 `Fin01ResearchRuntime`，复用 existing `DurableSchedulerService`、`RuntimeFacade`、`SQLiteCanonicalStore` 和 `FileCanonicalObjectStore`。API request thread 只完成 admission/enqueue；成功后登记一个 FastAPI BackgroundTask。确定性 profile adapter 只返回 typed `ProfileExecutionResult`，不直接写 canonical business objects。

## 完成工作

- 新增 `ExecutionProfileVersion`、`ProfileExecutionResult` 与 `Fin01ResearchRuntime`，exact profile 为 `fin01.execution_profile.p36_local_deterministic:v1`；
- `app.py` 作为唯一 composition root，把现有 P36 local analysis dependency 与 existing facade/scheduler 注入 Runtime；显式注入旧 `ExecutionService` 时仍保留 pending-only 兼容路径；
- existing scheduler claim 创建唯一 leased Attempt，且 claim events 在 profile 执行前完成；
- canonical models/store 新增 append-only `ResearchRunVersion`，SQLite trigger 强制 Attempt parent 与一 Attempt 一 Run identity；
- RuntimeFacade 新增 Run start/success/failure persistence，object store 先写 immutable JSON，随后 SQL transaction 提交 Artifact envelope、Run v2、Attempt/WorkUnit terminal head 和 events；
- Event 全部以 `task_run_id=research_run_id` 且携带 exact work_unit_id/attempt_id；Artifact producer 为 exact Attempt，input refs 同时包含 Run v1 与 business inputs，Attempt output refs 指向 exact Artifact version；
- deterministic failure 保持 Run/Attempt/WorkUnit failed，不创建 Artifact、不隐式切换 fallback；
- replay projection 新增 ResearchRun 状态，旧 Workbench API response schema 与显式 compatibility service 路径保持可用。

## 独立复核与修订

独立复核检查了 HTTP 202 时序、claim-before-execute、崩溃真实性、幂等、single-writer、Artifact 写入顺序、旧 Workbench 兼容和 T03 越界。复核发现 completion command 在检查 idempotency 之前先检查 Run state，成功后的精确重放会被 terminal state 拒绝；已在唯一一次自动修订中把 idempotency read 提前到 object write 和 terminal-state check 之前，同时保留 transaction 内二次检查。

复核结论：`pass_deterministic_mainline_connected_no_agent_or_release_claim`。

## 结果与证据

- current materialized P36 `analysis_preview` 已真实通过 `Fin01ResearchRuntime` 执行，输出仍为原有 bounded local deterministic analysis；
- success path：HTTP response body 为创建时 pending，durable final truth 为 WorkUnit/Attempt/ResearchRun succeeded + one immutable Artifact；
- failure path：WorkUnit/Attempt/ResearchRun failed，Artifact=0，hidden fallback=0；
- profile adapter direct canonical writes=0；model/provider/network/external-tool/真实业务 Case mutation=0；
- 相关回归：`50 passed`；
- 未运行前端 build、浏览器视觉检查、模型、网络、付费服务、商业数据、真实业务 Case、full-chain 或 release gate。

主要代码与测试：

- `apps/workbench/backend/application/research_runtime.py`
- `apps/workbench/backend/application/execution_service.py`
- `apps/workbench/backend/api/v1/execution.py`
- `apps/workbench/backend/app.py`
- `src/sec_agent/canonical_runtime/models.py`
- `src/sec_agent/canonical_runtime/store.py`
- `src/sec_agent/canonical_runtime/facade.py`
- `tests/contract/test_fin_0_1_s1_t02_research_runtime.py`

## 后续与安全边界

T02 已接受。下一 backlog item 是 S1-T03，但尚未获得本轮明确授权，不在本轮启动。RC-P38-042 只完成 deterministic mainline 部分修复；历史 Agent/Skill/Tool/Graph 仍未被产品 Runtime 消费，所以 full-chain blocker 保持。RG1/RG3/RG4、S2、release candidate、production cutover 和真实模型/provider/network 权限均未改变。
