# 725｜FIN 0.1.3 S1-08 P3A：protected fetch 与 typed cache v4 工程实现

日期：2026-08-08

阶段：`013-S1-08-P3A`

状态：working-tree 零调用工程通过；clean archive／fresh process 独立复证待执行。

## 本轮实际解决了什么

R3 的根因是同一 attempt 的 discovery 会先消费 landing、structured route 与正文额度，合格 locator 虽已出现却没有剩余额度抓正文；随后本地未发请求的 `response=None` 又进入跨 attempt 文档缓存，形成 false gap。

P3A 现以独立 v4 successor 实现：

- 全局网络上限仍是 16，所有真实请求仍进入同一总账；
- 每个有网络额度的非 market attempt 至少保留一次正文抓取机会，discovery 不能消费这份保留量；
- global／slot／document budget stop，以及 request 前 cancel／local timeout，全部是 `attempt_local_noncacheable`；
- captured remote success、captured remote failure、parser success、parser failure 与 local stop 分型记录；
- 远端失败可在同一运行中复用以禁止 identical retry，但没有 request/response capture 的本地停止永远不能写跨 attempt cache；
- landing 或 structured 子路径一旦因 request 前本地停止而未完整遍历，父级空结果或部分结果同样不得进入跨 attempt discovery cache；
- Source candidate 只允许 regulatory／issuer／industry／non-authoritative market authority，不得冒充 exact numeric authority。

## 一次重要的工程纠正

最初在原 v3 Runtime 和 adapter 内增加 v4 条件分支。回归立刻出现 6 个失败：历史 R3 successor 会逐字节核对这两个源文件，任何修改都会使旧 proof 的 source binding 失效。

这不是功能回归，而是历史证据保护正确工作。实现因此改成真正 successor：

- v3 candidate Runtime SHA 保持 `441718f5...5f42`；
- v3 official adapter SHA 保持 `aa55bc8f...f294`；
- v3 catalog、R3 result 与 R3 evaluation 均 byte-stable；
- 新行为只进入 v4 catalog、v4 candidate Runtime 和 v4 adapter。

这也验证了“合同升版不能在旧 source-bound 文件里偷偷加分支”应成为后续 Runtime 的默认做法。

## 零调用证明结果

- 新 P3A focused：22 passed；
- 原 S1-08：70 passed；
- 合计：92 passed，0 failed，0 skipped；
- allowance 2／3／4 均可在 locator 已合格时保留正文请求；
- synthetic natural topology 完整经过 landing → robots → sitemap → document；
- R3 restricted capture replay 使用真实 Microsoft landing／structured response 拓扑，前三次请求来自 immutable R3 captures，第四次确实成为受保护 document request；
- document、landing 与 nested structured 三类 cross-slot local-stop cache poisoning 均被拒绝；remote failure 与 parser failure typed cache 可复用且不 retry；
- DELL／MU／NVDA full-fake 每案 8 个 simulated budget calls 完成 5 slot；
- identity、currentness、relationship、numeric authority 与 lineage mutation 全部 fail closed；
- network／model／Provider／retry／formal admission／live=`0/0/0/0/0/0`。

## 还不能宣布什么

当前 checkout 通过不等于 clean-source 独立证明。P3A 尚未完成，S1-08、DELL candidate ceiling、target-in-pool、ranking、Agentic Research 与 FIN 0.1.3 产品能力均未通过。

下一步只允许先精确提交／推送本实现，再从该 commit 的 clean Git archive 和 fresh Python process 注入只读 R3 captures 做一次零调用复证。复证通过后也只进入 P3B owner decision；不会自动生成新 DELL Attempt 或修改 no-R4。
