# FIN 0.1 S0 至 S4-T05 全链路技术审计

日期：2026-07-28
状态：`R11 new L1 / T06 entry shared-runtime blocker disposition complete / T06 not entered`

产品结论见：`docs/product/FIN_0_1_S0_TO_S4_T05_GLOBAL_PRODUCT_AUDIT_AND_FORWARD_PLAN_20260728.zh-CN.md`

机器审计工件见：`configs/releases/fin_ia_0_1_s0_to_s4_t05_full_chain_global_audit_and_forward_plan_v1_0.json`

## 1. 全链结构

当前主链可概括为：

```text
Workbench / API
  -> Fin01ResearchRuntime
  -> S4 Case Runtime Binding / Profile Overlay
  -> Case-local Evidence + Numeric + Graph input
  -> Specialist x3
  -> Research Lead
  -> Memo Writer
  -> Verifier
  -> Adapter / profile validation / Artifact commit
  -> Workpaper / Report / Trace / Review
```

其中 Runtime identity、terminal truth、restricted capture、retry-zero、typed failure 和 lineage 已达到较强工程可观测性。当前最弱点不在 transport，而在跨节点 material semantics 的唯一所有权。

## 2. 合同拓扑审计

| 合同面 | 当前 owner | 已证明 | 当前缺口 | 处置 |
| --- | --- | --- | --- | --- |
| Case identity | S4 binding + 多处本地常量 | runtime binding/lineage | Writer title 仍写死 NVDA | case delivery identity projection |
| Evidence roles | case mapping/alignment policy | DELL/MU fixture + live | 当前无 blocker | 保持 |
| Claim/Task identity | local alias expansion | R3 live positive | 通用跨阶段统一仍 deferred | 不重入 T05 |
| Numeric membership | `authority_refs.numeric_refs` | WWC membership live | membership 不等于 value truth | canonical numeric projection |
| Numeric value rendering | model free prose + local output | 无 | value/period/unit/sign 可漂移 | local-only rendering |
| Capacity | profile + resolver | R10 live pass | 当前无 blocker | 保持 6000/8192/24576 |
| Gap overflow | Lead-v6 deterministic projection | R10 L2 finding | 非 L1 | 后传 calibration |
| Lineage | profile-aware lineage validator | R10 exact-live 9 Artifacts | 当前无 blocker | 保持 |
| Failure observation | typed post-provider envelope | R8/R9 live | 历史 R7 exact subtype 不可恢复 | 历史不改写 |
| Acceptance | model Verifier + paired owner review | structure/lineage pass | numeric and identity false negative | independent local L1 recomputation |

## 3. 最早错误路径

### 3.1 Numeric

```text
S4 raw row
  numeric_ref/value/comparison_operator/entity/period
        |
        v
legacy model-view selector
  financial_row_id/normalized_value/nested selector
        |
        v
scale_multiplier + empty selector
        |
        +--> model invents unsupported precision
        |
        +--> membership-only Fact validation passes
        |
        +--> empty Verifier numeric projection cannot recompute
        |
        v
machine false positive
```

修复必须从 S4 row adapter 开始，不能只在 Writer 或 Verifier 末端加 regex。

### 3.2 Case identity

```text
input_pack.company = DELL
        |
        v
Writer-v3 provider output: claim_ref + analysis text
        |
        v
local assembler inserts NVDA title
        |
        v
local validator requires NVDA title
```

这是纯项目缺陷，模型没有 title 写权限。

## 4. 版本与单体风险

`bounded_agent_executor.py` 当前约 12,904 行，同时包含：

- Specialist v1–v8；
- Research Lead v1–v6；
- historical admission compatibility；
- request/model-view construction；
- Provider segment validation；
- local assembly；
- Writer/Verifier；
- profile validation；
- telemetry 与 typed failure；
- Artifact construction。

这导致同一概念在不同函数和版本中拥有多个 schema owner。S4-T05 不适合做全量重构；本轮只把 numeric authority policy 和 case delivery identity policy 独立为明确 owner，并让 executor 通过 policy consumption 组装。

全量版本-family consolidation 放在 S4 closeout 后评估，不能成为 DELL R2 的新阻断。

## 5. 状态与工件审计

严格 duplicate-key 扫描的审计前基线覆盖 295 份 release JSON，发现：

- program backlog 重复 `S4_T05_RC_P36_059_status`；
- RC-P36-067/068 decision 重复 `first_provider_owned_numeric_drift_surface`。

