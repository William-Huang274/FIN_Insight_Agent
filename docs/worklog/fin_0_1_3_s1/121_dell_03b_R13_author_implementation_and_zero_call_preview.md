# DELL-RSQ-03B R13 作者实现、R12 直系谱系修正与零调用预演

日期：2026-08-28

状态：作者实现、T0～T3 分层门与 immutable-R12-raw 零调用 full-corpus preview 已通过；R13 implementation commit、policy-only authority、正式 attempt、result、case-correct manifest 与 fresh independent audit 尚未产生。

## 1. 范围与不可越界项

本轮只处理 R12 fresh audit 已证明的同阶段 03B 根因：

1. public pre-discard 不能从持久化行重算全部材料 transformation summary；
2. ownerless one-token unseen event head 可以跨事件借用左侧 quotation predicate；
3. participial／relative complement 可以把 service／arrangement 等治理价格误作 hardware ASP；
4. R13 的前序、raw reuse、preview 与 replay 必须直绑 immutable R12，而不是机械继承时继续把 R11 写成直接前序；
5. 后续 fixed audit manifest 必须保留 Git 路径原始大小写。

本轮没有执行 03C external ladder、0.6B／4B embedding、reranker、CandidateDecision、Evidence admission、Pack／Readiness、S2、S3、Writer、报告生成、formal 8D、人工验收或发布。R17 既有 citation/source appendix、crosswalk、WWC、数值桥与 human `0/16` 失败继续原样保留。

## 2. R13 实现

新增且不覆盖 R12：

- `src/retrieval/dell_report_predicate_frames_r13.py`
- `src/retrieval/dell_report_frame_transformation_r13.py`
- `src/retrieval/dell_report_internal_chain_ceiling_r13.py`
- `scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r13.py`
- 三份对应 direct tests。

### 2.1 authoritative persisted reconciliation

R13 新增唯一 `summary_population_scope`，材料 summary 只允许从即将持久化的四类行派生：target-filtered source packages、target-filtered compiled packages、coverage gaps、validated transformation bindings。编译时和 public projection 丢弃 private surface 之前均调用同一纯函数重新派生，要求 whole-dict exact equality。

每个 target 的 summary 现在显式保存并重算：source／compiled／coverage row count 与 set digest、binding／accepted／failed count、binding digest、unbound complete／partial、compiled-only、failed-complete、proof-rebind、governing-head、clause-decision maps、non-vacuous coverage、coverage pass 与顶层 reconciliation digest。逐字段 mutation test 会修改 summary 的每一个字段并要求 fail closed；另有 persisted package surface mutation、re-signed summary、clause map、coverage boolean 与 reconciliation digest attacks。

R12 的 clause maps 来自 full corpus，而持久化 package 是过滤后的 target semantic subset；两者不能自洽。R13 因此有意改变这些诊断 count／digest 的口径，不把它伪装成候选质量提升。preview 明示 predecessor 中新字段为 null、R13 中为可重算值，并附固定解释。

### 2.2 event-local ownerless unknown head

R13 在 conjunction 右侧材料 surface 前只有一个未知 lexical head 时建立 fail-closed event barrier。它不把未知词晋升为业务 predicate，只阻止左侧 actor／quotation／price 等角色跨事件继承。冻结了 `repaired/refurbished/serviced/assembled/reconfigured`、大小写、逗号、副词和助动词形态；product list、数量词与正常 shared-subject controls 保持正向。

作者曾尝试把所有“共享主语＋新谓词＋材料 surface”一律 split。定向运行得到 `11 failed, 106 passed`：正常 supplier fronted adjunct、auxiliary continuation 与既有 shared-subject 正例被误伤。该过宽方向已收回，没有通过修改旧断言掩盖；最终规则只关闭 audit 证明的 unknown ownerless event head 边界。

### 2.3 participial／relative governing price head

product complement 结构从 `for/of/on` 扩展到 `covering/including/bundling/containing/comprising/featuring` 与 `that/which covers/includes/contains/bundles/features`。`maintenance service`、`delivery arrangement`、`lease financing`、support plan 与 nonce heads 均不能把后置 hardware surface 的金额冒充 Dell hardware ASP。

正向门保留 direct hardware price、purchase/configuration price、四类 connector proof，以及“PowerEdge hardware bundle 先有明确 bundle price、随后说明 included GPU”的正例。transformation tests 还证明 participial governing-head loss、connector proof rebind 与 clause-ownership proof loss不会通过 source→compiled binding。

新增 governing-head transformation test 的第一次断言把实际 typed class `structural_product_complement_head` 写成旧的泛类名，得到 `1 failed, 13 passed`；修正测试期待后为 `14 passed`，没有改生产判断迁就测试。

### 2.4 R12 直系谱系与 zero-call runner

首轮机械 successor preview 虽然业务不变量通过，却暴露 runner 仍把 R11 当直接前序。该次 preview 只读、零输出写、零调用，因 lineage contract 错误不作为 R13 最终 preview 证据。

