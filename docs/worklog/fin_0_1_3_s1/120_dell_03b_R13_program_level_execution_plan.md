# S1 工作记录 120：DELL 03B R13 program-level 执行计划

日期：2026-08-28

状态：`plan frozen before implementation / same-stage non-overwriting successor only / no external or model authority`

## 1. 目标、非目标与版本边界

R13 是 FIN 0.1.3 / S1 / DELL-RSQ-03B 的同阶段、non-overwriting contract／attempt successor。它不是新产品版本，不是 R12 retry，也不允许覆盖 R12 attempt、raw、private/public result、reviewed-result commit、fixed manifest或失败审计。

R13 的唯一直接目标是关闭 fresh R12 双审计的四个边界：

1. private→public pre-discard summary reconciliation fail-open（P1）；
2. ownerless one-token unseen event head可跨事件借用 quotation predicate（P2）；
3. participial/relative product complement可绕过 governing price head（P2）；
4. fixed manifest changed paths被 lower-case（独立 envelope P2）。

R13 的非目标：

- 不执行五条 external source ladder；
- 不调用 0.6B、4B、reranker、generation model或 Provider；
- 不晋升 CandidateDecision、Evidence、NumericFact或 gap closure；
- 不重编 Pack/Readiness、S2、S3或 R17；
- 不宣称 Dell company ASP/units/mix、PVM、产品利润或营运资金桥已取得；
- 不代替 qualified-human或 formal 8D。

R13 author与fresh auditor都必须把工程资格、模型节点输出质量、研究证据质量和最终研报质量分开判定。任何一个通过不得自动签发其他层。

## 2. 冻结输入、输出与依赖图

### 2.1 immutable 输入

- R12 implementation=`e86d4a1d7a52911b25d31034d202ae29e6dfd314`；
- R12 authority=`e1aeefa3431dcf3e46cadc0f67472cee89f22422`；
- R12 reviewed result=`057eb98e7c48f4f6bb0e642e77003822bf084a02`；
- R12 fixed manifest=`3db8e535d68a6857ce066a28b5ef5a540eb66195`；
- R12 private/public digest=`5b478654...c1cd` / `7302201a...7fdc`；
- R12 raw successor digest=`eb4c50e8...57e5`，canonical raw execution SHA=`0e9e4456...f7458`；
- R12 machine audit digest=`d8bc5204...af9e`；
- 03A-R2 constant route registry及六 target identity；
- 1,888 source records、34,199 compiled objects、R11/R12 candidate-generation bindings；
- R17固定14-file report-quality bundle与 baseline `0/1/2/1`。

任何输入 SHA、result digest、commit/tree、route identity或 R12 raw equality漂移，R13立即停止。不得“顺便刷新”输入来让新实现通过。

### 2.2 计划输出

- `dell_report_predicate_frames_r13.py`：event-local ownership与 GoverningPriceHeadProof v3；
- `dell_report_frame_transformation_r13.py`：继承 R12 proof-aware mapping，并绑定新 event/head identity；
- `dell_report_internal_chain_ceiling_r13.py`：authoritative reconciliation surface与 deterministic compiler/public projector；
- `run_dell_report_internal_chain_ceiling_r13.py`：zero-new-call exact successor runner；
- 三组 R13 direct tests与相邻 R12/R13 regression；
- policy v2.2、唯一 attempt=`dell-rsq-03b-internal-chain-r13`、private/public result v2.2；
- case-correct non-overwriting fixed audit manifest；
- 作者 preview／exact execution工作记录、model-run记录与新的 fresh dual-audit结果。

### 2.3 依赖顺序

`R13-00 freeze → R13-01 reconciliation → R13-02 event ownership → R13-03 governing head → R13-04 transformation/compiler integration → R13-05 runner/manifest → R13-06 tests → R13-07 preview → R13-08 implementation/authority/formal/replay → R13-09 fresh dual audit`

