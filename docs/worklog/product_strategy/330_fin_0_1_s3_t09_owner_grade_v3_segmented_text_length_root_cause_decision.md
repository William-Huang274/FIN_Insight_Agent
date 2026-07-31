# FIN 0.1 S3-T09 owner-grade v3 segmented text-length root-cause decision

日期：2026-07-22

## 授权与边界

用户以“授权”只允许 `S3-T09-OWNER-GRADE-V3-SEGMENTED-FIRST-SEGMENT-TEXT-LENGTH-FAILURE-RESULT-AND-ROOT-CAUSE-DECISION`。本轮没有实现代码、签发或消费 admission，也没有模型、Provider、网络、source、tool、canonical execution、paired comparison 或 Human Review。

## 判断

真实 Run 已证明 Provider HTTP/transport、`finish_reason=stop`、native JSON、首段 exact keys、Cell binding、`explanation_layer` list/cardinality 全部通过；失败仅落在“每项必须是非空 string 且不超过 320 Unicode 字符”的组合谓词。由于 raw output、item index 和 item length 未持久化，历史 subtype 仍不能在非 string、空白、超长之间重建。

直接失败类是 Provider 模型输出未满足应用文本合同，但这不足以证明“DeepSeek 模型本身有问题”。代码级最早 owned repair surface 是 segmented request：schema 只写 `explanation_layer: ["string"]`，320 上限只作为一次跨字段 constraint；system prompt 虽要求把 constraints 当规则，却漏掉 monolithic 路径已有的逐项 cardinality/character/byte limit 与 concise typed boundary 指令。与此同时，当前安全遥测把三个可行动 subtype 合并。

因此选择 versioned transport `fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v2`：保持 canonical output-v3 和本地 320 上限不变；在每个 narrative field 本地重复非空 string/≤320 合同，要求响应前逐字段检查与简洁表达；未来只保存 closed field/subtype/failing-count。禁止 truncate、trim 成合法、coerce、drop、join/split、放宽 validator 或自动 retry。

## 证据与下一项

机器决策：`configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_first_segment_text_length_failure_root_cause_decision_v1_0.json`。定向合同测试首轮 `5 passed`；完整 S3-T09 合同回归 `128 passed in 279.21s`；Project OS 授权与收口 scoped preflight 均 pass/open blocker=0。研究质量没有提升，0 新 Artifact/Evidence/Numeric/Alpha，T09 继续 blocked。

当前唯一下一项是 `S3-T09-OWNER-GRADE-V3-SEGMENTED-FIELD-LOCAL-TEXT-CONTRACT-AND-SAFE-SUBTYPE-TELEMETRY-ZERO-CALL-IMPLEMENTATION`，需单独授权。该项只能实现与 fake Provider fixture 验证；不能签发 admission、真实调用模型、重跑、比较 baseline、执行 Human Review 或进入 T10。
