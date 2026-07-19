# 227 隔壁任务自适应监督与上下文分层加载

日期：2026-07-17
状态：`heartbeat_active / first_adaptive_review_completed / repair_pending`

## 问题

旧监督自动化每次携带固定 Prompt，容易在目标任务状态变化后继续执行过时步骤；如果每轮重新全文读取 PRD、TECH、ReleaseContract、FeatureScope、backlog 和 ledgers，又会产生无意义的 context/token 消耗。

## 决策

1. heartbeat 只负责唤醒，不预写固定下一步。
2. 每轮先读取目标任务最新 turn/status 和 compact checkpoint；没有新 revision 时不发送消息。
3. 四份稳定合同先校验 SHA-256；digest 不变时只读取当前 execution point 的 backlog 子树和本轮 changed artifacts。
4. 只有合同变化、跨 release/Point、closeout/authority transition、跨 owner 冲突或审批规则不清时才全文展开。
5. 模型记忆只用于决定检索方向，不作为 gate evidence；审批仍需独立验证 Git、digest、tests、权限和调用/写入计数。
6. checkpoint 只在新 completed turn 已形成 disposition 后更新，并明确不是 release/gate authority。

## 落地

- automation `point-01` 已更新并启用，名称为 `FIN 发布自适应审计监督`，每十分钟运行；
- target execution thread：`019f54fe-4b90-74c0-b5e7-6325c47b77ce`；
- compact state：`docs/project_os/release_adaptive_supervision_checkpoint_v0_1.json`；
- 首项任务：独立审核 B0.7/v2.10；未通过前不得进入 operational baseline、Point01 Step2 或 FIN 0.1 `P02.0`。

## 边界

- 不从目标任务自述直接批准；
- 不自动批准 paid/full-chain、production cutover、商业数据、秘密持久化或真实业务 Case mutation；
- 本轮只修改监督方式和缓存合同，没有执行项目 runtime、模型、网络、数据库 migration 或业务 Case。

## 第一轮动态审核结果

目标任务最新完成 turn：`019f6bf8-934f-7222-8e90-013a1c92248d`。

独立复核接受：

