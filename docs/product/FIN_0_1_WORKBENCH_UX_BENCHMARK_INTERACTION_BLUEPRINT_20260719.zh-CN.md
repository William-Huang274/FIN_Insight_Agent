# FIN 0.1 Workbench UX Benchmark & Interaction Blueprint

> **实施状态更新（2026-07-19）**：用户已接受本蓝图的信息架构方向。可运行实现已在现有 React/Vite 产品中以 `/next` 独立路由落地，旧 `/tasks` 路径保留用于对照和回滚。当前实现覆盖 Task Center、Case Run、Evidence、Workpaper、Report、Human Review 与 Inspect，默认中文并支持英文切换；真实本地 10-cell/31-candidate 读模型已接入。模型运行按钮继续保持未准入，三-cell DeepSeek 纵向执行包已完成 freeze-only，等待显式付费调用批准。该状态不代表 Human Senior Review、RG1、RG3、RG4、FIN 0.1 发布或 production readiness 通过。

> Status: `DRAFT_FOR_USER_DECISION`
>
> Date: 2026-07-19
>
> Scope: FIN 0.1 Internal Alpha 的产品界面与交互冻结候选。本文不构成 release admission，不改变现有 runtime authority，也不授权真实业务 Case mutation。

## 1. 这份草稿解决什么问题

当前 Workbench 已经具备 Case、DecisionSurface、Evidence、Numeric、Workpaper、Deliverable、Review 与 Trace 等后端对象和前端模块，但界面仍以“对象页 + 审批状态 + 技术字段”为主要组织方式，导致三类问题：

1. 分析师看见的是系统对象和流程节点，不是“我正在完成哪项研究判断”。
2. Evidence、Workpaper、Deliverable 与 Review 分散在多条平级路由，研究主线被页面导航打断。
3. Case ID、digest、fixture、source access 等调试信息进入产品主界面，使产品更像中台或运维控制台。

本轮不继续局部美化，而是冻结一套可以直接指导实现的产品信息架构，并用独立原型验证布局、状态和跳转。

## 2. 产品定位与 FIN 0.1 边界

FIN 0.1 是面向内部 analyst 与 senior reviewer 的 **Institutional Research Control and Memory System**。它不是通用聊天机器人、无约束 agent builder、报告生成器，也不是企业后台审批系统。

首版必须支持的用户主线：

`创建 Case -> 接受研究计划 -> 运行研究 -> 检查证据与数字 -> 形成底稿 -> Senior Review -> 形成内部报告 -> 保留 exact record`

首版 P36 研究范围围绕 AI 基础设施利润捕获，覆盖需求真实性、accelerator、server OEM、foundry/advanced packaging、HBM、semicap 与跨链反证。Data Room 全链、Watchlist、Quant Lab、完整企业管理、实时行情与生产 cutover 不进入本轮界面承诺。

## 3. Benchmark：借鉴什么，不借鉴什么

| 产品类型 | 借鉴 | 明确不借鉴 |
| --- | --- | --- |
| AlphaSense Workspaces / Workflow Agents | 研究空间可恢复；从 signal 到 source-backed output 的连续工作流；重复研究任务可配置 | 把全量内容库搜索作为唯一入口；用功能菜单代替研究任务主线 |
| Hebbia Matrix | 多文档结果的矩阵比较；每个结果可回溯到原文；复杂工作流保持透明 | 把所有问题压成电子表格；让列配置成为普通分析师的首要工作 |
| Bloomberg RMS / FactSet 类研究系统 | 高密度、可扫描、面向公司/主题的持久研究记录；内部研究与数据并置 | 终端命令式学习成本；为覆盖所有资产类别而牺牲当前任务清晰度 |
| NotebookLM | 回答与来源并列；引用是阅读入口；来源范围对用户可见 | 以聊天记录作为最终研究资产；把综合结论留在一次性回答中 |
| Elicit Systematic Review | 搜索、筛选、抽取、综合分阶段；每一步有明确 inclusion/exclusion 决策 | 将学术论文工作流原样套入金融研究；用机械打勾代替 senior judgment |

参考资料：

