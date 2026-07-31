# 449｜FIN 0.1 S4-T06 入口 shared-runtime post-proof program scope-replace 决策

日期：2026-07-28

## 结论

本轮签发 `scope_replace`，不选择永久停止，也不把删除一个 `uniqueItems` 伪装成上一实现包的局部修补。

新的 program-level 合同把语义/本地合同与 Provider wire schema 明确分层：

- 服务端 strict schema 只使用 OpenAI Structured Outputs 官方文档列明的子集；
- `uniqueItems` 不再进入服务端请求；
- numeric alias 与 counterevidence alias 的唯一性仍由本地 validator 在 Artifact 前硬校验；
- material number、period、unit、entity、identity、ordering 与 lineage 仍全部由本地确定性 owner 管理；
- Prompt、服务端 schema、本地 validator、fake Provider 和 mutation fixtures 仍从同一语义 policy owner 生成，但经过显式 provider-subset compiler。

本轮只冻结合同，不修改 runtime 或业务代码，不读取/探测凭据，不调用模型或 Provider，不跑 canary，不签 admission，不进入 MU T06，也不执行 DELL R12。

机器决策工件 SHA-256：`da48871624cebb068d23f3b34087bf9772dcd39b58d4eb4c0914b5fec2f94ad8`。

## 为什么是结构性替换

当前 `StrictTruthKernelPolicy.json_schema()` 在三案例共同生成：

`$.properties.fact_judgments.items.properties.counterevidence_aliases.uniqueItems=true`

官方 Structured Outputs 指南列出的 array 支持约束为 `minItems` 和 `maxItems`，没有列出 `uniqueItems`。这只能证明当前 request-level compatibility 未建立，不能推断真实端点一定拒绝它。

与此同时，本地 `render_provider_output()` 已独立执行：

- duplicate numeric alias rejection；
- duplicate counterevidence alias rejection；
- wrong/cross-case alias rejection；
- enum validation；
- local material rendering 与独立 L1 recomputation。

因此移除 server-wire `uniqueItems` 不会把重复 alias 降级为质量 finding，也不会降低 L1；它只是把服务端结构约束与本地语义约束放回正确 owner。

## 冻结的 replacement 合同

- server compiler：`fin01.provider.openai_structured_outputs_supported_subset:v1`；
- semantic truth kernel：`fin01.s4.strict_truth_kernel.numeric_judgment_selection:v2`；
- local validator：`fin01.s4.strict_truth_kernel.local_semantic_validator:v1`；
- prospective exact model：`openai:gpt-5.6-sol`；
- server allowlist：`type/properties/required/additionalProperties/items/minItems/maxItems/enum`；
- 所有 object 字段 required，所有 object 为 `additionalProperties:false`；
- 服务端 schema 不得出现 `uniqueItems`、material numeric/identity 字段或 arbitrary free text；
- 本地必须继续拒绝 duplicate alias、cross-case replay、invalid enum 和 numeric projection mutation。

## Anti-loop 上限

这次 scope replacement 最多授权一个、且需再次单独授权的 zero-call implementation bundle。

- bundle 失败：T06 继续 blocked，立即停止；不允许第三个包；
- bundle 通过：fresh engineering proof 仍需单独授权；
- proof 通过后最多一个、仍需单独授权的 single-node canary；
- canary 失败：停止，不 retry、不 provider hopping、不 full-chain；
- DELL R12 永久禁止。

RC-P36-070 更新为 `scope_replace_selected_implementation_pending_one_replacement_bundle_max`，没有关闭。RC-P36-067 继续被 replacement 与未来 live proof 阻断；RC-P36-068 继续 carried-open；RC-P36-069 保持关闭。

## 下一项

`S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-SERVER-SUBSET-CONFORMANT-REPLACEMENT-MINIMUM-ZERO-CALL-IMPLEMENTATION`

该项当前未授权。S4-T05 仍 blocked/not passed/not owner accepted；DELL R2 未证明；S4-T06 尚未进入。

## 未执行

actual model/provider/execution network/source/tool/credential probe/admission/WorkUnit/Attempt/ResearchRun/business Artifact/paired/Human 均为 0。

## 验证

- 新 decision contract：`3 passed`；
- source decision + 新 decision：`6 passed in 2.48s`；
- 3 个 JSON 与 3 个 JSONL 严格解析、duplicate-key 检查通过；
- scoped Project OS preflight：`pass`，open blocker count=`0`；
- secret scan、`git diff --check` 与 trailing-whitespace 检查通过；
- 四个冻结 runtime code hash 与上一 fresh engineering proof 完全一致；
- 工作树包含大量此前的 mixed staged/unstaged/untracked 变更，本轮不 stage、不 commit。
