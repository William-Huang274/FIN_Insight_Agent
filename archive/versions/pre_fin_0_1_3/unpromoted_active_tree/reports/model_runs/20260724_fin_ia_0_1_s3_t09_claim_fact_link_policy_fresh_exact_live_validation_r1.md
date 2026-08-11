# FIN 0.1 S3-T09 ClaimFactLinkPolicy fresh exact-live validation

时间：2026-07-24 10:50–10:51（Asia/Shanghai）

## 结论

唯一获授权的 ClaimFactLinkPolicy exact-live 已 exact-once 消费并可信终止，但没有通过 S3-T09。三组 Specialist Claim segment 均消费 closed Fact alias 合同并完成，Research Lead、Memo Writer、Verifier 均被调用；原 RC-P36-048 的 Claim→Fact 错误未复现。最终失败发生在 Verifier：output-v4 Provider request 错误声明旧版三字段 finding schema，而本地 output-v4 validator 正确要求五字段 typed finding schema。

三态为 `failed / failed / failed`，orphan=false，Artifact=0。真实 model/provider/network calls=`12/12/12`，tokens=`53,834/5,742/59,576`，estimated cost=USD `0.02764032`，retry/fallback/rerun=`0/0/0`。12 份 assistant final text 与 receipts 均受限持久化并 `12/12` 回读；source network、external tool、live Case head write 均为 0。

## Code And Command

- Entry point：`scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py`
- Admission：`configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_claim_fact_link_policy_exact_admission_r1.json`
- Issuance：`configs/releases/fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_admission_issuance_v1_0.json`
- Admission digest：`65bcbedfa6d68f6932130aaffdddec5580abc8c4e683e0e5523e1da49b0b128d`
- Git：`codex/layered-data-source-expansion@54d2e072b30d`，历史暂存批次，执行前 483 staged、0 unstaged/untracked。
- Process-local：`LLM_GATEWAY_TRANSPORT_RETRIES=0`
- Scoped Project OS guard：pass，无 override。
- Exact runner preflight：pass；身份新鲜，目标 counts=`18/18/18/13`，credential 只确认存在，未输出或持久化。

## ClaimFactLinkPolicy live 观察

- 三个 Claim segment 全部完成，共五个 Claim。
- 两个 `fact_supported` Claim 分别选择 `F001`、`F002`；三个 `cannot_infer` Claim 按合同选择空列表。
- Provider 输出含五个 `support_fact_aliases` 字段、零个 `support_fact_ids` 字段。
- 本地 exact expansion、same-Cell Fact 和后续 owner-grade validation 均通过，否则链路不会继续到 Lead、Writer、Verifier。
- Lead、Writer、Verifier 的受限回答中 `Fxxx` token、`support_fact_aliases` 与 `support_fact_ids` 均为 0。
- 因最终零 Artifact，不能把 canonical Artifact residue 门槛宣称为完整产品通过；只确认 RC-P36-048 的 live repair path 已被观察到。

## 新硬失败与最早 owner

Verifier 返回 valid native JSON、四个正确 layer、两个 64 字符 digest binding 和 `accept_for_internal_review`，但每条 finding 精确包含：

`layer / status / issues`

这与 Provider request 的 `required_output_schema` 完全一致。项目的 output-v4 validator 则要求：

`layer / status / issue_codes / artifact_or_claim_refs / repair_owner`

最早错误在 `DeepSeekS3ThreeCellNodeExecutor._node_request`：typed Verifier schema 只在 output-v3 分支下发；validator 却对 output-v3 和 output-v4 都要求 typed schema。fake-provider 全链测试直接生成预制 typed-v4 Verifier 对象，没有从 request schema 派生 finding shape，因此未发现 prompt/validator drift。新增 RC-P36-049；这不是 Provider 不遵循 schema，也不是 ClaimFactLinkPolicy recurrence。

## Experiment Governance

- Hypothesis：closed Fact aliases 能消除 Claim support 选择错误身份层。
- Decision target：三 Claim segments 通过、same-Cell local expansion 通过，且完整链 terminal succeeded / 12 calls / 9 Artifacts / zero residue。
- Result：Claim-link hypothesis 获 live positive evidence；完整产品目标因 Verifier 项目内 schema drift 未满足。
- Stop condition：首个可信硬失败停止。
- Decision：`blocked_root_cause_repair_required`；不做 patch、retry、fallback、rerun、comparison 或 owner review。
- Closure regression：live result、issuance、proof decision 与 zero-call implementation 四组合同测试合计 `33 passed`。

## 下一步

唯一下一项为 `S3-T09-OUTPUT-V4-VERIFIER-PROMPT-VALIDATOR-SCHEMA-DRIFT-ZERO-CALL-ROOT-CAUSE-DECISION`，需独立授权。S3-T09、T10、S4、release、production继续 blocked。
