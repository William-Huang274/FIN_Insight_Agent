# FIN 0.1.3 角色 Skill、图谱与 DeepSeek Harness 重新资格审计

日期：2026-08-14

性质：只读审计、合同与执行顺序决策

模型／Provider／网络调用：0／0／0（官方资料只作只读架构核对）

## 1. 为什么在下一次自然运行前做这次审计

DELL `value_capture` 的 Chat／Responses paired R1 已证明两种协议都能完成同一个五步工具循环，但两路内容都未通过 L1。共同问题包括：比较关系没有绑定同口径期间、补证请求的来源类别与实际 route 不一致，以及把多因素利润改善写成 AI 周期的经营杠杆。

用户随后追问：此前为不同研究角色编写的 Skill 和知识图谱是否被当前 Agent 使用。这个问题必须先回答，否则继续修 Prompt 或再调用模型，会把“缺少研究方法和关系上下文”误判为单纯的模型能力问题。

## 2. 当前付费 canary 实际消费了什么

当前 Runtime Registry R11 有 10 个资源，覆盖金融研究内核、检索／路由、Evidence Pack、研究规划、来源接入和排名投影；没有当前 `SkillPack` 或 `GraphPack` 资源。

当前模型系统提示只要求模型作为“受限金融研究分析师”，使用四个工具并遵守证据边界。两路保存的 model-visible request 均没有：

- `method_runtime_pack` 或角色专属研究 Rubric；
- `SkillPack`／`RoleMethodPack`；
- `GraphPack`／`ProductIntelligenceGraph`；
- `value_capture_specialist` 的具体分析方法；
- 客户、供应商、产品、利润传导和反方机制的受控关系图上下文。

`value_capture_specialist` 只作为 EvidenceRequest 的 `requester_role` 标签出现，不等于模型消费了该角色的方法。`relationship_directions` 也只携带主体自披露和 provenance 方向，不等于经济关系图。

因此，本次 paired 仍可证明协议、工具续接和当前四工具合同；它不能证明旧角色 Skill 或知识图谱有效，也不能用来判定“加载这些方法后 DeepSeek 仍然同样失败”。

## 3. 旧角色 Skill 审计

归档目录 `archive/versions/pre_fin_0_1_3/unpromoted_active_tree/src/sec_agent/prompts/skills/` 中共有 20 个 Markdown 文件。它们包含 fundamental、industry/supply-chain、product/technology、valuation、risk/counterevidence、lead、writer、verifier、evidence boundary 等方法；部分 v0.1/v0.2 文件内容重复，部分文件名版本与正文版本不一致。

### 3.1 仍然有价值的内容

- Fundamental 明确禁止在没有 mix 或毛利率支持时把 AI server revenue growth 写成利润改善，并要求同比、环比和利润率比较具有兼容输入。
- Research Lead 要求形成 thesis path、必需证据、定向修复和写作顺序，不能只罗列 Evidence。
- Industry／Supply Chain 要求从关系图提出传导机制，但明确“图只产生假设，不能证明收入、利润或现金”。
- Risk 要求压力测试利润稀释、供应瓶颈和反证。
- Writer 要求按“判断—证据桥—机制—反方—WWC”组织，而不是把证据清单改写成报告。
- Verifier 要求检查数字 lineage、期间、来源权威和引用。

这些内容恰好覆盖 paired R1 的 AI 利润归因越界，因此不能把旧 Skill 视作无效文档。

### 3.2 已经过时的接入和对象

旧 Skill 依赖 `SpecialistMemolet`、ClaimCard v0.3、`assigned_task_card`、`method_runtime_pack`、旧 Exact-Value Ledger、静态 specialist 和“specialist 不调用工具”等接口。当前主线则使用 `ResearchObjective`、cell、`EvidenceRequest`、`QueryFacetPlan`、reviewed Evidence、NumericFact、FinanceToolContract 和 cell-local Judgment。

旧 Skill 不能原样复制回活动树；否则会恢复第二套角色、Prompt 和合同。正确处理是：

| 处置 | 旧内容 |
| --- | --- |
| 迁移为当前 `RoleMethodPack` | Lead、fundamental、industry/supply-chain、product、valuation、risk、writer、verifier、shared evidence boundary |
| 合并进确定性合同 | evidence sufficiency、coverage reflection、relationship universe、workflow |
| 不再作为模型角色 | renderer、旧 judgment aggregator；evidence operator 只有在以后确实模型化时再启用 |
| 继续留在归档 | 重复版本、文件名／正文版本漂移以及旧运行接口 |

