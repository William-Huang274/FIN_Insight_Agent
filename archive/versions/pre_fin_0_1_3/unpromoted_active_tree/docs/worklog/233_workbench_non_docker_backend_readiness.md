# Worklog 233: Workbench Non-Docker Backend Readiness

## Prompt

用户在本机 Docker 安装受 Windows 组件存储问题阻断后，要求先清理指定 D 盘文件，并继续推进除 Docker 以外的后端任务。

## Decision

本轮冻结 Docker 安装和容器验证，优先把本地 Workbench 后端做成可检查、可轮询、可并发写运行日志的状态。Docker 仍保留为后续部署入口，但不是本地 Workbench 后端的前置条件。

## Local Cleanup

- 删除用户明确指定的两个本地下载文件：
  - `D:\downloads\Yelp-Photos.zip`
  - `D:\downloads\Yelp-JSON.zip`
- 删除后 D 盘剩余空间约 `15.04GB`。
- 这两个文件不属于仓库，未产生 Git 删除记录。

## Work Completed

- `WorkbenchStore` 后端存储加固：
  - SQLite 连接增加 `busy_timeout=30000`、`foreign_keys=on`、`journal_mode=wal`、`synchronous=normal`。
  - `append_run_event` 改为 `begin immediate` 写事务，避免多个后台任务同时写同一个 job 事件时 sequence 冲突。
  - 增加 `idx_run_jobs_status`、`idx_run_jobs_job_type`、`idx_run_job_events_trace_id` 索引。
- 新增 `StoreHealthReport`：
  - 返回 SQLite 路径、父目录可写性、数据库大小、WAL 大小、journal mode 和 profile/source bundle/run/event 计数。
- 新增 API：
  - `GET /api/system/status`
  - 返回 Workbench store、仓库路径、数据目录、前端目录、磁盘剩余空间和 `docker_required=false`。
- 补充测试：
  - API system status 不泄露运行 key。
  - SQLite concurrent run-event append 保持单调 sequence。
- 更新快速开始文档：
  - 增加 `/api/system/status` 排障入口。
  - 明确 Docker 不是本地 Workbench 后端的前置条件。

## Verification

已执行：

```text
python -m pytest tests/test_workbench_backend.py tests/test_workbench_job_runner.py
```

结果：

```text
43 passed
```

## Boundary

- 本轮没有继续安装 Docker，也没有运行 Docker build。
- 本轮没有运行真实 DeepSeek/full-chain case。
- SQLite WAL 和事务加固适合本地 Workbench 任务管理，不等同于生产级多实例数据库；后续如果要多用户部署，应迁移到 PostgreSQL 或加入集中任务队列。