R13-01～03均通过前，不得运行 full-corpus preview；R13-07通过前不得 commit authority；fresh R13 engineering independent PASS前不得进入03C。

## 3. 需求票与双重质量验收

### R13-00：Predecessor、审计与 pass-surface freeze

责任阶段：S1 / 03B author governance。

输入：R12四个固定提交、40-file manifest、fresh failure audit、R17 baseline和网络修复记录。

输出：

- R12 immutable SHA/digest/count/route/test surface snapshot；
- 三个实现 finding与一个 envelope finding的 exact reproduction／静态路径；
- `PASS_BOUNDED` surface 与 `FAIL general contract` surface明确分列；
- 03C/4B/reranker/Evidence/S2/S3/report authority全为 false。

工程验收：40/40 bundle身份、15/15 inputs、37/37 bindings、R12 raw SHA与Git topology保持精确。任何 drift立即停止。

模型输出质量验收：证明所有 R13变更发生在 frozen candidate union/rank之后；若 candidate-generation input、query、embedding/vector或 rank需要改变，zero-model basis失效，必须停下重做 authority计划。

研报质量验收：原样保留 R17 `0/18` citation、14/9/4/10/4 crosswalk、WWC `0/6`、72/36、human `0/16`；不得写“工程修复等于研报改善”。

### R13-01：AuthoritativeSemanticReconciliationSurface v1

责任阶段：S1 / 03B private persistence与 public trust boundary。

#### 输入

- 每个 target的 source packages、compiled packages、union/final packages；
- transformation binding rows；
- coverage gaps；
- route identity；
- 全 corpus clause-decision与 governing-head diagnostics。

#### 输出合同

每 target保存一个 `private_semantic_reconciliation_surface`，包含：

1. `source_package_rows` 与 `compiled_package_rows`：所有参与 transformation／coverage权威判断的完整持久化 packages；
2. `source_scan_receipt_rows` 与 `compiled_scan_receipt_rows`：对全 corpus diagnostics使用的紧凑逐 package receipt。每行至少绑定 target ID、source-record或compiled-object ID、classification、completeness state、clause-decision count map、governing-head partial flag、package semantic digest与 row digest；不保存 raw text、URL、query template或 private locator；
3. `coverage_gap_rows`；
4. `transformation_binding_rows`；
5. `derived_summary`；
6. 各 row-set的排序规则、count、canonical digest与整体 reconciliation digest。

如果逐 package compact receipts令 private artifact超出预设 hard limit，允许的唯一替代不是丢行，而是先证明某类 full-corpus diagnostic不参与任何 downstream authority，然后从权威 summary/public projection中删除或显式降级为 `diagnostic_non_authoritative_replay_only`。不得保留“权威但不可复算”的 aggregate。

#### 唯一派生函数

实现一个纯 deterministic函数，从持久化 surface重算完整 summary。compile时先生成 surface再派生 summary；public projection在删除任何 private field前重调同一函数，并要求：

- exact key set；
- exact scalar/list/map value；
- exact sorted IDs；
- exact canonical row-set digest；
- exact whole-summary digest。

材料 summary至少包括：

- binding/accepted/failed counts与 set digest；
- unbound all/complete/partial family IDs与 counts；
- compiled-complete-without-source IDs与 count；
- failed-complete IDs与 count；
- proof-rebind failure IDs与 count；
- source/compiled governing-head partial IDs与 counts；
- source/compiled clause ownership decision maps；
- complete transformation coverage per target与 boolean；
- non-vacuous/vacuous coverage标记；
- route-required与 exact route identity reconciliation。

禁止继续使用“非负整数／mapping／bool类型正确”替代语义重算。

#### 行为验收

参数化 mutation逐一修改：每个 scalar、list element、map key/count、binding row、package receipt、row-set digest、whole summary digest、coverage boolean与 route ID。每项即使重新签发 private self digest，也必须在 public projection前 typed fail closed。

