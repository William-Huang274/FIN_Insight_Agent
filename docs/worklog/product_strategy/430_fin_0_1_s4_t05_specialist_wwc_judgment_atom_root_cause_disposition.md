# FIN 0.1 S4-T05 Specialist WWC judgment atom 根因处置

日期：2026-07-27
范围：`RC-P36-062` 零调用根因处置；不实施、不重跑、不 paired、不进入 S4-T06

## 结论

R5 的直接失败是 Demand Specialist `actionable_what_would_change_tasks` 在 `1400/1400` output tokens 时被截断。受限 capture 的结构审计显示，Provider 已开始生成 3 个任务，绝大多数必需键出现 3 次，最终只在第三个任务的 time-window 字符串中断；没有 Markdown fence、私有推理标记、raw `claim_id` 或一般 JSON 纪律失控的证据。因此不能把它归结为 DeepSeek “直接不遵循指令”。

项目内最早根因是 WWC Provider wire contract 的信息架构：最多 3 个任务、每个 13 个叙事字段且单字段上限 320 字符，同时请求重复携带 analysis input、prior segments、authority 与 alias surfaces；segment 只有 1,400 tokens，byte cap 则为 6,000。三任务最大合同形状为 12,826 bytes，R5 在 5,258 bytes 已先耗尽 token cap，说明 token/byte envelope 没有稳定可表示余量。

R4 在相同 DELL input digest 和当前 segmented path 下曾以 1,050 tokens、4,084 bytes 完成 3 个任务；R5 则以 1,400 tokens、5,258 bytes 截断。这证明现合同“偶尔能装下”，但不能稳定吸收正常叙事长度波动，也不能证明 Provider 路由普遍不可用。

## 处置

选择 `fin01.s3.specialist_WWC_judgment_atom_deterministic_assembly:v1`，并要求新的 Specialist segmented transport `v8`：

- Provider 只输出 1 至 3 个紧凑 WWC judgment atoms，保留 claim/authority aliases、判断条件、时间触发、预期 claim transition 和 stop condition。
- 本地确定性层拥有 `task_id`、exact alias expansion、authority kind validation、`source_target`、exact `as_of`、canonical `decision_rule`/`time_window` 嵌套、排序、identity 与 lineage。
- 任一 atom malformed、越长、unknown/cross-cell/wrong-kind ref 都 fail-closed；不得静默丢弃或从 partial JSON 恢复。
- atom 叙事字段上限收敛到 160 字符，Provider atom byte cap 4,800；WWC output token cap 设为有界的 1,800。每 cell Specialist segment 总上限为 4,600，三 cell full-chain maximum 为 18,000，较 R5 增加 1,200 output tokens，按当前输出单价只增加最多 USD 0.001044。
- 实施必须用同一版本化合同生成 prompt schema、validator、assembler、fake Provider 和 typed telemetry，并用最大形状 fixture 证明 byte/token envelope；如果装不下必须 fail-closed，不能继续盲目加 cap。

容量截断和 invalid JSON 仍是 L1 hard failure，不降级为 L3 质量 finding。拒绝 token-only 扩容、prompt-only “更简洁”、retry/rerun、换 Provider、DELL 特判和 partial output salvage。

## 序列边界

此决策没有调用 model/provider/network/source/tool，没有签发 admission，没有创建 WorkUnit/Attempt/Run/Artifact，没有 paired 或 Human Review。R5 失败事实与 restricted capture 保持不可变；`RC-P36-061` 仍是 `R5_consumed_failed_upstream_projection_live_observation_unproven`。

dependency/conflict、Writer/Verifier 和 all-node atomization 继续留给 S4-T10 至 S5，不在当前单任务序列无限扩展。

下一项仅为：

`S4-T05-DELL-SPECIALIST-WWC-JUDGMENT-ATOM-AND-DETERMINISTIC-TASK-ASSEMBLY-MINIMUM-ZERO-CALL-IMPLEMENTATION`

正式决策：

`configs/releases/fin_ia_0_1_s4_t05_dell_specialist_v7_wwc_segment_output_truncation_zero_call_root_cause_disposition_v1_0.json`

## 验证

