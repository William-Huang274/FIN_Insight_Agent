# 按需父子任务：B/D工程验收

设计依据为[按需研究运行时](../architecture/on_demand_research_runtime.zh-CN.md)。本记录区分可调用内部能力、统一产品入口和研究质量，不另定义流程。新增能力默认关闭；本轮无付费模型请求，没有切换现有服务。

## 维护入口与替换

| 责任 | 维护入口 | 替换的假设 |
| --- | --- | --- |
| 宿主装配 | `admitted_delegation_tools` | 任意父run/个人空间都能借用研究权限 |
| 模型操作 | `delegation_tools` | 委派意味着同步执行完整专家流水线 |
| 原生执行 | `DelegatedTaskRuntime`、`delegated_task_session_graph` | HTTP响应丢失就再次创建任务 |
| 命令持久化 | `OrganizationTaskCommands`、V12 | 所有命令共用报告checkpoint的唯一位置 |
| 当前成果 | `complete_delegated_task`、`current_work_catalog` | 保存或旧成功回执等于当前任务完成 |
| 原文与版本回读 | `handoff_tools`、`read_delegated_evidence/note` | 把别人的底稿当原始依据；重新复制全部历史 |
| 上下文 | 共享`conversation_summary`及原有历史投影 | 主任务和子任务维护两套摘要策略；未变化任务每轮完整重复 |

运行时只返回确切状态和来源，不替作者形成判断。专业角色尚未通过此执行器时在创建前拒绝。第一阶段限制一层、每根执行最多四个子任务，预算仍来自已存在的根预算；新run不新建额度。

委派控制是宿主独立准入且已绑定预算后的内部能力，使用`delegated_task_control`权限类别；不要求用户为每次内部研究动作再次确认。外部系统修改、用户文件修改和知识入库仍沿用原有人工确认边界。模型提出委派不构成权限或新增额度。

父Agent选择的`method_ids`是优先方法，不是禁止子任务考虑其他方法。宿主可用方法目录的版本摘要一起固定；子任务可根据进展读取目录内的其他方法。方法正文不能授权工具或扩展资料权限，新增专业执行器也不能借读取方法来绕过准入。

## 内部合同

Java路径为`POST /v1/runtime/organization-executions/{execution}/task-commands/{operation}`。沿用独立RuntimeDelegation签名，不能用用户Bearer身份直接调用。当前组织和资料权限每次检查，关闭执行或撤权不走正向权限缓存。

`claim`接收Python `TaskCommand`与create专用`fixed_input`。宿主填写父/子身份、原checkpoint、预算和资料摘要；模型只填写问题、交付条件、所需方法与已读材料/笔记选择。create固定模型配置和来源入口；continue只能提供当前checkpoint与新要求；cancel不以仍然匹配运行中的checkpoint为条件。原始创建与后续请求、原始失败和成功回执分别保留。

`catalog/read`为只读恢复入口；catalog给出每个child最近的命令及原创建身份。`admit`在子图执行时绑定实际run并持续检查；`accept`记录实际SDK回执。迟到的accept不能清除取消记录，且不能把命令改绑到另一个run。未知派发只按原operation和请求摘要核对，不能换个命令ID再次接续。

V12只扩展现有`organization_report_command`：报告命令仍以execution/checkpoint串行；子任务按execution/child/checkpoint/action隔离；child创建身份全局唯一。报告读取明确过滤`command_kind=report`，子运行不会成为报告的“最新运行”。

父方可按需读取目录、当前运行状态、确切底稿版本，以及来源/计算回执；不默认拉回子任务全部历史。长回执显示分页，完整artifact供原有计算器使用，不改值、单位、期间或权限等级。引用权限和金融结论正确性仍由后续研究检查负责。

## 离线证据

2026-10-28：Python相关广泛回归321项通过；最后的方法目录及宿主装配调整后，父子任务与交接专项18项通过。Java共51项通过（包含临时PostgreSQL专项），最终命令专项再测5项通过。以上测试集有重叠，不相加作为独立用例总数。活动基线检查及仓库秘密扫描通过。

- `tests/test_delegated_task_runtime.py`：实际LangChain/LangGraph工具循环配确定性模型；原生SDK使用可丢响应的替身。验证父工具真实派发、重建适配器后只读恢复、取消、错绑定拒绝、保存后限额停止与接续、确切版本提交、旧完成不带入新run、原始操作数回读后得到25%的合成计算。没有调用供应商。
- `tests/test_conversation_handoff.py`、工作对象/上下文/预算及组织入口回归：保留旧入口权限、方法披露、版本和回读语义。
- Java `TaskCommandTest`：关闭或不合法动作在存储/权限调用前拒绝。
- Java `TaskCommandDatabaseTest`：在独立临时PostgreSQL实际执行V11→V12、持久命令和事务SQL，验证旧报告唯一约束保留、同父checkpoint两子任务、重复命令、未知阻塞、run身份固定、取消与迟到accept、当前授权拒绝。外层组织授权组件使用替身，**不是完整跨服务授权验收**。

常规Java测试运行`./mvnw test`。数据库专项需显式提供指向一次性数据库的`FINSIGHT_TASK_DB_TEST_URL`和`FINSIGHT_TASK_DB_TEST_PASSWORD`；夹具只在随机测试schema操作并清理该schema，禁止指向正式数据库。未提供时专项明确跳过，不能据此称数据库迁移验证通过。

## C接入与E待完成

C内部主Agent已可接收这些准入工具，并以单项操作替换新路径固定后继，见[C工程验收](on_demand_operation_acceptance.zh-CN.md)。主Agent公开入口装配以及根任务停止的浏览器到后台传播仍属E。新增Java内部接口须完成双方代码审阅，再按统一版本开放；BFF现有A2拒绝不支持新交付的行为保持不变。不得借旧`begin_research`绕过独立准入。

E使用检索方的新稳定基线，验证真实服务中的所有权、资料权限、取消、恢复、版本展示与导出。此处确定性测试不证明真实模型会合理委派、费用下降或金融研究质量提升；这些须在统一入口上另做授权范围内的实际使用测试。
