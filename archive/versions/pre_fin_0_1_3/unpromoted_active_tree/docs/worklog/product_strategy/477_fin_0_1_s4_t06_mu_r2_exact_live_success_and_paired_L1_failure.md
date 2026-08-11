# FIN 0.1 S4-T06 MU R2 exact-live 成功与 paired L1 失败

日期：2026-07-29<br>
状态：exact-live 技术成功；MU R2 产品验收失败；S4-T06 blocked<br>
当前下一项：`S4-T06-MU-R2-L1-NUMERIC-AUTHORITY-AND-CASE-IDENTITY-LIVE-RECURRENCE-ROOT-CAUSE-OR-SCOPE-DISPOSITION-DECISION`

## 授权与边界

用户在 R2 exact-live authority 已冻结后说“继续”。本轮授权范围为：消费一次已签发的 R2 admission、执行一次 DeepSeek Pro exact-live，并且只在 coherent success 后物化同输入的 deterministic baseline 与进行只读 paired assessment。

不授权 retry、fallback、replay、relaunch、patch、rerun、automatic R3、owner acceptance、Artifact 改写、T07 或 strict-schema transport 恢复。

## Exact-live 结果

- admission：exact-once consumed
- WorkUnit：`wu_p02_5_43322e55457b647277d2297a`
- Attempt：`attempt_fin01_217f2f2aaaa051080a540f2a`
- ResearchRun：`research_run_fin01_1920b03b8205e9861dfb5676`
- canonical states：`succeeded / succeeded / succeeded`
- logical nodes：6
- Agent Artifacts：9
- model/provider/network calls：`12 / 12 / 12`
- usage receipts / restricted captures / readbacks：`12 / 12 / 12`
- Provider statuses：全部 `ok`
- finish reasons：全部 `stop`
- machine Verifier：`accept_for_internal_review`
- tokens：`69,484 input / 7,734 output / 77,218 total`
- estimated cost：`USD 0.0303834`
- retry/fallback/replay/relaunch/rerun：`0 / 0 / 0 / 0 / 0`

Lead-v7 Research Lead 完整通过，未再发生 `fact_presence_summary` 错配。RC-P36-078 获得真实全链正证据并关闭。

## Success-only baseline

同一 MU Case/version、DecisionSurface 和 input-head 上，先做两次 prospective prepare，结果逐字段一致；随后 exact-once 物化 source-grounded deterministic baseline：

- WorkUnit/Attempt/Run：新建且与 Agent Run 不同；
- terminal states：`succeeded / succeeded / succeeded`；
- Artifacts：4；
- model/provider/network/source/tool：`0 / 0 / 0 / 0 / 0`；
- Agent Run 与 9 个 Artifacts：未改写；
- baseline body：未暴露给 Agent；
- read-only verification：pass。

baseline 是非推理真实性下限，不作为 Agent 替代品。

## Paired L1–L4 结果

机器 Verifier 虽然给出绿灯，独立 L1 仍发现两个 critical findings。

第一，5 组 Agent material numeric statements 与其绑定 MU Numeric authority 不一致，典型包括：

- Agent `revenue $8,709M / GAAP GM 26.1% / op income $1,534M`，authority 为 `41,456M / 84.6% / 33,318M`；
- Agent `DRAM $5,344M / 61% / GM 30.2%`，authority 为 DRAM 约 `31,300M / 76%`，且所引 gross-margin ref 实际是 CMBU `83%`；
- Agent `inventory 8,663M / 160 days / capex 3,138M / adjusted FCF -1,149M`，authority 为 `8,567M / 120 days / 7,084M / +18,304M`。

第二，MU report title 是 `NVDA 三单元内部研究备忘录`。该字段由本地 Writer assembler 拥有，不是模型字段。

四层结论：

- L1：fail；
- L2：pass；仅有一个 `variant_view` 超过 320 字符目标但低于 512 ceiling 的非终态质量 finding；
- L3：Agent 相对 baseline 有 6 条 specialist claims、8 个 WWC tasks、3 条 dependency、3 条 conflict adjudication、4 个 selected gaps 的明显行动增益，但 L1 失败时不可采纳；
- L4：因错误公司标题、数字复核负担和摘要过密而 fail。

## 官方来源复核

Micron 官方 Q3 FY2026 results release 与 prepared remarks 确认 source pack 的核心 authority：revenue `41,456M`、GAAP gross margin `84.6%`、GAAP operating income `33,318M`、DRAM revenue 约 `31.3B` 且占 `76%`、capex 约 `7.1B`、adjusted free cash flow 约 `18.3B`、inventory 约 `8.6B / 120 days`。

因此不新增 source-pack issue。既有 RC-P36-067 以 shared numeric rendering/correspondence live recurrence 重新打开；RC-P36-068 以 local case identity live recurrence 重新打开。

官方来源：

- https://investors.micron.com/news-releases/news-release-details/micron-technology-inc-reports-record-results-third-quarter
- https://investors.micron.com/static-files/631b1a32-5537-46ae-8f40-82e42fc79dfe

## 结果物

- exact-live success：`configs/releases/fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_materialization_r2_exact_live_execution_success_result_v1_0.json`
- deterministic baseline：`configs/releases/fin_ia_0_1_s4_t06_mu_r2_source_grounded_deterministic_baseline_materialization_v1_0.json`
- paired assessment：`configs/releases/fin_ia_0_1_s4_t06_mu_r2_success_only_paired_assessment_result_v1_0.json`
- model run ledger：`reports/model_runs/20260729_fin_ia_0_1_s4_t06_mu_deepseek_pro_r2_exact_live_success_paired_L1_failure_r1.md`

## 决策

MU R2 不接受，owner acceptance 不具备资格，T07 不进入。Agent 与 baseline Artifacts 保持不可变。下一步只做零调用 root-cause/scope disposition，统一处理完整 delivery surfaces 的数值 material ownership、Verifier exact correspondence 与 Writer case identity；不得再逐字段补丁或自动启动 R3。

## 收尾验证

- 新结果与历史 authority focused tests：`9 passed`
- 完整 S4-T06：`170 passed`
- 下一零调用 disposition 的 Project OS preflight：`pass / open blockers 0`
- preflight：`.codex_runtime/s4_t06_mu_r2_l1_numeric_identity_disposition_project_os_preflight.json`
- preflight SHA256：`e1021694b1228afe5c98529313fbd73216a77e45f2240ccdd2b32d67e92143f5`
