# 707 — FIN 0.1.3 S1-08Q-H DELL R2 replacement authority decision

日期：2026-08-08
阶段：`013-S1-08`
状态：`one DELL R2 approved / successor entrypoint required / not yet issuable`

## 1. 决定

clean/synced `bce4dad1...04fe` 上，scope=`S1_08Q_H_DELL_R2_replacement_authority_decision` 的 Project OS preflight 为 pass、open blocker=`0`。结合 A..G 双 archive 独立复证，Q-H 批准最多一份 DELL R2 fresh admission 和一次 exact-live。

预算保持计划原值：network `<=16`、每 query 最多 1 个文档、model/provider/retry=`0/0/0`、单次 timeout `<=30s`、整案 `<=300s`。不允许自动 R3。

## 2. 为什么没有直接签发

旧 runner 是 R1 entrypoint：

- 默认 `v1_0` 结果文件已经存在，重用会覆盖或被 exact-once guard 拒绝；
- admission 只绑定 catalog 和 implementation commit，没有绑定本次 Q-H decision 与独立 quality/replay proof；
- 继续使用旧 contract 会让“批准 replacement”只停留在聊天语义，无法由 Runtime fail closed。

因此本决定是 `approved but not currently issuable`。先实现一个最小 R2 successor admission/runner，绑定 decision、independent proof、v2 catalog、clean commit、R1 immutable terminal、新 result path/namespace 和 shared-ledger exact-once；旧 R1 入口与结果保持不变。

## 3. R2 验收与停止

R2 必须同时检查 target-in-pool、required-slot recall@8、currentness、diversity/typed exception、reconciliation、selected-pack coverage、false promotion、qualified-document yield 和全请求终态分类。只要 required evidence 仍不在候选池，就继续留在 S1-08 source coverage，不能先调 BGE/Milvus 或进入 S3。

本项 network/model/provider/retry/admission=`0/0/0/0/0`。MU/NVDA、ranking 和 DeepSeek 仍未授权。