- decision focused contract：`6 passed`
- S4-T05 contract regression：`169 passed`
- full S4 contract regression：`210 passed`
- 下一实施范围 Project OS preflight：`pass / open blockers 0`

## 后续最小实现结果（2026-07-27）

用户以“继续”授权了处置中冻结的 current-blocker-only implementation。实现没有发起真实模型、Provider、网络、数据源或外部工具调用，也没有签发或消费 admission。

- 新增 runtime Specialist segmented `v8` capability；v1–v7 注册和请求行为保持不变。
- 新增共享 `fin01.s3.specialist_WWC_judgment_atom_deterministic_assembly:v1`，同一 policy 生成 prompt schema、closed alias surface、validator、canonical assembler 与 fake-Provider fixture。
- Provider 只输出 `what_would_change_judgment_atoms`；本地拥有 task ID、Claim/authority expansion、authority kind、source target、exact as-of、nested decision rule/time window、expected-transition 文本、ordering 与 lineage。
- Evidence/Numeric/Candidate/Graph aliases 全部从当前 Cell `authority_refs` 与冻结输入元数据生成；Provider 不再输出 raw authority refs。
- 新增 DELL research profile v2：WWC 1,800 tokens、Specialist 4,600、Lead-v6 full-chain aggregate 18,000；atom narrative 160 chars、Provider wire 4,800 bytes。
- contract-owned 三任务最大形状 fixture 低于 4,800 bytes；unknown/wrong-kind/cross-cell alias、非法 shape/enum/text/byte 都通过 content-free typed telemetry fail-closed。
- DELL frozen-input fake Provider 完整链达到 6 nodes、12 callbacks、9 Artifacts；canonical Artifacts 中无 atom surface 或 Q/A alias residue。

本实现没有改写 R5 failed/0 Artifact truth，也没有关闭 `RC-P36-061`。dependency/conflict、Writer/Verifier 与 all-node atomization仍后传 S4-T10 至 S5。

下一项为独立零调用：

`S4-T05-DELL-SPECIALIST-WWC-JUDGMENT-ATOM-AND-DETERMINISTIC-TASK-ASSEMBLY-FRESH-AGENT-PROOF-DECISION`

## Fresh-agent proof 结果（2026-07-27）

用户再次以“继续”仅授权独立零调用 proof decision。新增 proof generator 在两个 disposable runtime clones 上重算同一 DELL exact input：

- clone execution counts 前后均为 `5 WorkUnits / 5 Attempts / 5 ResearchRuns / 0 Artifacts`。
- 新 identity 为 `wu_p02_5_4fc6d8f6a641779d1c97861f / attempt_fin01_f34ce162a7e166702a3f5262 / research_run_fin01_e187ada6b55d471d462e3242`，目标 Runtime 中全部 absent。
- implementation SHA 和全部 exact code bindings、Specialist-v8 capability、WWC atom policy、DELL profile-v2 及 `1800/4600/18000` 预算重算通过。
- prospective R6 admission digest 为 `ac44bff5dda2911465859dc48dfbce44aefaa22533b74321c96fedc816a4b265`；文件保持 absent，未签发、未消费、未执行。
- 目标 canonical database、object tree 与 logical snapshot 前后不变；R5 consumed/failed/0 Artifact 与 restricted capture 未重写。
- model/provider/network/source/tool/admission/write/paired/Human 均为 0。

`RC-P36-062` 进入 `fresh_proof_contract_frozen_admission_issuance_pending`；`RC-P36-061` 仍为 live-unproven，DELL R2 仍未证明。dependency/conflict、Writer/Verifier 与 all-node atomization 继续后传。

下一项仅允许在独立授权下原样签发 frozen R6 admission：

`S4-T05-DELL-SPECIALIST-WWC-JUDGMENT-ATOM-AND-DETERMINISTIC-TASK-ASSEMBLY-FRESH-EXACT-ADMISSION-ISSUANCE-DECISION`

验证结果：

- fresh-proof contract：`7 passed`
- v7＋TaskClaim＋WWC authority＋Lead projection＋v8 implementation/proof 相邻链：`76 passed`
- S4-T05 contract regression：`187 passed`
- full S4 contract regression：`228 passed`
- Python compile：`pass`
- 下一 issuance 范围 Project OS preflight：`pass / open blockers 0`

