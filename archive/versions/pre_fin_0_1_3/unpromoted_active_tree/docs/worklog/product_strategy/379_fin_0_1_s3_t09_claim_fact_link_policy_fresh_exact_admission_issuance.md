# FIN 0.1 S3-T09 ClaimFactLinkPolicy fresh exact admission 签发

日期：2026-07-24

## 目标与授权边界

用户以“继续”仅授权 `S3-T09-GENERALIZED-CLAIM-FACT-LINK-POLICY-FRESH-EXACT-ADMISSION-ISSUANCE`。本轮只允许将上一轮 proof decision 的 frozen prospective payload 原样物化为 admission，并执行 schema、digest、factory、runner-load、fresh identity 和目标只读完整性复核；不允许消费 admission、调用模型/Provider/网络/来源/外部工具、创建 canonical execution state、重跑、比较、owner review、T10、S4、release 或 production。

## 签发结果

- Admission：`configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_claim_fact_link_policy_exact_admission_r1.json`
- Issuance result：`configs/releases/fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_admission_issuance_v1_0.json`
- Admission ID：`fin01-s3-t09-three-cell-deepseek-claim-fact-link-policy-exact-admission-r1`
- Admission digest：`65bcbedfa6d68f6932130aaffdddec5580abc8c4e683e0e5523e1da49b0b128d`
- Frozen WorkUnit/Attempt/ResearchRun：
  - `wu_p02_5_3462a35abeed38983ea2ebf8`
  - `attempt_fin01_4cf8eb001b193f7311d36937`
  - `research_run_fin01_0c4247687b5e4ee13c352d11`

物化后的 payload 与 proof decision 的 `prospective_admission.payload` 逐字段相等，canonical digest 不变。admission 显式绑定 `fin01.s3.claim_fact_link_policy:v1`、output-v4、Specialist-v7、Lead-v5、Writer-v3、profile-v3、scoped identity v1 和 restricted final-answer capture。

## 零调用与只读复核

- schema/profile/factory 构造通过，Provider callback 调用数为 0。
- live runner 可加载 issuance/admission，并绑定预测 ResearchRun。
- prospective WorkUnit/Attempt/Run 仍全部 absent。
- target counts 保持 `18/18/18/13`。
- canonical database SHA256 保持 `88dec30df4fe30aed9f76dc3eec1dbbef7bd0a2fd32a043c968db64c16f0cf03`。
- object tree SHA256 保持 `23852c76f26a2749a59cdab150944fa761b4820ff2ca44baf3b39ca7b0d610db`。
- credential 仅确认存在，明文未读取、输出或持久化。
- `LLM_GATEWAY_TRANSPORT_RETRIES` 当前未等于 `0`，因此 future exact-live 仍有显式执行前置条件。
- observed：new admission=1；consumption、WorkUnit、Attempt、Run、Artifact、model/provider/network/source/tool calls 全部为 0。

## 验证

- `python -m py_compile scripts/releases/issue_fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_admission.py tests/contract/test_fin_0_1_s3_t09_claim_fact_link_policy_fresh_exact_admission_issuance.py`
- `python -m pytest -q tests/contract/test_fin_0_1_s3_t09_claim_fact_link_policy_fresh_exact_admission_issuance.py`
- `python -m pytest -q tests/contract/test_fin_0_1_s3_t09_claim_fact_link_policy_fresh_exact_admission_issuance.py tests/contract/test_fin_0_1_s3_t09_claim_fact_link_policy_fresh_agent_proof_decision.py tests/contract/test_fin_0_1_s3_t09_claim_fact_link_policy_zero_call_implementation.py`
- 聚焦结果：`5 passed`；相邻 proof-decision 与 implementation 回归：`23 passed`；合计：`28 passed`。

## 当前边界与下一步

Admission 状态为 issued/unconsumed；签发不代表 live integrity proof。RC-P36-048 进入 `fresh_exact_admission_issued_unconsumed_live_execution_pending`，RC-P36-037、S3-T09、T10、S4、release、production继续 blocked。

唯一下一项为 `S3-T09-GENERALIZED-CLAIM-FACT-LINK-POLICY-FRESH-EXACT-LIVE-EXECUTION`，仍需用户独立授权。未来执行必须先令 process-local retry=0，经 Project OS 和 runner preflight 后 exact-once 消费；首个可信硬失败立即停止，禁止 retry/fallback/patch/rerun。
