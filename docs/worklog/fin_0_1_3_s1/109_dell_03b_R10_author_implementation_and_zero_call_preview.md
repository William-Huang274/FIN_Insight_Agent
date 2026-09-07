# S1 工作记录 109：DELL 03B R10 作者实现与零调用预演

日期：2026-08-27

状态：`R10-01～R10-05 author implementation and immutable-R9-raw zero-call preview pass / implementation commit and push pending / no R10 policy, attempt, private or public result / fresh audit pending`

## 1. 本轮边界

本轮只实现工作记录 108 中 R9 fresh audit 的两个 P2 successor：开放词主体的结构性事件边界，以及 ASP product↔price 同参数组关系与 source→compiled relational seal。R9 implementation、policy、attempt、raw/private/public、result、manifest 和 audit 均未修改。

本轮未创建 v1.9 policy，未消费 `dell-rsq-03b-internal-chain-r10`，未调用网络、Provider、generation、embedding、4B、reranker 或外源梯子，未做 CandidateDecision、Evidence/NumericFact promotion、gap closure、S2、S3 或报告生成。正式 R10 仍只允许五个冻结 request 的一次 fresh 本地 Qwen3-Embedding-0.6B query batch。

## 2. R10-01：开放词结构边界

新增 `src/retrieval/dell_report_predicate_frames_r10.py`，事件 split authority 不再依赖 `_FRAME_RIGHT_SUBJECT` 公司／实体枚举：

- coordinator 左侧已有 predicate，右侧第一 predicate 前存在非空 lexical owner prefix 时 split；`Acme`、`Supermicro`、未见多词主体和带前置时间修饰的主体使用同一规则。
- 右侧 predicate 从 offset 0 开始时保留 shared-subject continuation；bare discourse adverb 不冒充 owner。
- 左侧尚无 predicate 的 compound/shared subject 继续保持一个 frame，`Dell, NVIDIA, and Micron partnered` 不退化。
- `FrameBoundaryDecision` 保存 exact coordinator、左右 predicate、structural right-prefix span、reason 和 digest。

审计反例 `Dell quoted support for USD 150 and Acme offered PowerEdge XE9680 hardware for USD 15.` 现在拆为两个 frame，Dell 左侧 support 与 Acme 右侧产品价格不能跨事件 union，ASP fail closed。

## 3. R10-02／03：同组 ASP relation 与 transformation

`ArgumentGroupBinding` 新增 `normalized_product`。ASP 先编译全部参数组，再只允许一个同时满足 `hardware + ambiguity=null + specific product_span + resolvable price` 的 relation 产生 product 与 price roles；record-global product、generic `hardware`、多 product、多个 product-price relation、support/service/freight/financing 和跨组借位均 fail closed。

normalized relation 至少包含 `relation_type=hardware_product_price`、product、price、object class 与 attachment；span 只进入 representation/mapping。relation 已进入 `semantic_signature_digest`，并以 `argument_relation.hardware_product_price` 进入 source→compiled role mapping、loss/addition 和 semantic mismatch。合法 bounded slice 可 representation 不同而 relational semantic 相同；审计 source/compiled 反例的 compiled side 现为 partial，binding 被拒绝。

R10 compiler/runner 使用独立 module、schema v1.9、policy/result path 和 attempt ID。policy validator 除 R9 policy/public/private/attempt 外还要求 immutable R9 raw capture、fresh failure audit 和 fixed audit manifest，核对两个精确 P2 finding、R17 `0/1/2/1` 及 14-file carry-forward。runner 保留 clean/synced、policy-only parent、exclusive receipt、raw-before-compile、redacted terminal failure、atomic private/public 和 exact saved-formal replay。

## 4. 零调用全语料 preview 与 ASP 纠偏

命令：

`python scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r10.py --mode preview`

结果：source records=`1,888`；compiled objects=`34,199`；elapsed=`39.46156s`，低于 70s warning／120s hard stop；preview digest=`2d9fda9a0aefeaba3398cbf3705aedc0f0003a4cbdaa41f8b2203857aafbf6fd`。model/provider/network/generation/external/4B/reranker/retry/mutation/promotion/closure 均为 0。

