# 727｜FIN 0.1.3 S1-08 P3A A2 通过与 SearXNG 诊断路线重排

日期：2026-08-08

阶段：`013-S1-08`

状态：P3A independently proven；SearXNG diagnostic adapter 零调用实现已获授权，生产 Provider 与新 product-live 未授权。

## P3A A2 结果

只修改 clean-proof runner 的 declared-input assembly，把既有受治理 R1 request objects、R2 content captures 与 R3 capture store 同时按 digest 注入。v4 Runtime、16-call ceiling、quality gate、R3 和 A1 均未修改。

- source commit：`5e9726c2537386d2bc06a843ec43bfc5bf5d72fd`；
- clean Git archive／fresh process：`2/2`；
- 每 worker：`92 passed / 0 failed / 0 skipped`；
- restricted inputs：R1/R2/R3=`19/2/39`；
- before/after：byte-stable；
- network/model/provider/retry/admission/live=`0/0/0/0/0/0`；
- proof result：`configs/releases/fin_ia_0_1_3_s1_08_p3a_protected_document_fetch_cache_clean_zero_call_proof_v1_1.json`；
- result digest：`cdede8663276df743f795aa0d57411051c662104fb2ce7c41c64ca1ebb1e8deb`；
- file SHA-256：`16ca7cb0a2e343f6eef05cbd111f2ece9f20e227c22b05ee06973aa58012c696`。

A1 的 `90/1/1` 继续 immutable failed。P3A 通过只证明项目内调度／缓存不变量可复现，不证明外网召回、target-in-pool 或产品研究质量。

## 为什么重排下一步

原计划把所有 Provider 工作推迟到 P3B。这个边界对生产采购是正确的，但把低成本诊断也一起推迟，会继续让“免费官方域能力上限”和“broad search Provider 增益”混在一起。用户明确批准先做开源诊断路线，再申请正式 API。

因此保留生产边界，同时前移一个独立实验：自建 SearXNG，按 provider-neutral 合同输出 locator candidates，用同一 query/evaluator 低成本比较多个上游搜索引擎。它不能晋升 Evidence，不能写金融事实，也不能成为自动 fallback。

## 新执行顺序

1. 实现并零调用证明 SearXNG diagnostic adapter、本地容器入口、capture/normalization/typed failure/budget/no-promotion；
2. adapter 通过后，若本机 self-hosted instance operational，执行独立的 bounded diagnostic network baseline；若 Docker daemon 不可用，保留可复现入口并诚实记录 deployment blocker；
3. 用户取得商业 API 后，以同一 query set、schema、预算和 evaluator 做 apples-to-apples comparison；
4. 再由 Owner 决定 production Provider、Internal Alpha source claim、no-R4 和新的 DELL product-live。

本机当前有 Docker CLI/Compose，但 Docker Desktop Linux daemon 未运行。不会使用公共 SearXNG 实例绕过自建边界。