这符合 PRD 的既定边界：不通过增加大量拟人化 specialist 来替代 EvidenceRequest、确定性数值引擎和 Evidence Gate。

## 4. 旧知识图谱审计

旧活动树曾实现并登记：retrieval/evidence spine、dimension/evidence portfolio、ProductIntelligenceGraph、product relationship graph、research graph 和 source authority mart；注册摘要记录了 6 个 GraphPack、16 个 SkillPack、6 个 MemoryPack 和 4 份注入计划。

这项历史结果只是 registry／injection-plan 范围通过。旧设计文档自己也说明：Lead selector、specialist required-pack gate、行为评测、真实 reviewer 样本、context lifecycle 和 exact/citation preservation 都只是 partial；没有证明 Workpaper 或最终研报质量。

仍可复用的设计包括：

- entity、business、product、metric、customer、supplier、capital、macro、claim、evidence、gap 分离；
- edge authority、provenance、as-of 和 evidence status；
- 精确 KPI、规格、deployment signal 和商业缺口分离；
- 按角色和研究单元压缩 GraphPack；
- 图只用于导航、作用域和机制假设，不能自动晋升为 Evidence 或 NumericFact。

不能直接复用的是旧 materialization、旧公司／期间数据、旧 digest 和旧 role binding。它们没有绑定当前 Case、cell、EvidenceRequest、NumericFact 或 typed comparable relation，且已进入 archive。

当前还存在一项明确的配置／运行时漂移：route policy 声明了 `typed_relationship_graph`，但当前 `hybrid_candidate_runtime` 只实际执行 BM25 和 Qwen dense。`graph_constraints` 被携带为元数据，没有图查询 handler。该问题归 S1，不得通过在 S3 Prompt 中塞入旧图数据掩盖。

## 5. 与 DeepSeek 新官方 Harness 的对照

2026-08-14 重新核对的官方 `deepseek-harness` 仍明确属于 developer preview；当前包版本为 `0.1.0-rc.5`。本次审计新增关注的不只是工具循环，而是：

- Skills：先只注入名称和描述目录，模型按需加载完整 Skill；支持 agent scope 分层和最近作用域覆盖；
- Context：所有 model-visible context 应能从 append-only session log 重建；运行时可显式注入上下文；
- Preset／agent scope：不同 agent 可以拥有独立 prompt section、工具和 Skill 视图；
- Subagent／workflow：可做有界编排，但 worker 隔离不等于安全或金融权威；
- Guard／compaction：可监控无进展循环并管理上下文，但不理解金融证据权限。

可借鉴的是接口模式，不是把整个开发预览 Runtime 导入 FIN：

1. FIN 先定义 provider-neutral、版本化、内容寻址的 `RoleMethodPack` 和 `GraphContextPack`。
2. 当前 Python loop 通过 native adapter 消费同一份 pack。
3. DeepSeek Harness 只做 shadow adapter：RoleMethodPack 注册为 scoped Skill／preset；GraphContextPack 通过只读、cell-scoped context tool 或显式 context injection 暴露。
4. 两条宿主路线必须产生相同的 pack digest、model-visible consumption receipt 和 replay 结果。
5. Skill 是方法，不是 Evidence；Graph 是导航／假设，不是事实；Evidence、NumericFact、身份、日期、引用和晋升权仍由 FIN 控制面拥有。

这避免两种错误：既不会继续把每次 DeepSeek 失败写进核心 Runtime，也不会因为官方 Harness 新增了 Skills／workflow 就把金融控制面交给通用框架。

官方依据：

- https://github.com/deepseek-ai/deepseek-harness
- https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md
- https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.md
- https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/context
- https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/preset
- https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/subagent
- https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/workflow

## 6. 更新后的最小下一步

下一项不再只是 comparable relation 和 source route 两个字段，也不扩成“恢复全部旧多 Agent 系统”。它收敛为一个零模型的 `Research Context Closure v1`：

