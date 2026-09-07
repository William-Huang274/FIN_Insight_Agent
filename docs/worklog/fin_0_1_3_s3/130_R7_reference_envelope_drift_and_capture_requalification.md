# FIN 0.1.3 S3：R7 引用 Envelope 漂移与 capture 重放资格化

日期：2026-08-23
状态：`R7_terminal_preserved / reference_envelope_root_cause_closed / captured_patch_contract_requalified / content_assessment_pending`

## 1. R7 实际结果

- R6 自然 Plan 按 capture/digest 复用，未重复调用 planning 节点；
- R7 只执行一次 non-thinking patch：prompt `19,107`、completion `2,767`、`finish_reason=tool_calls`；
- 0 retry、0 retrieval、0 S1/S2、0 外网、0 Candidate promotion、0 新 Evidence；
- 五项 FeedbackReceipt、五项 semantic commitment 与 accepted PlanDelta 全部被提交；
- 旧 Validator 在 merge 前以 `dynamic_semantic_repair_patch_new_reference_forbidden` 拒绝，R7 终态失败保持不可变。

## 2. 为什么不是模型或信源失败

模型新增的是：

- `NUM::BA153FB9939D66DF`：DELL FY26 Q1 operating income；
- `NUM::D0EA6489B2C138EE`：DELL FY27 Q1 operating income；
- `REL::E3A67501DFA73ACF`：两者同季度同比关系。

三者均已在本轮 immutable S2 current authority 中，且 R6 accepted Plan 明确要求分别呈现毛利与经营利润。旧 Tool Schema 从全 cell authority 编译并允许三者；旧 Validator 只按旧稿 `sourced_claims` 使用过的引用做子集校验。这是 Prompt Schema／Validator 的编译源不一致。

## 3. 结构处置

- 从旧稿结构化引用和 thesis／mechanism 内联引用形成 prior envelope；
- accepted action 只可加入其确定性需要、且已 reviewed 的 current-context 引用；
- 本轮 permit additions 精确为上述 `2 NumericFact + 1 Relation`；
- Tool Schema、模型可见 catalog、Validator 与 receipt 共用 `reference_envelope_digest`；
- 任意其他 current-context 引用 mutation 继续 fail closed；
- `new_evidence_or_authority_reference_count=0` 与 `context_bound_reference_addition_count=3` 分账。

R7 保存的完整 Tool Call 已零调用重放并通过结构合同。重放没有修改模型文字、补写观点或新增引用；只更正了项目自身对“已有权威首次结构化引用”的错误分类。

## 4. 当前边界

当前只达到 `semantic patch contract requalified`。独立 L1／L2 和单单元适用内容质量尚未签发；在其完成前，多 Agent、S3 acceptance、Workbench publication 和 release 继续禁止。

## 5. 工程复证

- capture requalification 使用原 `recorded_at` 重建后与已物化结果完全一致；
- 定向合同／Project OS 回归：`84 passed`；
- 全仓：`1101 passed`，仅两条既有 SWIG deprecation warning；
- `compileall`、`git diff --check` 通过；
- active baseline：`207 Python／8 frontend／5 detectors／28 Runtime／0 forbidden`；
- secret scan：`7,726 files／0 finding`；
- 历史 R6／R7 付费 scope 已消费，Project OS 明确 fail closed，不能借本次修复重复调用模型。
