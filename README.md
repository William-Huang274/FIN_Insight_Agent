# FinSight-Agent

[English version](README.en.md)

FinSight-Agent 是一个面向投研流程的证据约束型金融研究 Agent。它的目标不是只支持某几类固定材料，而是把开放式研究问题转成一条可执行、可检查、可扩展的分析流程：先界定研究范围，再检索相关材料，抽取和校验关键数值，组织判断框架，调用大模型生成投研备忘录，最后用规则校验答案中的来源边界和数值引用。

当前版本支持美股 SEC 披露文件、公司业绩新闻稿和离线市场快照作为投研备忘录的三类信息来源：10-K 和最新 10-Q 用来支撑财务事实和业务描述，8-K 业绩新闻稿用来补充管理层解释和经营叙事，市场快照用来提供非实时的价格、收益率、事件窗口和估值语境。后续版本更新将支持更多数据源，如行业新闻、电话会纪要、分析师研报等（新增信息来源会进入同一套证据分层、口径管理和校验机制）。

最终输出不只是“看起来合理”的用户问题回答/分析报告，而是带有来源类型、期间口径、披露文件边界和市场快照日期的可追溯投研备忘录。

## 功能概览

FinSight-Agent 适合处理需要同时采纳、比对财务报告、管理层解释、市场反应等多信息源的投研问题。同时Agent自带上下文管理，支持多轮对话。

典型任务包括：

- 比较 AI 相关公司在收入增长、数据中心业务、资本开支、剩余履约义务、云业务和半导体业务上的基本面变化。
- 结合年报、最新季报、业绩新闻稿和市场快照，分析公司基本面、管理层解释、市场反应和估值分歧。
- 追问某个指标变化背后的 SEC 证据、管理层表述和市场快照信号。
- 在一次会话中先生成行业研究备忘录，再继续追问某家公司、某个指标或某段证据。
- 检查模型回答中的结论分别来自审计年报、未审计季报、公司管理层口径还是市场快照。

当前输出定位是带证据边界的研究备忘录和可反驳判断框架，不是实时行情终端、自动交易系统或直接投资建议生成器。

## 从问题到投研备忘录

```text
用户问题
  -> 受约束的用户意图解析
  -> 多源证据检索与数值抽取
  -> 证据覆盖和分析框架
  -> API 大模型生成研究备忘录
  -> 规则校验和可追溯呈现
  -> 可继续追问的会话状态
```

大模型负责理解问题、综合证据和组织表达；工具链负责检索、取数、口径管理、证据覆盖、后置校验和会话状态恢复。这个职责划分是项目的核心：让模型做解释和取舍，让可测试的程序处理证据和约束。

研究任务解析默认可以由 API 大模型完成：设置 `QUERY_PLANNER=llm` 后，系统会通过统一的模型调用层调用外部模型，例如 DeepSeek 或其他 OpenAI-compatible 接口。模型输出的不是自由文本，而是固定 schema 的查询计划；计划会继续经过字段长度、公司范围、财年范围、披露类型、证据层级和市场快照约束校验。启发式 planner 只用于无 API key 的本地结构检查，不参与完整链路质量评测。

## Agent 工作机制

FinSight-Agent 的运行时不是一次接口调用，而是一组可以检查中间结果的 Agent 步骤。表中的中文名称面向读者说明职责，括号中的英文是代码和评测里沿用的内部模块名。

