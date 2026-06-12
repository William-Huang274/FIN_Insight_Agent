# Skill / Playbook / Eval Gate 内部合同

## 状态

- 来源：2026-06-10 外部 Skill / Playbook / Eval Gate 文档包。
- 当前处理：吸收为内部合同，不改运行时代码。
- 实施顺序：先完成数据源覆盖审计和 source registry，再把合同转成机器可执行 skill、schema 和 gate。

## Runtime 组装原则

vNext 不应在一次运行中加载所有 skill。运行时应按任务动态组装：

1. base system prompt
2. role skill
3. source boundary
4. industry playbook 摘要
5. task card
6. evidence bundle
7. output schema
8. 相关 eval rubric 片段

这与当前系统的 source-family bundle、task-card、ClaimCard、Memo Writer、Verifier 方向一致。后续改造重点不是增加长 prompt，而是让每个节点只看到它有权消费的证据和 rubric。

## Core Role Skills

| Role Skill | vNext 职责 | 当前映射 | 处理意见 |
| --- | --- | --- | --- |
| Research Lead v2 | 判断 research mode、激活 agent、定义证据需求。 | 当前已有 Research Lead、route selection、profile 和 source-family bundle。 | 暂不扩；等 source coverage matrix 完成后再升级 mode 和 evidence requirement schema。 |
| Context / Saved Run Resolver | 解析多轮上下文、已保存 run、失效范围。 | 当前已有 ContextManager 和 saved run inspection。 | 保持现状，后续补 replay 与 invalidation gate。 |
| Hypothesis Builder | 先形成 thesis / counter-thesis / unknowns，再驱动检索。 | 当前多为 Lead/Planner 隐式完成。 | 新节点候选，但必须等数据源缺口可被机器识别。 |
| Universe & Relationship Scope v2 | 确定公司、同业、供应链、客户、监管主体范围。 | 当前已有 universe / relationship plan 和 staged relationship edges。 | 优先依赖实体解析 registry 和 verified relationship edges。 |
| Retrieval Plan Builder v2 | 把证据需求编译成 route、source family、budget。 | 当前已有 cost-aware route selection。 | 可升级，但不能绕开 source-family 权限。 |
| Coverage & Gap Auditor v2 | 区分 sufficient、partial、source_gap、data_not_available、tool_blocked。 | 当前已有 Coverage / Reflection gate。 | 本阶段优先升级，因为数据源覆盖检查直接服务它。 |
| Thesis vs Counter-thesis Adjudicator | 对 verified claim cards 做裁决和权重排序。 | 当前 Judgment Aggregator 已有雏形。 | 待 ClaimCard 和 source gap 稳定后再实现。 |
| Memo Writer v2 | 只消费 verified outline / claim cards / compact evidence table。 | 当前 Memo Writer 已升级为 ClaimCard/outline 输入。 | 保持现有边界，后续补写作 profile。 |
| Verifier / Editor v2 | 检查 unsupported claims、数值、来源边界和缺证表达。 | 当前 Verifier 已有一轮 repair 和边界 gate。 | 后续合并 G10/G11 规则。 |
| Presenter | 把已验证结果转换成用户需要的格式。 | 当前 renderer / answer profile。 | 低优先级。 |

## Specialist Skills

统一合同：

- Specialist 只能读取 assigned evidence bundle 和 task card。
- Specialist 不能直接调用工具、扩 scope、补来源或把行业/新闻线索改写成公司事实。
- 输出必须是结构化 ClaimCard 或 CounterThesisCard，包含 `source_refs`、`support_strength`、`limits` 和 `source_gap`。

