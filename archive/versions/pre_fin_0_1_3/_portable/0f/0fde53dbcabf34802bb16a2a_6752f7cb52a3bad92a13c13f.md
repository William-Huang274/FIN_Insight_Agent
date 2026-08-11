# 450｜FIN 0.1 S4-T06 入口 server-subset-conformant replacement 最小零调用实现

日期：2026-07-29

## 结论

一次性 replacement zero-call implementation bundle 已消费并通过 deterministic fixture。

当前 strict truth-kernel 明确拆成三层：

- semantic owner：`fin01.s4.strict_truth_kernel.numeric_judgment_selection:v2`；
- OpenAI server compiler：`fin01.provider.openai_structured_outputs_supported_subset:v1`；
- local validator：`fin01.s4.strict_truth_kernel.local_semantic_validator:v1`。

服务端 Responses schema 不再包含 `uniqueItems`，只允许 `type/properties/required/additionalProperties/items/minItems/maxItems/enum`。本地仍在 Artifact 前硬拒绝 duplicate numeric alias、duplicate counterevidence alias、wrong/cross-case alias、invalid enum 与 numeric mutation，L1 没有降级。

实现工件 SHA-256：`54012a8f7e2ede6206f711516ac669d4dcdb33046d8e6d2192c5382db6e48618`。

## 实现

`OpenAIStructuredOutputsSubsetCompiler` 现在：

- 从 semantic schema 编译 Provider wire schema；
- 只移除显式登记的 local-only `uniqueItems:true`；
- 遇到其他未知 keyword 时 fail-closed；
- 检查 object 的全字段 required 与 `additionalProperties:false`；
- 检查 array items 以及 `minItems/maxItems` 边界。

`StrictTruthKernelPolicy` 现在分别暴露：

- `semantic_json_schema()`；
- `server_json_schema()`；
- backward-compatible `json_schema()`，其含义为 exact Provider wire schema。

Prompt 与 Responses adapter 均消费 `server_json_schema()`；Prompt 同时携带 compiler/local-validator refs 和本地 uniqueness rules。registered failure descriptor 与 truth-kernel v2 使用同一个共享合同常量，避免版本再次漂移。

## Fixture 证明

- DELL/MU/NVDA 的 semantic schema 均保留 local `uniqueItems` marker；
- 三案 server schema 均不含 `uniqueItems`，且所有 schema keyword 位于冻结 allowlist；
- 三案完整 full-fake 仍达到 `6 nodes / 12 callbacks / 12 captures / 9 Artifacts`；
- duplicate counterevidence 在 unit 与完整 runtime 负例中均形成 `counterevidence_alias_duplicate`，首个 Artifact 前停止；
- unknown server keyword、invalid required contract、wrong/cross-case alias、numeric mutation、extra text、invalid enum、duplicate numeric alias 与 missing capability 均 fail-closed；
- atomic failure integration 继续形成 `failed/failed/failed`，保留 12 receipts/captures、0 Artifact、1 Attempt。

## 验证

- replacement focused 与历史 decision 合计：`33 passed`；
- shared-runtime adjacent regression：`61 passed`；
- Python compile：pass；
- 4 个 JSON 与 3 个 JSONL 严格解析及 duplicate-key 检查：pass；
- 下一 scope Project OS preflight：`pass/open blocker count=0`；
- secret scan、`git diff --check` 与 trailing-whitespace：pass；
- actual model/provider/network/source/tool/credential/admission/Run/business Artifact/paired/Human 均为 0。

## 状态与下一项

RC-P36-070 更新为 `replacement_fixture_proven_fresh_engineering_proof_pending`，尚未关闭。RC-P36-067 继续等待 future live requalification；RC-P36-068 carried-open；RC-P36-069 保持关闭。

S4-T05 仍 blocked/not passed/not owner accepted；DELL R2 未证明；S4-T06 尚未进入。

下一项：

`S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-REPLACEMENT-FRESH-ENGINEERING-PROOF-AND-PROVIDER-CAPABILITY-BINDING-DECISION`

该项需另行授权。它只允许独立复算 code/schema、重新判断 exact request-level binding；不得读取凭据、运行 canary、签 admission 或进入 MU。

## Git

工作树在本轮开始前已包含大量 mixed staged/unstaged/untracked 历史变更。本轮保留这些用户状态，不 stage、不 commit。
