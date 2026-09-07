# S1 工作记录 112：DELL 03B R11 program-level execution plan

日期：2026-08-27

状态：`same-stage non-overwriting R11 plan / implementation not started / no R11 policy, attempt or result`

## 1. 目标、非目标与不可变前序

R11只修R10 fresh audit的两个P2：

1. clause ownership不能由“第一个有限predicate hint前有prefix”代替，必须分别证明shared-subject continuation和independent owner，并把无法证明的material coordination隔离；
2. product-price relation不能由同组共现或闭合排除词表推定，必须有可定位的affirmative attachment proof。

R10 implementation、policy、attempt、raw/private/public、result、fixed manifest与fresh fail audit全部immutable。R11使用新module/test/schema/policy/attempt/result path，不覆盖R10，不重试`dell-rsq-03b-internal-chain-r10`。

R11不是补源、4B或研报轮次。五条external ladder、mixed embedding/reranker、CandidateDecision、Evidence/NumericFact、Pack/Readiness、S2、S3与报告仍无authority；R17 `FAIL_GATE_OPEN_NOT_ASSESSABLE`和human `0/16`原样携带。

明确禁止的“修法”：只往company/owner列表加`Rose`，只往predicate列表加`cost`，或只往non-hardware列表加`maintenance/delivery fee/lease payment`。这些词可做测试fixture，但不能成为正确性的唯一来源。

## 2. 顺序与依赖图

`R11-00 failure freeze → R11-01 clause ownership proof → R11-02 affirmative price attachment proof → R11-03 proof-aware transformation → R11-04 compiler/runner/tests/preview → R11-05 implementation freeze → R11-06 policy/formal/replay → R11-07 fresh dual audit`

任一前置未通过，后续ticket不得开始；formal前必须先有clean/synced implementation与policy-only authority。

## 3. Tickets、输入输出与验收

### R11-00：前序失败与攻击族冻结

输入：R10 fixed manifest、fresh fail audit、immutable R10 raw/private/public、R9/R10 inherited controls和R17 14-file bundle。

输出：

- 两个exact finding ID与根因所有权；
- false-split、predicate-collision、unseen-predicate、co-presence relation攻击族；
- R10通过面与实际六target计数；
- R17 `0/18`、14/9/4/10、WWC 0/6、72/36、human 0/16 carry-forward。

验收：所有SHA/size/result_digest精确；任何漂移停止。implementation阶段不得创建policy/attempt/result。

### R11-01：ClauseOwnershipDecision v2

责任：S1 predicate-frame segmentation。

输入：coordinator左右surface、case-preserving aligned surface、normalized surface、全部predicate candidates、material role surfaces与前序frame state。

输出新的确定性状态：

- `non_clause_continuation`
- `shared_subject_proved`
- `independent_owner_proved`
- `ambiguous_material_boundary`

每个decision必须保存left predicate、leading adjunct span、shared-continuation proof、explicit-owner proof、chosen predicate span、ambiguity reason和digest。

规则：

1. 先识别并单独记录fronted adjunct，不把`in Q2`、`later in Q2`、`under the agreement`等功能性修饰表面当owner。adjunct识别可使用有限英语功能词/介词语法，但不得使用公司/实体内容词白名单。
2. shared subject只有在“去除adjunct后，右侧第一个clause head被证明为finite predicate/auxiliary，且不存在owner NP”时成立。
3. independent owner必须由owner span与其后predicate/clause evidence共同证明；不得只取first predicate match。必须评估predicate-token collision，例如proper-name surface `Rose Systems`与verb `rose`。
4. 未见predicate不能默认`no_split`。若右侧存在显式owner候选和material target surface，但finite predicate无法证明，状态为`ambiguous_material_boundary`，形成role隔离barrier；左右roles绝不union。
5. 左侧无predicate且共享predicate位于右侧的compound subject继续保留；真正predicate-offset-zero continuation不false split。
6. surface alignment若无法无损映射到normalized spans，fail closed为typed boundary ambiguity，不猜span。

对抗验收：

