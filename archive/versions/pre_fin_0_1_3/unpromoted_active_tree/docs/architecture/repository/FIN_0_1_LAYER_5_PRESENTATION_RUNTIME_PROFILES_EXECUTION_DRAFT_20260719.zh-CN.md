# FIN 0.1 第五层：Presentation / Verification / Runtime Profiles 执行草稿

日期：2026-07-19
状态：`docs_only_discussion_draft`
适用范围：FIN 0.1 下一阶段 Agent 产品主线

## 1. 本层目标

> 2026-07-21 S3-T07 执行更新：同一 deterministic `ResearchRun` 已从 T02-T06 adjudicated heads 编译 exact 三 Cell Workpaper、Report、Trace-review 三个 canonical Artifact；主 manifest 与所有 Cell/SurfaceClaim/SpecialistJudgment/Artifact refs 可闭合重建。Writer 的 source、retrieval、external-tool、raw-Candidate 权限均为 false，模型 Writer 未执行。Workbench 逐 Cell 暴露 Evidence/Numeric/Graph/gap/WWC/repair/typed-stop，并明确 why/gap/WWC 不自动发起新研究。Verifier 绑定 profile、input-head、as-of、content digest、findings 和 machine decision；Visual 仍是 `pending_browser_validation`，Human Review/decision/digest confirmation 仍为 `not_performed/false`。因此本增量只证明 deterministic presentation 与 review-target runtime/node consumption，不证明付费 Writer 质量、浏览器或人工接受、Alpha、release 或 production。

> 2026-07-19 S1-T04 执行更新：同一 `agent_fixture_shadow` Run 已经过 Writer、Verifier、Renderer 节点，生成 canonical `agent_fixture_report` 与 `agent_fixture_trace`，Writer source/tool calls 为 0，Verifier 明确 `human_review_status=not_performed`。Writer 阶段注入故障会使原 Run/Attempt/WorkUnit 全部 terminal failed、产物为 0、无 deterministic fallback；独立复核又把所有子产物交叉引用修正为 exact canonical ArtifactVersion refs。Workbench 中的 Profile/event/artifact/stop-reason 区分仍是 T05，真实 model/provider/network、Human Review、release 与 production 均未授权。

本层解决两个产品真实性问题：

1. Writer 如何把已裁决的研究对象组织成有主次、有边界、可供决策的叙事，而不重新检索、伪造事实或覆盖专业判断；
2. deterministic、Agent shadow、bounded model 和 release candidate 如何共用同一产品主线，并在失败、降级、权限和 UI 中保持真实区分。

本层消费 D02-D10 已冻结的 DecisionSurface、Evidence、Numeric、Judgment、Context、Repair 和 exact lineage，不新增平行 Runtime、Registry、Writer 或业务真相 head。

## 2. `L5-D11`：Writer / Verifier 角色边界

`L5-D11-WriterVerifierRoleBoundary` 已冻结为：

```text
bounded_presentation_agent_with_independent_layered_verification
```

### 2.1 Writer 是受限的 Presentation Agent

Writer 保留 Agent 能力，用于选择叙事顺序、合并重复内容、建立跨 Cell 过渡、突出核心判断与边界，并生成适合 Workpaper 或 Report 的表达。Writer 不是 Evidence、Numeric、Judgment 或 release authority。

Writer 只消费冻结的：

- exact `LeadSynthesis`、`SpecialistJudgmentVersion` 和 `ClaimVersion`；
- What-Would-Change、cannot-infer、material conflict、Gap 和 boundary；
- `WriterBrief`、目标读者、文体与篇幅约束；
- 已授权的 citation refs、Numeric refs 和 presentation policy。

Writer 默认无 retrieval/source/tool/raw Candidate 权限，不得修改 Evidence/Numeric/Judgment head，不得把缺失依据补写成事实，也不得把多个有限判断合成为更强结论。

### 2.2 Writer 输出

Writer 输出至少包括：

