# FIN 0.1 S4-T05 DELL Exact R2 Provider 前失败

日期：2026-07-26

## 结果

用户以“继续”授权 `S4-T05-DELL-EXACT-R2-EXECUTION-AND-PAIRED-ASSESSMENT-AUTHORITY-DECISION`。本轮只允许：

- exact-once 消费现有 DELL admission；
- supervision-v2 下执行一次 DELL exact-live；
- 仅在 coherent terminal success 与九 Artifact 成立后进行只读 paired assessment；
- retry、fallback、replay、relaunch、patch、rerun 均为 0。

执行结果为：

- WorkUnit / Attempt / ResearchRun=`failed / failed / failed`；
- terminal reason=`bounded_agent_profile_error:EvidenceServiceError`；
- Artifact=`0`；
- orphan=`false`；
- runner exit=`0`，self-finalized receipt 完整；
- model / Provider / execution network / source / tool=`0 / 0 / 0 / 0 / 0`；
- token / cost=`0 / USD 0`；
- paired assessment=`not performed`；
- DELL R2=`not proven`。

Admission `da035e71...a60f` 已 exact-once 消费，不能修改或重跑。

## Root Cause

disposable runtime clone 将目标 WorkUnit 恢复为失败前的 `running` 状态后，实际 evidence-plan 编译精确复现：

`EvidenceServiceError: s3_required_evidence_role_slot_missing`

实际 Runtime 在进入 S4 adapter 前调用 `compile_s3_three_cell_runtime_evidence_plan`，其 `_s3_runtime_context` 固定要求：

- `demand_signal`
- `revenue_capture`
- `thesis_counterevidence`

DELL accepted DecisionSurface 保存的是 14 个 case-specific roles，例如：

- `issuer_demand_or_order_signal`
- `issuer_financial_statement`
- `official_supply_or_component_constraint`
- `working_capital_or_cash_stress`

两套 role name 的 exact match 数为 `0`。因此 Runtime 在 Provider 前 fail-closed。

登记：

`RC-P36-058-s4-case-specific-evidence-role-to-runtime-plan-taxonomy-gap`

这是项目内 runtime contract composition 缺口，不是模型问题，也不是外部数据边界。

## 为什么此前没有发现

T04 exact prepare 直接构造 source-grounded bounded-agent input，没有运行 actual dispatch 前置的 EvidenceService plan；T03 deterministic fixture 证明了 S4 pack 注入和节点消费，但同样没有覆盖实际 pre-adapter role taxonomy bridge。

因此 `RC-P36-057` 的 input dispatch 修复是必要但不充分的：S4 input 已接入 actual adapter，但 adapter 之前仍有一段 S3-only evidence planning contract。

## 证据

- Authority：`configs/releases/fin_ia_0_1_s4_t05_dell_exact_r2_execution_and_paired_assessment_authority_decision_v1_0.json`
- Result：`configs/releases/fin_ia_0_1_s4_t05_dell_exact_r2_execution_failure_result_v1_0.json`
- Run：`research_run_fin01_2eced17671df87082b95db9a`
- Runtime result SHA256：`51cca2977f91ba68086ba536a806a438b6e0cd15d27d7f60fdb49ba0e57dee0a`
- Launch receipt SHA256：`34e425acb89a68b58a5c4b1a6cb68070980381e67ef92a756177ab14394a2232`
- Exit receipt SHA256：`05b8ab3ddc7b4bc7000858f690daaa97f39bb5a569f9140b807507c697ec6b38`

## 下一步与边界

当前下一项：

`S4-T05-DELL-EVIDENCE-ROLE-TAXONOMY-TO-RUNTIME-PLAN-ALIGNMENT-ZERO-CALL-ROOT-CAUSE-DISPOSITION-DECISION`

下一项只允许选择显式 case-local role mapping 合同，并要求 actual Runtime planning 与 exact preflight 共用。禁止：

- 重命名或覆盖 14 个历史 DELL source roles；
- DELL 特判或 synthesized generic slots；
- 修改已消费 Run；
- 未经 deterministic actual-dispatch proof 直接签 replacement admission；
- 自动第二次模型执行。

MU、NVDA、Human review、S5、release 与 production 均未授权或证明。

## 收口验证

- T05 authority/result、T04 历史快照、S3 closeout、S4 entry/T02/T04 与 cross-slice 邻接合同：`71 passed`；
- 下一项 Project OS full-chain preflight：`pass`，open blocker=`0`；
- 当前 slice 状态已同步为 T05 provider 前失败，历史 T04 issuance 证据与当前已消费状态分别断言；
- 本轮未修改 bound runtime code，未重试、未签 replacement admission、未发起第二次模型调用。
