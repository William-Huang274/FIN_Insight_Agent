# 代码目录与命名

目录按职责组织，模块名称描述功能。数据集中的公司、研究时点和来源身份由配置与数据合同表达。

| 目录 / 入口 | 职责 |
| --- | --- |
| `apps/workbench/` | FastAPI 接口、React 界面、报告导航和交付 |
| `scripts/deployment/research_workbench.py` | 本地工作台检查、构建、启动与服务命令 |
| `deploy/agent_server/` | Agent Server、PostgreSQL、Redis 及相关部署配置 |
| `src/sec_agent/agent_runtime/` | 研究任务、专家、审阅、会话与运行基础设施适配 |
| `src/sec_agent/research_foundation/` | 方法、资料读取、MCP 工具与来源绑定计算 |
| `src/retrieval/`、`src/ingestion/` | 资料解析、节点生成、检索和索引构建 |
| `scripts/data_retrieval/`、`data_sec/`、`market/`、`industry/` | 可重复的数据准备命令 |
| `tests/` | 合成回归与需要显式启用的原始资料测试 |

## 运行模块

| 模块 | 职责 |
| --- | --- |
| `agent_server_data_composition.py` | Open validated data sources for a configured research task. |
| `agent_server_entry.py` | LangGraph Agent Server entry points for research and review. |
| `agent_server_identity.py` | Persist FIN task and Agent Server identity bindings in PostgreSQL. |
| `agent_server_recovery.py` | Represent uncertain run creation and explicit recovery decisions. |
| `research_contracts.py` | Typed research tasks, evidence coverage and working-paper contracts. |
| `case_artifacts.py` | Read saved case reports and working papers with their source bindings. |
| `report_synthesis_agent.py` | Compose, review and revise a report from case working papers. |
| `case_review_agent.py` | Review working papers and bind findings to their supporting sources. |
| `capability_inventory.py` | Validate available local and external research routes. |
| `lead_research_graph.py` | Delegate research tasks and assemble a reviewed working-paper handoff. |
| `data_access_policy.py` | Validate access decisions for configured source and financial datasets. |
| `research_graph_contracts.py` | State and tool contracts for the configured research workflow. |
| `research_graph.py` | Research workflow with planning, source tools and independent review. |
| `research_mcp_tools.py` | Adapt scoped research tool requests to MCP calls and typed results. |
| `report_session.py` | Follow up on saved reports while retaining source and version bindings. |
| `reviewed_evidence_inventory.py` | Build a source inventory from validated reviewed evidence. |
| `source_family_compiler.py` | Compile configured source families into bounded retrieval routes. |
| `specialist_composition.py` | Bind specialist tasks to data tools, models and execution budgets. |
| `specialist_graph.py` | Specialist tool loop for source reading, calculation and working papers. |
| `model_execution_policy.py` | Validate model-call budgets, allowed modes and audit destinations. |
| `workpaper_review_graph.py` | Review and revise a working paper with preserved observations. |
| `execution_profile_checks.py` | Validate execution profiles and the configured no-model diagnostic task. |

## 已有环境兼容

模块与文件名可以演进，已有图 ID、MCP 工具 ID、数据库结构、凭据派生标识与数据快照身份保持稳定。部分兼容标识含早期示例名称；它们不用于根据公司名称选择不同的产品行为。

当前配置中仍有为参考案例定义的资料路线和方法约束。模块改名不表示这些约束已对任意行业或公司完成验证；扩充数据和方法时需按研究范围验证。

[运行说明](../../public/quickstart.zh-CN.md) · [系统架构](../../public/architecture.zh-CN.md)