- `CanonicalPresentationModel`：标题、核心回答、章节、claim/numeric/citation refs、边界、反证和 What-Would-Change；
- `SurfaceClaim[]`：每个面向用户的陈述及其 exact upstream refs；
- Workpaper/Report draft；
- `PresentationGap[]`：无法仅靠表达解决的上游缺口；
- `WriterDecision[]`：结构选择和省略原因，不包含模型私有思维链。

遇到 unsupported claim、版本冲突、citation 缺失或上游判断不足时，Writer 必须 typed stop，并按 D10 返回最早 owner；不得自行搜索或静默弱化后继续生成貌似完整的报告。

### 2.3 独立分层 Verifier

Verifier 与 Writer 分离，按四层执行：

1. **Deterministic Integrity Verifier**：检查 exact Case/Run/version、权限、citation 可达性、数字/单位/期间、forbidden claim、no-source 和 artifact digest；
2. **Semantic Verifier Agent**：检查 SurfaceClaim 是否忠实表达 upstream Claim/Judgment、是否发生遗漏限定、过度概括或反证失衡；
3. **Financial Coherence Verifier**：检查收入、利润、现金流、分部、周期、估值和跨 Cell 机制是否自洽，不能以语言流畅覆盖 Numeric/Claim 冲突；
4. **Visual Verifier**：检查标题层级、表格、引用、分页、可扫描性、文本溢出和关键边界是否在最终用户表面可见。

Verifier 只生成 finding、severity、affected refs、earliest owner 和 repair recommendation。Verifier 不直接改写 Evidence、Numeric、Judgment 或已冻结研究结论；纯排版/措辞问题才可返回 Writer/Renderer。

### 2.4 Human 与 Release 边界

Verifier pass 只代表机器核验通过，不等于 Human Senior Review、R3、release admission 或 production readiness。Human Reviewer 必须看到 exact artifact、关键依据、边界、版本和 verifier findings，并形成独立 attestation。

### 2.5 最小完成证明

至少证明：Writer 无 source/tool/raw Candidate 权限；每个 SurfaceClaim 可追溯到 exact upstream refs；Writer 遇到研究缺口会返回上游而非补写；四层 verifier 可分别发现版本、语义、金融一致性和视觉问题；机器 pass 不会被写成 Human accepted；Workpaper 与 Report 消费同一研究真相但呈现结构不同。

## 3. `L5-D12`：Execution Profiles 与失败真实性

`L5-D12-ExecutionProfilesAndFailureTruth` 已冻结为：

```text
one_runtime_multiple_explicit_profiles_without_silent_substitution
```

### 3.1 一个 Runtime，四种显式 Profile

所有模式都通过同一个 `Fin01ResearchRuntime`、`ResearchRun`、`EventTrace` 和 artifact contracts，不得复制平行 API/Case/UI 主线。

| Profile | 用途 | 允许能力 | 产品声明 |
| --- | --- | --- | --- |
| `deterministic_fallback` | 保持本地可演示、开发回归 | deterministic fixture/parser/numeric/judgment projection | 明确标记 fallback，不证明 Agent 能力 |
| `agent_fixture_shadow` | 验证 Agent 编排与合同 | Agent/Skill/Tool/Graph 在 fixture/shadow 上运行 | 不晋升为 release 研究结果 |
| `bounded_agent_internal` | FIN 0.1 内部真实 Agent 纵向 | 受限模型、工具、数据、预算和 exact artifact | 可用于 RG1/RG3/RG4 候选证明，不等于发布 |
| `release_candidate` | 冻结候选和发布评测 | exact candidate、固定 policy/model/data/skill versions | 只在全部 release gates 后可形成发布决定 |

每个 Profile 必须版本化并固定：model/provider、Agent/Skill/Tool/Graph allowlist、network/data policy、context policy、预算、并发、stop/repair、输出 authority、UI label 和 eval suite。

### 3.2 禁止静默降级

Agent 运行失败时，原 `ResearchRun` 必须保持 `failed`、`partial` 或 typed stop。系统不得用 deterministic 输出覆盖同一 Run，也不得把 fallback 结果显示成 Agent 成功。

