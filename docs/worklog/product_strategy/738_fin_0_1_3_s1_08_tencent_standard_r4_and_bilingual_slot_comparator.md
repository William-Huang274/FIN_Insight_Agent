# FIN 0.1.3 S1-08：Tencent standard R4 终态与三案中英 Evidence Slot comparator

日期：2026-08-08

## 结论

Owner 将腾讯 WSA 切换到 standard 后，唯一 same-query R4 已从 clean commit `2e6fbf9f...7c17` exact-once 完成。`Version=standard`，1 provider/network call、0 retry/model/document/Evidence，耗时 971 ms，文档价 0.046 元。标准版确实把 frozen DELL 查询从 lite 的 `0/10` 主题相关结果改善为 `10/10`，但不能据此接入 SourceHunter：10 条均属于 `qq.com` 的同一腾讯内容生态，没有命中任何冻结的一手资料，四个 DELL hidden target group 仍为 `0/4`，日期也只有 Provider 字段而没有一手页面校验。

因此本轮把两个不同概念分开记录：

- `topical useful@10=10/10`：结果谈的是戴尔 AI 服务器、订单、收入或 backlog；
- `Evidence-eligible useful@10=0/10`：没有一条同时满足冻结目标身份、日期一致和一手来源边界。

这证明 standard 改善了语义召回，却没有证明 primary-source discovery、日期权威、来源独立性或三案例迁移。后端 reranker 无法从缺失的一手资料中创造 Evidence，故 ranking 继续不准入。

## Comparator 设计

按 Owner 要求，建立一个 gold-blind 的三案中英对照：

- 案例：DELL、MU、NVDA；
- 外部 Evidence Slot：发行人业绩、监管/财务核对、客户需求验证、供应链/反证；
- 语言：英文、中文；
- 总计：`3 × 4 × 2 = 24` 个 Query-only SearchPro 调用；
- 本地市场价格槽不交给 Web Provider，继续使用 governed local snapshot；
- 预算：最多 24 provider/network、0 retry/model/document/Evidence，standard 文档价上限 1.104 元。

查询编译阶段只允许公司身份、通用 Evidence Slot 语义、年份和机制词，不允许 Gold ID、target ID、benchmark URL、隐藏 expected insight 或既有结果 URL。全部 Provider 调用 terminalize 后，evaluator 才加载冻结的 source registry 与 hidden target groups。

## 评分和门槛

必须同时报告：

1. topical useful@10；
2. Evidence-eligible useful@10；
3. 每 query 与中英 union 的 target-in-pool；
4. 加入本地 market control 后的 12 个 hidden target group recall；
5. Provider 日期存在率与 exact-target 日期准确率；
6. hostname、registrable domain、独立 publisher ecosystem 与最大生态集中度；
7. 每次和总成本；
8. 每次、p50、p95、最大值与整轮延迟。

SourceHunter 接入前硬门包括：24 次全部 terminalize、standard Version 率 100%、每 query topical useful@10 至少 0.3、每 case-language 均值至少 0.5、12 个 case-slot 中英 union target-in-pool 100%、产品 hidden target group recall 100%、matched-target 日期准确率 100%、每案例至少 3 个独立 registrable domain、单一生态占比不高于 70%、p95 不高于 5 秒、总文档价不超过 1.104 元。任何一项失败都保持 diagnostic-only，不能先调 reranker。

## 工程证明与权限

focused comparator 与 R4 related=`18 passed`，compile pass。三案 fake 能通过全部预注册门；Gold ID 注入查询会 fail closed；同一 case-slot 的中英两路均缺目标会阻断 integration。每次调用均先保存 safe request，再保存完整 raw response 或 typed failure，最后写单调用 terminal 和聚合 terminal；凭据只接受 hidden input，不进入版本化结果。

已签发一次独立 comparator authority：`24 calls / 0 retry / 0 model / 0 document / 0 Evidence / <=1.104 CNY`。它只允许比较，不允许自动接入、Evidence 晋升、DeepSeek、Agentic Research、S1-08 closeout 或 release。

## 下一步

先提交并推送 clean authority，然后 exact-once 消费 comparator。运行后再执行零网络 evaluator：若全部硬门通过，只进入一个独立 SourceHunter adapter integration decision；若任一门失败，保留结果并返回 Provider/语言/槽位差异，不再用 reranker“救”候选池。
