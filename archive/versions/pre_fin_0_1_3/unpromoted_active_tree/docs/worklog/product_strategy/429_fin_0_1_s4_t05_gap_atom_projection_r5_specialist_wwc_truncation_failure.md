# FIN 0.1 S4-T05：R5 Specialist-v7 WWC segment 截断失败

日期：2026-07-27

## 权限与停止线

用户以“继续”进入已授权的唯一一次 R5 exact-live。Project OS、admission/issuance/code digest、credential presence、retry=0、fresh identity/result/supervision path 与 exact runner preflight 全部通过后，supervision-v2 发出一次 direct detached launch。

自动 retry、fallback、replay、relaunch、patch 与 rerun 均未授权；paired assessment 只允许在 6 nodes/12 calls/9 Artifacts coherent success 后执行。

## 执行结果

- admission digest：`37873166...a5db`
- Run：`research_run_fin01_3ce365aa075bacbc2cc31346`
- WorkUnit / Attempt / Run：`failed / failed / failed`
- Artifact：`0`
- orphan：`false`
- model / Provider / execution network：`3 / 3 / 3`
- input / output / total tokens：`13,103 / 2,247 / 15,350`
- estimated cost：`USD 0.00494911`
- Provider latency sum：`33,678 ms`
- capture / restricted readback：`3 / 3`
- retry / fallback / replay / relaunch / rerun：`0 / 0 / 0 / 0 / 0`
- paired assessment：未执行
- DELL R2：未证明

runner PID `25608` 自行 terminalize，exit code=0；supervisor 只读监控，monitor mutation 与 signal 均为 0。

## 第一个可信失败

Demand Cell 前两段 Facts 与 Claim Cards 均完成 `ok/stop`。第三段：

`actionable_what_would_change_tasks`

在输出恰好达到 segment cap `1400` tokens 时返回 `finish_reason=length`，触发：

`s3_bounded_node_output_truncated`

runtime 在 partial segment parse 与 Artifact commit 前正确 fail-closed。这不是 credential、网络、Provider transport attempt、supervision 或 retry 问题。

## 对 RC-P36-061 的影响

Research Lead-v6 尚未调用，gap-atom projection policy 未被 live 执行。因此 RC-P36-061 既不能关闭，也不能声称本次复发；其 live proof 状态变为“R5 已消费但在上游失败，projection 未观察”。

新增：

`RC-P36-062-s4-specialist-v7-WWC-segment-output-truncation-recurrence`

本轮只固化即时失败，不读取或披露受限 assistant 正文，不在已消费 Run 上决定压缩、扩容、切换 Provider 或重跑。历史 RC-P36-035 不自动重开；两次 1400-token truncation 是否共享最早根因，需要下一项零调用 request/capture/budget 审计。

## 产物

- failure result：`configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_projection_r5_exact_live_execution_failure_result_v1_0.json`
- contract test：`tests/contract/test_fin_0_1_s4_t05_dell_research_lead_gap_atom_projection_r5_exact_live_execution_failure_result.py`
- model run：`reports/model_runs/20260727_fin_ia_0_1_s4_t05_dell_gap_atom_projection_r5_specialist_wwc_truncation_r1.md`

## 收尾验证

- R5 failure-result focused contract：`5 passed`
- S4-T05 contract：`163 passed`
- S4 contract：`204 passed`
- 下一项 Project OS full-chain preflight：`pass`，open blocker=`0`

历史合同测试只更新“当前项目状态”的优先级与已消费状态；未改变 R3、R4、R5 发行时的历史事实，也未放宽 runtime failure contract。

## 下一步

`S4-T05-DELL-RESEARCH-LEAD-GAP-ATOM-DETERMINISTIC-PROJECTION-R5-FIRST-CREDIBLE-FAILURE-ROOT-CAUSE-DISPOSITION-DECISION`

该步骤必须是零模型调用；不得自动实施或签发新的 execution。