| 组件 | 职责 |
| --- | --- |
| 研究任务解析（Query Contract Planner） | 使用受 schema 约束的 API 大模型或本地评测解析器，将自由文本问题整理成公司范围、年份范围、披露文件类型、证据层级、指标族和分析意图 |
| 工具调用控制层（Tool-call Controller） | 在多轮会话中让 API 大模型选择高层工具；真实执行由工具执行层（Tool Harness）接管 |
| 证据检索 | 使用 BM25、ObjectBM25 和 BGE 重排找到披露文件文本、结构化数据、8-K 证据和市场快照 |
| 财务数值台账（Exact-Value Ledger） | 抽取可比财务值，保留公司代码、财年、披露文件类型、期间口径、单位和来源对象编号 |
| 证据覆盖检查 | 检查每个分析任务是否有足够证据，记录缺口和边界 |
| 分析框架生成（Judgment Plan） | 在生成答案前组织可验证的分析框架，避免模型自由发挥 |
| 大模型综合 | 调用 API 大模型接口，例如 DeepSeek 或 OpenAI-compatible 模型，在证据和分析框架约束下生成投研备忘录 |
| 规则校验 | 校验来源边界、数值引用、市场快照日期、结论支撑和禁止生成的断言 |
| 会话记忆 | 保存会话状态、当前答案、证据引用和后续追问所需上下文 |

这让系统能支持多轮追问、`/state`、`/context`、`/answer`、会话恢复和已保存证据检查，而不是每次都从一段新的提示词开始会话。

## Agent 编排

FinSight-Agent 的执行层分成模型控制器、工具执行层、图执行器和上下文管理四个边界：

- 模型控制器（Controller）由 API 大模型驱动，负责从用户追问中选择合适高层动作，例如启动研究、是否收缩公司范围、解释某条证据、检查覆盖缺口或恢复中断分析。多轮会话入口使用 OpenAI-compatible 工具/函数调用（tool/function call）；模型返回的是工具名和参数，而不是直接执行检索或写入状态。
- 工具执行层（Tool Harness）是模型和真实执行链路之间的边界。它接收高层工具调用，管理会话、来源策略、范围变更后的失效规则和产物引用，并决定哪些请求需要重跑有向无环链路（DAG），哪些只需要读取已有答案、覆盖矩阵或证据包。
- 图执行器（Graph runner）使用 LangGraph 做轻量状态编排：当前版本将主链路包装成可记录、可检查、可恢复的图运行，写出 `sec_agent_state.json`、阶段记录和产物引用。检索、台账、覆盖、生成和规则校验仍由现有确定性模块执行。
- 上下文管理器（ContextManager）保存当前会话、当前答案、短期追问上下文和长期产物线索，让后续问题可以复用上一轮证据，而不是重新开始一次无关查询。

需要区分两类入口：`ask-full-source-api` 主要是固定 DAG 编排，研究任务解析和答案综合会调用 API 大模型；`session-full-source-api` 才启用工具调用控制层。也就是说，模型在多轮会话中负责选择下一步动作，Python harness 负责安全执行、状态更新和校验。

这也是它和“单纯大模型 API 调用脚本”的主要区别：模型不能直接越过工具链读私有文件或自称完成校验；每次回答都要落到可检查的查询计划、证据对象、数值台账、校验结果和会话状态上。

## 示例：一次 AI 公司横向比较如何经过各层

用户可以提出这样的问题：

```text
结合 10-K、最新 10-Q、8-K 业绩新闻稿和最近三个月市场快照，
比较 NVDA、AMD、MSFT、AMZN、GOOGL 的 AI 基本面、管理层解释、
市场反应和估值分歧。
```

系统不会直接把这个问题丢给模型生成答案，而是按以下步骤处理：

