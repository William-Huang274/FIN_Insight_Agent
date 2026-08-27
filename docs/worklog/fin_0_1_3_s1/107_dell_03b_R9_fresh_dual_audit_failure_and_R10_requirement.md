# S1 工作记录 107：DELL 03B R9 fresh dual-audit 失败与 R10 要求

日期：2026-08-27

状态：`R9 immutable integrity PASS_BOUNDED / R9 engineering FAIL P2×2 / R17 report quality FAIL_GATE / same-stage non-overwriting R10 required`

## 1. 审计对象与约束

审计对象为 immutable result commit `6e2189de23c7b86e9370b344501e96cea10a0e5f`，authority=`2c6d7ba526157533770c40ebdbc2f9392c00cc48`，implementation=`3b608ca63631f7c6783443eeb55cae85d111c6b1`，fixed manifest commit=`a93b2abb1269c65ea10094a28e1991c0b77cdf56`。

Fresh fork-none、作者分离 reviewer 严格只读：0 writes/commit/push，0 network/provider/model/formal，0 targeted/full pytest。Manifest 的 20 个 engineering 文件和 14 个 R17 文件全部 SHA/size 通过；manifest SHA=`4b99aa5b...db9e`，self digest=`b69f8171...f16c`。

## 2. 可以保留的 R9 事实

- Git parent/tree/changed-path、12 bound inputs、25 implementation bindings、8 bound result digests、receipt/raw/private/public 互链与 exact public reprojection全部通过。
- 5 requests、1 个本地 Qwen3-Embedding-0.6B batch、338 union、80 final；每 request 96/16 unique contiguous，12 类 forbidden counters 全 0。
- 实际 ASP=`1/1/1/1 rank2`，supplier=`3/3/2/1 rank2`，capacity/yield/HBM/units=`0/0/0/0`；这些只保留为 bounded actual observations。
- 1,622 条 transformation 中 1,360 accepted／262 failed；当前 complete family 没有 unbound/failed-complete。Public validator、15/15 attacks、3/3 controls 通过。

这些事实证明 R9 执行完整、当前 artifact 可重放；不能证明一般 predicate-frame 与 relational anchor 资格。

## 3. 新 P2-1：开放词主体绕过事件边界

`_FRAME_RIGHT_SUBJECT` 是封闭枚举。右侧显式主体不在枚举中时，即使左右各有 predicate，也会 `no_split`。

反例：

`Dell quoted support for USD 150 and Acme offered PowerEdge XE9680 hardware for USD 15.`

实际为 `right_subject_span=null`、一个 frame、`complete_bounded_target_package`，错误联合 Dell/quoted 与 Acme 的 product/price。换成 `Supermicro` 同样失败；`the reseller` 只因命中枚举才正确 split。

R10 必须使用结构性 right-prefix/predicate ownership，不再让公司或实体词表决定是否拆事件。封闭词表只可帮助解释，不能授予 completion。

## 4. 新 P2-2：product↔price 关系未进入 completion 与 transformation

R9 虽然在 argument group 中计算 `product_span`，ASP completion 却分别使用 record-global product 和唯一 hardware price；semantic signature 与 transformation 只比较 role/scope bag。

源文 `Dell offered PowerEdge XE9680 hardware for USD 15.` 与编译文 `Dell offered PowerEdge XE9680 and support for USD 100 plus hardware for USD 15.` 都被判 complete。后者 `$15` hardware group 的 `product_span=null`，但 semantic digest 相等、binding accepted、loss/addition/ambiguity 均为空，因而可把 generic hardware price 错证成 XE9680 price。

R10 必须从同一个 unique unambiguous hardware argument group 派生 product 与 price；该 group 必须具有非空 product span。标准化 product-price relation 必须进入 semantic signature，并在 source→compiled 映射中可见。

## 5. R17 研报质量仍失败

R17 14 文件相对 R8 audit 完全不变，因此既有 open=`0/1/2/1` 原样 carry forward，并在当前 fixed bundle 内重新验证：

- reader 21,118 chars、25 `[Sources:]`、59 EV occurrence／18 unique、0 URL，无 citation/source appendix；
- 18/18 EV 只能回到内部 authority rows，0/18 有 title、exact passage、page/section locator 或 URL；底层 pack 的 55/55 passage/URL 完整，但 report EV 与 pack EV 交集为 0，claim semantic support=`NOT_ASSESSABLE`；
- crosswalk 为 14 pack／9 dynamic／4 groups／10 writer refs／4 S2 bridges，digest 未进入 R17；price-in、scenario/sensitivity、supplier-capacity read-through、valuation basis 未呈现；
- WWC 0/6 完整操作化，method parameters 0 frozen／2 pending；Facts 72 occurrence／36 unique；
- 02B 8 requests／18 items／16 human-required／0 decisions；formal 8D score=null。

## 6. 当前门禁与下一合法动作

R9 new severity=`0/0/2/0`，engineering=`FAIL`，R9 independent=false，03B independent=false。R9 bytes、attempt 与 result 不覆盖、不重试。

下一合法动作是先写 R10 program-level plan，再在同一 S1/03B 建立 non-overwriting successor；完成 direct/adjacent tests、zero-call full-corpus preview、新 implementation/policy/new attempt/exact replay 与另一名 fresh reviewer。其前 03C、4B、reranker、CandidateDecision、Evidence/NumericFact、Pack/Readiness、S2、S3、R17 successor、qualified-human、product/publication/release 均 false。

完整机器可读结论见 `configs/audits/fin_ia_0_1_3_commit_6e2189de_dell_03b_r9_fresh_dual_audit_fail_v1_0.json`。
