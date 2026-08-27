# S1 工作记录 115：DELL 03B R11 fresh 双审计失败与 R12 要求

日期：2026-08-27

状态：`R11 immutable exact execution retained / fresh engineering FAIL / R17 report quality FAIL_GATE_OPEN_NOT_ASSESSABLE / same-stage R12 required`

## 1. 独立审计结论

全新 `fork_turns=none`、作者分离、只读 reviewer 对 immutable R11 engineering bundle 20 项与 R17 report-quality bundle 14 项完成双审计。reviewer 全程 0 写入、0 commit/push、0 formal、0 pytest、0 network/provider/model/external/embedding/4B/reranker；仅在形成具体怀疑后做 direct in-memory mutation probe。

- R11 engineering：`FAIL_MATERIAL_FINDINGS_PRESERVED_SAME_STAGE_SUCCESSOR_REQUIRED`。
- R11 新 finding：`P0/P1/P2/P3=0/1/3/0`。
- R17 carried finding：`0/1/2/1`，verdict=`FAIL_GATE_OPEN_NOT_ASSESSABLE`。
- 合并：`0/2/5/1`。
- R11 independent=false，03B independent=false，qualified-human=false，02B decisions=`0/16`。
- 下一合法工作只有 FIN 0.1.3 / S1 / 03B non-overwriting R12；03C、4B、reranker、Evidence、Pack/Readiness、S2、S3、新报告、product/publication/release 均无权限。

机器可读审计记录为 `configs/audits/fin_ia_0_1_3_commit_cd1d41b3_dell_03b_r11_fresh_dual_audit_fail_v1_0.json`，result digest=`810d77215350f9bd42ce14a8ec6337958c394ea1435bceb21be5e16a36d3f7fd`。

## 2. 通过且应保留的边界

R11 不是“全部作废”。下列证据继续成立且不得被 R12 覆盖：

- fixed manifest 34/34 文件 SHA 与 size 精确匹配，17 个 nested digest/binding 通过；Git implementation→authority→reviewed result→manifest 线性身份通过。
- policy 14/14 inputs 与 33/33 implementation bindings 通过。
- attempt 只有 receipt/raw/private 三件，terminal failure absent；exclusive-create、raw-first、private/public atomic publish 和 exact replay 均通过。
- 5 requests × 96 union → 16 final；aggregate 338/80，rank permutation 全通过；本地 0.6B 一批，其余禁止计数均为 0。
- 当前 public privacy threat-first 检查通过。
- 当前真实 corpus 中 supplier complete source family 3/3 均有 accepted transformation binding；六 target complete-coverage check 6/6。该结果只支持 current corpus，不支持通用 contract。

## 3. 四项材料性根因

### R11-P1-ROUTE-STATE-ERASURE-ASP

ASP 在 public v2.0 中同时为 `external_required=true`、scope 非空、mandatory external route IDs 为空。R11 只继承 immediate predecessor 的 route IDs；当某轮 `external_required=false` 时字段被清空，后续重新变 true 无法从 03A-R2 恒常 route registry 恢复。结果是 summary 声称 5 条 ladder，但 exact contract-ID 枚举只能执行 4 条，ASP 可被静默漏掉。

R12 必须以 immutable 03A-R2 residual program 或独立 constant registry 为 route source of truth；inactive 不得销毁 identity；强制 `external_required => nonempty and resolvable exact external contract IDs`；author comparison 必须比较 IDs，并冻结 true→false→true regression。

### R11-P2-CLAUSE-OWNERSHIP-OPEN-VOCAB-AND-CASE-DEPENDENCE

lowercase／未知公司名和未知谓词会绕过 explicit-owner barrier，例如 `eBay Systems wugged`、`vanadium labs zorps`、lowercase `rose systems offered` 可把右侧第三方硬件价格与左侧 Dell quotation union 成伪 complete。反向地，`in the following quarter` 等合法 fronted adjunct 会把共享主语 continuation 误拆为 partial。

