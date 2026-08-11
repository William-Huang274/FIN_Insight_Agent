# FIN 0.1 S4-T06 MU R3 current-case identity boundary scope-replace 决策

日期：2026-07-29<br>
状态：已选择一次结构性 scope replacement；实现、fresh proof、R4 均未授权

## 问题

MU R3 在第一个 Specialist segment 后，以
`s4_case_delivery_identity_provider_narrative_invalid` 终止。受限复核显示
Provider 输出只含正确本案 `MU` 四次，`DELL/NVDA` 均为零，因此没有观察到
跨案例污染。

当前 `CaseDeliveryIdentityPolicy.provider_narrative_has_entity_token()` 把“非本案
身份污染”实现成“Provider 叙事不得出现 DELL/MU/NVDA 任一 token”，连当前正确
ticker 也会被拒绝。正向 fake 又把所有 ticker 替换成“发行人”，导致 deterministic
proof 没覆盖真实模型自然重复本案身份的路径。

## 裁决

选择 `scope_replace`，不选择永久阻断，也不继续 blanket ban。

新合同冻结为：

`fin01.s4.case_delivery_identity_current_case_aware_provider_boundary:v2`

- 当前 case ticker 可以出现在 Provider 叙事中，但只属于非权威分析上下文；
- 已登记的非本案 ticker 仍是 L1 hard failure；
- 当前与非本案 token 混合出现仍 fail-closed；
- title、workpaper、review、manifest 和 runtime identity 仍全部由本地 exact case
  projection 确定性装配；
- 最终 9 Artifact 必须独立重算 identity L1，模型 Verifier 不能替代该门；
- 新规则从 exact case projection 与 case identity registry 派生，不再由硬编码
  `("DELL", "MU", "NVDA")` tuple 充当策略 owner；
- 历史 v1 admission、已消费 Run 和 R3 failure 不重解释，新 admission 必须显式
  绑定 v2。

这不是把身份问题降级成质量 finding。只有正确本案 token 被允许；非本案污染和
任何最终交付身份错配仍是 L1 硬失败。

## 为什么不选择其他方案

- 继续 blanket ban：会持续把正确身份叙事误判成产品失败，并依赖脆弱的词面省略。
- 本地删除/改写 ticker：会隐藏污染，且让 capture 与实际接受文本不一致。
- 所有 identity token 降级为 finding：会削弱跨案例污染的 L1 完整性。
- 立即阻断 Agent delivery：当前本地 delivery owner 与 final L1 足以支撑一个有界
  的结构替换，因此还不需要放弃该范围。

## 唯一 replacement bundle

下一实现包必须同时完成：

1. DELL/MU/NVDA 三案在每个 Provider phase 自然出现本案 ticker，仍到达
   `6 nodes / 12 callbacks / 12 captures / 9 Artifacts`；
2. fake 不得清洗本案 ticker；
3. 每个 phase 的非本案 ticker 与 local+nonlocal 混合输入均 typed fail-closed；
4. wrong title/workpaper/review/manifest mutation 均被独立 final L1 拒绝；
5. numeric projection 与 canonical numeric Fact mutation 继续被拒绝；
6. Prompt policy、validator、fake 与 mutation rubric 共用一个 versioned owner；
7. failure telemetry 只保留 content-free digest/count/phase/segment，不把 raw text
   写入业务结果，并保留 receipts/restricted captures。

本包不扩展 generic NER、公司 alias ontology、numeric redesign、Lead dependency/
conflict atomization、叙事调优或 Provider 切换。

## Anti-loop

- replacement zero-call implementation 最多一个，且需单独授权；
- 失败则阻断受影响的 Agent delivery scope，T06 保持 blocked，不允许第二包；
- 通过后 fresh-agent proof、fresh admission 和 R4 各自仍需单独授权；
- 未来 R4 最多一次；若出现新的 L1 failure，停止并回到项目级 block，不进入 R5；
- 禁止 field-by-field prompt/regex/allowlist 补丁循环和 Provider hopping。

## 本轮边界

本轮没有修改 runtime、fixture 或业务代码；没有读取凭据、调用 DeepSeek、签发
admission、创建 WorkUnit/Attempt/Run/Artifact、执行 paired assessment、owner
acceptance 或进入 T07。

## 结果物

- 机器决策：
  `configs/releases/fin_ia_0_1_s4_t06_mu_r3_current_case_identity_token_policy_overconstraint_program_scope_replace_or_block_decision_v1_0.json`
- 合同测试：
  `tests/contract/test_fin_0_1_s4_t06_mu_r3_current_case_identity_token_policy_overconstraint_program_scope_replace_or_block_decision.py`

## 下一项

`S4-T06-MU-CURRENT-CASE-AWARE-DELIVERY-IDENTITY-BOUNDARY-SCOPE-REPLACEMENT-MINIMUM-ZERO-CALL-IMPLEMENTATION`

该项当前未授权。S4-T06 仍 blocked；MU R3 维持真实 failed，不执行 paired/owner；
T07、S5、release 与 production 继续 blocked。

## 验证与仓库边界

- 新 decision contract：`4 passed`；
- 完整当前 `tests/contract -k "s4_t06"`：`188 passed / 1771 deselected`；
- 19 个首次失败均为历史 next-action/RC 状态兼容断言；只推进其允许的当前状态
  和描述性 action 前缀，没有放宽 L1、调用、admission、Run 或 Artifact 断言；
- 37 个 S4-T06 Python test source 完成不写 `.pyc` 的内存编译；
- 349 个 release JSON 完成标准解析；新 decision 与 S4 detailed backlog 另做
  duplicate-key 严格解析；
- 24 个 Project OS JSONL、1,327 条记录完成逐行 duplicate-key 严格解析；
- decision SHA-256：
  `d15dd5af7cc9cdbff1d451f11978d92bc2f29c1ff2d3b8d0ab53a5f0df77a394`；
- policy、executor、原 safety implementation 与 R3 failure result 的 SHA 均保持
  决策前值，证明本轮未改 runtime 或历史结果；
- secret scan 与 `git diff --check` 通过，只有既有 JSONL CRLF 提示；
- 全库严格 duplicate-key 审计另发现 program backlog 当前已有两个
  `admission_issuance_authorized` 键；它们不是本轮新增，标准 JSON 解析仍通过，
  本轮未扩大到历史 backlog 清理，后续应在独立 repository-hygiene slice 处理；
- 工作树在本轮前已包含大量 mixed staged/unstaged/untracked 项，本轮不 stage、
  不 commit、不清理或覆盖这些既有改动。