- v2.8 + v2.10 定向回归 `22 passed`，相关 `compileall` 通过；
- package、plan、blueprint 及三个 gate 的 canonical digest 全部匹配；
- package 绑定的 Git-index 输入 `79/79` 匹配；
- fixed approval DB SHA-256 保持为 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`；
- v2.10 formal namespace 不存在；单一 runtime routing 与 trigger DDL digest binding 可接受。

独立复现的阻断：

1. 使用不存在的 `review_receipt_id` 和任意合法形状的 `review_receipt_digest`，仍可通过 `validate_production_human_jit_window_approval_v2_10` 并生成 production context。当前 production provenance 只做自报字段验证，没有解析 package-external reviewer decision artifact/ledger。
2. `execute_approved_window_core` 的 production 分支可在生命周期开始前把整条执行图委托给任意 `production_runner`；无副作用 probe 直接返回 sentinel。现有四分支 fixture 使用 v2.8 synthetic child，未实际执行 v2.10 registrar/parent/clean-child production dependency graph。
3. production adapter 在 child consume 后若 `open_existing` 本身失败，尚无已执行回归证明可凭已知 authority root/receipt 恢复 durable `outcome_unknown`。

已向目标任务发送：`REJECT_AND_REPAIR_B0_7_V2_10_EXECUTION_PROOF_ONLY`。只允许修复 reviewer receipt resolution、真正共享的 package-bound lifecycle kernel 和 post-consume recovery；不得进入 baseline、Step 2-5、paid/full-chain、production cutover、商业数据、真实业务 Case mutation或 fixed/secret store 写入。

## 第二轮动态审核结果

目标任务完成 turn：`019f6eae-683c-7240-8f6e-18d6573cc7e9`。

四份 FIN 0.1 稳定合同 digest 未变化，因此本轮没有全文重载 PRD、TECH、详设或 Point 02-07 backlog。独立复核结果：

- v2.8 + v2.10 focused suite `26 passed`，相关 `compileall` 与 targeted cached diff check 通过；
- 新 package/gate、plan/gate、blueprint/gate canonical digest 全部匹配，Git-index package inputs `79/79` 匹配；
- 旧 `production_runner` / `execute_approved_window_core` callback bypass 已从 active source/test 消失；production wrapper 与 synthetic fixture 均进入唯一 `execute_approved_window_kernel`；
- package-external reviewer receipt 的 missing/digest/actor/package drift、valid binding 和 CLI no-side-effect preflight 均有 deterministic proof；
- first ledger reopen failure 能按 known authority root 恢复 `outcome_unknown`，且 replay denied；
- fixed approval DB fingerprint 未变，formal namespace 和正式 execution counts 均为零。

Disposition：`APPROVE_B0_7_L2_EXECUTION_PROOF_ONLY`。该批准只覆盖 static package + synthetic same-kernel execution proof，不是 M2 operational qualification、Point 01 complete 或 production ready。reviewer receipt 当前只有 integrity/exact binding，不具备 production-grade PKI/企业身份不可抵赖能力；该限制在 Foundation Alpha 的 `production_readiness=not_admitted` 边界内接受并转 deferred release-security backlog。

已动态授权下一点 `P01-G2.0_OPERATIONAL_TRANCHE_FREEZE_ONLY`：只冻结一条 baseline 与 wrong package/approval、stale input/version drift、unauthorized transport 三个负例，并把其余十二场转 named regression backlog。本轮禁止生成 active receipt 或执行 scenario；待 tranche exact digest 形成后再独立决定执行授权。

## 第三轮动态审核结果

目标任务完成 turn：`019f6ed2-c355-7ea2-bedf-c49bd349b1bb`。

四份稳定合同 digest 仍未变化，本轮只展开 P01-G2.0 变更。独立复核确认：

- tranche/gate canonical digest 分别匹配 `8df521fcc321c6c5dfa30f6ae7a3ad377a0be223c21091525ef741d9208a047f` 与 `cfe1f33f2c06b109561fcda349dc1a7e06e249b3ceb7804ef7d81faf76c14a87`；
- v2.10 Git-index 输入 `79/79`、tranche freeze 输入 `5/5` 匹配；
- focused suite `31 passed`，相关 `compileall` 与 cached diff check 通过；
- fixed approval DB 指纹未变，formal namespace 仍不存在，冻结期执行计数全为零。

Disposition：`REJECT_AND_REPAIR_P01_G2_0_AUTHORITY_AND_COVERAGE_MODEL_ONLY`。静态冻结质量通过，但不能据此授权执行，原因是：

1. 已接受的 B0.7 blueprint 只允许 baseline authority，并明确禁止其余 scenario 获得 authority；当前 tranche 却为 stale 与 unauthorized-transport 规划 receipt、namespace 和 runtime，越过了上游 authority contract。
2. 新增的 wrong-package/approval 负例被标成原 `p01-oracle-path-access`，而原 oracle-path 语义没有进入 named backlog，造成 ID 集合闭合但行为覆盖缺失。

已要求目标任务保持 B0.7 exact family 不变：只有 baseline 可以规划 future operational authority；三个负例全部降为无 authority、无 receipt/namespace/runtime 的 pre-authority/boundary probe。wrong-package/approval 必须标为 supplemental case，原 16 场按 3 个实际消费语义加 13 个 deferred regressions 做无遗漏闭合。修复前不得进入 P01-G2.1 或创建任何 active execution artifact。

## 第四轮动态审核结果

目标任务完成 turn：`019f6ef0-468e-7240-b813-b5ba81815d67`。

稳定合同 digest 仍未变化。P01-G2.0 v1.1 的独立复核通过：

- tranche/gate canonical digest 分别为 `aeeccb1525d693f1dc19eb42a6f9666fed3ebf4a3b3f578f73fd8dc22678f861` 与 `32cc169081b9e4158894925d4fb207824c28bc17e408190e6cce900de950b7a5`，均匹配；
- v2.10 Git-index 输入 `79/79`、v1.1 freeze 输入 `5/5` 匹配；
- focused suite `38 passed`，相关 `compileall` 与 cached diff check 通过；
- coverage 已改为三个 original selected、十三个 original deferred 和一个 supplemental probe，原 `p01-oracle-path-access` 已恢复；
- 只有 baseline 保留 future single-use authority；三个负例的 authority、receipt、namespace、runtime 和 terminal lifecycle 计数均为零；
- fixed store 指纹未变，formal namespace 仍不存在，冻结期执行计数全为零。

Disposition：`APPROVE_P01_G2_0_V1_1_FREEZE_AND_AUTHORIZE_P01_G2_1_EXACT_OPERATIONAL_TRANCHE_EXECUTION_ONLY`。授权只覆盖一次 baseline operational execution 和三个无 authority 的 pre-authority probes；不是 production cutover、Point 01 complete 或 FIN 0.1 entry。

执行必须使用 case-local isolated roots：baseline 经唯一 v2.10 production lifecycle kernel，actual schema/digest validation 先于 terminal success；三个负例不得继承 baseline namespace、receipt 或 runtime。transport probe 只能被本地 canary 截获，不能产生真实 outbound network。执行结束后只能写 `P01_G2_1_OPERATIONAL_TRANCHE_EXECUTED_PENDING_INDEPENDENT_REVIEW` 并等待下一轮审计。

## 第五轮动态审核结果

目标任务完成 turn：`019f6f09-0156-74a1-9586-2c7fd8a17dac`。

四份 FIN 0.1 稳定合同 digest 未变化，本轮仅复核 P01-G2.1 的执行包、隔离运行根、append-only receipt ledger 和失败产物。独立核验确认：

- execution package / gate canonical digest 分别为 `7ded46ddadb54a697877e3426bab8b9ab868bab0ceb7c2cd735a7349b15339e1` 与 `6bf29f9397d82d1e2b540c2520cb1f85f9f51c2886e28ba77169e5c23668340d`，均匹配；package staged inputs `13/13` 匹配；
- P01-G2.1 定向合同测试 `12 passed`，cached diff check 通过；
- baseline receipt 只注册和消费一次，ledger 顺序为 `REGISTERED -> CONSUMED_BEFORE_RUN -> TERMINAL(outcome_unknown)`；terminal digest 为 `13785b7d5d0bdee2459842d1eaa7137eccdbd747aa969f36aa309970194daf8c`；
- baseline result digest 为 `58de7732bfeffee09d80f93fb997aa898727c7ea84e29d8c844f7607b92a858b`，当前 formal run 没有 actual/oracle/reviewer artifact；三个负例均未执行，且没有 authority、receipt、namespace 或 runtime；
- fixed approval DB SHA-256 仍为 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`，没有 network/tool/model/provider success、fixed-store write、legacy authority change 或真实业务 Case mutation；
- read-only reconstruction 能通过既有 admission/grant/ledger binding，因此当前故障位于 child actual runner 的更下游阶段；但 adapter 未持久化 stdout/stderr 或结构化 exception envelope，现有证据不足以确定具体 root cause。