1. 保留 RC-S2-003：建立同口径 NumericFact／typed comparable relation。
2. 保留 RC-S3-008：让 EvidenceRequest 的 source class 与真实 route availability 同源编译。
3. 只迁移 `value_capture` 当前单元需要的 `RoleMethodPack v1`，重点是收入—利润桥、mix／毛利支持、归因边界、反方和 WWC。
4. 只从当前 Case、reviewed Evidence、NumericFact 和来源绑定关系编译 `GraphContextPack v1`；不读取旧图谱事实，不重建全图。
5. 每次 pack 选择、压缩、注入和模型消费都保存 digest、选择原因、丢弃项和 receipt；capture replay 必须能重建同一 model-visible context。
6. 用 paired R1 immutable captures、DELL／MU／NVDA identity／period／cross-case／stale-pack mutation 做零调用证明。
7. 证明通过后，最多执行一条 Chat `value_capture` 单单元自然复验；不再做第二轮协议 pair。
8. 只有 L1 通过且相对旧 capture 的归因、机制、反方和 WWC 明显改善，才决定五单元运行并逐单元迁移其他 RoleMethodPack。

S1 的完整 typed graph handler、全公司图谱重建和 DeepSeek Harness shadow host 都不阻断这条最小单元复验；它们分别留在 S1 产品门和后续宿主一致性资格，不得再次膨胀当前修复包。

## 7. 当前结论

- 旧 Skill：方法内容多数仍有效，运行接口和版本治理过时；应选择性迁移，不应原样恢复。
- 旧图谱：对象／权限思想仍有效，物化数据与当前消费链已过时；不能冒充当前能力。
- 当前 canary：没有消费角色 Skill 或知识图谱，因此内容失败是“当前合同缺口＋模型判断”的混合结果，不能只归因于模型。
- 新 Harness：提供了更合适的 Skill／context／scope／log 接缝，但仍是开发预览；适合作为同合同 shadow host，不适合接管 FIN 金融权威。
- 当前最早可执行项：先完成有界、零模型的 `Research Context Closure v1`，再决定是否值得花费一次 Chat 单单元调用。

## 8. Research Context Closure v1 工作树实现结果

本轮没有恢复旧多 Specialist Runtime，也没有把归档 Skill／Graph 当作当前事实。实现收敛为一条当前合同链：

1. S2 在同一披露批次内保留当期和上年同季度／同 YTD 的可比 NumericFact；S3 只从这些端点编译 `REL::*`。比较词必须同时引用 relation 和两个端点，否则 fail closed。DELL 当前输入形成 10 条同口径关系；MU、NVDA 当前 mart 没有足够同口径端点，因此关系数保持为 0，系统不会补造同比。
2. EvidenceRequest 的 `requested_source_class`、可接受来源类型、可执行 route、intent mode 和禁止项由同一 branch 编译。当前没有真实商业／行业 Provider 的路线会从模型可见枚举中消失，不能再出现“模型被要求找行业数据、工具却只支持 SEC”的假可执行请求。
3. 只给 `CELL::value_capture` 注入 `ROLE_METHOD::VALUE_CAPTURE::V1`。它要求收入—利润桥、同口径比较、mix／毛利支持、归因边界、反方和 WWC；其他四单元没有借机迁移 Skill。
4. `GraphContextPack` 只从当前 Case、当前 reviewed Evidence、当前 NumericFact／typed relation 编译。DELL、MU、NVDA 的 value cell 只含本案主体节点和本案引用；归档图谱读取数为 0。它是导航／上下文，不具备 Evidence 或 NumericFact 晋升权。
5. 选择、压缩、注入和消费均形成 digest／receipt。模型提交 Judgment 时必须回传实际使用的 method、graph edge 和 relation refs；不存在的、跨案的或跨单元的引用会被拒绝。
6. paired R1 的 Chat／Responses 两份 immutable Judgment 已按原 digest 回放；它们因缺少当前 relation／method／graph 消费字段而同时被 v1.2 拒绝，旧失败没有被静默追认。三案例完整 fake 循环与 mutation 另覆盖 identity、关系端点、YoY 无 relation、method 数量、cross-case graph、不可用来源和 stale／归档上下文。当前全仓回归为 `276 passed`，compileall 通过，active baseline 为 `123 Python / 8 frontend / 10 Runtime resources / 0 forbidden reference`，secret scan 为 `6,536 files / 0 finding`。

