# FinSight 产品定位草案：ToB / ToC 分岔与 AI Analyst Workbench

日期：2026-06-28

状态：产品草案。本文记录近期关于产品定位、ToB / ToC 分岔、底部工作替代路径和 B 端功能规划的讨论。它是产品经理向文档，不定义具体技术实现；技术实现需另行拆成技术需求单、架构文档和交付记录。

## 核心判断

FinSight 不应定位为“全能投研专家”或“通用金融 ChatGPT”。更自洽的定位是：

```text
Evidence-backed Financial Research Workbench
可审计的金融研究工作台 / AI junior analyst layer
```

产品短期不直接替代 PM、基金经理、投行 VP、咨询 manager、审计签字人等责任岗位，而是先替代底部高频、重复、可流程化、可审计的工作：

- 找资料；
- 抽表；
- 对数；
- 查引用；
- 生成研究底稿；
- 做 first draft；
- 做公告/财报/事件监控；
- 生成 evidence pack、gap ledger、memo draft、deck outline。

目标是让传统 `1 个 senior + 5 个 junior` 的覆盖模式，逐步变成：

```text
1 个 senior / manager
+ 1-2 个 AI-native junior
+ FinSight evidence graph / agent workflow / audit system
```

长期如果模型、数据、合规和 workflow 能力继续提升，再逐步向 AI-managed research pod 演进。但当前产品承诺应集中在可审计提效和低阶工作替代，不应承诺完全替代 senior judgment。

## ToB / ToC 分岔

### ToB: AI Analyst Workflow Platform

B 端用户更重视流程规范、可审计、可复盘、权限、成本控制和人力替代。核心价值不是“炫酷智能”，而是：

```text
用可审计 AI 工作流替代低阶重复劳动，
提升研究/咨询/审计/投顾团队产能，
并保留复核、权限和责任链。
```

典型用户：

- 券商研究团队；
- 买方投研团队；
- 投顾 / 财富管理；
- 咨询公司；
- 会计师事务所；
- 企业战略 / IR / 投资部门；
- PE/VC/并购/债券尽调团队。

B 端优先功能：

| 功能 | 价值 |
| --- | --- |
| Research Task Workflow | senior 提目标，系统拆任务、派 agent、生成证据包和 memo |
| Evidence Package / Source Audit | 每条结论可追溯到数据源、parser、citation、authority boundary |
| Human Review / Approval | manager / senior review、修改、批准，保留责任链 |
| Watchlist / Portfolio Monitoring | 持续跟踪 thesis driver、公告、资金面、政策、产品、客户部署 |
| Data Room / Document Intelligence | 解析上传 PDF、Excel、Word、会议纪要、招股书、合同、行业报告 |
| Memo / Deck / Report Output | 生成 IC memo、earnings review、client brief、deck outline |
| Internal Knowledge Base | 沉淀机构历史 thesis、投委会记录、修正、gold set、私有材料 |
| Trace / Eval / Feedback | run trace、node eval、failure/gold lifecycle、成本和质量 dashboard |
| Permission / Tenant / Cost Budget | 团队权限、模型/工具预算、私有数据边界、审计日志 |

B 端产品形态：

```text
SaaS 工作台
+ 私有数据/权限
+ agent workflow
+ evidence graph
+ audit/eval/trace
+ standardized deliverables
```

### ToC: AI Research Companion

C 端用户更重视易懂、可靠、便宜、快速和持续陪伴。核心价值是：

```text
让个人投资者获得接近机构研究流程的公开信息整理、
证据审计、风险提示和投资逻辑拆解能力。
```

典型用户：

- 专业散户；
- 独立研究员；
- 财经内容创作者；
- 学生和研究爱好者；
- 有投资需求但没有专业团队的个人。

C 端优先功能：

| 功能 | 价值 |
| --- | --- |
| Stock / Industry QA | 用可读语言解释公司、行业和事件 |
| Company Deep Card | 公司业务、财务、产品、资金面、风险的一页式卡片 |
| Bull / Bear Case | 帮用户理解支持和反对逻辑 |
| Earnings / News Explanation | 财报和新闻发生了什么，市场为什么反应 |
| Watchlist Alerts | 跟踪关注股票和主题 |
| Risk Education | 告诉用户哪些数据只是 proxy，哪些缺口不能判断 |
| Price-in / Valuation Context | 解释好消息是否已反映、估值是否极端 |

C 端必须有投资建议边界：

- 输出信息整理、风险提示、情景分析、证据解释。
- 不输出确定买卖指令。
- 不把低权重新闻、社媒、options、short interest 直接写成投资结论。

C 端产品形态：

