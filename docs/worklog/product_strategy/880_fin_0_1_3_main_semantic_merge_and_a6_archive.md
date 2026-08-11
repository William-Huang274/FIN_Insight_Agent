# 880 — FIN 0.1.3 `main` 语义合并与 A6 历史归档

日期：2026-08-11

状态：完成；不等于产品基线冻结

## 结果

`origin/main` 的 20 条独有提交已逐条按 patch-equivalent、promote、current-superseded、archive-history 或 merge-topology 分类。合并提交 `b7263309fe808e4e3bb41b6d46318f35389d8d6a` 同时保留两个父提交，`origin/main` 已成为当前候选分支祖先。

仍有长期价值的 Workbench 路径策略、Runtime 配置／预检、维护、部署、Docker、前端 smoke、release-quality 报告和公开架构文档进入当前树。旧 A6 runner、resident worker、压力／Milvus 实验测试及其运行报告进入 `archive/code/pre_fin_0_1_3_main_a6` 与 `docs/archive/pre_fin_0_1_3_main_a6`，不进入活动导入图。

## 合并中发现并解决的问题

`main` 的 data-build command 已传入 `timeout_s`，当前 Job Runner 却没有该合同。没有删除 timeout 或抬高上限，而是把超时、进程树终止、并发槽和 `timed_out` terminal 统一进当前 Runner。Workbench 合并回归为 `66 passed`。

机器处置见：

- `configs/repository/fin_0_1_3_main_unique_semantic_merge_disposition_v1_0.json`
- `configs/repository/fin_0_1_3_archive_redirect_manifest_v1_0.json`

## 边界

该合并只解决 Git 祖先与有效语义的整合。它不证明 `/workspace`、旧消费者归零、三案业务验收、FIN 0.1.3 冻结或 release。

