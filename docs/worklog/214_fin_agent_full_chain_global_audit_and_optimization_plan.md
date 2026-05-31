# 214 - Fin Agent Full-chain Global Audit and Optimization Plan

Date: 2026-06-01

Branch: `codex/api-model-call-architecture`

Baseline commit locked before this audit: `945ca23 Add multi-agent research orchestration framework`

Sensitive-data note: user-provided API keys are not written to this document, repository files, or run artifacts.

## 1. Objective

本轮目标不是继续把链路做成“金融证据抽取器”，而是把 185/186 设计里的 multi-agent 投研系统往成熟 Fin Agent 推进：

- 能理解不同金融问题的方向、深度和上下文约束。
- 能合理调度 Research Lead、Universe / Relationship、Evidence Operators、Coverage / Reflection、Specialists、Judgment Aggregator、Memo Writer、Verifier。
- 能用知识库和工具给出高价值答案，而不是只把证据片段交给用户自己思考。
- 能在多轮对话中处理追问、改范围、查证据、重写输出、解释来源和继续分析。
- 能在安全边界内提高输出密度、投资判断质量和 token 使用效率。

## 2. Current Full-chain Map

当前 multi-agent native graph 主链：

1. `load_session_state`
2. `research_lead_plan`
3. `validate_activation_plan`
4. `universe_relationship_expand`
5. `route_by_execution_mode`
6. `compile_evidence_requirements`
7. `execute_evidence_operators`
8. `coverage_reflection`
9. `optional_second_pass`
10. `optional_specialist_subgraph`
11. `aggregate_judgment_plan`
12. `memo_writer`
13. `verifier`
14. `renderer`
15. `persist_session_state`

上一阶段已经完成：

- Banking runtime ledger / exact-value rows 修复。
- Specialist ClaimCard v0.3 ranker。
- Aggregator `memo_thesis_plan`。
- Memo Writer thesis-led output。
- Research Lead cost-aware activation。
- Relationship edge schema v0.2。
- Verifier quality gate。

但这些修复仍偏局部。当前最关键问题是：链路已能安全跑通并调用真实 retrieval / BGE / DeepSeek，但很多节点仍把“安全、可验证、能跑通”放在首位，没有把“投资论证密度、上下文连续性、输出可用性”作为同等级目标。

## 3. Global Issue Inventory

### 3.1 Orchestration and Gate Flow

1. `coverage_reflection` 依赖 `coverage_matrix`。在 multi-agent real retrieval 路径下，若没有显式 `coverage_matrix`，旧逻辑会默认 `sufficient`，导致真实检索缺行、route blocked、source gap 时也可能不触发 second-pass。
2. 初始 evidence coverage 和后置 quality second-pass 是两套机制。前者缺失时，后者只能在 Specialist / Aggregator 之后补救，代价更高。
3. `execute_evidence_operator_plan` 返回 `tool_observations`、rows、source gaps，但没有转换成 requirement-level coverage matrix。
4. `optional_second_pass` 可以执行，但 second-pass request 的质量受上游 reflection 的缺口表达影响；缺口不准时会重复搜、搜偏或不搜。
5. `quality_second_pass` 是 post-specialist 的启发式补救，不能替代 route-level coverage gate。
6. Summary artifact 对 rows / route / source gap 的总览不够直接，调试 token 是否有效时需要读多处 runtime ledger。

### 3.2 Scheduling and Agent Activation

1. Research Lead 已从粗暴全量激活改为 cost-aware activation，但 sector-depth 仍容易偏保守，可能多激活 supporting agents。
2. Specialist 是否运行主要看 evidence signal 数量，而不是“该 agent 是否有明确 thesis slot / user question / claim gap”。
3. Agent priority 还没有完全反映到 retrieval budget、row allocation、memo slot allocation。
4. `primary / supporting / conditional` 的策略已存在，但缺少全链路 cost telemetry 回流，无法基于真实 case 学习何时少跑或多跑。

### 3.3 Permission Matrix and Tool Ownership

1. 186 里的权限矩阵已部分落地，但 `relationship_graph` route 存在不一致：
   - Universe node 可以直接调用 `relationship_graph_lookup`。
   - `execute_evidence_operator_plan` 通过 `validate_operator_tool_call` 时，`universe_relationship` 是 `request_only`，所以 `relationship_graph` route 可能被阻断。
2. Universe relationship 直接调用 tool 时没有完全走统一 operator permission validator，权限审计口径和 route compiler 不一致。
3. Registry `max_tool_calls`、LoopBudget、route cap 分散，最终 budget explainability 不够清晰。

### 3.4 Retrieval, RAG, Chunking, and Rerank

