# S1 工作记录 116：DELL 03B R12 program-level execution plan

日期：2026-08-27

状态：`same-stage non-overwriting R12 plan / implementation not started / no R12 policy, attempt or result`

## 1. 决策摘要

R12 只修 immutable R11 fresh audit 的四项材料性 finding：

1. `R11-P1-ROUTE-STATE-ERASURE-ASP`：route contract identity 被当成临时 disposition state，在 `external_required false→true` 后无法恢复；
2. `R11-P2-CLAUSE-OWNERSHIP-OPEN-VOCAB-AND-CASE-DEPENDENCE`：小写／未知 owner-predicate 可伪合并，未见 fronted adjunct 可误拆；
3. `R11-P2-PRICE-INTERVENING-NOMINAL-HEAD`：service／financing／contract 等 governing head 可被最近 `hardware at price` 覆盖；
4. `R11-P2-TRANSFORMATION-CONNECTOR-PROOF-REBIND`：connector/proof 改绑可在无 typed flag 时被接受。

R11 implementation、policy、attempt receipt、raw、private/public、reviewed-result、fixed manifest与fresh fail audit全部 immutable。R12 使用新 module、test、schema、policy、attempt 与 public/private path，不覆盖 R11，不重试 `dell-rsq-03b-internal-chain-r11`，不改变产品版本或 S-stage。

R12 不是补源轮次。03C external、4B embedding、reranker、CandidateDecision、Evidence/NumericFact、Pack/Readiness、S2、S3、新报告和 qualified-human 均无 authority。R17 的 `FAIL_GATE_OPEN_NOT_ASSESSABLE (0/1/2/1)` 与 human `0/16` 原样携带并进入最终双审计。

## 2. 执行策略与为什么不重复调用 embedding

四项修复全部位于 frozen union 之后的 route projection、deterministic semantic compiler 与 source→compiled provenance，不改变 query、source/object inventory、0.6B vectors、96-candidate union 或 raw rank permutations。因此 R12 默认采用：

- 以 R11 canonical raw execution SHA `0e9e4456ba75ecd07bc2e3bd6d5deddafc1972ba19700b029b2e6793e99f7458` 为唯一 frozen retrieval input；
- zero-call preview 和后续 exact R12 attempt 都做新的、digest-bound deterministic compilation；
- R12 exact attempt 仍有 exclusive receipt、raw-first successor capture、atomic private/public 与 saved replay，但 `local_0_6B_embedding_batches=0`，network/provider/model/generation/external/4B/reranker=0；
- 新 raw successor 必须保存 R11 raw ref/SHA、canonical payload digest、reuse reason、candidate-generation-equivalence proof 与 zero-call counters；不能只复制一个无 lineage 的文件。

这不是为了省成本删除研究工作，而是避免对完全相同的 frozen candidate set 重跑同一模型。task-specific `TokenBudgetBasis` 必须写明 node purpose、input 规模、required outputs、schema burden、materiality、可比 R11 evidence、reasoning/stop 行为，并明确本阶段模型 token/embedding budget 为 0。

如果实现或 preview 证明任何 changed path 会改变 query、vector、candidate union、raw ranking或 candidate-generation identity，则立即停止 saved-raw 方案；不得静默复用，必须另写 authority 决定是否允许一次 fresh 0.6B batch。

## 3. 依赖顺序

`R12-00 failure freeze → R12-01 route identity registry → R12-02 structural clause ownership → R12-03 governing price head → R12-04 proof-preserving transformation → R12-05 compiler/runner/public contract → R12-06 behavior tests and layered gates → R12-07 zero-call full-corpus preview → R12-08 implementation/policy/exact attempt/replay freeze → R12-09 fresh dual audit`

任一 ticket 未通过，后续 ticket 不得开始。policy 前必须有 clean/synced implementation commit；exact attempt 前必须有只改 policy 的 authority commit，且 `HEAD==upstream`。

## 4. Tickets、输入输出、验收与停止条件

### R12-00：前序身份、失败与质量基线冻结

责任阶段：S1 / 03B governance。

输入：R11 fixed manifest、R11 fresh fail audit、immutable R11 receipt/raw/private/public、R11 author worklogs、03A-R2 residual route program、R17 14-file bundle。

输出：

- 34/34 manifest identity、Git topology、14/14 policy inputs、33/33 implementation bindings与 R11 raw SHA 复验；
- 四个 exact finding ID、攻击族和 owner stage；
- R11 bounded passes、六 target count/family/rank与 R17 `0/18` citation、14/9/4/10/4 crosswalk、WWC 0/6、Facts 72/36、human 0/16 carry-forward。