最终 R13 policy／runner／replay 合同已统一改为直绑：R12 policy v2.1、public v2.1、private result、attempt receipt、raw-reuse capture、fresh failure audit、fixed manifest、R17 audit/bundle 与冻结数据／runtime／route inputs。R13 raw successor 的 source 是 R12 raw-reuse capture；R12 capture 内再可追溯到 R11 canonical candidate-generation execution。合同分别记录 `canonical_R11_raw_local_embedding_inference_batches=1`、`upstream_R12_new_local_embedding_inference_batches=0` 与 `saved_R12_raw_reuse_count=1`，避免把传递来源写成直接前序。

R13 policy validator同时冻结 R12 implementation findings `0/1/2/0`、separate manifest envelope `0/0/1/0`、总数 `0/1/3/0`、三个 material finding ID、7 个 case mismatch 与 R17 `0/1/2/1`；re-signed audit boundary drift 会 fail closed。

## 3. 最终分层门

- T0：changed Python `py_compile`、`pyflakes`、`git diff --check` 通过；R12 fixed bundle `40/40` SHA 不变；active baseline=`213 Python / 8 frontend / 5 detectors / 28 resources / 0 forbidden`。
- 最后一处 corpus-index 调用从直接 R11 implementation API 改为 R12 successor API 后，T1 R13 direct最终复跑：`162 passed in 56.25s`，低于 90 秒门。
- 同一最终代码上的 T2 R12+R13 adjacent：`292 passed in 79.74s`，低于 150 秒门。
- T3 Project OS + base/R3 foundation seam：`140 passed in 15.11s`，低于 180 秒门。
- 最终 ledger写入后 Project OS=`82 passed in 11.32s`；8 份 JSONL／`1,382` 行全部解析；R12 fresh-audit self-digest 独立复算一致；repository secret scan=`8,243 files / 0 findings`。
- T4 未运行。R13 仅增加隔离 successor module／runner／tests／记录，没有修改 shared active runtime、依赖、pytest config或 current consumer；T1～T3没有跨域失败，故 T4 trigger=false。

上述两次作者失败运行均保留在本记录，不作为通过证据，也没有产生 policy、attempt、formal output或外部调用。

最终 preview 的第一次只读 Python wrapper 调用在 import 前因当前解释器未把工作目录加入 `sys.path` 而得到 `ModuleNotFoundError: scripts.data_retrieval`；它没有进入 runner、没有写文件或发生任何调用，也没有消费 formal identity。显式加入仓库根目录后，同一当前代码完成下述 preview。该失败不能被计作产品 attempt。

## 4. immutable-R12-raw full-corpus preview

最终 preview：

- mode=`preview_from_immutable_R12_saved_raw_zero_call`
- elapsed=`25.315615s`
- source=`1,888`
- compiled objects=`34,199`
- candidate union occurrences=`794`
- preview digest=`5cd4fe82a987f571cf8844649faa1579c73a86b69d82a6c2f176951c17ed523e`
- network／provider／model／generation／external／4B／reranker／retry／mutation／promotion／closure=`0`

R12→R13 complete crosswalk完全不变：

| target | source / compiled / union / final | best rank | external required |
|---|---:|---:|---:|
| ASP | 0 / 0 / 0 / 0 | null | true，2 条 exact route IDs |
| capacity release | 0 / 0 / 0 / 0 | null | true |
| utilization/yield | 0 / 0 / 0 / 0 | null | true |
| HBM supply | 0 / 0 / 0 / 0 | null | true |
| supplier readthrough | 3 / 3 / 2 / 1 | 2 | false |
| units | 0 / 0 / 0 / 0 | null | true |

R13 transformation totals=`1,596 bindings / 1,273 accepted / 323 failed`。逐 target 为：ASP `815/649/166`、capacity `378/294/84`、yield `5/5/0`、HBM `10/8/2`、supplier `64/52/12`、units `324/265/59`。相对 R12 `1,601/1,277/324` 的唯一 binding population 变化在 supplier partial：`69/56/13 → 64/52/12`；source/compiled partial count `76/69 → 71/65`，一个 unbound partial family被移除。complete families、coverage、rank、route identity与 downstream disposition均不变。

五个 target 仍缺 complete bounded local package；这不是“信源已补齐”，也不是 public non-disclosure 证明。supplier虽有 complete candidate，仍保留 residual research boundary，不能自动晋升 Evidence。

## 5. 当前结论与下一顺序

R13 当前只有 author implementation/test/preview pass，`R13_executed=false`、`R13_independent=false`、`03B_independent=false`。下一步严格为：

1. 追加 Project OS 状态并完成最终 T0；
2. clean implementation commit 与 non-force push；
3. 只增加 v2.2 policy 的 authority commit，父提交必须精确等于 implementation；
4. 创建唯一 `dell-rsq-03b-internal-chain-r13` formal attempt，先 receipt/raw、再 atomic private/public；
5. saved formal exact replay 与 public reprojection；
6. 建立 case-preserving fixed R13 audit manifest和不可变 result commit；
7. 启动全新 `fork_turns=none`、作者分离、只读 reviewer，同时审 R13 engineering 与 R17 report quality。

只有 fresh R13 engineering PASS 后才进入五条 external-required source ladders；其后才是 changed pool 0.6B/4B mixed shadow、条件式 reranker、Evidence/human admission、Pack/Readiness、S2、受影响 S3 动态单元与非覆盖式新报告。新报告仍必须单独通过 citation/source appendix、claim-to-passage、crosswalk、WWC、数值血缘、密度/去重与 qualified-human 质量审计。
