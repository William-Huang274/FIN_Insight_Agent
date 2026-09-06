# 对外展示范围 / Sharing scope

2026-09-07。本文是展示准备，不是修改远端仓库可见性、自动发布报告或授权重分发第三方资料。

## 可以准备展示 / Suitable for review

- 源码、版本锁、合成测试、实际架构和可验证交互。Source, dependency locks, synthetic tests and truthful architecture.
- 已脱敏的截图、按请求/角色汇总的成本/token/耗时，附运行类型、样本数与失败。Redacted screenshots and request/role metrics, with sample sizes and failures.
- 人工确认的报告节选及可访问的出处链接；完整报告对外分享需另确认。Human-reviewed excerpts with source links; full publication is a separate decision.

## 不默认公开 / Excluded by default

`.env`、账户/鉴权信息、用户上传、原始抓取正文、私有SQL/索引、原始模型请求/回复/私有reasoning、完整LangSmith trace、个人求职资料和机器本地状态。也不把忽略规则当作Git历史已无秘密的证明。

Credentials, uploads, crawled source bodies, private databases/indexes, raw model context/private reasoning, full traces, job-search data and host state are excluded. Ignore rules do not prove Git history is secret-free.

## 指标怎么说 / Evidence claims

- 一个Dell开发case不等于跨公司泛化或盲测；一种上传图片不等于OCR准确率。One developed case is not generalization; one vision probe is not an OCR benchmark.
- 测试替身不计作真实模型成功；子图成功不能相加为端到端成功。Scripted fixtures and independent segment successes are not full-chain model results.
- 单样本耗时不是P95；估费不是账单。Single-run latency is not P95; estimates are not invoices.
- token包括已知失败；缺失用量单列。Include known failed-call usage; disclose unknown usage.
- 模型审查、宿主核查和Owner验收分别记录。Model review, host review and Owner acceptance remain distinct.

## 当前证明 / Current evidence

2026-09-07真实前端→新Dell九主题研究→审查/责任修订→综合/Writer/终审已发生；v3为7,281字符、42引用、3图，四格式已下载/渲染。当前仍为needs_revision：1条重大意见指向P02需求底稿旧推断未与正文同步，未Owner验收。265请求/264已知用量/17,060,539tokens/估28.092715元，包含失败、原生接续和人审改稿，另1次失败用量未知。不是无辅助一次通过、不是单次普通问答定价。任务上传MCP视觉另1请求、423tokens、2.801s，正确识别两个值且标为合成数据；再次请求缓存。详S3/190，不再追加paid。

The fresh UI-started nine-topic case has reached v3 (7,281 narrative characters, 42 citations, three charts) with real reviews, targeted repairs and four rendered exports. One material workpaper/report inconsistency remains; the state is needs_revision, not accepted. The six native runs total 265 requests, 264 with usage, 17,060,539 tokens and estimated CNY 28.092715; one failed request has unknown usage. This includes development continuations and human-directed revisions, not unassisted one-shot success or short-Q&A pricing. A separate real MCP vision probe used 423 tokens in 2.801s and correctly identified synthetic data; repetition used the cached interpretation. No further paid execution was started.

公开前仍需确认展示选稿、第三方许可/再分发、仓库当前及历史敏感项、私有数据剥离，以及用户是否要改变远端可见性。当前只做准备，不擅自公开。

Before publication: choose approved examples, review third-party redistribution/licenses, inspect current and historical sensitive material, separate private assets, and obtain the Owner's visibility decision. No visibility change is performed by this work.
