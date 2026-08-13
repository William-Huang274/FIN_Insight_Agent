# FIN 0.1.3 S3 当前研究消费者

日期：2026-08-13
状态：`v1.1 clean zero-call engineering pass / historical R1 remains failed / GA four-tool loop clean zero-call pass / paired live pending`

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

Dell/TSM 官方托管 transcript 已经过人工 route、parser、对象编译和 Evidence Gate，因此可以作为 reviewed Evidence 被 S3 消费；这不会把 `EARNINGS_CALL_TRANSCRIPT` 自动加入 S1 开放检索白名单，也不会让 transcript 数字获得 S2 NumericFact 权限。

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

默认循环上限是 24 step／24 tool calls、同一时刻 1 个 tool call、连续 2 次无进展即停止；五个 cell 各最多读取一次 Evidence、一次 NumericFact并提交一次 Judgment，EvidenceRequest 总数最多 9。这里的 24 是安全上限，不是目标调用次数；fake 五单元证明路径只需要 15 step，单单元含补证提案的路径需要 4 step。

工具 Schema 由当前 Research Input 生成 cell-local enum，所有 object 都是 closed schema。没有 NumericFact 或 gap 的单元使用不可匹配占位约束，而不是生成非法空 enum。模型若提交未知 cell/ref、跨 cell 引用、重复判断、非法指标/关系方向或未完成所有必需 cell，循环都 fail closed。

thinking tool loop 所需的 `reasoning_content` 只存在于同一次受控运行的瞬时 continuation message；落盘的 request/response capture、receipt 和 terminal result 都会剔除 Provider 私有推理。工具参数、最终 assistant/tool 输出、usage、finish reason、capture ref 和 digest 仍完整保存。凭据和 Authorization 永不落盘。

DeepSeek 差异只存在于三个可替换 profile：标准四工具、JSON 对照和 `/beta` strict tool。三者都固定正式模型名、`thinking=enabled`、`reasoning_effort=max`，且不发送无效 sampling 参数；strict Beta 不会被当作核心金融合同依赖。

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
4. 独立零调用 R1：已通过。单单元 4 step、五单元 15 step；两次 fresh process 结果等价；no-progress、unknown tool 和错 cell 判断均 fail closed；EvidenceRequest 后 gap 仍 open，0 retrieval／promotion／network／model／Provider。
5. 单独签发 DELL 单单元 paired canary：`v1.1 JSON + thinking=max` 对 `strict final-tool + thinking=max`。
6. 选择可靠传输后，再执行 DELL 五单元有界循环；调用次数由真实步骤决定，但受总 step、工具预算和无进展停止条件约束。
7. 依次执行 L1、八维绝对内容质量、与 R1 同 Evidence Pack paired、qualified-human 验收。任何一项失败都留在 S3，不自动扩成下一产品版本。
