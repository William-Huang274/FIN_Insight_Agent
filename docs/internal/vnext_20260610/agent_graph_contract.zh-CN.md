# Agent Graph vNext 内部合同

## 状态

- 来源：`Agent_Graph更新方案.docx`。
- 当前处理：吸收为内部架构合同，不改当前 native graph / feature flags。
- 前置条件：公开数据源覆盖审计和 source registry 完成后，再决定节点升级顺序。

## 总体判断

vNext Graph 不应推倒重写当前系统。更稳妥的路线是：

1. 保留已验证的 evidence operator、source-family bundle、ClaimCard、Memo Writer、Verifier 和 gate。
2. 先定义状态对象、工件 schema、节点输入输出和 replay ledger。
3. 再逐步替换或插入节点，而不是先扩 prompt。

## 推荐状态对象

后续如果实现 `ResearchGraphState`，应至少包含：

| 字段 | 用途 |
| --- | --- |
| `query_context` | 用户问题、多轮上下文、语言、saved run 引用。 |
| `research_mode` | exact_value、focused_answer、standard_memo、deep_research 等模式。 |
| `universe_scope` | focus ticker、peer、supplier/customer、监管主体、排除项。 |
| `hypotheses` | thesis、counter-thesis、unknowns、验证需求。 |
| `evidence_requirement_plan` | 证据需求、source family、route、budget、claim boundary。 |
| `source_coverage_matrix` | 每类来源是否可得、是否已抓取、是否可支持目标 claim。 |
| `tool_call_ledger` | 工具调用、输入、输出、成本、去重、失败和重试。 |
| `evidence_bundles` | 分 role 的 bounded evidence bundle。 |
| `claim_cards` | Specialist 输出的 verified / inferred / weak / source_gap claims。 |
| `counter_claim_cards` | Risk / Counter-thesis 输出。 |
| `adjudication` | thesis vs counter-thesis 权重、冲突、证据强弱。 |
| `memo_outline` | Memo Writer 输入，不应包含 raw rows。 |
| `verification_report` | unsupported claim、数值、来源边界、缺口表达检查。 |
| `bounded_gap_register` | 公开来源不足、auth 缺口、parser 缺口、商业 API 延后项。 |

## 推荐节点序列

```text
Context / Saved Run Resolver
  -> Research Lead
  -> Hypothesis Builder
  -> Universe & Relationship Scope
  -> Retrieval Plan Builder
  -> Evidence Operators
  -> Coverage & Gap Auditor
  -> Specialist Subgraph
  -> Thesis vs Counter-thesis Adjudicator
  -> Memo Writer
  -> Verifier / Editor
  -> Presenter / Saved Run Review
```

## 节点升级边界

| 节点 | 规划收益 | 当前是否实施 |
| --- | --- | --- |
| Hypothesis Builder | 把研究从“找资料”前移为“验证 thesis / counter-thesis”。 | 暂不实施；等 source gap 可机器识别。 |
| Product / Technology Specialist | 处理产品周期、专利、论文、临床/监管信号。 | 暂不实施；等 PatentsView、OpenAlex、ClinicalTrials、openFDA coverage 进入 registry。 |
| Risk / Counter-thesis Specialist | 系统性产出反证和 downside risk。 | 暂不实施；当前 Risk skill 保持现有边界。 |
| Investment / Ownership Signal Specialist | 处理 13F、13D/G、Form 4、LEI/FIGI。 | 暂不实施；先补公开 ownership 数据覆盖。 |
| Thesis Adjudicator | 在 Memo Writer 前裁决 claim 权重。 | 暂不实施；可延续当前 Judgment Aggregator。 |
| Bounded Gap Register | 把缺口变成可追踪工件。 | 高优先级；与 Coverage & Gap Auditor 一起做。 |

## 并行与门控

- Evidence Operators 可以按 source family 并行，但必须写入统一 tool-call ledger。
- Specialist 可以本地并行，但每个 Specialist 只能消费自己的 evidence bundle。
- Coverage & Gap、ClaimCard、Memo、Verifier gate 必须同步阻断，不能由 Memo Writer 自行补洞。
- replay ledger 必须能回答：运行使用了哪些来源、哪些来源缺失、哪些结论被降级、哪些工具调用失败或被跳过。

## 对当前项目的直接影响

当前阶段只记录以下待办，不改 runtime：

- 把公开数据源覆盖审计转成机器可执行 source registry。
- 为 `Coverage & Gap Auditor` 增加 auth gap、parser gap、source unavailable、commercial deferred 的分类。
- 为未来 Graph state 定义 artifact refs，而不是把每个节点输出塞进长 prompt。
- 在 R3-R5 relationship 工作完成前，不把 relationship/news/industry 线索升级为直接业务关系事实。