工程验收：所有 SHA/size/result digest 精确；任何漂移立即停止。计划与 implementation 阶段不得创建 policy、attempt 或 result。

模型输出验收：证明 R12 修复位于 raw union/rank 之后，否则不得使用 zero-model execution contract。

研报质量验收：明确 R12 只移除未来伪证据风险，不补 R17 逐 Claim citation，也不把当前 gap 判作 public non-disclosure。

### R12-01：恒常 RouteContractIdentityRegistry v1

责任阶段：S1 / 03B downstream route projection。

输入：

- immutable `configs/retrieval/fin_ia_0_1_3_s1_dell_report_residual_source_ladder_program_v1_1.json`；
- R11 target dispositions与完整性结果；
- 03A route family registry、target program digests 和 per-contract digests。

输出：每个 03B target 的恒常 route identity row，至少包含 internal target ID、03A target ID、all resolvable external route IDs、mandatory external route IDs、contract digests、active/inactive disposition、registry source digest与 row digest。

五个当前 `external_required=true` target 的 mandatory external IDs 精确冻结为：

- ASP：`official_issuer_regulator`、`product_procurement_deployment`；
- capacity release：`named_supplier`、`official_issuer_regulator`；
- capacity utilization/yield：`industry_primary`、`named_supplier`、`official_issuer_regulator`；
- HBM supply：`industry_primary`、`named_supplier`、`official_issuer_regulator`；
- units：`industry_primary`、`official_issuer_regulator`。

规则：

1. local `local_data_object_index_sql` contract 必须继续保留在恒常 registry，但不得混入 external mandatory IDs；03B 已证明 local repair target count=0。
2. `external_required=false` 只改变 active disposition，不删除 route identity。
3. `external_required=true` 强制 mandatory external IDs 非空、全部存在于绑定 registry、target ID 一致、digest 匹配且 route family 非 local。
4. compiler 不得从 immediate predecessor 的 conditionally-cleared field恢复 authority；predecessor 只用于 comparison，不是 source of truth。
5. public projection只暴露安全的 route IDs、状态和 digest，不泄漏 query template、URL、私有 path或未授权执行参数。
6. author comparison必须逐 target 比较 exact route IDs、顺序无关集合 digest、external-required 与 scope。

行为验收：ASP `true→false→true` 后恢复同一两个 external IDs；任一 ID 删除、伪 target、伪 digest、local 混入 external、required=true + empty list全部 fail closed。当前五 target每项均有非空可解析 IDs，supplier current complete 不被误授权 external。

模型/研究质量：route registry只恢复“下一阶段可枚举合同”，不执行来源、不证明 exhaustion、不关闭 gap，不授予 Evidence。

停止条件：03A program digest 不匹配、目标映射一对多/缺失、mandatory route 不可解析、public projection泄漏或任何 target 被静默省略。

### R12-02：StructuralClauseOwnershipDecision v3

责任阶段：S1 predicate-frame segmentation 与 role isolation。

输入：case-preserving aligned surface、normalized tokens、所有 predicate candidates、coordinator左右 span、material role spans、function-word/adjunct grammar evidence与前序 frame state。

输出：沿用四个 typed state，并新增结构证明字段：

- `non_clause_continuation`
- `shared_subject_proved`
- `independent_owner_proved`
- `ambiguous_material_boundary`

每项保存 all predicate candidates、chosen predicate、owner-candidate span、fronted-adjunct structural span、shared-subject proof、independent-owner proof、material-right-surface proof、collision evidence、case-independence flag、isolation decision与 digest。

规则：

1. owner proof 不依赖首字符大写；case 只保留作 provenance，不能决定 split/merge。
2. 不再以“第一个 predicate token”决定 owner。必须评估全部 predicate candidates；若早期 token 既可能是 entity surface 又可能是 predicate（rose/target/will 等），优先检查后续 clause predicate与 owner NP 结构，无法唯一证明即 barrier。
3. material right surface 只在结构上证明 shared subject 时可复用左 owner；不能证明时一律隔离为 independent/ambiguous，左右 material roles 绝不 union。
4. 未知 verb 不默认 `no_split`。右侧存在 material product/price/relationship surface且共享主语未证明时，即使 verb 不在词表也形成 barrier。
5. fronted adjunct 由“function-word/preposition/temporal-or-instrument phrase + 后续 finite predicate/auxiliary + 无 owner NP proof”结构识别，不用 exact phrase白名单决定。未见 lexical content可以 typed ambiguous，但不能把 adjunct 当 owner。
6. compound subject、object list、bare discourse continuation与真正 predicate-offset-zero shared subject继续保留；alignment 不可无损时 fail closed。

