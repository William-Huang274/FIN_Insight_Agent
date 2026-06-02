# FinSight-Agent

[English version](README.en.md)

FinSight-Agent 是一个面向公开公司研究的可审计金融研究系统。它不是把几段材料丢给大模型写总结，而是把用户的金融问题拆成一串能检查、能复用、能追责的研究步骤：先判断问题类型和研究范围，再检索有边界的证据，整理数值台账和行业/关系上下文，交给不同角色的专家智能体形成可验证的结论卡，汇总成论证提纲，最后写成投研备忘录，并检查来源、数值和结论有没有越界。

这个项目不做实时行情终端，不做自动交易，也不生成个性化投资建议。它想解决的是另一件事：让金融研究回答既能利用大模型的理解和表达能力，又能保留证据边界、财务口径、工具调用记录和多轮上下文。

## 当前定位

FinSight-Agent 当前适合处理这类问题：

- 比较公司基本面、管理层解释、市场反应和风险边界。
- 围绕某家公司或某个指标做聚焦分析，例如利润率、资本开支、现金流、银行资产质量，或者能源/公用事业经营指标。
- 研究行业主题或经济传导链，例如 AI 基础设施、云厂商资本开支、数据中心用电需求、半导体供应链。
- 在多轮会话中缩小范围、追问某条证据、检查覆盖缺口，或者复用上一轮已经跑出的产物。
- 检查回答里的事实到底来自 SEC 披露、公司 8-K 业绩材料、离线市场快照，还是行业/关系假设。

公开仓库不包含私有 SEC 原文、市场数据、生成索引、运行产物或 API key。用户可以用自己的公开披露、市场快照和行业数据生成同类产物，再通过本项目的配置约定接入。

## 面向非金融场景的迁移性
FinSight-Agent 当前用美股上市公司研究作为高约束验证场景，但底层链路并不依赖金融领域本身。只要目标任务存在多源材料、口径边界、工具调用、多轮追问和结论校验需求，同一套流程可以迁移到企业知识库问答、行业研究、合同/合规文档分析、数据分析报告生成等场景。

## 为什么不是普通 RAG

普通 RAG 往往是“检索几段文本 -> 塞给模型 -> 生成答案”。FinSight-Agent 的重点是把金融研究里最容易出错的地方显式管起来：来源边界、数值口径、经济关系、多轮上下文和结论校验。

| 能力 | FinSight-Agent 的做法 |
| --- | --- |
| 问题理解 | 研究负责人先把用户问题整理成研究模式、公司范围、数据需求和智能体激活计划 |
| 工具调用 | 工具执行层通过 MCP 工具注册表调用受控工具，模型不能直接越权读数据 |
| 检索与重排 | SEC BM25、ObjectBM25、BGE 重排、8-K、市场快照、行业和关系数据分层进入上下文 |
| 数值证据 | 精确数值台账记录公司、期间、指标、单位和来源对象，而不是让模型从长文本里猜数 |
| 专家分析 | 专家智能体只看限定证据，输出可验证的结论卡，不自己检索、不扩大范围 |
| 投研主线 | 汇总器把结论卡整理成论证提纲，备忘录写作器只基于已验证提纲写作 |
| 多轮上下文 | 上下文管理器保存研究范围、当前答案、产物引用、覆盖情况和可复用证据 |
| 质量门控 | 校验器和规则门控检查来源边界、数值引用、未支持结论、权限和调用成本 |

## 当前数据源与边界

| 来源类型 | 支持的分析 | 边界 |
| --- | --- | --- |
| `primary_sec_filing` | 10-K / 10-Q 中的财务事实、业务描述、风险、MD&A | 年报、季报、QTD、YTD、TTM、全年口径不能混用 |
| `company_authored_unaudited_sec_filing` | 8-K 业绩公告中的管理层解释、业务动量、经营叙事 | 公司发布口径，不能替代 SEC 披露里的审计或未审计财务事实 |
| `market_snapshot` | 离线价格、收益率、事件窗口、估值语境 | 必须携带 `snapshot_id` 和 `as_of_date`，不是实时行情 |
| `industry_snapshot` | 行业主题、供需、监管、市场结构背景 | 支持研究假设和背景判断，不能覆盖公司披露事实 |
| `relationship_graph` | 经济关系、产业传导、潜在受益和风险暴露 | 主要支持研究范围和经济机制假设，不能写成已确认客户、供应商或合同事实 |

## 多智能体链路

```mermaid
flowchart LR
  A["用户问题"] --> B["研究负责人"]
  B --> C["公司范围与关系分析"]
  B --> D["证据执行器"]
  C --> D
  D --> E["覆盖检查与反思"]
  E --> F["角色化专家"]
  F --> G["判断汇总器"]
  G --> H["备忘录写作器"]
  H --> I["校验与修复"]
  I --> J["结果呈现与会话状态"]
```

