# S1 工作记录 113：DELL 03B R11 作者实现与零调用预演

日期：2026-08-27

状态：`R11-01～R11-04 author implementation and immutable-R10-raw zero-call preview pass / implementation commit and push pending / no R11 policy, attempt, private or public result / fresh audit pending`

## 1. 本轮边界与不可变前序

本轮只实现工作记录 112 定义的同阶段、non-overwriting R11：`ClauseOwnershipDecision v2`、`PriceAttachmentProof v1`、proof-aware source→compiled transformation，以及隔离的 R11 compiler/runner/tests。R9、R10 的 implementation、policy、attempt、raw/private/public、result、fixed manifest 与 fresh failure audit 均未修改。

本轮未创建 v2.0 policy，未消费 `dell-rsq-03b-internal-chain-r11`，未调用 Provider、网络、generation、embedding、4B、reranker 或外源梯子，也未执行 CandidateDecision、Evidence/NumericFact admission、Pack/Readiness、S2、S3 或报告生成。R17 固定质量失败面原样携带。

## 2. ClauseOwnershipDecision v2

新增 `src/retrieval/dell_report_predicate_frames_r11.py`，将 coordinator 后的归属判定显式化为四个状态：

- `non_clause_continuation`
- `shared_subject_proved`
- `independent_owner_proved`
- `ambiguous_material_boundary`

每个 decision 保存 case-preserving aligned surface、leading adjunct、右侧 predicate candidates、shared-subject proof、explicit-owner proof、ambiguity reason、surface-alignment result 和 digest。`in Q2`、`later in Q2`、`under the agreement` 等前置功能性 adjunct 不再冒充 owner；`Rose Systems`、`Target Labs`、`Will Technologies` 等 predicate-token collision 通过保留大小写的 surface 处理；`cost`、`wugged`、`zorps` 等未见 predicate 在存在 material 右事件时形成隔离 barrier，而不是与左 frame 合并。

边界 decision 在一次 frame 编译中只计算一次，并以 proof record 保留。shared、independent、ambiguous 三种 material decision 进入 semantic signature；`non_clause_continuation` 仅是 representation provenance，不改变业务语义，否则 compiled window 中额外的无事件 continuation 会制造虚假 transformation mismatch。

## 3. PriceAttachmentProof v1 与 proof-aware transformation

删除 R10 的 `single_typed_object_in_argument_group` 共现 fallback。价格关系只允许两条可定位路径：

- object/product NP → `for`／`at`／`priced|quoted|offered|sold at|for`／`cost|costs|costing` → price；
- price → `for`／`of` 或明确 purchase/config/list/recommended price 路径 → priced object。

`ArgumentGroupBinding` 现在保存 `proof_state`、`proof_type`、connector span、competing object span 和 proof digest；specific product 必须位于 priced-object span 内。contract amount、maintenance costing、delivery fee、lease payment，以及 nonce `quasar levy`／`nebula escrow` 均保持 unproved partial；正向 object→price、price→object、priced-at 与 purchase-price 路径通过。

`RoleBinding` 和 `RoleTransformationMapping` 保存 proof digest 与 labeled spans。transformation validator 会重算 ownership proof、price proof、argument-group digest 和结构；proof 删除、添加、改绑 object/product/connector/price 均拒绝。仅表示切片不同但 normalized proof 等价时允许 semantic equality。

## 4. 作者期自检发现与同阶段修正

第一次全语料 preview 没有消费 formal authority，但暴露 supplier complete transformation coverage=false。根因不是业务 family 变化，而是 compiled window 比 source 多出的 `non_clause_continuation` 被错误纳入 semantic signature，导致无业务含义的上下文差异被判为 semantic drift。

修正后，所有 clause ownership proof record 仍保留在 representation；只有 material ownership decision 进入 semantic mapping。该修正没有放宽 shared／owner／ambiguous barrier，也没有恢复 co-presence price fallback。随后重新运行完整零调用 preview，六 target complete transformation coverage 全部恢复 true。

