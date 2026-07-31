# Model Run: 20260727 FIN 0.1 S4-T05 DELL replacement exact R2 Specialist WWC claim-link failure r1

## Summary

- Purpose: 在 RC-P36-058 修复后执行唯一一次 DELL replacement exact-live。
- Status: terminal failed；admission 已消费；paired assessment 未执行。
- Run type: exact-live inference。
- Timestamp: 2026-07-27。
- Environment: Windows local，supervision-v2。

## Code And Command

- Entry point: `scripts/releases/supervise_fin_ia_0_1_s3_t09_exact_live_execution.py`
- Admission: `fin01-s4-t05-dell-evidence-role-group-mapping-repair-fresh-exact-admission-r2`
- Admission digest: `058c579211eb1f4573959d86f0b904b64e2535e749631ab7ee208571ef601af3`
- ResearchRun: `research_run_fin01_9756044e7d7f23b3ff9fb395`
- Retry/fallback/replay/relaunch/rerun: `0/0/0/0/0`

## Inputs

- Case: DELL / `case_7b5c2042bef3825b8df71a96:v1`
- As-of: `2026-07-26T00:00:00Z`
- Input digest: `3499c03470c5bec5168dc87a2974802869da389f2ef588f41021731828d09e96`
- Source boundary: frozen issuer-bound Evidence/Numeric、context-only Graph、typed gaps。
- Source/tool/live Case writes: forbidden。

## Results

- WorkUnit / Attempt / Run: `failed / failed / failed`
- Artifact: `0`
- Orphan: `false`
- Runner exit: `0`
- Calls: model/provider/network=`9/9/9`
- Tokens: input/output/total=`38,266/5,583/43,849`
- Cost: `USD 0.02050905`
- Provider latency sum: `71,995 ms`
- Capture/readback: `9/9`
- Finish reason: 9 个均为 `stop`

RC-P36-058 未复发：三个 Cell 的九个 Specialist segment 都已调用。新失败发生在第三个 Cell 的 WWC segment 本地校验；上一步只有合法 Claim `C1/C2`，回答中的三个任务却绑定 `C1/C2/C3`，其中 `C3` 不存在。所有三项任务字段形状完整，前两项先通过，第三项因 unknown Claim link 被硬失败。

## Experiment Governance

- Decision label: `stop`
- Layer: L1 identity / lineage hard integrity
- Paired assessment: 未执行，因为没有 coherent terminal success 或九 Artifact。
- Direct response fault: 模型在已验证 Claim 集之外新增了一个 Claim ID。
- Project-owned robustness gap: WWC segment 仍让模型复述 raw Claim ID 和自由 task ID，未使用 ClaimFactLinkPolicy 已证明的 closed alias + local expansion 模式；现有 generic `wwc_task_incomplete` 也没有区分 unknown-claim、shape、authority 与 blank-field subtype。
- Root cause issue: `RC-P36-059-s4-WWC-task-to-claim-open-identity-surface`

## Caveats And Next Step

- 本结果不说明 DELL 全链分析质量，因为 Lead、Writer、Verifier 均未到达。
- 不得把 `C3` 静默改成 `C1/C2`，也不得丢弃第三项任务后让旧 Run 通过。
- 下一项仅为另行授权的零调用 root-cause disposition；当前 admission 和失败 Run 不可重用。
