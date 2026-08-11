# 历史和内部资料索引

本目录用于说明哪些文档不作为 FinSight-Agent 的公开主入口。它们可以保留在仓库中用于追溯实现过程、旧版本发布、内部执行计划或故障排查，但不建议放入简历、项目展示或公开阅读路径。

## 不作为公开主入口的资料

| 类型 | 当前位置 | 处理口径 |
| --- | --- | --- |
| 工作日志 | `docs/worklog/` | 内部交接和排查记录，保留但不作为公开导航 |
| 模型运行明细 | `reports/model_runs/` | 审计资料，公开摘要只引用关键结论 |
| 扩容执行计划 | `docs/architecture/layered_data_source_expansion_*.zh-CN.md` | 阶段执行文档，公开层面沉淀到架构专题 |
| 扩容后执行框架草案 | `docs/architecture/expanded_universe_retrieval_agent_framework_v0_1.zh-CN.md` | A6 前后的内部执行文档，当前公开状态以 README 和公开评测摘要为准 |
| 早期发布清单 | `docs/release/sec_agent_v0_1_pre_release_checklist*.md` | full30 时代历史资料，不代表当前 603-company 扩展状态 |
| 早期云端运行手册 | `docs/deployment/sec_agent_cloud_full_source_runbook_v1*.md` | full30 时代云端手册，不作为当前部署入口 |
| 早期评测生成提示词 | `docs/eval/sec_agent_*_case_generation_prompt.md` | 历史评测设计材料，不作为当前评测结果 |

## 公开读者应优先阅读

- [项目主文档](../../README.md)
- [文档地图](../README.md)
- [架构文档入口](../architecture/README.md)
- [公开评测摘要](../eval/fin_agent_public_eval_summary.zh-CN.md)

## 后续整理原则

- 新增公开文档应讲当前系统设计和当前结果，不复述内部推进过程。
- 历史文档可以保留原路径，避免断链；但公开导航不再把它们列为主要阅读入口。
- 如果未来需要清理仓库展示面，可以把历史文档移动到单独归档目录或私有资料库，再统一修正链接。
