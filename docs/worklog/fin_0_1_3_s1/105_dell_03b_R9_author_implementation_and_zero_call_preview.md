# S1 工作记录 105：DELL 03B R9 作者实现与零调用预演

日期：2026-08-27

状态：`R9-00～R9-06 author implementation, zero-call preview and local engineering freeze pass / implementation commit and push pending / no R9 policy, attempt, private or public result / fresh audit pending`

## 1. 本轮交付与权限边界

本轮严格执行工作记录 104 的 R9-00→R9-06，不创建 v1.8 policy，不消费 `dell-rsq-03b-internal-chain-r9`，不调用网络、Provider、generation、外源梯子、4B embedding 或 reranker，不做 CandidateDecision、Evidence/NumericFact promotion、gap closure、S2、S3 或报告生成。正式 R9 后续只允许五个冻结 request 的一次 fresh 本地 Qwen3-Embedding-0.6B query batch；本轮 preview 仅重编 immutable R8 saved raw execution。

R9 仍是同一 S1/03B stage 的 non-overwriting successor。它修复 R8 fresh audit 的 general frame/scope/anchor/provenance finding，但不会自动关闭四条 residual 外源、R17 研报质量、qualified-human、S1/S2/S3、产品、publication 或 release。

## 2. R9-01～R9-03：typed frame、scope 与 argument-group anchor

新增 `src/retrieval/dell_report_predicate_frames_r9.py`：

- `FrameBoundaryDecision` 显式记录 split、compound-subject、shared-subject、scope-attach 与 no-split 决策、左右 predicate/subject exact spans 和稳定 digest；无逗号的独立事件不能再借用另一 predicate frame 的角色，compound company subject 仍保留。
- `PredicateFrame` 增加 `actuality`、`lifecycle_status`、`speech_mode`、`assertion_owner`；demonstrative revocation/discontinued、exploring、analyst attribution、third-party/unconfirmed/alleged 等状态进入 frame-local typed semantic state。
- coreferential state modifier 不再文本 merge，而是保留独立 modifier frame，并以 `ScopeEdge` 的 source modifier ID、target assertion ID、evidence span、target predicate span和 digest 显式附着。
- `ArgumentGroupBinding` 同时保存 predicate、object、product、price spans、object class、typed attachment、ambiguity 和 digest。`USD 150 support + USD 15 hardware` 只能将 15 绑定到 hardware；support-only、freight、financing 或不能唯一证明 locality 的价格 fail closed。
- semantic signature 只由 target、标准化 role/value multiset 和 typed scope state组成；representation digest 继续包含 exact spans、source kind 和记录形态，避免把“表示相同”误写为“语义相同”。

## 3. R9-04：source→compiled FrameTransformationBinding

新增 `src/retrieval/dell_report_frame_transformation_r9.py`：

- frozen `RoleTransformationMapping` 与 `FrameTransformationBinding` 保存 canonical source family、source/compiled frame ID、representation/semantic digest、source/compiled spans、object/window IDs、transformation type、逐 role 映射、loss/addition/ambiguity flags 和 self-digest。
- complete source frame 必须在该 family 的全部 compiled windows 中找到同 semantic signature 的 frame；不能再用“最佳 source package 对最佳 compiled package”替代 provenance pairing。
- complete family 只有 lossless binding 才能通过；partial family 的缺失或语义损失保留为 explicit diagnostic，不能被计入 complete，也不冒充 public-information gap。
- representation 不同而 semantic signature 相同是合法 bounded transformation；role loss、role addition、target/state mismatch、缺 compiled frame 均 fail closed。

## 4. R9-05：compiler、runner 与 exact-once 合同

新增 `src/retrieval/dell_report_internal_chain_ceiling_r9.py` 与 `scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r9.py`：

- compiler 绑定 R8 policy/public/private/receipt、fresh R8 failure `0/0/3/0`、R17 `FAIL_GATE_OPEN_NOT_ASSESSABLE` 的 `0/1/2/1`、R17 固定 14 文件 bundle、source/object/runtime/execution inputs、implementation SHA 与完整 `TokenBudgetBasis`。
- runner 强制显式 `preview|formal|replay` 模式；formal 必须 clean/synced、authority parent 精确等于 implementation、authority commit 只改 policy、canonical paths 无碰撞、磁盘门通过。
- attempt receipt 使用 exclusive create；模型返回后先写 immutable raw capture，再 compiler；terminal failure 只保存 stage 和 exception type，不保存异常消息；private/public 通过临时文件+hard-link pair 发布，第二个 publish 失败会回滚第一个 final。
- replay 从 R9 raw capture 重编，要求 private dict 与 canonical bytes 均完全一致。public projection复用冻结的 R8 threat-first validator，并在投影前精确删除 R9 两个 private transformation surface，未知字段继续 fail closed。
- 正式 authority 只允许一次 fresh 本地 0.6B query embedding batch；4B、reranker、network、external、promotion、closure 和下游 authority 全 false。

## 5. 作者期发现并修复的问题

1. 初版 transformation pairing 将 best source package 直接配 best compiled package，造成 current corpus 的假 provenance gap。现改为在同 canonical family 的全部 compiled windows 中按 semantic signature 匹配，再按 completion rank/object identity 稳定选择。
2. 初版 compiler 只重用 R8 raw execution，和 R9-07“formal 必须 fresh 0.6B batch”矛盾。现 compiler 显式接收 execution 与 SHA；preview 传 R8 saved raw，formal runner 执行一次 current runtime 后 raw-first capture。
3. 初版说明把整个 R9 写成 zero-call replay。现合同明确：只有 preview 是 zero-call；formal 是一次 fresh local 0.6B batch。
4. 直接测试最初把 exact sentence slice 强行断言为 representation unequal；该样本实际 representation 相等。现 integration 测试承认 exact slice，另由 transformation unit test 独立覆盖“representation 不同但 semantic 相同”。
5. 14-file drift test 最初先被绑定 digest 门挡住。现测试重绑故意篡改件的 digest，确保真正进入“必须恰好 14 文件”的语义门。