Disposition：`APPROVE_INCIDENT_CONTAINMENT_REJECT_OPERATIONAL_QUALIFICATION_AUTHORIZE_P01_G2_1_R1_FORENSIC_REPAIR_ONLY`。本次 fail-closed 与隔离行为可接受，但 P01-G2 operational qualification 失败，Point 01 Step 3-5 和 FIN 0.1 entry 继续阻断。

已授权的 R1 仅允许：冻结现有 incident digests；为 child 失败持久化受限、脱敏的 execution envelope；使 terminal 引用 incident artifact digest；增加 deterministic failed-child 回归；把计数拆为 `baseline_attempt_count=1`、`baseline_success_count=0`、`actual_artifact_count=0`。禁止重用 consumed receipt，禁止签发新 operational authority，禁止运行三个负例、paid/full-chain、外部模型/工具、production cutover、商业数据或真实业务 Case。R1 经独立复核前，不得批准新的 baseline attempt。

## 第六轮动态审核结果

目标任务完成 turn：`019f6f2e-88ff-7d82-8d2a-d5971cb41866`。

稳定合同 digest 未变化。本轮独立复核接受了 R1 的主体行为：

- repair package / gate / historical reconciliation canonical digest 均可复算，八个 Git-index input hash 全部匹配；
- historical baseline result 与 consumed ledger 文件指纹仍匹配，fixed approval DB 指纹未变；
- 独立运行 receipt lifecycle、v2.8/v2.10、P01-G2.1 和 R1 定向回归得到 `49 passed`；
- historical terminal 未改写，计数已拆为 attempt=1、success=0、actual=0；没有新 authority、receipt、baseline、negative case、network、tool、model、provider 或 fixed-store 写入；
- future nonzero child 能在 parent 返回前生成 envelope，并将 digest/ref 绑定到 future `outcome_unknown`；root cause 仍保持 `not_determined`。

但 R1 gate 不能接受。独立安全探针复现：

1. `_argv_shape()` 把 `--token=SENSITIVE_VALUE_A` 整个 token 作为 role 输入，因此只改变 inline value 就会改变 `argv_shape_digest`，违反“shape digest 不含 secret value”的冻结合同。
2. `_redacted_excerpt()` 无法覆盖 `{"api_key":"SENSITIVE_VALUE"}` 的 JSON quoted-key 形式，也未处理 `User-Agent: SENSITIVE_AGENT`；两个值都会原样进入持久化 excerpt。
3. `source_refs` 当前按任意 `Mapping[str, str]` 原样进入 envelope，缺少 key allowlist、digest/identifier 格式和长度校验。

Disposition：`REJECT_AND_REPAIR_P01_G2_1_R1_SANITIZATION_CONTRACT_ONLY`。只授权 R1.1 修复上述值无关 argv shape、结构化 source refs 和 excerpt sanitization，并补 adversarial tests；不得扩大取证 schema、运行历史 baseline、签发新凭证或进入 P01-G2 后续。当前 R1 package/gate digest `3e9114adfde081240311228ebebf2de1b3f03f94570714c0d834022f60e46c9a` / `d91fb8c06679f98dbec09326633937fafc55a9375840a5f84901662bfabd75db` 保留为 rejected evidence，修复后必须生成 superseding digest。

## 第七轮动态审核结果与新监督规则 dry run