R12 不得依赖首字母大写或闭集 adjunct phrase；material right surface 未证明 shared subject 时必须 fail closed 隔离，predicate-name collision 大小写无关，shared-subject 必须是结构证明。

### R11-P2-PRICE-INTERVENING-NOMINAL-HEAD

`maintenance service for ... hardware at USD 15`、delivery service、lease financing、support services、contract 等句式仍被误判 hardware price。最近的 `hardware at price` connector 抢先胜出，未检查同一 argument group 的 governing service/financing nominal head。

R12 必须证明 argument group governing head；任何更高层非硬件 service/financing/contract head 都形成 competing-head barrier，不允许最近 hardware 表面覆盖真实收费对象。

### R11-P2-TRANSFORMATION-CONNECTOR-PROOF-REBIND

source 的 `hardware for USD 15` 编译成 `hardware at USD 15` 时，proof digest 和 connector spans 已改变，但 binding 仍 `accepted=true` 且无 loss/addition/ambiguity flag。原因是 mapping 虽保存 proof digest/span，acceptance 却未比较。

R12 必须把 connector lexical class、proof digest 与验证过的 span mapping 纳入 lossless contract；proof rebind 若不是显式获准且可复证的 normalization，必须 typed-fail。

## 4. R17 研报质量继续失败

R17 14 项 bundle byte-identical，工程改动没有解决研报缺口：

- reader report 21,118 chars、25 个 Sources markers、59 次 EV、18 个 unique EV，但 URL=0，无 source/citation appendix。
- catalog 可按 ID 找到 18/18 EV，但 EV→exact passage/title/issuer/date/period/locator/URL=`0/18`，claim semantic support=`NOT_ASSESSABLE`。
- 14 Pack gaps／9 dynamic gaps／4 writer groups／10 writer refs／4 S2 bridge gaps 未被 R17 绑定或消费。
- WWC 6 项中 fully operational=`0/6`；2 个方法参数 frozen=0、pending=2。
- frozen evaluator metric=`72 Facts / 36 unique`；独立窄口径=`71/32`，不改变明显重复的 P3 实质。
- 8D score=null，02B qualified-human=`0/16`。

R12 是 S1 工程前置，不得声称解决 R17。外源和 Evidence/S2 完成后，新报告必须 non-overwriting，并补 18 EV 精确 citation appendix、完整 crosswalk、operational WWC、方法参数冻结与去重，再单独通过研报质量和 qualified-human 验收。

## 5. R12 实施与停止条件

R12 仍是同一产品版本、同一 S1/03B 阶段的新 contract/attempt，不是 R11 retry，也不是产品版本升级。顺序为：

1. 先冻结 program-level plan，将四项 finding 拆成需求、依赖、输入输出、工程／模型输出／研报影响验收、定向 tests、停止条件和责任阶段。
2. 从 R11 复制为 non-overwriting R12 文件，逐根因修复并补正负对照与 mutation tests。
3. 先 T1；再相邻 R11/R12 T2；仅按影响跑 Project OS/foundation T3。共享 runtime 未变且影响可证明时不跑约 20 分钟的全仓 T4。
4. 用 immutable R11 raw 做 zero-call preview；逐 target 解释 count/family/rank、route IDs 与 transformation delta。任何伪 complete、route omission、无 flag proof rebind 或无解释 complete-family 漂移立即停止。
5. author gate 通过后才允许 implementation commit→policy-only authority→唯一 R12 attempt→saved replay→fixed manifest。
6. 再由全新作者分离只读 reviewer 审工程和 R17；只有 R12 independent PASS 才能讨论精确五条 03C 外源梯子。

网络连接重置的根因与持久修复不变：Git 未继承 Windows Internet proxy；仓库级 `http.https://github.com.proxy=http://127.0.0.1:6696` 已使多次 push 成功。代理 listener 是外部依赖，缺失时必须 fail closed；不修改系统／全局代理。
