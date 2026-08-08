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

## SQL 与 ranking 边界

18-row research qrels 混合定性、关系和监管目标，不能把 exact SQL 0/18 当成统一失败。SQL 将建立独立 numeric-fact qrels suite，核对 metric、period、unit、authority 和 value。BGE/fusion/rerank 仍需等待 research candidate 18/18 与 Owner qrels review，不能替代缺失源。