1. SEC chunking 默认约 `900` words / `150` overlap，表格作为原子 paragraph。长表格可能超过 BGE doc truncate 上限，导致排序看到的信息不完整。
2. `evidence_top_k` / `object_top_k` 默认 per physical search 为 `4`，对 sector-depth、多 ticker、多 metric 问题可能偏低。
3. Route candidate budget 与最终 prompt row cap 是两层限制；candidate 多不代表 Specialist 最终能看到足够 evidence rows。
4. BGE 只有在 runner 显式传 `bge_first` / `BGE_DEVICE` / `bge_device` 时才稳定走 CUDA；否则默认可能走 CPU。
5. Rerank query 对真实 free-form query 主要依赖 prompt 和 route metadata，缺少“analyst lens + evidence requirement + thesis slot”的组合检索 query。
6. Context rows 没有被稳定转成 requirement-level coverage matrix，导致检索质量和 coverage gate 脱节。

### 3.5 Data View and Context Allocation

1. `build_agent_data_view` 已经有 role-scoped data view，但 Fundamental / Market 的 row selector 仍偏 first-N，缺少 ticker / metric / source / recency / rerank-score 平衡。
2. Industry Specialist 已补 relationship balanced selector，但 Risk Specialist 默认不看 relationship graph，sector-depth 风险分析可能漏掉依赖链风险。
3. Deep research data view 最大可到 32 rows，但 Specialist prompt 层还会再裁到 24 rows，预算口径不一致。
4. Row summary 约 300-420 chars。安全且省 token，但容易把可形成投资观点的细节压成证据摘要。
5. Specialist prompt 接收 relationship_summary，但还没有收到明确的 “assigned thesis slot / required claim cards / counterclaim task card”。

### 3.6 Specialist and Role-specific Skills

1. 四个专家已经升级到 skill v0.2 / ClaimCard v0.3，但 Research Lead、Universe、Coverage、Aggregator、Memo Writer、Verifier 等非专家 skill 仍混有 v0.1/v0.2。
2. Specialist 能理解上游任务，主要问题不是“看不懂”，而是：
   - 输入 rows 过压缩。
   - assigned task 不够 claim-oriented。
   - claim-card ranker 偏依赖特定 implication trigger terms。
   - 缺少从 evidence 到 investment implication 的强制中间步骤。
3. Fundamental / Market 仍容易输出“证据摘要 + 缺口提示”，不够像投资 analyst。
4. Risk 已修掉 no-ref supported claim 污染，但对 relationship risk、cross-source contradiction 的利用还弱。

### 3.7 Judgment Aggregation and Memo Writing

1. Aggregator 安全但压缩偏重。它会挡住 unsupported 内容，但也会把 Specialist 的分析深度压成可验证计划。
2. Memo Writer 输入主要是 verified judgment plan，而不是 richly structured thesis pack。安全但容易输出 bounded summary。
3. Memo Writer 当前输出 token 和 claim 数仍偏紧，适合短答，不适合高价值投研 memo。
4. 输出 contract 没有按用户需求区分：
   - quick answer
   - standard memo
   - deep research
   - evidence explanation
   - follow-up revision
5. Verifier 主要是 safety gate，不负责提升深度。通过 Verifier 不等于 memo 好。

### 3.8 Multi-turn and Product Agent Behavior

1. ContextManager / session store / tool harness 已存在，但 multi-agent graph 的 Research Lead 对 previous-turn summary 的消费还不够核心化。
2. Follow-up query 应该能识别“延续上一轮公司/年份/source scope/active answer”，当前更多是 controller/harness 层处理，graph 内部缺少统一 conversation state contract。
3. 成熟 Fin Agent 需要能在多轮中做：
   - scope revision
   - ask clarification when source unavailable
   - explain evidence
   - compare previous answer vs new evidence
   - produce shorter/longer rewrite
   - keep investment thesis stable while updating facts
4. 当前 eval 的 multi-turn 仍偏工具路由和场景回放，缺少 full-chain answer quality 多轮评测。

### 3.9 Eval and Observability

1. 当前 eval 能区分 route pass、Specialist quality pass、Verifier pass，但 memo-quality 和 token efficiency 仍需要更强指标。
2. 需要把 runtime ledger、tool observations、rows、source gaps、specialist input rows、claim-card rank、memo slots、verifier warnings 渲染成同一层 audit view。
3. 需要分层指标：
   - route / tool success
   - retrieval evidence quality
   - requirement coverage
   - Specialist task understanding
   - claim-card usefulness
   - aggregator thesis quality
   - final memo investment value
   - multi-turn consistency
   - token cost per useful claim

