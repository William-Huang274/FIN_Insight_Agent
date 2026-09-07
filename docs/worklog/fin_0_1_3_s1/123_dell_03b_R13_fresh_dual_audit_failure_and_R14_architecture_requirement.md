# S1 工作记录 123：DELL 03B R13 fresh 双审计失败与 R14 架构要求

日期：2026-08-28
状态：`R13 immutable exact execution retained / current artifact PASS_NARROW / general engineering FAIL 0-1-2-0 / R17 report quality FAIL_GATE_OPEN_NOT_ASSESSABLE 0-1-2-1 / same-stage R14 architecture replacement required`

## 1. 结论先行

两名全新、`fork_turns=none`、作者分离、只读 reviewer 已分别完成 R13 工程合同和 R17／S1／S2／研报质量审计。两名 reviewer 均未写仓库、未 commit／push、未创建 formal attempt、未运行 pytest、未调用网络、外源、模型、embedding、4B 或 reranker；起止工作树 clean，HEAD 保持 `8dd03fa9b55477e08b3b14608e26359fa08b72a7`。

最终必须分开记录四个 verdict：

1. R13 Git／manifest／attempt／raw／private／public／当前已存计数：`PASS_NARROW_CURRENT_ARTIFACT_ONLY`；
2. R13 一般工程合同：`FAIL_SAME_STAGE_03B`，新 finding=`P0/P1/P2/P3=0/1/2/0`；
3. R17 研报研究质量：`FAIL_GATE_OPEN_NOT_ASSESSABLE`，carried finding=`0/1/2/1`；
4. qualified-human Evidence decision=`0/16`，S1／S2／S3／产品／publication／release 均为 false。

完整机器可读结论见 `configs/audits/fin_ia_0_1_3_commit_07909cc1_dell_03b_r13_fresh_dual_audit_fail_v1_0.json`。

## 2. R13 保留为不可变证据的通过面

下列事实已由 reviewer 独立复核，不因一般合同失败而撤销：

- fixed manifest 的 engineering 26＋R17 14=`40/40` 文件 SHA／byte size exact，45 个 declared values exact；
- implementation／authority／reviewed result 的 commit／tree／parent 和 case-sensitive changed paths=`16/1/8` exact；
- attempt 目录只有 receipt／raw／full result，无 terminal failure；
- R13 raw 与 R12 raw dict／bytes exact，canonical raw SHA=`0e9e4456...f7458`；
- private SHA／digest=`9502e498...e090e94c`／`0d58e3ea...ac68a055`，public digest=`d186be68...24dbe8d`，private→public exact rebuild；
- R13 新模型、Provider、网络、外源、embedding、4B、reranker、retry、mutation、promotion、closure 全为 0；
- transformation=`1,596=1,273 accepted+323 failed`，unbound partial=`379`，failed complete／unbound complete／compiled-only complete／proof rebind 均为 0；
- supplier=`3/3/2/1 rank2`，其余五 target=`0/0/0/0`；当前三条 complete supplier family 是前序冻结的真实 partnership／delivery read-through family；
- 未发现当前 formal 文件的 complete family、count、rank 或 route 已经算错。

因此 R13 必须保留为“当前 artifact 窄口径正确”的不可变运行证据；不能把 fresh audit FAIL 误写成当前 1,596 条结果已观察到错误，也不能把当前计数正确写成通用能力合格。

## 3. 两份审计的表面分歧与统一判断

研究质量 reviewer 确认 R13 已关闭 R12 的旧 P1：材料摘要字段可以从当前持久化 rows 完整重算，public projector 会检查 whole-summary equality。工程 reviewer 又发现新的、更深一层 P1：当前 rows 自己同时定义 package population 和 summary，projector 没有把 rows 与冻结 source／object 输入 population 做独立双射。

二者不矛盾：

- 已关闭的是“摘要能否从当前 rows 重算”；
- 未关闭的是“当前 rows 是否完整、无缺失、无重复、无 orphan、无跨 target 改绑”。

工程 reviewer 从真实 ASP target 删除一个 partial package row，同步重算全部 reconciliation summary 和 private self digest；source package count `844→843`，而 full-corpus population／scan digest保持不变。R13 projector 仍接受并生成 public digest。这证明 `persistedPackageMutationFailsClosed` 的旧 durable claim 过度，必须在 Project OS 更正。

## 4. R13-P1：缺少独立 InputPopulation authority

### 4.1 最早根因

`derive_private_semantic_reconciliation_summary_r13()` 只接收 persisted source／compiled package、binding 与 gap rows；compiler 在过滤 `not_target_semantic_equivalent` 后，同时把剩余 rows 当作 population 与 summary 输入；projector 再从同一批 rows 重算。这只能证明内部一致，不能证明对冻结 `1,888 source records / 1,862 canonical families / 34,199 compiled objects × 6 targets` 的完整覆盖。

