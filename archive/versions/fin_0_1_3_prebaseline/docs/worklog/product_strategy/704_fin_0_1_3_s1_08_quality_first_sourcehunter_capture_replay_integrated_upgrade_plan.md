# 704 — FIN 0.1.3 S1-08 质量优先 SourceHunter × Capture Replay 一体化升级计划

日期：2026-08-08
阶段：`013-S1-08`
状态：`plan approved / implementation not started / live not authorized`

## 1. 用户纠偏与结论

R1 后如果只补网络异常、日期过滤和 partial result，最多只能得到一个“更不容易崩”的爬虫，不能证明它更会找研究材料。用户明确要求把 **质量优先的 SourceHunter 升级** 与 **capture replay** 合成同一轮计划。

因此本轮不再把 replay 当作修完代码后的附属回归。R1 的 19 次请求、导航噪声、旧 SEC filing、三个已分类 transport failure 和最后一个未配对 request，直接成为 SourceHunter 规划、筛选、晋升、预算和终态物化的共同验收语料。每个被回放的 URL 都必须能回答：

1. 它服务哪个研究 Evidence Slot；
2. 为什么选择该来源路线；
3. 为什么值得在 fetch 前消耗网络预算；
4. fetch 后为何成为 candidate、context、rejection 或 typed gap；
5. 失败后是否仍留下完整、可追溯的部分结果。

## 2. 一体化升级边界

统一升级包编号为 `S1-08Q-A` 至 `S1-08Q-H`，但它们不是八轮 live 修补，而是一个零调用工程包内的可验证工作单元：

- `Q-A`：建立受限 exact replay manifest 与可进 Git 的脱敏结构 fixture；
- `Q-B`：把研究问题编译为 issuer results、regulatory reconciliation、customer demand、supply/counterevidence、market context 五类 Evidence Slot；
- `Q-C`：建立 provider-neutral 多通道 discovery，覆盖 SEC、IR results/news/events/sitemap/RSS、外部/site search 以及客户、供应商、政府/行业官方材料；
- `Q-D`：fetch 前按 source family、path、title、entity、form、date、as-of 和 slot fit 过滤；
- `Q-E`：fetch 后按正文内容、权威、时点、研究角色和重复度决定 promotion；
- `Q-F`：所有连接终止 typed capture，逐步物化 partial attempts、receipts、rejections 与 gaps；
- `Q-G`：capture replay、三案例 full-fake/mutation、质量与效率同时过门；
- `Q-H`：只在 clean proof 后另做一次 DELL replacement authority decision。

## 3. Replay 如何真正服务质量

Replay 分两层：

1. **受限 exact manifest**：Git 只保存 digest 和脱敏元数据，正文仍留在受限 content-addressed store；Authorization、Cookie、SEC contact 明文和任何私有推理不得进入版本库。
2. **可移植脱敏 fixture**：只保留 anchor 类型、路径、日期/form、连接异常、partial terminal 等结构形状，不包含 hidden Gold、benchmark 答案或预期洞察。

每项质量改造都必须有对应 replay 证明。比如 Outlook/Store/Surface 链接必须在 fetch 前被拒绝；2022/2023 filing 在存在更新且适格文件时不能胜出；最后一个 request-only 形状必须生成 typed failure；前 18 次已有工作必须在 terminal candidate result 中保留。

## 4. 产品级质量门

结构门要求：R1 所有请求 `100%` 有终态分类、未配对 request=`0`、partial materialization=`100%`、已知导航噪声 fetch=`0`、有更新适格文件时 stale filing selection=`0`、Gold/cross-case 泄漏=`0`。

研究来源门要求：五类 Evidence Role 均得到 candidate 或 typed gap；DELL live `target-in-pool=1.0`、`required-slot recall@8=1.0`、currentness/diversity-or-typed-exception/reconciliation/selected-pack coverage=`1.0`、false promotion=`0`、qualified-document yield 至少 `0.5`。

拟议 DELL R2 上限为 network calls `<=16`、model/provider/retry=`0/0/0`、单次调用 timeout `<=30s`、全案 hard timeout `<=300s`。这里的关键不是单纯少抓，而是至少一半网络请求形成能关闭/解释 Evidence Slot 的合格正文；外部延迟单独记录，不能成为丢 capture 或丢 partial result 的理由。

## 5. 停止规则

- 没有可运行的 external/site-search provider 时必须返回 route unavailable，不能把官方定向抓取宣传成广域 Agentic Search。
- 若不看 hidden Gold 就无法排除导航噪声或旧文件，说明 source-family classifier 仍是过拟合，应继续留在 S1-08 重构。
- replay 通过只证明结构和历史样本，不能代替 live；DELL R2 live target-in-pool 不过，继续修 candidate coverage，不准进入 ranking/BGE/Milvus/S3。
- DELL 通过后也不自动扩 MU/NVDA，需分别做 transfer authority。

## 6. 本轮实际变更

本轮只冻结计划、机器可读合同、文档边界和 Project OS 状态。runtime、网络、模型、admission、replacement=`0`；R1 保持 immutable failed，R2 未签发。

机器合同：`configs/releases/fin_ia_0_1_3_s1_08_quality_first_sourcehunter_capture_replay_integrated_upgrade_plan_v1_0.json`。

下一项：`S1_08Q_A_TO_G_ONE_ZERO_CALL_INTEGRATED_IMPLEMENTATION_AND_PROOF_PACKAGE`。
