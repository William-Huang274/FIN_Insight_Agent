# 667 — FIN 0.1.3 S2-05 Experiment A DELL exact-live R1 首错终止

日期：2026-08-07

类型：`paid exact-live / raw model-only / first-failure audit`

状态：`terminal failed / no retry / zero-call disposition pending`

## 1. 本轮授权与执行

用户明确授权“签发并跑一次 exact live”。执行前完成 Project OS scoped preflight（open blockers 0）、runner preflight、35 项 focused contract、冻结 SHA、credential presence 和 clean/synced Git 复核。新增受限 issuer 并提交推送到 `a3f2edf8…c1989`；admission 只写 Git 忽略的 `.codex_runtime`，未保存凭据正文。

唯一 DELL admission digest=`de2ae5a…fe1d0`。shared ledger exact-once 消费后只发生一次 Lead Provider 调用；原始响应 capture-first 保存，随后本地 numeric surface 校验失败，campaign 立即停止。

## 2. 结果证据

- terminal=`terminal_failed_no_retry / lead_planning / experiment_a_unbound_numeric_surface`；
- calls/captures=`1/1`，transport attempts=`1`，finish reason=`stop`；
- usage=`2604/1162/3766`，估算 USD=`0.0035378`；
- Specialist/synthesis/Writer/Verifier=`0/0/0/0`；
- retry/fallback/rerun/MU/NVDA=`0/0/0/0/0`；
- business/correction/corrected/evaluator writes=`0/0/0/0`；
- terminal digest=`8f9729b0…9c0c`，receipt=`84029979…b86`；
- raw capture secret pattern scan=pass，raw 内容未进入 Git。

## 3. 根因与反思

Lead 已形成 6 个 DELL-specific 研究单元，并正确引用本案 Evidence/Gap；所以不能把这次结果概括成“没有研究能力”。失败包含两类问题：

1. Provider 违反冻结数字合同：自行提出 `>20%` backlog cancellation、`12 months`、`top 3`、`10%` memory-cost shock、`<3%` margin 等输入外阈值。
2. 项目 numeric gate 假阳性：`51.3B/24.4B` suffix 被正则截断，value 与 percent unit 分字段导致 `36.7%/55.5%` 无法对齐，且事实数字和研究情景阈值没有 typed distinction。

这说明当前 S2-05 合同过于刚性：金融事实数字必须继续硬保护，但 Lead 的“待验证情景阈值”需要独立 typed surface 和本地标注，不能与事实数字混为一谈。登记 `RC-P36-141`，归 S2 合同/本地 authority；模型的明示指令违约作为并存证据保留。

## 4. 后续边界

本次 admission 已消费，不得重用；失败 capture/terminal 不修改、不晋升。当前不签第二份 DELL admission，不启动 MU/NVDA，也不做 supervisor correction。

下一项仅为：

`FIN-0.1.3-013-S2-05-DELL-LEAD-NUMERIC-AUTHORITY-AND-PLANNING-THRESHOLD-ZERO-CALL-DISPOSITION`

该处置应先用本次 raw capture、本地 unit/suffix mutation 和事实数字/假设阈值分类证明结构方案，再决定是否申请一次 replacement exact-live；不能逐数字打补丁。
