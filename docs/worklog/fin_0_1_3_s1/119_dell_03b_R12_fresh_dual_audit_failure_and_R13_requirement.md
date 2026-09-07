# S1 工作记录 119：DELL 03B R12 fresh 双审计失败与 R13 要求

日期：2026-08-28

状态：`R12 immutable exact execution retained / current stored result PASS_BOUNDED / fresh engineering FAIL / R17 report quality FAIL_GATE_OPEN_NOT_ASSESSABLE / same-stage R13 required`

## 1. 结论先行

全新 `fork_turns=none`、作者分离、只读 reviewer 对 fixed R12 engineering bundle 26 项与 R17 report-quality bundle 14 项完成 A～F 双审计。reviewer 全程 0 写入、0 commit/push、0 formal attempt、0 pytest、0 network/provider/model/external/embedding/4B/reranker；只在形成明确怀疑后执行一次最小内存 mutation probe，未执行第二个 probe。

- R12 implementation／reviewed result 新 finding：`P0/P1/P2/P3=0/1/2/0`。
- fixed-manifest envelope 单独 finding：`0/0/1/0`。
- 本次 R12 合计观察：`0/1/3/0`。
- R12 engineering=`FAIL_SAME_STAGE_03B_MATERIAL_FINDINGS`，R12 independent=false，03B independent=false。
- R17 byte-identical carried finding=`0/1/2/1`，verdict=`FAIL_GATE_OPEN_NOT_ASSESSABLE`。
- qualified-human=false，02B decisions=`0/16`。
- 下一合法动作只有 FIN 0.1.3 / S1 / 03B non-overwriting R13；03C、0.6B/4B mixed shadow、reranker、Evidence、Pack/Readiness、S2、S3、新报告、formal 8D、product/publication/release 均无权限。

机器可读审计记录：

`configs/audits/fin_ia_0_1_3_commit_057eb98e_dell_03b_r12_fresh_dual_audit_fail_v1_0.json`

result digest=`d8bc52045773ca5c1f31d148b9a097da8f193410ddac3799284f854c5b75af9e`。

## 2. 必须分开的两个事实

### 2.1 当前 immutable R12 stored result 没有被审计证明算错

独立审计通过并重算了：

- manifest 40/40 文件 SHA、bytes、嵌套 digest 与 Git implementation→authority→reviewed-result→manifest 线性拓扑；
- policy 15/15 inputs、37/37 implementation bindings与 task-specific zero-model `TokenBudgetBasis`；
- receipt exclusive-create、raw-first、落盘重读、private/public atomic publish、R11→R12 raw execution exact equality；
- canonical raw=`1,527,387 bytes`、SHA=`0e9e4456...f7458`，5 requests、338 union、80 final，R12 新增调用与禁止计数全为 0；
- 六 target 恒常 route identity；五个 external-required target exact IDs均非空可解析，ASP exact 两条 route；
- 全部 1,601 transformation binding／role mapping ID、digest、source frame、compiled object与 connector proof links；
- 实际计数 `1,601=1,277 accepted+324 failed`，unbound partial=380、failed-complete=0、unbound-complete=0、compiled-complete-without-source=0、proof-rebind=0；
- supplier=`3/3/2/1 rank2`，其余五项=`0/0/0/0`；实际 stored public privacy=`PASS_BOUNDED`。

因此 R12 继续作为不可覆盖的精确执行与当前样本证据保存。不能把 fresh audit FAIL 误写成“R12 现存 1,601 条结果已观察到错误”，也不能把当前数字正确误写成“通用能力已通过”。

### 2.2 R12 一般合同仍有材料性 fail-open

R12 的失败是：公共投影信任边界不能从持久化权威表面重算全部材料摘要，且两个未覆盖语言结构仍可制造伪 ASP complete。只要这些一般合同失败，03B 就不能成为外源、Evidence 或报告的资格前置。

## 3. 三项实现 finding

### R12-P1-PUBLIC-PRE-DISCARD-SUMMARY-RECONCILIATION-FAIL-OPEN

`build_dell_report_internal_chain_ceiling_r12_public_projection` 在丢弃 private surfaces 前，会重算 binding count、accepted/failed、binding digest、proof-rebind与部分 list count；但对以下字段只检查类型或布尔值：

- `failed_complete_binding_count`；
- source/compiled governing-head partial counts；
- source/compiled clause ownership decision maps；
- `complete_transformation_coverage_pass`。

唯一最小 probe 将真实 ASP `failed_complete_binding_count` 从 0 改为 1、重新签发 private self digest 后，public projection 仍接受并生成 public digest。作者 mutation test只覆盖 `binding_count`，没有覆盖上述字段。

更深的持久化不一致是：compiler 在完整 corpus 上计算 clause maps，随后只保存 `classification != not_target_semantic_equivalent` packages。六 target 的 saved clause maps因此都不能从 persisted packages复算。ASP 示例：

- source saved `{no_split:1308, shared_subject:604, split:329}`，persisted package重算 `{566,327,208}`；
- compiled saved `{1795,743,522}`，persisted package重算 `{965,467,336}`。

这些差异不证明 saved full-corpus map错；它证明 immutable artifact 没有足够 reconciliation surface，public projector只能信任不可自证摘要。

R13 必须建立一套“唯一权威持久化表面→完整材料摘要”的派生函数；compile 与 public projection调用同一逻辑并做 whole-summary equality。任何仍需要全 corpus口径的字段，必须持久化足够的紧凑逐行 receipt，或明确降级为非权威且不进入 public/admission gate；不得继续保留无法复算的权威摘要。

