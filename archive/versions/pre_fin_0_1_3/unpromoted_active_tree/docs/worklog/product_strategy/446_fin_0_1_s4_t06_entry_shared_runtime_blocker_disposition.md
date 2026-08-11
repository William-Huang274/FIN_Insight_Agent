# 446｜FIN 0.1 S4-T06 入口 shared-runtime blocker 处置

日期：2026-07-28

## 问题

R11 在首个 Specialist 返回命中新的 numeric narrative L1。原 v1 设计虽然把 exact numeric value 移到本地 renderer，却仍把 arbitrary narrative 放在 L1-required Provider response 内；模型只要在该字段写入数字，整条链就必须 fail-closed。

同时 `case_numeric_authority` telemetry 未同步进入 canonical facade allowlist，原始失败无法 terminalize，形成第二个项目内 RC-P36-069。

根据全链路审计冻结规则，本轮只能做 program-level blocked、scope swap 或 shared-runtime hardening 决策，不能启动 R12。

## 外部能力与本地历史

- DeepSeek 官方 `json_object` 只保证合法 JSON，并仍依赖 prompt/example 获得目标 shape，不能作为 L1 exact-schema 保证。
- DeepSeek Beta strict tool 支持 JSON Schema 子集，但项目历史已消费两次 strict-tool live attempt，closed output=0；第三次同路线已被此前决策禁止。
- OpenAI 官方 Structured Outputs 提供 strict JSON Schema constrained decoding，但 schema conformance 不等于金融语义正确，仍需本地 authority validation。
- 项目已有 provider-neutral native-json-schema adapter fixture；历史 OpenAI live route 在 generation 前 HTTP 401，未评估 schema，当前 credential/model availability 不可假设。

本轮只读取官方文档和仓库历史；没有 Provider health probe、credential 读取或模型调用。

## 决策

Decision label=`pivot`。

T05 paid execution series 以 `blocked / not passed / not owner accepted` 结束：

- R11 immutable；
- 不启动 R12；
- 不把同一合同改名后复跑；
- 不进入 MU T06；
- 不把 Provider/model switch 混入当前实现。

R11/T05 的历史事实不变，但不新增 H01 阶段。上一版尚未执行的 `S4-H01` 只是临时 hardening 标签，现撤销并改为 T06 入口门禁：

`S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER`

该门禁属于 T06 readiness，不等于已经进入 MU T06，也不是继续扩展 T05。

### Strict truth kernel

`fin01.s4.strict_truth_kernel.numeric_judgment_selection:v1`

Provider 只允许：

- request-local Evidence/Numeric/Claim aliases；
- direction、materiality、confidence、causal relation；
- 本地 interpretation catalog code；
- counterevidence aliases。

Provider 不再拥有 arbitrary free text、material number、currency、percentage、period、entity/title、canonical ID、rendered sentence 或 lineage。所有 material clauses、formula、scope、identity、ordering 与 lineage 由本地唯一 owner 渲染并独立重算。

### Provider capability routing

`fin01.provider.capability.strict_json_schema:v1`

Truth-kernel node 必须在调用前绑定 strict-schema capability。DeepSeek `json_object` 不满足；DeepSeek Beta strict-tool 不作为当前 mainline。OpenAI native structured output 只是后续独立 credential/model gate 的第一候选，不在本轮切换。

### Narrative shell

`fin01.s4.non_authoritative_narrative_shell:v1`

L3 narrative 不再是 L1 完成必需项或 truth owner。Invalid draft 只能作为受限 rejected candidate 与 L3 finding；不得静默修改后冒充原始 Provider 输出。Canonical product 只消费 deterministic truth shell。

### Atomic terminalization

`fin01.bounded_agent.atomic_failure_terminal_core_and_registered_observation:v1`

Terminal core、receipts、captures、counts 与 `failed/failed/failed` transition 原子提交。Optional telemetry extension 不得 veto terminal state；unknown/invalid/secret-like extension 不持久化正文，只记录 content-free observation-rejected code。

这比单独给 facade 增加 `case_numeric_authority` allowlist 分支更结构化，也能避免下一种 telemetry family 再次 orphan。

## 本轮产物

- `configs/releases/fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_disposition_v1_0.json`
- `tests/contract/test_fin_0_1_s4_t06_entry_shared_runtime_blocker_disposition.py`
- 产品审计、技术审计、S4 execution plan 与 Project OS 同步。

## 防止无限修复的硬上限

- 只允许一个独立授权的 zero-call implementation bundle；
- 不允许自动追加第二个 repair bundle，也不允许逐字段、逐 prompt、逐 allowlist 循环补丁；
- zero-call bundle 失败时，T06 保持 blocked，只返回一次项目级 stop/scope-replace 决策；
- bundle 通过后，最多允许一个需另行明确授权的 single-node strict-schema canary；
- canary 失败即停，不 retry、不 provider hopping、不 full-chain；
- canary 通过后，只能另行授权 MU T06 exact execution；
- DELL R12 或等价改名复跑永久禁止；更广的 executor/provider matrix/narrative/cross-stage identity 工作后传 T10/S5。

## 边界

本轮 runtime code/model/provider/network/source/tool/credential/admission/Run/business Artifact/paired/Human 均为 0。

下一项：

`S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-MINIMUM-ZERO-CALL-IMPLEMENTATION`

需要独立授权。T05 保持 blocked，T06 尚未进入；本处置本身不实施 runtime，也不启动 canary 或 full-chain。