目标任务完成 turn：`019f6f52-18b4-7243-b410-1b7d29b702c5`。

本轮先将自动化保持 `PAUSED`，再按“Foundation Alpha 发布目标优先、P0-P3 风险分级、每 EP repair budget”做一次手动 dry run。稳定合同 digest 未变化，只复核 R1.1 的 changed artifacts 和已知三个泄漏面，没有新增 adversarial 范围。

- R1.1 package / gate / reconciliation digest 分别为 `3657309f5e2cea214d72acb57e97789fe362f69c92ee1222fff731e895459532`、`0646e5b60b9b1a4a318adc8e14ef03e283390de71697eae4b508a5fff354bd45`、`74bd8df676f895b621f09c24158b1b5570a6685e12cd8d72bcf33df044280688`，均可复算并精确 supersede rejected R1；
- Git-index input bindings `10/10` 匹配，compileall 与 cached diff check 通过；
- 独立组合回归 `65 passed`；手动行为探针确认 argv shape 不再依赖 inline value，JSON、User-Agent、Bearer、Cookie 和 URL query 测试值均被脱敏，不安全 source refs 在 child spawn 前被拒绝；
- historical terminal/ledger 未改写，fixed approval DB 指纹未变；新 authority、receipt、baseline、negative case、network、tool、model、provider、fixed-store write 均为 0；
- sanitizer 明确为 bounded supported-shape secret minimization，不宣称通用秘密移除；production root cause 仍为 `not_determined`。

`product_capability_delta`：未来 current-path nonzero child 现在具备 bounded、引用可追溯且不保留 raw stream 的故障 envelope，原始三类已复现泄漏已关闭。

`governance_cost_delta`：R1/R1.1 已增加两组 forensic manifests、策略、测试和监督审批；达到该 EP repair budget 上限，不再允许 R1.2 或新的 audit-only package/gate family。

`blocking_findings`：原 P01-G2.1 production actual leaf 的具体失败原因仍未知，operational qualification 尚未恢复。

`deferred_findings`：通用秘密检测、PKI/企业身份不可抵赖、生产 SLO 等保持 P2 release-security/backlog，不阻断 Foundation Alpha 的当前开发。

Disposition：`APPROVE_P01_G2_1_R1_1_BOUNDED_FORENSIC_PATCH_AND_AUTHORIZE_ONE_PRE_BASELINE_DIAGNOSTIC_TURN_ONLY`。下一步只允许在同一 P01-G2 lane 内用 copied/sanitized temporary inputs 复现原 actual-leaf 故障；若能确定当前路径 root cause，可同 turn 做一个最小修复和回归。不得新增 milestone/package/gate family。若一轮内不能复现或修复，停止并请求用户决定，不再自动扩展诊断。fresh operational baseline 仍需后续独立审批，且最多只剩一次机会。

## 第八轮动态审核结果：stop rule 生效

目标任务完成 turn：`019f6f8b-f050-7852-83c3-b28011ed084e`。

四份 FIN 0.1 稳定合同 digest 未变化。本轮只审查一次性诊断授权覆盖的两个代码文件、五个既有状态/记录文件和当前路径回归，没有扩展新的 package、gate 或 adversarial family。

