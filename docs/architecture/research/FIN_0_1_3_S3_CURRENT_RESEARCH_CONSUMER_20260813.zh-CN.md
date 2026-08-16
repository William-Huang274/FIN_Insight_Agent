# FIN 0.1.3 S3 当前研究消费者

日期：2026-08-13
状态：`consumer_v1.4 / fixed_pack_and_dynamic_single_cell_accepted / five_cell_context_qualified / stable_five_cell_runner_and_remaining_nodes_successor_formal_zero_call_pass / natural_five_cell_pending / S3_not_accepted`

## 1. 为什么需要这条链

严格重定基后，活动树保留了研究 Planner，却没有一个当前、版本中立的消费者把 reviewed Evidence Pack 和 S2 NumericFact 变成研究判断、底稿与报告。归档中的旧九调用 runner 与单次 attempt 绑定，直接恢复会重新引入多份 Prompt、Validator、Renderer 和结果物化逻辑。

当前唯一主干因此是：

```text
保存的 Planner atoms
  → 当前 EvidenceRequest / S1-S2 受控执行
  → reviewed Evidence Pack + NumericFact + residual gaps
  → provider-neutral 五单元研究输入
  → 模型判断原子与引用选择
  → 本地确定性绑定事实、数值、日期、引用和结构
  → structured workpaper/report candidate
```

候选检索结果和 rejected Evidence 永远不能绕过 Evidence Gate 进入模型输入。

## 2. 模型与 Harness 的分工

模型可见完整的来源事实摘录和权威 NumericFact，并负责：

- 判断状态与置信基础；
- 支持证据、反方证据、数值事实和缺口的引用选择；
- 公司特定 thesis、经济机制、最强反方；
- 可观察的 what-would-change 条件。

Harness 负责：

- 公司身份、研究截至日和 Case/Pack digest；
- exact number、单位、期间、公式和 citation surface；
- 引用是否属于当前研究单元；
- 五单元覆盖、枚举、长度和无自由数字叙事门；
- 最终 workpaper/report 结构与 lineage。

Harness 不得生成或改写研究结论；模型也不得自由重写精确事实表面。这不是“本地超级拼装”，而是模型作判断、本地作可信渲染。

## 3. 已解决的结构问题

### 3.1 Reviewed source policy 与开放检索 policy 分离

Dell/TSM 官方托管 transcript 已经过人工 route、parser、对象编译和 Evidence Gate，因此可以作为 reviewed Evidence 被 S3 消费。`RC-S1-019` successor 还把它们加入 current S1 对象库，但只对需求、经营、价值捕获和供给执行等相关 slot 开放，并继续执行本案身份与关系方向硬约束；这不是全局白名单。Transcript 数字仍不获得 S2 NumericFact 权限。

### 3.2 request 级重复不能冒充多份经济证据

同一个 S2 事实可能被多个 EvidenceRequest 或 `quarter_discrete/fiscal_ytd` 标签重复暴露。原始受控结果有 45 个 request-level NumericFact；按公司、指标、数值、期间、单位和来源权威合并后为 35 个经济事实，再按每项指标的最新季度、最近财年或最新时点选择 25 个模型可见事实。request、period-role 和 source lineage 仍保存在控制面，不用于虚增模型证据数量。

### 3.3 模型容量由信息选择解决

第一版模型视图约 88,526 字符，主要由内部 ID、digest、request lineage、citation URL 和重复事实造成。旧 R1 模型视图为 48,380 字符；v1.1 successor 进一步把不可变事实目录与 cell-local interpretation view 分开，当前约 46,061 字符：保留来源原文、业务含义、claim boundary 和精确 NumericFact；隐藏只供审计的内部字段。没有通过随手放大上限掩盖信息架构问题。

## 4. 零调用 R1 结果

- 当前 DELL Pack：20 Evidence／14 gaps；
- 模型可见：19 Evidence，其中 5 条为已复核 transcript Evidence；
- NumericFact：45 request-level → 35 semantic unique → 25 model-visible；
- 模型可见 residual gaps：10；
- 研究单元：需求质量、经营表现、价值获取、现金转换、反方/WWC，共 5 个；
- fake 输出成功编译 structured workpaper/report preview；
- unknown Evidence ref、cross-cell NumericFact、自由数字叙事、缺失 cell 均 fail closed；
- 网络／模型／provider／embedding 调用均为 0，fake deliverable 未发布产品面。

R1 是脏工作树上的工程证据，已保留且未改写。绑定远端提交 `b4016469...` 的 R2 随后复现相同 research input 与 deliverable digest，证明这不是脏工作树偶然结果。

## 5. R1 后的停止规则

旧 clean R2 只证明 v1.0 的离线消费者；随后唯一一次 DeepSeek Pro 综合 canary R1 已失败，且永久保持失败。当前不得重放旧请求、补包 envelope 后追认，也不得恢复旧九调用链。

新的自然门必须满足：

- 先完成 v1.1 provider-neutral 合同的干净零调用复证；
- 再建立 DeepSeek GA profile 和四工具最小研究循环；
- paired canary 前另行签发 exact-once authority；
- 完整保存模型可见请求、最终 assistant 输出、调用参数、usage、finish reason、tool call 和 typed terminal；
- Provider 私有推理不得成为 Evidence 或金融事实；工具循环所需的 `reasoning_content` 只在受控传输上下文中回传；
- 不自动发布到 Workbench，也不宣称 S3 或 FIN 0.1.3 通过。

## 6. 自然 Canary R1 结果

唯一一次 DeepSeek Pro 调用完成 HTTP 与 exact JSON，并返回五个必需单元，但在 envelope、枚举、cell ref、Evidence role 和自由数量级表述上未通过合同；内容层也存在 AI 归因、现金归因和供应缓解过度推断。特别需要更正的是：model-visible contract 没有列出实际合法枚举，因此枚举失败包含项目责任；同时模型已经看见 claim boundary，仍作出多项越界因果判断，因此也存在真实的模型研究质量问题。

R1 不重试、不追认。下一 successor 必须让 Harness 注入本地 envelope、明列枚举、按 cell 嵌套 Evidence/NumericFact/Gap，并把证据用途改为 `support / limit / context`，再增加显式 inference authority。保存 R1 只用于零调用回放，不能成为新报告或训练 gold。

## 7. v1.1 结构 successor

v1.1 把模型提交面收敛为 provider-neutral 的最终判断合同，而不是一次性 Prompt 修补：