普通 JSON parser 会静默保留最后一个值，因此这类错误会直接破坏 machine-readable source of truth。本次已做最小字段消歧；后续应把 duplicate-key 检查加入现有 release JSON 校验脚本，而不是新建 gate family。

加入本审计机器产物后，最终复扫覆盖 296 份 release JSON，重复键和解析失败均为 0；24 份 Project OS JSONL 在最终哈希修正记录写入前为 1192 行，写入后为 1193 行，重复键和解析失败均为 0。

Project OS 的 506 条 root-cause 记录对应 120 个 unique issue。按每个 issue 的最后一条记录计算，审计前仍有 47 个 `full_chain_blocker=true`，与 S3 owner accepted、R10 live success 不一致。S4 的 14 个 issue 中有 5 个仍标 blocker，但当前真正阻断 T05 的只有 RC-P36-067/068。

结论：append-only ledger 可以保留历史，但 active blocker projection 必须按最新 coherent evidence 重新计算，不能直接统计 raw flag。

## 6. T05 最终实现边界

### 必做

1. `CanonicalNumericAuthorityProjection`
   - 同时解析 S4 flat rows 与 legacy rows；
   - exact ref/entity/scope/period/metric/comparator/value/currency/unit/scale/formula lineage；
   - 每条 projection 有 digest；
   - unknown/duplicate/cross-Cell/missing field fail-closed。

2. `DeterministicNumericRenderer`
   - Provider 只输出 request-local alias 和定性 atom；
   - 本地生成所有 material numeric clauses；
   - Writer 只消费 validated rendered clauses；
   - Provider free-text material numeric injection 是负例。

3. `IndependentNumericIntegrityValidator`
   - Specialist/Lead/Writer 后检查；
   - Artifact commit 前重新从 authority 计算；
   - 不信任 Provider 或 model Verifier 自证。

4. `CaseDeliveryIdentityProjection`
   - title、entity label、manifest/export heading 全部由 case-local identity 派生；
   - Provider 无 title authority；
   - 无 NVDA/DELL/MU 分支常量。

5. 同源生成
   - Prompt schema；
   - local validator；
   - fake Provider；
   - telemetry subtype；
   - mutation fixture。

### 不做

- dependency/conflict/gap 全面 atomization；
- executor 全量拆分；
- provider/model 切换；
- arbitrary free-text regex 作为主合同；
- 修改 R10；
- MU/NVDA paid run；
- S5 或 production。

## 7. 零调用验证矩阵

| 维度 | 正例 | 必须失败的负例 |
| --- | --- | --- |
| Numeric ref | exact current-Cell alias | unknown / cross-Cell / wrong kind |
| Value | authority exact value | same ref wrong value |
| Period | authority period | wrong fiscal period |
| Unit/scale | exact currency/unit/scale | USD vs USD_millions、scale drift |
| Comparator/sign | exact operator/sign | positive/negative、greater/less drift |
| Derived metric | formula + inputs + rounding | wrong input/ref/formula |
| Narrative | qualitative interpretation atom | Provider-authored material amount/% |
| Identity | DELL/MU/NVDA derived title | cross-case title / missing identity |
| Full chain | each case 6/12/9 | any pre-commit mismatch |
| Compatibility | accepted S2/S3 contracts | silent historical admission behavior change |

## 8. R11 与后续 stop rule

R11 只在上述矩阵与 full-fake 通过后执行。

```text
R11 L1 pass + Agent gain
  -> paired assessment
  -> owner decision
  -> close T05

R11 only L2/L3/L4 findings
  -> record quality debt
  -> close T05

R11 new L1
  -> terminal stop
  -> no automatic R12
  -> program-level blocked / scope-swap / shared-runtime-hardening decision
```

S4-T06 和 T07 必须复用同一 contract topology，不再复制 T05 的 transport/version patch chain。

## 9. S5 前技术债

以下债务必须在 S4 closeout 或 S5 entry 明确处置，但不阻断当前 T05 implementation：

- issue-by-issue active blocker reconciliation；
- duplicate-key validation 纳入现有 release JSON 校验；
- coherent Git commit/manifest/rollback slices；
- executor version-family consolidation plan；
- current context pack 与 program plan 从 append-only事件流改为“短 current snapshot + linked history”；
- RG1 operational qualification；
- exact multi-case Workbench owner-time/value measurement。

## 10. R11 结果与 T06 入口技术门禁

