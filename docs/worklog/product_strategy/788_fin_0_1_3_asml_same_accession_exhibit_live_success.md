# 788 — FIN 0.1.3 ASML 同 accession 详细附件 exact-live 成功

日期：2026-08-09

归属：FIN 0.1.3 / S1 / held-out generalization

状态：`completed_detailed_exhibit_acquired_three_case_reparse_pending`

## 1. exact-live 结果

clean／synced implementation commit=`5f97b1e540f521156dd26132b3b0999a42a3aae9`。唯一 admission 已 exact-once 消费并 terminal success。

- accession index 与 detailed exhibit 共 `2 network`；
- retry／model／provider／embedding／rerank／Evidence=`0`；
- index 返回两份 candidate，第一份 `pressreleasefinancialresul.htm` 已达到内容门禁，第二份未访问；
- parsed text=`12,303 chars`；
- research facets=`7/7`：bookings/backlog、EUV/High-NA、systems/units、installed base、gross margin、cash/working capital、outlook；
- terminal=`success / detailed_exhibit_captured`；
- result digest=`631ba5c0a094dbd884870d13d043bb51930d3012238ff59099a0d319f3a1552f`；
- public record digest=`3b534dbc78b9a0ddfc514049756b19c71199cf2eacc33256fe44cc78288f4382`。

## 2. 业务上获得了什么

详细附件不再只有 headline。保存正文包含 Q2 2026 净销售额／毛利率／净利润、Installed Base Management sales、新旧光刻系统销量、现金及短期投资、全年和下一季展望，也包含 AI 需求、客户扩产承诺、low-NA EUV 与 DUV immersion capacity 计划。它足以进入下一阶段的结构化对象和 Evidence Slot 评估，但仍不是自动 Evidence。

## 3. 新观察

SEC accession index 将 `.htm` candidate 的 `type` 标成 `text.gif`。因此后续 parser routing 不能把目录 MIME 字段当唯一权威，必须组合扩展名、实际 HTTP content type 和 parser 结果。这没有阻断本次 HTML 解析，但应纳入统一 reparse mutation。

## 4. 下一步边界

ASML 详细 source capture 已关闭。下一项不是继续抓网页，也不是立即建向量；而是使用同一 provider-neutral、table-preserving parser/object contract，把已保存的 ORCL 10-K、ASML Q2 exhibit、ANET 10-Q 一次性重解析，生成带 source／parent／table／row／column／period／currency／unit lineage 的 CandidateBundleV2，再跑三案与格式突变。只有这一步通过，才可结束留出案例泛化 gate 并讨论 sparse／dense rebuild。