正向验收：未修改的 real R12 raw→R13 compile可以被重算两次且 dict/canonical bytes完全相同；公开结果仍不包含 private rows、raw text、URL、locator或 secret-like payload。

研究质量：`complete coverage 6/6`必须同时标出 non-vacuous仅 supplier 1/6；五个 source-complete=0不得展示成“证据完整”。

停止条件：任一 material summary只能从不可持久化运行时状态获得；任一重签 summary mutation可通过；compact receipt与实际 package ID无法一一对账；private size或runtime超过 hard limit且没有经审计的非权威降级方案。

### R13-02：EventLocalClauseOwnershipDecision v4

责任阶段：S1 predicate-frame segmentation、event scope与 role isolation。

#### 核心更正

R12只回答“coordinator右侧是否有独立 owner”，但审计反例说明：即使 owner由左侧共享，右侧新 finite event也不能借用左侧 quotation predicate。R13必须把 subject ownership与 event/predicate ownership分开。

每个 frame新增或明确：

- `event_scope_id`；
- `predicate_head_span`、predicate proof type与 lexical/morphological class；
- `subject_ownership_state=explicit|shared_proved|ambiguous`；
- `predicate_continuity_state=same_event|new_event|ambiguous`；
- `role_inheritance_allowlist`；
- coordinator boundary与 proof digest。

#### 规则

1. 任何已证明或形态上有限的右 event head，在 material product/price/quantity/relationship surface前出现时，建立新 event scope；可以继承被证明的共享 subject，但不得继承左 event的 quotation/sale/supply predicate、price、product或其他 material roles。
2. one-token unknown head不再需要显式 right owner。`-ed/-ing/-s`、auxiliary chain、copular/finite structure与 case-preserving alignment可提供 bounded event-head evidence；命中失败但 material right event仍可能存在时，必须 ambiguous split，不能默认 no_split。
3. object list／compound product list不得被当成新 event。material surface从 coordinator后立即开始、或前缀仅为 determiner/adjective/quantity且没有 finite-head证据时，可保持同 event，但必须由 positive structural proof支持。
4. known predicate的 shared-subject coordination也建立 predicate-local event scope；若某 target需要跨两个 event组成关系，只能由显式 target contract连接，不能靠一条扁平 role union。
5. explicit right owner、lowercase owner、predicate-token collision、fronted adjunct与 compound subject继续沿用 R12已通过边界；R13不能修一个反例而退化这些路径。
6. 无损 surface alignment失败时 fail closed；embedding、词向量或相似度不能决定 ownership。

#### 对抗与正向验收

必须拒绝或保持 partial：

- `Dell quoted support for USD 150 and repaired PowerEdge XE9680 hardware for USD 15.`；
- `... and refurbished/reconfigured/assembled/serviced PowerEdge ...`；
- 大小写、标点、auxiliary、adverb与 ownerless mutations；
- 已冻结的 `eBay Systems wugged`、`vanadium labs zorps`、lowercase `rose systems offered`。

必须保留正确语义：

- `Dell quoted PowerEdge XE9680 hardware and XE9712 hardware for USD 15.`对象列表；
- `Dell quoted a new PowerEdge XE9680 hardware configuration for USD 15.`；
- `NVIDIA provides GPUs and ships them to Dell.`中 subject共享但 predicate-local roles不串；supplier target如需两谓词必须经显式 relation contract完成；
- R12 fronted adjunct positives与 explicit-owner negatives。

任何新增 complete/partial delta都必须给出 event-scope与family级原因。

研究／研报质量：所有 attribution必须绑定 event-local assertion owner与 predicate；Writer不得把同句另一事件的价格或产品拼成 Dell报价。

停止条件：任何跨 event quotation role union；case-dependent verdict；unknown one-token event仍落入无条件 no_split；object-list正例大面积退化且无 typed ambiguity解释；以闭集整句/公司名单作为唯一修复。

### R13-03：ComplementGraphGoverningPriceHeadProof v3

责任阶段：S1 ASP argument relation。

#### 输入与结构

