# 分功能执行顺序与通过条件

本执行文档把 vNext 拆成独立功能包，避免把 graph、reflection、web、playbook、skill、context、Milvus 一次性混改。

## G0 文档与合同冻结

工作：

- 落地本目录框架文档。
- 更新 architecture README、worklog、master checklist。
- 明确当前 product/public evidence authority。

通过条件：

- 文档可单独说明 graph vNext 的节点、边界和执行顺序。
- 未改 runtime 默认行为。

## G1 Source Family / Inventory Contract

工作：

- 扩展 `SOURCE_FAMILIES`：
  - `company_product_evidence_graph`
  - `public_source_context`
  - `live_public_web_context`
  - `milvus_semantic`
- 新增 `inventory_brief_v0.2`。
- Research Lead compact inventory 加入 product/public/source boundaries/gap counts/Milvus status/playbook candidates。

通过条件：

- Lead 能看到 source family 可用性、authority、gap type。
- Lead 看不到 raw rows / private paths。
- Existing Research Lead tests pass。

## G2 Plan Reflection Gate

工作：

- 在 `validate_activation_plan` 后加入 `plan_reflection_gate`。
- 检查 execution mode、industry schema、playbook、source family、web scope policy、budget。
- 不通过时只允许 plan repair，不允许进入 retrieval。

通过条件：

- 错误行业 schema / missing required source family 能被拦截。
- focused answer 不会误进 deep research。
- deep research 缺 relationship rationale 时 fail closed。

## G3 Evidence Fusion Selector vNext

工作：

- 把 product/public/market/industry/relationship/Milvus rows 统一投影为 authority-labeled bundle。
- 生成 `BoundedGapRegister` 初版。
- 明确 exact-authority / context-only / lead-only / gap-only。

通过条件：

- `runtime_fact_allowed` product rows 可进入 product KPI fact scope。
- public source rows exact authority 始终为 `false`。
- Milvus semantic rows 不可支持 exact value。

## G4 Reflection-driven Second Pass

工作：

- 拆出 `Reflection Diagnosis`、`Repair Plan Builder`、`Hard Gate`、`Targeted Repair Executor`、`Delta Auditor`。
- coverage second pass 和 quality second pass 分离。
- Delta audit 无新增 authority evidence 时停止循环。

通过条件：

- retrievable gap 能生成可执行 repair plan。
- commercial tracker gap 进入 bounded gap。
- parser/schema gap 不被弱 proxy 兜底。
- second pass 记录 closed gap / row delta / reason。

## G5 Web Evidence Operator

工作：

- 新增 web source scope registry。
- 新增 web repair request schema。
- 新增 allowlisted search/fetch/snapshot/source classifier/parser/authority gate。
- 默认写入 `live_public_web_context` context-only rows。

通过条件：

- search snippet 不能进入 claim card。
- unallowlisted domain 被 hard gate 拦截。
- ecommerce source 只能支持 SKU/price/availability，不支持销量/份额/库存。
- official/regulatory snapshot 只有 parser/gate 过后才能提权。

## G6 Product / Technology Specialist

工作：

- 新增 `product_technology_analyst` agent registry entry。
- 新增 skill prompt。
- 新增 source family selector 和 claim slots。
- 输出 product taxonomy / product KPI / public proxy / commercial gap claim cards。

通过条件：

- 产品 KPI claim 只由 company-disclosed exact-authority evidence 支撑。
- context/gap rows 不被写成事实。
- commercial gap 明确输出到 gap register。

## G7 Playbook Registry

工作：

- 新增 YAML playbook schema。
- 首批实现半导体、消费电子、SaaS、银行、能源、医药、汽车、零售/CPG。
- Research Lead 用 playbook 选择 source family / specialist / web scope。

通过条件：

- 同一 query 在不同 industry schema 下激活不同 source policy。
- playbook 的 forbidden claims 被 reflection/verifier 使用。
- 未覆盖行业能走 generic playbook 并暴露 coverage gap。

## G8 Shared Context Contract

工作：

- 升级 `AgentDataViewV0.3`。
- 定义 Global / Role / Private context。
- Specialist 并行消费 frozen evidence bundle。
- Memo Writer 只消费 verified judgment / claim cards。

通过条件：

- Specialist 不拿 private paths。
- Memo Writer 不拿 raw evidence rows。
- Operator 不拿 memo draft。
- Context digest 可复现。

## G9 Async Fan-out / Barrier Graph

工作：

- Evidence operators fan-out。
- Specialist fan-out。
- Evidence Fusion / Delta Audit / Claim Card Store / Adjudicator 作为同步 barrier。

通过条件：

- 并行结果 deterministic merge。
- 任一 operator fail 不污染其他 source family。
- Barrier 后状态 schema 稳定。
- Existing sync graph 可 feature-flag 回退。

## G10 Milvus Runtime Switch

工作：

- Inventory 显示 cloud/local/unavailable。
- 云端 Milvus 通过 env/profile 注入。
- 本地 Milvus Lite 可选。
- 缺 Milvus 时 route unavailable，不 mock 成可用。

通过条件：

- Local no-Milvus tests pass。
- Cloud Milvus route tests pass when enabled。
- Verifier 阻断 Milvus exact-value misuse。

## G11 End-to-end Gate

工作：

- 设计 10-20 case gate，覆盖 exact/focused/standard/deep/multi-turn。
- 覆盖行业：半导体、消费电子、SaaS、银行、能源、医药、汽车、零售。
- 检查 evidence authority、claim card、gap register、web boundary、Milvus route。

通过条件：

- No unsupported core thesis。
- No source-boundary violation。
- No weak proxy fallback。
- All gaps either closed by authority evidence or bounded.