对抗验收：

- `eBay Systems wugged`、`vanadium labs zorps`、lowercase `rose systems offered` 均不能与 Dell 左 actor union 成 complete；Title Case/lowercase/case-mixed mutation verdict同义。
- `in the following quarter`、`under the framework`、`after quarter-end`、`pursuant to the master services agreement` 的 shared-subject positives不误拆；同表面的显式右 owner control必须 split。
- owner 长度、unknown verb、predicate collision、adjunct词面使用参数化 mutation，不能靠加入公司名或整句白名单通过。

正向验收：R11 offset-zero continuation、auxiliary+adverb、compound/shared subject、对象列表和 bare continuation不退化。任何新增 partial必须有 typed reason和 family-level delta。

模型/研报质量：deterministic owner proof决定 attribution ceiling；embedding相似度不能补 owner。任何 ambiguity 保留为 typed gap，Writer 不得把第三方价格或供应事实写成 Dell-owned fact。

停止条件：任一跨 clause false-complete、case-dependent verdict、unknown material right merge、合法共享主语无理由丢失或新增 owner/entity白名单成为唯一修法。

### R12-03：GoverningPriceHeadProof v2

责任阶段：S1 ASP argument relation。

输入：clause-local quotation/sale predicate、argument group、nominal chunks、prepositional/complement edges、product/hardware span、price span、connector candidates与 competing head evidence。

输出：

- `proof_state=affirmative|ambiguous|unproved`；
- governing nominal head span/class/proof；
- priced object、specific product、price、connector span；
- complement chain、competing head rows、proof type、normalized proof identity与 digest。

规则：

1. 先证明 argument group governing priced head，再评估最近 object↔price connector；不得反向从 `hardware at price` 推断 hardware 一定是最高 governing head。
2. `<governing nominal phrase> for/of/on <hardware/product NP> at/for price` 默认存在 competing-head ambiguity；只有结构上独立证明 governing phrase本身是 price predicate/price noun且明确把 price绑定product时才可 affirmative。
3. service/freight/lease/financing/support/contract taxonomy只用于解释，不是安全边界。任意 nonce nominal head 的同构句式必须 fail closed。
4. direct `product hardware for price`、`price for product hardware`、`product hardware priced at price` 与明确 purchase-price path保留 affirmative；多个 head、多个 object、跨 group或不唯一 connector保持 partial。
5. complete ASP必须有唯一 governing hardware/product price proof，且 proof identity进入 semantic signature。

对抗验收：maintenance service、delivery service、lease financing、support services、contract与至少三组 nonce governing heads全部 partial；把它们大小写、单复数和修饰词变异仍拒绝。R10/R11 contract amount、maintenance costing、delivery fee、lease payment继续拒绝。

正向验收：四类 direct positive继续 complete；support price + 独立 hardware price只选择有唯一 governing proof 的 hardware relation。

模型/研报质量：任何配置报价只可作为 bounded configuration observation，不得自动升级为 Dell company ASP；denominator、period与company-wide代表性仍待外源/Evidence门。

停止条件：最近 hardware span仍能覆盖更高层 nominal head、nonce攻击靠词表漏过、positive path无解释退化或多价格关系被合并。

### R12-04：ConnectorProofIdentity 与 lossless transformation v4

责任阶段：S1 source→compiled provenance。

输入：R12 ClauseOwnership/GoverningPriceHead frames、source/compiled aligned slices、connector surfaces、proof digests、normalized relation body与 span mapping。

输出：

- `normalized_proof_identity_digest`：包含 owner state、governing head class/edge、connector lexical class、product/object/price normalization，不含绝对 offset；
- `proof_span_mapping`：逐 role 保存 source/compiled text、相对与绝对 span、offset transformation、surface equality/approved normalization与 digest；
- typed `loss_flags`、`addition_flags`、`ambiguity_flags`、`proof_rebind_flags`；
- acceptance reason与 binding digest。

规则：

1. source/compiled proof digest不同不能被忽略；必须能由同一 normalized identity与验证过的 span-offset mapping解释。
2. connector lexical surface/class改变（如 `for→at`）默认 `proof_rebind` 并拒绝；只有预先冻结、双向可复证且不改变 relation direction/governing head 的 normalization规则才可接受，不能在运行时临时等价。
3. `representation_digest_equal=false` 且 proof identity/span mapping无法精确解释时，不得无 flag accepted。
4. price、product、predicate、owner、governing head、connector、proof type任一删除／新增／改绑均产生 typed mismatch并拒绝。
5. 纯切片 offset变化但 role surface、connector class、normalized proof完全相同，可在明确 offset map下 accepted。

