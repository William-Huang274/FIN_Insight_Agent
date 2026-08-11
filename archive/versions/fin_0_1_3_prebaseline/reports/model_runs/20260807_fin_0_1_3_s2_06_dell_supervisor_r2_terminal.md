# Model Run: 20260807_FIN_0_1_3_S2_06_DELL_Supervisor_R2

## Summary

- Purpose: 在 SupervisorPlan v1.1 下重新测量 DELL 同证据纠错链的 supervised recoverability。
- Status: `terminal_failed_no_retry / shared correction semantic and closure gap`。
- Run type: inference。
- Timestamp: 2026-08-07T07:30:22Z。
- Environment: Windows 本机，clean/synced Git `85b3a8bb8fc1e5d8b3a2796988fdc2596e98cffd`。

## Code And Command

- Entry point: `scripts/releases/run_fin_ia_0_1_3_s2_06_dell_r2_supervisor.py`。
- Model: `deepseek-v4-pro`，temperature 0，thinking disabled。
- Raw binding: `fin013_s2_05_exp_a_dell_f9e9264951d69da5ed86`。
- Admission: 一份 `DELL_R2` case-local admission，shared SQLite exact-once 消费。
- Retry/fallback: 0/0；R3、MU、NVDA 均未授权或执行。

## Inputs And Boundary

- Supervisor input: 27 visible findings / 27 corrections / 6 required directives；hidden/Codex Gold 与跨案例输入禁止。
- Capacity: 8 expected calls / 11 hard calls，USD 0.18 hard ceiling。
- Corrected-node request只允许本案 Evidence/Numeric/Gap authority，并声明只有 `what_would_change` 可容纳假设阈值。
- 原始失败链保持不可变，corrected run 使用 fresh Run/Attempt/Capture identity。

## Result

- Provider calls/captures: `3/3`；Supervisor、U3、U4 均为 `ok/stop`、单次 transport attempt。
- Tokens: `11,509 input / 1,668 output / 13,177 total`。
- Estimated cost: `USD 0.009741`，为 policy ceiling rates 估算而非 Provider invoice。
- Latency sum: `21,778 ms`。
- Terminal: `specialist:U4 / experiment_a_unbound_numeric_surface`。
- Candidate frozen/hidden score/business promotion: `0/0/0`。
- Raw mutation: 0。

## Root Cause And Interpretation

R1 的非空 authority 漂移没有复发：SupervisorPlan v1.1 自然输出通过并生成六条合法 directive，因此 RC-P36-147 已获得 live close evidence。

新的首个共享问题发生在 correction 语义传递与关闭验证：Supervisor 输入中知道 `DELL-CORR-023/024` 的含义是 `explicit_counterevidence_surface_empty`，但 corrected Specialist 请求只传 correction ID、action 和 authority aliases，没有传 finding code、path 或要求如何关闭。U3 仍返回空 `counterevidence_ids`，普通 Specialist validator 却接受了它；这证明当前 runner 验证的是节点 schema，而不是 assigned correction 是否关闭。

U4 同样没有补出反证，并在整节点重写时把方向性“中个位数”重新锐化成约 `5%`，还把仅允许出现在 `what_would_change` 的阈值复制进 `financial_or_valuation_link`。因此这里同时成立：项目共享 correction protocol 缺口，以及 DeepSeek 在显式 numeric semantics 下的字段级不遵循。不能只归因模型，也不能再做逐字段 live 补丁。

## Governance

- Decision label: `stop / shared zero-call structural disposition required`。
- DELL R2 admission、3 captures 和 terminal 保持 immutable。
- 因为这是可跨案例复现的共享 correction protocol 缺口，按预注册 campaign 规则停止 MU/NVDA。
- 不执行 R3，不做 candidate scoring、paired assessment、Owner acceptance 或 release。

## Safety And Next Decision

完整 request/response 只保存在 Git 外受限 capture；公开记录不保存凭据、Authorization/Cookie 或 Provider 私有推理。下一项只允许零调用设计：把 code/path/closure rule 编译成 corrected-node 可见的 typed objective，并在节点接受前逐条证明 correction closed 或 typed-unresolved；同时收回自由数值叙事表面的所有权，避免整节点重写重新制造 L1。
