# 077 Case Truth claim-polarity 零调用 R4：正式工程门通过

日期：2026-08-17  
Authority：`FIN013-S3-CASE-TRUTH-RECONCILIATION-R4`  
实现基线：`3656fe4bda6aa8c0809ce6737ad9aa1bd182fa43`

## 结论

R4 在零模型、零 Provider、零网络条件下正式通过。它证明新的 provider-neutral 合同能够把“原文声称什么”与“当前 Case 的权威事实是什么”分开，并能表达合法的跨公司背景；它不证明 DeepSeek 会自然完成正确分类，也没有修复或晋升 R7 报告。

## 本轮证明了什么

- semantic submission 改为 `claim_polarity`：`claim_asserts_present`、`claim_asserts_absent`、`claim_asserts_unresolved`、`claim_uses_cross_case_context`；Case Truth 仍只由本地 Validator 裁决。
- 模型只获得 current-cell 可用 alias、case-only outside-cell 紧凑索引、typed gap／bridge 和可见 cross-case context；每个 surface 最多提交 12 个直接 proposition，不能枚举全部 supporting facts。
- R2 的 Operating 9,919 字符旧草稿会在新 submission 前被拒绝；Counterevidence 单 surface 13 条 mapping 也会在调用前被容量门拒绝。
- R7 三条 false absence 被完整保留：当前 AI revenue、AI orders、backlog 已存在，不能被报告写成全案缺失。
- “产品／分部到公司利润桥尚未建立”继续作为合法 typed bridge gap；不能因新增 Case Truth 权威而被误洗成已证明事实。
- 其他公司的合法背景只能作为 `cross_case_context`；若把当前公司事实伪装成 context、引用当前 cell 不可见事实或跨 case 污染，均 fail closed。
- DELL／MU／NVDA 与留出案例、顺序扰动、未知 alias、digest 漂移、漏 slice／重叠 slice、13 proposition 等 mutation 全部通过。

## 机器结果

- public result：`configs/research/evals/fin_ia_0_1_3_s3_case_truth_reconciliation_zero_call_result_v1_3.json`
- public digest：`0a8393bfd5aad4e1f1fccf0437d4edef2eb4491e00d14fa48441cd794014286e`
- private full result SHA-256：`17da3ad9949d037ccce28724320f4af56534f3799895f68464d22b74fe1228f1`
- DELL／MU／NVDA presence 数量：`61 / 49 / 55`
- DELL typed gap／bridge：`7 / 1`；MU／NVDA typed gap：`10 / 10`
- 最大 analysis slice：22,075 字符；最大 strict submission 输入：4,136 字符；最大 canonical tool：5,367 字符。

## 边界与下一步

R4 状态只能记为 `zero_call_case_truth_claim_polarity_engineering_pass`。自然 semantic extraction、R7 Judgment 修复、Synthesis、DELL 内容验收、MU／NVDA／留出泛化、S3 acceptance、Workbench publication 和 release 仍为 false。

下一步只允许在新的 clean/synced commit 上签发一次两单元 successor：Operating 与 Counterevidence 各一次 non-thinking analysis 和一次 4k strict submission，共最多 4 次调用、0 retry。只有自然结果能识别三条 false absence、保留利润桥 typed gap、正确处理跨公司 context 并显式暴露真实 outside-cell claim scope，才考虑受影响 Judgment／Synthesis 的最小修复。
