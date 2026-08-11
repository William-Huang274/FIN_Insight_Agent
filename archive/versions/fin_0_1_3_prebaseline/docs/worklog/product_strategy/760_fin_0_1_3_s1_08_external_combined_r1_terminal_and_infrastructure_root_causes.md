# 760 — FIN 0.1.3 S1-08 external combined R1 终态与基础设施根因

日期：2026-08-09

## Exact-live 事实

唯一 admission 已在 clean/synced `9b5a306e0f016452caeadd997ef4def03cbf4422` 上 exact-once 消费，终态为 `completed_with_typed_failures`，没有 retry、fallback 或自动 replacement：

- official/shadow planned terminal=`3 cases / 24 queries`；
- official/shadow/total network accounting=`29/24/53`；
- document/model/embedding/rerank/Evidence=`0/0/0/0/0`；
- Firecrawl HTTP=`200×5 / 429×19`，成功物化 50 个 locator、10 credits；
- public result digest=`4306d11d...6ed1`，terminal digest=`074fac99...92e`；
- assessment digest=`7a3796c9...2cf4`。

91 个 official content-addressed object 和 72 个 Firecrawl capture ref 全部重算通过。模型、DeepSeek 与内源检索均未参与本轮。

## 根因，不把失败错算给查询或模型

### 1. official lane 是项目 runner 缺陷

公开 allowlist 域名在当前 Codex Desktop 网络代理中解析到受控 synthetic range `198.18.0.0/15`。此前独立 canary runner 已有“先验证所有地址均属于该 range、再临时允许”的握手，但 combined runner 漏接了它。结果 29 次 official network accounting 全部在 HTTP 前被 SSRF guard 拒绝，形成 26 个去重后的 `official_source_private_network_forbidden` failure object；不是 SEC/IR 没有资料，也不是 Query Facet 没生效。

### 2. Firecrawl 是外部额度约束加项目调度缺陷

前 5 次均成功且全是 DELL；其中 4/5 query 的 top-10 包含 Microsoft、Micron 或 NVIDIA 官方域结果。第 6 次开始 Provider 明确返回 keyless free-tier `reason=credits` 和约 17.5 小时的 `retry_after_seconds`。现有 Runtime 只把 401/402/403 当系统性停止，因此继续发出另外 18 次必败请求；同时 case-major 排序让所有成功观察集中在 DELL，MU/NVDA 未被观察。

这不能解释为 MU/NVDA query 质量失败。完整 24-query Firecrawl 历史矩阵仍是查询质量依据，本轮仅证明 combined Runtime 对额度耗尽和公平调度处理不足。

### 3. Query Facet 已进入 delegate，但审计表面不完整

39 份 binding receipt 全部存在；36 个 external attempt 的 budget query digest 与 bound receipt 完全一致，3 个 market slot 为零网络本地豁免。说明真实 delegate 使用了编译后的 Query Facet。问题是 candidate attempt 的公开 `query` 仍显示 binding 前对象，receipt 又只留 digest、未留 effective query 全文，容易造成“新查询是否真的生效”的追溯歧义。

## 阶段处置

R1 保持 immutable，禁止直接重跑。仍留在 S1-08，只做一个零调用 successor 结构包：

1. combined runner 接回受控 synthetic-DNS 预检与临时执行握手，不放宽真实私网 SSRF 拒绝；
2. shadow 改为 case-slot 公平顺序；
3. `429 + reason=credits` 立即停止后续网络，但 24 个 planned identity 仍全部终态化；
4. receipt 保存 effective facet-bound query，消除 telemetry 双真相；
5. replay、mutation、三案 full-fake 和独立 clean proof 通过后，才另行签发有界 recovery live；不自动重复 Firecrawl 的完整质量矩阵。

外源 candidate discovery 尚未关闭，内源 exact/BM25/dense/graph 尚未启动。内源以及后续 qrels、BGE/fusion/rerank、Claim/Workpaper/report utilization 已由 `fin_ia_0_1_3_s1_retrieval_query_facet_external_internal_progression_plan_v1_1.json` 明确排在外源收口之后，不会因上下文压缩遗忘。