核心原则：

- 研究负责人不直接检索，只负责理解问题、确定研究范围、列出证据需求，并决定哪些智能体该参与。
- 证据执行器负责真实工具调用，包括 SEC 检索、ObjectBM25、BGE 重排、市场/行业/关系查询和运行时数值台账。
- 专家智能体没有检索权限，只消费限定证据、数值台账、关系摘要和任务卡。
- 判断汇总器不新增事实，只把专家结论卡整理成可写作的论证提纲。
- 备忘录写作器不读取原始证据，只根据已验证的论证提纲写投研备忘录。
- 校验器是安全门，负责检查越界结论、缺少证据的断言和修复是否收敛，不负责增加分析深度。

## 智能体激活策略

FinSight-Agent 不会遇到任何问题都把所有专家全开。研究负责人会先判断问题类型，再决定哪些是主力智能体、哪些是辅助智能体、哪些只在条件满足时启动、哪些不该启动。

| 问题类型 | 主要启动 | 条件启动 | 通常不启动 |
| --- | --- | --- | --- |
| 精确查询 | 证据执行器、结果呈现 | 校验器 | 全量专家 |
| 单公司聚焦分析 | 基本面专家、风险专家 | 市场专家、行业专家 | 无关行业专家 |
| 标准投研备忘录 | 基本面专家、市场专家、风险专家 | 行业专家、关系分析 | 不相关专家 |
| 行业深度研究 | 关系分析、行业专家、基本面专家、风险专家 | 市场专家 | 只做查数的呈现流程 |
| 市场反应分析 | 市场专家、基本面专家 | 风险专家、关系分析 | 纯关系扩展 |
| 多轮追问 | 控制器、上下文管理器 | 根据研究范围是否变化决定 | 无意义全链路重跑 |
| 已保存运行检查 | 运行产物读取工具、结果呈现 | 覆盖检查 | 新检索、新备忘录 |

这个策略的目标是同时控制质量和成本：该启动的智能体必须启动，不相关的智能体不能浪费调用成本，也不能污染上下文。

## 多轮上下文

多轮能力不是把上一轮回答简单拼到提示词里，而是保存可以审计的状态：

- 会话状态：当前用户目标、研究范围、当前答案、来源策略和产物引用。
- 图运行状态：每个节点的输入、输出、状态、错误和可恢复点。
- 上下文证据行：检索后传给下游的限定证据。
- 数值台账行：精确数值和来源对象的绑定。
- 关系摘要：经济关系和产业传导假设。
- 专家结论卡：专家输出的可验证中间结论。
- 备忘录论证包：备忘录写作器的结构化输入。

当用户在后续轮次修改公司、年份、来源类型或输出形式时，工具执行层会判断哪些产物可以复用，哪些必须失效重跑。例如用户说“只保留 NVDA”，系统应该复用已有的 NVDA 证据，并失效 AMD 相关的备忘录段落，而不是从头跑一次无关研究。

## 快速开始

安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

公开仓库可以直接跑结构检查，不需要 API key 或私有数据：

```powershell
python scripts/eval_context/evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600
python -m pytest tests/test_resume_closeout_readiness.py tests/test_sec_agent_context_source_policy.py tests/test_market_snapshot_fixture.py
```

更快的本地合同检查：

```powershell
python scripts/eval_context/evaluate_sec_agent_resume_closeout_readiness.py `
  --skip-main-chain-case-suite `
  --skip-context-load-smoke `
  --skip-latency-profile