- 模型只提交 `cells`；`schema_version`、`research_input_digest` 和可信 residual gaps 由 Harness 注入；
- model-visible view 明列全部合法 status、confidence、evidence-use、inference 和 WWC direction 枚举；
- Evidence、NumericFact 和 gap 以 cell-local view 暴露，禁止跨单元引用；
- Evidence 使用从互斥的 support/counter 数组改为 `support / limit / context`；
- 每个判断显式声明 `directly_supported / bounded_inference / not_inferable`；
- 最终数字、身份、日期、引用和 remaining gaps 仍由本地确定性绑定；
- immutable R1 payload 与独立内容审计绑定回放，必须继续被拒绝，不能被 v1.1 静默“修好”。

当前聚焦测试为 25 passed；全仓复跑为 238 passed。绑定 HEAD/upstream `db1e9db43370e880b868aeb6c8fcf7402f62876f` 的独立 zero-call R3 已通过：0 网络／模型／Provider，successor user view 46,061 字符，六类 mutation 全部 fail closed，immutable R1 的五项内容 finding 与合同失败继续被拒绝，未 salvage、未发布。

## 8. DeepSeek V4 Pro GA 与官方 Harness 处置

2026-08-13 官方发布 V4 Pro 正式版，API 模型名仍为 `deepseek-v4-pro`。因此旧 R1 仅凭模型名和调用日期不能被可靠标注为 Preview 或 GA；后续 paired 只能声称比较“旧 R1 请求形态”与“新 GA profile／新合同”，不能伪称模型 build A/B。

FIN 采纳的官方约束：

- 标准 Chat Completions 地址为 `https://api.deepseek.com`；高度复杂 Agent 任务使用 thinking=`enabled`、reasoning effort=`max`；
- thinking 模式下 `temperature`、`top_p`、presence/frequency penalty 不生效，因此 GA profile 不再发送这些无效参数；
- thinking＋tool calls 的后续请求必须回传 assistant 的 `reasoning_content`，否则 API 会 400；
- strict function schema 需要 `/beta`、`strict=true`、所有 object properties required 且 `additionalProperties=false`；它仍是 Beta，只能独立资格验证；
- JSON Output 只作为 paired 基线，不能替代本地 schema 校验。

官方 `deepseek-ai/deepseek-harness` 当前是 developer preview，并明确可能产生破坏性变更。项目不整体引入其插件系统，也不把通用 coding harness 当金融事实控制面；只借鉴最小工具面、有界 step loop、事件/capture 可追溯和停止条件。参考版本固定为审计时 HEAD `47f943859bef60e4160492346772ded9b24f765a`，升级必须重新审计。

### 8.1 当前活动实现

当前活动树已经实现 provider-neutral 的四工具循环，而不是复制官方 Harness 或恢复旧九调用 runner：

- `read_reviewed_evidence_for_cell`：只读取指定研究单元已经通过 Evidence Gate 的 reviewed Evidence；
- `read_numeric_facts_for_cell`：只读取 S2 已绑定期间、单位、来源和 lineage 的 NumericFact；
- `submit_evidence_request`：只提交新的补证提案并通过当前金融内核、route policy 和 planning policy 编译；它不执行检索、不晋升候选，也不会因为模型提了请求就关闭 gap；
- `submit_research_judgment`：只提交判断原子、引用用途、推断权限、机制、反方和 WWC，再交给 v1.1 本地校验和确定性渲染。

默认循环上限是 24 step／24 tool calls、连续 2 次无进展即停止；五个 cell 各最多读取一次 Evidence、一次 NumericFact 并提交一次 Judgment，EvidenceRequest 总数最多 9。当前 v1.1 唯一允许的双工具 step 是同一 cell 的 Evidence read＋NumericFact read；其余工具仍为单调用。24 是安全上限，不是目标调用次数；旧 v1.0 fake 五单元为 15 step，v1.1 安全并行路径为 10 step／15 tool calls；含一条补证提案的单单元路径为 3 step／4 tool calls。

工具 Schema 由当前 Research Input 生成 cell-local enum，所有 object 都是 closed schema。没有 NumericFact 或 gap 的单元使用不可匹配占位约束，而不是生成非法空 enum。模型若提交未知 cell/ref、跨 cell 引用、重复判断、非法指标/关系方向或未完成所有必需 cell，循环都 fail closed。

thinking tool loop 所需的 `reasoning_content` 只存在于同一次受控运行的瞬时 continuation message；落盘的 request/response capture、receipt 和 terminal result 都会剔除 Provider 私有推理。工具参数、最终 assistant/tool 输出、usage、finish reason、capture ref 和 digest 仍完整保存。凭据和 Authorization 永不落盘。

DeepSeek 差异只存在于三个可替换 profile：标准四工具、JSON 对照和 `/beta` strict tool。三者都固定正式模型名、`thinking=enabled`、`reasoning_effort=max`，且不发送无效 sampling 参数；strict Beta 不会被当作核心金融合同依赖。

### 8.2 paired canary 实现边界

paired canary 没有新增第二套 runner。当前唯一 `run_s3_current_research_consumer_canary.py` 保留旧 R1 authority schema 的只读兼容，并为新的 GA paired authority 增加显式分支；两路继续共享当前 DELL 输入编译、capture-first Provider transport、本地 Validator、terminal result 和 exact-once Git boundary。

两路固定为 `CELL::value_capture`，因为该单元同时拥有 reviewed Evidence、权威 NumericFact 和未关闭的利润/归因 gap，能够检验模型“看见数字并分析”与 Harness“拥有最终数字/引用渲染”是否真正分离。JSON 与 strict 路的公司、问题、Evidence、NumericFact、gap、枚举和研究规则完全相同；只允许最终提交方式和 `null`／strict-string 空值表示不同，并生成归一化业务 payload digest。

DeepSeek V4 thinking 集成说明标记 `tool_choice` 不兼容，因此 strict 路不发送该字段，而是只暴露一个 `submit_research_judgment` 工具并要求模型调用。JSON 路出现认证、配额、断网或服务端故障会停止 strict 路；JSON 参数级 HTTP 400 不会掩盖 strict 独立资格。两路各最多一次调用、0 retry、0 fallback、0 tool execution，所有 terminal 均保存 capture ref；任何一条通过都不等于内容质量或 S3 通过。

官方资料：

- https://api-docs.deepseek.com/zh-cn/news/news260813
- https://api-docs.deepseek.com/zh-cn/guides/thinking_mode/
- https://api-docs.deepseek.com/guides/tool_calls/
- https://api-docs.deepseek.com/guides/json_mode/
- https://github.com/deepseek-ai/deepseek-harness

## 9. 更新后的执行顺序

