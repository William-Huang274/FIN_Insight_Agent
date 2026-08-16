# 056 DELL 动态五单元容量 successor 零调用关闭

日期：2026-08-17

## 结果

`RC-S3-031` 的最早责任层已由 consumer policy v1.4 关闭。旧 v1.3、R1 authority、公开失败结果和私有 full result 均保持不可变；没有重跑 Planner、S1/S2、embedding 或模型。

新合同不把上限随手从 8 改成 10，而是把 `CELL::value_capture` 的数值视图显式绑定为五个允许指标（收入、毛利、毛利率、营业利润、营业利润率）乘以两个同口径期间。加载时会复算 `5 × 2 = 10`；运行时还检查本案 ticker、允许指标、唯一引用、每指标期间数和完整 comparable relation。

## R1 不可变回放

- predecessor plan digest：`f964f9fe814e1ea5d50c5286fb57b3cb00144514c2ee47cc9c770b7d662debaf`
- successor research input digest：`5a99ba2297a6d36c92c5b292341ea1b1599b7d852ffc7616ab75728ff8d2505c`
- 五单元 NumericFact：`0 / 12 / 10 / 10 / 3`
- 五个分析消息、五个严格交卷 Tool Schema、fake Judgment、结构化底稿、综合分析消息和综合 Tool Schema 均可编译。
- 10 条合法视图和重排通过；第 11 条、重复 ref、跨案例 ticker、缺 comparable relation 均 fail closed。
- 两个独立相关测试进程均为 `64 passed`；全仓为 `418 passed`。

正式结果：`configs/research/evals/fin_ia_0_1_3_s3_dell_dynamic_five_cell_capacity_successor_zero_call_result_v1_0.json`，result digest=`a9ccbf9974934fe42239c53468e67dc6969fa1a50b855b9310a642afec50a354`。

## 边界与下一步

该 proof 只关闭容量合同和 R1 prefix 的零调用可编译性，不授权自然 live。下一步仍须在同一个稳定 runner 中实现受约束 successor：复用 R1 已成功的 Planner 与当前 S1/S2，只给五个 cell 分析、五个严格交卷和两次综合共 12 个新节点；不得新建 attempt-specific runner、重跑 prefix 或发布产品。
