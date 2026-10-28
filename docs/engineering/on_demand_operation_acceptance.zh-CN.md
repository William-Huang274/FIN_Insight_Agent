# C：按需研究操作与统一主 Agent

2026-10-29。设计依据：[按需研究运行时](../architecture/on_demand_research_runtime.zh-CN.md)。本次交付研究侧内部入口、能力组合和离线工程验证；公开 Java/BFF 准入、部署切换和浏览器连续使用属于 E，尚未验收。没有供应商调用、数据库迁移或服务部署。

## 执行与替换边界

`create_on_demand_research_agent` 是待集成的唯一新主入口。它复用 `build_conversation_agent`，接收宿主已经批准的工具，包括 B/D 的委派、笔记和回读工具。主 Agent 可以直接回答、保存底稿、委派连续任务，也可以选择一项专业操作。专业操作返回同一个主 Agent；没有第二个调度器、任务库或消息历史库。

| 主 Agent 的选择 | 复用的实现 | 返回之后 |
| --- | --- | --- |
| 普通回答、材料读取、工作笔记 | 共享 conversation agent、现有 grants | 可以直接结束，不初始化旧 case，也不自动包装成报告 |
| 委派、接续、观察与取得子任务结果 | B/D 已准入工具和原生子任务 | 主 Agent 按需读取、继续判断；不自动转入专业角色 |
| `synthesize` | 现有 Lead 综合执行器 | 保存综合结果，返回主 Agent |
| `compose` | 现有成文、差异修订及引用校验 | 返回报告版本；不会自动复核 |
| `review_workpaper` | 现有 Counter 或 Verifier，由请求选择其中一个 | 检查选定的一份底稿，允许必要关联读取；不强制评价其他底稿或再跑另一个角色 |
| `review_report` / `review_synthesis` | 现有报告检查器 | 指定当前版本、全文或唯一原句选区；局部结果不表示整篇通过 |
| `revise_workpaper` | 原作者恢复、分批保存与提交执行器 | 返回版本变化与作者答复；不自动进入确认、综合或成文 |

自由形式的 B/D 笔记继续使用既有工作对象工具，不伪装成旧金融底稿 schema。主任务的 `deliver_working_note` 与子任务共用 `saved_note_artifact`，按当前版本分页读取、复核版本并计算摘要，交付时不让模型重写正文。专业 `revise_workpaper` 针对保有原作者身份的结构化底稿；普通笔记由同一主/子任务使用既有版本保存能力修改。没有底稿时，宿主可以提供已读取原文的 `CaseArtifacts.from_observed_sources` 视图，沿既有引用/成文能力生成报告，不为满足流程制造专家底稿。

在 `build_research_convergence_graph(operation=...)` 中，原来的完整阶段图被替换为“准备当前对象 → 执行这一项 → 返回结果”。新路径不进入 focused/single 的报告包装，也不采用 depth 决定后继。默认角色方法改为按需读取，当前操作指引替换旧阶段顺序要求；显式 Studio 自定义内容仍保留。

旧报告图仍供当前未切换服务和已冻结历史会话使用。E 切换时只能将新建任务指向一个已准入版本，不能同时开放两套新建流程，也不能把旧 checkpoint 静默迁移到新状态图。此提交没有通过旧 `orientation` / `begin_research` 偷开新动作。

## 状态、版本与权限

`research_object_catalog` 提供当前底稿、综合稿、报告及已读来源集合的摘要与分页入口。模型提交操作目的、准确目标版本和可选检查范围；runtime 在创建模型或资料会话前核对。范围是本次检查目标，不是来源权限；宿主的组织、固定资料及当前权限检查保持原样。

操作回执同时保存请求 basis 和实际可见输入版本。即使请求只指向报告，其他可见依据换版后也不能复用旧检查为当前结果。来源版本排除原始记录中单独保存的传输回执，以及可准确判定的空/冗余传输别名；原文、数值、单位、期间、计算操作数、非空别名及权限等级仍进入版本摘要。打开经过授权验证的新资料会话不会仅因回执 ID 不同就误报原文换版。

