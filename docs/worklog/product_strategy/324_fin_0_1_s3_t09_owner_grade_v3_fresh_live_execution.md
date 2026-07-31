# FIN 0.1 S3-T09：owner-grade output-v3 fresh live execution

日期：2026-07-22

## 结论

用户以“授权”只允许 `S3-T09-OWNER-GRADE-V3-FRESH-EXACT-LIVE-EXECUTION`。Project OS 和 exact zero-call preflight 均通过后，已签发 admission 被唯一消费；Run 在第一位 Demand Specialist 以 typed schema failure 终止。WorkUnit、Attempt、ResearchRun 三态均 failed，0 Artifact、7 events、无 orphan。没有 retry、fallback、rerun、paired comparison、Human Review、T10、S4、release 或 production 行为。

这说明 exact execution、首错停止和 canonical terminalization 正常，但不能证明 output-v3 owner-grade 修复在真实 Provider 输出上成立。RC-P36-037 继续 blocked，并新增 RC-P36-039 记录第一 Specialist schema 与安全 subtype 可观测性缺口。

## 执行安全修复

执行前发现 runner 把所有新结果固定写入既有 `live_execution_result.json`，会覆盖 output-v2 历史证据。零调用修复为可选、受限的 `--output-prefix`，使 preflight/result/inspection 各写独立文件；默认行为保持不变。fixture 证明带 prefix 时历史文件内容不变。本次执行后旧 output-v2 result SHA256 仍为 `8210b6ae...f474`。

## Live 结果

- Admission：`fin01-s3-t09-three-cell-deepseek-owner-grade-v3-exact-admission-r1`。
- Run：`research_run_fin01_b939a453b921cb5bcf3c2edf`。
- Provider/model：DeepSeek / `deepseek-v4-pro`。
- Calls：model/provider/network=`1/1/1`。
- Tokens：input 2,916、output 1,316、total 4,232。
- Estimated cost：USD 0.00241338。
- Provider：`finish_reason=stop`、transport attempt=1、latency=17.305s。
- Terminal：WorkUnit/Attempt/Run=`failed/failed/failed`，Artifact=0，events=7，orphan=false。
- Failure：`s3_bounded_specialist_output_schema_invalid:demand_authenticity_and_sustainability`。

`_parse_native_json_object` 已通过，随后 `_validate_specialist_output` 在精确顶层 keys 或 `program_cell_id` 检查处失败。因此可排除 HTTP、JSON decode、length 和 canonical closeout；但安全持久化没有 raw output，且当前 typed code 合并了 missing/extra/cell-id 三类，不能事后臆测具体一类。

终态后对同一 issuance 再做一次零调用 preflight，按预期以 `s3_t09_exact_execution_identity_already_consumed` 在 Provider 前拒绝；gateway event 行数保持 `16→16`，证明该 identity 不可复用。

## 产品与研究质量边界

本轮没有生成任何 v3 Artifact，所以不能做 paired comparison，也不能检查 Claim Card、WWC、Lead、Writer 或 Verifier 的 live 语义表现。没有新 Evidence、来源、指标或 Alpha。Provider 的 `json_object` 路线只保证 JSON 语法，不等于 server-side exact schema；严格性仍由本地 validator 正确 fail-closed。

当前唯一下一项是 `S3-T09-OWNER-GRADE-V3-FIRST-SPECIALIST-SCHEMA-FAILURE-ROOT-CAUSE-AND-TRANSPORT-DECISION`。它必须另行授权且保持零调用，只决定安全 shape telemetry、Provider structured-output transport 与 schema conveyance 的方案；不得复用已消费 admission、自动修复后重跑、放宽 v3 validator、比较 baseline 或进入 T10。
