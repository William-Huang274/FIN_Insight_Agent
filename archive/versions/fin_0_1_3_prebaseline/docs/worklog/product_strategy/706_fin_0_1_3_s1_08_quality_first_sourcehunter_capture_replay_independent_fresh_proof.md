# 706 — FIN 0.1.3 S1-08 质量优先 SourceHunter × Capture Replay 独立复证

日期：2026-08-08
阶段：`013-S1-08`
状态：`independent fresh zero-call proof pass / replacement live not authorized`

## 1. 复证对象

复证绑定 clean/synced commit `ee5ebf3b4773eae839f4646d21cec2f85a517925`。从同一 commit 制作两个独立 Git archive，各自在 fresh Python process 中挂载受限 R1 object store；受限内容只供测试按 manifest digest 核验，没有把 raw body、headers 或 runtime contact 写入 Git或输出。

## 2. 首次复证发现并修复的问题

首次 archive 运行的 46 项测试已通过，但 proof 文件重物化后的字节 SHA 与 archive 原文件不同。根因不是研究逻辑，而是 Windows `Path.write_text` 默认输出 CRLF，Git blob/archive 使用 LF；此前在同一工作区内连续执行得出的“byte-identical”结论不具跨 checkout 可移植性。

materializer 已固定 `newline="\n"`，并在新 commit 上重新执行完整双 archive 复证。该失败保留在本记录中，不把第一次结果改写为通过。

## 3. 最终结果

- worker A：`46 passed`；
- worker B：`46 passed`；
- 两个 worker 均逐一验证 restricted R1 request objects=`19/19`；
- 两个 worker 重物化 proof SHA 均为 `8c3a3129...edc1`，与仓库文件一致；
- canonical proof digest 均为 `37fea4fb...d1d3`；
- network/model/provider/retry/admission=`0/0/0/0/0`。

因此 `S1-08Q-A..G` 可记为 `independently proven`。这只关闭 deterministic engineering/replay portability，不证明 fresh live 来源覆盖、target-in-pool、ranking 或报告质量。

## 4. 下一步边界

下一项仅为 `S1-08Q-H` DELL R2 replacement authority decision。复证本身没有签发 admission，也没有授权或执行 DELL R2；MU/NVDA、ranking/BGE/Milvus 和 S3 继续保持未授权。
