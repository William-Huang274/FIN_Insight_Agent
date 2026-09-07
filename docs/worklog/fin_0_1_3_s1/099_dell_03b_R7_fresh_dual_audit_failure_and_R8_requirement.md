# S1 工作记录 099：DELL 03B R7 fresh dual-audit 失败与 R8 要求

日期：2026-08-27

状态：`fresh author-separated audit FAIL / immutable R7 integrity and actual route retained / same-stage non-overwriting R8 plan required`

## 1. 审计身份与结论

全新 `fork_turns=none` reviewer 在 result commit=`22c85026aaf1703f3f96a473b545a3a3e18cb35e` 上只读审计；零文件写入、零 commit/push、零网络/Provider/生成/embedding/4B/reranker/付费调用、零全仓 pytest。Audit artifact：

- ref=`configs/audits/fin_ia_0_1_3_commit_22c85026_dell_03b_r7_fresh_dual_audit_fail_v1_0.json`
- digest=`904637666c90ce9c65a45ef741ac7669b19bd118c1797de6ebffa5d601844abb`
- SHA=`d8532fa54974555a30b2d08d3f50cc1d30389d1312b804ea450c95a60776c147`

Overall=`FAIL`。R7 integrity=`PASS`、current public cleanliness=`PASS_BOUNDED`、actual immutable route=`PASS_BOUNDED_FOR_ACTUAL_IMMUTABLE_EXECUTION`；general semantics/anchors/privacy=`FAIL`，03B independent=false。R7 新 finding=`P0/P1/P2/P3=0/0/3/0`；R17 open=`0/1/2/1`；combined=`0/1/5/1`。

## 2. 保留的不可变事实

- result→authority→implementation 拓扑、policy-only authority、result public-record-only changeset 全部精确。
- 29/29 input 与 17/17 implementation SHA、四份 self-digest、receipt links、raw execution digest、public exact reprojection、exact-once population 全部通过；当前 public 未观察到实际泄漏。
- 正式 route 仍为：5 requests、1 local 0.6B batch；其余 forbidden counters=0。ASP=`1/1/1/1 rank2`、supplier=`3/3/2/1 rank2`、四 residual=`0/0/0/0`、coverage=0、external=4、local repair=0、4B=0、reranker=0。
- 这些是 current immutable corpus 的 bounded observations；不会因通用资格失败而改写，也不能反向证明通用资格。

## 3. R7 三项新 P2

### P2-1：仍会跨独立事件借用角色

同一 sentence 内不同 predicate frame 仍可被当成一个 proposition；尾部不确定性也未覆盖完整 proposition span。Frozen reproductions 包括：

- `NVIDIA quoted $15, and Dell sold the PowerEdge XE9680 hardware.` 被拼成 Dell actor + quoted + `$15` + XE9680 complete；
- `NVIDIA shipped chips, and Dell sold PowerEdge servers.` 被拼成 supplier→Dell delivery；
- `Dell received financing alongside GPU capacity being allocated to HP in Q1 2026.` 把融资事件的 Dell recipient 借给 HP capacity；
- solar yield + unrelated GPU、HBM→HP + unrelated Dell、Dell marketing shipment + NVIDIA four-server delivery 均能跨事件 complete；
- trailing `allegedly`／`unconfirmed report` 被忽略。

R8 不得只修 conjunction regex；必须建立 predicate-frame/span-bound argument ownership，并把 polarity/modality/status/report scope 覆盖完整 proposition span。

### P2-2：anchor 局部归属与正向召回仍失败

`Dell quoted $150 for support plus $15 for PowerEdge XE9680 hardware.` 错把 `$150` 绑定到 XE9680；应绑定 `$15` 或因歧义 fail closed。六条正常正例 `provides/released/yielded/uses/dispatched/offered` 全部不能 complete。

R8 必须让 anchor 保存 predicate-argument provenance，多值时做局部归属/歧义拒绝；同义语法用受审 positive controls 扩展，不能继续宣称枚举 regex 已通用化。

### P2-3：public allowed-value 仍可绕过

- grammar-valid 高熵 ID `REQ::DELL::TOKEN_LIVE_PRODUCTION_A1B2C3D4E5F6G7H8::V1` 在 secret/entropy guard 前 early return；
- 四层 percent-encoded `https` locator 因只解码三轮而通过。

R8 必须先做 threat/entropy，再做 identifier acceptance；percent decode 到 bounded fixed point，若仍有 encoded octet 则拒绝，并先 Unicode normalize。

## 4. R17 研报质量

R17=`FAIL_GATE_OPEN_NOT_ASSESSABLE`。内部 provenance 与九条数值关系重算通过，未发现算术错误；但这不能替代读者信源与产品质量：

- 59 次 EV／18 unique 与 15 次 GAP／10 unique 均可内部解析，但 reader URL=0、source appendix=false；两条 fact-bearing WWC 无 citation，原文语义支持因缺 passages/locator 为 NOT_ASSESSABLE。
- crosswalk=`14/9/4/10`、S2 bridges=4，digest 未被 R17 绑定；price-in、scenario/sensitivity、supplier capacity read-through、valuation basis 四 facet 缺失。
- WWC=`0/6 operational`，八项 metric/direction/window/threshold/authority/owner/evidence/response 全缺；method parameters=`0 frozen / 2 pending`。
- 20,574 字、71 fact occurrences／32 unique，核心事实重复 4–5 次。
- 02B=`8 requests / 18 items / 16 human-required / 0 decisions`；formal 8D invalid。

所以 R7 无法让 S3/report/human/product 通过。四 residual 外源、Evidence、S2 和新报告继续未开始。

## 5. 审计效率纠偏

Direct integrity/mutation/targeted/R17 bundle machine checks 都很短，且无需全仓；实际延迟来自 reviewer 在直接检查前递归阅读大量历史 context/ledger，并在 R17 closeout 再次扩大推理时间。主 Agent 两次中断并限缩：只允许 fixed bundle，缺失项标 NOT_ASSESSABLE。

未来 fresh audit 必须由作者提供 hash-bound audit manifest，列出 exact files、frozen findings、positive controls、route expectations、报告 checklist 与允许命令；reviewer 仍完整读取 AGENTS 要求的 Project OS/policy，但不得据此递归扫描全部历史 ledgers。每完成 engineering 与 report phase 必须先交 checkpoint；缺 bundle 不扩搜。

## 6. 下一门

R7 不覆盖、不重试。下一合法动作仅是：保存并推送本 fresh audit failure，然后写 program-level R8 plan，把三项 P2 拆成 predicate-frame ownership、anchor provenance/ambiguity、positive recall grammar、fixed-point public validation、attack matrix、audit manifest、依赖/输入输出/验收/停止条件。R8 implementation/policy/attempt 必须另行冻结。

03C、4B、reranker、CandidateDecision、Evidence/NumericFact、gap closure、S2、新报告、qualified-human、product/publication/release 全保持 false。