唯一计划内 R11 在首个 Specialist Provider 返回后命中 `s4_case_numeric_authority_provider_narrative_invalid`。这证明 v1 numeric projection/local renderer 的确定性 fixture 仍不足以让当前 Provider 自由叙事稳定遵守 atom-only 边界。随后 `case_numeric_authority` telemetry 未进入 canonical safe allowlist，使 `FAIL_RESEARCH_RUN` 被拒绝；三态一度 orphan，现已零调用收口为 `failed/failed/failed`。

因此不再对 v1 加 prompt、regex 或单个 allowlist 分支，也不执行 R12。未执行的 H01 临时标签撤销，以下技术合同归入 `S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER`：

1. `fin01.s4.strict_truth_kernel.numeric_judgment_selection:v1`
   - Provider 只返回 request-local Evidence/Numeric/Claim aliases 与有限 direction、materiality、confidence、causal-relation、interpretation codes；
   - schema 中不存在 arbitrary free-text、material value、currency、percentage、period、entity/title、canonical ID 或 lineage 字段；
   - material clause、derived formula、scope、identity、ordering 与 lineage 全由本地渲染并独立重算。
2. `fin01.provider.capability.strict_json_schema:v1`
   - truth-kernel node 必须绑定真正的 strict-schema capability；
   - 未绑定时在 Provider 调用前 fail-closed；
   - DeepSeek `json_object` 只保证合法 JSON，不满足该能力；
   - 项目已消费两次 DeepSeek Beta strict-tool 尝试但没有 closed output，故不作为当前 mainline；
   - 既有 provider-neutral native-json-schema adapter 可复用，OpenAI native structured output 仅是第一候选；历史 live 路径在 generation 前 HTTP 401，当前 credential/model/budget 仍需独立 gate。
3. `fin01.s4.non_authoritative_narrative_shell:v1`
   - L3 叙事不是 L1 truth 的 owner，也不是 L1 成功必需项；
   - material numeric/identity clauses 由本地注入；
   - 无效 Provider draft 只保存受限 rejected-candidate 事实并形成 L3 finding，不静默改写，不作为 canonical claim。
4. `fin01.bounded_agent.atomic_failure_terminal_core_and_registered_observation:v1`
   - terminal core、receipts/captures/counts 和三态 transition 原子提交；
   - optional telemetry enrichment 不得 veto terminal state；
   - unknown/invalid/secret-like extension 不持久化正文，只记录 content-free observation-rejected code，并仍完成 `failed/failed/failed`；
   - Prompt schema、validator、fake Provider、failure descriptor 与 canonical registry 从同一 versioned owner 编译。

该入口门禁最多只允许一个另行授权的零调用实现包，用 DELL/MU/NVDA mutation/full-fake proof 覆盖 shared runtime。实现失败时 T06 保持 blocked，并直接回到一次 program-level stop/scope-replace 决策，禁止局部补丁循环。实现通过后须先做独立 engineering proof 与 Provider capability binding；最多允许一个另行明确授权的 single-node canary，失败即停且不 retry/provider hopping/full-chain。只有 canary 通过后才可另行决定 MU T06 exact execution；不存在 DELL R12 或自动 full-chain。

### Fresh engineering proof 后续结论

独立测试与 hash 复算证明 runtime/fake contract 没有漂移，但官方 request-subset 审计发现 `StrictTruthKernelPolicy.json_schema()` 在三案例共同生成 `counterevidence_aliases.uniqueItems=true`。OpenAI 官方 `gpt-5.6-sol` 页面确认该模型支持 Responses、Chat Completions、Structured Outputs；Structured Outputs 指南确认 Responses wire 为 `text.format` strict JSON Schema、object 全字段 required 与 `additionalProperties:false`，同时只列 `minItems/maxItems` 为 array 支持约束。

因此精确候选可冻结为 `openai / https://api.openai.com/v1 / gpt-5.6-sol / openai:gpt-5.6-sol / OPENAI_API_KEY /responses + /chat/completions`，但 request schema 兼容性未建立，`fin01.provider.capability.strict_json_schema:v1` 不能 live-bound。RC-P36-070 是 owned request-contract gap；它在任何 credential probe 或 Provider call 之前阻断 canary。按 anti-loop ceiling 不在本轮修改 runtime，直接回到一次 program-level scope-replace-or-stop 决策。

## 12. Post-proof program scope-replace 技术合同

一次性 decision 选择 `scope_replace`，冻结 semantic/local contract 与 Provider wire contract 的显式编译边界：