```

## 完整链路演示

完整链路需要本地已有数据产物、检索索引和 API 模型路由。API key 只通过命令行环境变量注入，不写入仓库文件。

```bash
export LLM_BACKEND=deepseek
export MODEL_NAME=deepseek-v4-pro
export API_KEY_ENV=DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY="<set-in-shell-only>"
```

复制配置模板到被 Git 忽略的 `.env`，再替换成本地数据产物路径：

```bash
cp configs/sec_agent_full_source_demo.env.example .env
```

单轮完整数据演示：

```bash
SEC_AGENT_PROFILE_ENV=.env bash scripts/cloud/sec_agent_interactive.sh ask-full-source-api \
"结合 SEC 10-K、最新 10-Q、8-K 业绩新闻稿和最近三个月市场快照，比较 NVDA、AMD、MSFT、AMZN、GOOGL 的 AI 基本面、管理层解释、市场反应和估值分歧。"
```

多轮会话演示：

```bash
SEC_AGENT_PROFILE_ENV=.env bash scripts/cloud/sec_agent_interactive.sh session-full-source-api
```

会话内常用命令：

```text
/state
/context
/answer
/exit
```

## Workbench

Workbench 是本地产品化体验入口。它现在不只是启动问答链路，也可以把本地数据准备和运行检查集中到网页端：导入运行配置、生成和校验数据包、预览受控的数据构建命令、后台执行 SEC / 8-K / 市场 / 行业数据处理步骤、在成功后把新产物路径回填到数据包，再发起单轮或多轮任务、查看运行产物、检查节点台账，并运行冒烟评测。

```powershell
.\scripts\workbench\run_workbench.ps1
```

如果只需要启动后端，也可以运行：

```powershell
python scripts/workbench/start_workbench.py
```

详细说明见 [Workbench 快速开始](docs/workbench/workbench_quickstart.zh-CN.md)。

## 仓库结构

```text
src/
  connectors/      SEC 连接器和披露文件清单
  ingestion/       SEC / 8-K 解析器、章节切分器
  retrieval/       BM25、ObjectBM25、向量检索和混合检索
  evidence/        证据对象、结构化数据和文本证据
  sec_agent/       查询合同、工具执行层、上下文、门控、市场快照、Workbench

scripts/
  README.md        当前主线脚本入口和保留范围
  cloud/           交互式智能体、会话 CLI、图运行器
  data_sec/        SEC / 8-K 下载、清单、切分和来源缺口处理
  data_retrieval/  证据对象、结构化对象、BM25、ObjectBM25 和数值台账
  eval_context/    上下文、工具控制器、延迟和发布就绪检查
  eval_multi_agent/ 多智能体分层门控和全链路评测
  eval_sec_benchmark/ SEC benchmark 运行时支撑和后置门控
  eval_query_planner/ 自由问题解析评测
  market/          市场快照下载、标准化、分析视图和证据包
  mcp/             MCP 工具合同、服务端和冒烟检查
  workbench/       本地 Workbench 启动和环境辅助脚本
  archive/         带版本号的历史脚本归档

docs/
  README.md        文档地图和读者路径
  deployment/      自有数据接入和部署说明
  demo/            CLI 演示入口
  architecture/    架构文档入口
  eval/            投研质量体系和分层门控
  workbench/       Workbench 使用说明
  worklog/         历史实现记录和交接文档

tests/
  来源策略、10-Q / 8-K 合同、市场快照、上下文、多智能体门控、Workbench
```

## 质量评价与门控

本项目不只看最终备忘录是否流畅，还检查每个智能体和节点是否正确理解任务、合理启动、真实调用工具、消费合法证据、输出可验证中间结果，并控制调用成本和工具预算。

当前质量体系覆盖：

- 问题理解与任务授权。
- 证据充分性与来源边界。
- 财务与指标分析。
- 经济关系与产业传导。
- 投资论点、风险反证和观察项。
- 输出结构与用户可用性。
- 过程效率、权限安全和审计。

分层门控遵循“单层通过，再跑全链路”的原则。S1-S8 覆盖研究负责人、公司范围与关系分析、证据执行器、覆盖检查与反思、专家智能体、判断汇总器、备忘录写作器和校验器；全链路和多轮评测只在关键层通过后运行。

主要入口：

- [投研质量评价体系](docs/eval/fin_agent_investment_research_quality_framework_v0_1.md)
- [分层质量门控执行文档](docs/eval/fin_agent_layered_quality_execution_plan_v0_1.md)
- [全链路 / 多轮评测计划](docs/eval/fin_agent_full_chain_multiturn_eval_plan_v0_1.md)

## 文档地图

- [文档地图](docs/README.md)
- [架构文档入口](docs/architecture/README.md)
- [中文演示入口](docs/demo/sec_agent_demo_entrypoints_v1.zh-CN.md)
- [中文自有数据快速接入](docs/deployment/local_custom_data_quickstart.zh-CN.md)
- [Workbench 快速开始](docs/workbench/workbench_quickstart.zh-CN.md)
- [脚本发布面](scripts/README.md)
- [模型运行记录索引](reports/model_runs/model_run_index.md)

## 当前边界

- 公开仓库不包含私有数据、生成索引、运行输出、模型缓存或 API key。
- 市场快照是离线数据，不是实时行情。
- 行业和关系数据支持研究范围、经济机制和假设，不等同于已确认商业合同。
- 当前会话存储适合演示、开发和单进程评测；多用户服务需要数据库、Redis 或带锁状态存储。
- 校验器能阻止越界和缺证结论，但高质量投研深度仍取决于上游证据覆盖、专家结论卡密度和备忘录写作器输入质量。
