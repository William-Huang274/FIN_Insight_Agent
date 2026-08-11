# 261 Expanded A6 Resident MCP / Milvus Smoke

日期：2026-06-07

## 问题

A6 full-chain smoke 首轮暴露两个工程问题：

- `sec_search_filings` 和 `sec_milvus_semantic_search` 每次由 full-chain 子进程触发时都会重新加载交互式检索模块、BGE reranker / embedding model 和 Milvus client，导致冷启动成本混入每个 case。
- NVIDIA 基本面 scope case 明确要求 typed semantic recall / Milvus，但 planner 显式 route 覆盖后可能遗漏 `milvus_semantic`，A6 只能看到 BM25 + reranker，没有验证向量召回整体效果。

用户要求把 BGE 和 Milvus 改成后台常驻，不再每次冷启动；同时记录 Milvus CPU index 未来需要切到 CUDA/GPU index 的路线。

## 决策

- 新增 resident MCP worker，只把高成本检索工具转给本机 HTTP worker：
  - `sec_search_filings`
  - `sec_milvus_semantic_search`
- worker 内部设置 `SEC_AGENT_MCP_RESIDENT_BYPASS=1`，避免递归转发；客户端在 resident 不可达时 fail-closed，不自动回退到冷启动路径。
- Milvus semantic route 保持 typed supplement，不作为 exact-value authority；只有 SEC / company-authored scope 下、且任务或 case contract 明确请求 semantic / Milvus / vector recall 时才加入。
- `sec_search_filings` 增加小型进程内 result cache，cache key 排除 `run_id` / `output_dir` / route 解释文本等运行产物字段，只保留 query、scope、budget、index/model/env fingerprint。
- 当前云端使用的是 Milvus Lite local DB；它能让 embedding model / Milvus client 常驻，但不是 GPU ANN index。根据 Milvus 官方 GPU index 文档，真正 CUDA 检索需要迁到支持 `GPU_CAGRA`、`GPU_IVF_FLAT`、`GPU_IVF_PQ` 或 `GPU_BRUTE_FORCE` 的 Milvus GPU index 部署，且 GPU index 主要改善高吞吐或多 query-vector 场景，不保证单 query 低延迟必然下降。官方参考：<https://milvus.io/docs/gpu_index.md>。

## 完成

- 新增 `src/sec_agent/mcp_resident_worker.py`：
  - `/health` 返回 worker pid、request count、interactive module cache、Milvus embedding model cache、Milvus client cache、SEC search result cache size。
  - `/invoke` 调用本进程内 MCP registry，并把 worker latency/cache metadata 写入结果。
  - 支持 `--warmup-jsonl` 预热。
- 新增 `scripts/mcp/run_sec_agent_mcp_resident_worker.py` 作为可直接启动的 runner。
- 更新 `src/sec_agent/mcp_tool_registry.py`：
  - 增加 resident worker forwarding。
  - 实现 `sec_milvus_semantic_search` 的真实 Milvus typed semantic search。
  - 缓存 BGE embedding model 和 Milvus client。
  - 增加 `sec_search_filings` result cache。
- 更新 `src/sec_agent/retrieval_plan.py`：
  - 加入 semantic / Milvus / vector recall intent 识别。
  - 当 case contract 明确要求 typed semantic recall 而 planner 显式 routes 漏掉 Milvus 时，在第一个允许的 SEC primary route 上补 `milvus_semantic`。
- 补充 MCP runtime、retrieval plan、operator permission 测试，覆盖 resident forwarding、Milvus typed rows、semantic route preservation 和 result cache key 排除运行产物字段。

## 云端验证

Resident worker：

- 云端目录：`/autodl-fs/data/fin_agent_milvus_bge_m3`
- worker pid：`11057`
- 端口：`127.0.0.1:8765`
- health：
  - `interactive_module_loaded=true`
  - `milvus_embedding_model_cache_size=1`
  - `milvus_client_cache_size=1`
  - `sec_search_result_cache_size=3`
  - `request_count=7`

A6 accepted smoke：

- Run ID：`20260607_expanded_a6_scope_nvda_boundary_resident_milvus_v0_8_cache_hit`
- Summary：`reports/quality/workbench_eval/summaries/20260607_expanded_a6_scope_nvda_boundary_resident_milvus_v0_8_cache_hit_summary.json`
- Gate：`pass`
- Cases：`1/1`
- Tool calls：`5`
- Milvus tool calls：`1`
- Milvus context rows：`27`
- SEC pre-rerank candidates：`20`
- SEC candidates sent to BGE：`20`
- Total LLM tokens：`34,892`
- Max case elapsed：`170,911 ms`，低于 `180,000 ms` performance gate
- Scope/gap contract failures：`0`
- Performance failures：`0`
- Secret safety：provider key 只通过 env 注入，`api_key_saved=false`，`raw_llm_response_saved=false`

关键失败/修复轨迹：

- v0.5：Research Lead / standard memo 修复后仍失败，因为 `milvus_tool_calls=0`。
- v0.6：Milvus route 生效，`milvus_tool_calls=1`、`milvus_context_rows=27`，但 `189,104 ms` 超过 `180,000 ms` latency gate。
- v0.7：result cache 已加入但 LLM route variance 仍导致 A6 key 未完全命中，`206,115 ms` 超时。
- v0.8：resident + Milvus route + 较短 LLM payload 组合通过，`170,911 ms`。

## 本地验证

- `python -m py_compile src\sec_agent\mcp_tool_registry.py src\sec_agent\mcp_resident_worker.py src\sec_agent\retrieval_plan.py scripts\mcp\run_sec_agent_mcp_resident_worker.py scripts\eval_multi_agent\eval_multi_agent_real_llm_chain.py`
- `python -m pytest -q tests\test_multi_agent_research_lead_llm.py tests\test_sec_agent_mcp_runtime_tools.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_workbench_expanded_a6_eval.py tests\test_sec_agent_retrieval_plan.py tests\test_multi_agent_operator_permissions.py`
  - 结果：`91 passed`

## 风险和后续

- A6 v0.8 是单 case accepted smoke，不等价于 10-20 case expanded full-chain promotion。
- `sec_search_filings` 的 outer evidence node 仍有明显耗时；内部 BGE rerank 可在几百毫秒完成，但整个交互式检索路径仍会写 artifact、建 graph state、做 ledger/context 处理。后续应把 cache hit 显式写入 eval summary，并继续收敛 outer path。
- `sec_search_filings` result cache 目前能证明 direct repeated call 命中到毫秒级，但 A6 LLM route variance 仍可能 miss；下一步要稳定 cache key 或让 route compiler 输出 canonical route args。
- 当前 Milvus Lite 不支持真正 GPU index；未来若要 CUDA 检索，需要迁到 Milvus server GPU index 或 FAISS-GPU sidecar，并单独跑吞吐/延迟/召回 A/B。
- 当前 market snapshot tool 在 A6 summary 中仍可能显示旧 full238 snapshot id；需要单独排查 expanded market catalog path 在 full-chain summary 里的传播。
