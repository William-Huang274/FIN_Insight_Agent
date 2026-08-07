# 722｜FIN 0.1.3 S1-08 P2D：DELL R3 Exact-Live Issuance Authority Projection

日期：2026-08-08

阶段：`013-S1-08-P2D`

结论：首个零调用 P2D candidate 在投影验证时发现 transition-invariant test defect，已 `superseded_unconsumed`；v1.2 clean requalification 随后以 `85/85` 通过，最终 P2D v1.1 批准后续一个独立 DELL R3 Attempt。本项没有签发 admission 或执行 live。

## 核对结果

- Project OS：typed preflight v0.2、RunScopeRegistry v1.0，P2D scope=`pass / 0 blocker / 0 contract error`；
- S0-04G result SHA=`fb18617f...15583`；
- R3 successor proof v1.1 SHA=`7ae6f46f...bd2f1e`，source commit=`2f14684e`，clean archive/fresh process=`85/85`；
- superseded v1.0 candidate source=`0f20934e`，当时的 pre-transition Runtime/Runner SHA=`4e1dcc63...10c36 / 3f62ed6e...d6779`；
- 最终 v1.1 decision 与 v1.2 proof source=`4358edcb`，有效 R3 Runtime/Runner SHA=`b02ac0e9...9b81e / efbf908e...aa7b`，proof source 到当前受保护 Runtime 树漂移=`0`；
- runtime-only SEC contact=`configured + valid format`，值未写入命令输出或版本化产物；
- R3 result path 不存在；
- 本项 network/model/Provider/retry/formal admission/live=`0/0/0/0/0/0`。

## 投影时发现的缺陷

S0-04G production contract test 把“direct R3 在 P2D 前必须 blocked”写成永久断言。P2D 若合法把同一 typed scope 改为 one-attempt eligible，这条测试必然失败。该缺陷属于测试对状态迁移建模错误，不是 Runtime、SourceHunter、DeepSeek 或 Provider 问题。

v1.0 decision 因此不生效。修复只把断言改为“preflight 必须与 RC-P36-157 最新 typed projection 一致”，并要求 runner 改绑尚不存在的 successor proof v1.2。这样在 clean requalification 完成前，即使错误开放 scope，runner 也会因 proof 缺失而在 admission/网络前拒绝。

## 条件授权边界（v1.2 通过后才可生效）

后续最多：`1 admission / 1 exact-live / 16 network / 2 fetch per attempt / 1 unique accept per attempt / 0 model-provider-retry / 30 s per call / 300 s overall / no R4`。旧 R2 authority、namespace、runner 和结果禁止复用。

最终 P2D 仍必须是 issuance authority projection。后续执行必须是新的独立 Attempt，重新要求 clean/synced、proof/Runtime/runner/source SHA、contact 和 result-absent 检查全部通过，并在任何 DNS/网络前完成 exact-once ledger reservation。

若 R3 再次到达来源但 candidate ceiling 或 target-in-pool 失败，立即停止 live repair，进入 `S1-08-P3` Provider acquisition／Internal Alpha source-scope 决策；不允许 R4。ranking、MU/NVDA、DeepSeek、S3、Workbench 和 release 仍未授权。

## 最终复证与决定

- v1.2 source=`4358edcb`，predecessor v1.1 SHA=`7ae6f46f...bd2f1e`；
- clean Git archive＋fresh Python process=`85 passed / 0 failed / 0 skipped`；
- transition-aware production contract、旧 S1-08 exact-once、authority/source mutation 全部通过；
- R1/R2 restricted objects=`19/2`，输入未变；
- v1.2 proof SHA=`d3c3d668...bced680`、digest=`43fdf99e...2aa3c3`；
- final P2D v1.1 SHA=`f5583ac3...3aa94bb`、decision digest=`847b7cf9...c7634c7`；
- external/formal admission/live=`0/0/0`。

最终 P2D artifact 为 v1.1；v1.0 保留为 superseded-unconsumed。当时下一项为独立 `S1_08_V3_DELL_R3_EXACT_LIVE_ISSUANCE_AND_EXECUTION`；该权限现已由 worklog 723 所记录的唯一 R3 消费，不得复用。
