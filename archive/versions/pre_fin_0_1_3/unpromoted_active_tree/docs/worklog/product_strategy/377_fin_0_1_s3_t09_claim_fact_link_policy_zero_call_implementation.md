# FIN 0.1 S3-T09 ClaimFactLinkPolicy 零调用实现

日期：2026-07-24
状态：`pass_zero_call / runtime_injected / node_level_consumed / fixture_proven / fresh_proof_decision_pending`

## 本轮目标

按已通过的 final hard-failure disposition，实现共享 `fin01.s3.claim_fact_link_policy:v1`，修复 Provider 在 Claim Card 中把底层 Numeric refs 当作 local Fact IDs 的身份层错误。授权只覆盖 runtime policy、deterministic/fake-provider tests 和 Project OS 同步；不覆盖 admission、真实调用、重跑、比较或 T10。

## 最早 owner 与实现

- `apps/workbench/backend/application/bounded_agent_contract_policies.py`
  - 新增 `ClaimFactLinkPolicy` 和 `ClaimFactAlias`。
  - 从当前 Cell 已验证 Fact 集合按 exact `fact_id` 排序，生成 request-local `F001/F002/...`。
  - Provider 只接收 alias、Fact statement、support type、boundary 和本地 scope summary。
  - Claim-selection model view 与 prior Fact surface 移除 source/object/routing identity；不把 request alias 当权威身份持久化。
  - 只允许 exact alias membership，本地展开回原 validated Fact IDs；禁止 trim、normalize、prefix guess、fuzzy match 和 silent rewrite。
- `apps/workbench/backend/application/bounded_agent_executor.py`
  - `S3ThreeCellBoundedAgentAdmission.claim_fact_link_policy_ref` 作为独立显式 capability binding；旧 admission 未设置字段时 digest 与行为不变。
  - Claim segment schema 使用 `support_fact_aliases`，Provider `support_fact_ids` 在策略启用时 fail-closed。
  - exact expansion 发生在 local scope assembly、epistemic-state 和 canonical owner-grade validation 之前。
  - 新增 closed `s3_owner_grade_claim_fact_link_invalid` telemetry，只保存 contract/subtype/count 和 content-persistence flags。
  - 没有新增 Specialist-v8，也没有修改 transport v7 capability。

## 验证

- 新增 `tests/contract/test_fin_0_1_s3_t09_claim_fact_link_policy_zero_call_implementation.py`。
- 聚焦测试：`17 passed`。
- 相邻 Specialist-v7、Lead-v5、profile-v3、cross-Cell identity、Specialist-v6：`56 passed`。
- 合计：`73 passed`。
- 覆盖 AMD、`FY2027-Q1-53W`、mixed Evidence/Numeric authority、三个 Cell 各自复用 `F001`、raw/unknown/duplicate/blank/non-array/empty-required/wrong-Cell、Provider 原始 `support_fact_ids`、旧 admission digest 与旧 request shape。
- 完整 fake-provider 路径：六逻辑节点、12 fake calls、九 Artifact families；Writer、Verifier、Artifact 中 request alias residue=`0`。
- typed negative 路径在第二次 fake call 停止，telemetry 不含 raw alias、Fact ID、source ref、Cell ID、item index 或 private reasoning。

## 本轮未执行

- model/provider/network/source/external tool calls：`0`
- 新 admission / admission consumption：`0 / 0`
- 新 live WorkUnit / Attempt / ResearchRun / Artifact：`0 / 0 / 0 / 0`
- paired comparison / Human Review / owner acceptance：`0 / 0 / 0`

## 当前边界与下一步

RC-P36-048 已从 `contract_translated` 推进为 `runtime_injected / node_level_consumed / fixture_proven`，但没有 live proof。S3-T09、T10、S4、release、production 继续 blocked；cross-slice manifest 仍未到期。

下一项仅为需独立零调用授权的：

`S3-T09-GENERALIZED-CLAIM-FACT-LINK-POLICY-FRESH-AGENT-PROOF-DECISION`

该决策只能冻结 fresh identity、exact input、policy/profile/transport binding、budget、nonreuse、capture、first-failure-stop 和完整产品成功门槛；不能签发或消费 admission，不能调用模型、重跑、比较、review 或进入 T10。