如用户显式选择继续，可创建绑定原失败 Run 的 `deterministic_fallback` child run；两者拥有不同 Profile、Run ID、artifact heads 和 UI 标识，且不能合并统计。

### 3.3 允许的确定性服务

Agent profile 内可以调用 deterministic parser、numeric、schema validator、Evidence Gate、permission checker 和 renderer。这些是被追踪的服务能力，不属于失败替换。

2026-07-20 S2-T03 v4 增量冻结：provider request document 与 response document 必须使用不同 namespace。Specialist+Lead response 只允许单一 outer key `result`；`result` 内只允许 `output_contract_ref`、`specialist_judgment`、`lead_adjudication`。未知 outer/result 字段不得静默删除、重命名或转成研究语义；只能记录 secret-safe count/digest/type telemetry 并 typed fail-closed。当前 provider mode 仍只是 `json_object`，未证明 server-enforced nested schema；因此 v4 只达到 deterministic fixture proof，不构成真实 Agent、T03 pass 或 live admission。

2026-07-20 S2-T03 v4 live-validation decision：不得在普通 `json_object` mode 下直接签发新的 v4 admission。DeepSeek 官方合同仅保证该 mode 产生合法 JSON，并不保证 exact nested keys；其强 schema 约束位于 `/beta` strict function/tool calling。下一实现项固定为一个不执行外部工具的 output-carrier function：`strict=true`、forced named `tool_choice=submit_specialist_lead_result`、exactly one `tool_calls` finish、arguments 服从 v4 closed schema，之后仍通过本地 candidate/semantic validator。strict adapter 未 deterministic 通过前，新 admission、model/provider/network call、T04 与 S3 均不授权。

2026-07-20 S2-T03 v4 strict-tool adapter 增量：上述 adapter 已在唯一 bounded executor 中完成 deterministic fixture proof。Specialist 请求精确绑定 `https://api.deepseek.com/beta/chat/completions`，发送唯一 `submit_specialist_lead_result` function、`strict=true` 和 forced named `tool_choice`；schema 中每个 object 都满足 all-properties-required 与 `additionalProperties=false`，candidate IDs 固定为本次输入 enum。运行时不发送官方合同未列出的 `parallel_tool_calls`，本地要求 `finish_reason=tool_calls`、恰好一个 exact-name function call、空 message content，并只把 arguments 当作输出载体，绝不执行外部工具。arguments 必须是原生 JSON object；围栏 JSON、重复键、非 object、0/多 call、错误名称和 schema/semantic 不合规均 typed fail-closed，且 strict path 不再通过历史无损 normalizer。Writer/Verifier 仍使用 `json_object`，本地 candidate、evidence boundary 与 semantic validator 不变。Focused=`32 passed`、相关 Runtime/S1/S2/Workbench=`91 passed`，model/provider/network/external-tool execution、新 admission、live validation 均为 0；因此只证明 adapter fixture 可用，不证明 provider live compliance、Agent 研究质量或 T03 pass。该段的 admission decision 已由下方最新签发状态消费。

2026-07-20 S2-T03 v4 exact admission 增量：用户选择“只签发、不执行”。已创建 `fin01-s2-t03-bounded-agent-v4-strict-tool-live-validation-r1`，绑定 output contract v4、strict transport v1、DeepSeek beta、同一冻结 Case/input digest、最多 3 次 semantic/provider/network calls、每次 1 transport attempt、retry=0、USD 0.05 cap；source network、external tool、live business Case head write 继续关闭。执行身份另行冻结为 WorkUnit key `fin01-s2-t03-bounded-agent-work-unit-v4-strict-tool-r1` 与 isolated root `.codex_runtime/fin01-s2-t03-v4-strict-tool-live-validation-r1`。本次只签发并做零调用校验，execution 未开始、admission 未消费、model/provider/network=0；下一步仍须用户明确要求“执行”后才允许消费一次，且成功或失败后均停止，不自动重跑或进入 T04。

