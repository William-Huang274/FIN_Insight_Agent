# FIN 0.1 S4-T06 MU RC-P36-078 R2 exact-live authority

日期：2026-07-29<br>
状态：R2 exact-live 已授权、admission 未消费、execution 未开始<br>
当前下一项：`S4-T06-MU-RESEARCH-LEAD-CONFLICT-FACT-PRESENCE-LOCAL-MATERIALIZATION-R2-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT`

## 范围

用户在 R2 admission 已签发且 durable next 明确为 authority decision 时说“继续”。本轮只允许完成零调用执行资格判断和 authority artifact，不允许消费 admission、启动 supervisor、调用 DeepSeek、生成 Artifact、执行 paired assessment 或进入 T07/strict-schema。

## 零调用资格

- Project OS scope：`pass / open blockers 0`
- runner preflight：`pass_exact_zero_call_execution_preflight`
- credential：presence=true，值未读取、输出或持久化
- provider health probe：false
- transport retries：0
- model/provider/network/source/tool：`0/0/0/0/0`
- R2 supervision root/result：absent
- R2 WorkUnit/Attempt/Run：逐 ID absent
- R1 failed Run：存在且 state=`failed`

runner 显示的 same-Case counts `1/1/1/0` 是历史 R1，不代表 R2 已创建；preflight 前后完全相同。

## 冻结 authority

- artifact：`configs/releases/fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_materialization_r2_exact_live_execution_and_success_only_paired_assessment_authority_decision_v1_0.json`
- SHA256：`d8264d529754b3c1d283d53981b2d5f92a3771b453f92f06138802abeaded480`
- Project OS preflight：`.codex_runtime/s4_t06_mu_fact_presence_local_materialization_R2_exact_live_authority_project_os_preflight.json`
- runner preflight：`.codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/s4_t06_mu_fact_presence_local_materialization_r2_live_execution_preflight.json`
- supervision root：`.codex_runtime/fin01-s4-t06-mu-fact-presence-local-materialization-r2-supervision-r1`
- output prefix：`s4_t06_mu_fact_presence_local_materialization_r2`

执行预算为 `12 semantic / 12 provider / 12 network calls / 16800 output tokens / USD 0.10`，每次调用最多一个 transport attempt。Lead-v7、local fact-presence materialization、Specialist-v7、MU exact input、supervision-v2 与 7 个 execution code hashes 全部冻结。

## 成功与停止

只有以下条件全部成立，才可执行 same-input-head 只读 paired assessment：

- WorkUnit/Attempt/Run coherent succeeded；
- 6 logical nodes；
- 12 Provider calls、12 usage receipts、12 restricted captures；
- typed Verifier success；
- 9 Artifacts；
- L1 hard integrity pass；
- MU HBM 证据边界、case-local identity 和 Graph context-only 不降级。

首个可信失败立即 terminal fail-closed，保留可用 receipts/captures 后停止。失败不得 paired，不允许 retry、fallback、replay、relaunch、patch、rerun、第二次 execution 或 automatic R3。

## 验证

- authority focused：`5 passed`
- fresh proof + issuance + authority current chain：`16 passed`
- 完整 S4-T06：`166 passed`
- JSON/JSONL、hash、compile：`pass`
- secret scan、Git diff：待最终收尾
- model/provider/network：`0/0/0`

没有创建 model-run ledger，因为本轮没有 inference 或 Provider 请求。

完整回归首次出现 17 个历史 next-action compatibility 失败；它们只把 authority decision 注册为 DeepSeek 主线最远合法后继。更新仅把已授权 R2 exact execution 登记为合法后继，并让 fresh-proof/issuance 历史测试识别后续 authority artifact；没有修改 schema、validator、L1 gate、Provider request 或 runner 行为。重跑后 `166 passed`。
