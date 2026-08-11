# 715 — FIN 0.1.3 S1-08 v3 clean independent zero-call proof

日期：2026-08-08
阶段：`013-S1-08-P1`
状态：`independent deterministic proof pass / fresh-live authority decision pending`

## 1. 本轮目标与权限

本轮只执行 `S1_08_V3_MATURE_COMPONENT_RELATIONSHIP_BUDGET_CLEAN_INDEPENDENT_ZERO_CALL_PROOF`。目标是在 clean Git archive 与 fresh Python process 中独立复现 v3 依赖、R1/R2 immutable inputs、日期裁决、三案例 fake/mutation 和完整 S1-08 contract。网络、模型、Provider、retry、admission、live、ranking 与业务晋升均未授权。

Project OS scoped preflight 在实现前通过。proof runner 先作为独立提交固定并推送，正式证明只对 clean/synced commit 执行，避免使用未提交脚本证明自身。

## 2. A1 失败与处置

第一次正式 proof 绑定 commit `2cdb09ce7fd62e01ae2994248298ad1347eec690`。worker 1 结果为 `59 passed / 1 failed`：runner 已注入两份 R2 Microsoft content captures，却漏掉完整 S1-08 suite 仍要求的 19 份 R1 request objects，故 restricted-manifest contract 在 clean archive 中 fail closed。

该失败归 `proof input assembly`，不是 SourceHunter Runtime、成熟组件或金融日期逻辑回归。A1 没有生成成功 result、没有访问网络、没有创建 admission，也没有修改业务 Runtime。修复只将 19 份 R1 request objects 按 manifest/digest 只读复制到 disposable archive；raw body/header 不进入 Git 或公开结果。

## 3. 最终独立复证结果

最终 proof 绑定 clean/synced commit `a3f15fa29f53a6e4537a04a96b9481d7a314b8ee`：

- clean Git archive：`2`；
- disposable root / fresh Python process：`2 / 2`；
- 每个 worker：`60 passed / 0 failed / 0 skipped`；
- 依赖：`feedparser 6.0.12 / Trafilatura 2.1.0 / lxml 6.1.1`；
- restricted R1 request objects：每边 `19/19`；
- restricted R2 content captures：每边 `2/2`；
- R2 event/release 日期：`2026-07-29 / 2026-07-29`；
- press-release `2026-06-30`：同时以正文 reporting period 与 Trafilatura inferred date 两条候选拒绝，未晋升为发布日期；
- DELL/MU/NVDA round-robin full-fake、relationship/date mutation、nested-customer pre-fetch reject、document-fetch ceiling：全部复现；
- 两个 normalized worker output 完全一致，SHA=`fc99e9cfe347fddc74ccc198166d7a05561aa9954e88195df621f96023070b70`；
- restricted inputs 前后 manifest 一致，network/model/provider/retry/admission/live=`0/0/0/0/0/0`。

正式机器结果：

`configs/releases/fin_ia_0_1_3_s1_08_v3_clean_independent_zero_call_proof_result_v1_0.json`

## 4. 能宣称与不能宣称

可以宣称：S1-08 v3 deterministic engineering 从 working-tree engineering pass 提升为 `independently_proven`；依赖身份、R1/R2 immutable input binding、日期/关系/预算/分账和三案例 mutation 在 clean checkout 可重复。

仍不能宣称：

- official feed/sitemap/bounded-domain route 已 fresh-live 可达；
- DELL required target 已进入候选池；
- target-in-pool、required-slot recall、ranking 或 selected Evidence Pack 已通过；
- broad external search 已有运营 Provider；
- MU/NVDA transfer、DeepSeek Research、内容质量或 release 已通过。

## 5. 下一步

唯一下一项是零调用：

`S1_08_V3_DELL_FRESH_LIVE_AUTHORITY_DECISION`

该 decision 只核对 immutable R2 terminal、clean proof、当前 provider availability、exact-once successor、预算和停止规则。它不在同一步签发或执行 live。即使 decision 批准，也只能在后续独立步骤签发至多一次 DELL successor；不得自动进入 R4、ranking、MU/NVDA 或 S3。

收口后的 Project OS transition probes 已验证：新 decision scope=`pass`；已完成的旧 proof scope=`blocked`；`additional_S1_08_live_attempts` 同时被 RC-P36-156/157 阻断。故本轮没有因更新 allowlist 而间接放开 live。
