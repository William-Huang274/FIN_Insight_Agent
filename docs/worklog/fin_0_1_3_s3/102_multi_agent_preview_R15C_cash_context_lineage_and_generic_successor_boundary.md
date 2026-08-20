# FIN 0.1.3 S3 — R15C Cash 上下文 lineage 与通用 successor 边界

日期：2026-08-20
状态：`R15C_terminal_failure_preserved / zero_provider_call / generic_successor_compiler_required`

## 1. R15C 实际到达哪里

R15C 在 clean／synced commit `aaa4c3a7...27edf` 和 fresh Project OS preflight 后签发。它成功越过 task-specific profile 校验和 active V2 checkpoint 集合校验，但在复验已完成 repair 的不可变绑定时以 `multi_agent_bound_workpaper_digest_invalid` fail closed。

本次仍为 0 个模型节点、0 Provider attempt、0 网络、0 Candidate promotion、0 Supply analysis、0 Evaluator 和 0 Writer。authority、公开结果与 private terminal failure 必须保持不可变，不能重标为 DeepSeek 失败。

## 2. 逐节点尸检

- Demand repair：原业务 payload、原模型可见 SpecialistContext 和 workpaper digest 完全一致，可精确复用。
- Cash repair：R14 保存的业务 payload digest 为 `31c61429...12a45`，但从 R14 analysis-continuation request 恢复的模型可见 context digest 为 `51944726...37d5f`；将完全相同的业务字段重新对该 context 校验，得到 `1f5d07a2...5109e`，与持久化 digest 不同。
- R14 Cash 的持久化 payload 实际绑定 context digest `18d5f6ab...24063`。该 context 是 R14 当前 session 下本地重编的验证 context，不是 continuation 中模型真实读取的 `51944726...37d5f`。

因此，这不是 Cash 观点被证明错误，而是 R14 把“模型分析所见上下文”和“本地 submission 校验上下文”拆成了两个 lineage。R15C 拒绝复用是正确行为；不能靠关闭 digest 校验继续。

## 3. 为什么不再增加 R15D 特例

RC-AR-016 已提前规定：R15 后若再次出现 successor 编排缺陷，不得新增 R16／R17 式 attempt-specific authority 分支。当前条件已经满足。继续给 giant runner 加 `if R15C` 只会制造下一套历史特例，并不能回答任意节点应该精确复用、重绑派生字段还是 fresh 重做。

下一项归 S0，必须是 provider-neutral 的通用 successor compiler。它读取不可变 predecessor lineage，并对每个节点编译统一 execution frontier：

1. `exact_reuse`：业务 payload、模型可见 context 和 digest 一致；
2. `derived_digest_rebind`：业务字段逐字不变，且对 capture-bound 模型可见 context 可完整重验，只允许重算本地派生 context／workpaper digest并保存 receipt；
3. `fresh_rerun_required`：业务字段无法在原模型可见 context 下通过，或缺少足够 capture；
4. `pending_fresh`：原本未完成的节点。

authority、Project OS preflight 和 runner 都消费同一份 frontier，不再各自手写 attempt 语义。任何字段、capture、顺序或角色 mutation 必须 fail closed。

## 4. 当前边界

当前不能宣称 Supply、Evaluator、Writer、完整报告、L1、八维内容质量、S3 或多案例泛化已经通过。Cash 是否可以零模型规范化，必须由通用 compiler 的逐字段等价证明决定；若证明失败，就 fresh 重做 Cash，不能把旧结果冒充完成前缀。
