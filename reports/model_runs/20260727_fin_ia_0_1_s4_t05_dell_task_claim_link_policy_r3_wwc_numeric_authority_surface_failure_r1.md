# Model Run: 20260727 FIN 0.1 S4-T05 DELL TaskClaimLinkPolicy R3 WWC numeric-authority failure r1

## Summary

- Purpose: 验证 `fin01.s3.task_claim_link_policy:v1` 的 DELL R3 exact-live 路径，并仅在 coherent success 后执行 paired assessment。
- Status: terminal failed；admission 已 exact-once 消费；paired assessment 未执行。
- Run type: exact-live inference。
- Environment: Windows local，supervision-v2。

## Exact Identity

- Admission: `fin01-s4-t05-dell-task-claim-link-policy-fresh-exact-admission-r3`
- Admission digest: `4be4fa99479da78547bfc9266c708478aa524d459db97c7341799b2724a7f29d`
- WorkUnit: `wu_p02_5_4e861814210bbc43c8632e22`
- Attempt: `attempt_fin01_ed9ba7af7a2805527b0d7cb1`
- ResearchRun: `research_run_fin01_8905466e65d6259e54d42f6c`
- Retry/fallback/replay/relaunch/rerun: `0/0/0/0/0`

## Results

- WorkUnit / Attempt / Run: `failed / failed / failed`
- Artifact: `0`
- Orphan: `false`
- Runner exit: `0`
- Calls: model/provider/network=`3/3/3`
- Tokens: input/output/total=`12,851/1,857/14,708`
- Cost: `USD 0.00543886`
- Provider latency sum: `23,913 ms`
- Capture/readback: `3/3`
- Finish reason: 3 个均为 `stop`

第一 Cell 的 facts、claims 和 WWC 三段均得到完整 Provider response。Lead、Writer、Verifier 均未到达。

## Live Policy Observation

TaskClaimLinkPolicy 的 live 路径已生效：

- Provider WWC task 只返回 `Q001/Q002`；
- 两个 alias 本地精确展开为 `claim_1/claim_2`；
- unknown alias=`0`；
- Provider task 中 raw `claim_id`=`0`。

因此 RC-P36-059 没有复发，可记录为在新失败前获得 live positive evidence。

## First Credible Failure

失败发生在：

`demand_authenticity_and_sustainability / actionable_what_would_change_tasks`

两个 task 的形状完整，Claim link 都有效。第一项 task 引用了 6 个 DELL Numeric refs；这些 refs：

- 全部位于 exact input 的 `authority_refs.numeric_refs`；
- 全部是同一请求的 `FactSupportAuthorityPolicy` 明确允许集合；
- 已被前一 facts segment 合法使用；
- 但在旧 WWC `_owner_grade_authority_surface` 中全部缺失。

原因是两个 validator 读取了不同 authority source：

- Fact support 读取 `authority_refs.numeric_refs`，得到 6 项；
- WWC validator 只从 `numeric_input.selected_financial_rows/derived_metrics` 重建 Numeric authority；该 Cell 此路径为 0 项。

第一 task 因此被 generic `s3_owner_grade_WWC_task_incomplete` 拒绝。第二 task 的两个 Evidence refs 均合法。

## Root Cause And Governance

- Immediate owner: project runtime validator authority-surface drift。
- Model/provider fault: false。
- New issue: `RC-P36-060-s4-WWC-numeric-authority-surface-drift`。
- Layer: L1 authority/lineage，不能降级为质量 finding。
- Paired assessment: success-only 条件不成立，未执行。
- DELL R2: 未证明。

本轮不修复、不重跑，也不重入已后传的 deterministic task identity、完整 WWC taxonomy 或跨阶段 identity redesign。

下一项仅为另行授权的零调用 disposition：

`S4-T05-DELL-WWC-NUMERIC-AUTHORITY-SURFACE-ZERO-CALL-ROOT-CAUSE-DISPOSITION-DECISION`