这仍只是工作树工程结果，不是正式 fresh proof 或自然模型质量结果。下一门是先提交并推送这条实现链，再签发一次零网络／零模型 authority；只有正式 proof 复现相同三案例结果后，才允许唯一一次 Chat `CELL::value_capture` canary。五单元、Responses 重跑、Anthropic live 和其余 RoleMethodPack 迁移继续不在本轮范围。

## 9. Formal zero-call R1 authority 失败与处置

实现已在干净远端提交 `93d58d10...`，但 R1 authority 误绑 `bounded_finance_agent_loop_policy_v1_0`。该旧 policy 的并行上限为 1，而当前已经资格化的 mandatory read 是同 cell Evidence＋NumericFact 两个只读工具；因此 runner 在 single-cell fake 的第一步以 `finance_loop_parallel_tool_calls_exceeded` 终止。

R1 没有发生网络、模型、Provider、embedding、retry 或产品发布，也没有开始检验新 relation／source-route／method／graph 内容。失败 authority 与 terminal result 保持不可变。后续只允许签发 ATTEMPT-02，唯一差异是绑定已验证的 loop policy v1.1；不能修改 R1 后追认为通过。

## 10. Formal zero-call R2 result 投影失败与处置

R2 正确绑定 loop policy v1.1，DELL 单单元 fake 完成 3 step／4 tool receipts，五单元 fake 完成 10 step／15 receipts，三案例矩阵中的 DELL full-fake 也已完成 15 receipts。失败发生在把 `BoundedFinanceLoopResult` 写入三案例 proof 摘要时：runner 错把 digest 当作对象属性，而标准合同要求从 `as_dict()` 读取。

该处已改为 canonical dictionary projection。签发下一条 authority 前，已直接执行完整本地函数链：single=`3/4`、five=`10/15`；DELL／MU／NVDA full-fake 全部为 15 receipts；三案 identity／graph／archived-context／unavailable-route pollution 均为 0；paired R1 两份旧 Judgment 均被 v1.2 fail closed。R2 保持 immutable failed，ATTEMPT-03 只能绑定这一行投影修复后的干净提交。

## 11. Formal zero-call R3 结果

R3 绑定干净远端提交 `c6a97699...`，正式状态为 `zero_call_engineering_and_fresh_process_proof_pass`：

- 两个独立 fresh process 与主进程 normalized result 字节级一致；
- DELL 单单元为 3 step／4 receipts，五单元 fake 为 10 step／15 receipts；
- DELL／MU／NVDA 三案 full-fake 各 15 receipts；DELL 为 19 Evidence／25 NumericFact／10 same-basis relations，MU 为 14／14／0，NVDA 为 13／15／0；
- case identity、GraphContextPack、归档 Skill／Graph row、不可用 route 暴露均为 0；
- paired R1 的 Chat／Responses 旧 Judgment 均被当前合同拒绝，没有静默 salvage；
- network／model／Provider／embedding 均为 0，fake deliverable 未发布。

至此 RC-S2-003、RC-S3-008、RC-S3-009 的结构性部分具备 formal zero-call closure。它仍没有证明 DeepSeek 自然 Judgment 的 L1 或内容质量；下一门严格限制为唯一一次 Chat `CELL::value_capture` canary。Responses 不重跑，五单元和其他 RoleMethodPack 迁移仍等待 canary 后的 Owner 决策。

## 12. Formal zero-call R4 当前 Provider 容量复证

R3 的结构结论有效，但 authority 仍绑定旧 GA profile v1.0，其 `max_tokens=5000`；当前单单元 live runner 的容量资格要求是 GA profile v1.1 的 `max_tokens=16000`。因此没有把 R3 伪装成当前 Provider 容量证明，也没有直接放行付费调用，而是签发 ATTEMPT-04：实现、输入、合同、fake、三案例矩阵和 mutation 全部不变，只把 agent／strict／JSON 三份 Provider profile 更新为 v1.1。

R4 正式通过，两个 fresh process 字节一致，三案例污染仍为 0，DELL 仍为 19 Evidence／25 NumericFact／10 same-basis relations，MU 为 14／14／0，NVDA 为 13／15／0；唯一预期变化是 `standard_profile_max_tokens` 从 5000 变为 16000。network／model／Provider／embedding 均为 0。R4 不增加产品能力，只关闭“当前 profile 容量尚未被 clean proof 绑定”的资格缺口；下一门仍然只有一次 Chat `CELL::value_capture` 自然复验。