1. v1.1 全量回放、mutation、全仓回归、active-baseline 和 secret scan：已完成。
2. 干净远端提交上的 v1.1 zero-call authority 与 R3：已完成，R1 保持失败、successor 合同可执行。
3. DeepSeek GA provider profiles、capture-first tool-step transport 与四个 typed tool：已在干净远端提交 `ae86d8bc...` 上实现。
4. 独立零调用 R1/R2：已通过。历史 v1.0 单单元 4 step、五单元 15 step；两次 fresh process 结果等价；no-progress、unknown tool 和错 cell 判断均 fail closed；EvidenceRequest 后 gap 仍 open，0 retrieval／promotion／network／model／Provider。R1 live 后发现的 v1.1 successor 将在新的 clean proof 中单独证明 3/10 step 与 4/15 tool-call 形状，不改写旧结果。
5. 单独签发 DELL 单单元 paired canary：`v1.1 JSON + thinking=max` 对 `strict final-tool + thinking=max`。
6. 选择可靠传输后，再执行 DELL 五单元有界循环；调用次数由真实步骤决定，但受总 step、工具预算和无进展停止条件约束。
7. 依次执行 L1、八维绝对内容质量、与 R1 同 Evidence Pack paired、qualified-human 验收。任何一项失败都留在 S3，不自动扩成下一产品版本。

## 10. GA 单单元 paired R1 结果与预算处置

R1 已在干净提交 `b8f335eb...` 上按 authority 执行。JSON control 与 strict final-tool 各完成一次 HTTP 200，0 retry、0 fallback；两路都在提交最终答案前以 `finish_reason=length` 结束。JSON 路 prompt=`3,796`、completion=`5,000`、reasoning=`5,000`；strict 路 prompt=`4,912`、completion=`5,000`、reasoning=`5,000`。两路可见正文与 tool call 都是 0。

因此 R1 不是 JSON/strict 合同失败，更不是金融内容失败；它没有产出可被合同或内容验收的 Judgment。首因属于项目 profile 容量标定：`thinking=max` 与 5,000 token 上限组合不足。网关此前把它记成通用 `content_empty`／`tool_step_empty`，后续已增加 typed reasoning-budget exhaustion 分类，但 R1 结果保持原样。

replacement 只允许使用同一业务 payload 和 versioned JSON／strict profile v1.1，每路 `max_tokens=16,000`、一次调用、0 retry、0 fallback。16,000 是针对本次单 cell 的受控容量，不是未来五单元循环的固定预算；五单元需要在 paired 通过后单独按实际步骤定标。若 replacement 再次用尽预算或出现新的 L1，停止并做阶段处置，不自动签发第三轮。

## 11. GA 单单元 paired R2 与核心传输选择

R2 继续绑定同一个 DELL `CELL::value_capture` 和归一化业务 payload digest。JSON control 使用 v1.1 16,000-token profile 后以 `finish_reason=stop` 提交可见 Judgment，本地合同、身份、引用、自由数字和 gap 门均通过；usage 为 prompt `3,796`、completion `7,380`，其中 reasoning `6,918`。这关闭了 R1 的项目 profile 容量问题，但不追认 R1。

JSON Judgment 使用四条本 cell reviewed Evidence，明确区分 support／limit／context，保留价格、销量与组合三条 gap，并拒绝把公司／分部指标冒充 AI 产品利润桥。与旧 R1 相比，它删除了“AI server margin 低于传统业务”和无证经营杠杆等越界。其明显不足是八条公司级 NumericFact 全未选择，故节点适用评分为 18/24，Q5 跨单元综合和 Q8 最终交付不适用；不得折算成完整八维研报通过。

strict Beta 在 R2 中没有取得 HTTP 业务响应，capture 只记录 `URLError`／status 0。由于 schema adherence 与内容均未被观察，项目既不能宣布 strict 不遵循，也不为可选 Beta 通道自动做第三轮 paired。JSON control 可作为非工具最终提交对照；本地 validator 和确定性 renderer 继续拥有最终权威。

完整五单元实际依赖标准 API Tool Calls，因此传输选择还差一个小而必要的资格门：使用 versioned 16,000-token 标准 profile，只运行 DELL `value_capture` 单 cell 四工具循环；必须至少真实读取 reviewed Evidence 与 NumericFact，EvidenceRequest 仍只记录提案，最终 Judgment 仍由 v1.1 本地合同校验。该门通过后才执行五单元；这不是新产品版本，也不是重开 strict paired。

### 11.1 标准 Tool Calls live successor

当前永久 canary runner 增加 provider-neutral bounded-loop authority 分支，没有按 R3/R4 新造 attempt runner。核心四工具仍只有 `bounded_finance_loop.py` 一份实现；runner 只负责 Git/authority 绑定、current input 编译、exact-once Provider step、capture、receipt 和 terminal materialization。单 cell authority 被硬绑定为 DELL `value_capture`，预算收窄为最多 6 step：Evidence read 1、NumericFact read 1、EvidenceRequest proposal 最多 3、Judgment 1。每个 cell 在提交 Judgment 前必须真实完成两类 read；该顺序和本次预算同时对模型可见，不能用直接提交答案伪装成 Agentic Research。

成功的每一步立即保存 receipt；中途 Provider 或本地校验失败时，公开 terminal 保留成功前缀、失败 phase/code、capture ref 和实际调用数，0 retry、0 fallback。完整 Judgment、工具返回和 provider step 存在受限 private result，公开结果不把未验收内容晋升为产品事实。standard profile v1.1 使用正式标准地址与 16,000-token 上限；strict Beta 保持停放。

同一 generic 分支未来可运行五 cell，但不能复用本次单 cell 决策：五 cell authority 必须绑定一份新的机器可读 scope decision，明确 `five_cell_live_authorized=true`，并且 cell 顺序必须等于当前 research input 的全部五单元。这阻止 runner 可复用性扩大当前权限。

### 11.2 标准 Tool Calls R1 与有界兼容 successor

标准 single-cell R1 在干净提交 `2aab623d...` 上取得 HTTP 200、`finish_reason=tool_calls`。DeepSeek 在第一步一次请求 `read_reviewed_evidence_for_cell` 和 `read_numeric_facts_for_cell`，两者参数均为当前 `CELL::value_capture`；这是正确且互不改变状态的 mandatory read pair。失败发生在项目边界：Provider 为每个 tool call 附带标准顺序 `index`，当前归一化器要求绝对三字段；核心循环又把 `maximum_parallel_tool_calls` 固定为 1。异常在 step receipt 前抛出，还造成公开 terminal 未引用已经保存的 response capture。

successor 不把这个结果固化成 DeepSeek 专用分支，也不放开任意并行。provider-neutral transport 只允许可验证的非负整数 `index` 并在归一化后剥离；核心策略只允许同 cell、不同 call id、名称集合恰为 Evidence read＋NumericFact read 的两个只读调用共存。EvidenceRequest、Judgment、重复 read、三工具或未知组合继续 fail closed。每个 tool receipt 必须拥有不会相互覆盖的 sequence identity，Provider 归一化失败也必须携带 capture ref。

