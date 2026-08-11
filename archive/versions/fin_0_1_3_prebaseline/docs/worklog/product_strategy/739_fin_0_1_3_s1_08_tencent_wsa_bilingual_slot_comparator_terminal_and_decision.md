# FIN 0.1.3 S1-08：Tencent WSA 三案中英 Evidence Slot comparator 终态

日期：2026-08-08

## 结论

唯一已签发 comparator 已在 clean source commit `19943317af953c77627d7c3ba25320fe8d89e2dc` exact-once 消费。24 个 `DELL/MU/NVDA × 4 external Evidence Slot × EN/ZH` Query-only 请求全部返回 `Version=standard`，0 retry、0 model、0 document fetch、0 Evidence promotion。总文档价 1.104 元，p50/p95/max=`754/941/1052 ms`，整轮 20,296 ms。

运行可靠性和成本达标，但候选质量没有达到 SourceHunter 接入线：155 个 locator 中 topical useful=`110/240 useful@10 slots`，Evidence-eligible=`0/240`；12 个 case-slot 的中英 union target-in-pool=`0/12`，加入本地 market control 后 12 个 hidden target group recall=`0/12`。因此结论固定为 `fail_diagnostic_only / remain_diagnostic_only_no_reranker_rescue`，不接入 SourceHunter，也不准入 ranking/reranker。

## 中英文差异

| 案例 | EN mean topical useful@10 | ZH mean topical useful@10 | Evidence-eligible | target-in-pool |
| --- | ---: | ---: | ---: | ---: |
| DELL | 0.375 | 0.525 | 0 | 0 |
| MU | 0.350 | 0.625 | 0 | 0 |
| NVDA | 0.325 | 0.550 | 0 | 0 |

中文在三个案例都明显优于英文，但提升集中在泛相关报道和腾讯内容生态，未转化为冻结的一手目标。监管/财务核对槽最弱：DELL EN/ZH=`0.0/0.1`，MU=`0.0/0.0`，NVDA=`0.0/0.3`。这说明继续做一般 query rewrite 可能提高主题命中，却没有证据证明能补足 SEC/IR、客户验证和供应链反证目标。

## 日期与来源

- Provider 为 155/155 locator 都填了日期字段；但 exact target 命中为 0，故 matched-target 日期样本为 0，日期准确率不可计算，按预注册硬门失败。日期“存在”不能替代一手页面日期校验。
- DELL/MU/NVDA 的 unique registrable domain=`15/20/15`，最大单域占比=`0.372549/0.490566/0.558140`，表面来源多样性门通过。
- 候选中确有 `dell.com`、`investors.micron.com`、`nvidianews.nvidia.com` 等官方域，但多为支持页、首页/季度结果入口或非目标期间公告；它们没有满足冻结的 case-slot target，不能因域名官方就自动晋升 Evidence。

## 硬门结果

通过：24/24 terminal、standard rate=100%、每案例至少三个 registrable domain、最大单域占比不高于 70%、成本、p95、0 Evidence、0 reranker/document fetch。

失败：每 query 最低 topical useful@10、每 case-language 均值、case-slot target-in-pool、12-group hidden target recall、matched-target date accuracy。六个 query 低于 0.3，且三个英文 case-language 均值都低于 0.5。

## 决策与边界

1. Tencent WSA standard 保留为 `diagnostic provider`，不成为 SourceHunter production adapter。
2. 不追加 R5、query patch、正文抓取或 reranker rescue；这些动作不能证明缺失目标已经进入候选池。
3. 本 comparator 作为下一家 broad-search Provider 的同合同基线。只有候选 Provider 在相同 gold-blind 三案矩阵上通过全部硬门，才进入独立 integration decision。
4. S1-08 的 broad Web candidate coverage blocker 继续 open；该失败不是 DeepSeek、Agent Writer 或下游排序器问题。
5. 聊天中暴露过的 Tencent AK/SK 不在 Git、result 或 capture 中持久化，但应立即在腾讯云控制台吊销并轮换。

## 不可变证据

- result SHA256=`7c1aa3e21ccdca5d21820df0d6a125328c248e92ab6905053ab6e17003e6935e`
- result digest=`150b9f6236a120b125eeab1e3ec1b7b2602f25bbb72f8f2070d2933c35b3640c`
- assessment SHA256=`7b86708686b5c40d22202be9effbb252fc5afc278786f45e3b1bddae2f48b047`
- assessment digest=`51ae5c82e922c444dda3ddb8dd37316cebae47320b60b9b2cecfbd5bd5d0e89f`
- post-live Tencent＋Project OS 回归=`55 passed`，exact-once 复用在凭据读取前以 `result_already_exists` 阻断；Git tracked/untracked 与 Runtime 共 5,446 个文件的两项实际凭据值精确扫描均为 0 命中。