验收：`for→at` probe必须 `accepted=false` 且有 `proof_rebind`；price 15→16、XE9680→XE9712、offered→sold继续 loss/addition/mismatch；合法 offset-only slice仍 accepted。所有 actual complete source families 100% accepted，failed-complete/unbound-complete/compiled-complete-without-source均为0；partial-only unbound逐 target解释，不冒充 lossless全量覆盖。

模型/研报质量：compiler transformation不能通过改写 connector“制造”更强关系；报告只能消费 source-bound proof，不消费 compiled-only complete。

停止条件：proof metadata只保存不比较、任一 rebind无 flag通过、complete source family失联或 compiled-only complete出现。

### R12-05：compiler、public projection 与 zero-model exact runner

责任阶段：S1 03B compiler/runner。

新建 R12 predicate/transformation/compiler/runner/tests，默认 schema/policy/public/private successor为 v2.1，attempt=`dell-rsq-03b-internal-chain-r12`。不改 active consumer或 R11文件。

compiler必须精确绑定：R11 policy/public/private/receipt/raw/fresh audit/fixed manifest、03A-R2 residual program、R17 audit与14-file bundle、source records、compiled objects、execution program、runtime registry/binding。route registry不能是未绑定的隐式全局读取。

runner合同：

- unique R12 receipt exclusive-create；
- R11 raw identity复验后，先落 R12 raw successor capture，再 deterministic compile；
- private/public atomic pair；terminal failure只保存 typed failure与安全digest；same ID no retry；
- saved replay从 R12 raw successor精确重编并要求 private dict与canonical bytes相同；
- counters：embedding/model/provider/network/generation/external/4B/reranker/retry/promotion/closure全0。

author comparison新增 exact route-ID集合/digest、proof-rebind counts、governing-head partial counts与 clause decision counts；不得像 R11 一样省略 route IDs。

public threat-first validator继续 fail closed；新增 route/proof字段必须 explicit allowlist，禁止 raw text、query template、URL、absolute/private path、credential与高熵 payload。

停止条件：任何 frozen input未绑定、raw reuse lineage不完整、counter非0、route/proof字段未比较、public schema依赖递归黑名单或 exact-once/raw-first/atomic contract退化。

### R12-06：直接行为测试与分层回归

责任阶段：S1 engineering verification。

测试至少覆盖：

- 四个 R11 finding 的 exact reproduction与正向 control；
- route true→false→true、ID删除/伪造/digest drift/local混入；
- clause case、owner长度、unknown verb、predicate collision、unseen adjunct参数化 mutation；
- governing head的 service/financing/contract和 nonce mutation；
- connector rebind、offset-only mapping、price/product/predicate/head mutation；
- inherited R9/R10/R11 negatives/positives/scope/public controls；
- zero-model exact-once、raw-first、failure receipt、atomic pair、saved replay与 public privacy。

分层门：

- T0：changed py_compile/pyflakes、new JSON/JSONL、diff、R11 immutable hashes、R12 import isolation、active baseline；secret scan仅在新增敏感输入/输出或freeze时跑，不在每个patch重复。
- T1：R12 direct，目标 `<90s`。
- T2：R11+R12 adjacent，目标 `<150s`。
- T3：Project OS、compiler/runner、S1 foundation seam，目标 `<180s`。
- T4 仅在 shared/active/runtime/dependency/config变化、影响范围无法证明或T1–T3暴露跨域问题时运行。隔离 R12 文件默认不跑约20分钟全仓pytest。

每门记录 count、duration、failure owner与T4 trigger；未跑T4不得写“全仓通过”。

### R12-07：immutable-R11-raw zero-call full-corpus preview

输入：1,888 source records、34,199 compiled objects、R11 raw 5×96→16，0 model/network/write。

输出并解释：

- 每 target source/compiled/union/final/rank；
- complete/partial family delta、clause decisions、governing-head diagnostics、proof-rebind counts；
- transformation total/accepted/failed、complete coverage；
- exact external route IDs与 registry resolution；
- 4B/reranker eligibility继续只是后续 changed-pool decision，不执行。

性能门：`<70s` warning，`>120s` hard stop。所有 delta 必须按 family/source解释；不得硬编码 R11 count 来掩盖正确语义变化。尤其要确认五个 external-required target exact route IDs均非空、supplier complete不误开 external、任何新增 ASP complete都具有 governing price proof。

