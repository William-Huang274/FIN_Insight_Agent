# 713 — FIN 0.1.3 S1-08 成熟组件、关系方向与预算 v3 零调用实现

日期：2026-08-08
阶段：`013-S1-08`
状态：`zero-call engineering pass / independent clean proof pending / no live authority`

## 1. 本轮做了什么

本轮按 712 已冻结的顺序继续，没有重新跑 DELL live，也没有调用 DeepSeek、ranking 或外部搜索。工作分成一条统一链：先用 DELL R2 immutable capture 比较现有解析器与成熟组件，再把胜出的窄能力接回现有 capture-first Runtime，随后用三案例 full-fake 和 mutation 证明日期、关系方向、预算与唯一来源分账。

实现与机器证明：

- v3 catalog：`configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_relationship_budget_policy_v3_0.json`；
- 成熟组件适配：`src/sec_agent/s1_08_official_content_tools.py`；
- scheduler/candidate：`src/sec_agent/s1_08_candidate_generation_runtime.py`；
- capture-first adapter：`src/sec_agent/s1_08_official_discovery_adapter.py`；
- 关系与质量 gate：`src/sec_agent/s1_08_source_quality.py`；
- proof：`configs/releases/fin_ia_0_1_3_s1_08_mature_component_relationship_budget_zero_call_proof_v1_0.json`。

## 2. 成熟组件 bake-off 的真实结论

采用 `feedparser 6.0.12`、`Trafilatura 2.1.0` 和 `lxml 6.1.1`，但权限非常窄：它们只能读取已经 capture 的 bytes，不能自行联网，不能决定 Evidence promotion，也不能成为金融日期权威。

真实 DELL R2 中两份 Microsoft 页面给出了关键反例：

- earnings-event 页：Trafilatura 与本地规则都找到 `2026-07-29`；本地将它绑定为 `event_date / official_event_heading / high`；
- press-release 页：Trafilatura 把 `2026-06-30` 识别为日期，但这其实是 quarter-ended 报告期；本地规则从 release masthead 恢复真正的 `2026-07-29`，把 `2026-06-30` 记为 rejected `reporting_period_end`。

正文层面，Trafilatura 把两页的已知导航词命中从 `14/14` 降到 `0/1`，证明它对静态页面清噪有实际价值；但上述日期误判同时证明“采用成熟轮子”不能等于“把金融控制权交给成熟轮子”。最终选型是：库做候选提取，FIN typed adjudicator 做日期类别、置信度、冲突和晋升。

没有把 Scrapy 整体接入，也没有把 Crawl4AI/Playwright 设为默认。当前问题是官方域内受限发现和静态页解析；再引入一套通用 scheduler 会与 exact-once、capture-first 和 Evidence-Slot 预算重复。动态页工具仍保留为以后按独立 fixture、成本和预算准入的 fallback。

## 3. v3 Runtime 的结构变化

1. **官方发现**：HTML alternate feed、RSS/Atom、robots/sitemap 和同 host HTML locator 都从已捕获响应解析；SEC submissions 支持 `10-K/10-Q/8-K/20-F/6-K`。
2. **日期权威**：输出 date value/kind/source/confidence/capture/conflict；只有 library-inferred date、modified date或高权威日期冲突时 fail closed。
3. **关系方向**：query/candidate 绑定 subject、evidence owner、ecosystem role 和 claim direction；Microsoft 客户案例这种“证据所有者的客户”页面在 document fetch 前拒绝，不能证明 Microsoft 自身需求。
4. **预算公平**：保持 16 次全局 ceiling，issuer+regulatory/customer/supply/market/contingency=`4/4/5/0/3`；五 slot 先各走一次，earlier slot 不再先跑完所有 revision。每 attempt 最多抓 2 份、最多接受 1 份 unique document。
5. **确定性与分账**：候选先稳定排序再应用 ceiling；相同 locator/capture 跨角色只计一份网络文档，role binding 单列；本地市场快照不进入网络文档收益率分子。
6. **历史兼容**：v1/v2 query/candidate 不注入 v3-only 字段，既有 30 个核心回归保持通过。

## 4. 验证结果

- 新 v3 测试：`18 passed`；
- 新 v3＋原 focused regression：`48 passed`；
- 全部 S1-08 contract tests：`60 passed`；
- compileall/diff check：通过；
- DELL/MU/NVDA full-fake：每案 5 role binding、4 unique network documents、1 governed local binding、4 network-equivalent fake calls、slot starvation=`0`；
- date/relationship/fetch ceiling/candidate permutation/canonical duplicate/feed/sitemap/robots/20-F/6-K mutation：全部 fail closed；
- network/model/provider/retry/admission：`0/0/0/0/0`。

回放还及时修正了一个指标缺陷：最初把 4 份网络文档加 1 份本地 market snapshot 除以 4 次网络访问，得到不合理的 `1.25` yield。现已改为网络唯一文档与本地受管来源分账，fake 口径回到 `4/4=1.0`。这证明本轮不是只让测试变绿，而是在校验指标的经济含义。

## 5. 仍未通过什么

这不是 S1-08 产品通过，也没有恢复 R3：

- official feed/sitemap 与 official-domain bounded route 只有离线 replay proof，没有 fresh live reachability；
- broad `external_site_search` 仍未配置真实 Provider；
- 当前没有新的 DELL live target-in-pool/recall 结果；
- ranking、BGE/Milvus、MU/NVDA live、DeepSeek、S3 研究综合和报告内容质量仍阻断；
- RC-P36-156 的共享 Project OS status/run-scope bug仍归 S0/S5，本轮只更新 canonical-open allowlist 继续 fail closed。

## 6. 下一步

下一项限定为：

`S1_08_V3_MATURE_COMPONENT_RELATIONSHIP_BUDGET_CLEAN_INDEPENDENT_ZERO_CALL_PROOF`

它只允许在 clean Git archive/fresh process 中复现代码、依赖、两份 R2 capture date decision、三案例 full-fake/mutation 和 60-test S1-08 suite。独立证明通过后，再单独决定是否值得签发一次新的 DELL fresh-live；本轮没有自动继承或创建任何 live authority。
