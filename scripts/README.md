# 脚本发布面

这个目录只保留当前主线还会用到的脚本：完整链路入口、数据准备、评测门控、MCP 服务和 Workbench 启动。历史实验脚本、一次性基准评测构造器、旧版人审草稿和临时检索调试脚本不再作为公开入口保留。

## 稳定入口

- `cloud/sec_agent_interactive.sh`：公开 CLI 演示入口，支持单轮完整链路和多轮会话。
- `cloud/sec_agent_interactive.py`：SEC / 8-K / 市场快照完整链路运行时。
- `cloud/sec_agent_graph_runner.py`：图运行器，供 CLI、工具执行层和 Workbench 使用。
- `cloud/sec_agent_context_session_cli.py`：多轮会话上下文运行入口。
- `evaluate_sec_agent_resume_closeout_readiness.py`：本地发布就绪检查，覆盖上下文、来源策略、市场快照、耗时和结构性门控。

## 数据准备

- SEC 披露和清单：`download_sec_filings.py`、`build_sec_manifest.py`、`build_sec_mixed_latest_manifest.py`、`build_sec_chunks.py`。
- 8-K 业绩材料：`download_sec_8k_earnings.py`、`build_sec_8k_earnings_manifest.py`、`build_sec_8k_earnings_chunks.py`、`merge_sec_source_gaps.py`。
- 证据对象和索引：`build_evidence_store.py`、`build_structured_objects.py`、`build_bm25_index.py`、`build_object_bm25_index.py`、`build_object_sqlite_fts_index.py`、`indexing/`、`ledger/`。
- 市场快照：`market/06_*` 到 `market/60_*`。
- 行业和关系覆盖：`industry/`、`build_sector_depth_expansion_configs.py`、`probe_sector_depth_source_availability.py`。

## 评测和门控

- 多智能体分层门控：`eval_multi_agent_*.py` 和 `audit_multi_agent_*.py`。
- 上下文和控制器检查：`evaluate_sec_agent_context_*.py`、`evaluate_sec_agent_tool_*.py`、`benchmark_sec_agent_context_api.py`、`evaluate_sec_agent_latency_profile.py`。
- 基准评测运行和后置门控：`run_sec_benchmark_eval.py`、`run_sec_benchmark_post_gates.py`、`run_sec_benchmark_vllm_synthesis_from_traces.py`、`run_sec_eval_synthesis_qwen9b_backend.py`、`run_sec_eval_synthesis_contract_backend.py`、`score_sec_benchmark_outputs.py`，以及后置门控会调用的 `validate_sec_benchmark_*` 脚本。

## 服务和本地工作台

- `mcp/`：MCP 工具合同导出、服务端、调用器和冒烟检查。
- `workbench/`：本地 Workbench 启动和环境辅助脚本，包括一键启动脚本、后端启动脚本和前端构建辅助。

## 维护原则

- 新用户应该从根目录 `README.md`、`docs/README.md` 和本文件开始，不需要翻历史工作日志。
- 一次性实验脚本不要继续加回主线脚本目录；如果需要保留背景，写进工作日志。
- 用户会复制的命令必须使用当前保留脚本，不能引用已删除的历史脚本。
- 私有数据、运行产物、索引、模型缓存和 API key 不进入 `scripts/`。
