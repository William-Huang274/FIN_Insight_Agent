# FIN 0.1 S3-T09 ClaimFactLinkPolicy fresh exact-live 失败收口

日期：2026-07-24

## 授权与执行

用户以“继续”独立授权 `S3-T09-GENERALIZED-CLAIM-FACT-LINK-POLICY-FRESH-EXACT-LIVE-EXECUTION`。本轮只允许 exact-once 消费 admission `65bcbedf...b128d`；禁止 retry、fallback、patch、rerun、comparison、Human Review、T10、S4、release 和 production。

Scoped Project OS guard 与 exact runner preflight 均通过。进程级 `LLM_GATEWAY_TRANSPORT_RETRIES=0`；fresh WorkUnit/Attempt/ResearchRun 和 exact input 一致，执行前目标 counts=`18/18/18/13`。

## 结果

- Canonical：`failed / failed / failed`，orphan=false，Artifact=0。
- Calls：model/provider/network=`12/12/12`。
- Tokens：input/output/total=`53,834/5,742/59,576`。
- Estimated cost：USD `0.02764032`。
- Retry/fallback/rerun=`0/0/0`。
- Restricted capture/readback=`12/12`。
- Source network/external tool/live Case head write=`0/0/0`。

## ClaimFactLinkPolicy live 进展

三个 Claim segments 全部完成；五个 Claim 中两个 `fact_supported` Claim 分别选择 `F001/F002`，三个 `cannot_infer` Claim 使用空 alias 列表。Provider 未返回任何 `support_fact_ids`。本地 exact expansion 和 same-Cell validation 通过后链路继续到 Lead、Writer、Verifier；下游三份回答无 Fact alias 或 Claim-support 字段残留。RC-P36-048 的具体修复获得 live positive evidence，但最终零 Artifact，因此不能宣称完整产品或 Artifact residue gate 通过。

## 新根因

Verifier 返回合法 JSON，四个 finding 使用旧版 `layer/status/issues`。受限结构审计与纯本地 request 复现确认：

- output-v4 request builder 只有 output-v3 条件会下发 typed finding schema；
- output-v4 实际下发旧三字段 schema；
- output-v4 validator 要求 `layer/status/issue_codes/artifact_or_claim_refs/repair_owner`；
- DeepSeek 遵循了被下发的旧 schema，本地 validator 正确 fail-closed；
- fake-provider 九 Artifact 测试直接生成预制 typed finding，没有从 `required_output_schema` 派生，形成 fixture blind spot。

新增 RC-P36-049：`output_v4_verifier_prompt_validator_schema_drift`。本轮没有修复代码或第二次执行。

## 证据

- Tracked result：`configs/releases/fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_live_execution_result_v1_0.json`
- Model run：`reports/model_runs/20260724_fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_live_validation_r1.md`
- Restricted runtime result SHA256：`240b3bacb724991735690ace10858cb404b5250b21a6d693907a855078eee67a`
- Post-run counts=`19/19/19/13`
- Post-run DB SHA256=`86c623db5cfaa02a8e462a925134135c2f91518d2d44e4b2eb32cf988092098a`
- Post-run object tree SHA256=`0f081e219fbb32f0a5b493473c8d3078c6c0960d873bf98540744320a00b1541`
- ClaimFactLinkPolicy live result、issuance、proof decision 与 zero-call implementation 合同回归：`33 passed`。

## 下一步

唯一下一项为 `S3-T09-OUTPUT-V4-VERIFIER-PROMPT-VALIDATOR-SCHEMA-DRIFT-ZERO-CALL-ROOT-CAUSE-DECISION`，需独立授权。不得自动 patch、签发 replacement admission、调用、重跑、比较、owner review 或进入 T10/S4/release/production。
