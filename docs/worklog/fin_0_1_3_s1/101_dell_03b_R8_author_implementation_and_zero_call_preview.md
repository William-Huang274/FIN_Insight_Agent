# S1 工作记录 101：DELL 03B R8 作者实现、零调用预演与单次冻结门

日期：2026-08-27

状态：`author implementation, zero-call preview and single T4 freeze pass / R8 policy, attempt, private and public result absent / fresh dual audit pending`

## 1. owning-stage 修复范围

R8 不覆盖 immutable R7，而是新增 v1.7 predicate-frame kernel、candidate-chain compiler、public validator、formal runner 和直接合同测试，处置 fresh R7 audit 的三个 material findings：

- `RC-S1-079`：以 immutable `PredicateFrame` 和 `RoleBinding` 代替 sentence-wide role scan。每个 actor、predicate、object、recipient、counterparty、product、price、quantity、period、process 和 epistemic scope 都保存 normalized-document exact span、frame ownership、raw/normalized value 与 stable digest。`complete` 只能由一个 frame 内的同一命题角色集合成立；并列公司主语不被误切，同句独立谓词、`alongside`、后置 `allegedly`、`unconfirmed report`、撤销和第三方转述均按 owning frame 处理。
- `RC-S1-080`：material anchor 升级为 `accepted_frame_role_span_bound_v4`。价格、数量、产品、期间、supplier entity 和 process 只从 accepted frame 的 owning role span 生成；多值时不能用 nearest-value 或 package union 猜测。`$150 support + $15 PowerEdge hardware` 正确绑定 `$15`；无法证明 locality 时 typed ambiguity/fail-close。
- `RC-S0-105`：public scalar 统一先做 NFKC、control/bidi 检查、最多 6 轮 bounded fixed-point percent decode、残留 encoded octet 拒绝，再做 locator/traversal/credential/secret/high-entropy threat checks，最后才允许 field grammar。合法 commit/digest、repo ref、request/target ID 和中英文金融 narrative 保留；任何 type-specific validator 都不能提前绕过 threat checks。

四层 source、compiled object、union、final 共用同一 R8 frame classifier；R7 predecessor policy/public/private/receipt/audit finding 均由 validator 精确复核。Formal runner 同时增加 clean/synced exact parent、policy-only path、disk/collision、exclusive attempt、one batch、atomic private/public pair，以及失败可追溯合同：模型返回后立即在 private attempt directory 独占写入 `raw_execution_capture.json`；后续失败只写不含异常消息的 redacted `terminal_failure_receipt.json`，保留原始失败且不重试。

## 2. 冻结回归与作者期内纠偏

R8 直接测试最终为 `97 passed`，覆盖：

- 动态 hash-lock R7 直接测试中的全部 63 条 immutable negative attack cases，canonical digest=`6e618bcf...`，要求 R8 false complete=`0`；
- R7 fresh audit 的 8 条跨 frame／scope false-complete、1 条双价格 anchor attack、6 条 positive controls、2 条 public bypass；
- frame 数量、predicate/role exact span、actor/recipient/counterparty ownership、scope/revocation、limitation、anchor 和 positive recall，不只检查最终 boolean；
- compound company subject、`U.S.` initialism、malformed `innovation . In...` sentence boundary、Dell sell-through actor 与 NVIDIA supplier role；
- R7 selected positive contracts、unknown public fields、旧 locator/credential/secret/traversal attacks、合法 public controls；
- policy bindings、Git exact parent/path、exact-once、raw capture、terminal failure receipt、output collision 与 atomic rollback。

实现中发现并在同一 stage 修复了三类作者问题：

1. 初版 coordinator splitter 会把 `Dell, NVIDIA, and Micron` 的 compound subject 误切；现只有左右都存在独立 predicate 且右侧有 subject 时才把 coordinator 当 frame boundary。
2. 初版 absolute span 用“前句长度 + 1”推算，不能保证等于 normalized full-document slice；现逐句从 normalized document 单调定位，任何 provenance 丢失直接报错。
3. source page 的 malformed `innovation . In...` 曾把下一句 AI-server 文本泄入 partnership frame，错误产生 `local_repair=1`；residual sentence boundary 修复后回到 `0`。这说明全量 preview 不只是性能检查，也是 current-corpus semantic regression gate。

## 3. 零模型全量预演

