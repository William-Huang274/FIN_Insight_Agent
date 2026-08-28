# S1 工作记录 124：DELL 03B R14 program-level 架构执行计划

日期：2026-08-28
状态：`revision 1 after fresh plan audit PLAN_FAIL / implementation not started / awaiting fresh read-only re-review / no policy / no attempt / no downstream authority`

## 1. 目标、非目标与版本边界

R14 仍属于 FIN 0.1.3 的同一个 S1／03B internal-chain qualification stage，不是产品版本、S阶段或完整迭代升级。R13 implementation／policy／attempt／raw／private／public／result／manifest与fresh failure audit全部保持不可变。

R14只解决fresh R13双审计确认的三个一般合同根因：

1. package population只由自身与derived summary相互证明，缺少独立输入population authority（P1）；
2. flat frame没有event-local role ownership，known／unknown predicate、owner、period、price、product、quantity可跨事件拼成complete（P2）；
3. governing price head依赖connector枚举，结构同构的未枚举higher nominal head可被误作hardware ASP（P2）。

R14明确不做：

- 不执行03C外源、0.6B／4B、reranker、CandidateDecision、Evidence admission、Pack／Readiness、S2、S3或Writer；
- 不改写R17，不生成新报告，不补reader citations；
- 不把supplier candidate晋升为Evidence；
- 不宣告public／commercial／private information boundary；
- 不新增付费模型或parser模型；
- 不通过向verb、connector、service词表追加例子来宣称根因关闭；
- 不因某个测试失败自动创建R15。

R14的成功含义仅为：在冻结输入和确定性零模型compiler上，03B engineering general contract获得独立通过。它不等于S1整体、S2、S3、研报、产品或发布通过。

## 2. 已接受的关键设计决定

### 2.1 Population authority与output commitment职责分离，不把同源output称为独立truth oracle

R14必须同时存在：

1. `InputPopulationManifest`：classifier-independent population authority；它只由冻结source／object／target contract重建expected keyset，不含classifier outcome；
2. `PreFormalDecisionCommitment`：same-compiler precommitted output；它由冻结implementation＋manifest＋冻结输入的zero-call preview生成，绑定每个target／lane的outcome vector root和detail graph root。

前者证明“应处理哪些输入”。后者只证明“被审查实现当时承诺了什么确定性输出”，不是独立语义真值。语义独立性来自versioned structural grammar、独立oracle／decoder、implementation freeze后才生成的reviewer holdout，以及author-separated审查。formal result必须从source／object重新执行compiler后再与commitment比较；不得把preview output作为extraction／classification输入。

#### 2.1.1 非自引用、不可换签的`I → B → A → P`线性freeze topology

本计划与R13 failure audit先形成治理基线commit `G`。每个pre-formal cycle必须满足：

1. `I`（implementation freeze）：parent=`G`或上一个FAIL audit commit；只允许R14 parser／schema／target contract／manifest builder与独立validator／compiler／runner／projector／tests及machine-readable requirement manifest路径变化。禁止preview、policy、attempt或result。`I`记录exact commit、tree、parent和changed-path allowlist；
2. `B`（pre-formal bundle freeze）：parent=`I`；只允许public-safe manifest commitment、preview commitment、decision-vector／property／mutation receipts和preview worklog。`PreFormalDecisionCommitment`绑定`I`，不绑定自身`B`，因此不存在commit/tree自引用；
3. `A`（author-separated audit freeze）：parent=`B`；只允许fresh pre-formal audit receipt和必要的append-only治理状态。receipt必须绑定`I`、`B`、二者tree／parent／changed paths、Manifest／Commitment SHA＋digest、property／mutation roots和reviewer fresh holdout root；
4. `P`（policy-only authority）：parent=`A`；只允许一个新policy路径变化。policy必须绑定exact `I/B/A`、PASS audit receipt、Manifest／Commitment、所有frozen input和TokenBudgetBasis。任何额外path变化都拒绝。

若`A`为FAIL，不得创建`P`。后续修复仍属于R14，但必须从该FAIL audit之后创建新`I′ → B′ → A′`，旧`I/B/A`保持不可变；只有最新`A′=PASS`才可创建唯一`P`。这阻止审查Commitment A后在policy前偷偷换成Commitment B，也阻止因失败惯性创建R15。

完整private `InputPopulationManifest`、decision details和source locators保留在ignored private workbench；`B`只提交其SHA／self-digest／counts／roots和不含原文、私有locator、长ID的public-safe commitment。review packet可在本机只读访问private artifact，但tracked audit不得泄漏内容。

### 2.2 采用紧凑、全量decision vector，不重复216,522个长ID

冻结输入规模为：

- source records=`1,888`；
- canonical source families=`1,862`；
- compiled objects=`34,199`；
- targets=`6`；
- source＋compiled logical decisions=`(1,888+34,199)×6=216,522`。

为避免再次生成一个包含21万条重复长ID的巨大JSON：

- manifest只保存一次canonical input order、ID、input digest和occurrence map；
- 每个target／lane保存定长`DecisionVectorReceipt`，cell按manifest index对齐，outcome code为`C/P/N/E`（complete／partial／not-target／typed-error）；
- `C/P/E`和任何需说明的`N`另有content-addressed sparse detail receipt；
- vector长度、canonical index、outcome counts、cell-root、detail-root与manifest-root共同建立双射；
- 逻辑上每个expected key恰好一个decision cell，物理上不重复长ID。

这不是省略not-target receipt；not-target由定长vector中的`N`显式表示。删除、重复、移位、跨target替换或改变cell都必须改变root并被policy commitment拒绝。

### 2.3 采用确定性保守proof parser，不增加外部NLP模型

当前依赖不含可冻结的英语dependency parser model。为避免在03B根因修复中引入新的模型、下载、GPU、许可和不可重复性风险，R14采用内部确定性`conservative_event_proof_v1`：

- 只在结构与typed span足以肯定证明时给complete；
- coordinator／标点／右侧material surface出现而无法证明是object list或同一event时，降级partial；
- shared subject可以产生显式inheritance edge，但每个predicate仍是独立event；
- unknown predicate或unknown attachment不猜测语义，只保留candidate＋typed limitation；
- price attachment采用少量肯定式结构证明；未满足肯定式proof的paraphrase不是靠denylist拒绝，而是因“unique priced head/path unproved”降级partial。

R14不会宣称完整英语dependency parsing。若保守parser使真实正例大量退化且无法用结构性proof恢复，hard stop要求更换parser／IR职责或交human，而不是继续堆词表。

#### 2.3.1 `StructuralProofGrammar v1`必须先成为机器可读合同

`conservative_event_proof_v1`不是原则性名称。R14-00必须先冻结machine-readable `StructuralProofGrammar v1`及独立schema validator；implementation只能消费该合同中的rule IDs，不得在classifier内另写隐式真值规则。合同至少包含：

- 原文span统一为Unicode code-point半开区间`[start,end)`；proof normalization仅做NFKC、大小写折叠和冻结的标点同类映射，raw text与raw span永不改写；
- deterministic tokenization、sentence boundary、hard clause boundary、soft coordinator、parenthetical和quotation范围；abbreviation/function-word资源有版本和digest；
- event candidate、nominal chunk、role edge、subject inheritance、temporal edge、price path的rule ID、premises、conclusion、precedence、conflict handling与canonical proof bytes；
- 每个rule输出`PROVED / AMBIGUOUS / UNSUPPORTED / MALFORMED`之一，并保存premise span／edge IDs；无rule或冲突不得默认为`PROVED`；
- graph canonical order为`(document span, node type, rule ID, normalized identity, digest)`；相同输入必须byte-exact。

