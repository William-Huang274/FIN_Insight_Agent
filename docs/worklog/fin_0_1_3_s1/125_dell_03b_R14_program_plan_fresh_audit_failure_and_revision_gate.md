# S1 工作记录 125：DELL 03B R14 program plan fresh 审计失败与修订门

日期：2026-08-28
状态：`fresh author-separated read-only plan audit complete / PLAN_FAIL 0/3/2/1 / revision 1 written / implementation forbidden pending fresh re-review`

## 1. 为什么先停在计划层

Owner明确要求不再出现R1–R13式无限修复：先把一般合同、反例和停止条件审干净，再开始R14实现。于是本轮没有修改任何R14代码，也没有运行formal、pytest、模型、网络、外源、embedding、4B或reranker；只让一个`fork_turns=none`、作者分离、只读reviewer审查R13根因、R14计划与当前R13实现形态。

reviewer结束时：

- repository HEAD=`8dd03fa9b55477e08b3b14608e26359fa08b72a7`；
- reviewer writes／commits／pushes／formal／pytest／model/network calls均为0；
- 当前R14 implementation、policy、attempt、03C和所有downstream authority均为false；
- 审计结论=`PLAN_FAIL`；`P0/P1/P2/P3=0/3/2/1`。

这不是R13再新增一个产品版本，也不是R14实现失败；它是“原R14计划还不足以机器阻止下一轮局部打补丁”的pre-implementation failure。

## 2. 三个P1：为什么原计划仍可能无限修

### P1-1：pre-formal commitment仍可同源换签或被formal回抄

原计划有InputPopulationManifest和PreFormalDecisionCommitment，但没有冻结commit／parent／changed-path topology。Commitment由同一个compiler生成，本身不是独立truth oracle；若审查后重新生成一份Commitment，或formal直接复制preview vector/details，root equality和replay equality仍可通过，却没有证明compiler从source/object重新计算相同decision。

revision 1冻结：

- `I` implementation；
- parent=`I`的`B` manifest/preview bundle；
- parent=`B`的`A` author-separated audit receipt；
- parent=`A`且只改policy的`P`；
- policy绑定exact `I/B/A`、Manifest、Commitment和PASS receipt；
- formal compiler只能读取raw source/object、target contracts、manifest order和`I`；preview output只进入末端comparator；
- FAIL后只能同一R14创建新的`I′/B′/A′` cycle，旧bundle不可覆盖，不自动开R15。

### P1-2：event/price graph只有名词，没有可执行grammar

原计划要求EventNode、RoleEdge和PriceAttachmentGraph，但没有唯一tokenization、scope/event discovery、object-list、subject inheritance、nominal path、rule precedence和proof state。R13的verb/connector/service表完全可能改名为`hint/lexicon/cue`后继续决定complete。

revision 1新增：

- machine-readable `StructuralProofGrammar v1`；
- deterministic `TOKENIZE → SCOPE → EVENT-CANDIDATES → OBJECT-LIST → SUBJECT/TIME → NOMINAL → PRICE → TARGET` procedure；
- `PROVED/AMBIGUOUS/UNSUPPORTED/MALFORMED`与`C/P/N/E`唯一映射；
- vocabulary-use matrix，禁止verb/company/service/connector表直接决定event scope、priced head或complete；
- 六个完整target的required roles、role→event edge、event cardinality、temporal/quantity scope、typed bridge、forbidden inference和positive fingerprints；
- implementation freeze后才由reviewer生成fresh nonce event/head/link/owner holdout，防止作者只对已知例句调参。

### P1-3：mutation、audit和no-R15仍只是Markdown

原计划写了critical kill=100%和不自动开R15，但没有不可删减的mutant分母、pre/post audit receipt schema、lifecycle state或runner拒绝条件。作者少列mutant仍可声称100%，另一个policy也可绕开文字限制。

revision 1新增：

- `CriticalMutationManifest`与`CriticalMutationKillReceipt`；
- critical unexecuted／survived／excluded必须全部为0；
- `PreFormalAuditReceipt`、`PostFormalAuditReceipt`；
- `R14LifecycleReceipt`状态机；
- `R14_STOP_OWNER_DECISION_REQUIRED`下runner和03C/downstream preflight拒绝R15、03C、模型、Evidence、S2、S3和Writer；
- 只有OwnerDecisionReceipt可选择同一R14更换parser/IR、永久partial＋human或终止03B。