```text
个人投研助手
+ 公开数据
+ 可读解释
+ watchlist
+ 风险教育
+ 低成本模型路由
```

## 共用底座

ToB 和 ToC 不应做两套底座。共用部分：

```text
Public Data Sources
Parser / Normalizer
Source Authority
Evidence Graph
ProductIntelligenceGraph
SecondaryMarketCapitalFeedback
Research Lead
ClaimCard / GapLedger
Eval / Trace
```

差异主要在产品 surface：

| 模块 | B 端 | C 端 |
| --- | --- | --- |
| 输出 | memo、deck、底稿、审计 trace | 可读解释、卡片、提醒 |
| 权限 | 团队、角色、审批、私有数据 | 个人账户、watchlist |
| 风控 | 合规审计、版本管理、责任链 | 投资建议边界、风险提示 |
| 数据 | 公开 + 私有 + 机构知识库 | 主要公开数据 |
| 成本 | seat / workflow / usage 可控 | 低成本、高缓存、轻量默认 |
| Agent | 多节点深链路，可人工复核 | 快速分层，默认 focused scan |
| 价值 | 降本增效、标准化流程 | 类机构研究能力 |

战略原则：

```text
B 端底座，C 端体验。
```

也就是后端、数据治理、trace、eval、权限、workflow 按 B 端标准建设；C 端可以从同一底座裁剪出轻量、可读、低成本的 Research Companion。

## 产品阶段

### Phase 1: AI Junior Analyst

替代资料收集、公告跟踪、表格抽取、证据整理、引用、初稿和 focused answer。

通过标准：

- 用户能把一个公司/行业问题交给系统，拿到可审计 evidence pack 和 memo draft。
- 每个关键结论有 citation、source boundary、gap 或 forbidden claim 检查。
- senior 可以 review，而不是从零查资料。

### Phase 2: AI Research Associate / Workflow Co-pilot

替代标准 earnings review、peer comp、watchlist monitoring、standard memo、IC prep 初稿。

通过标准：

- Research Lead 能持续监督 specialist；
- 维度证据能进入 thesis / counter-thesis；
- watchlist 能持续触发变化说明；
- 人工修改能沉淀进机构记忆和 eval。

### Phase 3: AI-managed Research Pod

系统按研究目标自动维护 coverage、监控事件、生成更新、提出 repair 和 follow-up。

通过标准：

- manager 主要管理问题定义、复核和客户/投资判断；
- agent 负责日常 coverage 和 evidence operations；
- 成本、质量和失败生命周期可审计。

### Phase 4: Human-led, AI-operated Professional Service Workflow

长期方向。人类保留客户关系、责任承担、策略判断和线下/线上真人交互，AI 负责大多数标准化分析流程。

当前不作为近期承诺。

## B 端核心工作流

```text
Senior / Manager 提出研究目标
 -> Research Lead 生成 Research Objective Contract
 -> Agent 自动查公开数据和内部文档
 -> 生成 EvidencePack / ClaimCard / GapLedger / GraphEdges
 -> LeadReview 判断是否需要 targeted repair
 -> 形成 JudgmentState / MemoLogicPlan
 -> Memo / Deck / Checklist 输出
 -> Human Review / Approval
 -> 进入机构知识库和 Eval / Gold / Failure lifecycle
```

## 产品与技术文档分工

产品文档维护：

- 产品定位；
- 用户分层；
- 业务场景；
- 用户流程；
- 功能范围；
- 交互和输出形态；
- 产品验收标准；
- 商业化假设；
- ToB / ToC packaging。

技术文档维护：

- runtime 架构；
- API / DB / queue / object store；
- data source adapter；
- parser / graph / eval contract；
- agent graph / prompt / tool permission；
- deployment；
- performance / cost / observability；
- implementation delivery checklist。

工作日志维护：

- 本轮改了什么；
- 为什么这么改；
- 跑了什么命令；
- 结果是什么；
- 剩余缺口是什么；
- 回滚或后续注意事项。

禁止混放：

- 产品文档不写具体脚本实现和 runtime 调试日志。
- 技术文档不直接替代产品定位和用户价值判断。
- 工作日志不作为长期 PRD 或架构 source of truth。

## 当前建议

1. 先把 B 端作为主线设计：因为它要求更高，能倒逼审计、权限、trace、eval、数据治理。
2. C 端作为体验层和增长入口：用同一底座裁剪出低成本、可读、风险边界清晰的 Research Companion。
3. 近期不要把产品叫“金融通用办公平台”，而是叫“金融研究工作台 / AI Analyst Workbench”。
4. 后续所有功能规划先进入 `docs/product/`；再拆技术需求单和交付文档。
