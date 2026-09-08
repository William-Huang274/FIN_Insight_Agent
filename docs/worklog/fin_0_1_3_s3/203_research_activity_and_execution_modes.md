# 203 研究资料关联、Agent 活动流与可选运行模式

日期：2026-09-08。产品 FIN 0.1.3；现存 Dell v5 未接受、不覆盖。当前工作分支 codex/fin013-report-reader，从 PR #5 合并后干净基线继续。

## 本轮要求和实施范围

对应 [正式前端方案](../../product/FRONTEND_OVERALL_DESIGN_20260908.zh-CN.md) 的最新修订：同源专题/判断/来源关系，自然语言名称，宽幅公开 Agent 活动流；新建/追问/修订模式和模型从界面接到原生执行；准备难度、模式不同的测试题并实测。

成熟栈选择：沿用已安装 LangGraph StateGraph/Send/ToolNode/create_agent、官方 SDK custom stream、Assistant/run config、现有公开审计文件。依据官方 streaming 与 workflows-agents 文档核对，无新调度器/状态库/通用规则平台。公开进展是已有 reason_summary 或显式 report_research_progress 产物，绝不读取私有推理日志渲染。工具事件持久化仍使用现有审计文件；用量只统计 model 事件。

## 当前状态

- [x] 同源资料路径、自然语言显示与前端三宽度检查。
- [x] 公开活动流真实持续更新及历史回读。
- [x] 单 Agent / 自由 / 指定 / 完整模式原生消费及选择回执。完整模式沿用既有流程，本轮不追加大型完整研究付费重跑。
- [x] 新题、追问、修订模型选择真实消费；Flash 和 Pro 均有真实请求。
- [x] 五类小题实测完成，含失败共九个 attempt，费用完整归集。
- [x] 本地真实界面部署、截图内容审阅。
- [x] 代码与文档分开提交，推送 [PR #6](https://github.com/William-Huang274/FIN_Insight_Agent/pull/6)；最终 CI、合并与临时远端分支状态由该 PR 和远端引用记录承载。

产品增量：研究资料与研究地图共用 reportTopics 和服务器引用绑定，按专题→判断→来源展开；编号保留底层身份，界面使用判断内容、来源标题或自然语言编号说明。未绑定的正文编号不会伪装为证据链接。公开 Agent 活动在主栏按时间追加，工具调用可展开；切换历史、回到最新、节点过滤、运行中意见与停止均有真实接口。任务说明在尚无报告的运行页也可以关闭。

工程增量：ExecutionOptions 经 Pydantic/实际目录校验后进入 run config，模型选择替换既有角色模型并保留预算和推理合同。自由模式由原生 Lead 选择必要研究范围；指定模式只允许所选专家；单 Agent 新研究绕过 Lead 和多角色复核，产物明确未独立复核、不能直接接受。追问咨询使用原生 create_agent/ToolNode、独立子上下文、已绑定引用回传；没有新工作流引擎或公司名称路由规则。

研究证据与限制：实际新增 NVIDIA 收入研究、NVIDIA/Micron 财年口径比较；仍需人工审阅，不据这两题声称任意公司全案金融质量已通过。Dell v5 未修改/未接受，RC-S3-199 旧判断与报告措辞漂移仍开放。

## 有界实测计划与预算依据

先完成确定性检查，再逐项启动 fresh attempt，结果不明不重发。原主任务报告不自动接受。小题覆盖：概念/口径澄清的简短追问、跨来源对照的指定专家追问、单 Agent 新研究、自由调度小研究、报告限定语微修订。已批准真实模型调用及此批实测；本轮总费用保护上限暂取 12 元，非目标消费；每项完成即审阅，失败先修根因，不按余额追绿。该上限只控制是否再发起下一项，不静默删减必要研究。

TokenBudgetBasis：每个实际调用继承 runtime/research_session.json 的角色合同。输入为当前问题、当前报告/目录和角色按需读取的资料；咨询子节点使用新的 quick_writer 历史，只接问题、范围和资料目录，不转发主 Agent 私有历史。所需输出为有绑定来源的回答/工作底稿，保留期间、计算与未核实边界；单 Agent 输出不包含伪造的审查结论。新增公开进展工具使用短公开说明，不重复原文。模型切换仅替换已有模型 ID，保留各角色 reasoning_profile、max_output_tokens、max_input_characters、超时、零传输重试和截断停止；比较依据是此前短问 43,622 tokens / 0.085984 元与小修订 272,176 tokens / 1.436408 元，非同题基准。新模式质量与费用必须靠本轮独立运行记录，不能从旧数字推定改善。咨询最多两次，子节点无继续分派工具。

若一项复杂研究触及预算、失败或公开记录用量不明：保留原尝试，停止新增付费，先查选题范围、重复上下文和实际节点，再决定是否需要 Hermes 有界资格；不直接替换底层架构。

## 已知边界

当前资料部署仍含 Dell 专用历史绑定。不同公司题目只能按可达上传/公开文献来源验证，不把该部署宣传为通用实时证券数据库。原 RC-S3-199 claim/report 漂移不由此次界面名称修改关闭。

## 实际模型运行与失败保全

均由前端发起；原生 checkpoint、公开调用审计和私有请求日志保留在本地原目录，不提交原文到 Git。金额为运行用量×已配置分时单价的估算，不是账单。全部 93 次请求均有用量与费用回执，无未知/待计价。

| Attempt | 题目/模式 | 实际模型节点或停止原因 | 调用 | tokens | 已知元 |
| --- | --- | --- | ---: | ---: | ---: |
| A1 | Dell 短问，单 Agent/Flash，优化前 | quick_writer | 2 | 44,069 | 0.041490 |
| A2 | 订单证据边界，指定需求专家/Pro | quick_writer + Q2_DEMAND_QUALITY；无其他专家 | 11 | 332,365 | 0.399698 |
| A3 | NVIDIA 收入，单 Agent/Flash | 问题型入口被误当 Lead assignment，调用前 KeyError | 0 | 0 | 0 |
| A4 | 同题，新尝试 | 正确 SQL/计算后被旧 Dell F2 文献门槛阻断，research_needs_attention，无报告 | 14 | 512,472 | 0.186043 |
| A5 | 同题，新尝试 | 入口门槛修复，但下游产物投影丢失当前问题作用域，再次旧门槛拒绝 | 6 | 111,806 | 0.086291 |
| A6 | A1 同问题/同模式/同模型，历史按需读取后 | quick_writer；Dell v5 不变 | 2 | 25,495 | 0.026517 |
| A7 | NVIDIA 收入，单 Agent/Flash | 仅 specialist:Q1_ISSUER_TRUTH；v1 未独立复核 | 5 | 84,774 | 0.065476 |
| A8 | A7 财年衔接文字微修订，自由/Flash | writer + report_verifier；v1→v2 待人审 | 12 | 238,828 | 0.228074 |
| A9 | NVIDIA/Micron 财年比较，自由/Flash | Lead 仅选 Q1；Counter、Verifier、Synthesis、ResearchVerifier、Writer、ReportVerifier | 41 | 506,744 | 0.423949 |
| 合计 | 六个成功运行＋三个失败/需处理尝试 | 失败费用包含在内 | 93 | 1,856,553 | 1.457538 |

Run IDs（按 A1–A9）：

```text
01a08132-2e2a-72e0-b314-4761b16c67b3
01a08134-5b97-7e41-8fdf-a5e09b12a1e9
01a08137-b7d0-7ae2-9a11-5343dc4020f5
01a08141-8f06-78b2-a2b8-f461f6835713
01a0814c-4035-7281-b3b3-5e8876c8bb87
01a0814d-797c-7490-af24-baff17137f56
01a08154-e0b3-7003-a0f4-fe5a59f6dcc6
01a0815a-52f2-77b0-9a99-79f857082589
01a0815b-ba1b-7742-abc0-c4960c39e88e
```

公开审计路径模板：`Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/report-workbench-20260906-a1/calls/{thread}/{run}/model-call-events.jsonl`。本地汇总：`D:/temp/fin-activity-mode-real-attempts.json`。原生 API 18165，BFF 18793；原 PG/Redis volumes 未改。

A7 核对 FY2025 2024-01-29→2025-01-26 收入 130,497,000,000 USD，FY2026 2025-01-27→2026-01-25 收入 215,938,000,000 USD，同比约65.5%；两年增长不足以单独证明盈利质量。原文财年先后方向写反，在前端定位实际“单位与财年可比性”判断后提交 A8，修正为后一财年期初在前一财年期末次日，明确2025-01-26接2025-01-27。结果只有一处 diff hunk、收入与同比未变；Writer 重查了两个事实，引用绑定确有更新，不能称引用未变。v1 checkpoint 保留。

A9 另取得 Micron FY2025 2024-08-30→2025-08-28 收入 37,378,000,000 USD，说明两个财年标签不能直接当同一自然年。只有一个专家方向被激活，但后续固定多层审查仍执行。两份新报告均未由 Owner 接受；模型短问超过180字的要求也未被包装为完美遵循。

## 根因修复、上下文与成熟栈决定

A3 修复 question-only task_context 适配，旧有 assignment 模式不变。A4/A5 的最早责任层是当前研究问题与历史案例资格混用：当前用户研究任务不再强制 Dell 案例专用文献路线；task_context 的当前问题/来源在工作底稿验证与产物投影间保持。原始来源权限、精确引用、数值与计算回执、未知引用拒绝仍执行；旧 Dell 专项案例继续执行原路线门槛。回归覆盖两条路径及伪造引用拒绝，不能将旧门槛失败改称信息未披露。

A1→A6 使用已有公共历史按需读取工具，不再逐轮注入全部旧问答。请求只保留最近两条短预览与索引；全部原文和引用仍持久化，可分页读回。同题两次均两次模型调用，总 tokens 44,069→25,495，下降42.1%；这是 n=1、缓存/历史时点不同的局部证据，不能外推普遍节费或证明所有细节质量相同。自动摘要仍 disabled，现有 LangChain 工具输出清理继续启用。

已按最新授权核查 [Hermes Context Engine](https://hermes-agent.nousresearch.com/docs/developer-guide/context-engine-plugin) 和 [官方压缩/缓存说明](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/context-compression-and-caching.md)：请求选择与持久历史分离、压缩和观察钩子可作为候选；选择/重排会影响缓存前缀，插件失败的 fail-open 行为不能当成本硬上限。

决定：**Adopt** 既有 LangGraph/LangChain 与按需历史读取；**Hold** 整体 Hermes runtime 替换。A9 小题仍41次调用，累计50万 tokens，不是单轮上下文溢出的同义词；只接压缩不能取消固定审查次数。下一片若开展 Hermes 资格，限一个执行节点/上下文策略对照，保持金融 artifacts/checkpoints 和复核语义不变，比较数值/限定语/引用回读、缓存、总费用与故障恢复。尚未安装或接入 Hermes，不声称已省费。另需评估与题目复杂度匹配的复核策略，不能为便宜静默削弱独立核验。

## 验证与展示

- Project OS profile preflight 通过，0模型；15个相关 Python 测试文件最终 **263 passed / 19 skipped**（材料/环境跳过），包含原生图路由、作用域保留、历史按需读取、引用回传、BFF与基线修订。
- 初次审计 fixture 测试失败、两项旧 revision_handler 兼容测试失败均保留并修根因；原生研究 graph 显式要求 case_review 才走研究修订，旧公共 builder 的默认兼容不变。
- 保存投影 a1 回放发现它不是完整带 digest 的 canonical notebook；a2 只核对实际投影四条判断的新旧路线门槛，未伪装为 checkpoint 全链重放。canonical graph 路径另有测试和 A7 实跑。
- TypeScript/build 通过，现有约926KB主包的 chunk-size 提示仍在；未为去提示引入新依赖。
- 公开浏览器 suite 15项，1440/1024/390三宽度，含流式追加、历史选择关闭、运行无报告时关闭资料、同源图/资料跳转、修订 diff、空范围禁止发送、模型/模式真实 payload。最终输出目录 `D:/temp/fin-activity-modes-browser-a6`；此前 a1失败与a2–a5结果保留。
- 默认兼容后端浏览器首次启动被 Windows 保留端口8765阻断（default-a1，0模型）；补充 `FINSIGHT_E2E_BACKEND_PORT`，监听与 Vite 代理同步，18795下 default-a2 **18 passed**。公开 suite 无后端，不受该端口影响。中英文试用说明已补充配置方式。
- 仓库 secret scan **8,691 files / 0 findings**，JSON ledgers/题目集解析与 diff whitespace 检查通过。
- 实际页面截图 `D:/temp/fin-activity-public-capture-a1`，1600×1000、0 page errors、0写请求、0模型调用。选取新起始页和 A9 已完成公开活动流，非伪造实时运行；保留此前 Dell 地图和配置编辑图。
- 可复用题目与检查要点见 [workbench_execution_modes.json](../../../eval_sets/workbench_execution_modes.json)。大型完整模式题目仅备好，未在本批追加付费。

发布：工程提交 `b5a5dfc9`、实测/展示提交 `f8ac4de1` 已推送 [PR #6](https://github.com/William-Huang274/FIN_Insight_Agent/pull/6)，本地提交后工作区干净。最终 CI 与合并状态查看该 PR；检查通过后按 Owner 授权合 main 并移除临时远端分支，保留 main 与两个 history 分支。FIN 0.1.3 不升版、不创建 release、不自动接受报告。
