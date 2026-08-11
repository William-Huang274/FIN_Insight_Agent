# 709 — FIN 0.1.3 S1-08 DELL R2 successor clean zero-call preflight

日期：2026-08-08
阶段：`013-S1-08`
状态：`clean preflight pass / one R2 eligible / admission not issued`

## 1. 证明结果

clean/synced commit `27d31315...c638` 上，Project OS 的 successor-proof scope 通过。随后从该 commit 建立 fresh Git archive、挂载受限 R1 capture object store，在 fresh Python process 中运行：

- S1-08 focused/related=`53 passed`；
- compileall=`pass`；
- R1 result 存在，R2 result 不存在；
- Runtime SHA=`2ecfd993...ec2a`；
- Runner SHA=`c81412f8...447f`；
- network/model/provider/retry/admission=`0/0/0/0/0`。

proof artifact 已成为 admission 的必需输入；proof 不存在、状态不通过、测试数不符或 source SHA 漂移时，issuance 在 ledger/network 前拒绝。

## 2. 新发现与有界处置

额外检查发现 Project OS preflight 对未登记的新 exact run-scope 字符串默认不会报错。这个问题属于共享治理层，不能靠给当前 blocker 换一个字符串假装修好。

本案已有更强的直接防线：R2 admission 必须绑定本 clean proof 与 exact Runtime/Runner SHA。因此 DELL R2 不需要等待一次跨项目的 scope registry 重构；通用问题作为共享治理债登记，在后续 S0/S5 工程处理中统一修复。

## 3. 下一步

当前只允许一次 DELL R2 issuance＋exact-live，预算仍为 `<=16 network / 1 doc per query / 0 model-provider-retry / 30s per call / 300s overall / no R3`。MU/NVDA、ranking 和 S3 仍未授权。
