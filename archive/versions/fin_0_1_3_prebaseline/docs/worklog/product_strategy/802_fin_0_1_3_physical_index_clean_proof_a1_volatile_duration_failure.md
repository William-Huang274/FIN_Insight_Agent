# 802 — FIN 0.1.3 physical-index clean proof A1 volatile-duration failure

日期：2026-08-10

阶段：S1

状态：A1 terminal failed；0 model／0 vector write；A2 修复待提交

## 发生了什么

two-clean-archive A1 从 commit `3d39ef43...adad` 建立两份独立仓库副本，在断网环境下都成功重现同一个 implementation proof、同一个文件 SHA、11 个 mutation、同一个 directory fixture digest 和同一份零调用计数。但 orchestrator 最终仍报 `physical_index_v1_1_clean_archive_mismatch`，且没有写出正式 failure artifact。

随后进行一次不写业务状态的差异诊断，确认唯一不同字段是 pytest 摘要中的墙钟耗时：`1.44s` 与 `1.57s`。也就是说，代码和证明内容一致，比较器却把机器调度时间当成了证明身份。

## 处置

- A1 保持失败，不重复使用；补建的 failure record 明确标为 terminal 日志与零调用诊断的事后重建，不冒充原生 terminal artifact；
- comparator 改为只比较 `passed／skipped` 计数，不再比较 wall-clock duration；
- successor attempt 改为 A2；
- 已发布 microcanary 不重跑、不改写，A1/A2 均只读源文件并使用临时 archive；
- A2 通过前不签发 R2。

这是 clean-proof Harness 的确定性比较缺陷，不是 Milvus、BGE、语料或检索质量问题。
