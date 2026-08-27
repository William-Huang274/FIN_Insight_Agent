# S1 工作记录 108：DELL 03B R10 program-level execution plan

日期：2026-08-27

状态：`same-stage non-overwriting R10 plan / implementation not started / no R10 policy, attempt or result`

## 1. 目标与不可变边界

R10 只修 R9 fresh audit 的两个 P2：开放词主体导致的跨事件 false complete，以及 ASP product↔price argument relation 未进入 completion/transformation。R9 的 implementation、policy、attempt、raw/private/public、result、manifest 与 audit 全部 immutable；R10 使用新 module/test/schema/policy/attempt/result path，不覆盖或重试 R9。

R10 不执行四条外源梯子，不运行 4B embedding/reranker，不做 CandidateDecision/Evidence、Pack/Readiness、S2、S3 或报告生成。R17 `FAIL_GATE_OPEN_NOT_ASSESSABLE` 与 human `0/16` 原样保留。

## 2. 顺序与依赖

`R10-00 audit freeze -> R10-01 structural event boundary -> R10-02 relational ASP completion -> R10-03 relational transformation seal -> R10-04 integration/tests/preview -> R10-05 implementation freeze -> R10-06 policy/formal/replay -> R10-07 fresh dual audit`

### R10-00：冻结 R9 审计与通过面

输入为工作记录 107、R9 fail audit、fixed manifest 及 immutable R9 raw execution。输出为两条攻击 fixture、R9 既有 negatives/positives/privacy controls、实际四层计数与 R17 14-file carry-forward binding。

验收：任一 predecessor SHA/size/digest 漂移立即停止；R10 implementation 阶段不创建 policy/attempt/result。

### R10-01：结构性开放词事件边界

责任：S1 predicate-frame segmentation。

规则：

1. coordinator 左侧已有 predicate、右侧第一 predicate 前存在非空 lexical prefix 时，按结构认定右侧有显式 frame owner，拆分事件；不得要求该 prefix 命中公司/实体枚举。
2. 右侧 predicate 从位置 0 开始时视为 shared-subject predicate continuation，不仅因出现第二 predicate 就盲拆。
3. 左侧无 predicate、共享 predicate 尚在右侧时保留 compound/shared subject；`Dell, NVIDIA, and Micron partnered` 必须仍为一个 frame。
4. `Acme`、`Supermicro`、任意未见专名、多词主体、`the reseller` 与带前置时间修饰的显式主体必须使用同一结构规则。
5. ambiguous boundary fail-close，不允许 sentence-wide completion 借 sibling roles。

输出：`FrameBoundaryDecision` 继续保留 exact coordinator、left/right predicate 与 structural right-prefix span/digest。新增 reason code 不依赖词表。

攻击验收：Acme、Supermicro、未见多词主体均 split 且 ASP partial；同 subject `Dell quoted ... and offered ...` 与 compound subject controls 不产生无理由 false split。

### R10-02：同组 product↔price completion

责任：S1 ASP argument compiler。

规则：

1. 先生成全部 `ArgumentGroupBinding`，再选择 completion roles。
2. 只有 `object_class=hardware`、`ambiguity=null`、`product_span!=null` 且 price 可解析的 group 可成为 ASP candidate。
3. product 与 price 必须由同一个 group 派生；record-global product 不再单独授予 `bounded_object`。
4. 合格 group 恰为一个才 complete；0 个为 typed missing，多个为 typed ambiguity，不猜 first/nearest/largest。
5. support/service/freight/financing/generic hardware price 保留为 context，不得借用邻近产品。

验收：审计 source/compiled 反例的 compiled side 必须 partial；合法 `XE9680 hardware $15` complete；`support $100 + XE9680 hardware $15` 仍选择 $15；generic hardware、两个 product-price group 与跨 group 产品均 fail-close。

### R10-03：relational semantic signature 与 transformation

责任：source→compiled provenance。

输出 normalized relation row，至少包含 `relation_type=hardware_product_price`、product normalized value、price normalized value、object class 与 attachment rule；span 只进入 representation/mapping，不进入 normalized identity。

该 relation 必须：

- 进入 `semantic_signature_digest`；
- 作为 source→compiled 可见 mapping，具有 source/compiled group span；
- 参与 loss/addition；
- 在 product/price 相同但 relation 不同或缺失时造成 semantic mismatch/binding rejection。

合法 bounded slice 允许 representation digest 不同、relational semantic digest 相同；非法 generic hardware 映射必须失败。

