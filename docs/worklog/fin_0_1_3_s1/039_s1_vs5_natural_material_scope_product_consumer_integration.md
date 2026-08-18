# S1 VS5 自然材料范围与产品消费者集成

日期：2026-08-18

状态：`product_consumer_integrated / deterministic_scope_replay_proven / natural_scope_execution_path_qualified / live_not_run / S1_not_qualified`

## 本轮解决的业务问题

此前 S1 已能从完整候选池保护一组研究材料，但它并不知道复合研究题中的哪些产品、指标、机制、期间和证据角色是本次判断真正必须覆盖的。确定性 fallback 可以解释 MU／NVDA 的标准化请求，却不能替用户把“AI 服务器需求与营运资本”“客户集中、定价、取消与库存风险”等复合题强行压成一个产品词。继续扩充 DELL／COST 专用词表只会制造案例特化。

本轮把这个边界接入了当前 Workbench 受控研究计划：

1. 模型可见范围只包含 EvidenceRequest 的公开索引、候选研究维度、期间和枚举，不含候选 ID、对象 ID、qrel、reference、答案 URL 或排名结果；
2. Harness 固定公司身份、截至日、来源角色、允许的枚举、容量和 request digest；模型只能选择 material scope，不能创造事实或引用；
3. 已能确定的标准主题继续走本地编译；只有确定性编译无法覆盖的请求才需要一次自然 `ResearchBlueprint` 范围提交；
4. 自然结果必须覆盖每个待解释请求、必需 Evidence Role、metric 轴和 hard-product 轴，并与首次受控计划 digest 完全相同；漏项、越界、候选身份泄漏和将固定分类改弱均 fail closed；
5. 完整 BM25＋Qwen 候选并集先参与材料保护，再执行来源配额与有限 review window。硬 requirement 候选可保留，普通材料候选只有排序优先权，不能借机绕过来源多样性。

## 产品纵切结果

四案保存资产零调用回放仍保持：COST 5、DELL 3、MU 4、NVDA 6 个请求的 fallback 候选材料组均完整且排列稳定；这里使用新的明确字段 `candidate_material_set_complete_request_count`，不再把它误读为产品范围已准备。真正的 `runtime_scope_ready` 仍为 COST 2／5、DELL 0／3、MU 4／4、NVDA 6／6。

当前 Workbench DELL 受控计划也已走实际产品消费者，而不是 replay-only runner：自然 planner 保存的 10 个 atoms 中选择 8 个请求、2 个延后；S1 为 8／8 请求形成非空候选面，S2 同步执行 28 个 typed fact request，得到 19 个 resolved、9 个 typed gap 和 58 个 NumericFact。 learned candidate route 在 RTX 4060 Laptop 的 `cuda:0`／FP16 执行，未回退 CPU。由于这 8 个自然产品短语均超出确定性 hard/context ontology，产品诚实返回 8／8 `explicit_scope_required`，没有把 fallback 候选齐全冒充成研究范围已齐。

首次真实集成还暴露并关闭了一个重要缺陷：早期实现把所有材料 review 候选都当成硬保留，导致它们绕过来源配额。当前只有 requirement receipt 明确绑定的候选属于 hard reservation；其余候选只获得排序优先级，仍受来源配额控制。修复后 DELL 每个请求只有 1–2 个硬保留候选，最终 16 个 review 候选通常来自 10–15 个不同 source object，来源多样性没有被材料保护破坏。

## 验证

- `tests/test_s3_material_scope.py`：自然范围合同、候选盲、固定分类保护、digest 漂移和 fail-closed mutation；
- `tests/test_s1c_hybrid_candidate_runtime.py`：pre-topK reservation、请求漂移、来源配额和 filler 不得豁免；
- `tests/test_s3_research_planning.py`：Workbench 两步受控计划、deterministic ready 与 explicit scope required；
- 全仓 `672 passed`；
- `python -m compileall -q src apps scripts`：通过；
- active baseline：161 Python／8 frontend／20 Runtime resources／0 forbidden reference；
- 四案 replay result digest：`cb7f0d3f403ccb61643a709ea6f205774cd2b95597720db698de442b033bd3fe`。

## TokenBudgetBasis 与下一步

下一步只允许一个 DELL 自然材料范围 canary，不访问网络、不运行检索、不读取候选或 gold，也不生成判断或报告。它一次处理当前 8 个 explicit-scope request；输入规模、输出原子上限、exact JSON 负担、研究重要性、可比零调用证据、reasoning profile、截断和停止行为均冻结在 `configs/research/fin_ia_0_1_3_s3_material_scope_policy_v1_0.json` 的任务专属 `token_budget_basis`。该调用的价值不是“再问模型一次”，而是验证模型能否在看不到答案的情况下把自然复合研究题转成完整、受约束、可执行的材料范围。