最小可执行rule set与优先级固定为：

1. `G00-MALFORMED`：仅处理manifest预注册坏输入；优先级最高；
2. `G10-SENTENCE`／`G11-HARD-CLAUSE`：句末及分号等hard boundary绝不共享material role；
3. `G20-EXPLICIT-EVENT`：显式finite／auxiliary predicate span产生独立event candidate；target ontology只标注semantic type，不决定scope存在；
4. `G21-COORD-EVENT`：coordinator右侧若有finite／auxiliary／morphological predicate candidate、新subject或无法排除predicate的nonce head，产生新event或`AMBIGUOUS` event barrier；
5. `G22-OBJECT-LIST`：只有同typed-role并列项之间不存在finite／auxiliary/predicate candidate、新subject或hard boundary时，才证明no-new-event object list；证明失败不把右侧material mention并回左event；
6. `G23-SUBJECT-INHERIT`：只把显式subject的actor edge继承到协调event，禁止复制predicate、object、price、quantity、period、recipient或owner；
7. `G30-ROLE-LOCAL`／`G31-TEMPORAL-LOCAL`：material mention只有通过有向proof edge才能属于event；span邻近、整句共现和shared subject不能替代edge；
8. `G40-NOMINAL-HEAD`：以chunk／complement／relative／participial／apposition／coordination结构建立有向nominal graph；unknown head/link保留节点并标`UNSUPPORTED`，不得被跳过；
9. `G50-PRICE-DIRECT`／`G51-PRICE-NOMINAL`／`G52-HARDWARE-BUNDLE`：只接受第4.4节列出的肯定式price topology；connector文本只记录provenance；
10. `G90-CONFLICT`：多event owner、多head、多price、跨scope role、互斥proof或未闭合path一律`AMBIGUOUS`，优先于任何complete rule。

状态到decision outcome唯一映射：没有target candidate=`N`；有target candidate且全部required topology=`PROVED`才可`C`；candidate存在但任一required proof为`AMBIGUOUS/UNSUPPORTED`或缺失=`P`；只有manifest预注册的malformed-input key/code可为`E`。未捕获parser/compiler异常属于terminal execution failure，不能批量写成`E`。

#### 2.3.2 Deterministic parse procedure（不得由实现自行改写）

1. `TOKENIZE`：按raw Unicode code point扫描，依优先级产生`MONEY`（currency symbol/code＋number）、`PERCENT`、`NUMBER`、`WORD`（Unicode letter/digit，内部连字符/撇号仅在两侧均为word时并入）、`PUNCT`和`WHITESPACE`；proof token保存raw span、raw bytes digest与normalized form。最长匹配，优先级冲突即`MALFORMED`；
2. `SCOPE`：段落换行、`.?!;:—`在非括号/引号内建立hard boundary；comma/coordinator为soft boundary；括号与引号建立嵌套local scope。跨hard/local scope不允许material edge，除非TargetTopology显式的cross-sentence bridge；
3. `EVENT-CANDIDATES`：target predicate ontology命中、auxiliary＋non-nominal token序列、可识别finite/participle morphology均产生candidate。coordinator右侧若出现新subject、上述candidate或typed material mention且`OBJECT-LIST`不能证明，则产生新event或`AMBIGUOUS_EVENT_BARRIER`；因此unknown base/nonce即使无法判作verb也不能被左event吞并；
4. `OBJECT-LIST`：只在左右项type相同、共享同一role slot、两者间无subject/auxiliary/predicate/hard boundary、且右项后没有独立event complement时产生`NO_NEW_EVENT_PROOF`；缺任一premise即不合并；
5. `SUBJECT/TIME`：显式subject先连本event；协调event仅经`G23`继承actor。前置/后置period只有在同clause且无competing event时连接一个event；共享period必须逐event有proof edge；
6. `NOMINAL`：每个NP保留所有candidate heads；`of/for/with` complement、relative pronoun＋finite predicate、participial形态、appositive comma pair和NP coordination分别产生typed directed edge。无法唯一确定head时保留全部competing nodes并标`AMBIGUOUS`，不选nearest/first-match；
7. `PRICE`：在同一event/local scope收集全部money与nominal paths，只按`G50/51/52`四个positive family构造price proof；若money还可由service/contract/finance/unknown higher head支配，或存在多条路径，`G90`先行；
8. `TARGET`：candidate discovery后只消费有向graph和TargetTopologyContract；禁止回读raw sentence做第二套regex complete规则。

finite/inflection资源只能增加“可能存在event”的保守barrier，不能单独证明target predicate或complete。若实现无法用上述procedure唯一parse真实positive，结果应为`P`并触发positive recall审查；不得为该例在classifier加special case。

#### 2.3.3 Vocabulary-use matrix与anti-relabel约束

| 资源 | 可用于 | 禁止单独决定 |
|---|---|---|
| target entity/product/measure ontology | candidate discovery、mention typing | event split、role ownership、complete／negative |
| target predicate ontology | event semantic label、candidate discovery | event scope存在、跨event合并、complete |
| auxiliaries/coordinators/inflection/function words | structural premise | target meaning、complete |
| company／verb／service／connector表 | provenance或positive typing | event barrier、priced head、complete／partial／negative |
| unknown／nonce head、link、owner | 产生node和ambiguity proof | 因“不在词表”直接negative或因“未命中denylist”complete |

pre-formal审查必须静态检查dependency与vocabulary-use：任何改名后的`hint/lexicon/cue`只要直接控制complete、scope合并或priced head，均为P1。除作者固定seed外，reviewer必须在`I`冻结后才用独立确定性operator grammar生成nonce event/head/link/owner holdout；seed、operator manifest、fixture root和结果root进入`A`，不得在`I`前泄漏给实现。

### 2.4 Transformation只证明preservation，不证明parser truth

source与compiled两侧同一parser的semantic digest相等，只能证明common output被保存，不能证明output语义正确。R14把职责分成：

- extraction invariant gate：event／role／temporal／price-head truth与property oracle；
- transformation gate：node／edge／topology是否无loss、无addition、无rebind；
- population gate：expected input是否全部有decision；
- projection gate：formal output是否精确等于pre-formal commitment。

任何一门不能由另一门的PASS抵消。

## 3. 冻结输入、输出与依赖图

### 3.1 Immutable inputs

R14 plan与implementation必须绑定：

- R13 implementation、policy、attempt receipt、raw reuse capture、private／public result、fixed manifest与fresh failure audit；
- canonical R12/R13 raw execution SHA=`0e9e4456...f7458`；
- source records `data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/v5/records.jsonl` SHA；
- compiled objects `data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/v9/objects.jsonl` SHA；
- execution program、residual route program、runtime registry／binding receipt；
- R17 14-file carry-forward bundle；
- fresh R13 finding seeds与positive controls；
- current Python／frontend／detector／runtime baseline。

任何输入SHA、target set、raw、route identity或R13 immutable artifact漂移，R14立即停止；不得“刷新输入让实现通过”。

### 3.2 Planned outputs

formal前的artifact必须分commit生成，不得混在一次提交：

- `I`：R14 machine-readable requirement/grammar/topology schemas、implementation、runner/projector和tests；
- `B`：private `InputPopulationManifest`的public-safe commitment、zero-call `PreFormalDecisionCommitment`、compact vectors/details roots、property/mutation receipts、canonical byte-count receipt和preview worklog；
- `A`：fresh pre-formal author-separated audit receipt及append-only治理状态；
- `P`：只有`A=PASS`后，单独生成policy v2.3或下一个非覆盖identity；该commit不允许其他path变化。

