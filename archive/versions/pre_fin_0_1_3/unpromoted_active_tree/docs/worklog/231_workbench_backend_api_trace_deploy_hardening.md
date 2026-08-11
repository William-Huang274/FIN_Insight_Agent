# Worklog 231: Workbench Backend API Trace And Deploy Hardening

## Prompt

用户要求先专注后端开发，另一个窗口并行做 case 测试。本轮不改 full-chain 评测逻辑，聚焦 Workbench 后端基础能力。

## Decision

按照后端产品化缺口优先处理：

- 保持成功响应兼容，不引入全局 response envelope。
- 错误响应保留 FastAPI 既有 `detail` 字段，同时新增标准 `error` 对象。
- `trace_id` 成为 API 请求、后台 job、run event 和子进程环境变量的共同关联字段。
- 增加 Dockerfile 和 GitHub Actions 基础测试，但 CI 只跑 Workbench 后端 smoke，不跑真实 LLM/full-chain case。

## Work Completed

- 新增 `src/sec_agent/workbench/api_contracts.py`：
  - 请求级 `X-Trace-Id` 读取/生成。
  - `X-Elapsed-Time-Ms` 响应头。
  - 统一 HTTP / validation / unexpected error handler。
  - 标准错误对象 `finsight_workbench_api_error_v0.1`。
- 新增 `src/sec_agent/workbench/runtime_ids.py`，避免任务模型依赖 FastAPI。
- 扩展 `RunJob` / `RunLogEvent`：
  - `trace_id`
  - `elapsed_ms`
  - `error_message`
- 扩展 SQLite store：
  - `run_jobs.trace_id / started_at / finished_at / elapsed_ms / error_message`
  - `run_job_events.trace_id`
  - 对既有 SQLite 表执行增量 column migration。
- 扩展后台任务 runner：
  - 每条 system/stdout event 带 trace。
  - 子进程环境变量注入 `SEC_AGENT_TRACE_ID` 和 `SEC_AGENT_WORKBENCH_JOB_ID`。
  - terminal job 自动写入 elapsed/error summary。
- 补齐部署基础：
  - `requirements.txt` 增加 `fastapi` 和 `uvicorn[standard]`。
  - 新增 `Dockerfile`，构建 React/Vite 前端并以 Workbench 后端启动。
  - 新增 `.dockerignore`，排除私有数据、运行产物、临时目录、前端 node_modules。
  - 新增 `.github/workflows/backend-smoke.yml`，在 PR/main push 上编译 Workbench 后端并跑 Workbench 测试。

## Verification

已执行：

```text
python -m pytest tests/test_workbench_backend.py tests/test_workbench_job_runner.py -q
```

结果：

```text
39 passed
```

## Boundary

- 本轮没有运行真实 DeepSeek/full-chain case。
- 本轮没有引入用户认证、权限租户隔离、限流、PostgreSQL 或集中日志系统。
- Dockerfile 是本地 Workbench 镜像基础，不包含私有数据、模型权重或 API key。

## Follow-Up

- Workbench 前端可以继续显示 `trace_id / elapsed_ms / error_message`，方便用户排查任务。
- CI 后续可以增加 Docker build smoke，但不应默认跑真实模型评测。

## Continuation: Trace Inspection API

用户要求继续后端开发。本轮仍不触碰真实 LLM/full-chain case，继续把上一轮新增的 `trace_id` 做成可查询能力。

### Work Completed

- `GET /api/runs` 增加过滤参数：
  - `trace_id`
  - `status`
  - `job_type`
  - `limit`
- 新增 `GET /api/traces/{trace_id}`：
  - 返回同一 trace 下的 jobs。
  - 返回同一 trace 下的 run events。
  - 返回 `job_count / event_count / status_counts / first_event_at / latest_event_at`。
  - 未找到 trace 时返回标准错误合同：`trace_not_found`。
- Store 层新增：
  - `list_run_jobs(...filters...)`
  - `list_trace_events`
  - `inspect_trace`
  - `TraceInspectionReport`
- 测试新增：
  - trace 过滤后的 run 列表。
  - trace inspection report。
  - missing trace 标准错误合同。

### Verification

已执行：

```text
python -m compileall apps\workbench\backend src\sec_agent\workbench
python -m pytest tests/test_workbench_backend.py tests/test_workbench_job_runner.py -q
```

结果：

```text
40 passed
```

### Boundary

- 前端尚未展示 trace 查询面板。
- 本轮没有跑 Docker build smoke。

## Continuation: Lightweight Status API And Docker Smoke CI

用户继续要求推进后端开发。本轮仍保持边界：不运行真实 LLM/full-chain case。

### Work Completed

- 新增轻量状态模型：
  - `RunStatusReport`
  - `TERMINAL_RUN_STATUSES`
  - `run_status_report_from_job`
- 新增 store 方法：
  - `get_run_status(job_id)`
  - 返回 job 基础状态、`is_terminal`、`event_count` 和 `latest_event`。
- 新增 API：
  - `GET /api/runs/{job_id}/status`
  - 不检查 artifact index，不扫描运行目录，适合前端轮询。
- Dockerfile 增加可选构建参数：
  - `ARG REQUIREMENTS_FILE=requirements.txt`
  - 默认仍安装完整 `requirements.txt`。
  - CI smoke 可用 `requirements-workbench.txt` 避免安装模型/检索重依赖。
- 新增 `requirements-workbench.txt`，只覆盖 Workbench API / LangGraph import / uvicorn 运行需要。
- 新增 `.github/workflows/docker-smoke.yml`：
  - 路径触发和手动触发。
  - 用 `requirements-workbench.txt` 构建 Workbench 镜像。
  - 启动容器并检查 `/api/health`。

### Verification

已执行：

```text
python -m compileall apps\workbench\backend src\sec_agent\workbench
python -m pytest tests/test_workbench_backend.py tests/test_workbench_job_runner.py -q
PowerShell here-string smoke: import `apps.workbench.backend.app:create_app` with repo/src on `sys.path`
```

结果：

```text
41 passed
FinSight Workbench API
```

本机 Docker CLI 不可用：

```text
docker: The term 'docker' is not recognized
```

因此本地没有实际执行 Docker build。Docker smoke 已落入 GitHub Actions，推送后由 CI 环境执行。

### Boundary

- 前端尚未调用 `/api/runs/{job_id}/status`。
- Docker smoke 是 Workbench 后端健康检查，不声明完整 Agent/full-chain 容器环境质量。
