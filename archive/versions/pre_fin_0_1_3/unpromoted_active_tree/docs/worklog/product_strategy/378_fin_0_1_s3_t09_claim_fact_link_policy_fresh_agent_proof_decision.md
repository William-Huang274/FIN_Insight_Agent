# FIN 0.1 S3-T09 ClaimFactLinkPolicy fresh Agent proof 决策

日期：2026-07-24

## 目标与授权边界

用户以“继续”仅授权 `S3-T09-GENERALIZED-CLAIM-FACT-LINK-POLICY-FRESH-AGENT-PROOF-DECISION`。本轮只允许在零调用、目标只读的边界内冻结一份 future exact proof 合同；不签发或消费 admission，不调用模型、Provider、网络、来源或外部工具，不创建 canonical WorkUnit/Attempt/Run/Artifact，不执行比较、owner review、T10、S4、release 或 production。

## 决策结果

- 冻结 decision：`configs/releases/fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_agent_proof_decision_v1_0.json`。
- 冻结全新 prospective identity：
  - WorkUnit：`wu_p02_5_3462a35abeed38983ea2ebf8`
  - Attempt：`attempt_fin01_4cf8eb001b193f7311d36937`
  - ResearchRun：`research_run_fin01_0c4247687b5e4ee13c352d11`
  - exact input digest：`c0e52d02c742b8f795539e4efcc68d5d7118e78b364ec01725691dfe927fb456`
  - prospective admission：`fin01-s3-t09-three-cell-deepseek-claim-fact-link-policy-exact-admission-r1`
  - prospective admission digest：`65bcbedfa6d68f6932130aaffdddec5580abc8c4e683e0e5523e1da49b0b128d`
- future admission 必须显式绑定：
  - `fin01.s3.claim_fact_link_policy:v1`
  - output-v4
  - Specialist-v7
  - Research Lead-v5
  - Memo Writer-v3
  - research profile-v3
  - Cell-scoped identity-v1
  - restricted provider-output capture
- 预算保持 12 semantic/provider/network calls、16,800 aggregate output tokens、USD 0.10、单次 transport attempt、retry/fallback/patch/rerun=0。

## 产品与硬完整性接受门槛

未来 proof 只有同时满足以下条件才可算成功：

1. canonical terminal state 为 `succeeded`；
2. 六个逻辑节点和 12 个 Provider calls 完整到达；
3. 九类 Artifact 全部存在；
4. 三个 Claim segments 均消费显式 ClaimFactLinkPolicy binding；
5. Provider 只返回 closed `support_fact_aliases`，不得返回 `support_fact_ids` 或看到 raw Fact/source/object/routing identities；
6. 本地展开先于 scope、epistemic 和 canonical 校验；
7. `fact_supported` / `bounded_inference` 的支持非空且全部解析到同 Cell validated Facts；
8. 持久化 alias residue 和 source-ref-as-Claim-support residue 都为 0。

transport、单个 Specialist 或部分节点变绿均不构成成功。首个可信 parse/schema/ClaimFactLink/scope/epistemic/canonical/identity/length/budget/terminalization/capture failure 必须终止，禁止自动修补或重跑。

## 只读与零调用证明

- 目标 canonical prior ResearchRun count：18。
- 目标 database SHA256：`88dec30df4fe30aed9f76dc3eec1dbbef7bd0a2fd32a043c968db64c16f0cf03`。
- 目标 object tree SHA256：`23852c76f26a2749a59cdab150944fa761b4820ff2ca44baf3b39ca7b0d610db`。
- disposable-clone prepare 前后目标逻辑状态、数据库与对象树不变。
- admission issued/consumed、model/provider/network/source/tool calls、canonical execution writes、paired comparison、Human review 全部为 0。

## 验证

- `python -m py_compile scripts/releases/prepare_fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_proof.py tests/contract/test_fin_0_1_s3_t09_claim_fact_link_policy_fresh_agent_proof_decision.py`
- `python -m pytest -q tests/contract/test_fin_0_1_s3_t09_claim_fact_link_policy_fresh_agent_proof_decision.py`
- 聚焦结果：`6 passed`。
- 与上一轮 implementation、Specialist-v7 proof decision、cross-Cell scoped-identity proof decision 的相邻回归：`33 passed`（本轮聚焦 6＋相邻 27）。

## 当前边界与下一步

RC-P36-048 进入 `fresh_exact_proof_contract_frozen_admission_issuance_pending`，但尚无 live proof。RC-P36-037、S3-T09、T10、S4、release、production继续 blocked；跨 Slice manifest 尚未到期。

唯一下一项为 `S3-T09-GENERALIZED-CLAIM-FACT-LINK-POLICY-FRESH-EXACT-ADMISSION-ISSUANCE`，仍需用户单独授权。下一轮最多只能原样物化和复核本轮 frozen payload/digest；执行和模型调用必须再次独立授权。