只有exact `PREFORMAL_PASS` lifecycle receipt与磁盘门同时通过后，runner才允许exclusive-create唯一未使用的R14 attempt ID、receipt、raw capture、private result、decision sidecars、public result、transaction manifest和terminal publish marker。之后另存exact replay、case-correct fixed audit manifest、fresh post-formal audit与model-run记录。tracked artifact不得包含private manifest IDs、source text或locator。

### 3.3 Dependency graph

```text
R13 fresh failure + R17 carry-forward
        |
        v
R14-00 machine requirements/grammar/oracle freeze
        |
        +--> R14-01 InputPopulationManifest
        +--> R14-02 event/mention/role graph schema
        +--> R14-03 price-attachment graph schema
                    |
                    v
            R14-04 target topology compiler
                    |
                    v
            R14-05 transformation graph
                    |
                    v
R14-06 decision vectors + reconciliation + projector
                    |
                    v
R14-07 frozen property/mutation inventory -> R14-08 full-corpus preview + bundle B
                    |
                    v
R14-09 independent pre-formal review + receipt A
                    |
              PASS only
                    v
R14-10 policy-only P -> unique formal transaction -> replay
                    |
                    v
R14-11 fixed manifest + independent post-formal review
                    |
              PASS only
                    v
03C external and later downstream sequence
```

R14-09通过前不得创建policy或attempt；R14-11通过前不得进入03C。

## 4. 数据合同

### 4.1 `InputPopulationManifest v1`

必需字段：

- schema／manifest ID／recorded_at／generator version；
- source records ref／SHA／count；
- compiled objects ref／SHA／count；
- sorted target IDs；
- source canonical order：`source_record_id`、canonical family ID、occurrence index、input digest、metadata digest；
- object canonical order：object ID、source family ID、input digest、metadata digest；
- duplicate／missing／empty-ID检查；
- source/object keyset digest、canonical family/occurrence digest、target cross-product digest；
- expected lane counts；
- canonicalization／enumerator version；
- builder module identity与changed-path digest；
- independent rebuilder identity与dependency scan digest；
- result digest。

Manifest不含classification、package row或summary，不能从private result反推。producer直接读取冻结source/object/target contract；independent rebuilder也直接读取这些原始输入，但不得import producer keyset builder、classifier、package、projection或其canonical-order helper。两者只允许共享schema constants、domain-separated hash primitive和文字化canonical-bytes规范；pre-formal reviewer还须用第三条只读脚本从原始输入重建exact keyset/count/root。

完整manifest是private artifact；tracked `InputPopulationManifestCommitment v1`只含input SHA、counts、expected lane counts、keyset/order/cross-product roots、private artifact SHA／size和result digest，不含raw text、private locator或逐条长ID。privacy test必须证明public/tracked projection无法重建私有标识。

### 4.2 `DecisionVectorReceipt v1`

每个target×lane必需：

- manifest ref／SHA／digest；
- target ID／lane／expected length；
- fixed canonical index version；
- outcome alphabet和semantic meaning；
- exact canonical outcome bytes；
- complete／partial／not-target／typed-error counts；
- vector root；
- sparse detail root与detail count；
- no missing／duplicate／orphan／out-of-range flags；
- parser／target topology／price graph versions；
- result digest。

Canonical encoding唯一固定为：`C=00`、`P=01`、`N=10`、`E=11`；按manifest index递增，每字节从高到低依次存四个cell（bits `7..6, 5..4, 3..2, 1..0`）；末字节未用的低位pair必须为`00`；byte length必须等于`ceil(expected_length/4)`。vector root为SHA-256：domain separator `FIN_IA_R14_DECISION_VECTOR_V1\0`＋length-prefixed canonical header（manifest digest、target、lane、length、alphabet version）＋exact vector bytes。target／lane／manifest identity均不可从root输入中省略。

Detail multiplicity唯一固定为：每个`C/P/E` cell恰好一个content-addressed decision detail row；每个`N` cell必须为零detail，不再存在“需说明N”的例外。每个detail row绑定manifest index、input digest、target、lane、outcome、vector cell code与row digest：

- `C`必须有accepted event／target topology／package digest，三者不得为null；
- `P`必须有candidate proof、missing／ambiguous／unsupported limitation和graph digest；
- `E`必须有manifest预注册的malformed-input key与closed typed-error code；
- frozen valid corpus若无预注册坏行，则formal `E=0`；ambiguity／unsupported structure只能为`P`，内部parser／compiler异常是terminal failure而非`E`。

detail root使用独立domain separator、manifest index canonical order和length-prefixed rows。第二个independent decoder/rebuilder必须直接从manifest＋vector bytes重建exact outcome keyset／counts，并验证detail双射；它不得import producer encoder／decoder或summary helper。

### 4.3 `EventArgumentGraph v1`

`EventNode`必需：

- event scope ID；
- sentence／clause／document exact spans；
- predicate head span、surface、normalized identity与proof type；
- explicit／inherited subject state；
- polarity、modality、actuality、lifecycle、speech mode、assertion owner；
- ambiguity／limitation；
- node digest。

`MentionNode`必需：

- mention ID、type、exact span、raw／normalized value、type proof、node digest；
- supported types至少entity、product、hardware/configuration、nominal head、price、quantity、period、recipient。

`RoleEdge`必需：

- event scope ID、role、mention ID、proof type、evidence spans、edge digest。

`SubjectShareEdge`必需：edge ID、source explicit-subject mention ID、left event ID、right event ID、destination role=`actor`、coordinator span、proof rule ID、cardinality和edge digest。每个edge只允许一对event和一个actor role；不得复制predicate或任何material mention。

`TemporalScopeEdge`必需：edge ID、period mention ID、event ID、scope type、proof rule ID、evidence spans和edge digest。默认一period→一event；只有grammar显式证明shared temporal adjunct时才允许同一period以独立edge连接多个event。没有edge的period不能完成target。

所有node／edge endpoint必须存在且类型匹配；orphan、duplicate、cycle（除schema明确允许）、span越界、many-to-one rebind或canonical ID collision均terminal reject。

### 4.4 `PriceAttachmentGraph v1`

必需节点／边：

- nominal heads；
- product／hardware heads；
- prices；
- complement、relative、participial、apposition、coordination edges；
- price attachment edge；
- unique governing head／path proof；
- competing head／price／object；
- path ambiguity；
- connector surface provenance；
- graph digest。

每条edge必须含edge ID、source node ID/type、destination node ID/type、direction、rule ID、proof state、exact spans、precedence与digest。允许endpoint矩阵固定为：nominal→nominal（complement／relative／participial／apposition／coordination）、event→nominal（event object/head）、price→nominal（price attachment）、product/hardware→bundle（member）；任何反向或未声明类型为`MALFORMED`。path canonicalization按edge direction和span order；multi-head／multi-price／competing path先进入`G90-CONFLICT`，不得用first-match消解。

Complete ASP只允许肯定式proof topology：

1. event内seller／quoter；
2. event内quote／offer／sale pricing predicate；
3. event内唯一priced head；
4. priced head为specific product／hardware configuration或经证明的hardware bundle；
5. event内唯一price attachment path；
6. period／denominator若target合同要求则有同event scope；
7. 无competing higher head、owner、event或price。

肯定式price proof只有四族：event内`pricing predicate → product/hardware object + price complement`；`product/hardware → priced-at → price`；显式`price/cost of|for product → copular amount`；全部成员均为hardware/configuration且有bounded total的hardware bundle。其他nominal/head/link路径（包括service、support、finance、maintenance、freight和nonce head）不是denylist negative，而是“unique priced hardware path未被肯定证明”→`P`。

### 4.5 `TargetTopologyContract v1`