未运行：真实模型、Provider/network/source/tool、admission issuance/consumption、exact-live、paired assessment 与 Human Review。

## R6 fresh exact admission 签发结果（2026-07-27）

用户以“签发”只授权 frozen R6 admission issuance。签发前重新执行两次独立 disposable-clone proof；输出与 frozen decision 完全一致，target counts 前后仍为 `5/5/5/0`。

- admission ID：`fin01-s4-t05-dell-specialist-wwc-judgment-atom-fresh-exact-admission-r6`
- admission digest：`ac44bff5dda2911465859dc48dfbce44aefaa22533b74321c96fedc816a4b265`
- admission file SHA256：`90f0905ef4cf323998b1a4c86cfabf50bf204037f9e63d4a3784a4dba5988acd`
- issuance record SHA256：`5926cb9859c16b02487082e32ac615483a51e27da5ca4167d9725d627a2397df`
- Specialist transport=`v8`、research profile=`DELL v2`、WWC atom policy=`v1`、Research Lead=`v6`，`1800/4600/18000` 预算保持冻结值。
- fresh WorkUnit/Attempt/ResearchRun 继续 absent；五个历史 ResearchRun 保留，R5 consumed/failed/0 Artifact 未改写。
- issued=true，consumed=false，execution started=false；model/provider/network/source/tool/WorkUnit/Attempt/Run/Artifact/paired/Human 均为 0。

验证：

- issuance verifier：`issued_unconsumed_zero_call_preflight_pass`
- 新 issuance contract：`5 passed`
- S4-T05 contract regression：`192 passed`
- 完整 S4 contract regression：`233 passed`
- Python compile：`pass`
- 下一 execution-authority scope Project OS preflight：`pass / open blockers 0`

RC-P36-062 推进到 `fresh_exact_admission_issued_unconsumed_execution_authority_pending`；RC-P36-061 仍为 `R5_consumed_failed_upstream_projection_live_observation_unproven`，DELL R2 仍未证明。

下一项仅为：

`S4-T05-DELL-SPECIALIST-WWC-JUDGMENT-ATOM-AND-DETERMINISTIC-TASK-ASSEMBLY-R6-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT-AUTHORITY-DECISION`

该门必须另行授权；当前未检查 credential presence、未消费 admission、未启动 supervisor 或 exact-live。失败后不得 paired/retry/rerun；成功也必须先满足 6 nodes、12 calls、9 Artifacts、三 Specialist WWC v8 consumption、Lead-v6 gap projection live observation、layered acceptance，才允许 paired assessment。

## R6 exact-live execution authority 决策（2026-07-27）

用户以“继续”授权本轮只完成 R6 exact-live execution authority decision。授权合同：

- authority decision：`configs/releases/fin_ia_0_1_s4_t05_dell_specialist_wwc_judgment_atom_r6_exact_live_execution_and_paired_assessment_authority_decision_v1_0.json`
- decision SHA256：`0e059de45c542bf380caea142e5f27abfd5f58445ddba9f89cfffa594537cfbc`
- Project OS preflight：`pass / open blockers 0`
- runner preflight：`pass_exact_zero_call_execution_preflight`
- credential 仅确认存在；值未读取、输出或持久化，Provider health probe=false。
- transport retry=0；host supervision receipt 有效；fresh supervision root absent。
- target identity 继续 absent，canonical counts 前后均为 `5/5/5/0`。

授权边界只允许下一项 exact-once admission consumption 与 R6 exact-live execution。自动 retry、fallback、replay、relaunch、patch、rerun、失败后 paired assessment、Human Review、S4-T06+、dependency/conflict/Writer/Verifier/all-node atomization均未授权。

paired assessment 仅在同一 coherent Run 达到 `succeeded/succeeded/succeeded`、`6 nodes / 12 semantic calls / 9 Artifacts`，三 Cell WWC segment 均消费 Specialist-v8 judgment atoms 并由本地确定性组装 task、Provider atom/alias residue=0、Lead-v6 gap projection live-observed、finding parity 与 layered acceptance 全部成立后才允许。

本轮未消费 admission、未启动 supervisor、未发起模型/Provider/network/source/tool 调用、未创建 WorkUnit/Attempt/Run/Artifact。focused S4-T05 regression=`196 passed`；完整 S4 contract regression=`237 passed`。

