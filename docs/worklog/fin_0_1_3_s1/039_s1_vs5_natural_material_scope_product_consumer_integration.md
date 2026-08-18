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
