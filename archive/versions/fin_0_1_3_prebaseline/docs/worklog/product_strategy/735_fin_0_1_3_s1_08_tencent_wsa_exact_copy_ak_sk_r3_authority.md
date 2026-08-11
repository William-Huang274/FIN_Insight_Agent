# FIN 0.1.3 S1-08 Tencent WSA exact-copy AK/SK R3 authority

日期：2026-08-08
状态：`zero_call_contract_pass / authority_issued_unconsumed`

## 为什么允许 R3

R2 已不可变地保留为 `AuthFailure.SignatureFailure`。它使用截图中人工转录的大小写敏感 AK/SK，因此“字符抄错”只是最可能但未证明的原因之一。Owner 本轮直接提供了一组新的标准 Tencent Cloud AK/SK 文本，并明确要求再试一次；这消除了截图 OCR／人工识别歧义，但不证明该凭据有效、具备 CAM 权限或已开通 WSA。

因此本轮没有重用已消费的 R2 authority，而是建立独立 R3：

- attempt：`fin013-s1-08-tencent-wsa-exact-copy-ak-sk-r3`
- predecessor：`fin013-s1-08-tencent-wsa-query-only-replacement-r2`
- scope：`S1_08_PAID_BROAD_SEARCH_TENCENT_WSA_EXACT_COPY_AK_SK_R3_DIAGNOSTIC`
- 凭据只允许在运行时 hidden input 输入；值不进入 Git、authority、capture 或 terminal
- wire body 继续严格为 `{Query}`；全部 optional field 继续禁止
- provider/network ceiling=`1/1`，retry/model/document/Evidence=`0/0/0/0`
- 成功或失败均保存 credential-free terminal 并停止；不自动进入 R4、三案 comparator 或 SourceHunter 集成

## 零调用实现与证明

新增独立 R3 support、runner、result namespace、registered scope、contract test、zero-call proof 与 authority。历史 R1/R2 文件没有修改。R3 authority 绑定：

- R2 result 与 failure assessment SHA/digest
- provider profile SHA/digest
- Query-only compiler、normalizer、SDK runner helper SHA
- R3 support、runner 与 zero-call proof SHA/digest

验证结果：

- focused tests：`21 passed`
- Python compile：`pass`
- Project OS scoped preflight：`pass`
- optional-field mutation：`Mode/Site/Cnt/Freshness` 均在 transport 前拒绝
- provider/network/retry/model/document/Evidence：`0/0/0/0/0/0`
- credential values persisted：`false`

## 当前边界与下一步

这只是可执行合同和权限签发，不是 live 成功。必须先把实现、proof 与 authority 提交并推送为 clean Git head，随后才可消费一次 R3。若 R3 返回任何失败，立即保存并停止；若返回 Pages，也只能进入 locator/date 诊断，不得自动晋升为 Evidence 或生产搜索能力。

本轮凭据已在聊天明文出现，无论 R3 结果如何，运行后都应在腾讯云控制台删除或轮换。