RC-P36-062 推进到 `R6_exact_live_authorized_execution_not_started`；RC-P36-061 继续为 `R5_consumed_failed_upstream_projection_live_observation_unproven`，DELL R2=false。

下一项为：

`S4-T05-DELL-SPECIALIST-WWC-JUDGMENT-ATOM-AND-DETERMINISTIC-TASK-ASSEMBLY-R6-EXACT-LIVE-EXECUTION`

## R6 exact-live pre-admission failure 终态（2026-07-27）

用户已授权持续执行到 R6 exact-live 终态。本轮只启动了一次 supervision runner，并严格执行首个可信失败即停止：

- runner 在 `create_app -> Fin01ResearchRuntime.__init__` 阶段以 `ValueError: s4_admission_research_profile_binding_mismatch` 退出。
- 冻结的 `S4CaseRuntimeBinding.research_profile_ref` 仍为 `fin01.s4.research_profile.dell_oem_three_cell:v1`；R6 exact admission 绑定 `fin01.s4.research_profile.dell_oem_three_cell:v2`。
- 失败发生在 WorkUnit 创建、admission 消费与 Provider 调用前；fresh WorkUnit/Attempt/ResearchRun 继续 absent，canonical counts 前后均为 `5/5/5/0`。
- admission issued=true、consumed=false、canonical execution started=false；model/provider/network/source/tool calls 全部为 0，Artifact=0。
- runtime guard 的 fail-closed 行为正确；问题归属为项目内 case runtime binding/version propagation drift，不是 DeepSeek、模型或 Provider。
- 原 preflight 验证了 admission、profile registry 与 executor factory，但没有实例化 `Fin01ResearchRuntime/create_app`，因此漏掉了 case binding 与 exact admission profile 的等值门。
- 自动 retry、fallback、replay、relaunch、patch、rerun、失败后 paired assessment 均为 0；DELL R2 未证明。

新增根因：

`RC-P36-063-s4-R6-research-profile-v2-case-runtime-binding-drift`

RC-P36-062 仍是“R6 未到达 Specialist-v8 live path”，RC-P36-061 仍是“未到达 Research Lead-v6 live path”，两者均不得关闭或宣称复发。

失败结果：

- `configs/releases/fin_ia_0_1_s4_t05_dell_specialist_wwc_judgment_atom_r6_exact_live_execution_pre_admission_failure_result_v1_0.json`
- SHA256：`a07fa25b6dacb6a0d766ec0f7ccedb54e59f1eb5ab0c23c8c56958eddb9489c7`
- S4-T05 contract regression：`200 passed`

下一项仅为独立零调用处置：

`S4-T05-DELL-R6-RESEARCH-PROFILE-V2-CASE-RUNTIME-BINDING-MISMATCH-FIRST-CREDIBLE-FAILURE-ROOT-CAUSE-DISPOSITION-DECISION`

本轮不修复、不重发、不重跑、不做 paired，也不进入 S4-T06 或后续序列扩展。

## RC-P36-063 零调用根因处置（2026-07-27）

用户以“继续”只授权 RC-P36-063 根因处置。本轮没有修改 runtime、签发 admission 或发起任何模型/Provider/网络调用。

审计确认 R6 的不一致发生在 preparation 阶段：

- 冻结 T02 DELL Case Pack 仍以 `fin01.s4.research_profile.dell_oem_three_cell:v1` 编译 T03 base binding。
- R6 fresh proof 用该 v1 binding 生成 exact input、consumer injections 与 `input_digest=3499c03470c5bec5168dc87a2974802869da389f2ef588f41021731828d09e96`。
- 随后 prospective admission 单独更新为 profile-v2；runner preflight 用同一个 v1 binding 重建 input，因此通过 input parity。
- `Fin01ResearchRuntime` 重新加载 v1 binding 并与 admission-v2 比较，正确在 WorkUnit/Provider 前 fail-closed。

这说明最早错误不是 equality guard，而是“不可变 Case Pack binding”和“可版本化执行容量 profile”缺少显式 overlay lineage，导致 preparation 与 admission 分叉。

选定最小合同：

