# 724｜FIN 0.1.3 S1-08 P3：自有修复、Provider 与产品来源范围处置

日期：2026-08-08

阶段：`013-S1-08-P3`

结论：P3 已完成零调用决策。先执行一个有界的项目自有调度／缓存修复与证明包；Provider 采购、受控动态页／站内搜索、licensed source 和 Internal Alpha 来源范围缩减均暂缓。no-R4、全局 16 次网络上限和既有质量门不变，本项没有授权任何新 live。

## 为什么不能先买 Provider 或先缩范围

唯一 DELL R3 的机械运行完整结束，但来源产品门为硬失败：`15 network / 13 query attempts / 229 qualified locator receipts / 0 document request / 0 candidate / 5 typed gaps`。

R3 已证明两个项目自有缺陷：

1. landing、feed/sitemap/structured discovery 与 document fetch 共用 attempt allowance，自然多 route 会在正文抓取前耗尽配额；
2. pre-request 的本地预算停止以 `response=None` 进入跨 attempt document cache，后续 slot 即使有自己的配额也会复用一份根本没有访问网络的失败。

Dell/Micron IR transport、`external_site_search` 未运营和 current market snapshot 缺失是真实运营缺口，但它们解释不了“229 个 locator 通过后 0 次正文请求”。在这条自有路径没有被证明可抓正文前：

- 接入新 Provider 仍会进入同一条坏路径，无法判断采购是否必要、充分或值得；
- 缩小来源承诺会把 false gap 当成公共资料上限，掩盖项目缺陷；
- 加预算、retry、放宽 Evidence Gate 或建立 R4 只会绕过已冻结的止损规则。

因此选定 `repair first, then decide provider/product scope`，不是默认坚持免费公开源，也不是拒绝未来购买数据。

## 获准的唯一工程包

下一 scope：

`S1_08_P3A_PROTECTED_DOCUMENT_FETCH_BUDGET_AND_ATTEMPT_LOCAL_CACHE_ZERO_CALL_IMPLEMENTATION_AND_PROOF`

它是一个整合包，不拆成逐 URL、逐字段的多轮修补：

- 在全局 `16` 次网络上限不变的前提下，合格 locator 必须获得受保护的正文抓取机会；
- discovery 与 document fetch 需要有明确的调度相位／保留语义，但所有真实请求仍计入同一全局预算；
- pre-request local stop、slot allowance stop 或 global stop 不得进入跨 attempt 文档缓存；
- captured remote success、captured remote failure、parser outcome 和 attempt-local stop 必须具有不同 typed lineage；
- 用 R3 immutable captures 回放真实 adapter 的 landing→structured route→document 拓扑，而不是 fake 直接返回 candidate；
- 覆盖多 route、locator/allowance permutation、跨 slot negative-cache poisoning；
- 执行 DELL/MU/NVDA full-fake，以及 numeric、identity、currentness、relationship、lineage mutation；
- R3 result、captures、terminal 和 evaluation 必须 byte-stable；
- 网络、模型、Provider、admission、live 调用均为 `0`。

candidate execution policy 必须升为 successor `v4`；不得偷偷修改历史 v3/R3 合同后声称旧证明仍成立。

若 P3A 在固定 16 次上限内无法证明 protected fetch 与 attempt-local cache 两个不变量，立即停止实现并回到 Provider／产品来源范围处置，不进入 live。

## 明确没有授权的事项

- R3 replay、R4 或任何新 DELL live；
- 增加预算、retry 或放宽 Evidence Gate；
- Provider 采购、凭据接入或动态浏览器 fallback；
- ranking、BGE、Milvus、selected-pack evaluation；
- MU/NVDA transfer；
- DeepSeek Experiment B、S3 研究、S4 Workbench 验收或 S5 release。

即使 P3A 全绿，也只说明项目内不变量被修复。任何新的真实 DELL Attempt 仍须另做 owner 决策，同时复核 residual Provider 缺口、Internal Alpha source claim 和是否明确修改 no-R4。

## 产品与版本边界

本项继续属于 FIN 0.1.3 的 S1-08，不创建 0.1.4，也不改变 FIN 0.2 定义。Internal Alpha 来源能力目前只是目标，不是已通过能力；P3 没有新增 source、candidate、Evidence、研究内容或产品验收。

机器决策：

- `configs/releases/fin_ia_0_1_3_s1_08_p3_post_r3_owned_scheduler_cache_and_provider_product_scope_disposition_decision_v1_0.json`
- decision digest：`d3ba29f87621b34b1339e25fe94982aea01a7104c0f97b72b9d1f6421cfc8f16`
- file SHA-256：`57e80147f657a62fd83dfef019bd5190e8a03dded90c60608484c97262970f9f`

## 当前下一步

只执行 P3A 零调用实现与证明。实现完成前不得把 P3 描述为 Runtime repaired，也不得宣布 S1-08、Agentic Search 或 FIN 0.1.3 产品能力通过。
