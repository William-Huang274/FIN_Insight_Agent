# 研究图实现评估：复用 checkpoint，补齐研究关系

后续状态：Owner认可后完成首个React Flow真实依据链和本地草稿切片，见[S3/195](../worklog/fin_0_1_3_s3/195_live_research_graph_pilot.md)。成熟画布已完成当前React19接入资格；基线写入、分支与精确局部运行仍未实现。以下为原始有界评估，未据此承诺全量能力。

2026-09-08，提议/未实施。关联[概念B](../product/UX_RESEARCH_GRAPH_CONCEPT_20260908.zh-CN.md)。本轮只读源码、官方资料和可运行交互演示，不安装新运行时，不调用研究模型。

## 结论

无需为图视图替换底层架构。首先做现有研究产物的只读图投影，再接入有基线的修订草稿；精确到任意图节点的分支重跑后置。图上的研究节点与LangGraph执行节点不是一一对应关系。checkpoint保存执行状态，不能替代金融判断依赖记录。

## 当前代码依据

| 现有位置 | 可复用能力 | 当前限制 |
| --- | --- | --- |
| `src/sec_agent/agent_runtime/research_session.py:35` | case_papers、research_tasks/outcomes、review、synthesis、convergence_history | 没有完整的可编辑研究节点/边合同 |
| 同文件 current_task_artifacts / revision_handler | 原来源与CALC绑定；修订产出与report_version | 不能据此承诺只重跑选中图节点；现有修订仍按已有流程边界执行 |
| `src/sec_agent/agent_runtime/dell_report_session.py:97` | human_review interrupt，ask/revise/accept | 交互草稿不应每次键入都resume |
| `apps/workbench/backend/api/v1/report_sessions.py:270` | checkpoint历史、报告读取、diff | report_versions按整数report_version聚合；同号分支候选可能混淆，分支上线前须改为明确复合标识 |
| 同文件 action/source | `command.resume`、`multitask_strategy=reject`、指定checkpoint读来源 | 修订动作目前没有图草稿和其基线绑定，不应仅传自由文本就声称版本冲突安全 |
| `apps/workbench/frontend/package.json` | React19 / TypeScript / LangGraph SDK | 无图编辑器依赖，需小范围兼容资格 |

源码检查是当前能力判断，官方框架文档不等于本仓库已集成。

## 成熟栈取舍

- 图画布：React Flow / `@xyflow/react` 作为首选资格候选，负责节点、边、选择、缩放及交互，不自写画布基础设施。先核查锁定版本、React19兼容性与许可；复杂自动布局出现后再资格ELK等成熟组件。本轮未安装或验证集成。依据：[React Flow官方文档](https://reactflow.dev/learn)。
- 执行和持久化：继续现有LangGraph Agent Server、Postgres与SDK，使用其checkpoint/history/interrupt机制。依据：[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)。
- 分支：原生update_state可以从旧checkpoint产生新的分支检查点，历史保留；继续执行会重新运行其后节点，包括模型/API。不能把time travel等同“免费读缓存”或“自动精确增量计算”。依据：[Time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)。部署版本及父子图边界仍需本地资格。
- 不引入第二套工作流引擎、事件溯源平台或图数据库。当前规模先复用已有关系存储/产物结构，通过薄适配返回节点和边。

## 最小数据分工

| 对象 | 最少要知道什么 | 保存边界 |
| --- | --- | --- |
| 图视图 | 节点位置、折叠、选中、缩放 | 浏览器视图状态；不创建研究checkpoint |
| 研究节点 | 稳定ID、类型、修订、出处/定位、as-of与期间/单位、产物引用、原始核验状态 | FIN产物/结构化投影；正文按需读取，避免复制进每个checkpoint |
| 研究关系 | 起点/终点及对应修订、关系类型、关系出处和确认状态 | 仅投影明确记录的引用/计算依赖；模型提出的关联标为待核 |
| 修改草稿 | 基线研究修订及checkpoint、目标节点/修订、修改字段、理由与修改者 | 未提交内容先本地；持久化时用现有存储，不建立新的运行队列 |
| 候选结果 | 所属分支/基线、运行ID、产物修订、checkpoint、质量与采纳状态 | 复用原生运行记录；应用层明确当前接受的产物引用 |

稳定节点ID不能等于数组位置、图坐标、报告段落序号或checkpoint ID。同一节点可以跨多个checkpoint出现；一次checkpoint也可包含多个研究产物。source ID若只在论文/任务内唯一，投影要保留命名空间。

确定关系的初始来源：报告引用→来源、CALC→操作数及来源、明确任务产物→所属任务、原有审查finding→paper。判断→假设、反证→判断等若旧记录不存在，不从段落邻近或词语相似自动认定。旧报告允许图不完整，明确缺少结构化关系。

## checkpoint与执行建议

1. 读图/展开/拖动只读或更新视图；编辑假设形成草稿，不改变事实或研究运行。
2. 提交时服务端检查草稿所依据的研究修订仍匹配。head有无关运行变化时应按相关产物修订判断；无法安全区分就提示重新核对，不能默默套到新结果。
3. 用户修改转为领域修订请求，在现有审阅点进入既有修订流程。首版明确标为“提交针对该判断的修订”，不承诺任意节点重跑。
4. 完整checkpoint分支前先验证：父图/子图状态可见性、reducer更新语义、重复提交和并发提交、原引用可回读、候选不污染基线、取消/失败后不自动重发付费请求。
5. 精确局部执行需同时具备显式依赖、可独立重算的产物边界、运行节点映射及所有共享依赖。如果任一缺失，只能扩大范围并如实预览；不能用前端连线推断调度策略。

原始证据不可直接编辑。修订产生新假设/新产物，旧CALC及引用状态保留，假设成立与算术成立分开。不会按画布操作频率生成完整研究快照，也不需要把整个长聊天变为图数据。

## 最小接入顺序与停止点

1. Owner审阅本轮概念。下一工作包必须是可执行资格：React Flow接一条真实“报告引用→CALC→操作数→来源”只读链，0模型，缺失关系不补造。
2. 在已认可交互下增加绑定基线的草稿与既有修订入口；先以确定性fixture检查过期编辑、原记录保留、引用与版本一致，再按任务TokenBudgetBasis开展有界真实资格。
3. 第一条真实闭环通过后，再决定完整候选分支与精确受影响子图重跑。未达此阶段，不对外宣称全量可编辑研究推导图。

本次演示能证明交互链可操作；不能证明真实数据投影、持久化、重跑粒度、语义质量或token节费率。避免再连续扩写多轮纯设计文档。Hermes不是上述步骤的前置依赖，仍在Owner五项＋新增需求审阅后再讨论。