R1 保持 immutable failed。实现、replay、mutation、fresh-process 和干净提交 proof 完成前不执行 replacement；replacement 仍只有 single cell、最多 6 次模型调用、0 retry/fallback。五单元权限不随兼容修复自动产生。

### 11.3 标准 Tool Calls R2 与合同编译缺口

v1.1 successor 的 fresh zero-call R3 通过后，唯一 replacement R2 在 clean upstream `6f9ed940...` 执行。第一步真实完成同 cell Evidence＋NumericFact 并行读取并保存两份 receipt，证明 R1 的 wire／并行／terminal 缺陷已关闭。第二步模型针对缺失 AI server unit volume 提出 shipments／compute capacity 补证，希望区分 volume-led 与 price-led revenue growth；该业务方向与 reviewed gap 一致。

R2 仍 terminal failed，但失败责任在项目 Tool Contract Compiler。`product_intents` Schema 只写“concise”，没有公开本地 120-char／数组上限；更深一层，Schema 分别暴露全局 facet enum 与 metric enum，没有表达 `facet → query family → allowed metrics` 依赖。模型选择 `pricing_and_mix` 加 shipments／capacity／orders／backlog 在 Schema 上可生成、在本地 route 上必然拒绝。单纯增大字符上限会立即撞到下一道门，故禁止字段级补丁。

successor 必须由同一 provider-neutral EvidenceRequest／route 合同编译 Tool Schema、validator、fake 和 repair feedback。合法但跨 family 的研究需求由本地拆成 facet-compatible atoms；proposal-only 的长度／路由不匹配可以返回 `rejected_not_executed`、保持 gap open 并给出安全的 allowed-family 提示，在原调用预算内由模型修正。身份、Evidence／NumericFact 权威、Judgment、引用和跨 case/cell 错误仍 hard fail。完成 R2 capture replay、四工具合同对齐、三案 fake 与 mutation 前，不允许第三次 single-cell live或五单元。

### 11.4 统一 Tool Contract Compiler 与 R2 replay

当前 successor 已把 Case、Cell、visible gap、Evidence Slot、facet、target owner/relationship、query family、metric route 和 proposal limits 收敛到唯一 `FinanceToolContract`。四工具的 Provider Schema、运行时验证和可修复提示都从该对象派生；不存在“Prompt 写 concise、本地另藏 120 字符”或“全局 metric enum 与 facet family 各自维护”的第二真值。

可修复范围只包含 proposal-only 的字段形状、facet、metric family、数量和长度。失败结果固定为 `rejected_not_executed`：0 retrieval、0 Evidence/NumericFact promotion、gap 继续 open，并返回当前 cell 的 allowed gap、facet→target、facet→metric 和长度预算。它仍消耗一次已发生的模型/tool step，不能伪装成免费 retry。跨案 target、跨 cell、Evidence/NumericFact/引用、Judgment 和身份错误不降级，继续 hard fail。

绑定干净远端提交 `17bb0c5a...` 的正式零调用 replay 已把 immutable R2 的真实长 intent／错 family proposal 放回当前循环：该动作被拒绝后，一个合法 `pricing_and_mix + average_selling_price` repair 在同一预算内被记录，最终 Judgment 完成；4 step／5 receipts，只有 1 个有效 proposal。DELL／MU／NVDA 的跨案 target mutation 全部 hard fail。proof 同时绑定当前 Runtime Registry、Evidence Pack、合同、实现与历史 captures，network/model/provider/embedding 均为 0。

### 11.5 Chat／Responses／Anthropic 的协议边界

核心金融循环只处理一套 canonical messages、tools、tool calls 和 tool results。外层允许三个版本化投影：

- Chat Completions：当前 control，继续传递 thinking-mode 所需的瞬时 `reasoning_content`；
- Responses：主候选，采用 stateless 全历史输入和 `function_call/function_call_output`；Provider reasoning output item 只在同一 loop 内存继续传递，落盘前删除；
- Anthropic Messages：只做 schema/transcript shadow，当前 dispatch 明确拒绝 live。

DeepSeek Responses 当前不支持 `previous_response_id`、conversation/store 等有状态能力，并会忽略 `max_tool_calls`／`parallel_tool_calls`；Runtime 因此禁止发送这些“看似有控制力、实际无效”的字段，工具预算、串并行安全和 no-progress stop 始终由本地循环执行。标准四工具仍使用非 strict schema；DeepSeek strict tool Beta 不支持本合同使用的全部长度/数组约束，继续停放。

下一次自然门不再是“第三次 Chat 修补”，而是同一 DELL `value_capture`、同一 Evidence Pack/NumericFact、同一 canonical tools 的 Chat control 对 Responses candidate。两路各自 exact-once、0 retry，失败都保存完整 capture；协议合同通过后仍须审查研究机制、反方、WWC 和数字使用。Anthropic 不参加本轮。五单元必须等 paired 结果后的新 scope decision。

官方协议依据：

- https://api-docs.deepseek.com/guides/responses_api
- https://api-docs.deepseek.com/guides/anthropic_api
- https://api-docs.deepseek.com/guides/tool_calls/

### 11.6 Chat／Responses paired R1 与新的最早责任层

paired R1 绑定同一 DELL `value_capture` research input digest `6505a58e...89b4c` 和同一 canonical FinanceToolContract。Chat 与 Responses 都完成 5 个 Provider step／6 个工具 receipt：同 cell Evidence＋NumericFact read、三个 open-gap EvidenceRequest 和一个 Judgment。两路均 0 retry、0 fallback、0 retrieval、0 publication；Responses 的 stateless full-history continuation 因此已真实资格化到“可完成当前单 cell loop”，不再只是 schema shadow。

该结果同时证明 transport pass 与 financial-content pass 必须分开。两路 Judgment 都选择 FY2027 Q1 与 FY2026 全年 NumericFact，并生成“同比上升／利润率扩张／毛利压缩”等比较关系。reviewed source table 包含上年同期数字，因此方向可能成立；但当前 S2/S3 没有把 same-cadence comparator、relation operation 和 lineage 绑定到 narrative atom。存在的 NumericFact ref 不能证明模型使用了正确比较期。后续 comparative language 必须引用 typed relation，而不是由模型或 renderer 从两个任意期间自行拼接。

EvidenceRequest 还有一项与 RC-S3-007 不同的新缺口。当前统一合同已经拥有 facet、target、metric 和长度，但 `EvidenceRequestBranch` 没有 source class／route availability。当前单位量 gap 提示可找行业出货数据，模型也确实请求行业数据；本地编译结果却只允许 10-K／10-Q／8-K。proposal 被记录不等于其研究意图可执行。后续合同必须让 source class 成为显式枚举，并确保 gap supplement direction、objective allowed sources 和实际 adapter route 同源编译。