- AlphaSense Platform: https://www.alpha-sense.com/platform/
- AlphaSense Workspaces: https://help.alpha-sense.com/hc/en-us/articles/51087728136979-Getting-Started-with-Workspaces
- Hebbia Matrix: https://www.hebbia.com/product
- Bloomberg Research Management: https://www.bloomberg.com/professional/insights/trading/how-research-management-solutions-help-firms-solve-complex-market-challenges/
- NotebookLM: https://workspace.google.com/products/notebooklm/
- Elicit Systematic Review: https://elicit.com/blog/systematic-review/

## 4. 核心产品原则

### 4.1 Case-first，而不是 Agent-first

用户创建和返回的是研究 Case。Agent、模型、插件、Skill、知识图谱与编排方式是 Case 的 Run Profile，不应成为导航一级对象。

### 4.2 Artifact-first，而不是 Log-first

主画布始终显示当前正在形成的研究资产：研究计划、证据矩阵、底稿或报告。运行过程在相邻区域呈现，但不能挤走研究结果。

### 4.3 展示结构化执行轨迹，不展示原始思维链

可展示：目标、计划、当前 agent、工具调用、检索范围、接受/拒绝的证据、数字计算、缺口、handoff、错误与下一步。

不展示：模型私有 chain-of-thought、冗长 token 流、内部提示词、无用户价值的 debug dump。

### 4.4 一页一个主对象

- Task Center：Case 列表。
- Case Ready：待接受的研究计划。
- Case Running：当前研究进度与正在形成的底稿。
- Evidence Matrix：证据决策矩阵。
- Workpaper：可编辑底稿版本。
- Senior Review：待审 exact artifact。
- Report：决策叙事。
- Inspect：运行审计记录。

### 4.5 渐进披露

分析师默认只看研究问题、判断、证据、数字、反证和下一步。对象 ID、digest、版本 lineage、调用计数和 raw trace 只在 Inspect 模式中出现。

### 4.6 模式不是页面堆叠

Case 顶部提供三种模式：

- `研究`：运行、证据、底稿与报告。
- `复核`：待审判断、inline comment、repair 与 exact outcome。
- `检查`：agent、工具、调用、成本、版本与错误。

## 5. 信息架构

### 5.1 全局层

全局导航只保留四个入口：

1. 研究任务
2. 工作底稿
3. 证据库
4. 待我复核

模型、插件/Skill、知识图谱和 agent 编排不放在全局左栏。它们属于 Run Profile，可从 Case 命令栏打开，也可保存为团队预设。

### 5.2 Case 层

打开 Case 后进入独立的 Case Workspace：

```text
Case Command Bar
├── Research / Review / Inspect mode
├── Run Profile
├── Pause / Stop / Continue
└── Case stage and human handoff

Main Workspace
├── Research Run Thread
│   ├── accepted plan
│   ├── structured agent events
│   ├── tool/source/numeric events
│   └── human interventions
├── Artifact Canvas
│   ├── plan
│   ├── live workpaper
│   ├── evidence matrix
│   └── report
└── Context Inspector (on demand)
    ├── source detail
    ├── exact numbers
    ├── comments
    └── lineage/debug in Inspect mode only
```

### 5.3 现有路由到新界面的映射

| 现有路由 | 新界面归属 | 处理方式 |
| --- | --- | --- |
| `/tasks` | Task Center | 保留路由，重做主对象与信息密度 |
| `/cases/new` | Case Composer | 保留；在创建前选择 Run Profile 预设 |
| `/cases/:id/overview` | Case Workspace / Ready or Running | 作为 Case 默认入口 |
| `/decision-surface` | Artifact Canvas 的 Plan/Questions 视图 | 不再作为一级标签 |
| `/evidence` | Evidence Matrix | 保留深链接，从主线打开 |
| `/numbers` | Workpaper 的 Numeric sheet 或 Inspector | 不再作为一级主路由 |
| `/workpaper` | Workpaper | 保留深链接 |
| `/deliverable` | Report | 重命名产品文案，不以系统对象命名 |
| `/activity` | Inspect | 从产品默认导航移除 |
| `/baseline` | Senior Review task | 不再展示为问卷式独立产品页 |

## 6. Run Profile

Run Profile 是“本次研究如何运行”的可读合同，不是开发者配置表。命令栏只显示摘要，例如：

`Research Pro · 3 data sources · P36 graph · Lead + 4 specialists · 45 min / US$12 cap`

