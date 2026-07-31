# FIN 0.1 S4-T06 Claim compiled-contract v2 post-result disposition

日期：2026-07-30

## 问题

changed-contract canary 的 Fact family 通过；Claim family 返回正常 native JSON，但本地 selector 报 `s4_compiled_claim_atom_no_valid_scope_compatible_subset`。本项按冻结权限只读取受限 Claim capture、exact request、确定性 seed 和 selector，不调用模型，不补跑 WWC。

## 零调用复现

- Claim 只有一个候选和一个合法 request-local Fact alias。
- alias 不存在 unknown、跨案、mixed scope 或 concrete scope conflict。
- Provider 选择 `claim_kind=insufficient_evidence`，同时选择一个 Fact alias。
- selector 的首个拒绝条件是：`insufficient_evidence` 必须绑定空 `support_fact_aliases`。
- exact request digest 与 capture readback 均通过。

## 最早根因

这个条件规则只存在于本地 selector，没有进入 model-visible compiled contract、wire schema 描述或 system instruction。fake Provider 只覆盖带事实的 `economic_mechanism` 路线，也没有覆盖：

- `insufficient_evidence + []` 正例；
- `insufficient_evidence + non-empty aliases` 负例；
- 带边界事实、但应编码为 `evidence_direction + unknown` 的 bounded-inference 路线。

因此 RC-P36-083 的 fixture/fresh-proof 关闭过早，现以 live semantic-parity recurrence 重开。当前证据不支持把失败归因为 DeepSeek、transport、JSON、跨案 alias、seed 不可满足或 scope selector 冲突。

## 两条合法 canonical 路线

使用同一冻结输入做零调用反事实：

1. 合法 Fact alias + `evidence_direction + unknown`：下游严格验证通过，形成 `bounded_inference`、一个 support Fact 和一个不能支持的边界；
2. `insufficient_evidence + []`：下游严格验证通过，形成 `cannot_infer`、零 support Fact 和一个确定性边界。

这说明无需弱化 canonical epistemic-state，也无需静默改写模型的 claim kind；需要把现有条件语义完整编译给 Provider。

## 决策

选择唯一后续包：

`fin01.s4.deterministic_judgment_atom_planner_and_compiled_contract_invariants:v2`

范围只包括 Claim family 的 claim-kind/support-role 条件编译。model-visible contract、wire schema 描述、system instruction、selector、fake、mutation 和 typed failure 必须从同一规则生成。

禁止：

- 静默把 `insufficient_evidence` 改写为其他 kind；
- 静默删除 support aliases；
- 放宽 cannot-infer hard integrity；
- prompt retry、Claim 重跑或 WWC 补跑；
- 修改 canonical Claim schema；
- 在本实现后增加第二次 Claim 单节点 canary。

原先每 family 一次的 canary 配额已经消费。v2 实现和独立 fresh proof 通过后，仍只保留一次最终 MU formal exact-live 上限；若再次出现新 L1，则项目级停止，不进入 R8 或新字段修补循环。

## 证据与验证

- decision：`configs/releases/fin_ia_0_1_s4_t06_mu_changed_contract_family_single_node_natural_output_canaries_post_result_disposition_decision_v1_0.json`
- decision SHA256：`5b30ba5969493945f4c57a4fb6918a83e87351490502a9b2b8fe7ed21c396745`
- source result SHA256：`410051c4dc94eb94c8d2f06fbc601e57dfc5b8e759cb6a938bbc17d99d7ae9bb`
- Claim capture digest：`e13a113e7c8ead1583ca60562c96d1a5e6cfa2b723d53415cd725d230ef56b17`
- restricted raw request/output 未复制到 decision 或 worklog。
- 本轮 model/Provider/network/source/admission/Run/Artifact/paired/owner/T07 均为 0。

## 下一项

`S4-T06-MU-CLAIM-EPISTEMIC-SUPPORT-ROLE-COMPILED-CONTRACT-V2-MINIMUM-ZERO-CALL-IMPLEMENTATION`

下一项尚未在本决策中自动授权。