2026-07-20 S2-T03 v4 live 结果：用户随后明确要求执行，唯一 admission 在最终零调用 preflight 后消费。DeepSeek beta 返回 `finish_reason=tool_calls`，但 function arguments 未通过本地 native JSON parser，Run 以 `bounded_agent_strict_tool_arguments_invalid_json` terminal failed；canonical 为 1 bounded WorkUnit / 1 Attempt / 1 failed ResearchRun / 0 Artifact。实际 model/provider/network=1/1/1、transport attempt=1、3272 tokens、latency=28026 ms、estimated cost=USD 0.00200448；source network/external tool/fallback/retry/rerun 均为 0。raw provider response 与 arguments 未持久化，所以目前不能区分 decode、duplicate-key 或 non-object subtype。此结果证明 named-tool live route 被触发，但不证明 closed v4 output、Agent artifact 或研究质量；不得复用 admission、自动放宽 parser、重试或进入 T04。下一项为独立 root-cause decision。

2026-07-20 S2-T03 post-v4 telemetry 增量：经独立复核，未来 strict-tool arguments parse 失败新增固定白名单的 secret-safe subtype telemetry，只允许 `json_decode_error`、`duplicate_key`、`non_object`；通用 failure code 保持 `bounded_agent_strict_tool_arguments_invalid_json`。Telemetry 仅记录固定 parser contract 和 raw arguments、digest、length 均未持久化的布尔事实，入口不接受任意 payload；敏感夹具验证正文不会泄漏，非白名单 subtype 也不会进入 observation。Native JSON parser 没有放宽，fenced JSON、重复键与非 object 继续 fail-closed。Focused T03=`39 passed`，model/provider/network、新 admission 均为 0。该修复只改善未来失败的可观测性，无法倒推已消费 v4 Run 的 subtype，也不构成 strict output、Agent artifact、研究质量或 T03 pass；下一项为 provider strategy / new exact admission decision，T04 继续 blocked。

2026-07-20 S2-T03 post-telemetry provider strategy 增量：官方合同复核后继续保留 DeepSeek beta strict named-function transport。理由是 strict Function Calling 仍是 provider 声明的 schema-constrained 路径，而 `json_object` 只保证合法 JSON；本地 gateway 审计确认 outer provider response 可解析，tool calls 与 arguments 均原样透传，未发现项目内 argument transformation 根因。当前证据只有一次 strict live failure，且历史 subtype 不可恢复；新 subtype telemetry 已向前 fixture-proven。因此最多建议一次全新 r2 exact admission，用同一 Case/input/candidates、v4 output contract、strict transport、最多 3 semantic/provider/network calls、每次 1 transport、retry=0、USD 0.05，继续关闭 source network、external tool、live Case head write 和 raw argument persistence。该 admission 尚未签发或执行；若 r2 再次出现任一 parse subtype，必须把它视为第二次 strict-output nonconformance 并在任何第三次尝试前 pivot/escalate provider transport。即使成功也须先审查 Artifact 与研究价值，不能自动通过 T03 或进入 T04。

2026-07-20 S2-T03 fresh r2 exact admission 增量：用户已单独授权签发，但未授权执行。新 admission `fin01-s2-t03-bounded-agent-v4-strict-tool-live-validation-r2` 与 fresh WorkUnit key `fin01-s2-t03-bounded-agent-work-unit-v4-strict-tool-r2`、isolated root `.codex_runtime/fin01-s2-t03-v4-strict-tool-live-validation-r2` 已冻结；admission digest=`671ec47b1085e51bfb43a8af46b8b89918498441ce6d92a3bdbbcd2b62ea0adf`。Case/version/input/candidates、v4 output contract、strict transport、DeepSeek beta、3-call/1-transport/retry-0/USD 0.05 和 no-source/no-tool/no-live-head-write 边界均未改变。prepare 与 exact preflight 只做本地检查且通过，model/provider/network/external-tool=0；execution started=false、consumed=false。签发不等于 provider conformance、Agent artifact、研究价值或 T03 pass；下一项只能是独立 execution decision，未经新的明确执行指令不得消费该 admission，也不得进入 T04。

