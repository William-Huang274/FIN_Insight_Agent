# FIN 0.1.3 S1-08：Firecrawl 关系感知 semantic control 终态与国内 Provider 接力

日期：2026-08-08

## 终态

唯一 admission=`fin-ia-013-s1-08-firecrawl-semantic-control-r1-20260808` 已 exact-once 消费：

- planned/terminal/success=`24/24/24`；
- provider/network=`24/24`；
- retry/model/document/Evidence=`0/0/0/0`；
- raw locators=`235`，跨案去重 URL=`176`；
- credits=`48`，未使用 API Key 或支付工具，观测现金支出=`0 USD`，但 credits 不被解释成零经济成本；
- p50/p95/max/whole=`4006/6877/9140/108539 ms`；
- result digest=`8b92ad90ee02f901acdd732dea1e6a862262fe115b26dbfa8d66f8c16d523a35`；
- result file SHA256=`84fbafa1b67c7c0b0d620086a3e94f1e4f9f36e439e7d2b4495aee47a3cc46f7`。
- 24 safe request、24 raw response、24 call terminal 共 72 个 capture ref 全部存在且 SHA 重算一致；24/24 请求明确未发送 Authorization/Cookie，aggregate terminal 存在。

## 研究质量结果

- topical useful@10=`133/240`；
- 六个 customer/supply case-slot exact target-in-pool=`5/6`；
- 命中 source identity 为 Microsoft Q3 FY2026 call（三次消费）、Dell Q1 FY2027 call（一次）、TSMC Q2 2026 results（两次）；
- 唯一未覆盖为 DELL supply 的 `SRC_MU_Q3_FY26_REMARKS`；英文结果出现 Micron 官方 Q3 results press-release locator，但没有命中 prepared-remarks exact URL，且本 authority 不允许额外 fetch/canonical/redirect 核验，故不能擅自判为 typed equivalent；
- provider date presence=`0/235`；六次 exact-target occurrence 都没有 date，matched-target date accuracy 按合同 fail closed=`0`；
- DELL/MU/NVDA unique registrable domains=`53/51/53`，单一生态最大占比均低于 8%，diversity 通过；
- 四条 query 的 topical useful@10 低于 0.3；中文 DELL/MU case mean=`0.375/0.300`，低于 0.5；中文 exact target=`0`；
- p95 6.877 秒超过 5 秒硬门。

最终状态=`fail_diagnostic_only / remain_diagnostic_only_no_reranker_rescue`。assessment SHA256=`1ba0d2a65ad7e1c72bd6c00d5c19a2f3f93649a4395e75a4cc33572ca4ea2a7c`。

## 如何解释 0/6 → 5/6

旧 A4 是每个 case-slot 一条英文通用 query，共 6 次；本轮是按 evidence owner fan-out 的中英 24 次。因此不能把差异写成只改一个词造成的严格 A/B，也不能把四倍预算隐藏掉。但目标进入 5/6 case-slot、且命中恰好来自 MSFT/DELL/TSMC 这些被新 compiler 显式投影的 evidence owner，是查询结构修复有效的强实证。项目自有 query compiler 可以记 `live-supported engineering pass`，Firecrawl Provider 则仍因目标缺口、日期、中文和延迟不合格。

## 下一步边界

不执行 Firecrawl R2，不逐 query 修补，不用 reranker 拯救上游 miss，也不自动运行 22 precise unit。下一步等待一份 fresh、未暴露、可安全注入的国内 raw-search Provider credential；只做 `S1_08_DOMESTIC_PROVIDER_FRESH_CREDENTIAL_READINESS_AND_SAME_MATRIX_COMPARATOR_AUTHORITY_DECISION`，复用完全相同的 24-query plan 和 evaluator。国内 Provider 结果出来前，S1-08、SourceHunter、ranking、S3 和 release 继续 blocked。
