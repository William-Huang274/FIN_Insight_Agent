# FIN 0.1 S4-T06：R4 classifier false positive 与审计证据合同

日期：2026-07-30<br>
状态：零调用根因更正与合同冻结完成；runtime v2 实现待后续；no R5

## 问题

R4 的 content-free telemetry 只记录：

- `provider_authored_numeric_token`
- `field_id=explanation_layer`
- `failing_item_count=2`

此前据此把失败解释成模型生成了两个无法判断正误的数字。但 R4 同时持久化了四份受限 assistant final-output capture，因此可以直接回放第四次输出。

## 回放结论

第四份 capture 的 SHA256 为：

`6223bfc2f55ccb8e83733622b071c6e756bf731adbd36aa2f869ea69a12d3c79`

完整 JSON 中两个命中叙事值位于：

- `$.fact_layer[0].statement`
- `$.explanation_layer[0]`

二者共同包含 `FQ3 2026`。当前 policy 按“一个 narrative string 是否含任意数字”计数，因此 `2` 表示两个字符串命中，不是两个财务数字；没有证据证明模型生成了错误金额、百分比或计量值。

RC-P36-080 因而更正为项目内 numeric narrative classifier false positive。R4 的三态、调用、成本、0 Artifact 和 no-R5 均保持不可变。

## 冻结合同

新增：

- 技术合同：`docs/architecture/fin_0_1_runtime_audit_evidence_retention_and_promotion_separation_v1.zh-CN.md`
- 可机读处置：`configs/releases/fin_ia_0_1_s4_t06_mu_r4_numeric_classifier_false_positive_and_audit_evidence_separation_disposition_v1_0.json`
- 合同 ref：`fin01.runtime.audit_evidence_retention_and_promotion_separation:v1`

合同把校验拒绝与证据留存分离：失败输出不得进入业务 Artifact，但必须以内容寻址、不可变、受限访问的方式留存。telemetry 仅作索引，并应绑定 capture ref/digest 和安全命中位置。

## 当前能力与缺口

已证明：

- assistant 最终输出可按 digest 回放；
- capture 绑定 Run/Attempt/Call/stage；
- R4 失败输出没有进入业务 Artifact；
- raw Provider envelope、私有推理和凭据没有保存。

仍未实现：

- 完整模型可见请求 capture；
- 非敏感推理参数完整 capture；
- telemetry 的安全字段路径/语义类别与 capture ref/digest 索引。

新增 RC-P36-081 追踪该 runtime gap。

## 运行与安全

- model/provider/network/source/tool calls：0；
- admission/Run/business Artifact：0；
- R4 capture rewrite：0；
- paired/owner/T07/R5：0。

## 验证

- R4 capture、处置合同与既有 capture 原子持久化组合：`15 passed`；
- 完整当前 S4-T06 contract regression：`208 passed / 1771 deselected`；
- JSON、JSONL 与 Python compile：pass；
- 首次完整回归出现的失败仅为历史合法 next-action 枚举不认识新实现项；只扩充后继兼容，不修改运行时、L1 或业务语义。
- Project OS broad full-chain preflight 按预期 fail-closed，列出 4 个 open blocker：RC-P36-067、068、080、081；没有执行 paid/full-chain。

## 下一步

`S4-T06-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-CLASSIFIER-MINIMUM-ZERO-CALL-IMPLEMENTATION`

只允许一个零调用实现包；不自动进入 R5。
