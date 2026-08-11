# 879 — FIN 0.1.3 严格主线重定基验收与迁移程序

日期：2026-08-11

## Owner 目标

本轮不能再交付一套半成品并把旧债继续留在活动树。终点必须是清晰代码结构、清晰项目结构、可追溯历史归档、唯一研究主线，并最终合并及推送 `main`。

## 关键新证据

- 当前候选分支相对 merge-base 有 510 个独有提交；`origin/main` 有 20 个独有提交。
- read-only merge probe 在 Workbench、检索、Agent Runtime、测试与文档等核心文件产生冲突；最后盲合并不可接受。
- 四套产品表面与运维能力仍混在同一 frontend/backend composition root。
- 第一条版本中立 Evidence Pack API 已真实通过三案，但 typed Case、UI consumer 和旧消费者归零均未完成。

## 主动纠偏

将 `main` 语义整合从最后一步提前到第一阶段。否则先在分支重构、最后再解决 20 个独有提交，会重新引入旧表面或用 blanket 冲突选择丢失有效能力。每个独有 patch 必须被归为 patch-equivalent、current-superseded、promote、archive-history 或 reject-with-reason。

## 已冻结的完成定义

- `/workspace` 唯一研究主入口；`/operations` 为独立运维入口。
- DELL／MU／NVDA 有 typed CaseSubject 和 digest-bound CasePackBinding。
- UI 真实消费 current Case/Evidence API，三案业务含义、边界、引用与 gap 可读。
- 活动 Workbench/Runtime 不再 import P36、FIN 0.1.2、`r53_r60` 或 attempt runner。
- 旧消费者归零后才移动；所有移动通过 redirect manifest 追踪。
- 私有数据只挂载，不复制；活动测试、前后端、API、UI、secret 与 zero-ref 全通过。
- PRD／TECH／Project OS／代码图一致；冻结后合并 main 并在 main 工作树复证。

## 当前动作与边界

已写入 PRD 16.21、TECH_00A 9、严格迁移程序和 machine acceptance。尚未归档、改路由、调用模型、复制数据或合并 main。下一项先形成 `origin/main` 20 个独有提交的逐项语义 disposition，再吸收仍有效能力。