canary 通过后，只将同一 payload 接回当前 Workbench 计划并复跑一次 CUDA 候选路径；随后才检查 CandidateDecision／Evidence Gate／S2 权威和 Pack Readiness。失败则保留原始 capture，最早责任归自然范围编译或 Provider 合同，不自动扩大本体、token 或重试。COST 人工 reference、一套新的 Git 外 blind qualification、Evidence 晋升与 S1 产品资格仍是独立门。

## Exact-once 执行路径预备

当前已补齐 provider profile、候选盲 input、exact-once authority、capture-first terminal result 和 Project OS preflight 的统一执行路径；fake exact-once、profile／input digest 漂移、合同失败物化与当前 Runtime 注册表均通过测试。这里的“qualified”仅指执行基础设施具备签发条件，不表示 DeepSeek 已通过自然范围任务。

第一次零调用输入 `v1_0` 绑定提交 `035d2210...`，完整复现 10 个 proposed／8 个 selected／2 个 deferred、8 个 explicit-scope request、128 个候选、58 个 NumericFact、0 网络／0 生成模型调用。模型消息只含请求公开索引与闭合枚举，不含候选、对象、qrel、reference、URL 或答案。该输入的每请求审计摘要因产品结果将 request ID 放在嵌套 `request` 对象而显示 `null`；模型可见内容与 required request binding 没有受影响，但该版本只保留为 superseded 审计证据，不进入付费 authority。修复后的输入必须由一个包含执行实现的干净提交重新生成，不能覆盖 `v1_0`。

执行实现已在干净远端提交 `20ca2768...` 冻结。随后生成的 `v1_1` 与 `v1_0` 具有相同 plan digest 和 model-visible messages digest，但 8／8 请求审计 ID 均完整，且输入声明的 `prepared_from_commit` 精确绑定 `20ca2768...`。`v1_1` 才是后续 exact-once authority 唯一允许绑定的输入；它仍不是模型结果、Evidence、S1 资格或产品发布。

`v1_1` 与回归测试已在干净远端提交 `c893c94f...` 冻结。R1 authority 逐项绑定该提交、输入及消息 digest、五份 provider-neutral 合同、DeepSeek profile、runner 和实现源码；预算仅允许 1 次模型／1 次传输、0 retry／fallback／协议切换／检索／embedding／候选读取／产品写入。Project OS 零调用预检确认 RC-S1-024 明确允许该 scope，另外 25 个 full-chain blocker 均保持 out of scope。authority 签发本身仍不表示 live 已发生。

## R1 真实结果与最早责任层

R1 在干净远端提交 `2ccfa1eb...` 上通过正式 Project OS preflight 后执行。唯一一次请求返回 HTTP 200，响应 body 完整；prompt 为 2,781 tokens，completion 为 12,000 tokens，其中 reasoning 为 12,000，`finish_reason=length`，可见 JSON 为 0。0 retry／fallback／检索／候选读取／产品写入，原始请求与脱敏响应均先行留存。由于没有任何 scope payload，不能评价材料范围质量，也不能进入 Workbench replay。

这不是 S1 检索、网络或合同 validator 失败。最早责任层是可替换的 DeepSeek provider profile：任务专属 TokenBudgetBasis 把本节点定义为“有界分类与分解”，profile 却启用了 `thinking=max`，模型把全部可见输出容量消耗在私有推理。R1 保持不可变且禁止重试；successor 不增 token、不改输入、不改 provider-neutral 合同，只允许将合同提交 profile 改为 `thinking=disabled` 且不发送 `reasoning_effort`。若同输入非 thinking 提交仍无法形成完整结果，才考虑按请求 microbatch，不能现在就扩大核心 Harness。

## R2 非 thinking successor 与合同编译器根因

R2 已从 clean／synced 提交 `ae62e8b3...` 通过 Project OS preflight 后 exact-once 执行。非 thinking profile 解决了 R1 的提交层故障：HTTP 200、完整响应、`finish_reason=stop`、prompt 2,689、completion 1,842、reasoning 0、可见 JSON 6,444 字符；1 次模型／1 次传输，0 retry／fallback／检索／候选读取／产品写入。失败 terminal summary 现在能从 capture 投影 finish reason、usage 和 request／response digest，原始内容仍不进入业务结果。

R2 仍为 `terminal_failed_no_retry`，但最早责任已前移到 provider-neutral 合同编译器。模型可见 `output_contract` 只列字段名，没有列 validator 已经要求的三个顶层字段、三组 closed enum 及跨字段绑定规则。模型返回了 8 个 request row、19 个 product disposition 和 12 个 material atom，却自行使用 `request_scope`、`direct`、`span_2026_2027`、`all_products_all_metrics` 等未授权词汇；validator 正确以 `research_material_scope_output_fields_invalid` 拒绝。