1. 研究任务解析根据用户问题识别出公司范围、年份范围、披露文件类型和分析意图：这是一个多公司横向比较问题，需要财务指标、管理层解释和市场反应三类证据。
2. 在多轮会话入口中，API 大模型先通过工具/函数调用选择高层工具，例如 `start_memo_analysis` 或 `revise_memo_scope`；工具执行层（Tool Harness）接收工具名和参数后，才启动真实检索、取数和状态更新。单轮入口则直接执行同一条固定 DAG。
3. 检索工具分别找到 10-K / 10-Q 中的业务和财务段落、结构化财务数据、8-K 业绩新闻稿片段，以及对应公司的市场快照记录。
4. 财务数值台账把可比数值拆出来，例如数据中心收入、云收入、资本开支或相关业务收入，并保留年度、季度、年初至今、过去十二个月等期间口径，避免把不同口径放在一起比较。
5. 证据覆盖检查确认每个判断是否有支撑：如果某家公司没有单独披露 AI 收入，系统会把它记录为证据缺口，而不是让模型补出一个看似完整的数字。
6. 分析框架把答案组织成基本面变化、管理层解释、市场反应、估值语境、分歧和风险几个部分。
7. 大模型只在这些证据和分析框架内写研究备忘录；它可以对证据做取舍和解释，但不能绕开证据边界。
8. 规则校验门控检查答案是否混用了 10-K、10-Q、8-K 和市场快照的权重，是否遗漏市场快照日期，是否把管理层口径写成审计财务事实。
9. 会话记忆保存本轮问题、当前公司范围、答案和证据引用。用户继续问“只展开 NVDA 和 AMD 的差异”时，系统可以复用上一轮的证据状态，而不是重新开始一次无关查询。

这个例子展示了项目为什么要把检索、取数、证据覆盖、分析框架、模型生成和校验拆开：投研问题不是单纯的文本生成任务，而是一个需要证据边界、财务口径和多轮上下文共同约束的工作流。

## 证据模型

投研分析最容易出问题的地方不是“模型不会写”，而是证据来源和口径混在一起。FinSight-Agent 把不同来源拆开处理，并在答案里保留边界。

| 证据层级 | 支持的分析 | 使用边界 |
| --- | --- | --- |
| `primary_sec_filing` | 10-K / 10-Q 中的财务事实、业务描述、风险和管理层讨论分析 | 年报与季报的审计属性不同；季度、年初至今、过去十二个月、全年口径不得混用 |
| `company_authored_unaudited_sec_filing` | 8-K 业绩新闻稿中的管理层解释、业务动量、指引和经营叙事 | 公司发布口径，不能替代 10-K / 10-Q 的结构化财务值 |
| `market_snapshot` | 近期、非实时市场表现、相对收益、事件窗口和估值语境 | 必须携带 `snapshot_id` 和 `as_of_date`，不能当作实时价格 |

财务数值台账用来把财务值从长文本和结构化数据中拆出来，统一记录期间、单位和来源。这样生成阶段引用的是已经组织好的数据，而不是临时从大段文本中猜数。

## 系统结构

```text
src/
  connectors/      SEC 连接器和披露文件清单
  ingestion/       SEC / 8-K 解析器、章节切分器
  retrieval/       BM25、向量检索、混合检索、ObjectBM25 检索器
  evidence/        证据对象、结构化数据和文本证据
  sec_agent/       查询计划、工具编排、上下文管理、规则校验、市场快照

scripts/
  cloud/           交互式 Agent / 会话命令行入口
  market/          市场快照下载、标准化、分析视图和证据包
  evaluate_*.py    规划器、上下文、发布检查、耗时分析等评测脚本
  build_*.py       清单、切分片段、台账、索引、结构化数据构建脚本

tests/
  证据来源策略、10-Q / 8-K 合同、市场快照、上下文、P0 可观测性
```

主要链路模块：

- `src/sec_agent/query_contract.py`：将开放问题约束成可执行查询计划。
- `src/sec_agent/tool_harness.py`：组织检索、台账、覆盖检查、分析框架、生成和规则校验。
- `src/sec_agent/context_manager.py`：管理多轮会话、当前分析范围、证据引用和长期记忆线索。
- `src/sec_agent/market_snapshot.py`：处理市场快照证据、事件窗口和估值语境。
- `scripts/cloud/sec_agent_interactive.sh`：交互式演示和会话入口。
- `scripts/evaluate_sec_agent_resume_closeout_readiness.py`：发布前结构性检查。

## 环境配置

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

大规模 SEC 下载需要设置 SEC User-Agent 联系信息。模型调用、数据供应商结果和私有索引通过环境变量和 Git 忽略目录管理。

不要提交 `.env`、API key、数据供应商令牌、私有披露文件、生成索引或运行输出。