最终命令只读取 immutable R7 saved raw execution；不调用 embedding、Provider、generation、network、external ladder、4B、reranker、CandidateDecision、Evidence/NumericFact promotion、gap closure，也不写 policy/result/receipt 或消费 R8 attempt。

- source records=`1,888`；compiled objects=`34,199`；elapsed=`35.276s`；result digest=`fb41f0f51d44ffc7cab3b1b0b8b167665ee8d6d28a73bb76c3ea366edf5bc58f`。
- ASP=`1/1/1/1 rank2`；supplier=`3/3/2/1 rank2`；capacity release、observed yield/utilization、Dell-HBM bridge、Dell company physical units 均=`0/0/0/0`。
- 六个 target 的 source/object/union/final add/remove crosswalk 全为空；coverage gap=`0`、local repair=`0`、external required=`4`、4B eligible=`0`、same-pool reranker eligible=`0`。
- Preview 相比 R7 `223.188s` 基线约快 6.3 倍，远低于 `600s` stop gate；没有用牺牲 frame/role/span 验收换性能。

一次 PowerShell 摘要曾把空 JSON 字段经 `@($null).Count` 显示为每层 `1`；直接检查原始 crosswalk 后确认字段实际为空。这是观察脚本计数问题，不是 compiled-object identity drift，也未写入正式 artifact。

## 4. 风险分层测试与冻结证据

Owner 对高频 20 分钟级全仓 pytest 的异议继续按 `risk_tiered_test_evidence_policy.zh-CN.md` 执行：

- T0：`compileall`、五个 R8 文件 `pyflakes`、`git diff --check` 通过；1,152 个 config JSON 与 8 个 Project OS JSONL 可解析；5 个 changed paths secret scan=`0 findings`。
- T1：R8 direct=`97 passed in 7.71s`。
- T2：R7+R8 adjacent=`248 passed in 16.83s`。
- T3：Project OS + S1 foundation=`93 passed in 40.75s`。
- active baseline=`213 Python / 8 frontend / 5 detectors / 28 resources / 0 failures`。
- T4：只在 implementation/test freeze 执行一次 `python -m pytest -q --durations=50`，结果=`1823 passed, 2 skipped, 2 existing SWIG warnings in 508.75s`。

本次 T4 最慢四项均来自 S3：`89.77s`、`61.36s`、`55.74s`、`53.59s`，合计约 260 秒，占总时长超过一半。后续可用正向 marker/显式慢测 lane、fixture/profile 与 hermetic isolation 优化，但本轮不再修改 production/test/marker，避免使 T4 freeze receipt 失效。Policy-only、formal result、Project OS 和 audit artifact 只跑受影响 validator；fresh reviewer 不重复 full pytest。只有 freeze 后 production/test/shared validator/active consumer 语义变化、定向失败影响面不明或 merge/release 明确要求时才升级到新 T4。

完整仓库 secret scan 在记录与 Project OS materialize 后执行一次：`8,163 files / 0 findings`。扫描结果写回本记录后，再以最终 changed-path scan 覆盖记录自身；不重复全仓扫描。

## 5. 当前能力与未完成边界

R8 当前只达到 author implementation + zero-call preview + local engineering freeze，不能写成 03B independent pass：

- v1.7 policy、attempt `dell-rsq-03b-internal-chain-r8`、private/public result 仍不存在；0.6B formal query batch尚未运行。
- 四个 residual external targets 仍是“当前本地链没有 complete evidence、外源路线待执行”，不是已经证明的 public-information gap；上一版研报的信源缺失尚未全部解决。
- 4B mixed embedding challenger、same-pool reranker、Evidence admission、Pack/Readiness、S2 units/share/ASP/mix/PVM/product-profit/working-capital、受影响 DELL 动态单元和非覆盖式新报告均未开始。
- R17 reader-visible citation/source appendix、14/9/4/10 crosswalk、六 WWC、事实密度/重复、source passage/locator、02B `0/16`、formal 8D 和 qualified-human gate 仍独立失败。

下一步必须是 clean implementation commit/push、单文件 policy-only authority commit/push、唯一 formal execution、saved-raw exact replay/reprojection、immutable result seal；随后才创建 hash-bound fixed audit manifest，并启动全新 fork-none、作者分离、只读 reviewer，同时审 R8 工程质量与 R17 研报质量。Fresh pass 之前，03C/4B/reranker/Evidence/NumericFact/S2/report/product/publication/release authority 全为 false。