- R10三条adjunct false split均恢复一个complete supplier frame。
- `Rose Systems offered`、任意predicate-token collision owner、普通未知单/多词owner均隔离，不能跨事件complete。
- `cost`及至少一组自动生成的未见verb surface不能借左frame roles；若verb不能肯定识别，必须ambiguous barrier而非merge。
- 参数化modifier/preposition、owner长度、predicate碰撞与material surface mutation不得靠增加公司名修复。

正向验收：offset-zero `offered/delivered`、auxiliary+adverb continuation、compound/shared subjects、对象列表、bare discourse continuation不退化；若保守barrier导致real positive loss，必须给typed reason和family-level说明。

### R11-02：PriceAttachmentProof v1

责任：S1 ASP argument relation。

每个price group输出：

- `proof_state=affirmative|ambiguous|unproved`
- priced object span、specific product span、price span；
- connector或price-predicate span；
- competing nominal head/object span；
- proof type、normalized relation fields与proof digest。

规则：

1. 删除`single_typed_object_in_argument_group` admission fallback；co-presence永不授予relation。
2. affirmative relation只能来自span-local可遍历路径：object/product NP→price predicate/connector→price，或price→明确priced-object connector→包含specific product的hardware NP。
3. unique specific product必须位于priced object span内；record-global product、generic hardware、邻近产品不得借位。
4. 任一intervening nominal head、第二priced object、多个attachment candidate或无法证明connector均为ambiguous/unproved partial。
5. service/freight/financing等taxonomy只用于诊断，不能作为“未命中排除词即接受”的admission逻辑。
6. normalized relation保留product/price/object/proof type；representation spans与proof provenance进入mapping，不把span漂移误作semantic drift。

对抗验收：R10的contract amount、maintenance costing、delivery fee、lease payment全部partial；再用任意nonce nominal heads生成同形mutation，确保未见词也fail closed。generic/global/cross-group/multiple-product/multiple-relation继续拒绝。

正向验收：`XE9680 hardware for USD 15`、`USD 15 for XE9680 hardware`、`XE9680 hardware priced at USD 15`及明确purchase-price→product路径complete；support price + hardware price只选择有proof的hardware relation。

### R11-03：proof-aware semantic signature 与 transformation

责任：source→compiled provenance。

- ClauseOwnershipDecision state与PriceAttachmentProof normalized row进入semantic signature。
- `argument_relation.hardware_product_price`必须携带affirmative proof type；unproved relation不得出现在complete roles。
- source/compiled mapping保存owner/adjunct/predicate/object/product/connector/price spans与proof digest。
- 删除relation、改变priced object、把connector改绑nominal head、改变product/price/proof type必须产生loss/addition/mismatch并拒绝binding。
- 仅span/切片表示不同而normalized owner/relation/proof相同可保持semantic equal。

验收：所有complete source family 100%有accepted proof-aware binding；failed-complete、unbound-complete、compiled-complete-without-source均为0。partial diagnostic不计complete coverage。

### R11-04：compiler、runner、行为测试与zero-call preview

新建R11 predicate/transformation/compiler/runner/tests；复用frozen public validator，不改active consumer。新compiler必须精确绑定R10 policy/public/private/receipt/raw/fresh fail/fixed manifest、R17 audit与14-file bundle。

行为测试至少包括：

- audit exact reproductions；
- adjunct、owner/predicate collision、unknown verb、ambiguous barrier的参数化mutation；
- arbitrary nominal head的attachment mutation；
- inherited R9/R10 negatives/positives/scope/public controls；
- proof loss/addition/mismatch与public privacy；
- exact-once、raw-first、failure receipt、atomic pair、replay contract。

Preview只读immutable R10 raw，0 model/network/write。性能门沿用<70s warning、>120s hard stop。对六target source/compiled/union/final/rank、partial family、transformation row、external/4B/reranker eligibility做family-level differential；任何未解释delta停止，不用硬编码旧count掩盖正确变化。

### R11-05：风险分层implementation freeze

