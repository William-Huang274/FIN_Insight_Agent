# FIN 0.1 S4-T05 R10 来源约束基线与配对 L1 失败

日期：2026-07-28

## 结果

R10 的 success-only paired assessment 已完成，但不能签发 owner acceptance，也不能进入 S4-T06。

同一 DELL Case、DecisionSurface 与 paired input-head 上已物化一个独立的来源约束确定性 baseline：

- WorkUnit / Attempt / ResearchRun=`succeeded / succeeded / succeeded`；
- Artifact=4；
- exact deterministic Run cardinality=1；
- model、provider、network、source、tool、evidence promotion、Agent rerun与 owner write 均为 0；
- 未使用会返回 NVDA 历史内容的 legacy P36 analysis preview。

## 配对结论

R10 Agent 相比 baseline 提供了明确的分析与行动增益：

- claims=6；
- what-would-change tasks=8；
- cross-Cell dependencies=3；
- conflict adjudications=3；
- selected gaps=4。

但 L1 hard integrity 失败，增益不具备验收资格。

### RC-P36-067：数值 authority 对应关系漏检

R10 多条叙事数值与其自身声明的 exact Numeric support refs 不一致。三个独立确认示例：

- Agent 写 Q1 FY27 AI server orders `$4.1B`，对应 authority 为 `24400 USD_millions`；
- Agent 写 Q1 FY27 AI server revenue `$1.7B`，对应 authority 为 `16132 USD_millions`；
- Agent 写 free cash flow 为负，authority 则为正 `3118 USD_millions`。

责任分为两层：模型生成了不受绑定 Numeric rows 支持的数值叙事；项目 Validator/Verifier 只校验 ref membership、shape 与 Cell scope，没有确定性比较 metric、value、unit、scale、period、business scope、comparator 与 sign，因此错误被机器验收为 `accept_for_internal_review`。

### RC-P36-068：公司身份标题硬编码

DELL R10 报告标题为 `NVDA 三单元内部研究备忘录`。Writer 请求、局部 Validator 与 fake Provider 合同保留了 S3 NVDA 硬编码，模型遵循了错误项目指令。该问题属于 L1 entity identity，不是可以忽略的 L4 文案瑕疵。

## 阶段决策

- paired assessment=completed；
- R10=`material_gain_not_admissible_because_L1_numeric_and_entity_identity_fail`；
- DELL R2=not proven；
- owner acceptance=`not_eligible_while_L1_fails`；
- S4-T06=not entered；
- R10 与 baseline 均保持 immutable，不做静默修订。

下一项仅允许零调用根因处置：

`S4-T05-DELL-R10-NUMERIC-AUTHORITY-AND-CASE-IDENTITY-FALSE-NEGATIVE-ZERO-CALL-ROOT-CAUSE-DISPOSITION-DECISION`

结构性方向是让模型选择 exact Numeric refs 与有限解释原子，由本地确定性渲染数值并执行 exact correspondence；所有 entity-bearing delivery fields 必须从 case-local identity contract 派生。完成 fixture proof 与新的独立 authority 前，不再发起付费 exact-live。

## 证据

- baseline result：`configs/releases/fin_ia_0_1_s4_t05_dell_r10_source_grounded_deterministic_baseline_materialization_v1_0.json`
- paired assessment：`configs/releases/fin_ia_0_1_s4_t05_dell_r10_success_only_paired_assessment_and_owner_acceptance_decision_v1_0.json`
- baseline decision：`configs/releases/fin_ia_0_1_s4_t05_dell_r10_source_grounded_deterministic_baseline_materialization_decision_v1_0.json`
- source decision：`configs/releases/fin_ia_0_1_s4_t05_dell_r10_success_only_paired_baseline_source_decision_v1_0.json`
- contract test：`tests/contract/test_fin_0_1_s4_t05_dell_r10_source_grounded_baseline_and_paired_assessment.py`

## 验证边界

本轮完成的是零调用 baseline 物化与只读配对判断，不包含根因修复、R11 admission、R11 exact-live、owner acceptance 或 T06。历史全量分支仍包含独立的陈旧 backlog expectation、历史 exact-code-hash binding 与 fixture lineage 失败；这些不能通过改写历史合同来伪装为通过，本轮以新增合同测试、JSON/JSONL 解析、只读 baseline verify 和针对性 preflight 为收口标准。
