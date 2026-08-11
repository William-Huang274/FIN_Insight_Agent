# FIN 0.1 S3-T09 Research Lead 截断零调用根因决策

日期：2026-07-23

## 问题与边界

用户在 transport-v5 exact Run 以 Research Lead `1200` output tokens / `finish_reason=length` 失败后授权继续。当前项只允许读取已持久化的第 10 份受限 final assistant output，复核 Lead 输入、输出合同与预算，并形成零调用根因决策；不允许改代码、prompt、预算或 admission，也不允许模型、Provider、网络、retry、fallback、rerun、paired comparison、Human Review、T10、S4、release 或 production。

## 受限原始回答复核

复核对象绑定 Run `research_run_fin01_1736461952f90e35f104f478`，object digest 为 `8df1d74e6f42bcb250a1b1186c919aaf1aa1595c6863efed319159be3c64b9b1`。正文仍只保存在 restricted content-addressed object store；本工作日志和 Git 合同没有复制正文。

安全结构审计结果：

- 回答为 4,278 characters / 4,278 UTF-8 bytes；从 JSON object 开始，但没有闭合。
- JSON decoder 在 character 4,260、line 127、column 7 报 `unterminated string`，捕获尾部只剩 18 characters。
- 五个必需顶层字段均已开始；三组 `cell_heads` 完整。
- 已出现 2 个 cross-cell dependency、1 个 conflict adjudication、3 个 remaining gap；已闭合的 7 个 narrative statement 长度为 71–209 characters，未观察到额外 schema member。
- 因此，这次 malformed JSON 是 `length` 在字符串中间硬切断的结果，不是新的 HTTP、native JSON key 或 DeepSeek schema-conformance 失败。

## 合同审计与根因

Lead 请求输入为 4,581 tokens，包含三份完整、已校验 Specialist 输出及一份独立 digest map。这个输入规模低于多次已成功的 Specialist 请求，而且 Claim、Fact、Scope、Qualification、Gap 与 actionable WWC 正是 cross-cell synthesis 所需语义；没有证据支持用有损输入压缩作为修复。

最早的项目内缺口在输出侧：

- `cell_heads` 的 digest、terminal、Evidence/Numeric count 与 claim-state count 都能由本地确定性计算，却仍要求模型重复输出。
- dependencies 只要求非空，conflicts 只要求 list，remaining gaps 只要求非空；没有最大基数。
- Lead branch 没有 narrative character limit、serialized byte limit 或可机验的 concision self-check。
- 1200-token cap 没有对“所有合同允许的输出形状”做闭合证明。

一个 deterministic valid fixture 的 compact / pretty 大小为 1,932 / 2,623 bytes，只能证明“小输出可以通过”，不能证明开放的真实合同受 1200 tokens 约束。因此根因不是“token 数字太小”这一项本身，而是开放输出合同、冗余确定性字段与未经证明的预算组合。

## 决策

拒绝 cap-only、prompt-only “be concise”和有损 Specialist body compression。选择版本化 `fin01.s3.bounded_agent.research_lead_owner_grade:v2`：

- 保持 Specialist transport v5、canonical output-v3、完整 Specialist 语义和本地 authority validator 不变。
- Provider 只生成 dependencies、conflicts、variant view、remaining gaps 四个语义成员；三组 `cell_heads` 由本地从已验证 Specialist bodies/digests 精确计算后装配回 canonical Lead。
- dependencies `1..3`、conflicts `0..3`、gaps `1..4`、variant exactly one；每个 narrative field 最多 320 Unicode characters。
- Provider segment 最大 6,000 UTF-8 bytes，local assembled Lead 最大 8,192 bytes；不允许 truncate、trim、coerce、drop、join、split 或 silent repair。
- future Lead cap 选择 1,800，aggregate ceiling 从 16,200 调整到 16,800；在当前 USD 0.87 / million output tokens 下，最大增量仅 USD 0.000522，总成本 cap 仍为 USD 0.10，retry/fallback/rerun 仍为 0。

这不是本轮实现结果。下一项只能在独立授权后做 zero-call implementation 和 fake Provider fixtures；在此之前不得签发或真实运行。

## 结果与证据

- 决策合同：`configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_research_lead_output_truncation_root_cause_decision_v1_0.json`
- 源 live result：`configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v5_fresh_live_execution_result_v1_0.json`
- 源 model-run ledger：`reports/model_runs/20260723_fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_segmented_transport_v5_live_validation_r1.md`
- 本轮新增 model/provider/network/admission/Run/Artifact：`0/0/0/0/0/0`
- 新决策合同＋历史 v5 result contract：`8 passed in 0.33s`
- JSON/JSONL parse：pass；scoped Project OS preflight：pass，open blockers=`0`
- `git diff --check`：pass（既有 JSONL line-ending warning，无 whitespace error）
- T09 仍 blocked；Writer、Verifier 与九 Artifact product quality 仍未被新证明。

## 下一项与安全说明

唯一 next action 为 `S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-CLOSED-OUTPUT-LOCAL-HEAD-ASSEMBLY-AND-BOUNDED-HEADROOM-ZERO-CALL-IMPLEMENTATION`，尚未授权。原始回答未写入 Git；没有读取、输出或持久化 credential；没有执行实验或付费作业。
