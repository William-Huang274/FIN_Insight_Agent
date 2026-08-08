# 752 — FIN 0.1.3 S1-08 official-first 组合路由与外源／内源检索接力

日期：2026-08-08

## 问题与决定

用户批准按 official-first 顺序继续，并要求把内源检索作为外源完成后的明确待办，覆盖 BM25／ObjectBM25、dense／Milvus、relationship graph，以及下游 BGE、fusion 和 rerank。审计确认两者共享同一个根因：当前 query 形状没有稳定编译为 route-specific exact／lexical／semantic／graph facets；但外源 Provider live 与内源索引／排序不能混成同一次验收。

因此保持 FIN 0.1.3 与 S1-08，不换版本、不跳阶段：先关闭 external candidate discovery；随后立即处理 internal retrieval；candidate ceiling 未通过前，BGE／rerank 为 `not_admitted`。

## 本轮完成

- 新增 `s1_08_official_first_portfolio.py`，把 60 个 relationship-aware SearchIntent 编译为 `36 official primary + 24 Firecrawl discovery shadow`，Tencent assignment=`0`；
- 12/12 required external slot 均获得 route opportunity；lane 只产生 candidate，不拥有金融日期、事实或 Evidence 晋升权；
- immutable replay 保留 Firecrawl relational target=`5/6`、Tencent=`0/6` 和 DELL supply typed route gap；
- 重放 DELL R2 capture／parser／promotion receipt：两个 role binding 共享同一 SEC 文档，统计为 `2 bindings / 1 unique canonical network document`；
- 重放 S1-03 official closeout：`11 accepted / 6 attempt-backed gaps / 9 semantic role bindings / 3 unique official documents`；
- SearchQualityCard 分开 route opportunity、locator contribution、capture/local authority、portfolio Evidence qualification、duplicate accounting、typed gaps 与 downstream utilization；
- provider date 只作 telemetry。cross-case、wrong owner/direction、future local date、shadow promotion、missing capture mutation 全部 fail closed；
- 新增机器顺序合同，登记 unified Query Facet、三路比较、external combined live、internal exact/BM25/dense/graph、qrels/candidate ceiling、BGE/fusion/rerank 和下游利用；
- PRD、TECH_02、R58 retrieval 技术文档和 FIN 0.1.3 计划已同步。

## 当前结果

- 当前实现与治理组合测试：`45 passed`；完整 S1-08 合同回归：`214 passed`；
- provider/network/model/document/Evidence=`0/0/0/0/0`；
- 当前状态：`portfolio runtime contract + combined zero-call replay engineering pass`；
- 尚未完成：clean independent proof、统一 Query Facet 实现、三路对照、fresh combined live、内源 route 接线、BGE/rerank、下游 Claim/Workpaper 利用、S1-08 关闭。

这轮没有把 Firecrawl 晋升为生产 Provider，也没有用既有 official Evidence 冒充 Firecrawl locator 已经完成 capture。DELL supply target 仍缺，因此 ranking 继续 blocked。

clean proof A1 在第一份 Git archive 内按预期 fail closed：Tencent result／assessment 和 official closeout 的 Windows CRLF 工作树字节摘要与 Git archive LF 字节不同。内容与运行逻辑没有漂移；根因是本轮新 policy 没有声明跨平台 hash profile。处置限定在同一 S1-08：输入绑定改为 `sha256_utf8_lf_normalized_v1`，不复制本机文件进入 archive、不放宽内容摘要，也不把 A1 记成通过。

clean proof A2 证明上述摘要修复有效：第一份 archive 已重物化相同 proof digest，并完成 `45 passed`；随后 proof runner 从不存在的 `proof.route_plan` 读取 route opportunity，触发 `KeyError`。真实字段在 `search_quality_card.route_opportunity`，故 A2 仍记为 proof-runner failure；本次只更正 runner 的读取路径，不改 portfolio Runtime、policy、路由或验收阈值。

## 后续顺序

1. clean archive／fresh process 复证本轮零调用实现；
2. 实现统一 Query Facet；
3. DELL／MU／NVDA 比较 raw query、本地 compiler、DeepSeek query atoms＋本地 compiler；
4. 另行签发 official routes＋Firecrawl shadow combined live；
5. 外源关闭后，立即接入内源 exact／BM25／dense／graph；
6. 扩大人工 qrels、先过 candidate ceiling，再比较 BGE／fusion／rerank；
7. 证明 selected evidence 被 Claim／Workpaper／报告实际消费。

机器合同：`configs/releases/fin_ia_0_1_3_s1_retrieval_query_facet_external_internal_progression_plan_v1_0.json`。

## 安全与回滚

历史 Provider result／assessment 和 raw capture 不改写。本轮没有网络、Provider、模型、正文抓取或 Evidence promotion。若 clean proof 失败，保留当前工作树结果为 diagnostic，不进入 Query Facet；若后续 candidate ceiling 失败，停在检索上游，不启动 reranker 调优。