现有 candidate ceiling 虽保存 full-corpus population 和 scan digest，projector 没有用它建立 exact keyset authority；`not_target` rows 在持久化前消失，也没有每个 expected input 的 outcome receipt。

### 4.2 R14 必须实现

1. policy authority 前生成独立 `InputPopulationManifest`，绑定 source／object SHA、全部 input IDs／digests、target set、canonical occurrence map、enumerator version和 expected cross-product keyset；
2. 对每个 expected `(target_id,input_kind,input_id)` 物化恰好一条 `PackageDecisionReceipt`，outcome至少为 `complete|partial|not_target|typed_error`；
3. manifest↔receipt 必须 exact bijection，missing／duplicate／orphan／wrong target／wrong input digest全部 fail closed；
4. `PackageRow`、candidate ceiling、coverage、route disposition和所有 summary只能从 manifest＋full receipts派生；
5. public projection必须显式接收 policy-bound manifest authority，不得再让 private packages自证完整性。

## 5. R13-P2：扁平 frame 跨事件拼角色

### 5.1 复现

以下均出现 false complete 或错误 topology：

- `Dell quoted support for USD 150 and shipped PowerEdge XE9680 hardware for USD 15.`：右侧 shipment 的 product／price借左侧 `quoted`；
- `Dell quoted support for USD 150, HPE shipped PowerEdge XE9680 hardware for USD 15.`：跨 owner 拼接；
- `NVIDIA allocated GPU capacity to Dell and shipped support in FY2026.`：右事件 period补左事件；
- `...and configured/delivered PowerEdge...USD 15`：known predicate 因 shared subject进入 `no_split` 后 false complete；
- `...and offered PowerEdge...USD 15` 的 complete verdict可能正确，但 accepted predicate仍指向左侧 `quoted`，说明 topology错误被 verdict掩盖。

### 5.2 最早根因

`FrameRecord`／`PredicateFrame` 没有 `event_scope_id`、predicate continuity或 typed role→event edges。known right predicate＋shared subject被保留在一个 record；ASP、capacity、yield、HBM、units extractors从整条 record搜索 actor／product／price／period／quantity，再把首个 predicate span写给所有 argument groups。Transformation只能检查同一扁平 parser的两份输出是否相等，不能发现两侧共同误解析。

### 5.3 R14 必须实现

- `EventNode`：event scope、predicate head、polarity、modality、actuality、lifecycle、assertion owner；
- `MentionNode`：entity／product／hardware／nominal／price／quantity／period exact span和type proof；
- `RoleEdge`：每个 required role明确连接到一个 event；
- `SubjectShareEdge`：只允许共享 actor，不允许继承 predicate／product／price／period／quantity；
- `TemporalScopeEdge`：period明确作用于哪个 event或经证明的 event set；
- 每个 coordinated predicate均产生独立 event scope；无法证明是 object list还是 event时，保留 partial；
- 每个 target声明允许的 event topology；supplier若需要 partnership＋delivery多事件组合，必须有显式 typed bridge。

## 6. R13-P2：价格 governing head仍靠 connector枚举

### 6.1 复现

以下结构同构句均被误判成 hardware ASP complete：

- `maintenance service with PowerEdge XE9680 hardware at USD 15`；
- `support plan incorporating PowerEdge XE9680 hardware at USD 15`；
- `financing arrangement bundled with PowerEdge XE9680 hardware at USD 15`；
- `service agreement encompassing PowerEdge XE9680 hardware at USD 15`。

### 6.2 最早根因

R13 只在固定 `for/of/on/covering/including/bundling/containing/comprising/featuring/relative` link regex命中后才搜索 higher nominal head。未枚举的结构同义 surface会退化为“最近 hardware-at-price”，错误写成 direct typed object。继续向 regex 加 `with`、`incorporating` 或 `encompassing`只会延长补丁循环。

### 6.3 R14 必须实现

- `NominalNode` 与 `ComplementEdge`／`RelativeEdge`／`ParticipialEdge`／`AppositionEdge`／`CoordinationEdge`；
- `PriceAttachmentEdge(price_id,priced_head_id,path,proof_state)`；
- 从 price沿结构路径解析唯一 priced head，再判断 product是该 head还是 higher service／finance／support／nonce head的 complement；
- connector surface只作 provenance，不作闭集真值；
- unknown／multiple／unparsed head或path、跨 event、多价／多头必须 partial；
- direct product-price、price-for-product、product-priced-at-price、explicit purchase/configuration price与合法 hardware bundle为正向控制。

