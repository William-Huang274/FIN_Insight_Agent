# FIN 0.1 S4-T06 Claim epistemic-support-role compiled-contract v2 最小零调用实现

日期：2026-07-30

## 结果

唯一授权的 Claim-only 结构包已经实现：

`fin01.s4.deterministic_judgment_atom_planner_and_compiled_contract_invariants:v2`

v2 把 `claim_kind` 与 `support_fact_aliases` 的条件语义从一份 typed rule 同时投影到模型可见合同、wire schema 描述、compiled system instruction、本地校验、selector、fake、mutation 与 typed failure。v1 仍是默认合同，原 model-visible surface、wire 描述、system instruction 与运行语义保持不变。

## 实现的两条 epistemic 路线

1. `insufficient_evidence`
   - `support_fact_aliases` 必须严格为 `[]`；
   - 本地生成 `cannot_infer`；
   - alias expansion 后 `support_fact_ids=[]`；
   - 本地生成至少一个 `cannot_support` 边界。

2. `evidence_direction / economic_mechanism / counterevidence`
   - 必须选择一个或多个唯一、同请求允许的 Fact alias；
   - 本地按 direction 生成 `fact_supported` 或 `bounded_inference`；
   - support alias 精确扩展为 canonical Fact ID；
   - `cannot_support` 只来自已绑定 Fact boundary。

当已绑定 Fact 的边界是不能形成更强判断的原因时，Provider 应编码为 `evidence_direction + unknown/mixed + support aliases`，不得再使用 `insufficient_evidence + support aliases`。

## 不做的事情

- 不修改 canonical Claim schema；
- 不静默改写 Claim kind；
- 不静默删除 support alias；
- 不放宽 epistemic-state hard integrity；
- 不把该冲突降级成质量 finding；
- 不重跑 Claim、不补跑 WWC、不增加第二次 family canary；
- 不签发 R7、不执行 exact-live、不做 paired 或 owner acceptance。

## 验证

零调用测试覆盖：

- v1 默认 ref、Claim model-visible surface、wire 描述和 system instruction 保持兼容；
- `evidence_direction + unknown + support` 正确生成 bounded inference；
- `insufficient_evidence + []` 正确生成 cannot infer；
- `economic_mechanism` 与 `counterevidence` 保留 exact support；
- insufficient/non-insufficient 交叉冲突、空支持、重复支持、unknown/cross-case alias、mixed scope、conflicting concrete scope 均 fail-closed；
- cross-field 冲突使用 typed code `s4_compiled_claim_atom_epistemic_support_role_invalid`，且失败 Claim capture 已在校验前保留；
- DELL、MU、NVDA full-fake 各达到 `6 nodes / 12 callbacks / 12 captures / 9 Artifacts`；
- focused v2+v1=`29 passed`；
- current-chain adjacent=`46 passed`；
- S4-T06 全历史组=`275 passed / 55 failed / 1771 deselected`；55 项归类为旧 current-next allowlist、共享文件整 SHA 冻结、以及后来已物化 identity 仍被旧测试要求 absent，不是本次 v2 行为断裂；
- Python compile 通过；
- model/Provider/network/source/admission/Run/business Artifact/paired/owner/T07 均为 0。

旧 v1 fresh-proof 的两项测试仍冻结共享源文件整文件 SHA，因此新增 v2 后会按设计报 binding drift。v1 语义兼容测试通过，未建立运行时回归；新的 v2 独立 fresh proof 必须重新冻结当前 bindings，不能把旧 proof 冒充为当前证明。

## 证据

- implementation：`configs/releases/fin_ia_0_1_s4_t06_mu_claim_epistemic_support_role_compiled_contract_v2_minimum_zero_call_implementation_v1_0.json`
- source disposition：`configs/releases/fin_ia_0_1_s4_t06_mu_changed_contract_family_single_node_natural_output_canaries_post_result_disposition_decision_v1_0.json`
- test：`tests/contract/test_fin_0_1_s4_t06_mu_claim_epistemic_support_role_compiled_contract_v2_minimum_zero_call_implementation.py`

## 当前状态

RC-P36-083 已从“待实现”推进为“v2 runtime injected / three-case fixture proven / independent fresh proof pending”。RC-P36-080 仍需最终 formal nine-Artifact L1 reproof；S4-T06 尚未通过。

## 下一项

`S4-T06-MU-CLAIM-EPISTEMIC-SUPPORT-ROLE-COMPILED-CONTRACT-V2-INDEPENDENT-FRESH-AGENT-PROOF-DECISION`

下一项仍是零调用独立证明，不自动签发 admission、不执行 DeepSeek，也不恢复第二次 Claim canary。