## 4. Root-cause Clusters

### Cluster A: Coverage Contract Gap

真实 retrieval 产物没有稳定进入 requirement-level coverage gate，导致 second-pass 的早期纠偏能力不足。

### Cluster B: Evidence-to-Claim Compression Gap

证据 rows 为了安全被压缩，但压缩后的输入没有明确 thesis slot 和 claim task，Specialists 容易停留在证据摘要。

### Cluster C: Permission Contract Split-brain

Universe relationship direct node 和 route operator validator 不是同一个权限通道，影响 186 权限矩阵的一致性。

### Cluster D: Output Contract Too Narrow

Memo Writer 和 Verifier 的 contract 仍像安全摘要器，不像成熟投研答复器。

### Cluster E: Multi-turn Context Not Native Enough

多轮能力在 controller/harness 层较强，但 multi-agent graph 内部没有把 conversation state 当作 first-class planning input。

## 5. Optimization Program

### P0: Observability and Chain Telemetry

Goal: 让每次 full-chain run 能一眼判断 token 花在哪、哪些节点被合理激活、哪些 rows 真正进入 agent。

Implementation:

- Summary artifact 增加 evidence row counts、source gap count、tool observation count、retrieval route count、reflection sufficiency。
- Eval renderer 增加 per-agent input rows / output claim cards / memo slots / token stats 的统一视图。
- Runtime ledger 标注 `route_id`、`requirement_id`、`retrieval_route`、`source_family`、BGE candidate/rerank stats。

Gate:

- 每个真实 full-chain case 必须能回答：哪个 route 搜了、搜到几行、BGE 是否执行、哪些 rows 进入哪个 Specialist、哪些 claims 进入 memo。

### P1: Route-level Coverage Reflection

Goal: 没有 `coverage_matrix` 时，也能从真实 `tool_observations` 推导 coverage gaps 和 second-pass requests。

Implementation:

- 新增 `reflection_report_from_tool_observations`。
- `_node_coverage_reflection` fallback 不再默认 sufficient。
- 对 route no rows / blocked / skipped 生成 requirement-level missing tasks。
- 对 permission / unsupported / budget 类 non-retriable blocked route 标为 source unavailable，避免重复无效 second-pass。

Gate:

- 单测覆盖 no coverage matrix + zero row route 触发 second-pass。
- 单测覆盖 permission blocked route 不重复 second-pass。
- Full-chain summary 展示 reflection trigger 和 row counts。

Status:

- 本文档创建后已执行第一切片实现。

### P2: Permission Matrix Unification

Goal: 让 186 的 agent 权限矩阵成为唯一事实来源。

Implementation:

- 把 `relationship_graph_lookup` 拆成明确的 bounded lookup route policy，或增加 `relationship_operator` owner。
- Universe node direct lookup 也走统一 permission audit wrapper。
- `validate_operator_tool_call` 支持 request-only planner 与 bounded relationship lookup 的边界区分。
- Registry、LoopBudget、route cap 输出同一份 budget explanation。

Gate:

- relationship route 不再因权限 split-brain 被误 blocked。
- Universe direct lookup 和 route lookup 在 ledger 中都有一致的 permission trace。

Status:

- 已执行首个 P2 切片：`relationship_graph_lookup` 通过 `bounded_relationship_lookup` 权限边界统一放行，Universe direct node 在调用 lookup 前也走 `validate_operator_tool_call`，`relationship_graph` retrieval route 的 rows 会作为 `relationship_graph` bounded context rows 进入下游 data view。

### P3: Retrieval Budget and RAG Quality

Goal: 提高真实 evidence row 质量，而不是盲目增加 cap。

Implementation:

- 按 execution mode / sector-depth / ticker count 动态设置 `evidence_top_k`、`object_top_k`、rerank top-k。
- BGE device policy 显式化：real full-chain 默认 `bge_device=cuda` when available，并在 summary 记录 fallback 原因。
- Rerank query 注入 evidence requirement、agent lens、thesis slot。
- 对长表格 chunk 做 table-aware clipping / column-aware structured extraction，减少 BGE truncate 损失。

Gate:

- AI infra、banking、healthcare、energy、utilities sector-depth packs 的 retrieval rows 通过真实 evidence quality gate。
- 每个 case 至少有 primary requirement coverage explanation。

### P4: Agent Data View v0.3

Goal: Specialists 看到的 rows 更像 analyst 工作台，而不是 first-N 摘要。

Implementation:

