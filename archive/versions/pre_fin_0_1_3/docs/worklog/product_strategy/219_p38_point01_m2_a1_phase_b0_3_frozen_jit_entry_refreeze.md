# P38 Point01 M2-A1 Phase B0.3：冻结 JIT 入口 v2.6

## 目的与授权边界

修复 B0.2 审计发现：v2.5 把 JIT orchestrator 纳入 package，但其实现是永久拒绝 stub；审批后修改入口会使 package hash 失效，而 package 外新增入口会重现 v2.4 的未冻结 dispatch 风险。

本轮只获准实现、冻结并验证默认拒绝的 approval-driven JIT entry。未签发 active `HumanJITWindowApproval`、admission 或 receipt；未执行 baseline 或任何 16-scenario actual；未创建 v2.6 namespace/runtime/output/ledger。

## 交付

- 新增 package-external `HumanJITWindowApproval` 的严格 schema、canonical digest 与 exact binding validator。
- 新增冻结的 `run_point01_m2_a1_v2_6_frozen_jit_window.py`；仅 `--execute-approved-window --approval <path>` 预留未来活动路径，默认/缺失/错误 approval 在任意写入前 fail-closed。
- future path 的固定顺序为 `verify approval → issue admission → verify → register → preflight → consume → staged reverify → grant verify → materialize → v2.6 parent/clean child → immutable actual → independent oracle → reviewer → closeout`。
- 新增 v2.6 parent、clean child、registrar 和 generic frozen helper，所有入口均为 Git-index package input。
- v2.6 policy、package/plan/blueprint 均保留 unresolved/not-active authority template；v2.4/v2.5 authority 只保留为 historical non-replayable evidence。

## 冻结证据

| Artifact | SHA-256 |
| --- | --- |
| v2.6 package | `b967edcdb5b472bab4531c0603e14a397fc2e9364c9830090ba763463d9fdee2` |
| package gate | `c39cd7f3e7674ee57ec84eeeef19b459369b0b494b8203cbc0ad1ccc8bbe6dbb` |
| receipt plan | `f06cb482cf30aa0466b3bd8425db7fea140a86e78f613ffa0ac87b35be47dc8b` |
| plan gate | `24dba2134b3c96da19837f2569390f97b14136e1c8fffb1150f047d4f2fe6512` |
| baseline blueprint | `199f0a01ab79255e44207137ab9e692f34a0c337014ca3e069224944043c2cb5` |
| blueprint gate | `5a5ee2094ba1c6409747699dd9b7843a3c1bc1728604ef662bbc7176c8d7138c` |

## 验证

- `python scripts/engineering/run_point01_m2_a1_operational_qualification_v2_6_refreeze.py`：pass；production package validator 的 no-admission normal terminal 为 `package_admission_required`，orchestrator missing-approval dry-run 为 fail-closed，gate 所有执行计数均为 0。
- `python -m pytest -q tests/contract/test_point01_m2_a1_v2_5_dispatch_and_expiry.py tests/contract/test_point01_m2_a1_operational_qualification_v2_4_production_preflight.py tests/contract/test_point01_m2_a1_v2_6_frozen_jit.py`：`14 passed`。
- v2.6 targeted tests 覆盖 default/missing approval、synthetic exact approval dry-run、wrong reviewer、package/plan/blueprint gate digest、scenario、TTL 与 expiry；所有错误路径在 namespace/admission/receipt/runtime/actual 创建前停止。
- fixed approval DB SHA-256：`ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`；`D:/temp/FIN_Insight_Agent/point01_m2_a1_exact_admitted_runs_v2_6` 不存在。

## 当前状态与下一步

状态仅为 `phase_b0_3_frozen_jit_entry_refrozen_pending_independent_review`。M2 deterministic-shadow closeout 保持；operational qualification 仍为 `pending_frozen_jit_entry_independent_review_and_fresh_baseline`。

下一步只能由 total reviewer 审核 v2.6 exact package/plan/blueprint，之后才可能单独批准一份短期、一次性 baseline HumanJITWindowApproval。不得自动签发 authority、重跑 baseline、执行其余 15 场、进入 M3–M7、调用网络/model/tool/provider/full-chain，或变更业务/legacy authority。

## Final staged-byte addendum

表中 preliminary digest 已被最终 staged test bytes supersede：package=`e85ceffb0922ceda99e105b519a7f2dac19d5e5bdcea357925ee451d066ad4ed` / gate=`a07b44b7c0bc4970730abc57d61ba9978119fa34cbe1c29a237af909eef329c7`，plan=`4f50ef334f594aba5d073fab6e11caefafa91b1391b4a9b96da959b1e44c0c4e` / gate=`8e28d55fe88e720a992862a13f6f0a8b81a9fc7b8f75e6c4aff143eff2000b77`，blueprint=`d9e7dcba8b03e5099451efb6413a113a8e2866cbf30cca88df499414c9958cb7` / gate=`7399e04a5de9752590f2ec1e93f8abf3235ddd73d7614de090bb9102d514c091`。最终回归为 `15 passed`；新增 old v2.5 admission -> v2.6 `admission_schema_version_mismatch` 的无写入负例。
