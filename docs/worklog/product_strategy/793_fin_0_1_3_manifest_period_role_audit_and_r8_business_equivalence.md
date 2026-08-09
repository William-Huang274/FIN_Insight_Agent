# 793 — FIN 0.1.3 索引清单期间角色审计与 R8 业务等价收敛

日期：2026-08-10

阶段：S1／CandidateBundle-only sparse／dense manifest 前置对象审计

状态：R8 working-tree 零调用通过；clean independent proof 待执行

## 1. 为什么没有直接构建索引

R4 虽已 clean-reproof，但新 manifest 在编译 48 条留出案例 Metric 时发现 13 条没有 `period_role`：ASML 的季度销售、利润、毛利率、系统销量与期末现金共 10 条，ANET 的 Customer relationships useful-life／gross／net carrying amount 共 3 条。年份和单位正确仍不够；研究系统不能让模型猜一个数字是期间流量还是时点存量。因此 manifest R2 在写私有清单、BGE 或 Milvus 前 fail closed。

## 2. 同一 S1 内的有界 successor

本轮没有 ticker 特判，也没有调用 DeepSeek、BGE、reranker、Milvus、外网或 Evidence promotion。修复围绕通用表格时间坐标展开，并对每次正式物化后的 48 条业务对象做跨 Attempt 差异审计：

- R5：补齐 `Q1/Q2 year -> qtd`，`End-quarter／carrying amount／remaining useful life -> instant`；审计发现 ASML 两条 `Total net sales` 被旧纯年份表头判断误跳过，R5 失败保留；
- R6：恢复 ASML 销售额；审计发现 ANET 四列季度／半年毛利率被压成三条错位坐标，且 `Cash and cash equivalents / June 30, 2026` 被误标 `qtd`，R6 失败保留；
- R7：拆开纯年份表头与“年份＋Change”分组表头，并将裸日期列标为 `instant`；48 条候选与期间角色完整，但 ORCL 7 条年度指标的列名从 `Year Ended May 31, 2026` 退化成 `2026`，R7 失败保留；
- R8：分组年份判定忽略独立单位单元格，同时保留完整年度组标签。48 条入选对象与 R4 在公司／行／列／数值上逐条一致，13 条期间角色缺失归零。

## 3. R8 当前事实

- result digest：`6ca7ce22b86d5dbe347d02b3195fd6db50ff43488884cb830f1e44c8beff86b1`；
- ORCL／ASML／ANET projected bundles=`27／13／27`，Slots=`8／5／7`；
- 入选留出 Metric=`19／10／19=48`；
- period role=`14 instant／10 qtd／8 ytd／16 annual／0 missing`；
- R4↔R8 业务 identity 差异=`0／48`；
- unsafe numeric admission=`0`，mutations=`9／9`；
- network／Provider／model／embedding／rerank／Evidence=`0`。

ANET admitted table metrics 从 R4 的 470 变为 471，是通用表头修复后多恢复一条底层合法对象；最终冻结的 19 条索引候选与 R4 的业务 identity 完全一致，未靠扩大选择数量过门。

## 4. 下一步边界

先提交并推送 R8，再从两个 clean Git archive、两个 fresh process、三份 exact digest-bound capture 做独立复现。只有 clean proof 通过，manifest 才能改绑 R8，执行 93 条六案例 spec、15 类 mutation 与 fake sparse／fake dense 物化。真实 BGE／Milvus build、ranking、Evidence Pack、外源 residual supplement、DeepSeek 动态研究和报告验收仍未授权。