- 诊断确认当前 baseline input 会先因 legacy adapter 未提供 `forbidden_substitutions` 而 full-validation typed stop；该缺陷不能解释历史 child nonzero，因为 public runner 会将其序列化为 typed stop，历史具体根因仍为 inconclusive；
- 本轮唯一代码修复为 evidence-role 到禁止替代规则的确定性映射，未知 role fail-closed；当前 AI-semis baseline 的七个 `issuer_metric` 和三个 `relationship_signal` 均被覆盖；
- 修复后同一隔离路径进入下一独立阻断 `case_delta_pack_lineage_missing`。执行任务遵守一次修复上限，没有继续修改第二处；
- 独立运行当前变更相关的五个合同测试文件得到 `53 passed`，JSONL 校验、cached diff check 通过；fixed approval DB SHA-256 仍为 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`；
- 四份稳定合同 SHA-256 与 checkpoint 完全一致；没有 fresh authority、receipt、baseline、negative probe、network/tool/model/provider 或 fixed-store write。

`product_capability_delta`：legacy-adapted evidence slot 现在具备明确、fail-closed 的替代边界，当前 compiler input 的第一处确定性阻断已消除。

`governance_cost_delta`：只增加一个映射 helper、一条聚焦回归以及既有台账更新；没有新增 milestone/package/gate family。自动 repair budget 已耗尽。

`blocking_findings`：`case_delta_pack_lineage_missing` 是下一次 operational baseline 必经路径上的已知 P1 阻断。带着它消耗最后一次 baseline 没有价值。

`deferred_findings`：历史 nonzero 的精确归因因 pre-R1 未保留 child streams 而无法恢复，按 P2 incident-forensics debt 记录，不再阻断当前代码修复；通用 sanitizer、PKI 和生产 SLO 继续留在未来 release gate。

Disposition：`CONDITIONAL_APPROVE_P01_G2_PRE_BASELINE_DIAGNOSTIC_PATCH_STOP_AUTOMATION_PENDING_USER_DECISION`。不授权第二轮自动修复，也不授权 fresh baseline。下一步必须由用户在“明确授权一次产品主链修复 `case_delta` lineage，完成后再决定是否消耗最后一次 baseline”与“缩小 Foundation Alpha operational scope，并相应重写 P01-G2/P01-G5 acceptance contract”之间作出产品取舍。

## 用户产品决策：保留 CaseInstancePack lineage

用户于 2026-07-17 明确选择保留三层 pack 泛化设计中的 case-instance lineage，并授权一次 `case_delta_pack_lineage_missing` 产品主链修复。该授权不是自动 repair budget 的延长，也不是新的审计 milestone/package/gate family。

实施边界：

- 复用现有 `PlanningPackVersion(scope_kind="case_delta")`、registry、selection 与 serializer 合同，不通过关闭 `require_case_delta_lineage` 绕过；
- 仅覆盖当前 Foundation Alpha 的 AI-semis baseline case，不顺带扩到 SaaS、医疗和银行 fixture；
- case 有调整时记录 delta；没有调整时必须显式记录 `no_override`、base pack refs、decision source 和可复算 payload digest，不能用无语义空 ref 通过 gate；
- compiler seed、pack metadata、registry resolution、selection reason、composition origin 和 serialized lineage 必须绑定同一 exact case-instance pack version；
- 增加当前主链正例与 lineage 缺失、digest/decision-source 不一致的最小负例；不扩建测试矩阵；
- 本轮不得运行 fresh operational baseline，不创建 authority/admission/receipt，不调用 network/tool/model/provider，不写 fixed/business store。

修复完成状态只能为 `P01_G2_CASE_INSTANCE_PACK_LINEAGE_REPAIR_PENDING_INDEPENDENT_REVIEW`。独立验收通过后，才可单独决定是否消耗最后一次 operational baseline。

## CaseInstancePack 独立验收与最后一次 baseline 授权

目标任务完成 turn：`019f7015-2649-7b83-8c01-31d7b5164a81`。

独立复核确认：

- 只有 `m2-a1-ai-semis-input` 新增 `pack-case-m2-a1-ai-semis-no-override:v1`；SaaS、healthcare 和 banks 保持无 case delta，符合本轮范围；
- payload 明确绑定 case、三层 base packs、decision source、freshness、promotion/source policy 和空 additions/removals/overrides；canonical digest 复算为 `71d9a25e7973db55ec0a99295e90d51d9acb2ed87c988b548d4e8089d00d28b9`，与 pack version 一致；
- seed、metadata、registry resolution、selection、composition 与 serializer 使用同一 exact ref；缺 payload、lineage、decision source、case/base-pack drift 和 digest mismatch 均在当前 assembly path fail-closed；
- 独立运行 assembly、registry、selection、serializer 和 compiler full-validation 五个相关套件得到 `30 passed`；JSONL、diff、稳定合同和 fixed DB fingerprint 校验通过；
- authority、admission、receipt、baseline、negative、network、tool、model、provider 与 fixed/business write 均为零。

`product_capability_delta`：当前 AI-semis baseline 已具备正式、版本化且可复算的 case-instance no-override lineage，`case_delta_pack_lineage_missing` 的已知主链阻断已解除。

`governance_cost_delta`：复用现有 pack 模型，增加一个 payload 合同、当前 fixture 和最小负例，没有新增 milestone/package/gate family。

`blocking_findings`：无已知 P0/P1 留在当前 CaseInstancePack 修复范围。

`deferred_findings`：通用 registry 仍允许未来非当前路径的 payload-less case-delta version，记为 P2 pack-registry hardening debt；当前 AI-semis assembly path 已显式拒绝，不阻断 Foundation Alpha。

Disposition：`CONDITIONAL_APPROVE_CASE_INSTANCE_PACK_LINEAGE_REPAIR_AND_AUTHORIZE_ONE_FINAL_OPERATIONAL_BASELINE_ATTEMPT_ONLY`。该产品授权分为两个不可合并的执行边界：先复用既有 family 冻结 current exact staged inputs 的 candidate package/admission preflight；独立复算 package、manifest 和输入 digests 后，监督方才可签发唯一 fresh digest-bound receipt 并允许一次执行。不得重用历史 consumed receipt。若本次 baseline 失败，必须保持 fail-closed、停止自动 repair/retry并请求用户裁决。只有 baseline 成功且 actual artifact、terminal、lineage、调用/写入计数独立验收通过后，才可继续三个既定 pre-authority negatives 或 Point01 后续 closeout。

## 最终 baseline candidate freeze 系统中断处置

目标任务 turn `019f7038-a9c4-7032-b6d5-da97f16ce843` 在 candidate freeze 中途以 system error 结束。仓库只留下现有 P01-G2 family 内的 validator、candidate policy 和 freeze script 草稿；尚无 candidate manifest/package/gate/preflight artifact、canonical digest、测试结果或完成状态，因此不存在可审批的 freeze。

- 四份稳定合同 digest 保持 `4/4` 不变；
- 两个 Python 变更文件可以 `py_compile`；candidate policy JSON 可解析；
- 没有证据显示 authority、receipt 或 baseline 被执行，但完整 zero-count 仍由续跑后的 freeze 结果证明；
- 本轮 `product_capability_delta` 为零；`governance_cost_delta` 是三个尚未闭环的局部实现文件；
- system error 不计作新的 repair，也不创建新的 execution point、milestone、package family 或 gate family。

Disposition：`CONTINUE_SAME_EP_AFTER_SYSTEM_ERROR_NO_APPROVAL_OR_REPAIR_BUDGET_CHANGE`。执行任务必须从现有半成品继续完成原 candidate freeze；完成前仍不得签发 receipt、执行 baseline 或进入 negatives。

## Final baseline candidate exact-digest 独立审批

目标任务 turn `019f7050-92b5-72b2-9fb3-4d869d83579a` 完成同一 EP 的 candidate freeze。监督方只复核本轮 candidate 工件和当前 execution path：

- input manifest / candidate package / preflight / gate 的 canonical digest 分别为 `bda9f0abb3efb56b65ab1868982ed92a677df62d1e8dc6eed6a6660e250fa1e4`、`bba3ce4bc30467b4997e2be71803e8bf01608411dae6dc0a27a60f6a02ac75f9`、`e9c24dae75f2ecc9f50c431365ad3ec8f2efbdc37ee06297977d730dbb2e643b`、`755c2decbe0aaf808d19f0e4a13e076ebc5e4b95afbb91a09a1dd5c814235c33`，四项均可独立复算；
- manifest 中 100 个 Git-index 输入 SHA-256 全部匹配，且不包含监督 checkpoint/worklog，审批记录不会制造自引用漂移；
- 独立聚焦回归 `33 passed`，fixed approval DB SHA-256 与四份稳定合同 digest 均未变化；
- candidate、preflight 和 gate 的 authority/admission/receipt/baseline/negative/runtime/network/tool/model/provider/fixed-business write 计数均为零；
- CaseInstancePack exact ref/digest、accepted forbidden-substitution patch 和八项 superseded historical input drift 均显式绑定，历史 consumed receipt 保持不可重放。

`product_capability_delta`：当前 AI-semis baseline 第一次具备一个可独立审批、精确绑定现有 runtime 输入且不携带历史权限的 future-only candidate。

`governance_cost_delta`：新增一个 candidate policy、四个静态 artifact、一个复用既有 family 的 freeze runner、validator 和三个聚焦测试；未新增 milestone/package family/gate family。

`blocking_findings`：无 P0/P1 留在 candidate freeze。`P2-pack-registry-case-delta-payload-hardening` 继续留在 backlog，不阻断本轮。

Disposition：`APPROVE_FINAL_BASELINE_CANDIDATE_EXACT_DIGESTS_AND_AUTHORIZE_ONE_FRESH_SINGLE_USE_RECEIPT_PLUS_ONE_BASELINE_EXECUTION_ONLY`。执行必须绑定上述四个 exact digest，使用 fresh isolated operational store，禁止复用历史 receipt；只运行 AI-semis baseline，不运行三个 negatives。若失败，立即 fail-closed 并请求用户裁决，不得 repair、retry、replay 或重签 receipt。

## Pre-execution compatibility stop 与一次 bounded bridge repair

目标任务 turn `019f706f-28e9-7440-afe8-3abec0924160` 在创建 authority/receipt 前正确 fail-closed。独立复核确认：candidate 四个 digest 与 100 个输入仍全部有效，但现有 production runner 固定读取 historical v2.10 execution package；candidate 使用独立 freeze schema，不能通过 `execution_package_contract()`，而 historical v2.10 package 已对当前八项输入产生 hash drift。

该问题按监督风险合同归类为 **P1 当前路径阻断**，不是 P0：没有实际越权、数据破坏、证据伪造、秘密泄漏或外部副作用。authority、admission、receipt、namespace、runtime 和 baseline 均未创建，最后一次 operational attempt 尚未消耗。

`product_capability_delta`：本轮无新增运行能力，但证明了当前 candidate 与 production kernel 之间缺少可执行桥接，且 fail-closed 在权限创建前生效。

`governance_cost_delta`：只增加只读 preflight 与事故记录；没有创建新 runtime/package family 或 receipt。

Disposition：`REJECT_AND_REPAIR_ONE_BOUNDED_CANDIDATE_TO_PRODUCTION_EXECUTION_BRIDGE_ONLY_P1_CURRENT_PATH`。允许在同一 P01-G2 execution point 内进行一次最小修复：复用既有 P01-G2 execution schema 和 v2.10 production kernel，生成一个绑定已批准 candidate 四 digest 与 100-input manifest 的 baseline-only executable package，并让 runner 显式消费该 package，而非硬编码 historical v2.10。修复轮只 refreeze 和测试，不得签 receipt 或执行 baseline。若该 bridge 复核仍失败，停止自动修复并请求用户裁决。

## Candidate-bound executable bridge 独立验收与最终 baseline 执行授权

目标任务 turn `019f707d-0a6c-7841-81f0-e5a4797619c7` 完成唯一一次 bounded bridge refreeze。监督方只复核本轮 bridge、候选四件套和既有 v2.10 production contract：

- bridge manifest / package / preflight / gate canonical digest 分别为 `d7904fb4ec7da8578abd7d47914c5ce073fa55d7035e6c58703ca29829525a6d`、`06a3ef6b5f1d8677e79e81676131ae3b8e83fcd87f9ccaeb9ed911100360f879`、`0ad2c6f8e5c3d157dc0cf2adbbe7d7fadf1f8f894be4c755e2e33cd8e8fad659`、`cf35d48b1200d1d3b7df661add38335f89f77a6158d1115a6bcf1df4244a2b38`；派生 inner v2.10 package digest 为 `4ca222da5dd5ab7991d258d49eb30a377e6c8f82e1a0885d8912567324d3d5e8`；14 个 candidate/bridge/derived artifact digest 全部可独立复算；
- bridge manifest 的 105 个 Git-index 输入及 working bytes 全部匹配；candidate 原四件套文件 SHA-256 与先前审批值完全相同，100/100 candidate inputs 未漂移；
- 独立运行 candidate、bridge 和既有 v2.10 execution-proof 回归得到 `22 passed`，相关 Python compileall 与 cached diff check 通过；
- 显式 bridge runner 的只读 preflight 通过，生产生命周期精确停在 `package_admission_required`；runner 不再选择 historical package，实际执行仍只能进入既有 v2.10 kernel；
- fixed approval DB 在复核前后 SHA-256 均为 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`；formal namespace 不存在；authority、admission、receipt、baseline、negative、runtime、network、tool、model、provider 和 fixed/business write 计数均为零；
- baseline-only bridge 显式禁用 negative cases，stable contracts `4/4` 未变化，legacy global authority 保持不变，production readiness 仍为 `not_admitted`。

