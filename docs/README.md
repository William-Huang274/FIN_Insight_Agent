# 文档地图

这里是 FinSight-Agent 的公开文档入口。公开读者应该先从主文档、架构专题和公开评测摘要理解当前系统；工作日志、旧版本发布清单和阶段执行计划主要用于内部追溯，不作为公开主线阅读材料。

## 推荐阅读路径

| 你想了解什么 | 先看 | 再看 |
| --- | --- | --- |
| 快速理解项目 | [根目录 README](../README.md) | 公开评测摘要 |
| 理解整体架构 | [总体架构](architecture/fin_sight_agent_architecture.zh-CN.md) | 多智能体协作、数据与工具权限 |
| 理解智能体如何协作 | [多智能体协作机制](architecture/multi_agent_orchestration.zh-CN.md) | 上下文与状态管理 |
| 理解多轮和状态恢复 | [上下文与状态管理](architecture/context_and_state_management.zh-CN.md) | 后端与评测运行时 |
| 理解证据和权限边界 | [数据与工具权限模型](architecture/data_and_tool_access_model.zh-CN.md) | 投研质量评价体系 |
| 理解后端和评测能力 | [后端与评测运行时](architecture/backend_and_eval_runtime.zh-CN.md) | 公开评测摘要 |
| 看当前效果 | [公开评测摘要](eval/fin_agent_public_eval_summary.zh-CN.md) | 投研质量评价体系 |
| 本地试运行 | 根目录快速开始 | 演示入口、工作台快速开始 |
| 接入自己的数据 | 自有数据快速接入 | 数据与工具权限模型 |

## 公开主文档

- [项目主文档](../README.md)：项目定位、核心亮点、当前能力、快速开始、评测摘要和边界。
- [架构文档入口](architecture/README.md)：五篇架构专题的导航。
- [公开评测摘要](eval/fin_agent_public_eval_summary.zh-CN.md)：20 个真实风格案例的覆盖、结果和边界。

## 架构专题

- [总体架构](architecture/fin_sight_agent_architecture.zh-CN.md)：用户问题如何进入研究链路，证据、智能体、写作和校验如何串起来。
- [多智能体协作机制](architecture/multi_agent_orchestration.zh-CN.md)：研究负责人、范围构建、证据执行、专家、汇总、写作和校验如何通过结构化状态协作。
- [上下文与状态管理](architecture/context_and_state_management.zh-CN.md)：多轮追问、范围收缩、产物复用、状态恢复和旧状态失效规则。
- [数据与工具权限模型](architecture/data_and_tool_access_model.zh-CN.md)：证据来源、工具权限、来源强度和智能体可见范围。
- [后端与评测运行时](architecture/backend_and_eval_runtime.zh-CN.md)：本地工作台、任务运行、工具台账、模型调用量、耗时和评测报告。

## 使用和运行

- [命令行演示入口](demo/sec_agent_demo_entrypoints_v1.zh-CN.md)：单轮演示、多轮会话和已保存运行检查。
- [自有数据快速接入](deployment/local_custom_data_quickstart.zh-CN.md)：用自己的公开披露、市场快照和索引跑完整链路。
- [工作台快速开始](workbench/workbench_quickstart.zh-CN.md)：本地工作台入口、配置导入、数据包管理、任务运行和产物查看。
- [脚本发布面](../scripts/README.md)：当前主线保留的脚本入口和用途。

## 质量与评测

- [公开评测摘要](eval/fin_agent_public_eval_summary.zh-CN.md)：公开读者优先阅读。
- [投研质量评价体系](eval/fin_agent_investment_research_quality_framework_v0_1.md)：定义什么是好的金融研究回答。
- [分层质量门控执行文档](eval/fin_agent_layered_quality_execution_plan_v0_1.md)：说明各层智能体和节点如何过门控。
- [全链路与多轮评测计划](eval/fin_agent_full_chain_multiturn_eval_plan_v0_1.md)：详细测试用例设计和停止/推进规则。
- [S1-S8 用例矩阵](eval/fin_agent_s1_s8_agent_quality_case_matrix_v0_2.md)：分层用例覆盖和历史分层结果。

## 历史和内部资料

- [历史和内部资料索引](archive/README.zh-CN.md)：说明哪些文档不作为公开主入口。
- `docs/worklog/`：内部实现记录、排查过程和交接文档。
- `reports/model_runs/`：模型运行和评测审计记录。
- 早期 `sec_agent_v0_1`、`full30` 和旧云端运行手册属于历史资料，不代表当前扩展链路的公开状态。

## 写作规则

- 公开文档优先讲当前系统设计、当前结果和当前边界。
- 不在公开文档中写接口密钥、私有数据、云端临时地址、原始模型响应或供应商私有产物。
- 具体运行编号、失败排查和内部成本诊断放在工作日志或模型运行记录中。
- 有中文对应名词时优先使用中文；文件名、命令、股票代码、接口字段和通用技术缩写保持原样。