六个target必须以machine-readable records冻结required roles、role→event edge、event cardinality、subject/temporal/quantity scope、bridge、forbidden inference、outcome precedence与真实positive family semantic fingerprints：

| target | required event-local proof | event cardinality／bridge | forbidden inference |
|---|---|---|---|
| `DELL-RSQ-03A-TARGET-ASP` | `dell_subject`、`affirmative_price_quote`、`price_surface`、`bounded_object`；seller/quoter、product/hardware和price均有edge；合同要求时含period/denominator | exactly 1 pricing event | configuration/bundle quote≠realized company ASP/mix；service/contract total≠hardware price |
| `DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH` | `dell_subject`、`named_supplier`、`directional_relationship_delivery`；Dell recipient/counterparty有edge | 1；或最多2个event且有same-supplier＋same-Dell typed relationship→delivery bridge | relationship/delivery≠allocation、capacity、yield、quantity |
| `DELL-RSQ-03A-TARGET-CAPACITY-RELEASE` | `relevant_supply`、`capacity_or_availability_event`、`upstream_Dell_allocation`、`timing_surface`；upstream actor和Dell recipient有edge | exactly 1 material event | generic supply/delivery≠Dell capacity release |
| `DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD` | `relevant_supply`、`observed_yield_or_utilization`、`observed_measure`、`timing_surface`；process owner有edge | exactly 1 measurement event | plan/goal/industry figure≠observed issuer measure |
| `DELL-RSQ-03A-TARGET-HBM-SUPPLY` | `hbm_subject`、`supply_state`、`directional_Dell_bridge`、`timing_surface`；upstream actor有edge | 1；或最多2个event且有typed HBM-state→Dell bridge | generic HBM market/supplier relationship≠Dell supply state |
| `DELL-RSQ-03A-TARGET-UNITS` | `dell_subject`、`physical_server_quantity`、`Dell_seller_or_shipper_role`、`timing_surface`；product与quantity有edge | exactly 1 event | project/node/install/customer/non-company count≠Dell company units |

machine record必须保存上述六个完整target ID。bridge endpoint、direction、role cardinality与allowed coreference rule均为closed schema。对valid input，先应用terminal structural validity，再按`candidate + all required PROVED + no conflict → C`、`candidate + missing/ambiguous/unsupported → P`、`no candidate → N`；`E`只由预注册malformed key触发。target vocabulary可以发现candidate和标注semantic type，但不能改变StructuralProofGrammar的event/head边界。

### 4.6 `PreFormalDecisionCommitment v1`

由冻结`I` implementation commit／tree＋manifest＋inputs＋zero-call preview生成并存入后继`B`，必须包含：

- implementation identity；
- manifest identity；
- parser／topology／transformation versions；
- 每个target／lane vector root、detail root、counts；
- aggregate package／event／binding／coverage roots；
- candidate ceiling、family、rank、route disposition摘要；
- current R13→R14逐family delta；
- canonical serializer identity、performance、memory、每个planned artifact exact bytes或proved upper bound、total planned bytes；
- critical mutation manifest／kill receipt SHA与root；
- property operator／seed／matrix／result roots；
- private decision vectors/details的SHA／size／root，以及不泄密public commitment；
- result digest。

policy必须绑定该commitment；formal result任何root不等即失败。Commitment不包含`B`自身commit identity，也不声称truth-oracle independence。

### 4.7 `CriticalMutationManifest`与`CriticalMutationKillReceipt v1`

Manifest逐mutant固定：ID、requirement/finding ID、operator ID/version、input/fixture digest、target layer、expected typed failure／oracle、severity、critical flag、seed、generator identity和row digest；exact keyset/root在执行前冻结。Kill Receipt逐项记录observed verdict、kill layer、test/implementation/tree identity、duration和row digest，并给出unexecuted／survived／excluded counts。所有critical mutant的unexecuted、survived、excluded必须为0；`100%`只能用Manifest frozen denominator计算，作者不能在执行后删减分母。

Property Receipt另存operator grammar、fixed author seed、generated keyset、positive controls、minimal counterexamples与roots。reviewer在`I`后生成的fresh holdout不写回作者Manifest，而进入Audit Receipt并与作者suite交叉复核。

### 4.8 `PreFormalAuditReceipt`、`PostFormalAuditReceipt`与author separation v1

`PreFormalAuditReceipt`必须含review task/reviewer identity、author identity、fresh/no-fork或等价隔离attestation、read-only/no-write attestation、禁止动作计数、reviewed `I/B` commit/tree/parent/pathset、Manifest／Commitment SHA＋digest、property/mutation roots、fresh holdout seed/operator/fixture/result roots、findings `P0/P1/P2/P3`、verdict和result digest。reviewer判断属于agent/human attestation，repo hash不能单独证明其主观独立性；runner能且必须证明receipt identity和reviewed bytes没有被替换。

`PostFormalAuditReceipt`必须绑定formal commit/tree、policy `P`、attempt ID、raw／private／public／all sidecar／transaction manifest／terminal marker SHA＋size＋digest、replay roots、Manifest／Decision roots、fresh mutation结果、findings vector、author separation和result digest。03C preflight只接受exact `POSTFORMAL_PASS` receipt。

审计者保持只读：它通过编排层返回structured payload；作者只能按canonical schema物化该payload并记录原始payload digest，不得改写verdict/findings。`A`的changed-path和payload digest由policy preflight复核。

### 4.9 `R14LifecycleReceipt v1`

机器状态唯一为：

`PLAN_FROZEN → IMPLEMENTATION_FROZEN → BUNDLE_FROZEN → PREFORMAL_REVIEW_PENDING → PREFORMAL_PASS → POLICY_BOUND → ATTEMPT_CONSUMED → FORMAL_TERMINAL → POSTFORMAL_PASS`

任一审查或formal材料失败进入`R14_STOP_OWNER_DECISION_REQUIRED`。每次transition receipt绑定prior state/root、actor、authority、allowed paths、required artifacts和result digest；runner只接受上一个exact state，不允许跳转或覆盖。STOP状态下禁止R15、03C和任何downstream policy创建/执行；只有单独`OwnerDecisionReceipt`可选择：同一R14更换parser/IR并回到新的`IMPLEMENTATION_FROZEN` cycle、永久route `partial＋human`、或终止03B。该receipt不能把失败attempt抹去或重新消费同一attempt ID。

## 5. 需求票与双重质量验收

### R14-00：Predecessor、finding与oracle freeze

输入：R13 fixed manifest、fresh audit、R17 carry-forward、历史R1-R13 failure seeds。
输出：machine-readable `R14RequirementManifest`、`StructuralProofGrammar`、`TargetTopologyContract`、lifecycle transition table、exact finding registry、positive controls、property/operator families、禁止重开的closed issues。

工程验收：每项finding有invariant、owner stage、input/output、oracle、critical mutations、stop state和downstream impact；三项R13 finding可精确复现；R13 current artifact PASS_NARROW与general FAIL分列；旧R12 summary-field P1和path-case issue标为closed，不被误重开；grammar和六target topology schema可独立validate。
模型环节质量：R14模型／Provider／token authority为0；若未来引入parser模型，必须另行TokenBudgetBasis和用户授权。
研报质量：R17 `0/18` citations、14/9/4/10/4 crosswalk、WWC 0/6、Facts 72/36、S2 null与human 0/16逐项carry，不因R14改变。
停止：finding计数或scope混淆；把current count正确当general PASS；把R17 finding合并后抵销。

### R14-01：InputPopulationManifest与canonical enumerator

输入：冻结source/object files、target set。
输出：manifest、independent validator、missing／duplicate／order mutation tests。

