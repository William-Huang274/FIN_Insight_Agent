# FIN 0.1 S4-T06 MU R1 Research Lead 语义失败

日期：2026-07-29<br>
状态：exact-live 已终态失败；success-only paired 未执行<br>
当前下一项：`S4-T06-MU-RESEARCH-LEAD-FACT-PRESENCE-SUMMARY-MISMATCH-FIRST-CREDIBLE-FAILURE-ROOT-CAUSE-OR-SCOPE-DISPOSITION-DECISION`

## 本轮目标与权限

用户授权持续执行至本轮 exact-live 结束。唯一执行目标由以下 authority 冻结：

- authority：`configs/releases/fin_ia_0_1_s4_t06_mu_fresh_exact_live_execution_and_success_only_paired_assessment_authority_decision_v1_0.json`
- authority SHA256：`0336d17833969fb8a1374f2d0f9b1bb73d99d819612b08f6e7738c0ec993f618`
- admission：`fin01-s4-t06-mu-fresh-exact-admission-r1`
- provider/model：`deepseek / deepseek-v4-pro`
- endpoint：`https://api.deepseek.com/beta`
- exact-live ceiling：12 model/provider/network calls、16,800 output tokens、USD 0.10
- stop contract：首个可信失败立即停止；失败后不得 paired、retry、fallback、replay、relaunch、patch 或 rerun

## 执行结果

supervision-v2 正常启动并自行终态化：

- WorkUnit：`wu_p02_5_fbe7fa234fce9f4c54403c56`
- Attempt：`attempt_fin01_e4473dd705631f215159fe76`
- ResearchRun：`research_run_fin01_c94013e1c3666739c35ff00c`
- canonical states：`failed / failed / failed`
- orphan：`false`
- business Artifacts：`0`
- admission：已消费

三名 Specialist 的 9 个 segment 全部返回 `status=ok / finish_reason=stop`。Research Lead 的第 10 次调用也返回 `status=ok / finish_reason=stop`，但本地 `closed_research_lead_output:v3` 语义校验失败：

`s3_bounded_research_lead_v3_semantic_fact_presence_summary_mismatch`

失败字段为 `conflict_adjudications.fact_presence_summary`。模型返回的是允许枚举之一，但与 involved Claim Cards 的 `support_fact_ids` 可确定性推导出的 `all/none/some` 摘要不一致。Writer 与 Verifier 因此没有调用。

## 调用与成本会计

- model/provider/network calls：`10 / 10 / 10`
- transport attempts/failures：`10 / 0`
- usage receipts/restricted captures/readbacks：`10 / 10 / 10`
- input tokens：`51,164`
- output tokens：`6,882`
- total tokens：`58,046`
- input cache hit/miss：`2,816 / 48,348`
- cost：`USD 0.02702893`
- receipt latency sum：`93,426 ms`
- retry/fallback/replay/relaunch/rerun：全部 `0`
- source/tool/live Case-head writes：全部 `0`

原始 Provider HTTP、private reasoning 和 credential 未持久化。

## 根因边界

这不是 credential、网络、HTTP、JSON parse、截断、token ceiling 或成本 ceiling 问题。DeepSeek 在该字段确实发生一次语义不一致；但项目不能只归咎模型：

- `fact_presence_summary` 可以从已绑定 Claim Cards 的 `support_fact_ids` 本地确定性派生；
- 历史 `RC-P36-041` 已明确识别这一点；
- 当前 runtime 仍要求 Provider 生成该字段，再用本地逻辑校验；
- 因而本轮还暴露了结构 ownership 漂移：确定性事实被不必要地交给概率模型。

已登记 `RC-P36-078-s4-t06-mu-research-lead-deterministic-fact-presence-summary-model-ownership-recurrence`。下一轮只能做零调用 root-cause 或 scope disposition，不能自动生成 R2。

## 门禁与后续

success-only 门禁未满足，以下动作故意未执行：

- paired baseline；
- paired assessment；
- owner acceptance；
- T07；
- strict-schema transport 恢复；
- 第二次 MU exact-live。

下一步应决定是把 `fact_presence_summary` 改为本地确定性组装，还是把该问题判定为当前 T06 范围阻断并关闭/替换范围。不得继续逐字段 prompt 补丁或原地重跑。

## 证据

- failure result：`configs/releases/fin_ia_0_1_s4_t06_mu_fresh_exact_live_execution_failure_result_v1_0.json`
- failure result SHA256：`ac048a27964330f776e0452f0fe7fff3d064805b5e6fadccb695d2460ee5a930`
- runtime result：`.codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/s4_t06_mu_fresh_exact_r1_live_execution_result.json`
- runtime result SHA256：`66514372b85cd3b8f2abbb1e1df33254d700ae9c86a62558288ec057675b4fa7`
- terminal inspection SHA256：`45c53b09de9964b97a540657842ec76d71653994476f05f2ae4f416481982dbe`
- focused/current：`16 passed`
- S4-T06：`131 passed`
