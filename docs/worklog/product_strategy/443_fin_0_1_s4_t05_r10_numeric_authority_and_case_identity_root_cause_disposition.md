# FIN 0.1 S4-T05 R10 数值 authority 与 Case identity 零调用根因处置

日期：2026-07-28

## 权限与结果

用户以“继续”授权：

`S4-T05-DELL-R10-NUMERIC-AUTHORITY-AND-CASE-IDENTITY-FALSE-NEGATIVE-ZERO-CALL-ROOT-CAUSE-DISPOSITION-DECISION`

本轮完成根因定位与结构方案冻结。没有修改 runtime、调用模型或 Provider、读取 restricted capture、签发 admission、创建 Run/Artifact、改写 R10、签 owner acceptance 或进入 S4-T06。

决策工件：

`configs/releases/fin_ia_0_1_s4_t05_dell_r10_numeric_authority_and_case_identity_false_negative_zero_call_root_cause_disposition_v1_0.json`

## RC-P36-067：最早数值错误合同

DELL source-grounded `cell_input.numeric_input` 中确实存在完整 exact Numeric rows，但它们没有完整进入 Specialist model view。S4 rows 使用平铺的 `numeric_ref/value/comparison_operator/entity_ref/period/...`；共享 model-view adapter 仍按 legacy `financial_row_id/normalized_value/nested selector` 取值。零调用重现显示一条完整 S4 row 到模型侧只剩 `scale_multiplier` 与空 `selector`，而 `authority_refs.numeric_refs` 仅提供不带值的 opaque ref。

因此最早项目错误位于 S4 flat Numeric row → legacy selected-financial-row model view/authority projection adapter。第一个 Provider 错误自由度随后位于 `facts_explanation_and_terminal.fact_layer.statement`：

- Provider 在没有获得 ref 对应 value/metric/period/operator/unit 的情况下仍自由撰写了具体数字，而不是保持 cannot-infer；
- `FactSupportAuthorityPolicy` 只校验 support type 和 ref membership；
- 不比较 statement 中的 metric、value、operator、period、unit、scale 或 sign。

随后错误可以继续传播：

- Claim statement 仍为自由文本，scope resolver 只检查 scope，不检查数值；
- Writer-v3 Provider 仍自由撰写 `analysis_text_zh_cn`；
- `_owner_grade_authority_surface` 同样要求 legacy `financial_row_id + selector`，因此对 R10 的 S4 Numeric refs 形成空 projection；
- Verifier 本地合同验证 state machine、typed refs 和 digest，不重算数值。

所以 RC-P36-067 同时包含：

- 项目先把完整 S4 Numeric rows 错投影成 opaque refs，未把 exact value surface 给到模型或 Verifier；
- 模型在缺少 exact values 时仍生成了不受支持的具体数字；
- 项目又没有建立确定性 value-authority correspondence，最终导致 machine-Verifier false negative。

## RC-P36-068：最早身份错误合同

R10 使用 Memo Writer v3。Provider 只返回 `claim_ref + analysis_text_zh_cn`，不返回标题。

错误标题来自本地：

- `_assemble_memo_writer_v3_output` 写死 `NVDA 三单元内部研究备忘录`；
- `_validate_owner_grade_writer_output` 又强制标题必须等于这个 NVDA 字符串；
- generic/fake Writer schema 也保留同一硬编码。

因此这是项目内 case delivery identity projection 缺失，不是模型不遵循。

## 选定结构方案

### 数值合同

选择：

`fin01.s4.case_numeric_authority_projection_and_deterministic_rendering:v1`

原则：

- 先将 S4 flat rows 与 legacy rows 归一到同一个版本化 canonical projection，禁止两套 schema owner；
- 每个 Numeric ref 投影 exact entity、scope、period、metric、operator、value、currency、unit、scale、lineage 和 cannot-support；
- Provider 只选择 request-local numeric aliases 与有界 qualitative interpretation atoms；
- Provider 自由叙事不得承载 material numeric value、金额、百分比或 sign；
- exact numeric clause 只由本地 projection 渲染；
- Specialist、Lead、Writer 等可承载数值的节点后与 Artifact commit 前独立重算；
- 模型 Verifier 不再是 numeric truth owner；
- Prompt schema、local validator、fake Provider 与 typed telemetry 从同一 policy 生成。

自由文本 numeric token detector 只能作为负向 guard，不能成为主要 correspondence 合同。

### 身份合同

选择：

`fin01.s4.case_delivery_identity_projection:v1`

标题和所有 entity-bearing delivery fields 必须从 `input_pack.company` 与 S4 case-runtime binding 派生。标题规则为：

`{case_ticker} 三单元内部研究备忘录`

Provider 没有标题写权限；禁止 DELL、MU、NVDA ticker 分支或常量特判。

## 明确拒绝与后传

拒绝：

- 再加强 prompt；
- 用 regex 解析任意自由叙事作为主要 truth 合同；
- 静默修正 R10 数字或标题；
- 将数值或 issuer identity 降级为 L2/L3/L4；
- 在项目 false negative 未修前先换模型；
- 带着 L1 缺口进入 MU 或 S4-T06。

继续后传到 S4-T10/S5：

- general all-node judgment atom framework；
- dependency/conflict/gap 全面确定性组装；
- cross-provider strict server-side schema matrix；
- cross-stage Claim/Task identity redesign。

## 下一步

`S4-T05-DELL-CASE-LOCAL-NUMERIC-ATOM-DETERMINISTIC-RENDERING-AND-DELIVERY-IDENTITY-MINIMUM-ZERO-CALL-IMPLEMENTATION`

该步骤需要独立授权。实现必须先通过 22 条 DELL exact Numeric、2 条 derived metric、错值/错 period/错 unit/错 scale/错 sign、DELL/MU/NVDA identity 正负 fixture，以及零调用 6-node/12-callback/9-Artifact fake full-chain。之后才可独立决定 fresh proof、admission、canary 或 exact-live。

## 本轮验证

新增根因合同测试首次运行时因为预期 Verifier projection 能找到 current Numeric ref 而失败；该失败揭示了更早的 S4-flat-row → legacy projection schema drift。修正根因描述和测试后：

- R10 disposition + paired-assessment focused tests：`9 passed`；
- raw S4 row 的 exact value/operator fields 存在；
- Specialist model view 实测仅保留 `scale_multiplier + empty selector`；
- Verifier numeric projection 实测为空；
- membership-only policy 对错误数值 statement 返回无 violation；
- Writer-v3 NVDA 本地 assembly、validator 与 schema hardcode 均确认存在。

因此本轮不是用测试为既定结论背书，而是由失败测试把最早 owner 从自由叙事层进一步上移到 S4 Numeric adapter 层；选定的结构合同不变，但 implementation 顺序已修正。