工程验收：source=1888、canonical family=1862、objects=34199、targets=6；producer与rebuilder分别直接读raw input并生成相同IDs/digests/keyset/root；rebuilder dependency scan证明未import producer keyset helper、classifier、package或projection；reviewer第三路径重建相同；canonical order确定；manifest不能读取R14 packages；相同输入byte-exact；改变input ID/text/metadata/order按合同产生预期结果；tracked commitment不泄漏私有标识。
模型质量：0 calls；manifest只记录输入事实，不生成研究结论。
研报质量：无报告authority；不得把manifest覆盖写成“source gap closed”。
停止：manifest依赖classifier output；keyset无法重建；source/object SHA漂移；内存或文件尺寸超限。

### R14-02：Typed EventArgumentGraph

输入：一个source sentence或compiled object text＋metadata。
输出：event／mention／role／subject-share／temporal graph。

工程验收：implementation逐rule消费`StructuralProofGrammar`，每个proof保存rule ID/premises/state；每个predicate scope独立；shared subject只建立actor edge；material role无event edge时partial；known／unknown event head、case、adverb、auxiliary、active／passive、punctuation不允许跨event complete；object list有肯定式no-new-event proof；SubjectShare/Temporal endpoint与cardinality exact；graph determinism和digest mutation通过；静态检查证明verb/company/service/connector名单不能直接控制scope或complete。
模型输出质量：不是“分类对了即可”，accepted claim的predicate、owner、product、price、period topology也必须正确；ambiguous必须显式。
研报质量：event-local attribution是未来claim-source accuracy前置，但本票不生成报告。
停止：修复依赖新增verb/company闭集；`and offered`虽complete但predicate仍指左event；supplier正例只能靠flat union保留。

### R14-03：Structure-first PriceAttachmentGraph

输入：event-local mentions与nominal spans。
输出：nominal/complement/attachment graph、unique priced-head proof。

工程验收：所有edge endpoint/direction/canonical path符合第4.4节；service/finance/support/freight/nonce higher head在所有结构同构surface上同verdict；`with`、participial、relative、appositive、multiword未知link不能因未枚举而complete；只有四个positive price proof family可complete；direct product price与explicit price head正例保持；多head／多price／跨event／unparsed为partial；nonce link/head substitution不改变proof state。
模型输出质量：proof path可读、可重算；connector只作provenance；unknown不猜测。
研报质量：configuration quote明确不等于company realized ASP／mix；未来Writer不得扩大解释。
停止：新增connector列表是主要修复；nonce substitution改变verdict；positive direct path不能重现。

### R14-04：Target-specific topology compiler

输入：EventArgumentGraph＋PriceAttachmentGraph＋target contract。
输出：complete／partial／not-target／typed-error decision与package detail。

工程验收：六个完整target ID逐一通过`TargetTopologyContract` schema；required roles、edge、event cardinality、temporal/quantity scope、bridge endpoint和forbidden inference可机验；ASP为single pricing event；capacity／yield／units的actor／object／measure／period同event；supplier/HBM仅在声明的最多两event typed bridge下允许；不得推断allocation／yield／quantity。complete不能由跨event union组成，positive family semantic fingerprint只能作回归标签，不能替代topology proof。
模型输出质量：classification、missing roles、ambiguities、limitations、accepted event ID、role edges与semantic signature一致；partial候选保留，不静默丢弃。
研报质量：candidate不等于Evidence；任何complete都保留forbidden inference边界。
停止：某target没有声明topology；accepted frame仍是整句flat span；current family变化无法解释。

### R14-05：Graph-aware transformation

输入：source与compiled graph／decision details。
输出：node／edge mapping、typed loss／addition／rebind receipts。

工程验收：event增删、predicate owner、role→event、period scope、governing head、attachment path、connector provenance改变均产生typed finding；offset-only在可复证offset map下通过；common-mode错误必须先被extraction oracle挡住。
模型输出质量：transformation coverage区分vacuous与non-vacuous；相等不冒充truth。
研报质量：future claim provenance能追到source而非仅compiled相似文本。
停止：任一topology rebind仍lossless；complete只存在compiled侧；source complete无映射。

### R14-06：Decision vector、reconciliation与public projection

输入：manifest、full decision vectors、detail receipts、transformation receipts、coverage、route registry。
输出：candidate ceiling、summary、private/public projection。

工程验收：固定2-bit alphabet、bit/endian/padding、domain separation和byte length exact；manifest↔vector exact length/index；每个C/P/E恰一detail、N零detail；typed-error admissibility exact；independent decoder不复用producer helper；missing／duplicate／orphan／wrong target／wrong digest拒绝；summary从manifest＋receipts派生；private self-digest仅为辅证；projector必须验证policy-bound pre-formal roots。删除整行＋同步重算全部derived surfaces、替换vector/detail后重签derived surfaces仍拒绝。
模型输出质量：complete/partial/not-target/error counts透明；zero complete允许coverage pass但non-vacuous=false。
研报质量：public只露出安全summary和bounded packages，不泄漏model_text／private locators；不生成reader citation。
停止：projector只接private dict；outcome vector可重签；candidate ceiling与full receipts分叉。

### R14-07：Property／metamorphic／critical mutation oracle

输入：冻结author seed、operator grammar、真实positive families、R14RequirementManifest。
输出：执行前冻结的`CriticalMutationManifest`、可重复test matrix、minimal counterexamples、`CriticalMutationKillReceipt`和property receipt。

工程验收见第6节；Manifest exact keyset/root先于执行，critical unexecuted/survived/excluded均为0，kill=`100%`；每个test同时断言classification和topology，不以总pass数替代。reviewer fresh holdout在`I`冻结后生成，不并回作者分母。
模型输出质量：irrelevant event insertion不能增加completeness；structure-equivalent lexical substitution保持negative或降级，不得创建complete。
研报质量：未来reader claim所需owner／period／price attribution由同一oracle约束。
停止：任一critical mutant存活；seed不固定；negative大量增加但没有positive recall审计。

### R14-08：Immutable R13 raw zero-call full-corpus preview

输入：R13 raw、raw source/object、manifest order、target contracts、冻结`I` compiler。
输出：bundle `B`、pre-formal commitment、full vector/detail roots、count/family/rank/route delta、canonical serializer exact-byte/storage receipt。

工程验收：216,522 logical decisions完整；无silent drop；manifest/vector/detail roots exact；preview compiler不能读取既有preview vector/detail；替换preview output但保持implementation/input时，compiler recomputation不变且末端comparator因commitment mismatch失败；canonical counting/hash sink与materializing serializer对同fixture给出相同bytes/root；R13→R14每个complete family和partial delta有解释；supplier三族保留或逐族结构性处置；五target 0 complete若变化必须逐package审阅；public privacy和routes不退化。
模型质量：0 model/provider/network/external/embedding/reranker；TokenBudgetBasis逐项记录zero-call目的、input scale、required outputs、schema burden、materiality risk、comparable run、stop behavior。
研报质量：R17 unchanged，所有report-quality verdict原样carry。
停止：false complete、unexplained delta、vacuous展示成Evidence完整、route omission、runtime／memory／disk hard stop。

### R14-09：Fresh author-separated pre-formal audit

输入：clean pushed exact `I`、parent=`I`的exact `B`、manifest、commitment、tests、mutation/property receipts、preview。
输出：结构化只读`PreFormalAuditReceipt`，形成parent=`B`的`A`。

