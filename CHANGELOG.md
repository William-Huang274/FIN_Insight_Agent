# 更新记录 / Changelog

## v0.1.3 · Local preview / 本地预览版

### Research workspace / 研究工作台

- 公司资料库、财务数据查询、原文阅读和来源计算。Company documents, financial queries, source reading and traceable calculations.
- 多角色研究、可编辑方法与执行配置、角色底稿和公开运行活动。Multi-agent research, editable methods, execution settings, working papers and visible activity.
- 报告地图、定向修订、版本差异及人工编辑。Report navigation, targeted revisions, version comparison and human editing.
- 同一报告导出 Markdown、PDF、Word、PowerPoint。Markdown, PDF, Word and PowerPoint exports from the same report.
- 文档/图片上传、后续追问、任务工作记忆与计算回读。Document/image attachments, follow-up questions, task memory and saved calculations.

### Engineering / 工程更新

- 使用 LangGraph Agent Server、PostgreSQL、Redis、MCP 和 LangSmith。Native execution, persistence, tools and observability.
- 本地身份校验、资源归属检查与工具审批。Local identity, resource ownership checks and tool approval.
- SQLite 本地记录替换旧缓存依赖，保留提交去重与历史结果。SQLite records replace the legacy cache dependency while preserving idempotency and saved results.
- 运行模块改为功能命名，部署入口统一为 `research_workbench`。Runtime modules use functional names and deployment uses the `research_workbench` entry point.
- 更新双语文档、实际界面截图、合成测试与容器检查。Bilingual documentation, actual screenshots, synthetic checks and container verification.

本版本需要使用者配置资料和凭据，金融判断仍需人工复核。示例和评测不代表生产多租户或无人审阅研究保证。
This preview requires configured data and credentials. Financial conclusions require human review; the evaluations do not establish production multi-tenancy or unattended research reliability.

[版本说明](docs/product/version_0_1_3.zh-CN.md) · [Evaluation](docs/public/technical-evaluation.en.md) · [路线图](docs/product/roadmap.zh-CN.md)

## Earlier versions / 早期版本

早期 SEC 研究演示和后续实验可通过 Git 历史查询。当前功能与运行方式以 README 和公开文档为准。
Earlier SEC research demonstrations and experiments remain available in Git history. The README and public documentation describe the current functionality and setup.
