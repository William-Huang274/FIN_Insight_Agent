# 447｜FIN 0.1 S4-T06 入口 shared-runtime blocker 最小零调用实现

日期：2026-07-28

## 授权与边界

用户以“继续”授权执行处置文件冻结的唯一一个：

`S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-MINIMUM-ZERO-CALL-IMPLEMENTATION`

本轮不允许模型、Provider、网络、source、tool、credential probe、canary、admission、WorkUnit、Attempt、ResearchRun、business Artifact、paired assessment、Human review、MU T06、DELL R12、S5 或第二个 repair bundle。

## 实现结果

### Strict truth kernel

新增 `fin01.s4.strict_truth_kernel.numeric_judgment_selection:v1`：

- 首个 Specialist `facts_explanation_and_terminal` 通过 strict JSON Schema；
- Provider 只返回绑定当前 Case numeric projection digest 的 opaque Numeric/Evidence aliases、direction/materiality/confidence/interpretation enums、counterevidence aliases 与 terminal enum；
- Provider 不拥有 arbitrary free text、material numeric value、period、currency、unit、entity/title、canonical ID、rendered sentence 或 lineage；
- Local Runtime 确定性生成 canonical Fact identity、exact numeric clause、scope、identity、ordering、lineage，并由既有 numeric precommit gate 独立重算 L1；
- `N001` 型跨 Case 可重放别名被替换为 Case-projection-scoped opaque alias。

### Capability binding

新增 `fin01.provider.capability.strict_json_schema:v1` admission binding。严格 truth-kernel admission 未绑定匹配 adapter 时，在 credential 检查与 Provider 调用之前以 `s4_strict_truth_kernel_capability_unbound_pre_provider` fail-closed。

本轮只证明 adapter/factory/fake route；没有证明任何真实 credential、model 或 endpoint 可用。

### Atomic failure terminal

新增共享 failure observation policy：

- terminal core、counts、receipts、captures 与三态 transition 不依赖 optional telemetry extension 成功；
- known S4 numeric/identity telemetry 在 canonical boundary 转为 registered content-free descriptor；
- unknown、invalid 或 secret-like extension 不持久化正文，只追加 `s3_bounded_failure_observation_extension_rejected`；
- facade 接受注册描述符与 S4 typed failure namespace；
- 历史直接 error telemetry shape 保持兼容，旧 admission digest 不因新增 optional fields 变化。

## 验证

三案例完整 fake：

| Case | strict Responses | 后续 Chat | 总 callbacks | captures | logical Artifacts |
| --- | ---: | ---: | ---: | ---: | ---: |
| DELL | 3 | 9 | 12 | 12 | 9 |
| MU | 3 | 9 | 12 | 12 | 9 |
| NVDA | 3 | 9 | 12 | 12 | 9 |

负向 fixture 覆盖：

- wrong alias；
- cross-case alias；
- numeric mutation；
- extra text；
- invalid enum；
- duplicate alias；
- missing strict capability pre-provider；
- registered failure observation；
- unknown secret-like failure extension。

后两类 canonical integration 均形成 `failed/failed/failed`，保留 12 receipts 与 12 captures，Artifact=0、Attempt=1，unknown secret-like 正文未进入事件。

测试结果：

- focused：`18 passed`；
- T05 numeric/identity + typed envelope + capture regression：`52 passed`；
- Python compile：pass；
- Ruff：当前环境未安装，未执行。

## 产物

- `configs/releases/fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_minimum_zero_call_implementation_v1_0.json`
- `src/sec_agent/canonical_runtime/failure_observation_policy.py`
- shared policies/executor/facade 更新；
- `tests/contract/test_fin_0_1_s4_t06_entry_shared_runtime_blocker_minimum_zero_call_implementation.py`
- program/S4 backlog、产品审计、S4 execution plan 与 Project OS 同步。

## 当前状态与下一项

- S4-T05：`blocked / not passed / not owner accepted`；
- DELL R11：immutable；
- DELL R12：forbidden；
- S4-T06：not entered；
- 唯一 zero-call implementation bundle：已消费并 fixture-proven；
- 第二个自动修复包：禁止。

当前唯一下一项：

`S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-FRESH-ENGINEERING-PROOF-AND-PROVIDER-CAPABILITY-BINDING-DECISION`

该项需独立授权，只允许 fresh engineering proof 与 exact Provider credential/model capability binding 决策。不得自动 probe credential、执行 canary、签 admission 或进入 MU T06。其后若另行授权 single-node canary，最多一次；失败即停，不 retry、不 provider hopping、不 full-chain。