工程验收：reviewer独立从raw input重建Manifest keyset，静态检查dependency/vocabulary-use，使用implementation freeze后fresh nonce holdout，复核三finding、data contracts、property/mutation exact denominator、current corpus delta、`I/B` topology；receipt绑定所有reviewed bytes与holdout roots；P0/P1/P2必须`0/0/0`。
模型／研报质量：分别签工程与R17 carry-forward，不混合finding；reviewer不是qualified human。
停止：任一material finding；reviewer需写仓库或跑昂贵全仓测试才能判断；bundle不完整。

### R14-10：Policy-only authority、唯一formal与exact replay

前置：exact lifecycle=`PREFORMAL_PASS`、`A` receipt PASS且磁盘门通过。
输入：exact `I/B/A` identities、manifest、commitment、audit receipt、all bound inputs、TokenBudgetBasis。
输出：parent=`A`且只改policy的`P`、唯一attempt、transactional raw/private/sidecar/public bundle、exact replay。

工程验收：policy commit只改policy；parent/tree/path exact；attempt ID未使用；capture-first；第8节multi-artifact transaction与terminal marker exact；attempt目录exact；formal compiler输入只能是frozen raw source/object、target contracts、manifest order和`I` implementation，preview vector/detail只允许末端comparator读取；private dict/bytes replay exact；formal roots精确等于commitment；新增调用全部0。
模型质量：0 calls；任何非0计数hard fail。
研报质量：下游authority全false。
停止：same ID存在、Git不clean/synced、input/manifest/commitment SHA漂移、disk不足、atomic失败、formal与commitment不等。

### R14-11：Fixed manifest与post-formal dual audit

输入：immutable formal result commit与terminal transaction marker。
输出：case-correct manifest、structured `PostFormalAuditReceipt`、fresh工程＋R17审计。

工程验收：hash／size／declared digests／Git topology／attempt／raw／transaction visibility／replay／population／semantic／route全部重建；真实artifact上的同步变更测试被拒；receipt绑定formal全部sidecars与roots；lifecycle只在P0/P1/P2=`0/0/0`时进入`POSTFORMAL_PASS`。
研报质量：R17仍须签`FAIL_GATE`，不能因工程PASS变更；report bundle若字节未变，只复证hash＋carry指标。
停止：任一material finding；不要自动开R15，回到第9节hard stop决策。

## 6. 测试与oracle矩阵

### 6.0 Frozen denominator、kill layer与独立holdout

`CriticalMutationManifest`必须在执行suite前冻结并覆盖至少以下critical operator family；每个materialized case有稳定ID，不能只写一个family总称：

| family | 必含operator | expected kill layer |
|---|---|---|
| population | 删除/重复/移位任一C/P/N/E cell；同步重算全部derived summary；替换manifest index/input digest | independent manifest/vector rebuilder或policy comparator |
| authority | 替换`B` commitment；审查A后换签；改变`I/B/A/P` parent/path；用preview vector作为formal compiler输入 | topology/lifecycle/formal preflight |
| event | shared subject跨event复制material role；different owner/period；known/nonce predicate；object-list↔event mutation | StructuralProofGrammar／TargetTopology |
| price | known↔nonce higher head/link；direct product↔service contract；multi-head/multi-price/path rebind | PriceAttachmentGraph／TargetTopology |
| transformation | event/node/role/period/head/path增删或rebind；common-mode wrong graph | extraction oracle或transformation gate |
| encoding/error | bit flip、padding非零、wrong endian、orphan detail、N detail、C null topology、valid ambiguity→E | independent decoder/schema/preflight |
| transaction | 每个artifact write/flush/manifest/marker/rename边界的subprocess kill；collision和partial staging | transaction reader/recovery preflight |
| privacy/route | public projection注入private ID/text/locator；route omission/rebind | privacy/route validator |
| positive protection | direct/list/supplier三族positive的结构破坏与无关surface替换 | positive topology oracle；不得靠boolean snapshot |

Manifest冻结后才执行；Kill Receipt exact keyset必须等于Manifest exact keyset。critical case不允许`excluded`、`xfail`、未执行或“因平台不适用”跳过；若Windows crash operator无法执行，formal能力本身判FAIL。每个kill记录最先拒绝layer，后续层不能掩盖前层漏检。

作者固定property suite用于重复回归；reviewer fresh holdout用于检测对已知表面过拟合。holdout operator grammar固定，但具体seed/nonce fixture只在`I/B`冻结后由reviewer生成；作者修复后必须重新freeze `I′/B′`并由reviewer生成新的holdout，不能把旧holdout补进词表后沿用原PASS。

### 6.1 Population completeness

- 删除complete／partial／not-target／typed-error任一logical cell；
- duplicate、跨target移动、index shift、input ID/digest替换、orphan detail；
- 同步重算package／summary／candidate ceiling／private digest；
- 修改manifest但保持policy SHA；
- vector root与detail root分叉；
- noncanonical order、重复canonical family occurrence；
- empty lane、vacuous complete coverage；
- 只重排set-like detail rows的canonical invariance。

预期：语义变化全部reject；允许的非语义重排要么canonicalize为exact，要么按on-disk canonical合同reject。

### 6.2 Event-local properties

- shared subject known／unknown predicate；
- different owner；
- comma／semicolon／colon／em dash／parenthetical／无标点coordinator；
- case、adverb、auxiliary、active／passive、inflection、nonce event head；
- period／quantity插入另一event；
- clause reorder、sentence split／merge；
- object／product／quantity list；
- fronted adjunct；
- supplier `NVIDIA provides GPUs and ships them to Dell`；
- `quoted support...and offered hardware...`必须由右pricing event自身complete；
- irrelevant event insertion不得改变原accepted event roles/digest，除representation offset。

核心property：插入无关event不能增加completeness；shared subject不能共享material roles；跨event role count永不参与single-event target完成。

### 6.3 Price attribution properties

- `covering↔encompassing↔incorporating↔with↔nonce participle`同构替换；
- prepositional／participial／reduced relative／full relative／possessive／appositive；
- common head↔nonce head；
- price before／after product；
- multiple head／price／product；
- service／lease／support／freight／finance／nonce higher head；
- direct PowerEdge price、explicit purchase/configuration price、bounded hardware bundle price positives；
- component price与contract total分离。

核心property：未证明unique priced hardware head时只能partial；插入competing non-product head不能提高completeness。

### 6.4 Transformation properties

- event node增删；
- predicate owner rebind；
- role edge／period scope rebind；
- head／attachment path rebind；
- connector provenance change；
- offset-only exact map；
- source／compiled共同错误surface。

预期：topology变化typed reject；offset-only接受；共同错误由extraction gate拒绝，不能靠equality放行。

### 6.5 Real-corpus positive protection

- supplier source complete三families、compiled three、union two、final one／rank2；
- direct Dell hardware quote／offer；
- explicit purchase/configuration price；
- bounded hardware bundle；
- product list；
- supplier relationship／delivery；
- R1-R13所有已修复execution、privacy、route、anchor、polarity、modality、state controls。

任何positive变化必须记录event graph和target topology原因；不能只比较最终boolean。

## 7. 风险分层测试与全仓pytest止损

### T0：每次结构编辑

- Python compile；
- targeted schema/static/diff；
-单模块关键property／mutation；
- JSON parse／self-digest；
- pyflakes仅changed files。

目标：秒级至低分钟；不跑全仓。

### T1：一个ticket完成

- R14 direct tests；
- property/metamorphic固定seed；
- critical mutation；
- population／event／price／transformation／projection各自direct suite。

### T2：接口冻结前

- R13↔R14相邻compiler／runner／projection；
- execution、privacy、route、atomic、replay相邻合同；
- DELL S1 adjacent narrow profile。

### T3：implementation freeze

- Project OS foundation；
- active baseline；
- changed／all config JSON parse；
- Project OS JSONL parse；
- repository secret scan；
- diff check。

