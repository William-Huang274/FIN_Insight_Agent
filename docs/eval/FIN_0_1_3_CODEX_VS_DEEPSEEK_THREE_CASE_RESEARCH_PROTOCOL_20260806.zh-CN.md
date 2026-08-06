# FIN 0.1.3 Codex vs DeepSeek 三案例研究对照协议

日期：2026-08-06  
更新：2026-08-07
状态：`active / shared evidence frozen / dynamic runner zero-call pass / DELL admission issuance authorized but not issued`

## 1. 比较目标

本协议不再用一次混合全链结果同时评价模型和工具。它拆成两个实验：

- **Experiment A — same-evidence reasoning**：在零检索条件下，让 DeepSeek 消费与 Gold candidate 相同的共享 Benchmark Evidence Pack，隔离评价分析、反证、机制综合、Lead、Writer 和 Verifier 能力。
- **Experiment B — end-to-end agentic research**：MCP、当前外部来源和 Agentic Search 通过后，再让 DeepSeek 从研究规划与检索开始完成三案全链，评价真正的 Agentic Search/Research。

当前九调用 S3 R3 只作为 minimum control：它证明结构与 exact-once，不是高质量研报标准答案。

## 2. 共同冻结对象与公平性

每案先冻结：

1. research objective、as-of、issuer identity、source authority 和八维质量 Rubric；
2. 共享 Benchmark Evidence Pack：包含 Gold 使用的重要事实、数值、来源、发布日期、抓取时间、lineage 和明确缺口；
3. blind input：不得含 Codex thesis、机制综合、counter-thesis 结论、WWC 答案、分数或逐条修订；
4. hidden Gold scoring objects：由 evaluator/reviewer 使用，DeepSeek 与执行节点不可见；
5. leakage checks、input digest、case/version identity 和预算。

Codex Gold candidate 实际使用了产品本地数据、部分可用 MCP 与额外官方公开来源，不能笼统声称“当前完整 MCP 已跑通”。Experiment A 必须先把这些事实编译进共享 Pack；若仍有可见证据差异，必须逐项登记，相关维度不得用于模型强弱结论。

### 2.1 S2-04 冻结结果

- model-visible Pack：`eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json`，digest=`93a75f3d…0030d`；
- model-visible blind input：`eval_sets/fin_0_1_3_same_evidence_v1/model_visible/experiment_a_blind_inputs_v1.json`，digest=`55b47486…61688`；
- evaluator-only hidden objects：`eval_sets/fin_0_1_3_same_evidence_v1/evaluator_only/hidden_gold_scoring_objects_v1.json`，digest=`4ec201a5…4ebab`；
- 内容规模：`3 cases / 10 sources / 33 evidence / 12 derived numeric / 12 explicit gaps / 12 hidden targets`；
- 冻结 manifest：`configs/releases/fin_ia_0_1_3_s2_04_shared_benchmark_evidence_freeze_v1_0.json`。

模型可见材料由原始事实重新编译，不沿用 Gold 报告的章节顺序或结论式标题。可见与 evaluator-only 对象物理隔离，validator 同时阻断未来来源、跨案证据、隐藏 key/phrase、公式漂移、digest 篡改及 hidden target 跨案绑定。S2-04 没有模型、MCP、网络或产品运行；Experiment A 的 admission 尚未签发。

## 3. Experiment A：同证据、零检索

### 3.1 执行顺序

1. `013-S2-04` 编译并冻结三案共享 Pack、blind input 和 hidden scoring objects；
2. `013-S2-05` 依次执行 Research Lead planning、Specialist judgment、cross-cell synthesis、Writer 和 Verifier；
3. 不开放 MCP、网页、搜索或额外知识补充，不用工具缺口解释当前实验的分析结果；
4. 每个节点保存完整 model-visible request、raw assistant output、usage、finish reason、capture digest 与 terminal；
5. 首个 material 偏离暂停当前 formal case，记录原因后才允许 supervisor 扶正；
6. `013-S2-06` 汇总 raw model-only、supervisor correction 和 corrected candidate，形成模型能力边界。

### 3.1.1 S2-05 admission 入口审计结果

S2-04 input 已满足公平性，但当前仓库只有三调用窄 canary 和九次 compact Specialist Anchor；二者都没有自然 Research Lead planning、动态多研究单元、自然 cross-cell synthesis、Writer 和 Verifier，因此不得复用并签发 Experiment A。

唯一允许的下一实现采用“一案一个 exact-once admission”：

- 每案 1 次 Lead planning，动态生成 6–8 个覆盖六个 mandatory family 的研究单元；
- 每研究单元 1 次 Specialist，随后各 1 次 synthesis、Writer、Verifier；
- 每案 10–12 次、三案最多 36 次，retry/fallback=0；
- 模型 runner 只能精确读取冻结的 blind input，不得目录通配、读取 hidden Gold、访问 MCP/外网或补充训练知识事实；
- raw track、supervisor correction、corrected candidate 和 evaluator-only 四类权限分开；
- 首个 material failure capture-first 后暂停本案，且不自动开始下一案。

当前 decision=`configs/releases/fin_ia_0_1_3_s2_05_experiment_a_admission_authority_decision_v1_0.json`。它只授权一个零调用 runner/full-fake/preflight 实现包；不授权 admission issuance、consumption 或 DeepSeek 调用。

### 3.1.2 S2-05 动态 Runner 与 fresh authority 结果

