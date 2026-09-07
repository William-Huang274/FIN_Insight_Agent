# S1 VS5 COST request／reference 一致性人工复核包

日期：2026-08-18

状态：`packet_ready / qualified_human_decision_pending / historical_R1_R2_immutable`

## 核对结果

COST temporal 的冻结请求只包含 revenue、gross margin、operating cash flow，产品意图只是 FY2024／FY2025 comparison；provisional reference 的五条正例中，两条却是 FY2024／FY2025 会员经营结果。这两条可能对研究 Costco 有用，但没有被本次 temporal request 授权，不能把“有用”直接等同于“本题必答”。

复核包绑定 input、reference 和 R2 evaluation 的文件摘要，并提供两个合法选项：

1. 未来题目若确实要求会员经营比较，必须先在 EvidenceRequest 显式加入会员费、续费率、Executive membership 及对应 facet，然后再冻结 reference；
2. 未来题目继续保持当前范围，则 reference 只保留收入、毛利和经营现金流的同口径材料组。

当前 Codex 的非权威建议是第二项：评测范围应服从运行前请求。若产品要扩大问题，就在未来请求层公开扩大，不能事后扩金标。

无论人工选择哪一项，历史 R1／R2 都不重算、不改写、不转为通过；COST R3 继续禁止。即使仅作诊断性删除两条争议正例，R2 也只是 `15/18=0.833333`，仍低于 `0.90`，所以这不是“删两条答案就过关”的包。

## 待人工填写

机器包：`configs/retrieval/fin_ia_0_1_3_s1_vs5_cost_reference_consistency_qualified_human_review_packet_v1_0.json`。

必须由 qualified human 或 Owner 明确授权的独立评审填写 reviewer、qualification basis、selected option、reason、review time 和签名／外部 receipt。当前实现 Agent 不代签，也不据未签包生成 blind labels。

三个绑定文件的 SHA-256 已逐一复核，packet／Project OS JSON 解析通过；repository secret scan 为 `7,142 files / 0 finding`。

## 产品影响

本包只解决未来 request／reference 的边界，不修复候选排序，也不证明 material Evidence Set 已接入 Runtime。S1、hidden qualification、完整 S1→S3 和发布状态均不改变。
