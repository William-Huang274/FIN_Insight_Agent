# 318 P0-P9 Operational Bridge And Product Surface Closeout

日期：2026-06-14

## Scope

本轮目标是把 P0-P9 从“最小闭环 / contract surface”推进到可真实跑通的后端桥接与 Workbench diagnostic 链路。P10 full-chain 12case regression 暂不执行。

## Implementation

Backend / runtime bridge：

- Java Task Gateway 增加 task events、cancel endpoint、worker callback event append、JDBC status update 与 event table。
- `JdbcTaskStore` 增加启动期 DB readiness retry，避免 Docker MySQL 初始化慢导致 false fail。
- Python worker 支持真实 Workbench eval task mode，并把 eval status、summary、artifact refs 回写给 Java task。
- 新增 Docker backend smoke，覆盖 `file+redis` 与 `jdbc+redis`。
- Runtime bridge smoke 输出改为 ASCII-safe JSON，避免 Windows GBK 控制台编码导致 pass run 打印失败。

Agent / eval quality：

- D-series pre-memo fact selector 增加 query-relevant product-line ranking，防止 AI server / ISG 产品事实被 Consumer / Commercial / Storage 这类泛产品线挤出产品面。
- Multi-agent ClaimCard normalization 增加 product surface routing：产品收入、product KPI、AI server、ISG 等事实即使由 `fundamental_analyst` 产出，也进入 `product_technology` memo slot 和 `product_and_production` dimension。
- Memo outline 现在会合并 ClaimCard 自身的 memo slot，避免跨角色证据无法形成对应 section。
- Eval known refs 扩展到 role-visible packs / nested evidence refs，避免 specialist 已可见证据被误判为 unknown ref。
- Diagnostic product term gate 增加 hyphen / underscore / plural 归一化，避免 `AI-optimized servers` 与 `ai_optimized_servers` / `AI-optimized server revenue` 的字符串形态差异造成误判。

## Verification

已通过：

```text
javac -encoding UTF-8 apps/research_gateway/java/src/**/*.java
pass

python scripts/runtime_bridge/smoke_java_python_bridge.py --task-mode local_smoke --store-mode file --queue-mode file
status: SUCCESS

python scripts/runtime_bridge/smoke_java_python_bridge_docker_backends.py
file+redis: SUCCESS
jdbc+redis: SUCCESS

python scripts/runtime_bridge/smoke_java_python_bridge.py --task-mode workbench_eval --eval-id context_api_smoke --limit 1 --run-id runtime_bridge_context_api_smoke
status: SUCCESS

python scripts/runtime_bridge/smoke_java_python_bridge.py --task-mode workbench_eval --eval-id agent_graph_vnext_diagnostic_probe --limit 1 --run-id runtime_bridge_agent_graph_diag_probe_l1_product_v4
Workbench summary: pass
real-chain summary: pass

python -m pytest tests/test_d_series_fact_selection.py tests/test_multi_agent_eval_known_refs.py tests/test_runtime_bridge_contracts.py tests/test_runtime_bridge_java_python_smoke.py tests/test_multi_agent_real_llm_chain_eval.py -q
37 passed

python -m pytest tests/test_multi_agent_memo_llm_repair.py -q
39 passed
```

Additional targeted verification after print fix:

```text
python -m pytest tests/test_multi_agent_contracts.py::test_product_revenue_observation_is_routed_to_product_surface_even_from_fundamental_agent tests/test_d_series_fact_selection.py::test_pre_memo_fact_selection_prioritizes_query_relevant_product_lines tests/test_multi_agent_real_llm_chain_eval.py tests/test_runtime_bridge_contracts.py tests/test_runtime_bridge_java_python_smoke.py -q
33 passed
```

## Current Boundary

- P0-P9 的 API / queue / DB adapter / worker / Workbench diagnostic 链路已跑通。
- P10 full-chain 12case regression 未跑，不能据此声明全量线上质量已完成。
- Milvus 仍保持云端待绑定；本轮没有重建 603 家公司向量库。
- Spring Boot parity、SSE 前端 dashboard、auth/tenant、多 worker 压测、真实 CUDA BGE scheduler 仍在下一阶段。

## Next Step

下一步应先做 P10 前置的上线门控整理：

- 清理并提交本轮 P0-P9 代码和文档。
- 等云端 Milvus 可用后补 collection binding / snapshot / parity。
- 再跑 P10 full-chain regression，按 11 文档把失败进入 failure lifecycle，而不是临时修一次。