### R12-P2-OWNERLESS-UNSEEN-FINITE-HEAD-CROSS-EVENT-ROLE-UNION

反例：

`Dell quoted support for USD 150 and repaired PowerEdge XE9680 hardware for USD 15.`

R12 的 unknown right-clause barrier 要求 material surface 前至少出现“owner token(s)+unknown head”两部分。`repaired` 只有一个词，且不在 frozen predicate hints，于是 barrier返回空、boundary落到 `no_split/non_clause_continuation`。后续 argument separator虽拆开两个价格组，ASP frame仍可能借左侧 Dell/quoted 与右侧 hardware/product/USD15组成 false complete。

R13 不能只在 unknown verb前找显式 owner；必须识别 coordinator后的新 event head。即使语法主语由 Dell共享，也不能让上一事件的 `quoted/offered/sold` 谓词跨新事件延续。one-word unseen finite head、大小写与词形 mutation必须形成 event-role isolation；真正同一 predicate的对象列表／复合商品正例必须保留。

### R12-P2-PARTICIPIAL-GOVERNING-HEAD-BYPASS

反例：

`Dell quoted a maintenance service covering PowerEdge XE9680 hardware at USD 15.`

R12 higher nominal-head detector只识别 `for|of|on` product complement。`covering/including/bundling` 等 participial/relative edge绕过 barrier，最近的 `hardware at USD15` 被误作 affirmative price attachment，service/bundle head不参与竞争。

R13 必须把 prepositional、participial与 bounded relative complement统一成结构 edge；先证明唯一 governing priced head，再考虑最近 connector。service taxonomy只能解释，不能成为安全边界；nonce heads与 direct hardware price positives必须共同进入参数化测试。

## 4. 独立 manifest envelope finding

fixed manifest v1.0 的生成器把 Git helper整段输出 lower-case，导致 exact changed-path contract有 7 个 case-sensitive 字符串不等：implementation 3 个、reviewed result 4 个。内容 population在 casefold下相同，commit/tree/hash都正确，所以该 finding不污染 R12结果身份，但会在 case-sensitive平台破坏可移植审计。

v1.0 必须保留为失败证据。后续生成 non-overwriting、case-correct successor manifest；路径必须来自 Git原始 path bytes，大小写仅可用于比较键，不能覆盖展示/权威值。至少冻结 `zh-CN`、`README`、`R13` 和 uppercase model-run 文件名。

## 5. R17 研报质量继续失败

R17 14项 bundle逐 byte不变，因此没有任何研报修复可主张：

- reader report 21,118 chars、25个 source markers、59次 EV、18 unique EV；reader URL=0，无 citation/source appendix；
- exact EV→passage/title/issuer/date/period/locator/stable URL=`0/18`，逐 Claim语义支持仍 `NOT_ASSESSABLE`；
- crosswalk `14/9/4/10/4` 存在但未被 R17绑定或消费；
- WWC 6项中 fully operational=`0/6`；
- `units/share→ASP/mix→PVM→产品利润→营运资金`完整量化桥为空；
- Facts=`72 occurrences/36 unique/36 duplicates`；
- formal 8D=null，英文-only报告未证明 bilingual semantic equivalence；
- 8 requests／18 items／16 human-required，qualified-human decisions=`0/16`。

R13 是 S1 资格修复，不得声称补齐信源、S2或R17。它的 fresh reviewer仍须把 R17作为独立审计域；未来只有完成外源、Evidence与S2后，才能生成 non-overwriting报告 successor，并要求 reader citation appendix、完整 crosswalk、operational WWC、去重、formal 8D、双语语义等价与 qualified-human验收。

## 6. 网络连接重置与本轮成本边界

历史多次 GitHub connection reset已在 R12 阶段定位为 Git未继承 Windows Internet Settings代理。仓库级：

`http.https://github.com.proxy=http://127.0.0.1:6696`

已通过 listener、default `git ls-remote origin HEAD` 和多次 non-force push持续验证。本轮审计起止本地 upstream相等、ahead/behind=`0/0`。不修改 global/system代理；若本地 listener缺失必须 fail closed并报告外部依赖，不能静默回退到已知不稳定的 direct 443。

审计耗时的根因不是 pytest，而是 reviewer逐文件复核40项 hash、1,601 bindings、34,199-object衍生口径与 R17 reader surface。后续 reviewer默认继续 0 pytest，只在具体怀疑后允许一个最小 probe；作者端继续 T0/T1/T2/T3分层，禁止每次小改跑约20分钟全仓 T4。

## 7. 下一合法顺序

1. 固化本工作记录、机器审计与 Project OS反对意见。
2. 先完成 R13 program-level execution plan；不得边写代码边补计划。
3. non-overwriting R13实现 authoritative reconciliation、event isolation与 participial governing-head proof；R12所有 attempt/raw/private/public/manifest保持 immutable。
4. 先 T0/T1，再相邻 R12/R13 T2，必要时 Project OS／S1 seam T3；只在风险触发时跑 T4。
5. 用 immutable R12 raw successor执行零调用 preview；逐 target解释所有 summary/count/family/rank变化。
6. author gate通过后，才允许 implementation commit→policy-only authority→唯一 R13 attempt→saved replay→reviewed result→case-correct fixed manifest。
7. 再启用另一名全新、作者分离、只读 reviewer；任一新 P0/P1/P2继续留在03B。
8. 只有 fresh R13 engineering independent PASS后，才讨论五条 exact external ladders；其后才是 changed-pool 0.6B/4B mixed shadow、条件 reranker、CandidateDecision/Evidence、Pack/Readiness、S2、受影响S3与新报告。

当前不能授权任何外源、模型、Evidence、S2、S3或发布动作。
