# 716 — FIN 0.1.3 S1-08 v3 DELL R3 fresh-live authority decision

日期：2026-08-08
阶段：`013-S1-08-P2`
状态：`conditionally approved / successor entrypoint required / not issuable`

## 1. 本轮目标与权限

本轮只执行零调用的 `S1_08_V3_DELL_FRESH_LIVE_AUTHORITY_DECISION`。它判断 v3 是否值得获得一次新的 DELL live 机会，但不实现 runner、不签发 admission、不访问来源，也不启动 ranking、MU/NVDA、DeepSeek 或 S3。

scoped Project OS preflight 为 `pass / open blocker 0`。工作树起点为 clean/synced `cfdfbd4843d35780da1470baa931cffc3dc06451`。运行时仅检查 `FINSIGHT_SEC_CONTACT_EMAIL` 是否存在，结果为 present；未读取、打印、哈希或持久化其值，未来签发前仍必须重新核验。

## 2. 决策输入

不可变 DELL R2 已 exact-once 消费并完整 terminalize：`16` 次网络调用、`0` 模型/Provider/retry，只接受 `1` 份 unique DELL 8-K，customer/supply/market 三类关键槽为 gap，target-in-pool=`0`，ranking 未准入。该结果证明的是 operational candidate ceiling 失败，不是 DeepSeek、reranker 或 terminal retention 失败。

v3 对 R2 暴露的首因完成了直接结构修复：

- official RSS/Atom/robots/sitemap 与同域 bounded discovery；
- SEC `20-F/6-K`；
- typed publication-date adjudication；
- subject/owner/claim-direction 关系约束；
- nested-customer 在 fetch 前拒绝；
- 五 slot round-robin 与 `4/4/5/0+3` reservation；
- 每 attempt 最多 `2 fetch / 1 unique accept`；
- canonical source、role binding 和 local snapshot 分账。

这些变更已在 clean `a3f15fa2` 上由两个 Git archive、两个 fresh process 各 `60 passed` 独立复现。不过 official feed/sitemap/bounded-domain 仍只有 replay proof，没有 fresh live proof；external broad search 仍无运营 Provider。

## 3. 决策结论

结论为 `approved_successor_entrypoint_required_before_issuance`：允许未来建立并复证至多一个 DELL R3 successor，理由是一次受限 live 是区分“v3 官方路线真实可达”与“仍缺运营 Provider 覆盖”的最小必要证据。

这不是当前可签发权限。旧 R2 runner 明确绑定 v2 catalog、R2 schema/namespace/result path，而 R2 result 已存在且 authority 已消费；复用旧 runner 会用旧执行面冒充 v3 证明。因此必须先新建 R3-only admission/terminal/namespace/result，并精确绑定本 decision、R2 terminal/evaluation、v3 independent proof、v3 catalog、source SHA 和 clean commit。

未来 R3 上限保持：`1 admission / 1 exact-live / <=16 network / 0 model-provider-retry / 30s per call / 300s overall / no R4`。不因 R2 失败增加调用数，也不放宽 target-in-pool、required-slot recall、currentness、selected coverage、false-promotion 和 qualified unique-document yield `>=0.5`。

## 4. 停止条件

- successor binding、source SHA、clean proof 或 runtime contact 任一失败：不签发；
- R3 exact-once，不自动 retry、relaunch、patch-and-resume、replay 或 R4；
- 若 R3 再次 candidate ceiling/target-in-pool 失败：停止 live，进入 P3 provider acquisition 或 Internal Alpha source-scope 决策；
- target-in-pool 未过时，不调 ranking/BGE/Milvus/top-k；
- `external_site_search` 未单独准入前，不把 official-domain bounded search 宣称为 broad Web search。

## 5. 本轮产物与下一步

机器决定：

`configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_fresh_live_authority_decision_v1_0.json`

合同测试：

`tests/contract/test_fin_0_1_3_s1_08_v3_dell_r3_fresh_live_authority_decision.py`

本轮 observed network/model/provider/retry/admission/live=`0/0/0/0/0/0`。唯一下一项为：

`S1_08_V3_DELL_R3_SUCCESSOR_ENTRYPOINT_ZERO_CALL_IMPLEMENTATION`

该下一项仍是零调用工程绑定；不能跳过它直接签发或执行 R3。
