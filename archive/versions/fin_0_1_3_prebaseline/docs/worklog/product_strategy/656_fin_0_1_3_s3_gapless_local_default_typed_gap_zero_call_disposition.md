# 656 — FIN 0.1.3 S3 gapless local-default typed gap 零调用处置

日期：2026-08-06

R2 失败保持不可变。本轮只修复其结构根因，没有签发 R3、调用模型、Provider、网络或来源。

S3 evidence-role v2 compiler 现在检查上游 gap surface：仅当 request 的 `gap_options=0`，且 Provider 返回一致的 `epistemic_state=answer_direction=cannot_infer` 与空 gap list 时，本地才基于 request ID 和 decision question 生成唯一默认 typed gap。这个 gap 表达“所选证据不足以回答当前问题”，`source_exhaustion_proven=false`，Provider 不能编写或选择其文案。若 request 原本存在 gap option 而模型漏选，旧硬失败保持不变。

R2 的 MU value/profit raw alias 输出已在零调用测试中重放：MU consolidated/DRAM Evidence 保持 `boundary_only`，本地默认 gap 阻止它们被误升格为 HBM revenue/profit/PVM 证据。typed-gap 要求没有放宽，模型可见 context 也没有改变。

formal Anchor 与单节点 canary terminal 现在会在 JSON 解析后、业务校验前保存 `provider_output_raw` 与 digest；若发生本地 normalization，则保存独立 digest-bound receipt。这样以后无需依赖私有 capture 才能知道模型实际返回了哪些安全 alias，同时 raw failure 仍不能晋升成 Claim 或 Artifact。

验证：focused=`15 passed`；canonical=`249 passed / 1 historical assertion deselected`；九节点 full-fake 可到 Claim/Lead/Workpaper/quality entry；existing-gap omission、alias overlap 和投影篡改继续 fail closed。R3 admission 未授权，下一项为独立权限决策。
