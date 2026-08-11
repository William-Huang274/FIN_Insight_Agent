# 810 — FIN 0.1.3 S1 外源残余缺口优先级计划

日期：2026-08-10

阶段：S1／五步计划第 4 步前半段

状态：zero-call priority compilation terminal；network authority pending

六份本地 Evidence Pack 共留下 126 个 raw facet gaps。本轮没有把它们机械变成 126 次搜索，而是按投资决策价值、公开可得性、证据披露主体和来源类型，压缩为六家公司各 2 个、合计 12 个 SearchIntent。88 个相关 facet 被组合进这些业务问题，38 个保留为 typed deferred gap。网络、Provider、模型、embedding、rerank 均为 0。

具体业务例子：DELL 的第一条意图问“AI 服务器订单和 backlog 是否可持续，以及能否转化为 ISG 利润率和现金”；第二条问“Micron／TSMC 自身披露的 HBM 与先进封装供给是否构成瓶颈”。ORCL 的第一条问“OCI 收入、RPO、客户承诺、产品组合和利润率能否共同证明云需求的量与价值”，而不是分别搜十个字段。估值公式、市场 point-in-time、用户风险阈值和公开资料无法证明的客户 allocation 不在本轮乱搜，继续由数值程序、S3 方法或 typed gap 所有者处理。

离线测试第一次真实发现边界写窄：校验器曾要求所有文档都属于被研究公司域名，这会错误拒绝 DELL／NVDA 的 Micron、TSMC 供应侧自我披露。现已改为显式 `evidence_owner_entity_key → official hosts` 注册表。研究主体、证据披露主体和关系方向是三个独立维度；供应商材料只能证明供应商公开说了什么，不能自动升级为 DELL／NVDA 获得了多少 allocation。

外源 live 仍未开始。后续最多 6 次官方发现页抓取、12 次腾讯标准搜索 URL 定位和 12 次官方文档抓取，总网络上限 30、retry=0。搜索服务商只提供 locator，snippet 和其标注日期都不是 Evidence；候选文档必须重新 capture、解析日期并通过本地内容门。找不到就是 typed gap，不允许靠模型补写。

验证：priority plan digest=`e1eb54f7...81c19`；`11 passed`；Project OS scoped preflight=`pass/open blocker 0`。该结果只授权后续另行签发的一次 exact-once live，不代表外源覆盖、Evidence Pack successor、DeepSeek 或研报通过。