输入为 event-local quotation/sale frame、argument group、nominal spans、product/hardware spans、price spans、connector spans与 complement edges。Complement edge至少覆盖：

- prepositional：`for/of/on`；
- participial：`covering/including/bundling/containing/comprising/featuring`；
- bounded relative：`that/which includes|contains|covers|bundles`；
- 并列与标点 barrier。

输出：governing head span/class、edge chain、priced object、product、price、connector、competing heads、proof state/type、event scope与 normalized proof digest。

#### 规则

1. 先从 price沿 connector回溯唯一 priced head，再判断 product/hardware是否为该 head；不得从最近 `hardware at price`反推最高 head。
2. 若 product NP由更高 nominal head通过 complement edge支配，默认 ambiguous；只有更高 head本身被结构证明为 hardware/product/configuration price head，才允许 affirmative。
3. service/freight/lease/financing/support/contract词表只用于解释。任何 nonce head的同构结构都必须得到相同 fail-closed verdict。
4. direct `product hardware for price`、`price for product hardware`、`product priced at price`、explicit purchase/configuration price保持 affirmative。
5. multiple heads/objects/prices、跨 argument group或跨 event scope一律 partial。

对抗测试：maintenance service `covering/including/bundling`、delivery arrangement、lease vehicle、support plan与至少五个 nonce heads；大小写、单复数、修饰词、relative-clause变体全部拒绝。

正向测试：四类 direct price path、明确 `configuration price for PowerEdge...`、hardware bundle本身包含GPU但由 bundle price明确治理的正例；每个正例必须有唯一 digest-stable proof。

研究质量：即使 bounded configuration price通过，也只表示某一配置观察，不得自动升级为 company-wide ASP、期间均值或 mix。

停止条件：participial/relative edge仍绕过；安全性依赖列举 service名；direct price正例不能稳定重现；多头关系仍被最近邻覆盖。

### R13-04：Proof-aware transformation与 compiler integration v5

责任阶段：S1 source→compiled provenance与 target compiler。

1. transformation semantic identity必须加入 `event_scope_id`、predicate continuity、governing complement edge chain与 head proof digest。
2. source/compiled event数量、predicate ownership、head/edge、product、price、connector任一删除、新增或改绑，必须产生 typed loss/addition/ambiguity/proof-rebind并拒绝。
3. 纯 offset改变只有在 role surfaces、event topology、connector class与 normalized proof完全相同且 offset map可复证时才接受。
4. R12 route identity、candidate-generation bindings、persisted raw rere读、exact-once、privacy guards全部继承并通过相邻回归。
5. author comparison必须比较完整 reconciliation digest、event/head decision counts、route IDs、complete-family IDs、proof-rebind IDs及所有 count/rank变化。

验收：R12 `for→at`、price/product/predicate mutations继续 typed reject；新增 event flattening与 participial-edge loss mutations必须 reject。actual complete source families保持100% source-bound；任何变化逐 family解释。

### R13-05：Zero-new-call runner、case-correct manifest与 identity seal

责任阶段：S1 execution governance与 S0 audit envelope。

Runner：

- 新 attempt ID，receipt exclusive-create；
- 精确验证 R12 raw successor、candidate-generation equivalence与 frozen inputs；
- 先以 `xb`落 R13 raw reuse successor、flush/fsync、重读验证，再 compile；
- private/public原子发布；同 ID失败不重试；terminal只保存 typed safe receipt；
- saved replay从落盘 raw重编，要求 private dict、canonical bytes、result digest精确；
- R13新增 embedding/model/provider/generation/network/external/4B/reranker/retry/mutation/promotion/closure全0。

Manifest：

- v1.0错误 manifest保持 immutable；
- 新 manifest从 Git case-preserving输出取 authoritative path；commit/hash比较值可 lower-case，path显示值不可 lower-case；
- strict case-sensitive exact compare `git diff-tree`；
- 冻结 `current_context_pack.zh-CN.md`、`README.md`、`R13`与 uppercase model-run path；
- manifest self digest、raw SHA、byte size、Git topology、policy inputs、implementation bindings与 report bundle逐项绑定。