- Fundamental selector: ticker / metric / filing type / exact ledger / high rerank text balanced。
- Market selector: valuation / reaction / event-window / peer market rows balanced。
- Risk selector: risk text + counterevidence + relationship risk rows balanced。
- Industry selector: 保留 relationship rows，同时加入 sector depth pack source diversity。
- Specialist prompt 显式传 `assigned_task_card`、`required_claim_slots`、`counterclaim_slots`。

Gate:

- Specialist input rows 与 required claim slots 可解释。
- sector-depth / relationship case 下，Industry 和 Risk 都能引用 relationship evidence when expected。

### P5: Role-specific Skill v0.3

Goal: 所有核心 agent 都有明确输入字段、执行步骤、失败处理、输出结构和质量 rubric。

Implementation:

- Research Lead v0.3: cost-aware + conversation-aware + thesis-slot-aware activation。
- Universe v0.3: relationship graph as scoped hypothesis source, not fact source。
- Coverage v0.3: route coverage and source-unavailable decisions。
- Specialists v0.3: evidence-to-claim transformation steps。
- Aggregator v0.3: thesis plan, debate map, memo slot weighting。
- Memo Writer v0.3: output depth tiers。
- Verifier v0.3: safety + quality minimums。

Gate:

- 每个 agent prompt request 都能映射到 skill 的 required input fields。
- Eval 检查 agent 输出是否满足该 role 的 required output structure。

### P6: Aggregator and Memo Output Depth Tiers

Goal: final answer 从 bounded summary 升级为用户可用的投资判断。

Implementation:

- Aggregator 输出 `thesis_pack`：
  - core thesis
  - supporting drivers
  - counterarguments
  - watch items
  - evidence strength map
  - source boundary
- Memo Writer 按 depth 选择输出 contract：
  - focused answer: concise, 2-3 claims
  - standard memo: thesis + drivers + risks + watch items
  - deep research: sector context + company comparison + evidence table + caveats
- Verifier 不只检查 unsupported，也检查 memo 是否有 thesis、counterargument、decision-useful conclusion。

Gate:

- Final memo 不允许只有 evidence-thin summary。
- deep_research case 至少包含 thesis、supporting evidence、counterview、watch items、source boundary。

### P7: Multi-turn Native Planning

Goal: 把多轮上下文放进 Research Lead / Query Contract / Evidence Plan，而不只放在 controller 外层。

Implementation:

- 定义 `conversation_context_contract`。
- Research Lead prompt 明确消费 active answer、recent turns、invalidated artifacts、user requested revision。
- Evidence Plan 支持 follow-up scope inheritance 和 deliberate override。
- Renderer 支持 answer revision / comparison / explanation modes。

Gate:

- 多轮 eval 覆盖 scope revision、follow-up explain evidence、shorten/expand rewrite、same-session comparison。
- Follow-up 不重复跑无关 retrieval，除非用户改了 source scope 或 facts stale。

### P8: Eval Suite Upgrade

Goal: 评测从“链路能跑”升级到“金融 agent 有价值”。

Implementation:

- Layered eval:
  - route success
  - evidence quality
  - coverage
  - specialist claim quality
  - memo thesis quality
  - multi-turn consistency
- Sector-depth case packs:
  - AI infra
  - banking
  - healthcare
  - energy
  - utilities
- Token efficiency:
  - total tokens
  - tokens per memo-ready claim
  - tokens per final useful section
  - retries / repairs / second-pass gain

Gate:

- Real LLM smoke 先小样本逐 node inspect，再 full-chain batch。
- 质量回归必须报告 pass/fail 和主要失败原因，不只报告最终输出文本。

## 6. Execution Order

1. P1 coverage fallback + summary telemetry。
2. P2 relationship permission unification。
3. P3 retrieval/BGE/cap policy calibration。
4. P4 data view v0.3 selectors。
5. P5 role-specific skill v0.3。
6. P6 thesis pack + memo depth tiers。
7. P7 multi-turn native planning。
8. P8 eval suite and real-case gates。

## 7. Current Slice Implemented With This Document

Implemented immediately after baseline commit:

- `reflection_report_from_tool_observations` added.
- `_node_coverage_reflection` now uses tool observations fallback instead of defaulting to sufficient.
- Summary artifact now includes `evidence_rows` telemetry.
- `relationship_graph_lookup` permission split-brain fixed with `bounded_relationship_lookup`.
- Relationship graph route rows now propagate as bounded relationship context rows.
- Unit tests added for:
  - zero-row route triggers second-pass without coverage matrix.
  - permission-blocked route is treated as non-retriable source gap.
  - summary artifact contains evidence row telemetry.
  - relationship graph route permission and bounded row propagation.

Next slice should start from P3 retrieval/BGE/cap policy calibration, then rerun real DeepSeek full-chain on the 4 sector-depth cases.