完整数据模式需要准备私有 SEC 数据、数据供应商产物和索引。主模型综合生成通过接口调用完成；BGE 可用 CUDA 加速，也可以在小规模演示中使用 CPU 或预计算索引。

```bash
export LLM_BACKEND=deepseek
export MODEL_NAME=deepseek-v4-pro
export API_KEY_ENV=DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY="<set-in-shell-only>"
```

接入其他 OpenAI-compatible 模型时，只需要替换模型路由参数：

```bash
export LLM_BACKEND=openai_compatible
export BASE_URL="<provider-base-url>"
export MODEL_NAME="<model-name>"
export API_KEY_ENV=PROVIDER_API_KEY
export PROVIDER_API_KEY="<set-in-shell-only>"
```

## 演示

完整数据环境中的单轮演示已经封装成短入口。默认数据范围和路径来自脚本内置的全信息源配置；如果要接入自己的数据源，可以把 `configs/sec_agent_full_source_demo.env.example` 复制到被 Git 忽略的 `.env`，修改里面的数据清单、索引和市场快照路径，然后用 `SEC_AGENT_PROFILE_ENV=.env` 加载。

单轮演示：

```bash
bash scripts/cloud/sec_agent_interactive.sh ask-full-source-api \
"结合 SEC 10-K、最新 10-Q、8-K 业绩新闻稿和最近三个月市场快照，比较 NVDA、AMD、MSFT、AMZN、GOOGL 的 AI 基本面、管理层解释、市场反应和估值分歧。"
```

多轮会话演示：

```bash
bash scripts/cloud/sec_agent_interactive.sh session-full-source-api
```

会话内常用命令：

```text
/state
/context
/answer
/exit
```

更完整的演示命令和环境变量说明见：

- [中文演示入口](docs/demo/sec_agent_demo_entrypoints_v1.zh-CN.md)
- [英文演示入口](docs/demo/sec_agent_demo_entrypoints_v1.md)

用自己的 SEC / 8-K / 市场快照数据跑完整链路，建议先看：

- [中文自有数据快速接入](docs/deployment/local_custom_data_quickstart.zh-CN.md)

## 评测

公开仓库可以运行不依赖私有数据的结构性检查：

```powershell
python scripts/evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600
python -m pytest tests/test_resume_closeout_readiness.py tests/test_sec_agent_context_source_policy.py tests/test_market_snapshot_fixture.py
```

完整数据环境中的发布前检查还包括：

- 真实 API 大模型研究任务解析评测
- 全信息源双轮会话冒烟测试
- 上下文回放和恢复评测
- 市场快照主链路冒烟测试
- 阶段级耗时分析
- 已保存运行结果的发布检查聚合

## 版本范围与可复现边界

这一版用一组可复现的私有数据产物演示完整链路：30 家科技 / AI / 云 / 半导体相关样本公司（full30），FY2023-FY2025 10-K，以及当前数据产物集合中最新可用的 FY2026 10-Q / 8-K。市场快照是离线快照，答案会展示 `as_of_date`，不会把它包装成实时行情。

公开仓库不包含 SEC 原文、数据供应商结果、索引或 API key。读者可以使用自己的数据生成同类数据产物，然后通过 `SEC_AGENT_PROFILE_ENV` 指向本地配置文件。数据清单没有包含的公司、财务期间或市场字段，会在覆盖检查中体现为缺口，而不是在答案里补写成已覆盖。

这一版适合展示证据约束、全链路可观测、多轮会话和恢复能力；还不是多租户生产服务。JSON 文件会话存储适合演示和单进程评测，多用户部署应替换为数据库、Redis 或带文件锁的状态存储。市场快照数据源能力表也可以继续扩展，用来区分只提供价格的数据源和支持估值字段的数据源。

## 文档入口

- [中文演示入口](docs/demo/sec_agent_demo_entrypoints_v1.zh-CN.md)
- [中文自有数据快速接入](docs/deployment/local_custom_data_quickstart.zh-CN.md)
- [模型运行记录索引](reports/model_runs/model_run_index.md)