2026-07-20 S2-T03 r2 live 结果：用户随后单独授权执行，三层预检通过后 r2 只消费一次。唯一 DeepSeek beta Specialist call 返回 `tool_calls`，1 transport、3074 tokens、19747 ms；Writer/Verifier 未启动，Artifact=0，无 retry/fallback。此次暴露的最早 owned root cause 位于 canonical failure path：executor 的 strict argument parse error 会产生闭合的 `failure_telemetry`，但 `RuntimeFacade.fail_research_run` 的 secret-safe allowlist 尚未接纳该字段，因此 terminal command 被拒绝；外层 background dispatch 将异常降格为 `not_dispatched`，导致同一 WorkUnit/Attempt/Run 遗留 running，未形成可审计 terminal reason。由于 raw arguments 与内存异常均未持久化，只能从唯一执行路径推断 strict arguments parse failure 再次发生，不能恢复或声称具体 subtype。r2 identity 已 consumed，禁止复用；不得发起第三次同 transport 尝试。下一项必须由用户决定是否做零调用 allowlist、background error propagation、runner terminal wait 和 orphaned-run typed closeout 修复，T04 与所有下游 gate 继续 blocked。

2026-07-20 S2-T03 r2 orphaned Run 零调用修复：用户批准后，canonical failure path 现仅接纳固定 strict-tool telemetry 结构，任意额外正文继续 fail-closed；background dispatch 不再吞 runtime exception；runner 在 HTTP 202 后必须等待 canonical `succeeded/failed/cancelled`。副本演练和幂等复演通过后，原 r2 WorkUnit/Attempt/ResearchRun 以 `bounded_agent_canonical_terminalization_interrupted` typed closeout 为 failed，Artifact=0，gateway events 保持 2 -> 2，本轮新增 model/provider/network=0。Closeout 只根据既有 gateway receipt 记录 1/1/1 call、3074 tokens、19747 ms 和 maximum reconstructable USD 0.00183222，不重建 provider arguments 或 parse subtype。该修复只恢复失败真实性，不产生 closed v4 output、Agent artifact 或研究价值；S2-T03 仍 failed，下一项为 provider-transport pivot decision，任何第三次相同 strict attempt、T04 或下游 gate 均未授权。

以下行为属于禁止的 hidden substitution：

2026-07-22 S3-T09 首节点 truncation repair：首次三 Cell exact Run 在 Demand Specialist 以 input=8973、output=1400、`finish_reason=length` fail-closed，未形成 Artifact。零调用拆解确认 provider request 直接序列化完整 canonical cell pack，因而选择的 repair 不是 cap-only，也不是删除研究输入的 blind compression，而是由不变 canonical input v1 确定性派生 `fin01.s3.specialist_model_view:v1`。随后经用户独立授权已完成实现：保留 T02 决策/stop/WWC/branch observation/authority、T03 candidate/promotion/source boundary、T04 exact rows/formula/result/support boundary、T05 method/edge/market/risk/typed gaps 和完整 authority refs；candidate snapshot、tool plan/preflight、重复 decision-cell list、其他 role context 与 audit-only digest 仍留在 canonical input/trace，不进入 Provider view。冻结 exact input 的实现后 v2 request 为 8331/12461/8969 bytes，相对 canonical payload 减少 67.9%/61.2%/66.5%。output v2 本地强制 fact≤3、explanation 1–3、judgment 1–2、gap 1–4、WWC 1–3、item≤320 Unicode chars、serialized≤6000 UTF-8 bytes，并对 duplicate/additional/unauthorized ref fail-closed；receipt 绑定 view contract/digest，最终输出仍对原 cell authority 验证。Specialist=2200，Lead/Writer/Verifier=1200/1400/1000，aggregate=10200，总 cap=USD 0.10、retry=0。该实现仅 fixture-proven；replacement admission 尚未决策/签发/执行，T10 仍 blocked。