专用 runtime policy、dynamic runner 和 production entrypoint 已完成零调用证明。Lead=`1`、Specialist=`6–8`、synthesis/Writer/Verifier=`1/1/1`；六 mandatory family 和完整 case Evidence/Gap 必须贯穿到 Writer，identity、as-of、跨案引用、未绑定数值、漏证据与 Verifier material failure 均 fail closed。每次完整 request/gateway result 在 parse/validation 前保存在 raw-only track；admission shared-ledger exact-once，首错停本案和 campaign。三案 full-fake=`30 calls`，8-unit 上界=`12 calls`，当前 S2 命名合同=`95 passed`。

fresh authority 只批准下一步签发一份 DELL admission，不批准消费、模型调用或 MU/NVDA。admission 必须在本 decision 提交后绑定 then-current clean/synced HEAD，并保存到 Git 忽略的 `.codex_runtime/fin013_s2_05/authorities/DELL`，避免把 admission 本身做成自指 Git commit。真实 DELL 成功前不得取得 MU authority；任一 material failure 停止，不自动 patch/retry/rerun/next-case。

当前 decision=`configs/releases/fin_ia_0_1_3_s2_05_experiment_a_fresh_admission_authority_decision_v1_0.json`。它仍是零调用治理结果，不证明 DeepSeek 分析质量。

### 3.2 Experiment A 只回答

- 同样证据下，模型能否形成公司专属而非模板化的判断；
- 能否区分事实、推断、边界和反证；
- 能否连接产品/需求/供应链证据到收入、利润、现金流、估值或风险机制；
- 能否处理跨 Cell dependency/conflict 与 material gap；
- 能否写出有结论、最强反方和可观测 WWC 的研究报告。

它不回答检索覆盖、MCP 可靠性、网页解析或自主工具使用能力。

## 4. 工具修复与 Experiment B 前置门

Experiment B 之前必须完成：

- MCP registry/resource binding、cold/warm start、handler phase telemetry、bounded timeout/cancel/no-orphan；
- SEC/IR/web/PDF/redirect/crawler/parser 的 capture-first 与 typed failure；
- 正文获取与 Evidence promotion，禁止只拿 URL 或 metadata wrapper 冒充证据；
- 三案 Agentic Search eval：Gold evidence slots、query revision、required recall、false promotion、currentness、source diversity、accepted/rejected/gap；
- 工具问题归 S1，禁止用 DeepSeek paid run 来逐个发现确定性 adapter/parser 缺陷。

## 5. Experiment B：端到端 Agentic Search/Research

1. DeepSeek 只看 objective、as-of、source policy、预算和可用工具，不看 Gold answer；
2. Research Lead 按 hypothesis、Cell、证据缺口和信息增益动态规划，不固定三 Cell、九调用或 15–25 调用；
3. EvidenceRequest 必须编译到具体 operator/query，来源请求与响应先 capture 再解析；
4. accepted evidence、rejected candidate、typed gap、query revision 和 stop reason 全部留存；
5. supervisor 可暂停、补证、缩小问题或退回节点，但 raw 与 corrected 分轨；
6. 三案结束后才对 hidden Gold 做八维、paired 和 qualified-human 内容验收。

调用上限按案例预注册，继续调用必须有信息增益：新增可信证据、关闭 material gap、解决冲突或提高 authority。调用次数本身不是质量指标。

## 6. 节点级暂停与 collect-all 规则

formal case 遇到以下 material failure 立即暂停：

- 公司、期间、单位、币种或来源身份错误；
- 关键数字无法回算或把 proxy 当 exact authority；
- 将 boundary-only evidence 晋升为 thesis support；
- 遗漏共享 Pack 中已有的重大反向证据；
- 核心机制没有连接到财务、估值或可观测风险；
- Lead 未处理 material conflict 就允许 Writer；
- Writer 引入 Pack 之外的新事实；
- Verifier 只验证结构、不验证研究实质。

若为集中暴露后续问题而继续，必须在执行前标记 `quarantined_non_promotable_collect_all`。这类下游结果只能用于诊断，不能成为 formal pass、paired gain 或产品晋升证据。非关键措辞与版式问题记录为质量 finding，不中断主链。

## 7. 问题归因

每个 finding 只能主要归入一个最早 owner：

- `tool_runtime_gap`：MCP、adapter、parser、timeout、source capture；
- `evidence_availability_gap`：授权来源确实无结果或截至日不可得；
- `research_planning_gap`：问题分解、查询路线、停止条件；
- `model_reasoning_gap`：同证据下的判断、反证、综合与写作；
- `contract_or_local_authority_gap`：schema、selector、renderer、numeric/date/identity ownership；
- `product_workflow_gap`：Workbench 的暂停、介入、repair、resume、review；
- `evaluation_gap`：Rubric、Gold 或 reviewer 不能区分质量。

工具缺陷不得记为 DeepSeek 失败；supervisor 扶正后成功不得记为 autonomous model success。

## 8. 必留产物

每案必须保留：

- research objective、DecisionSurface revisions 与预算；
- ToolUseLedger、原始来源 capture、解析结果、rejected candidates 与 gaps；
- 共享 Evidence Pack、Numeric checks、Claim/Judgment Cards；
- Lead review、repair/correction history、Writer input/output、Verifier findings；
- Codex Gold candidate、DeepSeek raw candidate、corrected candidate；
- 八维评分、逐差异、工具/模型分账和 reviewer decision。
