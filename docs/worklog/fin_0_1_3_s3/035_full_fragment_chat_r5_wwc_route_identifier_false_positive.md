# FIN 0.1.3 S3 FFJ-R5：WWC 路线标识误判

## 运行事实

- clean/synced implementation commit：`9d3ba6085a52ff73bd3793594ce94954a8285f8c`
- 模型调用：6/6；accepted Tool Calls：3/3；retry、fallback、外源检索、embedding、协议切换和发布均为 0。
- 三个自然片段均单独通过。因果极性 v1.5 的旧误判没有复发。
- 终态失败码：`research_consumer_wwc_evidence_route_invalid`；public result digest：`b7bf4277ef32baec56226b4e49c578349e3b9eb3921379af9088ba87c266cdc4`。

## 大白话根因

模型在“下一步去哪里核验”中写了“官方业绩稿或 10-Q”。`10-Q` 是项目来源政策本来就允许的官方财报类型，不是模型编造的财务数字。可是当前代码把写观点用的“禁止自由数字”规则也原样套到了来源路线字段上，只要看到数字字符就失败。因此这是字段职责混淆造成的本地误拒，不是 DeepSeek 没按研究边界写，也不是网络问题。

## 业务内容

R5 的 thesis、mechanism 和 counterargument 都没有把 AI 服务器强归因为公司利润。WWC 选择下一同财季公司毛利率，并用当前期毛利率作为阈值；它能检验公司层反方观察是否持续，但即使毛利率回升，也不能单独补齐产品利润桥。该限制应进入后续内容质量评价。

## 下一步边界

只在 `evidence_route` 字段允许来源政策中预注册的完整文件标识（例如 `10-Q`）。剥离该标识后，任何百分比、金额、日期、年份或未知数字仍硬失败。保存 R5 三个 fragment 必须原样通过终态，同时对“10-Q 加自由百分比／年份／未知数字”等 mutation fail closed；再做三案例与 fresh-process proof。R5 本身不追认为成功，新运行需新身份和独立权限。