2026-07-22 S3-T09 replacement admission preissuance decision：全新 output-v2 execution identity 已通过双重 exact-input prepare、三份 role-specific model-view digest、完整 authority 校验、admission schema/factory、预算和 credential-presence 零调用复核。该决策只冻结未来可签发 payload：Specialist=2200、aggregate=10200、USD 0.10、retry=0，且 source/tool/live Case write 继续关闭。决策过程没有创建 admission、canonical execution state 或发起 Provider probe；签发与消费/执行仍是两个后续独立授权边界。

2026-07-22 S3-T09 output-v2 replacement admission issuance：经独立授权，已把上一步审查的 exact payload 原样物化为唯一 admission；签发前重新执行 Project OS、双重 prepare、fresh-state absence、schema/factory 和 digest parity，全部通过。admission 当前 `issued=true / consumed=false / execution_started=false`，没有创建 WorkUnit/Attempt/Run/Artifact，也没有调用模型、Provider 或网络。下一步 exact-once consumption/execution 仍需独立授权，并在启动前要求 transport retry 环境值精确为 0。

2026-07-22 S3-T09 output-v2 replacement live execution：执行前修复 live runner 的旧 r1 constants/store-empty 假设，改为由 immutable issuance 显式加载 target，只对目标 WorkUnit/Attempt/Run 做 consumed guard，并允许同一 Case/store 保留历史 terminal identities；旧 r1 与 replacement shared-store fake-provider regression 通过。随后 exact-once DeepSeek 六节点 Run terminal succeeded，9 Artifact/23 events、6 calls、17683 tokens、USD 0.00893187、retry/fallback/rerun=0。三 Specialist node receipts 绑定 model-view v1 exact digests，四层 machine verifier pass。该 success 关闭 RC-P36-035 的 live proof，但 comparison artifact 仍缺 distinct terminal deterministic baseline，故打开 RC-P36-036；T09/T10 不得因 execution green 自动接受。

2026-07-22 S3-T09 replacement Artifact/paired-baseline 只读验收：exact 九 Artifact 的 canonical identity、manifest、lineage、六节点 receipt、Evidence/Numeric 与 source/tool boundary 均通过，且 SQLite/Object Store 摘要前后不变；但 owner-grade 复核确认 machine verifier 漏掉 unsupported declarative segment-revenue judgment、Lead fact-state 措辞冲突、Graph 术语误译和非结构化 WWC。由此打开 RC-P36-037，当前 verifier pass 只能证明内部机器合同，不是产品质量或 Human acceptance。跨 11 个 canonical DB 的 same Case+input-head 搜索没有任何 terminal deterministic profile candidate，T08 deterministic proof 也因 Case/head/DecisionSurface 不同而不可复用；RC-P36-036 因而从“comparison pending”推进为“baseline absent confirmed”。下一步只能先独立决定是否物化一条 fresh、distinct、same-input、zero-model deterministic baseline；本验收未物化 baseline，也未重跑 Agent 或进入 T10。

2026-07-22 S3-T09 paired baseline 物化决策：冻结 `fin01.s3.paired_three_cell_deterministic_baseline:v1` 的 exact prospective identity，同 Case/version、DecisionSurface、as-of、input-head 与三 Cell，但 deterministic profile、WorkUnit/Attempt/Run 及 deterministic result/Workpaper/Report/Trace-review 四 Artifact 均与 Agent distinct。disposable clone 上两次 production adapter 编译 payload/digest 完全一致，所有 prospective identity 在 target 中 fresh；baseline 未物化。一次直接 target store 初始化引发 SQLite 物理文件改写，虽未创建 execution row/object，仍以 RC-P36-038 如实登记，并把预检硬化为 target `mode=ro`/hash guard + clone-only initialization。下一步先处理 RC-P36-037 的 owner-grade semantic/actionability repair decision；在其闭合前不得以 baseline 合同或 machine verifier green 宣称 material gain。

