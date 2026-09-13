# 001：多用户运行、研究经济性与产品定位

2026-09-13。状态：规划补充；运行时和研究效果尚无增量。

用户要求将队列/并发/中断/接续/进程锁纳入真实部署准备；在成本与质量约束下优化工具、模型和runtime分工；明确与通用Agent加skill相比的系统价值。用户可能租服务器不等于已经授权购买或上线。

产品源文档：[0.1.4规划](../../product/fin_0_1_4_research_plan.zh-CN.md)。更新该文，不创建第二套执行规划。持续公司/议题跟踪、订阅加有限额度、BYOK选项均为助手建议，未宣称市场验证或用户已经确认收费模式。

## 现状证据

- `deploy/agent_server/compose.yaml`已有PostgreSQL/Redis、Agent Server和`N_JOBS_PER_WORKER=4`；这不是容量验证。
- `apps/workbench/backend/api/v1/report_sessions.py`、`conversations.py`使用`runs.create`、`multitask_strategy=reject`、interrupt取消、checkpoint/resume和stream接续；跨用户公平性和全局预算尚未被这些调用证明。
- `src/sec_agent/agent_runtime/agent_server_entry.py`的sink锁明确仅进程内；`src/sec_agent/workbench/process_runner.py`有进程内semaphore。需要逐共享资源审计，不可把它们统称为已具备分布式锁或一律升级为新锁服务。
- 208公开评测中MSFT约4.63元估算包含不同执行段和人工修改后继续运行，不等同用户本次“单case约4元”口径。211案例约16.92元已知费用估算、2请求未知、native Writer未完成。不得混合样本、实验或账单口径。
- PR #9于本次讨论前合并`271e4ee5`；当前规划分支从该main创建。此前完整测试仅证明0.1.3基线，不视为0.1.4验证。

## 2026-09-13核实的外部依据

- [Agent Server架构](https://docs.langchain.com/langsmith/agent-server)：内置持久化和任务队列，PG保存任务数据，Redis负责信号、取消与流式通信；可拆API和queue。当前官方说明不能替代锁定0.13.3实测。
- [独立部署](https://docs.langchain.com/langsmith/deploy-standalone-server)：列出license key和使用报告要求；小规模Docker与正式Kubernetes支持路径不同。需核实本项目版本、账户许可、总费用和退出成本，不能断言当前开发部署已获商业托管权限或推定具体收费。
- [Codex定价](https://learn.chatgpt.com/docs/pricing)：订阅用量随任务、模型和上下文等变化，API key按API价格计费。订阅价不能直接换算为可转售的后端推理预算，也不据此推断供应商利润。
- [WorkBuddy积分说明](https://cloud.tencent.com/document/product/1831/134339)：积分与模型定价和任务复杂度相关。没有取得其单位成本或利润数据，不认定亏损补贴或推断功能限制的动机。

## 最小后续与判断条件

先归因既有调用、核实当前许可和部署能力，用模拟供应商验证排队/取消/故障/重复提交/预算，避免产生新研究费用。然后在同一真实问题上比较0.1.3、通用Agent加同等资料工具方法、0.1.4候选；固定模型比较runtime，再单独验证模型分工。加入一次新披露或修订，检验持续价值；差异不得靠剥夺基线能力制造。

记录关键错误、有效反证、报告完成、人工时间和包含失败的合格交付成本。并发验证须含短长混合任务、跨worker和服务中断；未知外部调用不自动重发。没有获得质量/费用改善就不扩展专家层数或平台规模。

本次仅阅读代码/旧结果/官方文档，更新规划、路线图和接续记录；未修改代码、执行模型API、部署、购买、迁移或发布0.1.4。文档验证为相对链接、diff和候选内容检查，不重复完整产品测试。下一工作应产出离线归因或可执行验证，不能继续只扩写规划。提交/推送回执由本任务最终回复提供。