`fin01.s4.case_runtime_research_profile_overlay:v1`

实现边界：

- 不修改 T02 Case Pack SHA、T03 base binding digest、MU binding 或历史默认 v1 loader。
- exact admission 只能请求已注册的 `BoundedResearchProfile`；必须校验 company、三 Cell axis 与 cell count。
- 有效 binding 记录 base binding/case-pack/profile contract lineage，并重算 effective binding、7 consumer injections、role/alignment/dispatch、input 与 preparation digests。
- runner preflight 和 `Fin01ResearchRuntime` 共享一个 admission→effective binding resolver。
- process launch 前必须在 disposable clone 上运行 `create_app` 或等价 application-runtime binding path；Provider callback、canonical write、credential value read 均禁止。
- executor 的 input binding/admission profile equality 继续 hard fail-closed。

R6 处置：

- admission 与 failure result 均保持 immutable。
- R6 状态为 `issued_unconsumed_invalid_for_relaunch_due_to_internal_exact_binding_inconsistency`。
- 禁止原地 rebinding、消费、复用 identity 或重跑。
- 未来 R7 必须重新准备 input/digest，生成新 WorkUnit/Attempt/ResearchRun identity，并分别经过 fresh proof、issuance 和 execution authority。

决策文件：

- `configs/releases/fin_ia_0_1_s4_t05_dell_r6_research_profile_v2_case_runtime_binding_mismatch_zero_call_root_cause_disposition_v1_0.json`
- SHA256：`1fb954f3169a5ada585aaa211500c8fdac2c8fbbe83cdd14a37b8b4f4b4b7006`

验证：

- 新决策合同：`6 passed`
- S4-T05 regression：`206 passed`

RC-P36-062 仍未到达 Specialist-v8 live path；RC-P36-061 仍未到达 Lead-v6 live path。DELL R2=false，S4-T06 未进入。

下一项仅为：

`S4-T05-DELL-R7-PROFILE-V2-VERSIONED-CASE-RUNTIME-BINDING-AND-CREATE-APP-PREFLIGHT-MINIMUM-ZERO-CALL-IMPLEMENTATION`

该实现需独立授权；本轮未实施、未生成 R7、未调用、未 paired。

## RC-P36-063 R7 profile-v2 binding 最小实现（2026-07-27）

用户以“继续”授权已选定的最小零调用实现。本轮完成：

- 新增 `fin01.s4.case_runtime_research_profile_overlay:v1`，从冻结 base binding 生成 immutable effective binding 和可校验 lineage receipt。
- 保持 DELL/MU 历史 loader 行为不变；DELL base digest 仍为 `78755ee3afa99ae5d33a170ee8184ef073fc895377ff1f668bfaf100358cf187`。
- DELL profile-v2 effective binding digest=`42d257e791129b61c12ac7cd7e513b9da30ddf0ba0ea8bf88ca8fae48360bf89`，overlay digest=`36844435ce367fc3ddc9a819195316a0b7e60bcbc3077a8bb0404614bdcaa512`。
- runner preflight 与 `Fin01ResearchRuntime` 共享同一 admission→effective-binding resolver；disposable clone 上的 `create_app` application path 在 credential 检查前执行。
- v2 input 嵌入 overlay lineage 并重算 7 consumer injections、input/preparation digest；executor 对无 overlay 的 v2 binding 继续 hard fail-closed。
- 旧 R6 使用 stale input，现会在 credential 检查前以 `s3_t09_current_exact_input_or_identity_drift` 拒绝，不能被重绑或重跑。
- 内存 R7 fixture 以新 identity/input 通过 resolver、double compile 与 `create_app`，Provider callback=0、canonical writes=0；fixture identity 不构成 admission 或执行授权。

实施结果：

- `configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_case_runtime_binding_and_create_app_preflight_minimum_zero_call_implementation_v1_0.json`
- SHA256：`10e5d1b637e7dc990e8b543e941589d5a182bb0d67e958966eb0852d8fba3505`
- focused：`8 passed`
- S4-T05：`212 passed`
- 完整 S4：`249 passed`

本轮没有创建或签发 R7 admission，没有模型/Provider/网络/source/tool 调用，没有 canonical execution、Artifact、paired assessment 或 Human review。RC-P36-062 与 RC-P36-061 仍需未来 coherent exact chain 的 live evidence，DELL R2=false，S4-T06 未进入。