2026-07-22 S3-T09 RC-P36-037 零调用 repair decision：独立代码与 live Artifact 复核确认，v2 Specialist 只对 `fact_layer` 做 authority 校验，`judgment_layer`/WWC 仍是 bounded strings；Lead、Writer、Verifier 依次缺 fact-presence、claim surface 与 full authority body，故 false green 是项目内上游到末端合同缺口，不是 Provider JSON 问题。selected output v3 使用 typed Claim Card 表达 epistemic status、support/context、scope/period/metric/attribution 与 qualification/cannot-support；WWC 使用 source/metric/decision rule/threshold/time/transition/stop 任务合同；Lead 分离 terminal state 与 Evidence/Numeric fact count；Writer 只渲染 exact claim/task identity 并保留 qualification/Graph 术语；Verifier 收齐 authority/Specialist/Lead/Writer bodies，并受 local owner-grade semantic precommit gate 约束。实现需一个正例、十个负例、现有九 Artifact family、历史 v1/v2 不变、全程零调用；当前仅 decision，implementation 尚未授权。

2026-07-22 S3-T09 RC-P36-037 zero-call implementation：output v3 已在既有三 Cell 六节点 adapter 中实现。Specialist 本地从 Numeric selector/derived metric 重建 fact authority，Claim Card 和 actionable WWC fail-closed；Lead 由 Specialist body 重算 fact/claim state；Writer 校验 exact claim/task surface、scope digest、qualification 与 Graph 术语；Verifier 接收 full authority/fact/claim/WWC/Lead/Writer bodies，local issue 或 nonpass finding 均禁止 false green。六节点正例 terminal succeeded 并保留原九 Artifact family，十个负例全部在约定 earliest owner 失败；历史 v1/v2 行为回归通过。实现未调用模型/网络、未物化 baseline 或创建 admission，因此只证明工程合同，不能替代 fresh v3 Agent Artifact 与 owner acceptance。下一项按既定顺序为 separately authorized same-input deterministic baseline materialization。

- Agent Specialist 失败后用固定模板生成 Judgment 并标记 Agent completed；
- retrieval/tool 失败后注入历史 fixture Evidence；
- Writer/Verifier 失败后复用旧 artifact 作为当前 exact output；
- profile/version 变化后继续沿用旧 Human Review 或 release status。

### 3.4 Workbench 表达

Workbench 必须在任务列表、运行页、报告和 Review 中持续显示 Profile、Run 状态、数据模式和是否发生 child fallback。用户可查看结构化 Agent/Skill/Tool/Graph events、stop reason、artifact version 和失败位置，但不展示模型私有思维链。

### 3.5 能力与发布声明

- `deterministic_fallback` 通过只证明产品壳和确定性合同可用；
- `agent_fixture_shadow` 通过只证明 Agent 合同与编排可运行；
- FIN 0.1 的 Agent 产品能力声明至少需要 `bounded_agent_internal` exact runs；
- release evidence 必须来自冻结的 `release_candidate`；
- 即使 FIN 0.1 发布，`production_readiness` 仍须由独立生产准入决定，不能自动晋升。

### 3.6 最小完成证明

至少证明：四种 Profile 共用唯一 Case/Runtime/API/UI；Profile version 可重建；Agent 失败不会被 fallback 覆盖；显式 child fallback 与父 Run 分离；确定性服务调用可追踪；UI 不混淆 fixture、Agent internal 和 release candidate；旧 artifact/review 不能跨 Profile 冒充 current exact output。

## 4. 下一层接口

- `L6-D13-ReleaseScopeAndCaseProof`：FIN 0.1 与 FIN 0.2 分别交付什么完整产品能力，使用哪些真实 Case 证明深度与迁移性；
- `L6-D14-EvaluationHumanReviewAndReleaseGate`：如何分别评价完整性、研究质量、交付质量、Human 产品价值、成本与运行质量，并形成不会被平均分掩盖的 release decision。

## 5. 本草稿不授权事项

本文件不授权 runtime、Writer、Verifier、frontend、model、provider、network、paid data、真实 Case mutation、Human acceptance、release candidate run、production cutover 或发布。本文件不把当前 deterministic P36 预览写成 Agent 产品能力，也不改变现有 blocked release 状态。