| Specialist | 证据优先级 | 可支持结论 | 禁止结论 |
| --- | --- | --- | --- |
| Fundamental | 公司主披露、SEC CompanyFacts、官方年报/季报、8-K earnings release。 | 商业模式、收入质量、margin bridge、cash conversion、资本结构、ROIC。 | 用市场价格、行业数据或新闻推断公司披露财务事实。 |
| Market / Valuation | 价格/成交量快照、event window、公开估值输入。 | 市场反应、相对走势、估值上下文。 | 把 unofficial market data 当成审计财务事实；制造 consensus。 |
| Industry / Supply-chain | 宏观/行业公开指标、verified relationship edges、公司披露中的客户/供应链文本。 | 行业周期、供需、关系暴露、传导路径。 | 把行业数据改写为公司收入、把 sector exposure 改写为直接客户关系。 |
| Product / Technology | 产品公告、专利、论文、监管/临床、公司披露。 | 产品周期、技术信号、研发/监管里程碑。 | 把产品发布直接当作收入确认或商业成功证明。 |
| Risk / Counter-thesis | risk factors、监管、litigation、反向指标、未覆盖缺口。 | downside risks、counter-thesis、证据薄弱点。 | 为了平衡观点而编造反面事实。 |
| Investment / Ownership Signal | SEC 13F、13D/G、Form 3/4/5、LEI/FIGI/entity mapping。 | 机构持仓、内部人交易、所有权变化线索。 | 把滞后的申报持仓解释为实时交易意图。 |

## Playbook 摘要

### Fundamental Analysis

内部基本面框架保留六层：

- Business Model Mapping
- Revenue Quality
- Margin Bridge
- Cash Conversion
- Balance Sheet and Capital Structure
- Capital Allocation and ROIC

claim 强度必须区分：

- `verified`：有直接来源和数值/文本支持。
- `inferred`：由多个公开事实推导，但需要说明推导链。
- `weak_lead`：只是线索，不能进入核心 thesis。
- `source_gap`：当前公开来源不足。

### Industry Playbooks

第一阶段只建议优先落地两个 playbook：Semiconductor / AI Infrastructure、Cloud / Software / Cybersecurity。原因是当前项目已有半导体、AI infra、云软件和供应链关系的真实运行经验，且公开来源覆盖相对可控。

其他 playbook 保留为内部合同：

- Healthcare / Pharma / Biotech / MedTech
- Energy / Power / Utilities
- Banking / Financials
- Consumer / Retail / Manufacturing / Trade

跨行业硬边界：

- 产品发布不等于收入证明。
- 行业数据不等于公司事实。
- sector exposure 不等于直接业务关系。
- EIA、FRED、BLS、BEA、Census 等只能作为行业或宏观上下文。
- 银行分析不用 EBITDA 作为核心经营质量指标。
- Rule of 40、gross margin、operating margin 等必须保持口径一致。

## Eval Gate 采用策略

外部文档定义 G0-G14。当前阶段不一次性实现全部 gate。

| Gate | 用途 | 当前策略 |
| --- | --- | --- |
| G0 Skill Contract | skill 文件结构、输入输出、禁止行为。 | 后续第一批实现。 |
| G1 Research Lead Routing | mode 和 agent 激活正确性。 | 等 source coverage matrix 后升级。 |
| G2 Hypothesis Quality | thesis / counter-thesis / unknowns 质量。 | Hypothesis Builder 前置条件。 |
| G3 Universe / Relationship Scope | peer、supplier、customer、entity scope。 | 依赖 R3-R5 relationship 工作。 |
| G4 Retrieval Plan | source family、route、budget。 | 与 public source registry 一起做。 |
| G5 Evidence Operator / Tool Ledger | 工具调用权限和 ledger。 | 延续现有 tool-call ledger。 |
| G6 Evidence Fusion / Specialist Bundle | Specialist 可见证据边界。 | 延续 source-family bundle。 |
| G7 Coverage & Gap | 缺证分类和二次检索。 | 本阶段最高优先级。 |
| G8 Specialist ClaimCard | ClaimCard 支持度、限制和引用。 | 待覆盖审计后扩。 |
| G9-G14 | Adjudicator、Memo、Verifier、Industry、Multi-turn、Full-chain。 | 等 G0-G8 和数据源扩容稳定后再做。 |

## 当前决策

- 暂不把 Graph 和 Skill 文档直接迁入 prompt。
- 暂不新增 Specialist 节点。
- 先把公开数据源覆盖、auth 状态、claim boundary、parser 状态和缺口类型落成审计表。
- 后续第一项工程化动作应是把覆盖审计转成机器可执行 source registry / coverage matrix，而不是直接改 prompt。