### T4：全仓

仅在以下trigger为true时运行一次：

- 修改共享runtime／schema／公共API；
- T1/T2发现跨域回归；
- 影响范围不能由import／consumer图证明；
- pre-formal reviewer指出必须用全仓才能排除的材料风险。

R14新模块若只由新runner消费且R13冻结，默认T4=false。任何小改禁止频繁运行约20分钟全仓pytest。

## 8. 性能、磁盘与原子性门

2026-08-28 11:10实测：

- D盘free=`518,934,528 bytes`（约495 MiB）；
- 现有formal floor=`536,870,912 bytes`（512 MiB）；
- R13 private result=`58,032,303 bytes`（约55.3 MiB）。

因此当前已不满足formal preflight，R14 formal明确blocked。不得删除任何immutable历史evidence来“腾位置”。

R14存储策略：

- manifest IDs/digests只保存一次；
- decision outcome使用fixed-length compact vectors；
- full graph/details使用content-addressed sparse sidecars；
- 主private只保存roots、counts、refs和bounded public-safe projections；
- preview必须让formal使用的同一canonical serializer同时写入counting/hash sink，得到每个planned artifact的exact bytes/root；无法无物化确定的scratch只允许使用有测试证明的保守上界；
- Commitment逐artifact绑定relative path、exact bytes或proved upper bound、SHA/root和总planned bytes，禁止自由手填估算。

动态required free不再使用含义不清的`3 × output`。定义：

`required_free_before_attempt = max(512 MiB, B_stage + B_publish_duplicate + B_serializer_scratch + B_raw_capture_or_copy + B_replay_temp + B_failure_receipt + B_runtime_drift + 128 MiB)`。

其中`B_stage`覆盖private/public、raw/attempt receipt、全部vector/detail/graph sidecar、transaction manifest和terminal marker；`B_publish_duplicate=0`只有在same-volume directory rename路径通过能力测试时成立，否则必须计入完整第二份；raw hard-link能力未证明时按full copy计；`B_runtime_drift`取preview期间观测到的free-space下降上界与预注册floor之大者。policy前、attempt reservation前、每个large artifact写入前、staging完成后rename前都重检：`free_now >= remaining_bytes + scratch + failure + drift + safety`。低于门立即停止并向Owner报告，不自动清理、覆盖、压缩或删除任何历史attempt。

### 8.1 Windows same-volume multi-artifact transaction v1

formal不得再把逐文件hard-link＋进程内rollback称作atomic。唯一发布协议为：

1. preflight把attempt parent、reservation path、staging path和final path解析为canonical absolute path，证明位于预期workspace private attempt root、同一volume、无symlink/reparse逃逸，且final/staging/reservation均不存在；
2. 以create-new/no-overwrite写`attempt_reservations/<attempt_id>.json`并flush＋`FlushFileBuffers`＋close；reservation成功即`ATTEMPT_CONSUMED`，此后任何crash也不得复用ID；
3. exclusive-create同volume sibling目录`.<attempt_id>.incomplete.<nonce>`；所有artifact按Commitment pathset写临时文件，逐文件canonical serialize、flush、`FlushFileBuffers`、close、重开并验证size/SHA/root，再在staging内no-replace rename为最终相对名；
4. 所有artifact完成后生成`TRANSACTION_MANIFEST.json`，列出exact relative path、size、SHA、semantic root和bundle root；flush、close、重开复核；
5. 最后在staging内create-new `COMMITTED.json`，只绑定attempt/reservation/transaction manifest/bundle roots和lifecycle state；flush、`FlushFileBuffers`、close；
6. 通过Windows same-volume、fail-if-exists directory rename把整个staging目录一次改名为final `<attempt_id>`；不允许copy fallback或replace-existing；rename后立即从final path重开marker、manifest及全部artifacts复核；
7. reader/projector/replay只扫描final exact attempt目录，且仅在marker＋manifest＋reservation＋全部artifact exact时可见。`.incomplete.*`、无marker、marker漂移或额外sidecar全部视为terminal failed evidence，绝不部分读取。

进程/电源在任一写、flush、manifest、marker或rename边界退出的subprocess crash suite必须逐点通过。rename前失败保留reservation和`.incomplete`目录；rename后验证失败保留final目录并生成独立failure receipt；任何恢复流程只可标记／隔离，不能删除或覆盖历史。若当前Windows/filesystem不能通过same-volume no-replace directory-rename和crash-reader能力测试，formal在attempt消费前hard stop，不降级为多文件link/copy“最佳努力”。

implementation preview阶段可仅保留小型tracked commitment，但private counting/hash pass必须覆盖formal同一serializer和完整planned pathset；磁盘门未通过前不物化formal sidecars、不创建policy或attempt。

性能目标：

- direct property suite应保持低分钟级；
- full-corpus preview以R13约25–30秒为基准，R14 graph与216,522 decision vector允许预注册warning／hard limit，但必须在第一次完整preview前按micro-benchmark量化；
- runtime、peak memory、estimated bytes超hard limit时，不通过减少必需receipts降级；应优化representation或停止。

## 9. Formal前后门与禁止R15的hard stop

### 9.1 Pre-formal进入条件

- 本计划、fresh plan-review failure receipt、R13 fresh audit和root-cause更正已提交，lifecycle=`PLAN_FROZEN`；
- R13 immutables exact；
- `I`的parser backend、StructuralProofGrammar、ambiguity policy、六target topology、schemas、property/mutation denominator冻结；
- parent=`I`的`B`含classifier-independent manifest commitment与same-compiler decision commitment；manifest可由独立rebuilder重建，commitment可由`I`从raw input重算；
- no policy／no attempt；
- `I/B` branch clean／synced且changed-path allowlist exact；
- TokenBudgetBasis完整且calls=0。

### 9.2 Pre-formal退出条件

- 三项R13finding的exact regressions关闭；
- critical mutation kill 100%；
- property suite固定seed、最小反例与positive controls通过，critical unexecuted/survived/excluded=`0/0/0`；
- full-corpus keyset双射、无silent drop；
- current count／family／rank／route delta逐项解释；
- public privacy／transaction crash suite／route不退化；
- fresh author-separated reviewer完成独立keyset rebuild、dependency/vocabulary静态审查和post-freeze holdout；
- parent=`B`的`A` receipt绑定exact reviewed bundle且P0/P1/P2=`0/0/0`；lifecycle=`PREFORMAL_PASS`。

### 9.3 Formal退出条件

- parent=`A`的policy-only `P`／paths exact，policy绑定`I/B/A`及PASS receipt；
- 唯一attempt reservation capture-first成功，reservation后ID永不复用；
- formal compiler从raw source/object重新计算，preview vectors/details只参与末端比较；formal result roots=commitment roots；
- transaction final marker／manifest／all sidecars exact，reader从未暴露partial staging；
- exact replay private dict／bytes及sidecar roots equal；
- attempt population exact；
- manifest／receipt bijection exact；
-真实artifact同步变更测试拒绝；
-post-formal receipt绑定全部artifact，reviewer P0/P1/P2=`0/0/0`，lifecycle=`POSTFORMAL_PASS`。

### 9.4 Hard stop

以下任一发生时不得自动创建R15：

- private package＋全部derived surfaces同步改变仍能通过；
- manifest↔decision cells/detail不是双射；
- known／unknown predicate、shared subject、owner、period、product、price、quantity仍可跨event complete；
- 结构同构link/head词汇替换改变price verdict；
- topology rebind不能产生typed transformation failure；
- critical property mutant存活或full-corpus silent drop；
- direct／list／supplier正例无结构性解释退化；
- count／family／rank／route delta无法解释；
- pre-或post-formal独立审查出现任一材料P0/P1/P2；
- Git／input／manifest／commitment／policy／attempt／atomic／replay不exact；
- 磁盘、内存或runtime hard limit失败。