停止条件：same-ID输出已存在、raw/commit/tree/policy/path case漂移、Git proxy listener不可用且需push、private超出磁盘安全门、任一调用计数非0或manifest仅casefold通过。

### R13-06：直接测试、分层回归与性能门

分层策略：

- T0：changed py_compile、pyflakes、new JSON/JSONL、diff、R12 immutable hash、R13 import isolation、active baseline；
- T1：R13 direct，目标 `<90s`；
- T2：R12+R13 adjacent，目标 `<150s`；
- T3：Project OS、compiler/runner与S1 foundation seam，目标 `<180s`；
- T4只有 shared/active runtime、dependency、pytest config变化，影响范围无法证明，或T1～T3暴露跨域故障才运行。

测试矩阵：

- reconciliation每个 summary字段、row-set与digest mutation；
- ownerless event one-token、inflection、case、punctuation、auxiliary/adverb；
- object-list／shared-subject／explicit-owner正反 controls；
- participial/relative complement与nonce head；
- transformation event/head/connector rebind；
- route true→false→true与伪/空/local/cross-target IDs；
- exact-once/raw-first/persisted-reread/failure receipt/atomic pair/saved replay；
- public URL/path/secret/high-entropy/fixed-point decode；
- case-sensitive manifest changed paths。

每门记录 test count、duration、failure owner与T4 trigger。未跑T4不得写“全仓通过”。secret scan只在 freeze或敏感输出变化时跑，不在每次 patch重复。

### R13-07：Immutable-R12-raw zero-call full-corpus preview

输入：R12 raw successor、1,888 source、34,199 objects，0 model/network/formal/write。

必须输出：

- 6 target source/compiled/union/final/rank；
- event-scope counts与旧/新 clause decisions；
- governing complement edge/head diagnostics；
- reconciliation row counts/digests、summary exact recomputation两次；
- transformation total/accepted/failed、complete/partial/unbound/compiled-only；
- route IDs与 external-required；
- private artifact estimated bytes、peak memory与runtime；
- 对 R12每个 count/family/rank delta的 source/family解释。

性能：`<70s`正常，`70–120s` warning并解释，`>120s` hard stop。private estimated size设 warning/hard gate，hard gate前不得创建 attempt；阈值必须在实现记录中按当前58.3MB predecessor、磁盘余量与atomic pair所需空间定量冻结，不能事后放宽。

质量停止条件：任何 false complete、unexplained delta、non-vacuous complete family失联、compiled-only complete、unreconcilable summary、route omission、public leakage、runtime/size hard stop。

### R13-08：Implementation freeze、v2.2 authority、唯一 attempt与 replay

1. T0～T3与preview通过后，clean commit/push冻结 implementation/tree；
2. 只创建一份 v2.2 policy，authority commit只改该文件并push；
3. policy绑定 R12 audit、raw、result、route、source/object、execution/runtime与 R13 implementation；
4. `TokenBudgetBasis`逐项记录 purpose、input scale、required outputs、schema burden、materiality/quality risk、comparable run、reasoning profile、stop/truncation；本任务 model/embedding/token=0；
5. clean/synced、exact parent/path、outputs absent、disk preflight后消费唯一 R13 attempt；
6. exact saved replay；
7. non-overwriting reviewed-result commit；
8. case-correct fixed manifest commit。

Attempt失败时保留 receipt/raw/terminal证据，禁止同 ID retry。失败不自动创建产品版本；根因仍留03B。

### R13-09：Fresh作者分离工程＋R17双审计

另启全新 `fork_turns=none` reviewer；不得复用发现R12问题的reviewer充当“clean reviewer”。只读、0写入/commit/push/formal/network/model/external，默认0 pytest；只有先报告具体怀疑才允许一个最小 probe。

审计域：

