# FIN 0.1 S3-T09 原子终态化与 Verifier 状态机 fresh Agent proof 决策

日期：2026-07-24

> 后续状态：冻结 payload 已在独立授权下原样签发且保持未消费；见 `386_fin_0_1_s3_t09_atomic_terminalization_and_verifier_state_machine_fresh_exact_admission_issuance.md`。本记录仍保留签发前 proof decision 的历史事实。

## 授权与边界

用户以“继续”独立授权 `S3-T09-ATOMIC-CAPTURE-FAILURE-TERMINALIZATION-AND-TYPED-VERIFIER-STATE-MACHINE-FRESH-AGENT-PROOF-DECISION`。本轮只允许零调用 proof decision、disposable clone 双 prepare、目标只读审计、合同测试与 Project OS 同步；不允许 admission 签发/消费、模型/Provider/网络调用、supervisor launch、restricted capture replay、业务 Artifact、paired comparison、owner acceptance、T10/S4/release/production。

## 冻结结果

新 proof 冻结：

- WorkUnit：`wu_p02_5_1e93d822b376782fb7648693`
- Attempt：`attempt_fin01_d39d0f35211169de635d6643`
- ResearchRun：`research_run_fin01_1e49c5f66f867ce2ba5ab9e0`
- input digest：`d93c866109054c9ace40c7b73968f26efce089d1f1ca7f5cfd4dc9ade62a5f00`
- preparation digest：`c1b22eb52938c7fbf3cea61db0bee052b21278ebb5f2b23d5c9077d5108c0053`
- prospective admission digest：`2b87b9360ed53ec060670446125065497f2625f9384839cb65c4482ea8c381e1`

disposable clone 两次 prepare 完全相等；clone 前后 WorkUnit/Attempt/ResearchRun/Artifact counts 均为 `20/20/20/13`。目标 canonical SQLite digest=`808071d3afecc550377fb654a3e2f08cd5e490a3ca1a192565caa63fee369e45`，object tree digest=`a2475f3e5e8fe1d08046140034e50d9aa8d10625566f57197c654702acacda93`，逻辑/物理状态前后不变。新三态身份不存在，prospective admission 文件不存在；20 个历史 Run 身份全部不可复用，baseline body 未进入 Provider input。

## 精确绑定

prospective admission 保持当前完整三 Cell 产品路径：

- output-v4；
- Specialist-v7；
- Research Lead-v5；
- Memo Writer-v3；
- research profile-v3；
- scoped identity-v1；
- ClaimFactLinkPolicy-v1；
- restricted final-assistant capture-v1。

proof 额外冻结五个修复相关代码文件的 SHA-256，并绑定：

- `fin01.s3.owner_grade_verifier_output_state_machine:v1`
- `fin01.s3.exact_run_supervision:v1`
- 单个 capture-bearing `FAIL_RESEARCH_RUN` canonical transaction；
- before/during/after transaction 三段故障矩阵；
- Verifier 3 个正状态与 7 个 closed 负 subtype；
- canonical-safe failure code `s3_bounded_verifier_state_machine_invalid`；
- detached supervisor only、fresh supervision root、PID/stdout/stderr/exit receipts、read-only/no-signal/no-retry monitor；
- 最低 lifecycle budget `1560s`，parent timeout=`none`，parent 不得 terminate child。

## 预算、成功与停止线

future exact proof 上限冻结为 12 次 semantic/provider/network calls、16,800 aggregate output tokens、USD 0.10、每 call 单 transport attempt、retry/fallback/patch/replay/relaunch/rerun=0。

只有 supervisor exit code=0、WorkUnit/Attempt/ResearchRun=`succeeded/succeeded/succeeded`、六个逻辑节点、12 calls、九类 Artifact、same-Cell Claim-to-Fact lineage 合法、四层 Verifier 状态机合法，才可进入后续单独的只读 paired comparison 决策。任何可信 parse/schema/semantic/authority/identity/state-machine/atomicity/supervision/budget/terminalization/capture/Artifact failure 必须立即终态停止。

## 验证

- fresh proof generator：成功，双 prepare equal；
- proof 功能合同：`7 passed`；backlog 权限治理断言：`1 passed`；专项当前合计 `8 passed`；
- `py_compile`：通过；
- fresh identity/admission absence：通过；
- target SQLite/Object digest parity：通过；
- exact admission issuance scope 的 Project OS preflight：`pass`，open blocker=`0`；
- model/provider/network/source/tool/supervisor launch/admission/Run/Artifact/comparison/Human：全部 `0`。

没有运行实验、模型 job 或 live execution，因此不新增 model-run ledger。

## 当前状态与下一项

RC-P36-051 与 RC-P38-050 现为 `zero_call_implemented_fixture_proven_fresh_exact_proof_contract_frozen_admission_issuance_pending`。这仍不是 paid Artifact proof；T09 保持 0 fresh Artifact，成品检查、paired comparison 与 owner acceptance 未进入。

下一项：

`S3-T09-ATOMIC-CAPTURE-FAILURE-TERMINALIZATION-AND-TYPED-VERIFIER-STATE-MACHINE-FRESH-EXACT-ADMISSION-ISSUANCE`

该项需要新的独立授权，只能原样签发冻结 payload；不能消费或执行。