内容层仍保留独立模型责任：Chat 加入未绑定的 supply-allocation 利润机制；Responses 把存储、定价、传统服务器、配置和规模共同驱动的结果表述为“来自 AI server cycle 的真实经营杠杆”。Harness 应阻止无 relation／无 source route 的结构越界，但不能替模型代写更谨慎的经济结论。

当前处置是：Chat 保留 provisional primary；Responses 只晋升为 live-compatible shadow/candidate，因为它总 token=`102,176`、耗时约 `267s`，高于 Chat 的 `74,885`／`169s`，且没有形成内容硬门优势；Anthropic 仍 shadow。五单元继续 blocked。下一项是零调用 comparable-period relation＋source-route contract 包，通过后最多一条 Chat 单 cell 复验。

## 12. 角色 Skill、知识图谱与当前官方 Harness 重新资格

### 12.1 当前 paired 没有消费旧角色方法或图谱

两路保存的 model-visible request 只有通用 bounded financial analyst 指令、四个金融工具和 cell-local Evidence／NumericFact／gap。当前 Runtime Registry R11 的 10 个资源中没有 SkillPack 或 GraphPack；请求中也没有 `method_runtime_pack`、specialist rubric、ProductIntelligenceGraph 或经济关系 GraphPack。`value_capture_specialist` 只作为请求者角色标签出现，不是已消费的方法包。

因此 paired R1 可以证明 Chat／Responses 的协议续接，但不能证明此前角色 Skill 或知识图谱无效。它暴露的是三类责任的组合：S2 comparable relation 缺口、S3 source-route／研究上下文缺口，以及模型自身的过强因果表述。

### 12.2 旧资产的可迁移边界

旧 fundamental、industry/supply-chain、product、valuation、risk、lead、writer、verifier 和 shared evidence boundary 方法仍有价值，尤其旧 fundamental 已明确禁止在缺少 mix／gross-margin 支持时把 AI server revenue growth 写成 margin improvement。旧运行接口则依赖 SpecialistMemolet、ClaimCard v0.3、静态 specialist 和旧 ledger，不能原样恢复。

旧图谱的 entity／product／metric／customer／supplier／claim／evidence／gap 分层、edge authority、as-of 和 role-scoped GraphPack 思路仍可复用；旧物化数据、digest、公司期间和 role binding 已归档，不能作为当前事实。当前 route policy 虽声明 `typed_relationship_graph`，Runtime 还没有执行 handler；该配置／实现漂移归 S1 产品门，不用旧 GraphPack 在 Prompt 中伪装关闭。

### 12.3 DeepSeek Harness 只作为可替换宿主接口

旧的 Harness 审计固定于当时 HEAD，只覆盖最小 loop。2026-08-14 对当前官方开发预览版 `0.1.0-rc.5` 的重新核对表明，它现在提供按 agent scope 分层的 Skill registry、先目录后按需加载的 progressive disclosure、可重放 context injection、preset、subagent、workflow、guard 和 compaction 接缝。

FIN 只采纳这些接口模式：先定义 provider-neutral、版本化和内容寻址的 `RoleMethodPack`／`GraphContextPack`；当前 Python loop 使用 native adapter，官方 Harness 以后只作为 shadow adapter。无论宿主是哪一条，必须记录相同的 pack digest、选择／压缩理由、model-visible injection 和 consumption receipt。Skill 永远只是研究方法，Graph 永远只是导航／假设；Evidence、NumericFact、身份、日期、引用和晋升继续由 FIN 控制面拥有。

官方依据：

- https://github.com/deepseek-ai/deepseek-harness
- https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md
- https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.md
- https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/context
- https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/preset

### 12.4 更新后的执行门

下一结构包改名为 `FIN_0_1_3_S2_S3_RESEARCH_CONTEXT_CLOSURE_V1`，但范围仍然有界：

1. S2 提供同口径 prior comparator 或 typed relation；
2. EvidenceRequest 显式编译 source class 与 route availability；
3. 只为 `CELL::value_capture` 迁移最小 `RoleMethodPack v1`；
4. 只从当前 Case、reviewed Evidence、NumericFact 和受控关系编译 cell-scoped `GraphContextPack v1`，不恢复旧图谱物化；
5. capture replay 和 DELL／MU／NVDA mutation 证明 pack 可重建、无跨案／错期／stale digest 污染；
6. 通过后最多一条 Chat 单 cell 自然复验，Responses 不重跑，Anthropic 不进入 live；
7. 只有 L1 和同输入内容增益同时成立，才签发五单元 scope decision 并逐单元迁移其余 RoleMethodPack。

完整 typed graph handler 留在 S1，官方 Harness shadow host 留在宿主一致性资格；两者都不能膨胀当前单单元修复包。完整审计见 `docs/worklog/fin_0_1_3_s3/018_role_skill_graph_and_deepseek_harness_requalification.md`。

### 12.5 Research Context Closure v1 当前实现合同

当前 successor 使用 consumer policy v1.2，并新增以下 provider-neutral 合同：

- `NumericRelationCard`：只允许同 ticker、同 fiscal cadence、同单位和同语义指标的 current／prior 端点；本地计算绝对变化、百分比或百分点变化。模型可见精确数字不减少，但比较叙事必须引用 `REL::*` 和端点 NumericFact。
- `EvidenceRequestBranch`：source class、acceptable source types、executable routes、intent mode、query facet／typed metric family 和 forbidden terms 同源编译。policy 声明不等于 route 可用；只有当前 Runtime 能实际执行的 route 才进入模型枚举。
- `RoleMethodPack`：当前只存在 `ROLE_METHOD::VALUE_CAPTURE::V1`，且只绑定 `CELL::value_capture`。pack 是研究方法，不是 Prompt 文案集合，也不拥有事实权威。
- `GraphContextPack`：从当前 Case、reviewed Evidence、NumericFact 和 typed relation 即时编译；禁止读取归档 materialization，禁止跨 Case，禁止将 edge 当成 Evidence。
- `ResearchContextReceipt`：记录选择、压缩、注入和消费。最终 Judgment 必须提交实际消费的 `method_step_refs`、`graph_edge_refs` 和需要时的 `numeric_relation_refs`。

DELL 当前可见 19 条 Evidence、25 个 NumericFact 和 10 条同口径 relation；MU 为 14／14／0，NVDA 为 13／15／0。后两案的 relation=0 是正确的 typed gap，不是失败：当前资料没有足够端点时，模型不得生成同比／扩张／压缩关系。三案 full-fake 均完成 15 个工具 receipt，case identity／graph pollution／archived context／unavailable route exposure 均为 0。paired R1 的 Chat／Responses 旧 Judgment 也按 immutable result 回放，并因缺少 v1.2 的 relation／method／graph 消费字段而 fail closed，不能被新代码静默追认。