A. case-correct manifest、Git topology、policy、raw/exact-once/privacy；
B. authoritative reconciliation逐字段重算与mutation；
C. event-local ownership、ownerless finite head、object list、governing complement graph、transformation；
D. stored-result count/family/rank、route identity与vacuous coverage解释；
E. R17 reader citation、crosswalk、WWC、S2 numeric bridge、density、bilingual、8D、human；
F. engineering、report-quality、qualified-human三个分离 verdict。

任一新 P0/P1/P2：R13 immutable保留、03B independent=false、所有下游继续false。缺证据写 `NOT_ASSESSABLE`，不能写 PASS。

## 4. R13验收矩阵

| 层 | 必须满足 | 不能声称 |
|---|---|---|
| 工程身份 | R12 immutable；R13 exact new identity；case-sensitive manifest；zero-new-call exact replay | commit/hash通过不等于语义通过 |
| 信任边界 | 每个材料摘要从持久化权威行完整重算；重签mutation fail closed | self digest或类型检查不能替代reconciliation |
| 语义 | event-local predicate/roles；ownerless finite event隔离；participial/relative governing head fail closed；direct positives保留 | 加几个关键词/整句fixture不等于general contract |
| 模型节点 | candidate generation完全未变，R13模型/embedding=0且有task-specific预算依据 | 不调用模型不等于输出质量自动通过 |
| Evidence | complete family source-bound；五target 0 complete明确为local ceiling；route只是计划合同 | 0结果不等于公开信息缺口，配置价不等于company ASP |
| 研报 | R17失败指标逐项carry；fresh reviewer单独判定 | R13工程PASS不等于信源补齐、S2或研报PASS |
| 人工/产品 | 16项qualified-human decision与formal 8D仍独立需要 | agent不能代签human或release |

## 5. 全局停止条件

出现任一项立即停在责任阶段：

- frozen R12 input、raw、route、Git或audit digest漂移；
- 任一材料摘要不可从持久化surface精确复算；
- re-signed summary/package/digest mutation仍通过；
- ownerless新event仍可借quotation predicate，或object-list正例无理由退化；
- participial/relative governing head仍被最近hardware span覆盖；
- source/compiled event/head topology改绑无typed flag；
- target count/family/rank delta无法解释；
- private estimated size、memory或preview runtime超 hard gate；
- exact attempt identity已消费后失败；
- manifest path只casefold相等；
- fresh audit出现任一material finding。

## 6. Fresh R13通过后的完整恢复顺序

只有 fresh R13 engineering independent PASS，才恢复：

1. 以五个 exact route contract创建独立03C authority；
2. 执行五条真实 external source ladder，逐 route保留 capture/reachability/exhaustion/failed receipt；
3. 重新生成 changed candidate pool与 gap crosswalk；
4. 在同一候选集运行0.6B baseline＋可装入8GB GPU的4-bit 4B embedding shadow，记录GPU峰值、吞吐、召回增益与失败；不得把4B直接替代精确/BM25；
5. 重排器保留：只有同池候选数量和排序歧义达到预定义eligibility才调用，比较 reranker前后 recall/precision与material hit；
6. CandidateDecision与Evidence admission；人审每条来源、命题、时间、单位、适用范围与反证；
7. 重编 Pack/Readiness与14-gap crosswalk，真实不可补部分才可进入proved information boundary；
8. S2严格按 `units/share→ASP/mix→PVM→产品利润→营运资金`；缺分母或口径不得硬算；
9. 只跑受影响S3动态单元；
10. 生成不覆盖R17的新报告，提供reader-readable citation/source appendix、逐Claim locator/URL、完整crosswalk、operational WWC、去重与双语等价；
11. 分别进行工程审计、研报八维质量审计与qualified-human 16项验收；
12. 三者全部通过后才讨论产品/publication/release。

当前本计划只授权R13同阶段实现、分层测试、零调用preview、在author gates通过后的新identity formal/replay和fresh audit。其他全部继续false。
