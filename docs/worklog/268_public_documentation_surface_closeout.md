# 268 Public Documentation Surface Closeout

## Prompt

用户要求按公开展示范围重写项目文档：主 README 不承载所有细节，新增架构专题和公开评测摘要；同时把不应作为公开主入口的内部规划、历史发布和工作日志收口到归档口径，并推送文档分支。

## Decision

- 新增公开文档，而不是继续扩写主 README。
- 公开文档优先使用中文术语，保留文件名、命令、股票代码和必要技术缩写。
- 工作日志、模型运行明细、旧 full30 发布清单、云端 runbook 和扩容执行计划不再作为公开主导航。
- 不大规模移动历史文件，避免断链；通过公开文档地图、架构入口、归档索引和历史文档顶部说明明确当前阅读口径。

## Work Completed

- 新增五篇公开架构/系统说明：
  - `docs/architecture/fin_sight_agent_architecture.zh-CN.md`
  - `docs/architecture/multi_agent_orchestration.zh-CN.md`
  - `docs/architecture/context_and_state_management.zh-CN.md`
  - `docs/architecture/data_and_tool_access_model.zh-CN.md`
  - `docs/architecture/backend_and_eval_runtime.zh-CN.md`
- 新增公开评测摘要：
  - `docs/eval/fin_agent_public_eval_summary.zh-CN.md`
- 新增历史和内部资料索引：
  - `docs/archive/README.zh-CN.md`
- 更新公开入口：
  - `README.md`
  - `README.zh-CN.md`
  - `docs/README.md`
  - `docs/architecture/README.md`
- 给中文历史执行/发布文档加顶部说明：
  - `docs/architecture/layered_data_source_expansion_plan.zh-CN.md`
  - `docs/architecture/layered_data_source_expansion_execution_plan.zh-CN.md`
  - `docs/architecture/expanded_universe_retrieval_agent_framework_v0_1.zh-CN.md`
  - `docs/deployment/sec_agent_cloud_full_source_runbook_v1.zh-CN.md`
  - `docs/release/sec_agent_v0_1_pre_release_checklist.zh-CN.md`

## Result

公开文档现在分为：

- 主入口：根目录 `README.md`。
- 架构专题：总体架构、多智能体协作、上下文与状态、数据与工具权限、后端与评测运行时。
- 当前效果：公开评测摘要。
- 内部/历史资料：工作日志、模型运行明细、扩容执行计划、旧 full30 发布和云端手册。

## Verification

本轮只改 Markdown 文档，没有运行代码测试。应执行的校验是：

- `git diff --check`
- 链接和路径关键字搜索。
- 秘密关键词扫描。

## Follow-Up

- 英文 README 和英文公开文档可在中文口径稳定后再同步。
- 若后续要进一步清理公开仓库展示面，可以把历史文档移动到单独归档目录或私有资料库，再集中修正链接。
