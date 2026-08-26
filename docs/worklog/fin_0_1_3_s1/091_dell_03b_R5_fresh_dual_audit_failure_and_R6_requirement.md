# S1 工作记录 091：DELL 03B R5 fresh dual-audit FAIL 与 R6 要求

日期：2026-08-26

状态：`R5 immutable execution/integrity/actual-route observations retained / general semantic-anchor-privacy qualification FAIL / same-stage non-overwriting R6 required`

## 1. Fresh reviewer 与总判定

全新的 fork-none、作者分离、只读 reviewer 对 immutable result commit `8fe2caafede9eec451bde7c6326847a0e5996e2b` 完成工程、语义、route、privacy 与 R17 研报质量双审计。Reviewer 没有写文件、联网、调用 Provider/生成模型/embedding/4B/reranker/external capture，也没有委派其他 agent。

Overall=`FAIL`：

- R5 新 finding：`P0/P1/P2/P3=0/0/3/0`。
- R17 open finding：`0/1/2/1`。
- combined：`0/1/5/1`。
- R5 integrity=`PASS`；route=`PASS_BOUNDED_FOR_ACTUAL_IMMUTABLE_EXECUTION`；engineering/semantic/privacy general qualification=`FAIL`；03B independent pass=false。

审计 artifact：

`configs/audits/fin_ia_0_1_3_commit_8fe2caaf_dell_03b_r5_fresh_dual_audit_fail_v1_0.json`

self-digest=`56fc24881da2d814bce4daf7caac94df886e4c43be308b2105a07faaf48d7499`。

## 2. 通过并保留的 immutable R5 事实

- Git topology、19/19 bound inputs、12/12 implementation bindings、policy/public/private/receipt self-digest、private link、raw execution SHA 全部独立通过。
- 5 个唯一 request；每个精确 96 union／16 final；1 个本地 0.6B batch；所有 network/provider/generation/external/4B/reranker/retry/mutation/promotion/closure counter 为 0。
- Reviewer 使用保存 raw receipt 做零模型全量 deterministic recompile，1,888 sources／34,199 objects，耗时 `151.949s`；private 与 public 均逐字段 exact equal。
- 当前 immutable public 无 model text、material sentence、HTTP(S)、`www.`、source URL 或 private package key；没有实际泄漏。
- 当前 actual target result 可保留：ASP=`2/2/2/2` rank 15；supplier=`2/2/2/1` rank 2；capacity/yield/HBM/units 均 0；coverage gaps=0；external candidate=4、reranker candidate=1、4B candidate=0。所有 public-information-gap 与 downstream authority 仍 false。

这些是 bounded observations，不是通用 classifier/projector qualification，也不授予后续 route。

## 3. R5-P2-1：clause-wide polarity、direction、modality 与 ASP affirmation

现有 sentence-wide regex 仍可误收：

- `NVIDIA failed to supply Dell`；
- capacity/HBM `was rejected for Dell`；
- yield `should/anticipated/estimated` 与 `prototype-line`；
- `Dell disclosed NVIDIA shipped`、未枚举 counterparty、`Dell refuted reports it shipped`；
- ASP `did not quote`／`denied quoting`。

也会误杀真实正例：有效 supplier/allocation/observed-yield 命题后接无关否定、`unavailable` 或 next-process target 从句时，整句被降级。

根因登记为 `RC-S1-079`。R6 必须从整句正则升级为 clause-scoped typed proposition：subject、predicate、object、polarity、modality、process、reported-speech direction 同槽绑定；ASP 必须增加 affirmative quote/price polarity。上述 attacks 与 positive controls 全部冻结。

## 4. R5-P2-2：product-code 与 fiscal-year typed anchor 不等价

- `H100/H-100` 正确不产生 number anchor，但 `H/100/H 100` 产生 `number:100`；
- `XE9680/XE-9680` 不产生裸数字，但 `XE/9680` 产生 `number:9680`；
- `FY26` 与 `FY2026` 分别归一为 26 与 2026。

因此语义等价 source/object 可产生 false materialization gap。当前六 target coverage=0 经 reviewer 复核仍成立，但一般性 route 可被误导。

根因登记为 `RC-S1-080`。R6 必须规范化已知 product entity 的 hyphen/slash/whitespace 形式并排除实体内部数字，将两位/四位 fiscal year 归一到同一 canonical year；材料性数字最好绑定 proposition slot，而不是收集句中全部数字。

## 5. R5-P2-3：public projector denylist 不 fail-close

R5 public projector 复制整个 private target row，只删除五个已知字段；注入 `private_secret_payload` 或 `source_locator=www...` 可原样进入 public。当前 immutable public 实际干净，但未来 private schema 扩展可能静默泄漏。

根因登记为 `RC-S0-105`。R6 必须从显式、递归 public allowlist 构造输出，拒绝未知字段、raw/private text、HTTP(S)/`www.`、本地路径与 locator，并冻结 injected-secret attacks。

## 6. R17 研报质量仍未通过

- P1：39 surfaces、93 claim-ref occurrences／42 unique、18 EV、10 gaps、32 presentation refs 在 repo 内可解析；但 rendered report 只有 opaque `EV::`，0 reader URL，缺 title/publisher/date/period/section-page/locator source appendix。
- P2：R17 早于 crosswalk v1.2，未绑定或消费 14 pack gaps／9 dynamic gaps／4 writer groups／10 writer refs／4 S2 bridges。
- P2：六项 WWC 均无 metric/direction/window/threshold/owner/evidence route/action，operational=`0/6`，method parameter frozen count=0。
- P3：20,574 chars 中 Facts 71 次、unique displayed fact strings 32；inventory 与 AI revenue/orders/margin/WWC 有明显重复。
- 正向边界保留：内部 refs 全解析，24 numeric presentations、9 numeric relations、4 bounded presentations 和 margin bridge 可重算；FCF 为 deterministic non-GAAP，PVM/ASP/units/product attribution 保持 null。
- 02B 仍为 8 requests、16 human-required items、4 blocked requests／8 blocked items、qualified-human decisions=`0`；reviewer 不是 qualified human；formal 8D score 仍无效。

R17 successor 必须与 S1 R6 分开：先满足 L1/L2、crosswalk、typed WWC、reader citations/source appendix 和 human prerequisites，不得把 R17 问题混进 R6 classifier 修复。

## 7. 下一合法动作

1. R5 不覆盖、不重试，所有 bytes 与 actual observations 保留。
2. 在同一 03B owning stage 开 non-overwriting R6：新 module/runner/tests/schema/policy/attempt/result path；修复 `RC-S1-079`、`RC-S1-080`、`RC-S0-105`。
3. R6 在新 exact attempt 前必须先过 adversarial/positive controls、full-corpus zero-call preview、全仓门、clean implementation/policy commit topology。
4. R6 immutable result 仍需另一个 fresh fork-none、作者分离、只读 dual audit。
5. 03C、4B、reranker、Evidence/NumericFact admission、gap closure、S2、R17 successor、产品、publication、release 全部继续 false。
