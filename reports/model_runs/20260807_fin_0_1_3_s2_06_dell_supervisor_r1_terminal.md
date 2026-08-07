# Model Run: 20260807_FIN_0_1_3_S2_06_DELL_Supervisor_R1

## Summary

- Purpose: 测量 DELL 同证据链在 case-local Supervisor 扶正后的可恢复性。
- Status: `terminal_failed_no_retry / invalidated_by_project_contract_drift`。
- Run type: inference。
- Timestamp: 2026-08-07T06:45:58Z。
- Environment: Windows 本机，clean/synced Git `616432937dd00542af24fd8691951137179f163a`。

## Code And Inputs

- Entry point: `scripts/releases/run_fin_ia_0_1_3_s2_06_supervisor.py`。
- Model: `deepseek-v4-pro`，temperature 0，thinking disabled。
- Raw binding: `fin013_s2_05_exp_a_dell_f9e9264951d69da5ed86`。
- Input boundary: 27 visible findings / 27 corrections / 6 node directives；hidden/Codex Gold 与跨案例输入禁止。
- Admission: 一份 case-local admission，shared SQLite exact-once 消费。
- Retry/fallback: 0/0。

## Result

- Provider transport: `ok / finish_reason=stop / 1 attempt`。
- Provider calls/captures: `1/1`。
- Tokens: `8,567 input / 1,228 output / 9,795 total`。
- Estimated cost: `USD 0.0072278`，不是 Provider invoice。
- Terminal: `supervisor_plan / s2_06_supervisor_empty_case_authority`。
- Corrected candidate/hidden score/business promotion: `0/0/0`。
- Raw mutation: 0。

## Root Cause And Governance

自然输出的顶层 identity、correction partition、6 个 directive 顺序和 case-local alias 均合法；5 个研究/Writer directive 选择了 Evidence 或 Gap，Verifier directive 留空。模型可见 JSON Schema 允许这些空数组，Prompt 也没有写出“每个 directive 至少一个 Evidence 或 Gap”，但本地 Validator 隐式要求非空。因此 R1 是项目 Prompt/Schema/Validator 漂移，不是已成立的模型拒绝遵循指令。

R1 admission、capture 和 terminal 保持 immutable；没有 retry，也没有启动 MU/NVDA。下一步只允许一个共享零调用合同对齐包，之后需要 fresh proof 和单独的 replacement authority。

## Safety

受限 capture 保存在 Git 外；2 个 runtime JSON 文件 secret-like scan 命中 0。公开记录不保存完整请求、完整 assistant 输出、credential 或 Authorization/Cookie。