formal前失败：留在同一R14实现周期修根因并重新pre-formal review，不消费attempt。
formal后失败：R14 attempt保持immutable，lifecycle进入`R14_STOP_OWNER_DECISION_REQUIRED`并停止03B program。runner和03C/downstream preflight在该状态必须拒绝任何R15／03C／model／Evidence／S2／S3／Writer authority。只有独立`OwnerDecisionReceipt`可选择更换parser／IR后仍在R14创建新`I′/B′/A′` cycle、永久路由`partial＋human`、或终止03B；不能靠编号或新policy绕过。

### 9.5 Machine-enforced preflight与hybrid boundary

`R14LifecycleReceipt` validator在commit、policy、runner、03C四个入口执行，逐项验证prior state、commit topology、changed paths、artifact SHA/root、audit verdict和allowed transition；Markdown状态不参与授权。repo hash可以强制“审查的是哪些bytes、结论有没有被替换”，不能数学证明reviewer的主观独立性；fresh task identity、no-fork/read-only attestation和作者分离仍是明确记录的治理事实。任何attestation缺失均fail closed。

## 10. R14通过后的下游完整顺序与质量门

本节只冻结顺序，不授权执行。

下述每个未来model node或paid-call authority都必须另行记录task-specific `TokenBudgetBasis`：node目的、input scale、required outputs、schema burden、materiality/quality risk、comparable-run evidence、reasoning profile、stop/truncation、成本/资源上限。03C external若使用付费工具、0.6B/4B、reranker、S3 Agent、Writer均分别授权；不得用一个总预算覆盖全链，也不得为省钱/延迟静默取消required research work。

### 10.1 五个exact 03C external ladders

目标：ASP、capacity release、utilization/yield、HBM、units。每条保存reachability、original capture、title／publisher／date／period／locator／URL、rights、source/object materialization、exhaustion／failure与forbidden inference。先对账旧50 queries；22个已消费fresh units不得原样再跑。任何paid/model-backed retrieval在单独authority前必须有该梯子的TokenBudgetBasis。

### 10.2 Capture→source→object→index／SQL→crosswalk

本地层失败留在本地层；不得跳过object/index失败去跑embedding，不得声明public gap。重算14 Pack、9 acquisition、admission overlaps、supplier state、Writer 4/10、S2 4 gaps和product-profit独立gap。

### 10.3 Changed-pool 0.6B baseline

同query／corpus冻结target-in-pool、rank、recall、material precision、DELL/MU/NVDA regression、latency／resource。0.6B无Evidence authority；若该baseline需要模型执行，先单独记录TokenBudgetBasis。

### 10.4 Conditional 4-bit 4B embedding shadow

4B不是无条件流水线步骤。只有同时满足以下eligibility gate才可另发model authority：冻结changed pool内存在decision-relevant target candidate；candidate ceiling证明目标材料已进入可比较pool；0.6B baseline的材料缺口可归因于representation/semantic recall或同义排序，而不是source/object/index缺失；预注册hypothesis、same query/corpus/labels、metric floor、minimum material gain、DELL/MU/NVDA regression ceiling、4-bit量化配置、VRAM/latency/resource/cost和stop；并有独立TokenBudgetBasis。否则记录`SKIPPED_NOT_ELIGIBLE`，不加载4B，且CandidateDecision链按现有候选继续。

eligibility通过后才比较gain、irrelevant context、case regression、VRAM和latency。8GB能full-offload不等于质量晋升；任一DELL/MU/NVDA material regression、低于minimum gain或资源越界即停止promotion并保留0.6B结果。

### 10.5 Conditional reranker

只有candidate已在pool、数量达到预注册门槛且问题确为排序歧义时启用；另需独立hypothesis、metrics、stop和TokenBudgetBasis。candidate absent、source absent、object absent时禁止reranker。低于floor或材料误排即停止。

### 10.6 CandidateDecision／Evidence admission

统一处理16 human-required、supplier candidate、03C candidates、duplicate/rebind、counterevidence、period／entity／unit／relation／rights。reject/defer后的残差回到新、精确有界route authority；不能直接写commercial gap。

### 10.7 Pack／Readiness／boundary

重编Evidence Pack、ProductReadiness、gap status、14/9/4/10/4 crosswalk和public/private/nondisclosure receipts。只有所有必要route与admission执行后，才可宣告genuine information boundary。

### 10.8 S2严格顺序

`units/share → ASP/mix → PVM → product profit → working capital`。

- 缺units／denominator／mix weights则PVM null；
- 禁止bundle÷units伪ASP；
- 缺cost／opex allocation则product profit null；
- 禁止segment margin×product revenue伪product profit；
- 禁止company AR/inventory/AP变化归因AI product；
- estimates／scenarios与reported facts分开，全部formula／assumption有lineage。

### 10.9 S3 affected units与新Writer

只重跑受新Evidence/S2影响单元；完成conflict adjudication、strongest counterthesis、method parameters、operational WWC与cross-cell synthesis。Writer生成non-overwriting successor，消费current crosswalk、claim-source matrix、S2 bridge、method register和DocumentModel。每个S3 model node和Writer分别拥有与其input规模/required output匹配的TokenBudgetBasis与stop/truncation合同，不能沿用03C或embedding预算。

### 10.10 研报质量门

新报告必须：

- 100% material claims具reader-verifiable passage/title/issuer/date/period/locator/stable URL；若沿用18 EV则从0/18到18/18；
- source appendix存在；
- 14/9/4/10/4 crosswalk由candidate digest绑定并消费；
- WWC 6/6具metric/event、direction、window、threshold、authority、owner、response route；
- S2每段可算或明确null＋缺失输入＋决策影响；
- 无未解释exact duplicate，优于R17 72/36/36；
- 中英文claim／数值／限定语／不确定性等价；
- P0/P1/P2 report finding为0；
- formal 8D前置包完整，否则`NOT_ASSESSABLE`。

### 10.11 分离验收

依次签：工程／Evidence pipeline、研报研究质量、16项qualified-human Evidence decisions、独立qualified-human product verdict、publication／release。任一前序PASS不能替代后序。

## 11. Authority matrix

| 动作 | 当前：fresh plan re-review待完成 | fresh plan PASS后 | R14 pre-formal PASS后 | R14 post-formal independent PASS后 |
|---|---:|---:|---:|---:|
| plan/audit/governance revision | true | frozen | frozen | frozen |
| R14 implementation/tests/preview | false | true | frozen | frozen |
| R14 policy/formal attempt | false | false | true once | consumed/frozen |
| 03C external | false | false | false | eligible for separate authority |
| 0.6B baseline | false | false | false | changed pool + separate TokenBudgetBasis |
| 4B embedding | false | false | false | conditional eligibility + hypothesis + separate TokenBudgetBasis; otherwise skipped |
| reranker | false | false | false | conditional eligibility + separate TokenBudgetBasis |
| CandidateDecision/Evidence | false | false | false | after candidates and separate gate |
| Pack/Readiness/S2 | false | false | false | sequential only |
| S3/Writer model nodes | false | false | false | sequential + per-node TokenBudgetBasis |
| report/product/publication/release | false | false | false | still false until separate acceptance |

当前唯一允许的动作是完成本次plan审计记录、修订计划并做fresh author-separated只读re-review。只有该review给出`PLAN_PASS`且P0/P1/P2=`0/0/0`，才可按R14-00→R14-08创建`I/B`、再进入R14-09；仍不创建任何模型或外源authority。
