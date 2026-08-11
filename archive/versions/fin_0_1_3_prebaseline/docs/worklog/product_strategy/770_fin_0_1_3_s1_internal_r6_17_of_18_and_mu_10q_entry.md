# 770 — FIN 0.1.3 S1 内源 R6 17/18 与 MU 10-Q 入口

日期：2026-08-09

## R6 结果

Object compact-lineage 修复后，R6 的候选总量与失败的 R5 完全一致：`SQL 0 / ObjectBM25 369 / BM25 297 / Graph 196 / Milvus 0 qualification-only`。112 个 supplemental candidates 均绑定到正确的当前 DELL、MU 或 TSM URL、发布日期与 accession，证明修复只纠正血缘，没有放宽过滤或制造候选。

qrels 在候选生成完成后才加载。七条此前 absent 的行获得当前官方文档中的材料相关 partial hit：DELL FY2026 10-K 风险材料、MU Q3 FY2026 当前业绩/供给爬坡材料、TSM Q2 2026 当前先进节点需求和爬坡材料。SEC-hosted same-event exhibit 被明确标记为 semantic alternative，不声称和 IR 页面逐字相同，也不成为 Evidence。agent-curated target-in-pool 因此为 `17/18`；仍未做 Owner review。

## 唯一剩余研究候选缺口

`MU / regulatory_risk_and_financial_reconciliation / MU` 明确只接受 10-Q、10-K、6-K 或 20-F，不能用已经取得的 8-K 业绩附件代替。上一轮已经保存的 SEC submissions 响应中存在 Q3 FY2026 10-Q locator：accession `0000723125-26-000015`、filing `2026-06-25`、report `2026-05-28`、primary document `mu-20260528.htm`。这不是 broad search，也不是 benchmark URL 注入。

下一项只允许一次独立 successor：从 retained capture 固化 locator，最多抓取该一份 10-Q，网络上限 1、retry 0、模型/provider/embedding/rerank/Evidence 均为 0。成功后建立新的 supplemental successor 并重跑 18-row gate。上一 admission 不复用，R6 不覆写。

## 单文档 successor 零调用复证

locator 已由 retained submissions capture 独立物化，未读取 benchmark exact URL。首份 acquisition proof `v1_0` 诚实保留为失败：Runtime 把仅代表真实 I/O 的 `network_calls` 在 fake transport 下错误要求为 1，因而把已经完成 capture/parse 的 fixture 终态改写为 `terminal_failed`。这不是来源、解析器或模型问题。

修复仅让计数断言随 transport 类型变化：fake proof 必须为 0，真实 transport 必须为 1；授权 ceiling 仍为 1，未放宽。`v1_1` proof 通过，focused contract=`7 passed`，Project OS exact scope=`pass`。现已具备 commit-bound runner，但尚未签发 admission、未访问网络。下一步必须先 clean commit/push，再做 preflight；只有通过后才签发和消费唯一一次 live admission。

## Live 与 R7 结果

clean/synced commit `561aa6c29f91c3cb6bb07c44627b8a3cac5a65cf` 上唯一 admission 已 exact-once 消费。SEC 10-Q 抓取成功，正文 `230,003` 字符，network=`1`，retry/model/provider/embedding/rerank/Evidence=`0`；共享 ledger 为 terminal success。公开记录只保存 URL、日期、accession、capture refs/digests，原始响应与正文继续留在 Git 外。

该文档被机械切成 `118 BM25 + 118 ObjectBM25` candidate-only segments。三资产联邦 R7 沿用完全相同的 90 个请求、严格身份/期间过滤与每路预算，路由候选总量保持 `SQL 0 / ObjectBM25 369 / BM25 297 / Graph 196 / Milvus 0 qualification-only`。MU regulatory/reconciliation bundle 中有 `13 BM25 + 13 ObjectBM25` 个当前 10-Q 候选；选择的 `CHUNK_0053` 在 BM25 route rank 7，正文明确包含客户现金存款及承诺、2026 capex、采购义务、政府补贴 clawback 条件和 DRAM 产能扩张。

qrels v1.3 因此达到 agent-curated `18/18`，但状态仍是 `owner_review_pending`。这不是排名通过：17 行来自 BM25、1 行来自 ObjectBM25，尚未比较 BGE、fusion 或 reranker。Owner 未复核前不准入 BGE；研究 qrels 也不替代独立 exact-SQL numeric-fact suite。external official 4/12 与 hidden target-in-pool 0/12 的 blocker 完全不变。

## SQL 与 ranking 边界

18-row research qrels 混合定性、关系和监管目标，不能把 exact SQL 0/18 当成统一失败。SQL 将建立独立 numeric-fact qrels suite，核对 metric、period、unit、authority 和 value。BGE/fusion/rerank 仍需等待 research candidate 18/18 与 Owner qrels review，不能替代缺失源。

## 独立 exact-SQL 数值套件与资源资格

独立套件绑定两套不同性质的事实权威：此前冻结并已交付的 latest-available annual 数值结果，以及同证据包中明确给 Agent 看见的 current-quarter 数值。它没有把 benchmark 反向写入数据库，也没有调用网络、模型、embedding、reranker 或 Evidence promotion。

结果纠正了“Gold SQL 整体没有当前数据”的过度概括。候选审计仍配置到 74,897 行的旧主 mart；该库对 9 个 current annual qrel 只命中 MU 的 3 行，合计 `3/9`。此前 S1 已生成的 60 行三案例 successor mart 对 DELL FY2026、MU FY2025、NVDA FY2026 的 revenue／gross profit／operating income 达到 `9/9`，说明 exact lookup、metric、period、unit、value 和 authority 本身可工作，缺陷在资产路由和新鲜度分账。

但两套 mart 对冻结的 6 个 current-quarter 产品事实仍为 `0/6`：DELL Q1 FY2027 revenue／OCF、MU Q3 FY2026 revenue／capex、NVDA Q1 FY2027 revenue／OCF 均未进入 exact SQL。该结果被保留为 typed freshness gap；benchmark 只能评测缺口，禁止被用作自动回填来源。当前结论因此是 `annual exact route ready / current-quarter refresh blocked`，不能宣称 exact-SQL 产品面已完成。

资源资格也已单独完成：Milvus 约 66 万向量、字段、1024 维和 ticker coverage 沿用 R7 的已绑定观察；显式 runtime dependency 目录含 pymilvus；本机 `D:/hf_models/BAAI__bge-m3` 的必需文件与 hidden size 1024 匹配。当前 runtime 配置仍指向不存在的旧 snapshot，故只记为 `qualified successor locator not yet bound`。本机没有 BGE reranker，记为 optional resource absent，不自动下载。以上检查没有加载权重或执行一次向量／rerank。

下一门槛仍是 Owner 对 18 行 research qrels 的接受或退回。Owner 接受后才允许建立新的 BGE/Milvus execution policy，并先比较 sparse、dense 与 facet-aware fusion；reranker 缺失不会阻止前述三路对照，但也不能被冒充为已测试。current-quarter exact mart refresh 与 external 4/12 blocker继续独立保留。