当前实现通过 277 项全仓测试，并先由 formal zero-call R3 完成结构复证，再由 R4 在不改变实现和研究输入的前提下绑定当前 16,000-token GA profile；两个 fresh process 和三案 full-fake 均通过。结构门与当前 profile 容量门现为 pass；自然内容门仍只允许一次 Chat 单单元复验。完整 typed graph retrieval handler 仍归 S1；五单元运行和其他 RoleMethodPack 迁移仍需后续独立决策。

单次复验不能复用历史 disposition。当前 runner 只在 scope decision 同时绑定 R4 result digest、DELL、`CELL::value_capture`，并明确关闭 Responses、五单元和其他 RoleMethodPack 迁移时，才接受新的 Chat authority。这个校验把 Owner 本轮“先做 1–6、暂停第 7 步”的边界落实到了执行代码，而不只存在于聊天或文档。

该唯一 Chat R1 已消费：第一步正确读取 Evidence＋NumericFact，第二步含完整研究上下文的请求在约 175 秒后发生 `IncompleteRead`。没有 Judgment，因此 L1 与八维内容均不可评，不能用 R4 结构通过替代自然内容通过。项目 transport 也暴露了 capture 缺口：generic exception 分支没有保存 `IncompleteRead.partial` 与已经可见的 HTTP metadata。任何 replacement 都必须先独立处置该 capture/transport 问题并重新签发，不能自动重试。

### 12.6 IncompleteRead 原始响应留存合同

当前 successor 把网络终局统一为一份 provider-neutral capture 合同，普通 Chat 与 Tool Calls 不再各自维护异常分支：

- body read 前先冻结 HTTP status、安全 header、Content-Length 和 Provider request id；
- `IncompleteRead.partial` 只以原始 SHA-256／字节数作为不可变身份；只有它仍能完整解析为 JSON 时，才允许在移除 Provider 私有 reasoning 后保存业务可见结构；
- malformed partial 永不保存明文，只保存 redacted placeholder、长度和 digest；
- incomplete body 即使恰好是合法 JSON，也不得进入 contract parser、Tool executor、Evidence、NumericFact、Artifact 或重放输入；
- 不提供自动 retry、partial continuation 或跨 attempt 拼接。replacement 必须使用新的 Run／Attempt／authority；
- status=0 只表示连响应 metadata 都未取得的传输失败，不再用来覆盖已经取得 HTTP 响应的断流。

这项修复提高的是失败可追溯性和边界可靠性，不改变模型看到的 Evidence、NumericFact、RoleMethodPack、GraphContextPack，也不直接提升研报内容。旧 R1 已丢失的 partial 不可恢复；其 terminal result 与旧 capture 必须保持不可变。

该合同已由 formal zero-call replay R1 绑定干净提交 `a9578878...` 通过：两类 partial mutation 都是 1 attempt／0 retry，两个 fresh targeted process、全仓 280 tests、compileall、active baseline 和 secret scan 均通过。该结果只关闭 capture 可观测性门；replacement Chat 仍需新的 scope decision／Run／Attempt，且运行后仍必须单独进行 L1 与八维内容验收。

replacement gate 不复用旧 Research Context Chat decision。新 decision 必须同时绑定 R4、RC-S3-012 replay 和 immutable R1 result，并显式声明这是新 attempt 而不是 retry；runner 会重新验证 safe JSON partial 与 malformed partial 都不可 contract parse／business promotion。只有 DELL `value_capture`、Chat-only、0 retry／fallback 且所有扩大项关闭时才放行。该 gate 已通过全仓 281 tests；live authority 仍必须在 gate 提交并推送后的干净 HEAD 上另行签发。

### 12.7 replacement Chat R2：transport 恢复、因果门仍失败

新的 R2 authority 绑定干净 gate 提交 `8ce05106...`。真实循环完成 5 step／6 receipts，0 retry／fallback／external retrieval／embedding／publication。五份 HTTP response 均完整，capture-first 审计为 `5/5 status=200`、`5/5 body_complete=true`、`IncompleteRead=0`、私有 reasoning 明文 finding=0；这构成修复后的自然 transport 证明，但不改变旧 R1 partial 已不可恢复、历史断流来源仍未知的事实。

模型正确使用本案 4 条 reviewed Evidence、8 个 NumericFact、4 条 same-cadence NumericRelation、6 条 RoleMethod step 和 1 条当前 Graph edge，并把 ASP、unit volume、price-volume-mix bridge 三条 request 保持为未执行提案。关系端点、期间、来源 route、gap authority 和 context receipt 均通过。

最终内容仍违反 `METHOD::VC::CAUSAL_BOUNDARY`：公司／ISG 的多因素利润改善被升级为 AI server surge 已转成利润，且“semi-fixed cost base”没有 Evidence／NumericFact／relation／edge 绑定。模型自己的 counterargument 已承认 product profit line、ASP、unit、PVM bridge 不存在，这使强 thesis 与其证据边界内部冲突。当前 L1 因果归因 fail；单节点诊断为 18/24，正式八维报告不评分。五单元、其他 RoleMethodPack、qualified-human 和 S3 product acceptance 均未授权。

因此当前最早责任层仍在 S3 judgment authority，而不是再次修改 transport、S1 补源或增加 Prompt 长度。若继续，应先用零模型把 `claim_scope`、`financial_scope`、`causal_bridge_authority` 和 abstain／bounded wording 变成可校验合同，并把 R2 保存 Judgment 加入负向 replay；不能继续用自然调用逐句试错。

## 13. 片段分析与交卷的数值表面合同

片段链必须区分两个合法但不同的动作：分析节点可以读取并讨论 reviewed Evidence、NumericFact 和 source-bound QF 中的原始数值或文字区间；交卷节点的 model-owned atom 不能复制这些 authoritative surfaces，只选择 `NUM/QF ref` 并写不带值的判断。Harness 随后在 atom 外按 ref、期间、单位、来源和 qualifier 确定性渲染。这个边界不减少模型的分析信息，也不允许 Harness 代写结论。

FFJ-R1 暴露了投影缺口：完整 consumer 已有上述规则，但 fragment context v1.0 没有带入；submission system 只禁止“新增数字”，Tool Schema 只禁止 digits／refs，本地 Validator 却同时禁止 verbal numeric band。模型选择正确的 Dell 产品目标关系、Evidence、QF 和 management-only 权限后，仍因复制“中个位数”而失败。该结果保持不可变，不能删词追认。

projection v1.1 现在将同一 structured surface contract 编译到三个 fragment context、Tool Schema、submission system 和 Validator。Authority v1.1 还绑定旧失败 result／assessment，防止绕过失败另发 attempt。零调用证明同时要求两条：保存 R1 replay 继续失败；合规 fake 的 atom 不带区间，而最终 deliverable 仍展示该 QF surface。只有两条同时成立，才能证明这是权威分层而不是信息删除。