- T0：changed compile/pyflakes、JSON/JSONL、diff、secret、R10 immutable hashes、R11 import isolation与active baseline。
- T1：R11 direct，目标<90s。
- T2：R10+R11 adjacent，目标<120s。
- T3：Project OS、compiler/runner和S1 foundation seam，目标<180s。
- T4只在shared/active/runtime/dependency/config变化、影响范围无法证明或T1-T3暴露跨域失败时运行；隔离新版本路径默认不重复约20分钟全仓pytest。

必须记录测试数量、耗时、失败归属与T4 trigger，不得把跳过全仓写成“全仓通过”。

### R11-06：v2.0 policy、唯一formal与exact replay

implementation clean commit/push后，创建只改一个v2.0 policy文件的authority commit。唯一attempt=`dell-rsq-03b-internal-chain-r11`。

formal仍只允许5 requests、一个本地Qwen3-Embedding-0.6B query batch；network/provider/generation/external/4B/reranker/retry/mutation/promotion/closure=0。policy必须有task-specific `TokenBudgetBasis`，覆盖输入规模、proof schema、material risk、可比运行、推理profile与stop/truncation。

继续强制clean/synced、exact parent/path、minimum disk、exclusive receipt、raw-before-compile、redacted terminal failure、atomic private/public、same-attempt no retry和saved-formal canonical byte replay。

### R11-07：fresh作者分离工程＋R17双审计

新的fork-none reviewer只读审：

A. 34+ hash/topology/exact-once/route；
B. clause ownership proof与ambiguous barrier；
C. affirmative price attachment、transformation、current delta与public privacy；
D. R17 reader质量；
E. 分离verdict与authority。

默认0 targeted/full pytest；只有先陈述具体material suspicion才允许一次R11 direct。缺证据=`NOT_ASSESSABLE`，不是PASS。任一新P0/P1/P2继续留在03B；qualified-human不会由agent verdict自动变true。

## 4. 工程、模型节点与研究质量验收

### 工程

- 跨coordinator false-complete=0；ambiguous material boundary永不共享roles。
- shared-subject/compound positives无无理由退化。
- ASP complete 100%具有唯一affirmative PriceAttachmentProof。
- relation/ownership proof在source→compiled语义与provenance中无损。
- public threat-first与exact-once contracts不退化。

### 模型节点输出

R11 semantic admission是deterministic compiler，不把embedding相似度当relation或owner证据。preview为0模型；formal只有一次本地0.6B query embedding batch，embedding只排序。必须保存raw ranking并证明compiler delta来自R11规则而非模型漂移。R11不给4B/reranker authority。

### 研究与最终研报

R11若通过，只恢复执行五条external source ladder的资格，不等于补源完成。所有partial/ambiguous状态保留为typed gap，不得宣称public non-disclosure。

R17继续要求reader-visible citation/source appendix、claim→exact passage/title/issuer/date/period/locator/URL、完整14/9/4/10 crosswalk、operational WWC、去重/密度、formal 8D与qualified-human。R11工程PASS不能代替研报PASS。

## 5. 停止条件

出现以下任一项立即停在责任stage：

- adjunct仍被当owner，或unknown owner/predicate仍能跨事件union；
- 无affirmative attachment的price仍授予hardware relation；
- proof loss/addition/mismatch未拒绝transformation；
- inherited positive发生未解释loss；
- preview存在未解释count/rank/family delta或超过120s；
- policy/input/implementation/R17 binding、Git identity、request/rank/counter、raw-first、public privacy或replay不完整；
- formal attempt已消费后失败：只保留receipt/raw/terminal evidence，不重试同ID；
- fresh审计出现material finding。

## 6. R11通过后的恢复顺序

仅当fresh R11 engineering independent PASS：

`五条03C external ladders → Evidence admission/candidate pool重建 → 同池0.6B/4B mixed shadow → 存在eligible候选时reranker → CandidateDecision/qualified-human Evidence admission → Pack/Readiness → units/share→ASP/mix→PVM→产品利润/营运资金 → 受影响S3 → non-overwriting report successor → engineering/report/qualified-human三重验收`

在此之前，03B independent、03C、4B、reranker、G2/G3、S1/S2/S3、report quality、formal 8D、qualified-human、product/publication/release全部false。