## 3. 两个P2：编码与发布仍有歧义

### P2-1：compact vector没有唯一bytes/detail/error合同

原计划同时允许“需说明N”detail，又要求detail与非N cell双向一致；也没有bit order、padding、domain separation和valid-input error budget。

revision 1固定：

- `C=00/P=01/N=10/E=11`；
- 每字节从高到低四cell，末字节unused low pairs必须为0；
- domain-separated root包含manifest/target/lane/length；
- 每个C/P/E恰一detail，每个N零detail；
- C必须有accepted topology/package，P必须有candidate proof/limitation，E只允许manifest预注册malformed key；
- ambiguity/unsupported只能P，内部异常terminal；
- 第二个decoder不得复用producer encoder/decoder/summary helper。

### P2-2：逐文件link＋rollback不等于crash-atomic transaction

当前D盘free=`518,934,528 bytes`，低于512 MiB formal floor=`536,870,912 bytes`，formal继续blocked。原计划还没有定义进程在第一个sidecar发布后崩溃时reader如何避免看到半组artifact。

revision 1新增：

- formal同一serializer的counting/hash sink逐artifact给出exact bytes/root；
- required-free逐项包含raw、receipt、private/public、sidecars、staging、publish duplication、scratch、replay、failure、runtime drift和safety；
- same-volume exclusive attempt reservation；
- `.incomplete` staging逐文件flush/`FlushFileBuffers`/reopen验证；
- transaction manifest与terminal marker；
- Windows no-replace same-volume directory rename；
- reader只接受final目录中marker＋manifest＋全部artifact exact的bundle；
- 每个write/flush/manifest/marker/rename边界均做subprocess crash mutation；失败保留immutable staging/failure evidence，attempt ID不复用。

## 4. 一个P3：4B不能变成无条件算力关卡

4-bit 4B方案仍保留，但revision 1把它改为conditional experiment。必须先证明changed pool中存在decision-relevant candidate、0.6B材料ceiling确由representation/semantic recall或排序造成，并预注册hypothesis、minimum gain、三案例regression ceiling、resource/cost/stop和独立TokenBudgetBasis；否则记录`SKIPPED_NOT_ELIGIBLE`并继续CandidateDecision，不加载4B。reranker同样只对“candidate已在pool且确为排序问题”授权。

任何未来paid/model node——03C付费检索、0.6B、4B、reranker、S3 Agent、Writer——都需单独task-specific TokenBudgetBasis，不能共享一份总预算，也不能因省钱静默删掉required research work。

## 5. 当前authority与下一门

| 动作 | 当前authority |
|---|---:|
| plan/audit/governance修订 | true |
| R14 implementation/tests/preview | false |
| R14 policy/formal | false |
| 03C/0.6B/4B/reranker | false |
| CandidateDecision/Evidence/Pack/Readiness | false |
| S2/S3/Writer/new report | false |
| product/publication/release | false |

下一门不是写R14代码，而是对revision 1再做一次fresh、作者分离、只读plan review。只有review verdict=`PLAN_PASS`且P0/P1/P2=`0/0/0`，R14 implementation才从false变为eligible。若仍有材料finding，先在计划层关闭，同一R14内迭代；不能靠继续写regex、换receipt名字或创建R15绕过。

## 6. 关联材料

- R13 fresh dual audit：`configs/audits/fin_ia_0_1_3_commit_07909cc1_dell_03b_r13_fresh_dual_audit_fail_v1_0.json`；
- R13 failure/R14 architecture requirement：`docs/worklog/fin_0_1_3_s1/123_dell_03b_R13_fresh_dual_audit_failure_and_R14_architecture_requirement.md`；
- R14 revised program plan：`docs/worklog/fin_0_1_3_s1/124_dell_03b_R14_program_level_architecture_execution_plan.md`；
- 本次plan audit machine receipt：`configs/audits/fin_ia_0_1_3_head_8dd03fa9_dell_03b_r14_program_plan_fresh_audit_fail_v1_0.json`。
