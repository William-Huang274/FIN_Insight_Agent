# FIN 0.1 S4-T05 Research Lead gap-atom projection R5 exact-live execution authority decision

日期：2026-07-27

## 授权边界

用户以“继续”授权当前 R5 execution authority decision。本轮只检查是否可以在下一项 exact-once 消费已签发 admission，不启动 supervisor、不消费 admission、不调用模型或 Provider，也不执行 paired assessment、Human review、S4-T06 或 dependency/conflict/all-node atomization。

历史 R4 保持 immutable failed/0 Artifact；本决策不改写其 admission、Run、capture、tokens、cost 或 first credible failure。

## 零调用门禁

- Project OS scoped preflight：`pass`，open blockers=`0`。
- exact runner disposable-clone preflight：`pass_exact_zero_call_execution_preflight`。
- fresh WorkUnit/Attempt/ResearchRun：
  - `wu_p02_5_b63a5202479c6be94`
  - `attempt_fin01_ba8728e601ea22f6592189e2`
  - `research_run_fin01_3ce365aa075bacbc2cc31346`
- canonical execution counts：`4/4/4/0 -> 4/4/4/0`。
- R5 admission digest：`378731667e55e56740b5fd2fcc81fc152e3b2da91e15230cc7db33a6034ca5db`。
- credential 仅确认存在；值未读取、输出或持久化。
- `LLM_GATEWAY_TRANSPORT_RETRIES=0`；Provider health probe 未执行。
- supervision-v2 host capability receipt SHA256=`79199d2c...862d1d`，fresh R5 supervision root absent。
- 七项 runtime/runner/supervisor code binding 全部 exact。

## 决策

状态推进为 `authorized_R5_exact_once_and_conditional_read_only_paired_assessment`：

- 下一项允许通过 supervision-v2 exact-once 消费 R5 admission。
- 自动 retry、fallback、replay、relaunch、patch 或 rerun 均禁止。
- 首个可信失败必须 fail-closed terminalize，并转入最早 owner root-cause disposition。
- 失败后禁止 paired assessment。
- 只有 coherent terminal success、6 logical nodes、12 semantic calls、9 Artifacts、三 WWC TaskClaim/authority policy 消费、Research Lead-v6 gap-atom projection、全部 candidate 校验、manifest/JudgmentSet finding parity 与 layered acceptance 均通过后，才允许 success-only read-only paired assessment。

## 验证

- authority＋issuance focused：`9 passed`
- 完整 S4-T05：`158 passed`
- 完整 S4：`199 passed`
- model/provider/network/source/tool/admission consumption/WorkUnit/Attempt/Run/Artifact：全部 `0`

machine decision：

`configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_projection_r5_exact_live_execution_and_paired_assessment_authority_decision_v1_0.json`

SHA256=`71c0a661775fee4b9436208c28bf97dd412fe761fda59c96fd7c9db3ee644d37`。

## 下一项

`S4-T05-DELL-RESEARCH-LEAD-GAP-ATOM-DETERMINISTIC-PROJECTION-R5-EXACT-LIVE-EXECUTION`

该 execution 尚未发生。下一项只能使用本决策冻结的 admission、issuance、runtime root、supervision root 与 output prefix；不得在失败后自动重试或重跑。
