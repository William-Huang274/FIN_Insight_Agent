# 脚本发布面

这个目录只保留当前主线还会用到的脚本：完整链路入口、数据准备、评测门控、MCP 服务和 Workbench 启动。历史实验脚本、一次性基准评测构造器、旧版人审草稿和临时检索调试脚本不再作为公开入口保留。

## 稳定入口

- `cloud/sec_agent_interactive.sh`：公开 CLI 演示入口，支持单轮完整链路和多轮会话。
- `cloud/sec_agent_interactive.py`：SEC / 8-K / 市场快照完整链路运行时。
- `cloud/sec_agent_graph_runner.py`：图运行器，供 CLI、工具执行层和 Workbench 使用。
- `cloud/sec_agent_context_session_cli.py`：多轮会话上下文运行入口。
- `eval_context/evaluate_sec_agent_resume_closeout_readiness.py`：本地发布就绪检查，覆盖上下文、来源策略、市场快照、耗时和结构性门控。

## 数据准备

- `data_sec/`：SEC 10-K / 10-Q、8-K 业绩材料、混合清单、文本切分、来源缺口合并、行业深度 universe 配置生成和覆盖探测。
- `data_retrieval/`：证据对象、结构化对象、BM25、ObjectBM25、SQLite FTS、精确数值台账和覆盖矩阵。
- 市场快照：`market/06_*` 到 `market/60_*`。
- 行业来源：`industry/10_download_industry_source_snapshot.py`。
- 辅助索引和台账：`indexing/`、`ledger/`。

## 评测和门控

- `eval_multi_agent/`：多智能体分层门控、全链路真实模型评测和质量审计。
- `eval_context/`：上下文状态、请求 API、工具控制器、工具执行层、延迟和发布就绪检查。
- `eval_query_planner/`：自由问题解析和查询合同评测。
- `eval_sec_benchmark/`：SEC benchmark 运行、旧 benchmark 运行时支撑、Qwen/contract synthesis 适配、后置门控和相关 validator。虽然目录名保留 benchmark，但其中部分脚本仍被当前完整链路复用，不能归档。

## 服务和本地工作台

- `mcp/`：MCP 工具合同导出、服务端、调用器和冒烟检查。
- `workbench/`：本地 Workbench 启动和环境辅助脚本，包括一键启动脚本、后端启动脚本和前端构建辅助。

## 归档脚本

- `archive/`：不再作为当前公开入口的历史脚本。目录名带版本号，例如 `v0_1_free_query/`、`v0_1_vllm_diagnostics/`。归档脚本只用于查历史实现，不保证随主链路持续维护。

## 维护原则

- 新用户应该从根目录 `README.md`、`docs/README.md` 和本文件开始，不需要翻历史工作日志。
- 一次性实验脚本不要继续加回主线脚本目录；如果需要保留背景，写进工作日志。
- 用户会复制的命令必须使用当前保留脚本，不能引用已删除的历史脚本。
- 私有数据、运行产物、索引、模型缓存和 API key 不进入 `scripts/`。
