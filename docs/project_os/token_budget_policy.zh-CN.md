# Token Budget And Agent Information Economy Policy

状态：`repository_wide_active_policy`

Token 策略不是单纯省钱或缩短等待时间，而是决定一个节点能否完成其研究责任。预算必须服务于任务完整性、金融事实安全和内容质量；成本与延迟是约束，但不能代替研究范围和质量依据。

## 1. 每个节点必须签发 TokenBudgetBasis

任何自然模型节点、paid canary 或 live authority 在执行前都必须保存一份 `TokenBudgetBasis`，至少包含：

1. `node_mission`：本节点是开放规划、资料评估、研究分析、反方生成、综合写作、结构化交卷还是修复；
2. `input_inventory`：模型实际可见的 Evidence、NumericFact、关系、gap、方法步骤、图上下文和预计输入 token；
3. `required_outputs`：必须完成的命题、判断原子、引用、反方、WWC 或结构字段数量；
4. `schema_burden`：最终输出合同的字段数、枚举、引用绑定和合法组合复杂度；
5. `quality_and_materiality_risk`：遗漏本节点会对事实、投资判断、报告完整性和下游消费者造成什么影响；
6. `reasoning_profile`：thinking／non-thinking、协议、分析与交卷是否分离，以及为什么适合本节点；
7. `comparable_run_evidence`：同类节点历史 prompt／reasoning／visible completion 的 p50、p90 或最接近样本；没有历史样本时必须标为估算并先做最小 canary；
8. `headroom_and_limits`：基于输入、输出和历史波动得到的安全余量、最大值和批次拆分规则；
9. `stop_and_truncation_semantics`：无进展、截断、reasoning exhaustion、部分完成或预算不足时如何保存结果、如何续跑、哪些内容不得静默丢弃；
10. `cost_and_latency_estimate`：预估费用与延迟，作为执行选择的二级因素而非研究完整性的替代品。

未记录依据的统一 2k／4k／8k／16k 上限不能获得正式 execution authority。历史上“10 个自然 atoms 因固定上限只保留 8 个”的做法，只能在 materiality 排序、typed deferral 和下游可见的情况下成立；否则属于静默缩减任务。

## 2. 节点类型与预算方式

- **开放规划／研究分析**：预算由命题复杂度、可见证据、冲突、material gap 和预期推理步骤决定。不能用严格交卷节点的小预算压缩真实研究过程。
- **候选评估／Evidence Role／语义分类**：预算按待判对象数量与每项输出责任估算；超出单批容量时确定性分批并保存全量 coverage，不让尾部对象自然消失。
- **综合与正式写作**：预算由已验收 Judgment 数、依赖／冲突、交付深度和必答项决定；不得把输入 dump 给 Writer 后期待其在任意上限内自行压缩。
- **严格结构化交卷**：优先使用 analysis／submission 分离。交卷节点只映射已形成的分析草案、引用和枚举，可采用较低 thinking 与较小预算，但不能偷偷补写新观点。
- **修复／successor**：只为失败节点和受影响范围签发；预算依据保存的成功前缀与失败形态，不能借 repair 重跑无关上游。

## 3. 预算不足的产品语义

Token 上限导致 required output 无法完成时，必须产生 typed terminal state，例如：

- `budget_insufficient_for_required_scope`；
- `reasoning_budget_exhausted_no_visible_output`；
- `visible_output_truncated`；
- `partial_scope_completed_with_typed_deferral`。

这些状态不能冒充研究 gap、模型内容失败或成功结论。系统必须保存完整请求、Provider usage、finish reason、已完成项、未完成项和可复用前缀。提高预算、分批或改变 profile 都需要新的依据与 attempt，不得原地改写失败结果。

## 4. 信息经济指标

- token-to-rendered-claim yield；
- specialist useful-output rate；
- duplicate evidence transfer / prompt overlap；
- repair loop due to agent failure；
- required-item answer density；
- writer payload composition；
- low-value context ratio；
- paid-call fanout vs required-item coverage；
- material proposition completion rate；
- reasoning-token-to-visible-output ratio；
- truncation／typed-deferral rate；
- 内容质量增量相对于 token／费用增量。

这些指标用于寻找浪费、容量错配和质量边界，不能单独决定删掉哪个研究问题。

## 5. 修复顺序

1. 先确认节点责任和 required output 是否合理。
2. 再修 role-specific evidence selection 与重复输入。
3. 再修 specialist 激活、pack projection 和上下文分片。
4. 再修 ClaimCard → JudgmentCard／MemoLogicPlan 主输入。
5. 再判断是否需要分析／交卷分离、确定性分批或 profile 调整。
6. 最后才考虑提高 token、模型切换或 paid full-chain。

## 6. 不能接受的做法

- 为省钱简单砍 Evidence、研究命题、反方或必答项，且不留下 typed deferral；
- 因追求速度统一套用一个上限，不考虑节点复杂度和历史 usage；
- 将 reasoning exhaustion、截断或漏项误报成内容质量失败；
- 用小模型替代但不修上下游结构；
- Writer 收到 Evidence dump 后靠模型自己总结；
- 用 full-chain 反复烧 token 找 deterministic bug；
- 看到一次耗尽就无依据放大上限；
- 因预算不足把“未检索／未评估”写成“公开信息不存在”。

## 7. 通过口径

预算通过只说明“在有依据的资源范围内完整执行”，不说明内容质量通过。Closeout 必须同时证明：

- `TokenBudgetBasis`、实际 usage、finish reason 和偏差可审计；
- required item 已完成或逐项 typed deferral；
- 信息重复和低价值上下文受控；
- 没有因预算静默删题、删证据或删反方；
- Writer 输出不是模板化边界说明；
- Evidence-to-thesis 链条可追踪；
- 事实 L1、内容质量和任务价值另行通过；
- 失败能定位到最早 owned artifact、Provider/profile 边界或真实外部信息边界。

每轮结束后用实际 prompt、reasoning、visible completion、required-output coverage 和内容评分校准下一轮。预算应随证据改进，而不是成为永久常数。
