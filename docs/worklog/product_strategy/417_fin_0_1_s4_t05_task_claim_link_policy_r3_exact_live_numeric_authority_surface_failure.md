# FIN 0.1 S4-T05 TaskClaimLinkPolicy R3 exact-live：WWC Numeric authority surface 硬失败

日期：2026-07-27

## 权限与停止线

用户授权一直执行到 R3 exact-live 终态，并只在 coherent success 与九 Artifact 成立后做 paired assessment。唯一一次 launch 经 supervision-v2 发出；自动 retry、fallback、replay、relaunch、patch 与 rerun 均未授权。

## 执行结果

- admission digest：`4be4fa99...f29d`
- Run：`research_run_fin01_8905466e65d6259e54d42f6c`
- WorkUnit / Attempt / Run：`failed / failed / failed`
- Artifact：`0`
- orphan：`false`
- model / Provider / execution network：`3 / 3 / 3`
- input / output / total tokens：`12,851 / 1,857 / 14,708`
- estimated cost：`USD 0.00543886`
- Provider latency sum：`23,913 ms`
- capture / restricted readback：`3 / 3`
- retry / fallback / replay / relaunch / rerun：`0 / 0 / 0 / 0 / 0`
- paired assessment：未执行
- DELL R2：未证明

runner PID `91664` 自行完成 terminalization，exit code=0；supervisor 只读监控，monitor mutation 与 signal 均为 0。

## RC-P36-059 Live 结论

第一 Cell 的 WWC Provider output 使用 `Q001/Q002`，没有 raw Claim ID；本地精确展开为 `claim_1/claim_2`，unknown alias=0。说明最小 `TaskClaimLinkPolicy` 已走到 live path，旧 unknown `C3` 问题没有复发。

RC-P36-059 可关闭为：

`closed_live_path_positive_evidence_before_new_owned_failure`

## 新的最早失败

第一 Cell 的 facts、claims、WWC 三个 Provider response 都是 `ok/stop`。失败位于 WWC 本地 authority 校验。

受限结构回放确认：

- 两个 WWC task 字段形状完整；
- 两个 Claim alias 都合法并已本地展开；
- 第一 task 的 6 个 Numeric refs 全部是 exact input `authority_refs.numeric_refs` 的成员；
- 同一组 refs 已由前一 facts segment 的 `FactSupportAuthorityPolicy` 明确允许；
- 但 WWC `_owner_grade_authority_surface` 只从 `numeric_input.selected_financial_rows/derived_metrics` 重建 Numeric 集合，本 Cell 该集合为空；
- 因而 6 个合法 Numeric refs 全被误判为 outside authority，最终产生 generic `s3_owner_grade_WWC_task_incomplete`；
- 第二 task 的两个 Evidence refs 均在允许集合内。

这是项目内共享 validator 的 authority source 漂移，不是模型、Provider、credential、source data、role mapping 或 TaskClaim alias 问题。

新增：

`RC-P36-060-s4-WWC-numeric-authority-surface-drift`

## 序列边界

当前只登记阻断 T05 的最早 owner，不在本轮实施修复。此前已后传的 deterministic task identity、完整 WWC failure taxonomy 与跨阶段 unified identity redesign 不重入本序列。

## 下一步

`S4-T05-DELL-WWC-NUMERIC-AUTHORITY-SURFACE-ZERO-CALL-ROOT-CAUSE-DISPOSITION-DECISION`

下一关只能在单独授权后决定如何让 WWC validator 与 Fact support 共用同一 closed authority source，并保持 L1 fail-closed；不得重用已消费 admission 或自动再跑 DELL。