## 6. Immutable-R8-raw 零调用全量 preview

命令：

`python scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r9.py --mode preview`

结果：

- source records=`1,888`；compiled objects=`34,199`；elapsed=`39.649437s`，低于 70s warning/120s hard stop；preview digest=`c515f44d8f4b5e62651f800b6d58c7fb7f6072cc4ed18c8e15b84b5ebe32bb7b`。
- ASP R8→R9=`1/1/1/1 rank2`；supplier=`3/3/2/1 rank2`；capacity release、observed yield/utilization、Dell-HBM bridge、Dell company physical units 均=`0/0/0/0`。
- 六个 target 的 complete transformation coverage 全为 true；unbound complete source、compiled complete orphan、local repair 均为 0；完整计数和排序无 unexplained delta。
- partial transformation diagnostics：ASP 154、capacity release 70、yield 0、HBM 7、supplier 21、units 60，共 312。它们是 partial family 的显式 loss/missing-match receipts，不是 complete materialization failure，不得进入 Evidence 或 gap closure。
- external route required target=`4`；4B embedding eligible=`0`；same-pool reranker eligible=`0`。这不删除 4B/reranker 方案：后续只有真实新候选池产生 recall/ranking eligibility 时才运行，避免对当前已 rank2 或 target-not-in-pool 情况做无效重排。
- model/provider/network/generation/external/4B/reranker/retry/mutation/promotion/closure/write 均为 0。

## 7. 风险分层验证

- T1 R9 direct：`56 passed in 8.88s`。
- T2 R8+R9 adjacent：`153 passed in 21.68s`。
- T3 Project OS + S1 foundation：`93 passed in 40.62s`。
- compileall、7 个 changed Python 文件 pyflakes 与 active import isolation 已通过；pyflakes 曾发现一个未使用 `defaultdict` import，已在 owning file 删除并复验。
- active baseline=`213 Python / 8 frontend / 5 detectors / 28 resources / 0 forbidden`；8 个 Project OS JSONL=`1,319 rows / all parse`；repository secret scan=`8,179 files / 0 findings`。
- T4 未运行。R9 只新增隔离 module/runner/tests，没有修改 R8、shared validator、active Runtime、registry、dependency 或 pytest 配置；T1～T3 无跨域失败，import graph 未发现 active consumer。因此 `risk_tiered_test_evidence_policy` 的 T4 trigger 当前逐项为 false。R8 的 `1823 passed, 2 skipped` 不能冒充 R9 direct 证据，但其 shared/active freeze receipt也没有因隔离新增文件自动失效。

Implementation freeze 的行为、静态、活动图、JSONL 和 secret 门已完成；精确 staged diff/commit/push 是剩余 Git closeout。Policy、attempt 与 formal output 继续 absent。

## 8. 仍未完成的产品与研报质量边界

- R9 policy、formal attempt、raw capture、private/public result、exact replay、immutable audit manifest 和 fresh author-separated dual audit均不存在；当前只能写 `author implementation + preview`，不能写 03B independent pass。
- 上一版研报的信源缺失没有全部解决：capacity release、observed yield/utilization、Dell-HBM bridge、Dell company-period units 四条 residual 外源梯子仍未执行；必须在 R9 fresh audit pass 后逐条 capture/admit/recompute。
- 0.6B/4B mixed embedding shadow 与 reranker仍保留，但必须消费真实 candidate pool eligibility：target 不在 pool 先补源，target 已在 rank2 不为“证明模型更大”而重排。
- Evidence admission、CandidateDecision、人工证据验收、Pack/Readiness、S2 units/share→ASP/mix→PVM→产品利润/营运资金、受影响 S3 动态单元和非覆盖式新报告均未开始。
- R17 14 文件字节冻结，继续为 `FAIL_GATE_OPEN_NOT_ASSESSABLE`：reader-visible citation/source appendix、EV→exact passage/URL/locator、14/9/4/10 crosswalk、六 WWC operationalization、事实去重/密度、02B `0/16`、formal 8D 与 qualified-human 均未通过。后续独立审计必须同时审 R9 工程和研报质量，不能只看代码。

## 9. 下一合法顺序

1. 完成 T0/Project OS/Git implementation freeze，形成 focused implementation commit 并 push。
2. 仅在 clean/synced implementation 上生成绑定 commit/tree/SHA/TokenBudgetBasis 的单文件 v1.8 policy，形成 policy-only commit并 push。
3. 执行唯一 formal R9，立即 raw capture，生成 private/public；用 saved raw exact replay/reprojection封印。
4. 提交 immutable public/model-run/Project OS result，建立固定 audit manifest；启动全新 fork-none、作者分离、只读 reviewer，同时审工程与 R17 研报质量。Reviewer 不重复全仓 pytest，只有具体 material suspicion 才跑 targeted/mutation。
5. fresh audit pass 后才进入四条 residual 外源→真实 candidate pool→条件式 0.6B/4B/reranker→Evidence/human admission→Readiness→S2→受影响 S3→非覆盖式新报告→工程/研报/qualified-human 三重验收。
