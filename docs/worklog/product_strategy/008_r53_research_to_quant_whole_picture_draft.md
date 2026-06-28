# R53 Research-to-Quant Whole Picture Draft

日期：2026-06-28

## Prompt

用户认可 Research-to-Quant Lab 的定义：它应是把研究证据图谱转化为可检验量化假设的内部验证系统，不做真实资金操盘，也不对外提供交易建议。用户要求先把 R53 whole picture 讨论并落成草稿，再拆更细的版本迭代；同时追问回测 / 因子验证结果是否可以和内部经验沉淀、上下文库和图谱联动，构建标准化、方便查阅、可审计、可被 agent 检索的数据库。

## Decision

新增 R53 技术草案，先冻结公开数据前提下的全景能力和对象模型，不进入 v0.1 实现拆分。

核心判断：

- R53 不是 backtest runner，而是 `Evidence / ThesisDriver / GraphEdge -> FactorHypothesis -> PITDataset -> validation -> FactorCard -> ResearchExperienceStore` 的内部研究验证链路。
- LLM 只能提炼和解释，不得绕过 point-in-time、leakage、human approval 或 deterministic backtest。
- 反哺研究图谱和内部经验库应该是 R53 的核心输出：失败因子、有效因子、适用 regime、数据缺口、leakage blocked、过拟合和 human review 都应进入可检索、可审计、可失效的经验层。

## Work Completed

- 新增 `docs/architecture/agent_graph_vnext/28_r53_research_to_quant_lab_technical_plan.zh-CN.md`。
- 更新 `docs/architecture/agent_graph_vnext/README.zh-CN.md`，加入 28 文档索引。
- 更新 `docs/worklog/00_internal_master_checklist.md`，记录 R53 draft 状态但保持未完成。
- 更新 `docs/worklog/README.md`，加入本工作日志索引。
- 2026-06-28 update：把“哪些信号域归 R53，哪些应放到 R54 / R58 / R60”和“Research-to-Quant 对象模型如何设计才不推翻”从开放问题改成正式设计内容。

## Result And Evidence

R53 草稿已覆盖：

- Research-to-Quant 定位和 whole-picture 主链路；
- 公开数据下的信号全景：价格、财务、估值、产品技术、客户供应链、资本动作、宏观跨资产、衍生品、政策事件、文本披露、图谱结构；
- R53 / R54 / R58 / R60 分工：R53 拥有 quant object lifecycle、PIT / leakage / validation / FactorCard，R54 负责二级市场和资本反馈数据，R58 负责 SQL / RAG / feature materialization，R60 负责 eval / observability / release gate；
- 数据准备与清洗主线：Entity/Security Master、Market Data、Fundamental PIT、Feature Store、Label Store、Leakage/Cost/Liquidity Gate；
- 方法体系：传统截面因子、事件研究、因子评价、组合回测、ML 排序/预测、时间序列/regime、组合优化、paper trading；
- Agent / Human 分工；
- ResearchExperienceStore / FactorLifecycleLedger / QuantValidationMemory / SignalReliabilityProfile；
- Stable Object Model：`SignalObservation -> FactorHypothesisCandidate -> HumanApprovalDecision -> FactorHypothesis -> FeatureSpec / LabelSpec / UniverseSpec -> DatasetBuildPlan -> PITDatasetSnapshot -> LeakageGuardResult -> ValidationResult -> FactorCard -> ResearchExperienceRecord`；
- 和 Workpaper、Research Lead、ProductIntelligenceGraph、Watchlist、Deliverable Studio、Eval Runtime、ContextEngine 的联动。

## Verification

- 本轮是 docs-only，未运行 runtime、agent graph、parser、DB、frontend 或 backtest。
- 已运行 `git diff --check`。

## Follow-up

后续继续讨论后再拆：

1. R53 v0.1 是否只做 factor analysis + event study，还是保留简单 portfolio backtest。
2. 是否先只支持日频美股，非美 / A 股放到 v0.2。
3. FactorCard 第一版只生成 Markdown / JSON artifact，还是进入 Workbench UI。
4. ResearchExperienceStore 第一版用 SQLite / DuckDB，还是直接进入 Java 后端 DB schema。
5. R54 二级市场数据没有补全前，R53 v0.1 允许验证哪些低依赖因子。