## 5. 最终零调用全语料 preview

命令：

`python scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r11.py --mode preview`

结果：source records=`1,888`；compiled objects=`34,199`；union occurrences=`794`；elapsed=`44.022661s`，低于 70s warning／120s hard stop；preview digest=`b31ff486772953aac60940498602eab3f87456d7797335707dbf5ab0b865a215`。model/provider/network/generation/external/4B/reranker/retry/mutation/promotion/closure均为0。

- 完整层与 R10 精确相同：ASP、capacity、yield、HBM、units 均 `0/0/0/0`；supplier=`3/3/2/1 rank2`。
- 六 target complete family set、四层 count、rank、downstream external／4B／reranker eligibility 全部与 R10 相同；failed-complete=0、unbound-complete=0、compiled-complete-without-source=0、local repair=0。
- external-required 仍为5；4B eligible=0；reranker eligible=0。它们只是本阶段路由状态，不表示外源已经执行。
- partial source/compiled：ASP `844/951`；capacity `388/353`；yield `5/8`；HBM `17/19`；supplier `80/73`；units `332/295`。
- R10→R11 unbound partial：ASP `157→196`、capacity `61→87`、yield `0→0`、HBM `7→7`、supplier `22→23`、units `57→72`。preview 保存每个 exact added/removed family ID；这些变化来自更严格 proof schema 对 partial 的重新分类，未改变任何 complete family、coverage、rank 或 downstream disposition，不能冒充 Evidence 或 gap closure。

## 6. 风险分层作者门

- T1 R11 direct：`93 passed in 5.46s`。
- T2 R10+R11 adjacent：`159 passed in 9.76s`。
- T3 Project OS + base/R3 foundation seam：`152 passed in 18.04s`。
- changed Python `py_compile`／`pyflakes` 通过。
- T4 未运行。R11 只增加隔离 successor modules、runner 和 tests，未修改 shared/active Runtime、dependency、registry 或 pytest configuration；T1～T3 未暴露未知 import 或跨域失败。依据风险分层策略，不把约20分钟全仓 pytest 当作每次 patch 心跳。implementation freeze 前仍会再跑 T0、R11 direct、Project OS、JSON/JSONL、active baseline、secret 与 immutable predecessor 检查。

## 7. 产品与研报质量边界

R11 当前只达到 author implementation + zero-call preview，不能写成 executed、independent 或 03B pass。R17 继续为 `FAIL_GATE_OPEN_NOT_ASSESSABLE`：reader URL=0、18个 report EV 的 exact passage/locator/URL binding=`0/18`、14/9/4/10 crosswalk未绑定、WWC=`0/6`、Facts=`72/36 unique`、02B=`0/16`、formal 8D=null、qualified-human=false。

R11 fresh engineering PASS 后才恢复五条 external ladder；随后依次进行 Evidence admission/candidate-pool rebuild、同池0.6B/4B mixed shadow、仅在存在 eligible candidates 时启用 reranker、CandidateDecision/qualified-human Evidence admission、Pack/Readiness、S2、受影响 S3 和不覆盖 R17 的新报告。独立审计必须同时给出工程／Evidence verdict 与研报／研究质量 verdict，不能以工程 finding=0 替代报告质量验收。

## 8. 下一合法顺序

1. 完成 T0、Project OS、自检 diff 和 focused implementation commit/push。
2. 在 clean/synced implementation 上创建只改一个 v2.0 policy 文件的 authority commit/push。
3. 执行唯一 R11 formal；只允许5 requests和一次本地 Qwen3-Embedding-0.6B query batch，raw-first，随后生成 private/public 并 exact saved-formal replay。
4. 冻结 result 和 hash-bound audit manifest，启动全新 fork-none、作者分离、只读工程＋R17研报质量 reviewer。
5. 只有 fresh R11 engineering independent PASS 才执行五条 external ladder；此前 03C、4B、reranker、Evidence、S2、S3、report successor、product/publication/release authority均为false。
