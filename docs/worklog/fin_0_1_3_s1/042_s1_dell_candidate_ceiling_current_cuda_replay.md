# S1 DELL Candidate Ceiling 当前 CUDA 产品回放

日期：2026-08-18

状态：`real_current_replay_complete / candidate_ceiling_observable / source_sufficiency_and_product_decision_open / S1_not_qualified`

## 本轮做了什么

从干净提交 `37d69688...` 复用不可变的 DELL R3 自然材料范围，经过当前 Workbench 产品运行时执行 8 条 EvidenceRequest。运行使用当前 20,761 对象库、BM25＋Qwen dense、RTX 4060、FP16；模型、网络和 CPU 向量回退均为 0。私有文件保存完整候选，公开文件只保留计数、阶段与 digest，不泄露候选 ID。

## 真实业务结果

8 条请求都形成可执行材料范围，但只有 3 条形成完整候选材料组。12 个材料要求中，7 个完整保留到审阅面，5 个在 bounded union 内仍不完整；没有任何一个是“并集里已完整、后来被 16 条审阅窗截掉”。

五个不完整项不能合并成一种故障：

1. orders/backlog 已找到 Dell 关于 AI demand、elevated backlog、customer readiness 和 shipment timing 的直接披露，但精确 orders、backlog composition、shipments、customer count 仍未形成完整数值面；
2. reported results 已有 ISG revenue／operating-income 表与 AI-server growth 叙事，但不能把总 segment／EPS 变化直接归因给 AI servers；
3. margin 已有 AI-server revenue driver 与 ISG margin，但没有单独披露 incremental AI-server margin；
4. cash 已有 company cash flow 与 AI demand/payment-term 风险，但没有 AI revenue→cash conversion 的直接桥；
5. working capital 已有集中客户、较长账期、component commitment 和 inventory 风险，但没有 AI-specific receivable／inventory allocation。

因此，这些状态分别包含“已有材料但只能支持边界判断”“S2 有公司数字但缺产品归因桥”“可能在 64／96 候选上限之外”“来源或解析是否真的缺失尚未裁决”，不能统称公开资料 gap。

## 工程含义

RC-S1-035 的产品可观测 seam 已在真实 DELL 路径证明：产品现在能区分 Hybrid 未运行、材料在 bounded union 内不完整、以及完整材料在 union 后被截断，并固定拒绝由候选数量授予 public-gap 权威。

但当前每条请求的 BM25 64、Qwen 64 和 union 96 都触顶，且产品运行时明确显示 `financial_ranking_enabled=false`、`evidence_role_advisory_enabled=false`。这不是调大上限的理由，而是说明后续产品 producer 必须消费阶段收据、S2 NumericFact 和 reviewed Evidence；不能把 BM25＋Qwen top16 当成完整 S1，也不能把候选相似度当成 Evidence 判断。

## 下一步边界

先用同一合同建立 MU／NVDA 当前请求并做零模型 CUDA 回放，确认这不是 DELL 特例。之后实现产品级 EvidenceDecision／GapEligibilityReceipt／PackReadiness producer，并显式决定金融精排与 Evidence Role 是否进入当前 Runtime。source disclosure、OCR／parse 内容充分性和可达外源路线耗尽继续独立验收；S1、动态 S3、发布与 release 均未通过。

## 验证

- DELL 公开结果所绑定的私有 full result SHA-256 与实际文件一致；公开结果绑定干净提交 `37d69688...`。
- candidate-ceiling、current runtime binding、material-scope canary 与 Project OS 定向测试：`59 passed`。
- Python compileall：通过；active baseline：165 Python／8 frontend／22 Runtime resources／0 forbidden reference。
- JSON／JSONL 解析与 `git diff --check`：通过；secret scan：7,202 files／0 findings。