展开后分五组：

1. **模型策略**：默认模型、长文档模型、数字核验模型、失败回退；普通用户选择预设，Inspect 模式才显示具体版本。
2. **数据与工具**：official filings、internal RAG、SQL、graph、web policy；每项显示权限与 freshness。
3. **Skills**：P36 demand validation、revenue bridge、margin capture、counterevidence、writer no-source。
4. **知识图谱**：选择图谱版本和研究主题；默认自动绑定，不要求用户搭图。
5. **Agent 编排**：Lead、Evidence、Numeric、Domain、Counterevidence、Writer；以模板选择，不在主界面画流程图。

修改 Profile 会生成新 run candidate，不追溯修改已完成 artifact。

## 7. Case 四种状态

### 7.1 运行前 `READY`

主对象是待接受的 Research Plan。用户看见研究目标、12 个 cells、优先级、数据范围、预算和预计时长。主操作是“开始研究”；次操作是调整范围或 Run Profile。

### 7.2 运行中 `RUNNING`

左侧为结构化 Research Run Thread，右侧为实时形成的 Workpaper。当前 active agent、正在调用的数据源、已接受证据、数字核验、缺口和预计剩余时间持续更新。主操作是暂停或提出方向修正，不要求用户监控每次调用。

### 7.3 等待人工 `AWAITING_HUMAN`

主对象切换为 exact artifact under review。系统明确说明为何需要人：证据冲突、判断边界、数字不一致、writer usefulness 或发布决定。Review 不采用空白问卷，而是在原判断旁直接操作。

### 7.4 运行完成 `COMPLETED`

主对象是 decision-ready report。运行日志降为背景信息。报告必须有执行摘要、价值捕获地图、关键数字、反证、情景、What Would Change 与 citation map。

## 8. 页面详设与原型图

以下图片由 `docs/product/prototypes/fin_0_1_workbench_next/` 的独立原型渲染，不连接现有后端。

### 8.1 Task Center

图片：`design_assets/fin_0_1_workbench_next/01_task_center.png`

- 主对象：当前用户负责或待复核的 Case。
- 顶部先显示“继续当前研究”，避免用户每次重新寻找任务。
- 中央表格按研究阶段、进度、证据、缺口、下一步扫描。
- 右侧 Research Brief 只显示所选 Case 的判断、活跃 cells 与阻断。
- 点击 Case 进入其当前状态，不先进入对象概览页。

### 8.2 Case Ready

图片：`02_case_ready.png`

- 主对象：待接受的三阶段研究计划。
- 左侧 Thread 说明系统如何把问题拆成计划，而不是展示技术日志。
- 右侧 Canvas 展示 scope、cells、优先级、来源范围和成功条件。
- “Run Profile”打开抽屉；“开始研究”触发 `READY -> RUNNING`。

### 8.3 Case Running

图片：`03_case_running.png`

- 主对象：正在形成的研究结果。
- Thread 使用事件类型区分 plan、agent、source、numeric、gap 与 handoff。
- Canvas 顶部显示当前判断，正文随已验证内容增量更新。
- 运行指标只保留时间、完成 cells、证据与阻断；调用次数放 Inspect。
- “暂停”保持当前 checkpoint；“停止”要求 typed reason 并保持已形成 artifact。

### 8.4 Evidence Matrix

图片：`04_evidence_matrix.png`

- 主对象：claim/cell 到 evidence、number、counterevidence、state 和 next action 的矩阵。
- 不按来源堆卡片，而按判断问题组织证据。
- 选择一行后，右侧 Inspector 显示原文片段、出处、日期、适用边界和 inclusion decision。
- 用户可接受、降级、排除或标记 gap；这些操作改变 claim maturity，不直接改最终报告。

### 8.5 Workpaper

图片：`05_workpaper.png`

- 主对象：可编辑且有结构的 research workpaper。
- 正文按 thesis、mechanism、exact numbers、counterevidence、open gaps、What Would Change 组织。
- 引用以 inline marker 进入 Inspector，不把 evidence lineage 全量铺在正文。
- 数字可以打开 calculation sheet；编辑形成新 workpaper version。

### 8.6 Awaiting Senior Review

图片：`06_awaiting_review.png`