成功稿件仍在原生状态里，返回主 Agent 的消息只含状态、当前目录和可分页回读的操作入口；不复制全部正文，更不把作者私有会话作为交接。普通版本错误反馈可以在同一工具循环纠正；同批多个互斥的操作/交付不会竞争修改同一个状态字段。旧任务要求和没有当前版本绑定的复核意见不进入本次操作输入。

父循环的模型/工具次数跨操作返回累计，不把每次返回视为新额度。专业节点继续使用现有 `TokenBudgetBasis`、共享根预算守卫、来源访问检查、模型用量和失败记录。操作目的替换旧阶段目的，既有输出/推理上限与停止策略不变；额度不会作为“最后一轮必须收尾”的研究要求写进 prompt。原生人工批准仍用于外部修改，不因进入按需主 Agent 而失效。

交付既有底稿只引用准确对象版本，不要求全文重新生成。终态复用 `TaskOutcome`：请求报告却只回复“已完成”、没有提交成果时为 incomplete，不把模型结束输出等同于交付。未做复核明确为未评估；若宿主准入明确要求报告独立检查，当前全文检查缺失、不完整或有未解决重大意见时不能冒充已完成交付。检查回执始终不是金融正确性担保，runtime 不替作者接受意见或修正判断。

## 离线验收与剩余工作

`tests/test_on_demand_research.py` 使用实际 LangChain/LangGraph 工具循环、checkpoint、MCP 和确定性模型，覆盖普通回答、底稿交付、综合/成文独立返回、单份 Counter/Verifier、原作者修订、来源直接成文、旧版本失效、校验反馈纠正、父额度累计和人工批准接续。`tests/test_organization_phase_factory.py` 增加实际组织资料工厂与专业执行器的单项成文测试；权限外资料、个人上传与外部供应商调用在测试中禁止。

本轮相关子系统广泛回归234项通过；最后补齐自由笔记交付、终态及同一主Agent选择“综合→成文→检查→交付”的原生连续链路后，主入口、B/D、共享对话及实际组织工厂专项75项通过。测试集有重叠，不相加为独立用例总数。活动基线、秘密扫描及差异检查通过。未改Java、BFF、检索实现或部署配置。

复现命令：`python -m pytest -q tests/test_on_demand_research.py tests/test_delegated_task_runtime.py tests/test_conversation_agent.py tests/test_organization_phase_factory.py`；邻接回归包括 `test_research_convergence.py`、`test_case_review_agent.py`、`test_report_synthesis_agent.py`、`test_research_session.py`、`test_research_session_startup.py`、`test_delivery_intent_contract.py`、`test_conversation_handoff.py`、`test_research_guidance_runtime.py`、`test_saved_report_source_review.py` 和 `test_organization_case_artifacts.py`。使用项目锁定的运行/测试依赖，不需要私有数据或供应商凭据。

测试证明调度、来源与版本边界可以执行；不证明真实模型会恰当地选择能力、研究质量提升或费用下降。

E 必须完成：双方逐文件审阅 B/D/C；公开根任务命令与唯一创建/恢复入口接线；宿主提供当前授权成果 reader、已有根预算、固定模型配置、原生持久化及停止传播；前端正确展示成果类型、检查范围和版本；统一服务无模型检查与后续授权的真实使用。普通回答不要求预先构造 case，来源视图由宿主恢复与验证，不能接受浏览器/模型上传的“可信来源对象”。

2026-10-29 集成方确认上述宿主接线合同没有明显接口冲突，但尚未逐文件审查。检索 R01–R30 仍在整体验收，`7676bc4f`、`291446d5` 均不是 E 最终稳定基线。后续须取得其明确稳定提交、测试范围及部署配置后再合并与部署，不以本研究分支较旧检索代码直接替换当前优化。
