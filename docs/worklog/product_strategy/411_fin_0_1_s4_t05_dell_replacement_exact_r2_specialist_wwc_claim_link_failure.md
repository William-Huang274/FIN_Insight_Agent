# FIN 0.1 S4-T05 DELL Replacement Exact R2：WWC Claim Link 硬失败

日期：2026-07-27

## 权限与执行边界

用户以“继续”授权：

`S4-T05-DELL-REPLACEMENT-EXACT-R2-EXECUTION-AND-PAIRED-ASSESSMENT-AUTHORITY-DECISION`

允许 exact-once 消费 replacement admission，并只在 coherent terminal success 和九 Artifact 成立后执行只读 paired assessment。retry、fallback、replay、relaunch、patch、rerun 均未授权。

## 执行结果

- admission digest：`058c5792...1af3`
- Run：`research_run_fin01_9756044e7d7f23b3ff9fb395`
- WorkUnit / Attempt / Run：`failed / failed / failed`
- Artifact：`0`
- orphan：`false`
- model / Provider / execution network：`9 / 9 / 9`
- input / output / total tokens：`38,266 / 5,583 / 43,849`
- estimated cost：`USD 0.02050905`
- Provider latency sum：`71,995 ms`
- capture / restricted readback：`9 / 9`
- retry / fallback / replay / relaunch / rerun：`0 / 0 / 0 / 0 / 0`
- paired assessment：未执行
- DELL R2：未证明

supervision-v2 的 runner PID 与 creation identity 绑定，runner 自行写出 exit receipt，exit code=0；monitor mutation 与 signal 均为 0。

## 新的最早失败

RC-P36-058 没有复发。实际 Runtime 已完成三个 Cell 的九个 Specialist Provider segment，说明 14-role mapping、slot alignment 和 shared dispatch 已走过 live path。

新失败位于第三个 Cell：

`bottleneck_counterevidence_and_what_would_change / actionable_what_would_change_tasks`

受限结构回放只读取 assistant final output，确认：

- 上一步 validated Claim IDs：`C1 / C2`
- 本步 task Claim IDs：`C1 / C2 / C3`
- unknown Claim ID：`C3`
- 三项 task 的字段形状均完整；
- 前两项在顺序校验中先通过；
- 第三项引用不存在的 Claim 后，以 `s3_owner_grade_WWC_task_incomplete` fail-closed。

这是 L1 identity / lineage 错误，不能降为 L2 协议 finding 或 L3 质量分，也不能把 `C3` 静默重绑到现有 Claim。

## 根因分类

直接响应错误来自模型：它没有遵守“exact validated claim_id”，新增了一个 prior segment 中不存在的 `C3`。

同时存在项目内 robustness gap：WWC task 仍要求模型复述 raw Claim ID 并自由生成 task ID；项目已经在 Claim→Fact 上采用 closed alias + local exact expansion，但没有将相同原则应用于 Task→Claim。generic `s3_owner_grade_WWC_task_incomplete` 还混合了 shape、unknown Claim、authority 和 blank-field 多类失败，降低诊断精度。

登记：

`RC-P36-059-s4-WWC-task-to-claim-open-identity-surface`

当前只冻结事实与待决策方向，不实现修复。

## 收口验证

- authority + failure result + issuance history core contract：`13 passed`
- S4-T04/T05 adjacent regression：`47 passed`
- JSON / JSONL parse 与 tracked/runtime cross-hash：`pass`
- touched contract tests compileall：`pass`
- 下一零调用 disposition scope Project OS preflight：`pass`，open blocker=`0`
- Git working/index diff check：`pass`

## 下一步

`S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-ZERO-CALL-ROOT-CAUSE-DISPOSITION-DECISION`

下一关需单独决定是否采用 closed Claim alias、本地 exact expansion、deterministic task identity 与 typed failure subtype。不得修补本次回答、重用已消费 admission 或自动执行第三次 DELL live。