## 14. Relation Evidence Role 与片段／终局责任边界

FFJ-R2 证明 `required_evidence_refs` 不能继续同时表达“必须直接支持关系”和“只是帮助理解关系的上下文”。模型已经正确把 Dell 法说标为 support、把宽泛 8-K 标为 context；旧 relation card 却要求二者都以 support 出现，导致一个金融上保守的 mechanism 被合同拒绝。该失败属于项目关系合同，不属于 Provider 指令遵循或模型研究能力。

当前 v1.2 采用显式角色合同：

- `required_support_refs` 只列出缺失后便无法成立该 relation 的直接支持材料；
- 其他可见 Evidence 可以由模型选择为 context 或 counterevidence，但 Harness 不得自动晋升角色；
- 只提供 context、缺少 required support 的片段必须继续 fail closed；
- thesis、mechanism、counterargument／WWC 分别按自身 relation 的 `inference_authority` 验证，不允许把 thesis 的全局 status 提前套给其他片段；
- 所有片段通过后，canonical terminal compiler 才按最保守原则聚合 status、claim scope、financial scope 和 causal bridge authority。

保存的 R2 Tool Calls 在 v1.2 下原样 replay：thesis 与 mechanism 均通过，8-K 继续保持 context；context-only mutation 仍以 `finance_loop_micro_required_authority_missing` 拒绝。最终 fake Judgment 被保守汇总为 `bounded_support / bounded_inference / multi_scope / multi_scope_financial / multi_driver_context_only`。这项设计的目的不是让更多模型输出“过门”，而是避免把真实上下文伪装成直接证据，同时让片段责任与最终报告责任各归其位。

该关系角色合同属于 provider-neutral 金融控制面，Chat／Responses／Anthropic 投影必须共享；不得为 DeepSeek 或某次 attempt 增加特殊分支。零调用 closure 只授权一个 fresh FFJ-R3，不能代替自然完整 Judgment、动态检索、五研究单元、异质泛化或 S3 产品验收。

## 15. 动态 ClaimRelation 投影与安全 abstain

fixed-Pack ClaimRelation 模板不是动态研究的默认权限清单。EvidenceRequest 执行后，Runtime 必须以本轮 request-scoped reviewed Evidence、NumericRelation 和 typed gap 为输入，重新投影当前单元可提交的关系：

- 任一 required Evidence、QF、NumericRelation 或 gap 不可用时，对应关系整体移除；不得因它存在于固定 Pack 模板而继续暴露给模型。
- 动态投影只能删除权限，不得创建 Evidence、NumericFact、日期、身份、来源或因果桥。
- 若删除后没有关系可承担 `thesis_atom`，只有已经存在且完整绑定 typed gaps 的 `bridge_unavailable` 可以临时承担 thesis；其 inference/status 同时收窄为 `not_inferable / insufficient_evidence`。
- 该 gap-only thesis 只是让模型能够诚实交卷，不是 Harness 代写观点，也不能与 `bounded_support` 或正面归因组合。
- analysis／submission／Validator／Renderer 继续消费同一个关系卡；Chat、Responses 与其他 Provider 只做外层协议投影。

当前 DELL SEC-only 零调用 successor 删除了依赖 transcript 的 `PRODUCT_TARGET` 与 `MULTI_DRIVER_CONTEXT`，只保留 `COMPANY_MARGIN_OBSERVATION` 和 `PROFIT_BRIDGE_GAP`。后者是唯一 thesis 出口且只能 abstain；candidate promotion 仍为 0。该结构通过不代表自然 planner 或动态 Judgment 已通过。

## 16. 动态 micro-Judgment 的 request-scoped 消费合同

动态关系面可编译不等于三片段 Runtime 已安全消费它。formal v1.2 进一步冻结以下 provider-neutral 规则：

- fixed-Pack 与 dynamic 使用独立、显式 policy mode；半切换或用 fixed-only policy 消费 dynamic input 必须拒绝；
- cell-level `allowed_evidence_refs` 只能来自与该 cell Evidence Slot 相关的本轮 EvidenceResponse，不得从 case-level reviewed Pack 或其他请求补齐；
- GraphContext edge 的全部 supporting Evidence 都必须属于同一 request-scoped 集合，否则删除；若没有合格 edge，minimum edge requirement 同步收窄，不能保留陈旧最低数量；
- 每个 fragment 按自己的 ClaimRelation `inference_authority` 判定局部 status，terminal compiler 才做跨片段最保守聚合；
- abstaining thesis 对终态形成上限，后续 mechanism／counterargument 只能补充边界，不能升格结论。

这一合同关闭的是动态 Judgment 集成安全，不是研究内容能力。formal v1.2 的 DELL controlled fragments 能形成完整终态与 deliverable，但终态只能是 `insufficient_evidence / not_inferable / bridge_unavailable`；模型、Provider 和外部网络调用均为 0。自然 planner、自然 Judgment、动态 Agentic Research、五单元和三案例泛化仍必须由后续独立 live 与内容验收证明。

## 17. Reviewed source 同步后的 S3 输入边界

`RC-S1-019` 关闭后，动态 S3 不再需要在 SEC-only 与 current reviewed Pack 之间做临时二选一。普通 EvidenceRequest 可以执行当前 S1，并把已被本案 reviewed Pack 精确复核的 Dell transcript 候选回接成 EvidenceResponse；未审候选仍只返回 candidate／typed gap，0 自动晋升。

formal Truth Spine v1.4 已在零模型下证明：DELL demand 请求自然命中 Dell transcript page 3；TSMC transcript 只在关系方向匹配时出现；跨 Case、重排、未审文本注入、日期漂移、非法晋升、thesis 越权和未绑定期间关系全部 fail closed。这个结果是工程门，不是自然五单元内容门。

五单元前仍需两个前置动作：第一，做有限 S2 回归，确认新增 transcript 只提供 source-bound QualitativeFact／Evidence，不生成精确 NumericFact；第二，为其余四单元逐一迁移最小 RoleMethodPack 和只从本案当前 Case／Evidence／NumericFact／typed relation 编译的 GraphContextPack。不得恢复旧图数据，也不得把五份 Pack 拼成重复长 Prompt。

## 18. 稳定五单元自然执行器

五单元不能把单单元 runner 机械复制五次。稳定执行器采用一条共享的自然 planner／当前 S1／S2 路径，再按 cell-local 权威分别执行五组“分析草案＋严格交卷”。某个单元失败后，runner 仍继续运行其余单元，以便一次 attempt 暴露完整问题面；失败单元的输出不进入业务判断。只有五个单元全部通过本地 Judgment 合同后，才允许一次模型自有的跨单元分析和一次严格综合提交。

