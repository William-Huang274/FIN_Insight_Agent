# S2 法说数值权限与同期比较回归

日期：2026-08-16
实现提交：`9f0767141de309bd469f30e73cb282068f514179`

## 1. 为什么做这轮

S1 刚把 Dell 与 TSMC 法说接回当前检索。法说里包含订单、积压、收入和利润率等大量数字，因此在进入 DELL 五单元前必须确认：模型可以看见并引用这些数字，但它们不能绕过 S2，直接成为正式 NumericFact。

## 2. 第一次为什么失败

R1 重新构建出与当前库字节完全相同的 SQLite：1,319 条 observation、24/24 qrel、数据库 SHA 均未变化。但旧 mutation 仍要求开放期间查询只返回最新 Q1 和最新财年，因此把“当前 10-Q 同时披露的上年同期 Q1”判成错误。

这与当前产品合同冲突。S3 若要写“同比”，必须同时看到本期 Q1 与同口径上年 Q1；真正应该拒绝的是旧 Q3 YTD 混入，而不是拒绝合法同比端点。

因此 R1 保持失败，不追认。问题登记为 `RC-S2-005`，归 S2 验收器语义漂移，而不是事实库、法说或模型。

## 3. 怎么修

- 新验收明确要求三项同时出现：DELL FY2027 Q1、同一当前 10-Q 中的 FY2026 Q1 对比列、最新 FY2026；
- 明确要求旧 Q3 YTD 不出现；
- 旧 v1.0 结果及其 digest 保持不变，避免破坏已绑定它的 S1-D 历史 authority；
- 当前 builder 与 Workbench 构建入口晋升到 result v1.1；
- 增加回归，确认 S1 当前 manifest 中确有 transcript，但 S2 policy 仍只读取 digest-bound SEC CompanyFacts／Submissions，allowed forms 仍只有 10-K／10-Q。

## 4. 结果

- R1、R2、formal R3 的 SQLite SHA 完全相同：`d05b0cc8...c585`；
- S2 仍为 1,319 条 observation，DELL 390／MU 463／NVDA 466；
- private mart 只有 10-K 311 条、10-Q 1,008 条，非 SEC citation 为 0；
- transcript 进入 S1，不进入 S2 数值表；candidate／metric row 仍不授予 NumericFact；
- 最新财年 qrel 9/9、当前 interim qrel 15/15；所有 mutation 通过；
- formal R3 与 tracked v1.1 去除私有输出路径后的语义 digest 均为 `49e09985...f1924`；
- 全仓 `394 passed`，active baseline `131／8／10／0`，secret scan `6,747／0`；
- 模型、Provider、网络、新 Evidence 晋升均为 0。

## 5. 业务边界

这轮证明的是“法说不会篡夺财务数字权威”，不是“法说数字不能被分析”。模型仍可根据 reviewed transcript 讨论订单、积压、管理层目标和供需，但正式金额、期间、单位、同比关系和公式值必须引用 S2 NumericFact／NumericRelation。

仍未解决：AI server 产品收入—成本—利润桥、ASP/PVM、产品出货量、PIT 估值。公开资料没有时应返回 typed gap，不能因为五单元要写报告就拼装出来。

下一步可进入其余四个 RoleMethodPack／GraphContextPack 的五单元零调用资格化。