- 主对象：一个 exact workpaper/report version。
- Review action 与具体判断共址：接受、编辑接受、降级、退回 repair、保持 unresolved。
- Senior 可以看到证据、反证和数字，不需要在另一页复制内容到空白输入框。
- 所有动作形成 exact outcome，但主界面只显示可读原因；digest 在 Inspect 可查。

### 8.7 Report Complete

图片：`07_report_complete.png`

- 主对象：支持决策的研究叙事，不是十个 cell 的拼接。
- 首屏包含 thesis、confidence、关键数字、who captures value 和主要边界。
- 后续结构为价值链地图、情景、催化剂、风险、What Would Change 与来源索引。
- “分享/导出”在 FIN 0.1 只生成内部 artifact，不表达 production publish。

### 8.8 Inspect Mode

图片：`08_inspect_mode.png`

- 主对象：本次 run 的可审计执行记录。
- 展示 agent handoff、工具调用、模型策略、预算、checkpoint、错误、package/version identity。
- 只有这里显示 Case ID、digest、调用与写入计数。
- Inspect 不改变研究内容；任何 replay 或 authority 变化都不在该界面自动授权。

## 9. 原地迁移与新方案

### 9.1 现状判断

可以复用：

- FastAPI routes 与 typed frontend API clients。
- Case、DecisionSurface、Evidence、Numeric、Workpaper、Deliverable、Review、Trace 的 feature modules。
- 现有 fixture/shadow 数据合同和中文内容适配。

不建议继续复用：

- 当前 `AppShell` 的对象页式路由组合。
- 持久任务队列 + Case tabs + 右抽屉同时常驻的四栏结构。
- 已累计约 3,000 行、围绕旧壳层不断追加的页面 CSS。

### 9.2 方案 A：同一应用内新增 CaseWorkspaceNext（推荐）

- 在现有 React/Vite 应用内增加新壳层与 feature flag。
- 复用 API client、query state 和业务组件逻辑，重新组合为 Thread + Canvas + Inspector。
- 按 Case 状态逐步迁移；旧路由保留 deep-link adapter，完成后删除旧 shell。
- 优点：单一产品、单一 API、可逐步 dogfood、回滚简单。
- 代价：需要主动拆分现有 feature view 与 shell，不能只改 CSS。

### 9.3 方案 B：新建独立 Workbench 前端

- 新建单独 frontend package，通过相同 API/OpenAPI 访问后端。
- 优点：信息架构干净，不受旧 CSS 和路由影响。
- 风险：在迁移完成前形成双前端、双测试和行为漂移；旧新界面都需要维护。
- 适用条件：用户明确接受一次性切换，并允许旧前端停止功能开发。

### 9.4 当前建议

先用本独立原型冻结视觉与交互。用户确认后选择 A 或 B。没有确认前不改现有运行前端。默认工程建议是方案 A，但执行方式是“新壳层替换”，不是在旧页面上继续增补卡片和 CSS。

## 10. 设计验收标准

1. 新用户在 30 秒内能说清当前 Case 的目标、阶段、关键判断和下一步。
2. 从任务中心到运行中 Case 不超过一次点击。
3. 运行过程可解释，但默认界面没有 raw chain-of-thought、digest 或 fixture 字段。
4. 任意关键判断可在两次点击内打开其证据、数字和反证。
5. Workpaper 与 Report 的主次结构清晰，不以 cell 列表代替叙事。
6. Senior Review 在原判断上下文完成，不依赖空白问卷。
7. 四种 Case 状态的主操作唯一且不会互相矛盾。
8. Inspect 模式能完整承接现有审计和调试需求，产品模式不丢失可审计性。
9. 1440x900、1600x1000 与 1920x1080 无重叠、截断或动态布局跳动。
10. 中文为默认产品语言，英文仅用于行业专有名词或用户切换。

## 11. 用户需要作出的设计决策

本轮效果图通过后，只需要确认三件事：

1. 是否接受“Task Center + Case Workspace”作为两层主信息架构。
2. 是否接受 Case 内“Research Run Thread + Artifact Canvas + on-demand Inspector”的主布局。
3. 选择方案 A（同应用新壳层迁移）或方案 B（独立新前端）。

Evidence、Workpaper、Report 和 Senior Review 的字段细节在上述三项确认后再逐页冻结，不在本轮继续扩张。
