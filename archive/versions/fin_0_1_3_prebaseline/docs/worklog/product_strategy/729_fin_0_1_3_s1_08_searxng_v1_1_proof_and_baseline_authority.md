# 729 — FIN 0.1.3 S1-08 SearXNG v1.1 clean proof 与三案诊断 authority

日期：2026-08-08

阶段：`013-S1-08`

## 结论

修复 deployment boundary 后，clean commit `56e39f84` 的 v1.1 proof 通过：`15 passed`，DELL/MU/NVDA 三案 full-fake 各有一个未晋升 locator，capture=`9`，network/model/provider-model/retry/Evidence promotion=`0/0/0/0/0`。Docker compose config 与非搜索式 healthcheck 合同通过。

因此按用户已经批准的开源诊断路线，签发一次 exact-once diagnostic authority：

- DELL、MU、NVDA 各一个预注册 broad-search query；
- FIN adapter 到本机 SearXNG 最多 3 次 query；
- 每 query 最多 20 个 canonical locator；
- 配置 engine 固定 Bing、Brave、DuckDuckGo、Google，最多四路 fan-out；
- retry/model/document-fetch/Evidence promotion/Writer/production claim 均为 0；
- 不允许公共 SearXNG fallback；
- 即使 locator 为 0 或 engine 全部失败，也保存三案 typed terminal，不自动补跑。

## 重要口径

“3 次 query”只指 FIN 到 SearXNG 的可控调用。SearXNG 内部实际 HTTP 请求由 engine 实现、重定向和失败路径决定，无法被 FIN adapter 精确声明为 3 或 12；只能披露配置上限、参与 engine、unresponsive engine 和结果 lineage。这个限制本身就是未来付费 API 对照的重要维度。

本 authority 不解除 RC-P36-157，也不修改 no-R4。执行结果仅回答“这个自托管聚合器能否低成本把更多候选 URL 送到入口、哪些引擎在当前网络环境可用”；不能回答“来源是否真实”“Evidence 是否足够”“报告质量是否合格”或“SearXNG 是否可生产”。
