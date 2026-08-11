# FIN 0.1 S4-T06：MU R5 temporal-planning L1 failure 与 scope disposition

日期：2026-07-30<br>
状态：R5 immutable failed；no R6；一次零调用结构替换已选择但未授权

## 结果

MU R5 admission 已 exact-once 消费。DeepSeek `deepseek-v4-pro` 的前三次请求均完成网络调用并返回 `status=ok / finish_reason=stop`，但第一个 Specialist 的 `actionable_what_would_change_tasks` 段被 L1 拒绝：

- WorkUnit / Attempt / ResearchRun：`failed / failed / failed`
- model / Provider / network calls：`3 / 3 / 3`
- input / output / total tokens：`14,122 / 1,406 / 15,528`
- estimated cost：`USD 0.00736628`
- usage receipts / capture-v2 / Artifacts：`3 / 3 / 0`
- retry / fallback / replay / relaunch / rerun：全部 `0`
- paired assessment / owner acceptance / T07：均未进入

## 首个可信失败

模型在两个必填计划字段中写入了未出现在封闭合同中的日期：

- `$.what_would_change[0].time_window.deadline_or_review_date`
- `$.what_would_change[1].time_window.deadline_or_review_date`
- 两个值均为 `2026-09-30`

请求只允许复用 `2026-06-24`、`2026-07-26`、`FQ3_2026`、`Q1 2026`。因此，本次成立的是该字段上的模型指令不遵循；不成立的是财务金额造假、一般性 DeepSeek 不遵循、传输失败、无效 JSON 或截断。

更早的项目内根因也成立：`deadline_or_review_date` 是 mandatory Provider-owned free text，但系统只有财务数字/报告期分类器，没有独立的 planning-calendar authority、relative trigger enum 或 admission-bound date alias。既有三案例 fake fixture 又用无数字填充值，遗漏了自然 ISO 日期。结果是计划控制日期被错误纳入财务 numeric L1 家族。

## 原始证据留存

R5 生成的 3 份 capture-v2 均已内容寻址并通过 digest readback。每份包含模型可见请求、最终 assistant 输出、非敏感推理参数、finish reason、模型和安全 validator match index；不包含 credential、Authorization、Cookie、Provider 私有推理或 raw Provider response。失败输出没有晋升为业务 Artifact。

这证明 RC-P36-081 的 failure-path capture-v2 能力可以关闭。原始失败输出仅作审计证据，不会自动重放或成为金融事实。

## Runner 与 supervision 独立缺陷

canonical failure、3 份 receipts 和 3 份 capture-v2 均先于 runner 异常落盘。随后 runner 使用 legacy capture-v1 常量校验 admission-bound capture-v2，抛出：

`s3_t09_provider_output_capture_policy_mismatch`

因此 declared runtime-result JSON 未写出。supervision exit receipt 又在 Python traceback 完全 flush 前记录 stderr：receipt 为 `299 bytes`，最终文件为 `1,073 bytes`，digest 不同。canonical 三态仍可通过只读 SQLite 与对象存储重建，但 typed terminal-result 和 final-log receipt 合同未满足，登记 RC-P36-082。

## 结构性处置

不启动 R6，不做 Prompt-only retry、扩大数字白名单、字段名旁路或 Provider hopping。未来最多允许一个需单独授权的零调用实现包：

- Provider 只选择 closed relative trigger / review cadence enum，或 admission-bound date alias；
- exact issuer/review dates、unknown/unscheduled state 与文本渲染由本地确定性管理；
- 财务金额、百分比、measurement、sign、period 与 precision 继续 L1 fail-closed；
- DELL/MU/NVDA fixture 覆盖自然 ISO 日期、bound/unbound date、relative enum 和 financial-number-in-planning-field；
- runner 按 admission-bound capture policy 校验，并从 canonical terminal truth 总能写出 typed result；
- final stderr 在进程退出后验证，或另写 post-exit receipt。

若这个唯一包无法一次通过确定性验收，则阻断 Agent-authored WWC temporal delivery surface，退回确定性本地 planner；不再开启第二修复包。

## 工件

- failure result：`configs/releases/fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_v2_and_material_numeric_classifier_r5_exact_live_execution_failure_result_v1_0.json`
- failure result SHA256：`9662458edd0cfcddd4c999bbd2cb6374ade88b20fad473c7d432697a2ef6790f`
- disposition：`configs/releases/fin_ia_0_1_s4_t06_mu_r5_first_credible_failure_root_cause_scope_disposition_v1_0.json`
- disposition SHA256：`ef9e6e8e285c64289566c14dc76362ba08a673e73452329f675654ddcff2784e`
- regression：`tests/contract/test_fin_0_1_s4_t06_mu_r5_exact_live_temporal_planning_failure_and_scope_disposition.py`

## 下一步

`S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION`

该步骤当前未授权。R5 不可重放；R6、paired、owner acceptance 与 T07 均未授权。

## 验证

- focused R5 failure/disposition contract：`5 passed`
- 完整 S4-T06 contract regression：`246 passed / 1771 deselected`
- 下一零调用 scope Project OS preflight：`pass / open blockers 0`
- broad full-chain preflight：按设计 blocked，open blockers=`RC-P36-067/068/080/082`
- release JSON：`363` 个可解析
- Project OS JSONL：可逐行解析
- 新 R5 结果、处置、台账与测试 secret-pattern matches：`0`
- `git diff --check`：pass