- supplier 保持 `3/3/2/1 rank2`；capacity release、observed yield/utilization、Dell-HBM bridge、Dell company physical units 均保持 `0/0/0/0`。
- ASP 从 R9 `1/1/1/1 rank2` 变为 R10 `0/0/0/0`。逐 family 复核证明这不是漏绑：R9 唯一 complete family=`PUBLIC::DELL-EXT::329F1654BF36A1B63B37`，唯一 assertion 为 `Dell quoted $757,231 as the purchase price for the hardware`，其 product 只是 fallback `bounded_hardware_configuration`；没有型号、配置或同组可辨识产品。R10 按已批准的 generic-hardware fail-close 规则纠正该 false complete。
- 因此 external-required target 从 4 增至 5：原 capacity release、yield/utilization、HBM bridge、company-period units 四条，加上 bounded Dell AI server configuration/bundle price。supplier 仍不需要为既有 relationship completion 重跑，但 capacity readthrough residual 仍保留。
- 六 target complete transformation coverage 均 true，local source→object repair target=0。partial diagnostics 为 ASP 157、capacity 61、yield 0、HBM 7、supplier 22、units 57；它们不能冒充 Evidence 或 proved public-information gap。

## 5. 风险分层作者门

- T1 R10 direct：`66 passed in 5.28s`。
- T2 R9+R10 adjacent：`122 passed in 7.87s`。
- T3 Project OS + S1 foundation：`93 passed in 14.24s`。
- changed Python compile／pyflakes 通过；`1,160` 份 configs JSON 与 `8` 份 Project OS JSONL／`1,332` rows 全部解析；repository secret scan=`8,195 files / 0 findings`；active baseline=`213 Python / 8 frontend / 5 detectors / 28 resources / 0 forbidden`；R10 import 只存在于新 runner、tests 和隔离 R10 modules。
- T4 未运行。R10 未修改 shared validator、active Runtime、registry、dependency 或 pytest configuration；T1～T3 无未知／跨域失败。依据风险分层策略，约 20 分钟全仓门不作高频心跳；若后续 active/shared surface 改变或窄门出现无法归属失败，再升级 T4。

## 6. 产品与研报质量边界

R10 只达到 author implementation + zero-call preview，不能写成 executed、independent 或 03B pass。R17 继续为 `FAIL_GATE_OPEN_NOT_ASSESSABLE`：reader URL=0、18 个 report EV 的 exact passage/locator/URL binding=`0/18`、14/9/4/10 crosswalk 未绑定、WWC=`0/6`、Facts=`72/36 unique`、02B=`0/16`、formal 8D=null、qualified human=false。

R10 fresh pass 后必须先执行五个真实 source target 的 residual ladder 和 Evidence admission，再在 changed candidate pool 上运行 0.6B/4B mixed shadow；只有存在同池排序 eligibility 才启用保留的 reranker。之后才可重编 Pack/Readiness、S2 units/share→ASP/mix→PVM→产品利润／营运资金、受影响 S3 和不覆盖 R17 的新报告。新报告必须有 reader-visible citation/source appendix、claim→exact passage/URL/locator、完整 crosswalk、operational WWC 和去重，并分别接受工程、研报质量和 qualified-human 验收。

## 7. 下一合法顺序

1. 完成 T0、Project OS、自检 diff 与 focused implementation commit/push。
2. 在 clean/synced implementation 上创建只改一个 v1.9 policy 文件的 authority commit/push。
3. 执行唯一 R10 formal，先写 raw capture，再生成 private/public；随后 exact saved-formal replay/reprojection。
4. 冻结 result 与 hash-bound audit manifest，启动全新 fork-none、作者分离、只读工程＋R17 研报质量 reviewer。
5. fresh pass 后恢复五目标 external source ladder；其前 03C、4B、reranker、Evidence、S2、S3、report successor、product/publication/release authority均为 false。