停止条件：未解释 count/rank/family delta、伪 complete、route omission、proof rebind无 flag、complete coverage下降、compiled-only complete或 runtime超过120s。

### R12-08：implementation freeze、v2.1 authority、唯一 exact attempt 与 replay

implementation gate通过后：

1. clean commit/push冻结 implementation/tree；
2. 创建只改一个 v2.1 policy 的 authority commit并push；
3. clean/synced、exact parent/path、disk preflight与 outputs absent 后消费唯一 `dell-rsq-03b-internal-chain-r12`；
4. raw successor先落、private/public原子发布、same-ID失败不重试；
5. saved-formal replay要求 private dict/bytes/result digest完全相同；
6. reviewed-result commit、fixed 34+ manifest与新审计目标逐步冻结。

policy必须含 task-specific `TokenBudgetBasis`：purpose=deterministic route/semantic/provenance successor；input=R11 canonical raw 5×96、1,888/34,199 corpus；required outputs=route registry、proof frames、target ceiling、private/public、replay；schema burden=四套 typed proof；material risk=伪 attribution/ASP与漏执行梯子；comparable evidence=R11 exact raw/replay；model reasoning/token/embedding=0；stop=identity drift、candidate-generation change、counter非0、timeout或material delta。

### R12-09：fresh作者分离工程＋R17双审计

新的 clean/fork-none reviewer只读审：

A. fixed manifest、Git topology、R11 raw→R12 raw successor、exact-once与zero-model counters；
B. route identity registry、五 target exact IDs、true→false→true与 public safety；
C. clause open-vocabulary/case/adjunct、governing price head与 transformation proof identity；
D. current corpus delta、complete coverage与 public privacy；
E. R17逐 Claim citation、crosswalk、WWC、重复、8D与human carry-forward；
F. engineering、report-quality、qualified-human三个分离 verdict。

默认0 pytest；只有先给出 concrete material suspicion，才允许一组最小 direct in-memory probe。缺证据=`NOT_ASSESSABLE`，不是 PASS。任一新 P0/P1/P2 保留 R12 失败并继续留在03B；reviewer不能代签 qualified-human。

## 5. 汇总验收矩阵

| 层 | 必须满足 | 不能声称 |
|---|---|---|
| 工程 | 五个 external-required target exact IDs 非空可解析；case/open-vocab clause不跨事件union；governing head不伪ASP；proof rebind typed-fail；exact-once/privacy不退化 | 测试绿不等于general pass；author preview不等于independent pass |
| 模型节点 | R12 0模型的必要性由changed-path等价证明；raw/rank完全绑定；任何candidate-generation变化立即停 | 不得把embedding相似度当 owner/price proof；不得调用4B/reranker |
| Evidence/研究 | ambiguity保持typed partial；route ID只是可执行合同；current complete family全部source-bound | 不得把 planned route 当已补源、把0结果当public gap、把配置价当company ASP |
| 最终研报 | R17失败指标原样进入双审计；未来报告必须 exact citation appendix、crosswalk、operational WWC、去重、8D、human | R12 PASS不等于信源补齐、研报PASS、产品或发布通过 |

## 6. 全局停止条件

出现以下任一项立即停在责任 stage：

- route registry或R11 frozen identity/digest漂移；
- `external_required=true` 但 mandatory external IDs为空／不可解析／含local；
- unknown/lowercase independent material clause仍可跨事件complete，或合法shared-subject无解释丢失；
- governing非硬件 nominal head仍被hardware adjacency覆盖；
- connector/proof rebind仍无 flag accepted；
- current complete source family失联、compiled-only complete、public泄漏或raw reuse lineage不完整；
- preview出现未解释delta或超过120s；
- exact attempt已消费后失败：保留receipt/raw/terminal证据，不重试同ID；
- fresh审计出现任一material finding。

## 7. R12通过后的恢复顺序

仅当 fresh R12 engineering independent PASS：

`以R12精确IDs创建03C authority → 执行五条residual external ladders并形成route receipts → 重建changed candidate pool → 同池0.6B/4B mixed embedding shadow → 确有eligible候选时启用reranker → CandidateDecision/Evidence/qualified-human admission → Pack/Readiness → units/share→ASP/mix→PVM→产品利润/营运资金 → 受影响S3 → non-overwriting report successor与reader citation appendix → engineering/report/qualified-human三重验收`

在此之前，03B independent、03C、4B、reranker、G2/G3、S1/S2/S3、report quality、formal 8D、qualified-human、product/publication/release全部 false。
