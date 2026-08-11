# P38 / Point 01 P01-G2.0 Authority And Coverage Repair

日期：2026-07-17
状态：`P01_G2_0_TRANCHE_FROZEN_PENDING_INDEPENDENT_EXECUTION_AUTHORITY`

## 审计问题与决策

P01-G2.0 v1.0 的静态完整性和零副作用证明通过，但独立审计拒绝 execution authority：B0.7 baseline blueprint 只允许 `p01-baseline-separated-input` 的 future authority，而 v1.0 为 stale/transport 预设 authority/receipt/namespace/runtime；并且把 supplemental wrong package/approval 写成原始 `p01-oracle-path-access`，使 original 16-scenario coverage 行为语义缺项。

本轮仅修 freeze contract，生成 v1.1，不执行任何 scenario。v1.0 tranche/gate `8df521fcc321c6c5dfa30f6ae7a3ad377a0be223c21091525ef741d9208a047f` / `cfe1f33f2c06b109561fcda349dc1a7e06e249b3ceb7804ef7d81faf76c14a87` 是 rejected historical evidence，不能用来申请 authority。

## v1.1 冻结结果

- tranche：`aeeccb1525d693f1dc19eb42a6f9666fed3ebf4a3b3f578f73fd8dc22678f861`
- gate：`32cc169081b9e4158894925d4fb207824c28bc17e408190e6cce900de950b7a5`
- coverage：3 original selected + 13 original deferred = 16；另有 1 supplemental pre-authority probe。

baseline 是唯一未来可申请 package-external reviewer decision、admission、single-use receipt、formal namespace 和 runtime materialization 的 case。其余三个 probe 的 valid authority/receipt registration/consume/namespace/runtime/terminal lifecycle counts 均为 0：

1. `g2-wrong-package-or-approval`：supplemental，pre-authority `package_or_approval_mismatch` deny；
2. `g2-stale-input-version-drift`：original `p02-stale-or-superseded-pack`，pre-authority pack/version typed stop；
3. `g2-unauthorized-transport`：original `p03-network-tool-transport`，pre-authority canary/permission typed stop，network/tool success=0。

`p01-oracle-path-access` 已恢复到 13 项 named deferred original backlog。负例只列 deny/probe、input/package binding、permission/canary observation 与 reviewer comparison artifact，绝不列 future admission/receipt/runtime artifact。

## 验证与边界

- v1.1 deterministic contract tests：`7 passed`；
- v2.10 family staged inputs：`79/79` exact binding；
- fixed approval DB fingerprint 保持 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`；
- active approval/admission/receipt、formal namespace、runtime、baseline、external/network/tool/model/provider/fixed-store write 和 legacy authority change：全部 0。
- Project OS root-cause / supersession ledger：[point01_p01_g2_authority_coverage_repair_ledger.jsonl](/D:/FIN_Insight_Agent/docs/project_os/point01_p01_g2_authority_coverage_repair_ledger.jsonl)。

未运行 compiler/shadow、任何 operation scenario、网络、模型、provider、tool 或 full-chain。下一步必须是独立 reviewer 对 v1.1 tranche 的复审；不得自动进入 P01-G2.1。
