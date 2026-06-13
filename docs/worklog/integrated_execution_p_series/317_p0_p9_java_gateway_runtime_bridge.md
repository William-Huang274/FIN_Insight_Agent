# 317 P0-P9 Java Gateway Runtime Bridge

日期：2026-06-14

## Prompt

用户补充下一阶段执行要求：

- B0/P0 不应在 FastAPI 和 Java 之间二选一，而应按“前端 -> Java -> DB/Redis/MQ -> Python worker -> LangGraph -> DB -> Java 查询”的真实产品链路设计。
- P0 可以不做复杂 Spring Boot / 高并发，但本地或云端资源下的测试请求和必要接口必须可用；Python 到 Java 后端通路必须打通，不能只是 shell。
- 当前脚本和数据分别在 D 盘 / Z 盘，Milvus 仍在云端且暂不更新；路径兼容不能靠硬编码迁移。
- 实施过程中要同步更新 09-12 文档和本阶段工作日志。
- 本地 Docker / 后端环境可用，缺依赖可自行安装；DeepSeek key 只用于必要测试，本轮不跑 full-chain。

## Decision

本轮先实现 P0-P9 的最小可运行后端通路和 eval/resource/path contract：

- 不引入复杂 Spring Boot / Maven 作为第一步，因为本机没有 Maven，且当前目标是验证真实链路可用。
- 使用 JDK-only Java Task Gateway 打通 task lifecycle，保留后续 Spring Boot parity。
- Java gateway 支持 `file` local adapter 和 `jdbc` store mode；真实 MySQL/Postgres 通过运行时 JDBC driver jar + `FINSIGHT_JDBC_URL` 接入。
- Queue 支持 `file` local adapter 和原生 Redis RESP `LPUSH`。
- Python worker 支持 file/Redis queue，并通过 Java callback 回写状态、memo、evidence。
- Milvus 仍登记为 `unbound_cloud_deferred` semantic supplement，等待云端可用后再绑定。

## Work Completed

- 新增 Java gateway：
  - `apps/research_gateway/java/src/finsight/gateway/TaskGatewayServer.java`
  - `GatewayConfig.java`
  - `ResearchTask.java`
  - `TaskStore.java`
  - `FileTaskStore.java`
  - `JdbcTaskStore.java`
  - `TaskQueue.java`
  - `FileTaskQueue.java`
  - `RedisTaskQueue.java`
  - `JsonUtil.java`
- 新增 Python runtime bridge：
  - `src/sec_agent/runtime_bridge/task_worker.py`
  - `contracts.py`
  - `paths.py`
  - `eval_store.py`
  - `data_quality.py`
  - `resource_scheduler.py`
- 新增可复跑 smoke：
  - `scripts/runtime_bridge/smoke_java_python_bridge.py`
- 新增 tests：
  - `tests/test_runtime_bridge_contracts.py`
  - `tests/test_runtime_bridge_java_python_smoke.py`
- 更新 09/10/11/12 文档：
  - 10 文档改为 Java Task Gateway 先行，不再“先 FastAPI 后 Java shell”。
  - 12 文档同步 P0/P1/P8/P9 门控和 Java gateway -> Python worker 生命周期。
  - 09 文档记录 L6/L7 已有 deterministic scheduler 最小实现。
  - 11 文档记录 Eval Store / data-quality eval / resource scheduler 最小实现状态。

## Result And Evidence

Targeted tests：

```text
python -m pytest tests/test_runtime_bridge_contracts.py tests/test_runtime_bridge_java_python_smoke.py -q
5 passed
```

Manual smoke：

```text
python scripts/runtime_bridge/smoke_java_python_bridge.py --query "Check NVDA runtime bridge"
status: SUCCESS
memo: Runtime bridge smoke passed...
evidence[0].source_family: runtime_bridge_smoke
```

## 2026-06-14 Follow-up Completion

本日志初版记录的是 P0-P9 最小通路；随后按用户要求补到“真实链路可跑通，不是最小闭环”：

- Java gateway 增加 `GET /events`、`POST /cancel`、task event store、JDBC status update/event append/list、DB readiness retry。
- Python worker 增加 Workbench eval mode，支持 `context_api_smoke`、`context_api_load_smoke`、`agent_graph_vnext_run_audit_smoke`、`agent_graph_vnext_diagnostic_probe`。
- 新增 Docker backend smoke，覆盖 `file+redis` 与 `jdbc+redis`。
- 修复 Workbench diagnostic 中的 pack-visible evidence refs 误判。
- 修复产品收入 / AI server / ISG facts 被归到 fundamentals 的问题：产品事实现在进入 `product_technology` memo slot 与 `product_and_production` dimension。
- 修复 Windows GBK 下 runtime bridge smoke 输出 JSON 编码问题。

更新后通过门控：

```text
javac -encoding UTF-8 apps/research_gateway/java/src/**/*.java
pass

python scripts/runtime_bridge/smoke_java_python_bridge.py --task-mode local_smoke --store-mode file --queue-mode file
status: SUCCESS

python scripts/runtime_bridge/smoke_java_python_bridge_docker_backends.py
file+redis: SUCCESS
jdbc+redis: SUCCESS

python scripts/runtime_bridge/smoke_java_python_bridge.py --task-mode workbench_eval --eval-id agent_graph_vnext_diagnostic_probe --limit 1 --run-id runtime_bridge_agent_graph_diag_probe_l1_product_v4
Workbench summary: pass

python -m pytest tests/test_multi_agent_contracts.py::test_product_revenue_observation_is_routed_to_product_surface_even_from_fundamental_agent tests/test_d_series_fact_selection.py::test_pre_memo_fact_selection_prioritizes_query_relevant_product_lines tests/test_multi_agent_real_llm_chain_eval.py tests/test_runtime_bridge_contracts.py tests/test_runtime_bridge_java_python_smoke.py -q
33 passed
```

## Remaining Gaps

- 当前 Java gateway 是 JDK-only implementation，不是 Spring Boot parity；Spring Boot / SSE dashboard / auth / tenant 等留到后端产品化阶段。
- P10 full-chain 12case regression 未跑，本轮只跑 1 个 Workbench real diagnostic case。
- Milvus 云端绑定等待用户开启云端后再做。
- 前端 trace / eval dashboard 尚未新建；当前只通过 API / artifact / Workbench 后端验证。
- CUDA BGE 排队机制已有 contract，真实 GPU scheduler 仍待资源阶段验证。

## Follow-up

下一轮建议按顺序推进：

1. 把 Java gateway `jdbc + redis` smoke 接 Docker MySQL/Redis。
2. 把 Python worker 从 deterministic smoke 接到 Workbench `agent_graph_vnext_run_audit_smoke` 或轻量 graph command。
3. 将 worker 输出投影到 run audit / eval store。
4. 给 Java gateway 增加 events/cancel endpoint 和 SSE/polling surface。
5. 云端 Milvus 开启后补 collection binding / snapshot / parity。