`product_capability_delta`：当前 exact-approved AI-semis candidate 已能通过显式、digest-bound 的 bridge 进入既有生产执行生命周期；此前 freeze-only candidate 与历史 package 之间的主链断点已关闭。

`governance_cost_delta`：增加一个 bridge validator、两个 runner、一个策略、十个 bridge/derived manifests 和四个聚焦测试；这是已授权 bridge repair 的最终成本，不允许再新增第二个 bridge、runtime kernel、package/gate family 或扩展测试矩阵。

`blocking_findings`：bridge 范围内没有剩余 P0/P1。唯一待证明项是最后一次 fresh operational baseline 的真实 actual artifact 与 terminal 顺序。

`deferred_findings`：generic case-delta registry hardening、生产级 PKI/SLO 和通用 secret removal 保持 P2 backlog，不阻断 Foundation Alpha。

Disposition：`APPROVE_EXACT_CANDIDATE_EXECUTION_BRIDGE_AND_AUTHORIZE_ONE_FINAL_FRESH_BASELINE_EXECUTION_ONLY`。执行必须精确绑定上述 bridge digests、candidate 四 digest、100-input manifest、CaseInstancePack ref/payload digest、四份 stable contracts 和 fixed DB fingerprint；使用 fresh isolated persistent operational store，只创建一份 approval/admission/receipt，只运行 AI-semis baseline，禁止 negatives。actual artifact 必须先通过 schema/digest 校验并持久化，再写 success terminal。若执行失败或任一 binding 漂移，立即保持 fail-closed 并返回用户裁决，不得 repair、retry、replay、续签或创建第二份 receipt。

