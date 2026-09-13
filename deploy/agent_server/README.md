# Agent Server 本地部署 / Local Agent Server deployment

该目录提供 FinSight 研究与报告审阅的运行服务，使用 LangGraph Agent Server、PostgreSQL、Redis 和 LangSmith。完整启动方式见[快速开始](../../docs/public/quickstart.zh-CN.md)。

This directory provides the research and report-review services using LangGraph Agent Server, PostgreSQL, Redis and LangSmith. See the [quickstart](../../docs/public/quickstart.en.md) for setup.

## 部署入口 / Entry point

在仓库根目录使用统一命令，替换设置目录为实际路径：
Run from the repository root with a prepared settings directory:

```bash
python -m scripts.deployment.research_workbench check --settings-directory /path/to/settings --enable-research --fresh-only
python -m scripts.deployment.research_workbench up --settings-directory /path/to/settings --enable-research --fresh-only
python -m scripts.deployment.research_workbench serve --settings-directory /path/to/settings --enable-research --fresh-only
```

`check` 检查配置；`build` 构建镜像；`up` 启动或更新服务；`serve` 启动工作台接口。命令本身不会创建研究任务。执行研究需要从工作台提交问题，并会产生所选模型和工具的调用费用。
`check` validates configuration, `build` builds the image, `up` starts or updates services, and `serve` starts the workbench API. These commands do not create research tasks; submitted research uses the configured model and tool services.

## 配置与资料 / Configuration and data

- `host-settings.json` 与 `container-settings.json` 分别配置宿主和容器中的数据路径。Host and container settings bind the same research data through their respective paths.
- 模型、工具及数据库凭据放在忽略的 `.env` 或本地设置中，参考根目录 `.env.example`。Keep credentials in ignored local configuration; see `.env.example`.
- `--fresh-only` 使用原始资料开展新研究，设置中不包含旧报告与底稿答案路径。Fresh-only research uses source data and excludes saved report/answer bundles.
- `--working-memory` 启用任务底稿持久化；`--semantic-memory` 启用配置的语义检索；`--hybrid-rag` 使用已准备的原文向量。Working memory, semantic retrieval and prepared source vectors are enabled with the corresponding options.

| 配置文件 / File | 用途 / Purpose |
| --- | --- |
| compose.yaml | 基础运行服务 / Base services |
| compose.research-session.yaml | 新研究会话 / New research sessions |
| compose.report-session.yaml | 已存报告的审阅与追问 / Saved-report review and follow-up |
| compose.conversation-data.yaml | 财务数据只读挂载 / Read-only financial-data mount |
| compose.working-memory.yaml | 持久化工作记忆 / Persistent working memory |
| compose.zero-model-qualification.yaml | 不调用模型的运行诊断 / No-model runtime diagnostics |

其他可选诊断与专项审阅配置由相应测试覆盖，不随普通研究自动启用。Original case-specific policies remain scoped to their configured datasets; renaming modules does not expand their coverage.

## 已有部署兼容 / Existing installations

源代码目录和模块使用功能名称；已有 graph ID `dell_reference_vertical`、数据库身份、凭据派生标识和 Compose 项目名保持兼容。不要因为路径改名创建新的数据库卷或重置现有密码。迁移 SQL 文件内容及旧安装脚本的摘要保持不变；容器内的旧 SQL 挂载名用于兼容安装脚本。

Source paths use functional names. Existing graph IDs, database identities, credential derivation and Compose project names remain stable so saved runs and volumes can be reused. SQL contents and legacy installer hashes are unchanged; legacy container mount names remain for installer compatibility.

升级前停止使用这些目录的旧进程并备份数据，尤其是提交凭证和检索调用记录。详见[本地记录升级](../../docs/architecture/repository/local_record_upgrade.zh-CN.md)。
Stop old processes and back up data before upgrading, including submission receipts and retrieval call records. See the [record upgrade guide](../../docs/architecture/repository/local_record_upgrade.zh-CN.md).

## 访问范围 / Access

本配置用于本机运行：API 只绑定回环地址，PostgreSQL 和 Redis 不公开宿主端口。原生服务保持私有；启用面向用户的身份功能时，由工作台接口验证身份与资源归属。外网或共享主机部署需要独立配置认证、TLS、备份与运维。

This configuration is for local use: the API binds to loopback, and PostgreSQL and Redis have no published host ports. Keep the native service private; the workbench verifies identity and resource ownership when that feature is enabled. Internet or shared-host deployment requires separately configured authentication, TLS, backups and operations.

LangSmith 收集运行拓扑、时序和状态。配置隐藏输入与输出，但关联用的 ID 仍可能出现在跟踪中；使用前应检查所需的数据处理设置。
LangSmith records topology, timing and status. Input/output hiding is configured, but correlation IDs may remain in traces; review the data-processing settings before use.

This is **not a production deployment**. The native API uses **noop** authentication and binds to `127.0.0.1:${FINSIGHT_AGENT_SERVER_HOST_PORT:-18123}`; PostgreSQL and Redis have **no host** ports. The Agent Server layer does not provide a FastAPI, SQLite, direct-invoke or no-LangSmith fallback. The separate workbench BFF does not replace native run persistence.

## PostgreSQL schema upgrades

Use the existing deployment's Compose project, configuration and credentials. Validate with `config --quiet` so resolved secrets are not printed. Keep bootstrap-admin, Agent Server, FIN application and recovery-operator credentials distinct. The FIN application role has schema usage and `SELECT`/`INSERT` permissions; schema migration uses the bootstrap role.

Before applying a schema upgrade, back up the volume and stop the native writer. Replace `EXISTING_PROJECT` with the project that owns that volume and include the same Compose overrides used by the deployment:

```bash
docker compose -p EXISTING_PROJECT --env-file .env -f deploy/agent_server/compose.yaml stop langgraph-api
docker compose -p EXISTING_PROJECT --env-file .env -f deploy/agent_server/compose.yaml up -d langgraph-postgres
docker compose -p EXISTING_PROJECT --env-file .env -f deploy/agent_server/compose.yaml exec -T langgraph-postgres /bin/sh /docker-entrypoint-initdb.d/010-create-runtime-roles.sh
docker compose -p EXISTING_PROJECT --env-file .env -f deploy/agent_server/compose.yaml exec -T langgraph-postgres /bin/sh /docker-entrypoint-initdb.d/025-install-fin-runtime-lifecycle-v1-1.sh
```

The installer accepts only known schema versions and checks their catalog fingerprints; partial or unexpected schemas are rejected. Resume the updated application only after database readiness passes. After a write-incompatible migration, old writers must not remain in service. Retain the volume and its records; deleting it is not a migration procedure.