## 7. R17、信源和 S2 仍未关闭

R13 工程失败不能覆盖或替代下列独立事实：

- R17 reader report=`21,118` chars、25 source markers、59 EV occurrences／18 unique EV，但 reader URLs=`0`、source appendix=false、EV→passage/title/issuer/date/period/locator/stable URL=`0/18`；
- crosswalk=`14 Pack / 9 acquisition / 4 Writer groups / 10 refs / 4 S2 bridge`，R17没有绑定或消费；
- WWC=`0/6 operational`；Facts=`72 occurrences / 36 unique / 36 duplicate`；bilingual和formal 8D均 `NOT_ASSESSABLE`；
- supplier read-through已从“本地完整包缺失”推进为“本地完整 candidate存在”，但仍是 candidate_not_evidence，R14后必须重算并做 CandidateDecision／Evidence admission；
- ASP、capacity release、utilization/yield、HBM、units五 target provisional local complete仍为0，R14独立通过后才可执行真实外源梯子；
- admission-held三项为 demand durability、AI working capital、product profit；必须先完成人工 admission，不能直接重复补源；
- 已证明 public／commercial／private information boundary数量仍为0；旧 `commercial_data_gap`只是分类标签，不是边界证明；
- S2已有13 source-visible observations和7 deterministic derivations，但 units/share、ASP/mix、PVM、product profit、AI working-capital attribution均不完整或不可计算；四个 explicit bridge gap仍 open，S2 stage=false；
- qualified-human=`8 requests / 18 items / 16 required / 0 decisions`。

## 8. 审计效率与测试策略

本轮 reviewer没有运行全仓 pytest。作者实现继续采用风险分层：

- T0：schema／static／diff／compile／关键 mutation；
- T1：R14 direct contracts与property／metamorphic suite；
- T2：R13↔R14相邻接口、runner、projection、transformation；
- T3：Project OS／active baseline／JSON／secret scan；
- T4全仓仅在共享 runtime改变、影响范围无法证明或T1/T2暴露跨域问题时执行。

pytest总数不能替代 oracle质量。R14必须记录 critical mutation kill matrix、固定seed与最小反例；工程 reviewer仍以manifest、静态证据和最小探针为主。

## 9. R14 pre-formal门与禁止自动开 R15

R14 与以前最大的流程差异是：**独立工程审查移到 formal之前**。

顺序必须为：

1. 冻结本失败审计、root cause与R14 architecture／oracle；
2. 实现R14但不创建policy或attempt；
3. T0/T1/T2与immutable R13 raw zero-call preview；
4. 由全新作者分离 reviewer审实现 commit、property oracle、mutation receipts、full-corpus keyset和count/family/rank delta；
5. 只有 reviewer给出P0/P1/P2=`0/0/0`，才允许policy-only authority与唯一formal attempt；
6. formal／replay后再做一次result identity／stored semantics审计。

若以下任一不变量仍失败，必须留在同一个R14实现周期修复；**不得自动创建R15继续打补丁**：

- package＋全部derived surfaces同步变化仍可通过；
- manifest↔receipt不是exact bijection；
- known／unknown predicate、shared subject、owner、period、product、price、quantity仍可跨event complete；
- 结构同构link/head词汇替换改变price attribution verdict；
- event／role／period／head／path topology rebind没有typed transformation failure；
- critical property mutant存活或full-corpus有silent drop；
- current supplier正例无解释退化，或count/family/rank/route delta不可解释；
- pre-formal或post-formal独立审查有任一材料P0/P1/P2；
- Git／input／population／policy／attempt／atomic／replay identity不exact。

若同一不变量在架构重做后仍失败，下一决策不是换编号，而是停止当前parser职责，选择更强的parser／IR，或把无法证明的结构永久路由为partial＋human review。

## 10. R14通过后的完整恢复顺序

只有R14 fresh engineering independent PASS后，才允许：

1. 五个exact external ladders；
2. capture→source→object→index／SQL→crosswalk重建；
3. changed pool同query／同corpus的0.6B baseline；
4. 4-bit 4B embedding shadow；
5. candidate已存在且确属排序歧义时的conditional reranker；
6. CandidateDecision与16项qualified-human Evidence admission；
7. Pack／Readiness／gap boundary重编；
8. `units/share→ASP/mix→PVM→product profit→working capital`；
9. 受影响S3动态单元；
10. non-overwriting新报告，补reader citations／source appendix／crosswalk／WWC／dedup／bilingual；
11. 分开的工程、研报质量、qualified-human产品验收与publication／release决定。

本记录不授权上述任何下游动作。