## 最终 baseline 失败的独立终态验收与监督缺口

目标任务 turn `019f709e-365d-7160-a798-46594cf54d87` 已完成并停止。监督方只读取 package-external authority、隔离运行目录、SQLite append-only ledger、incident envelope 和本轮五个状态/审计文件，没有执行测试、诊断、修复或第二次命令。

- reviewer decision / HumanApproval / admission / consumption grant / incident envelope / authority chain 六个 canonical digest 全部可复算；
- SQLite 中只有一条 receipt，状态为 `consumed_before_run`；事件序列严格为 `REGISTERED → CONSUMED_BEFORE_RUN → TERMINAL(outcome_unknown)`，三条 event payload digest 全部可复算；terminal digest 为 `728d9ebd2e5c215f0c782f258c22e154658f316286e3c058ce43c379b99f0342`；
- incident envelope canonical digest 为 `1cc0532137f2704966bf364017caa31da271e25be91cf6fc1b4b87449d08653e`，文件 SHA-256 为 `9bbb7cc3d0077865cff6cf5b97eb884de87e2071e8904a9a105dd23228a5aa62`；它只证明 `production_actual_clean_child` 返回 code 1；
- output 目录仅有 `child_execution_incident.json`，没有 actual、oracle、reviewer 或 closeout artifact；baseline attempt=1、success=0、negative=0；
- authority chain、admission 和 grant 均精确绑定 bridge package `06a3ef6b...0f879` 与 inner package `4ca222da...d3d5e8`；fixed DB SHA-256 仍为 `ae48eea1...ab561f4`；四份 stable contracts 未变化；
- 三个 negative、network/tool/model/provider、fixed/business write、legacy authority change 和 business Case mutation均未发生。