### R10-04：六 target integration、直接测试与零调用 preview

R10 建立新 predicate/transformation/compiler/runner/test paths，复用 R8 public validator，不修改 active consumer。冻结：

- 新 2-root attack family 与轻微 mutation；
- R9 3 no-comma、compound subject、4 scope、3 anchor、63 R7 negatives、8 R8 negatives、17 selected positives；
- 15 public attacks／3 valid controls；
- actual complete family transformation；
- R9 current counts 作为 bounded expectation，不作为硬编码 golden。

Preview 只读 immutable R9 raw execution，0 model/network/write。R9 preview 39.649s；R10 >70s warning/profile，>120s hard stop。任何 count/rank/transformation delta 必须逐 family 解释。

### R10-05：风险分层 implementation freeze

- T0：changed compile/static、JSON/JSONL、diff、secret、R9 immutable hash、R10 allowlist，目标 <30s。
- T1：R10 direct，硬停 90s。
- T2：R9+R10 adjacent，硬停 120s。
- T3：仅 compiler/runner/Project OS seam，硬停 180s。
- T4：仅 shared/active change、未知 import impact或 T1-T3 暴露跨域问题时触发。R10 预计新增隔离版本路径并复用 frozen public validator，因此默认不跑全仓。

### R10-06：新 policy、唯一 formal attempt 与 exact replay

Implementation clean commit/push 后才创建 v1.9 policy-only authority；唯一 attempt=`dell-rsq-03b-internal-chain-r10`。Formal 仍只允许 5 requests 的一个本地 Qwen3-Embedding-0.6B query batch；network/provider/generation/external/4B/reranker/Candidate/Evidence/promotion/closure 全 0。

继续执行 clean/synced、exact parent、single policy path、collision/disk、exclusive receipt、raw-before-compile、terminal failure、atomic private/public、same-attempt no retry 与 saved-formal exact byte replay。

### R10-07：fresh author-separated dual audit

新 fork-none reviewer 固定包只读审计：A identity/integrity；B open-vocabulary boundary；C relational completion/transformation/current artifacts/public；D R17 fixed bundle；E verdict。0 full pytest，只有具体 material suspicion 才允许最多一次 direct targeted test。任何 material finding 继续留在 03B。

## 3. 工程与模型输出质量标准

- false complete：新增开放词与 relational attack=0；所有 inherited negatives=0。
- positive recall：冻结 controls 不退化；任何保守拆分造成的真实 positive loss必须显式解释并修复。
- ASP complete：100% 具有一个 unique product-price hardware relation。
- transformation：complete source families 100% 有 accepted relational binding；relation loss/addition/mismatch 不得为 0 而实际缺边。
- current corpus：六 target 四层计数/rank delta 全解释；coverage/local repair/external/4B/reranker authority仍按真实输出，不硬编码。
- formal：5 requests、1 local batch、96/16、forbidden counters zero、exact replay bytes equal。

TokenBudgetBasis：preview 为 deterministic zero-model；formal 为 5-query one-batch local 0.6B embedding，required output 包括 raw capture、六 target relational frames/transforms、private/public seal。Cost/latency 是次要约束；任一 schema/identity/request 不完整则保存 failure receipt、同 attempt 不重试。R10 不建立 4B/reranker token authority。

## 4. 研报质量与下游恢复条件

R10 不修报告，但审计必须继续携带 R17：0 reader URL、0/18 claim passage binding、未绑定 14/9/4/10 crosswalk、WWC 0/6、72/36 duplication、02B 0/16、8D null。

只有 R10 fresh engineering PASS 后才恢复原顺序：四目标 03C source ladder -> changed candidate pool 上 0.6B/4B mixed shadow -> eligible 时 reranker -> CandidateDecision/Evidence/human admission -> Pack/Readiness -> units/share→ASP/mix→PVM→product profit/working capital -> 受影响 S3 -> non-overwriting report successor（claim-source URL/locator appendix、完整 crosswalk、WWC、去重）-> engineering/report/human 三重验收。

## 5. 当前 authority

允许：R10 新路径 implementation/tests、zero-call preview、风险分层门、implementation freeze 后的新 policy/formal/replay/audit。

明确 false：R10 implementation/policy/attempt/result/independent、03B independent、03C、4B、reranker、CandidateDecision、Evidence/NumericFact、Pack/Readiness、S2、S3、report successor、formal 8D、qualified-human、product/publication/release。