Harness 不生成研究结论。它只校验模型选择的 Evidence／NumericFact／NumericRelation／gap、绑定身份和期间，并在模型完成综合后确定性渲染精确数字、引用和关系。综合合同禁止自由数字、未知引用、自连接和未由五个已验证单元选择的材料。私有 full result 保存模型可见输入、原始最终输出和逐阶段失败；公开结果只保留 capture ref／digest／usage／失败码及通过状态，不保存模型文字、Tool 参数或私有 reasoning。

当前 DELL 五单元 objective 另建新版本并显式允许已审 `EARNINGS_CALL_TRANSCRIPT`；旧 SEC-only objective 保持不可变。预算上限为 13 次模型调用：1 次规划、5 次单元分析、5 次单元交卷、1 次综合分析和 1 次综合交卷，0 retry／fallback／协议切换／外源网络／candidate promotion。13 是本次完整案例的可审计上限，不是未来产品固定调用次数。

工程回归已证明：成功路径恰好完成 13 步并编译内部报告；任一单元 Tool 失败时，后续单元仍执行，综合跳过，partial terminal result 仍完整物化；跨单元上下文 receipt 已收窄到当前 cell。正式零调用 proof 和 clean/synced authority 随后均通过。

自然 DELL 五单元 R1 已执行，但在任何单元 Judgment 前因 consumer capacity 合同矛盾终止。Planner 与当前 S1/S2 均成功；`CELL::value_capture` 的合法 route 同时需要 revenue、gross_profit、gross_margin、operating_income、operating_margin 五个指标，same-cadence selector 对每个指标保留当期和上年同期，因此最小完整原子视图为 10 条 NumericFact。policy v1.3 的静态上限 8 与该上游合同不相容。该失败归 `RC-S3-031`，不属于 Provider 内容、网络、S1 检索或 S2 数值正确性。

v1.3 与 R1 必须保持不可变。successor 只能建立 policy v1.4，显式绑定该五指标双期间原子容量，并证明：10 条合法视图通过、重排不改变选择、同口径 pair 不被拆分、额外第 11 条非法／重复／跨槽项目 fail closed。随后直接重放 R1 的 immutable planner 与 controlled plan；只有五个 cell 输入、消息、Tool Schema 和综合前置条件全部零调用通过，才可由同一个稳定 runner 复用已成功的 Planner/S1/S2，只运行剩余 12 个自然节点。独立 L1、八维内容质量、paired gain 和 qualified-human 验收继续待完成。

policy v1.4 和 R1 prefix replay 已满足上述容量门；稳定 runner 现在用同一实现支持 remaining-nodes successor，而不是复制 attempt runner。successor authority 不含 planner attempt，只允许五个分析、五个交卷和两次综合；运行时会从 R1 私有终态重新验证 planner、controlled plan、current Pack、S1/S2 结果和失败码，再用 v1.4 重新编译 research input。任何 prefix、Pack、policy 或 digest 漂移都在 Provider 前拒绝。

正式 Project OS 回归还发现 scope decision 起初漏写 `evidence_mode`，而通用 preflight 终态会读取它。当前 decision、Project OS validator 和 runner 已统一要求 `immutable_dynamic_R1_planner_current_S1_S2_prefix_no_new_evidence`，避免“schema 接受但结果物化报错”。两次独立相关测试均为 `83 passed`，全仓 `420 passed`；该工程门只授权 clean/synced 后一个 fresh successor authority，不证明自然金融 L1、内容质量、综合、泛化或发布。

## 19. R2 局部成功、紧凑分析投影与节点级恢复边界

remaining-nodes successor R2 已真实执行。它没有重跑 Planner 或当前 S1/S2，共尝试 7 次模型调用：`CELL::demand_quality` 与 `CELL::operating_performance` 完成分析和严格交卷；`CELL::value_capture`、`CELL::cash_conversion`、`CELL::counterevidence` 在分析阶段用尽 8,000 completion token，综合因此未执行。三次失败均取得 HTTP 200，0 retry／fallback／外源网络；其中两次隐藏推理占满全部预算且没有可见草案，另一次只留下被 `length` 截断的草案。R2 与两个有效 Judgment 均保持不可变。

两个有效单元没有发现新的金融 L1。需求质量单元把订单、AI server revenue 与 backlog 视为公司自述的可观察需求链，同时保留提前锁货、客户准备度、组件切换和订单到出货非线性；经营表现单元只在公司整体口径判断收入、利润和现金改善，并明确拒绝在缺少产品利润桥时把改善直接归因于 AI server。它们只能算局部研究结果，不能冒充完整五单元报告。

R2 的最早责任层是共享的 S3 model-visible analysis projection，而不是 S1/S2、Skill、Graph、网络或严格 Tool submission。旧分析请求同时携带交卷 schema、重复的 Evidence／NumericFact 目录和完整 route 诊断；隐藏推理和可见草案又共用同一个 completion budget。处置不能简化成“把 8,000 改成 16,000”：当前实现先从 canonical consumer contract 编译一份 analysis-only 投影，保留全部 Evidence、NumericFact、same-basis NumericRelation、RoleMethodPack、GraphContextPack 和 typed gap，只删除本步骤不可执行的交卷 schema及传输诊断，并把 gap route 压缩成决策所需摘要。DeepSeek 的 16,000／max-thinking 只存在于可替换 profile，用来验证紧凑投影是否给自然分析留下足够 headroom；它不是核心金融合同的新上限。

节点恢复仍使用同一个稳定 runner。Project OS 可以精确绑定本次 R2 的两个成功节点、三个失败节点和失败码；执行循环本身从 fresh authority 的 `reused_cell_ids`／`remaining_cell_ids` 读取恢复清单，重新用当前 research input 验证被复用的原始 Tool arguments 与 Judgment digest，然后只给剩余节点分配 attempt ID。它不是 R3 专用 runner，也不允许把历史失败改写为成功。

下一工程门必须同时证明：

1. 五个 analysis-only 投影的全部 authority ref 集合与 canonical consumer 一致；
2. submission schema 与动态 transport diagnostics 不再出现在分析视图；
3. 两个已验证 Judgment 被复用且不产生新模型调用；
4. 只有三个失败单元和一次综合可产生 8 个 fresh model call；
5. fake 全链仍要求五个单元都通过后才允许综合；
6. R2、capture 和失败评估保持不可变，0 retry／fallback／新 Evidence／publication。

只有该零调用门和 clean Project OS preflight 通过，才能签发一次 partial successor。若同类 hidden-reasoning／visible-output budget failure 再次出现，不再自动增加预算或新增 capacity patch；应转为模型 profile、分析动作面或提交职责的项目级选择。若运行成功，后续仍须独立完成五单元金融 L1、八维绝对内容质量、同输入 paired gain 与 qualified-human 内容验收，才能讨论 MU／NVDA 和异质留出案例。