独立代码路径审计同时确认一个监督缺口：顶层 candidate-bound runner 虽显式接收 bridge package，但 `run_point01_m2_a1_actual_audit_clean_child_v2_10.py` 仍通过 `PACKAGE_PATH` 固定读取 historical v2.10 manifest。此前 bridge 验收的测试只检查顶层 runner 没有 historical package 常量，没有验证 package binding 是否端到端传播到 production clean-child leaf。执行任务在创建 authority 前已识别该问题，却按“一次 baseline”字面授权继续执行并消费 receipt。该行为没有造成越权、数据破坏或外部副作用，但违反了“已知确定性主链错误应在 authority 前停止”的产品意图。

`product_capability_delta`：本轮没有获得 operational qualification；获得的是一次真实、可审计且不可重放的 fail-closed 终态，证明 authority/receipt/terminal 控制链能约束失败。

`governance_cost_delta`：新增一份外部 authority chain、一个隔离 SQLite ledger、一个 incident envelope 和五个状态/审计更新；没有新增代码、测试、milestone、package family 或 gate family。该成本不再允许继续自动扩张。

`blocking_findings`：P01-G2 operational qualification 未通过；唯一 receipt 已消费；candidate-bound package 未端到端传播到 clean-child leaf；Point01 Step 3-5、P01-G5 与 FIN 0.1 entry 仍阻断。

`deferred_findings`：具体 child exception 因 bounded stderr 截断仍未被动态证据完整确认；production PKI/SLO、通用 secret removal 和 generic case-delta registry hardening继续留在既有 P2 backlog。

Disposition：`ACCEPT_FAIL_CLOSED_EVIDENCE_AND_STOP_FOR_USER_DECISION_OPERATIONAL_ATTEMPT_CONSUMED`。不得自动 repair、retry、replay、refreeze、续签或创建第二份 receipt；不得运行 negatives、进入 P01-G3/P01-G5 或 FIN 0.1。下一步只允许用户在“将 Foundation Alpha 范围降级为 contract/runtime proof，明确把 operational qualification 延后到独立产品 release”与“显式重新开启一个有独立预算和验收合同的 operational qualification track”之间裁决。

## 用户范围裁决（2026-07-18）

用户选择第一种路径。监督状态因此改为：Point 01 只以 `POINT01_FOUNDATION_ALPHA_CONTRACT_RUNTIME_PROOF_COMPLETE` 收口；`P01-G2` 明确保留为 `failed_single_operational_attempt_consumed_and_deferred_to_REL_PROD_001_RG1`，不得重试或重写为 pass。P02.0 只可做 fixture/shadow/internal development；FIN 0.1 release 仍必须在 P07.5 前由 `RG1_vertical_path` 补齐 entry→adapter→subprocess→clean-child identity、一次 bounded operational vertical run 与 actual/oracle/reviewer/Workbench 结果。该裁决不授权 runtime、authority、receipt、network/model/tool/provider、生产切换或真实业务 mutation。

## P02.0 contract/dependency freeze 事实更新

P02.0 已在该窄准入下完成九项静态合同：entry preflight、new-lane authority/rollback ADR、canonical object subset、route surface map、frontend dependency lock、OpenAPI baseline、P36/SaaS/Bank fixture manifest、cross-owner review 和 closeout decision。`P02.1/P02.2` 的状态仅为 `ready_for_skeleton_fixture_internal_development_only`，没有 implementation/runtime/operational/browser/release admission。完整证据见 worklog 235；`RG1_vertical_path` 的 identity + bounded run + actual/oracle/reviewer/Workbench hard debt 不变。
