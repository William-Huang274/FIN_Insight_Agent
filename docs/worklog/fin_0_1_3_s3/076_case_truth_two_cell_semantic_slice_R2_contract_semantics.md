# 076 两单元 Case Truth semantic slice R2：可见输出成立，claim 语义合同不足

时间：2026-08-17

## 结果

R2 绑定 clean/synced commit `6827efe04990ba484a683078b1f07b3113287738`，只把 R1 的 max-thinking 分析 profile 替换为专用 non-thinking classification profile；Operating 与 Counterevidence 的 R7 claim slice、Case Truth、strict submission、本地 Validator 和四调用上限均保持不变。

四次 DeepSeek 调用均返回完整 HTTP 200，0 retry／fallback／协议切换／来源网络／embedding／研究改写／报告生成：

- Operating analysis：`finish_reason=stop`，prompt `9,964`、completion `2,811`；
- Operating submission：`finish_reason=length`，prompt `5,850`、completion `2,000`，Tool arguments 在 6,146 字符处截断，未形成本地 receipt；
- Counterevidence analysis：`finish_reason=stop`，prompt `9,885`、completion `1,269`；
- Counterevidence submission：`finish_reason=tool_calls`，prompt `4,093`、completion `1,415`，形成 receipt，但被 14 条 finding 阻断。

R2 未识别三条预注册错误中的 AI orders、AI backlog 两条 false absence，也未正确保留产品／分部利润桥的合法 absence。公开结果 digest=`d23ed3bf...6fe8`，原 authority、请求、响应、分析稿、截断 Tool arguments 和本地 receipt 均保持不可变。

## 原因拆分

R2 证明 RC-S3-041 的 profile 判断成立：关闭 thinking 后，两份分析都有可见内容，故 R1 的零输出确实是任务／profile 不匹配，而不是网络或模型完全无法分类。

R2 同时暴露了一个更早的 provider-neutral 合同问题，而不能简单登记为“DeepSeek 又不遵循”：

1. `asserted_state` 同时被用来表达“句子声称什么”和“Case Truth 实际是什么”。模型因此倾向复制权威状态，而不是忠实抽取句子的否定命题；例如“未单独给出订单／积压”被提交为 present。
2. `not_visible_in_current_cell` 是 Harness 路由状态，不足以表达“跨公司事实只作为上下文、不能冒充 DELL 事实”。MU／NVDA 存货明明对 Counterevidence 可见，却因缺少 `context_only` 语义而被模型错误塞进 cell invisibility。
3. 分析指令要求“每个 material assertion”但没有禁止枚举支撑事实。Operating 将三个短 surface 扩成 30 余条 alias，包括底层 NumericFact、Relation、Facet 和桥接边界，strict submission 因而在 2k completion 内截断。
4. 完整全案 catalog 与五单元 visibility matrix 同时进入每个 slice。模型会选到语义相近但不属于当前单元的 alias；这既制造错误 synonym，也意外暴露 R7 原始 Judgment 的真实跨单元证据泄漏，例如 Operating／Counterevidence 写入各自 allowed view 之外的经营现金流、收入或需求事实。
5. 其中并非所有 14 条 finding 都是模型错误。两条 `asserted_cell_local_invisibility_invalid` 是现有状态词无法表达合法跨公司 contextual evidence；其余一部分是 alias 误选，一部分是真实的 R7 cross-cell claim scope 问题。必须在合同层拆开后再裁决，不能为通过目标而隐藏。

## 下一处置

不扩大 S3 产品范围，不自动进入剩余三单元或 R7 修文。先做一次统一零调用结构包：

- 把模型输出改成明确的 claim polarity（句子声称存在／缺失／未解决／仅作跨案上下文），Harness 另行计算 authoritative truth；
- 为当前 claim slice 编译分层 alias view，明确 current-cell eligible、case-only outside-cell 与 typed absence authority，不再把五单元完整矩阵平铺给每个节点；
- 只映射 claim 直接表达的 proposition，禁止枚举用于支撑它的每个底层数字和事实；比较关系优先 Relation，只有原文给出精确数值才映射 NumericFact；
- local Validator 保留 false absence、unauthorized absence、outside-cell presence、cross-case contamination 与 legitimate gap 的最终权威；
- 用 R2 原始分析和 Tool arguments 回放，加入 DELL／MU／NVDA／留出、cross-cell、context-only、容量和 mutation 测试。

通过 clean proof 后，最多再签发一次同两单元自然 successor。若仍出现新的合同级 L1，不继续为 DeepSeek 逐字段扩建专用分支，转为模型职责缩减或独立语义分类 profile 的项目级处置。

## 结构包实现与 pre-proof 验证

同一维护模块现已实现 v1.1 reconciliation：

- `compile_case_truth_claim_model_view` 为单 cell 编译 eligible／case-only／typed-gap 三层视图，同时保留全案冲突检测能力；
- current Tool Schema 只接受 `claim_polarity`，旧 `asserted_state` 仅供不可变历史 replay；
- `claim_uses_cross_case_context` 由 owner ticker、subject ticker 与 cell visibility 本地复核；
- analysis draft 上限 8,000 字符、每 surface 最多 12 个直接 proposition；Tool 和 Validator 同源；
- Case Truth submission 使用独立 non-thinking 4k strict-beta profile，不修改其他 Judgment／repair 节点的 2k profile；
- maintained zero-call runner 已升级为 R2 capture-bound successor，准备验证旧 draft／overmapping 提前拒绝、三条 false absence、合法 bridge gap、context、outside-cell、容量、三案例与留出 mutation。

pre-proof 结果：全仓 `488 passed`；compileall 通过；active baseline=`138 Python / 8 frontend / 11 Runtime / 0 forbidden`；secret scan=`6,858 / 0`；`git diff --check` 通过。下一步只剩 clean commit/push 后签发 fresh formal zero-call authority；上述测试尚不等于 formal proof 或自然模型通过。