1. `fin01.s4.strict_truth_kernel.numeric_judgment_selection:v2` 继续定义 aliases/enums-only 语义面；
2. `fin01.provider.openai_structured_outputs_supported_subset:v1` 只允许 `type/properties/required/additionalProperties/items/minItems/maxItems/enum` 进入 strict server schema，禁止 `uniqueItems`；
3. `fin01.s4.strict_truth_kernel.local_semantic_validator:v1` 继续检查 exact keys、Case-local alias membership、numeric/counterevidence alias uniqueness、closed enum、cross-case replay，并在业务 Artifact 前失败；
4. Prompt、server compiler、local validator、fake Provider 和 mutation fixtures 由同一 policy owner 派生，避免再次发生 prompt/schema/validator 漂移。

下一实现必须零调用覆盖 DELL/MU/NVDA：断言 server schema 不含 allowlist 外关键词，同时 duplicate alias 等负例仍本地 fail-closed；并保留 6/12/9 full-fake、atomic terminalization、12 receipts/captures、历史 admission digest 与 run immutability。最多一个另行授权的 replacement bundle，失败即停且不得第三轮；通过也只进入另行授权的 fresh proof，不自动 canary、admission 或 MU。

## 13. Server-subset replacement 实现结果

实现新增显式 `OpenAIStructuredOutputsSubsetCompiler`。它从 semantic schema 编译 exact Provider wire schema，只移除登记的 local-only `uniqueItems:true`，其他未知 keyword 一律失败；同时递归验证 object required/additionalProperties 与 array items/min/max。`StrictTruthKernelPolicy` 分别暴露 semantic/server schema，backward-compatible `json_schema()` 明确定义为 Provider wire；Prompt、Responses adapter、required-output schema 和 registered failure descriptor 已同步 v2 owner。

三案 schema allowlist 与 local duplicate mutation 均通过，DELL/MU/NVDA full-fake 仍为 6/12/12/9；typed failure 与 capture 回归未破坏。focused=33、相邻回归=61 passed。该证据关闭 implementation gap，但不关闭 RC-P36-070 的 exact request binding/live proof；下一步必须另行做 fresh engineering proof，不得自动调用 Provider。

## 14. Replacement fresh engineering proof 与 documented request binding

独立复算确认 replacement implementation 与六个冻结 code/test SHA-256 均无漂移，focused suite 连续两次为 `33 passed`。DELL/MU/NVDA server schema canonical digest 分别为 `24cdd015...4938`、`9c2138b1...0879`、`3a4f560f...5cc7`；递归检查确认：

- schema root 为 object；
- 每个 object 的 properties 全部 required；
- 每个 object 均为 `additionalProperties:false`；
- 所有 keyword 位于 `type/properties/required/additionalProperties/items/minItems/maxItems/enum`；
- Provider wire 不含 `uniqueItems`；
- local semantic validator 继续拥有 duplicate-alias L1 hard check。

OpenAI 官方 `gpt-5.6-sol` 模型页确认 Responses 与 Structured Outputs 均支持；官方 Structured Outputs 指南确认 Responses wire、root object、all-required、closed object 与普通模型 array `minItems/maxItems`。因此 `fin01.provider.openai_structured_outputs_supported_subset:v1` 对 `openai:gpt-5.6-sol` 的 documented request binding 成立。

该结论严格不等于 live binding：credential presence/access 与 endpoint acceptance 均未评估，Provider 调用为 0。下一技术门禁只能是单独的 canary authority decision；未来 canary 失败必须立即停止，不 retry、不 provider hopping、不 full-chain、不自动 repair。

## 15. Single-node strict-schema canary authority

authority decision 授权一份 exact-once request，而不是完整 logical node 或 full chain。冻结目标：

- canary ID=`fin01-s4-t06-entry-openai-strict-schema-dell-demand-r1`；
- DELL Demand `facts_explanation_and_terminal`；
- exact request template digest=`b92911d0...43d7e`；
- server schema digest=`24cdd015...4938`；
- OpenAI `gpt-5.6-sol /responses`；
- `reasoning=none`、max output=512、timeout=120s；
- semantic/provider/network/transport attempt ceiling=`1/1/1/1`；
- cost ceiling=USD 0.05；
- retry/source/tool/chat/full-chain/canonical Run/Artifact=`0`。

实际执行前必须进行无调用的 digest、fake wire/local validator、Project OS exact scope、result absence、retry-zero 与 credential presence-only preflight。canary 结果只可持久化 request/schema digest、sanitized status、usage/cost/latency、attempt count、parse/local-validation status 和 content-free shape；raw Provider response、output text、reasoning、headers、credential、stack 均禁止。

成功关闭的只是 live endpoint/request-capability gap；失败不重试且返回 program-level blocked decision。该 authority 不进入 MU T06，不允许 DELL R12。
