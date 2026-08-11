# FIN 0.1 S4-T06 judgment-atom / compiled-contract fresh-agent proof

日期：2026-07-30

## 结论

`S4-T06-MU-DETERMINISTIC-JUDGMENT-ATOM-PLANNER-AND-COMPILED-CONTRACT-INVARIANT-HARDENING-FRESH-AGENT-PROOF-DECISION` 已通过。

证明生成器连续执行两次独立 disposable-runtime invocation，输出完全一致。当前 implementation 的四个源码/测试哈希、MU exact input、三案例全链、mutation、capture/failure 语义、R6 cached replay 和全新 prospective R7 identity 均重新计算；目标 Runtime 的 SQLite、对象树和逻辑快照保持不变。

这不是 DeepSeek canary、admission issuance 或 exact-live。R6 正式失败仍不可变，quarantined diagnostic 仍不可晋升。

## 独立证明结果

- proof generator invocations：`2`
- independent outputs equal：`true`
- MU exact input digest：`7887b5bb447fc6a844c410751f2038a04a1c0b04dbbe7e5bde41b040135a12e1`
- prospective R7：
  - WorkUnit：`wu_p02_5_f9068c5b7844123569d0178e`
  - Attempt：`attempt_fin01_f4705d1ce2ebfa9d01cb98ed`
  - ResearchRun：`research_run_fin01_112b220420c8b54907465112`
  - admission digest：`07c25f81095b8c82f75bfc320a3313976a093f5baf39754966f3b720858d18ed`
  - admission file：不存在
  - issued / consumed / execution：`false / false / false`
- clone execution counts before/after：均为 `7 WorkUnits / 7 Attempts / 7 Runs / 13 Artifacts`
- target DB digest：`203d6d0615dc1a9a00b8bda560e760454508777bf8af079c4301e43028470d20`
- target object-tree digest：`d524d754c32e7a5b9f186da703b7ae4d80dd0d929fe35214542c4072b773d292`
- target logical snapshot digest：`3ec10f2eaaba7cf2d55cb31f321fbd0228864c4322730153cf4118b133ada0fb`

## 重新执行的确定性证据

- DELL / MU / NVDA：各 `6 nodes / 12 callbacks / 12 captures / 9 Artifacts`
- compiled-policy surfaces：10
- unknown/cross-case alias：fail-closed
- arbitrary Provider narrative：fail-closed
- material numeric alias：本地唯一渲染
- mixed-scope leading candidate：先拒绝，再选择合法候选
- candidate permutation：稳定
- unknown calendar alias：fail-closed
- multibyte cost unit：未把 UTF-8 bytes 当 pricing token
- post-Provider fault：capture 保留
- R6 capture-v2 replay：被新 atom wire 拒绝

专项 proof、implementation 与 disposition 合计：`19 passed`。

下一项 canary-authority scope 的 Project OS postflight：`pass / open blockers 0`：

- `.codex_runtime/s4_t06_mu_judgment_atom_fresh_proof_postflight.json`

## 权限与产品边界

model、Provider、network、source、external tool、admission issuance/consumption、target write、exact-live、paired、owner、T07 均为 0。

本证明把结构包从 `runtime_injected / fixture_proven` 推进到 `independent_fresh_proof_passed`，但还没有证明 DeepSeek 的三个新合同家族会自然遵循 atom wire，也没有形成正式九 Artifact 研究结果。因此 T06 继续 blocked。

Git 仍位于 `codex/layered-data-source-expansion`，相对远端 ahead 5。工作树包含大量跨历史切片的 staged、unstaged 和 untracked 混合变更；为避免把既有用户变更混入当前提交，本项没有暂存、提交或推送。

## 下一项

`S4-T06-MU-CHANGED-CONTRACT-FAMILY-SINGLE-NODE-NATURAL-OUTPUT-CANARIES-AUTHORITY-DECISION`

下一项只允许做零调用 authority decision。未来 canary 若获独立授权，Fact、Claim/selection、WWC 三个家族各最多一次，总调用上限 3；不是 full-chain，不允许 retry、provider hopping 或失败后字段补丁。canary 通过后仍需分别完成 R7 admission 与 exact-live 权限链。
