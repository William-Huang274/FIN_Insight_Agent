# 422 R48 Public Evidence Data Engineering Contract Into 25

日期：2026-06-28

## Prompt

用户要求把刚刚讨论的“更硬的数据工程方法”整合进 25 文档，作为后续 agent runtime / graph / harness / Java 后端讨论的一部分。

## Reasoning And Decision

25 文档原本记录 graph、harness、ContextEngine、MCP/A2A、durable execution、observability/eval 和 Java 后端技术栈。用户进一步强调，数据基座、数据源和知识图谱决定项目上限，因此 25 不能只定义 runtime，也要定义公开数据如何进入研究系统。

本轮把 L2/L3 外部验证源、行业 playbook、关系图谱推理和持续 eval 统一成一条硬数据工程链路：

```text
Research Question
 -> Evidence Role
 -> Source Route
 -> Fetch / Snapshot / Attempt Ledger
 -> Parser / Entity Binding / Period Binding
 -> Authority Gate
 -> Fact Mart / Signal Mart / Graph Edge
 -> Role EvidencePack / DimensionEvidencePortfolio
 -> LeadReview / TargetedRepair / Eval Gate
 -> Memo / Thesis / Gap Disclosure
```

核心决定：

- 不按“网站清单”扩源，而按证据角色扩源。
- URL seed / route seed / 搜索命中不计 source coverage。
- 公开源必须产出 parser-backed row、graph edge 或 attempt-backed typed gap。
- ProductSpec、CustomerDeployment、Benchmark、Channel、SupplyChain 等可进入 bounded thesis driver，但不能冒充 Product-KPI exact。
- 每家公司需要 `PublicEvidenceCoverageProfile`，让 Research Lead 区分 strong fact、bounded signal、retrievable gap、public boundary 和 commercial tracker gap。

## Work Completed

- 更新 `docs/architecture/agent_graph_vnext/25_agent_runtime_reference_stack_and_harness_context_engine_draft.zh-CN.md`：
  - 新增 `Public Evidence 数据工程方法` 章节。
  - 新增 `PublicEvidenceCoverageProfile` contract。
  - 新增 evidence role matrix 和公开源参考出处。
  - 新增行业 playbook contract。
  - 新增 Product / CustomerDeployment / SupplyChain / CapitalMacro graph inference contract。
  - 新增 Data / Parser / Graph / Research Eval Gate。
  - 更新后续讨论待定项和当前结论。

## Result And Evidence

本轮为 docs-only，没有改 runtime、parser、graph 或 eval 代码。25 文档现在把“公开数据源扩展”纳入 runtime 设计锚点，后续 R48/RD8 可直接按该 contract 拆任务。

## Follow-up

建议下一步不是继续泛泛扩源，而是：

1. 生成 603 公司 `PublicEvidenceCoverageProfile` baseline。
2. 先落 AI/Semis、Banks、Pharma、Auto、SaaS、Energy 六个代表行业 playbook。
3. 对每个行业只接能产出 parser-backed row / graph edge / attempt-backed gap 的 source-route adapter。
4. 将 source-route、parser、authority、graph、Research Lead、Memo 输出全部纳入 eval gate。

## Verification

- 本轮未跑模型、pipeline、full-chain 或 runtime tests。
- `git diff --check` 已通过。