下一项仅为独立零调用：

`S4-T05-DELL-R7-PROFILE-V2-VERSIONED-CASE-RUNTIME-BINDING-FRESH-AGENT-PROOF-DECISION`

不得直接签发 admission、执行 exact-live、做 paired，或扩展到 S4-T06/后续序列。

## R7 fresh chain 与 exact-live 终局（2026-07-27）

用户持续授权到 exact-live 结束。本轮依次完成了 R7 fresh proof、admission issuance、runner preflight、一次性 execution authority 和唯一 supervised exact-live；没有自动重试、fallback、replay、relaunch 或第二次 R7。

R7 exact identity：

- WorkUnit：`wu_p02_5_60a289c44e6b3b4c66c409bc`
- Attempt：`attempt_fin01_edd02d2209af026b6fce532d`
- ResearchRun：`research_run_fin01_32fda07ef9f6d273b30a1732`
- input digest：`affb9eb031b9b8f85573fc7077f69a09b35e88a3ab6687dcd85f921b68b983a0`
- preparation digest：`5acfa300fa7e5aff944455135d33902331f9b498ec04ccfc4522644ec00d510c`

运行到达 Verifier 后终止：

- canonical states=`failed/failed/failed`
- terminal reason=`bounded_agent_profile_error:ValueError`
- Artifact=0、orphan=false
- admission consumed=true
- paired assessment 未执行，DELL R2=false

gateway ledger 以 ResearchRun 精确过滤后证明：

- model call started/finished=`12/12`
- `status=ok`=`12`，`finish_reason=stop`=`12`
- Specialist-v8 三 Cell × 三 segment=`9`
- Research Lead-v6=`1`、Memo Writer-v3=`1`、Verifier=`1`
- input/output/total tokens=`69,697 / 6,658 / 76,355`
- latency sum=`92,828 ms`
- transport attempts=`12`、transport failures=`0`

因此首个可信失败不是 DeepSeek 一般性不遵循、输出截断、credential、网络或 Provider transport。Verifier 已成功返回，失败发生在本地 Verifier 后、成功 execution-output materialization 之前。

同时发现项目侧 observability 缺口：runtime result 的 `failure_observation={}`、`observed_counts=null`、usage receipts=0、tokens=0、capture=0，与 gateway 证明的 12 次成功调用矛盾；原始 ValueError message 也未持久化，当前不能诚实指认更具体的 validator/materializer throw site。

新增 issue：

`RC-P36-064-s4-R7-post-verifier-untyped-valueerror-and-lost-failure-observability`

费用只能给出区间。gateway 未记录 input cache hit/miss token 分配，按 admission 价格：

- 全部 input cache hit：USD `0.00604511`
- 全部 input cache miss：USD `0.03611066`
- 两者都低于 USD `0.10` ceiling

终局工件：

- `configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json`
- SHA256：`04f5dfc0b5cb1190ffe56966a9725045b50e3cbf87df929ad33a0ea783b0ffcf`

下一项仅为：

`S4-T05-DELL-R7-POST-VERIFIER-UNTYPED-VALUEERROR-AND-LOST-FAILURE-OBSERVABILITY-FIRST-CREDIBLE-FAILURE-ROOT-CAUSE-DISPOSITION-DECISION`

该项必须先以零调用方式恢复 throw-site/failure-observation 证据并选择结构性处置；本轮不 patch、不重跑、不 paired，不进入 S4-T06。

最终验证：

- R7 proof + issuance + authority + failure result：`14 passed`
- 完整 S4 contract regression：`263 passed`
- release JSON：`271 valid`
- Project OS JSONL：`24 files / 1,148 records valid`
- `compileall`：pass
- refined credential/secret scan：`0`
- `git diff --check`：无 whitespace error（仅既有 CRLF→LF warning）

历史 S4 测试仅更新 current-state selector，使其优先读取不可变 R7 failure result；历史 proof、issuance、authority 与 failure 工件本身未被改写。对已经被后续账本推进影响的旧 issuance verifier，不再把当前测试文件哈希误当成历史签发时哈希重新验证。