因此 R2 不能简单归因于 DeepSeek，也不应 microbatch、加 token、放宽 validator 或本地偷偷改写输出。R2 保持不可变且禁止重试。下一修复必须从 policy／validator 同一词汇表编译精确顶层结构、closed enum 与 binding rule，补 schema-drift、R2 replay 和跨案例零调用测试；模型可见消息改变后必须生成新的 clean-commit-bound input。只有新的 Project OS authority 可另行允许一次 R3，R3 仍不是产品 replay、Evidence、Pack Readiness 或 S1 资格。

## R3 合同通过与产品回接的新最早责任层

R3 在 clean／synced 提交 `94fef96e...` 上通过 Project OS preflight 后 exact-once 执行。它使用与 R2 相同的 8 个请求、相同的产品投影和非 thinking profile，只改变 provider-neutral 模型可见合同。结果为 HTTP 200、`finish_reason=stop`、prompt 3,754、completion 1,752、reasoning 0；8 个 request、19 个 product disposition、12 个 requirement atom 全部通过本地合同，0 retry／fallback／检索／候选读取／产品写入。RC-S1-027 因而关闭，R3 不需要也不允许重跑。

同一不可变 R3 payload 随后接回当前 Workbench BM25＋Qwen CUDA／FP16 路径。运行在候选选择前以 `material_requirement_review_capacity_insufficient` 停止；这不是模型、Embedding、排序或公开资料 gap。审计显示 `_expand_atom` 把本应作为一个集合审阅的 `collective_axes` 原子按 metric×product 拆成单例 requirement：12 个 atom 被放大为 73 个 group、最坏预留容量 132。第一、二、三请求分别需要 27、21、36 个审阅位，而每请求 `review_k=16`；按 EvidenceSetCoverage v1.1 已有的集合语义，它们应只需 3、3、2 个位置。

因此下一项限定为 RC-S1-028 零调用修复：每个非时间型 `collective_axes` atom 编译成一个保留相关多轴的 requirement；跨期 `single_binding` 原子性、候选身份边界、review_k 和 R3 payload 均不变。补足多指标＋多产品、跨期、排列变化和 DELL／MU／NVDA 回归后，复用同一 R3 payload 回接当前 CUDA 产品链。只有到达真实候选选择，才继续审查 CandidateDecision、Evidence Gate、S2 权威和 Pack Readiness。

## RC-S1-028 关闭与候选送审语义的新断点

零调用修复已把 12 个 R3 atom 保持为 12 个相关材料组，各请求最坏预留容量恢复为 `3／3／2／2／2／3／1／2`；跨期原子性、`review_k=16`、候选身份和不可变 R3 payload 均未变化。DELL／MU／NVDA、时间型和排列 mutation 通过，因此 RC-S1-028 关闭。

同一 R3 payload 随后正式跑完当前 Workbench BM25＋Qwen CUDA／FP16 候选链：8／8 请求 scope-ready、128 个候选、58 个 NumericFact、19 个 typed fact resolved、9 个 typed gap，0 网络／0 生成模型调用／0 CPU vector fallback。但 12／12 requirement 仍未满足，0／8 material set complete。逐候选业务审计证明，这不是候选池为空：Dell 10-K 已有“AI 服务器需求推动 backlog 增长”的直接表述，业绩表也覆盖 revenue／income／EPS／margin；它们没有被 requirement receipt 预留，是因为 R3 把自然产品短语选为 hard axis，而候选编译器把相同短语仅保存在 `contextual_or_unclassified_need_product_intents`，集合选择器只读取 canonical `product_ids`。

不能把这些上下文短语直接晋升为 Evidence。只做这种粗暴替换，会把 Micron 的内存供给描述误当作“GPU 供应约束”，把相邻财务表误当作“AI 增量利润”证明。RC-S1-029 因此限定为候选送审与 Evidence 通过的分层：非时间型 `collective_axes` 可让同一请求、facet、role 下的自然短语贡献到有界复核 bundle，但必须继续标记 `abstain / candidate-not-Evidence / numeric-authority=false`；CandidateDecision／Evidence Gate 再依据实际文本逐 requirement 接受、拒绝或保留复核。`single_binding` 时间比较不得使用该放宽。

正式公开结果为 `configs/retrieval/fin_ia_0_1_3_s1_dell_material_scope_product_replay_result_v1_0.json`，处置说明为 `configs/retrieval/fin_ia_0_1_3_s1_dell_material_scope_product_replay_assessment_v1_0.json`。当前 0／8 不是公共资料 gap，也不证明 DeepSeek、Embedding 或网络失败；S1、Pack Readiness、完整 S3 与发布仍为 false。
