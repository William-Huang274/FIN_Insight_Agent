# S1 工作记录 118：DELL 03B R12 唯一零调用执行与作者完整性复证

日期：2026-08-28

状态：`R12 exact zero-new-call execution success / immutable R11 raw reuse successor preserved / exact saved-formal replay pass / reviewed-result freeze materialized / fixed manifest and fresh author-separated dual audit pending`

## 1. 冻结身份与唯一权限

- implementation commit/tree=`e86d4a1d7a52911b25d31034d202ae29e6dfd314` / `3f160e82d955d249d2696e96c8b8478c9d13cf27`；T1/T2=`130/223`、真实全语料 preview digest=`ad4ef78ca6226ceb749d50649419ba25ca90b8d88d50060d55982cbc48297b4a`。
- policy-only authority commit/tree=`e1aeefa3431dcf3e46cadc0f67472cee89f22422` / `fb8433baab63eddba04912e77b3320f130f7a510`；唯一父提交精确为 implementation，唯一 changed path 为 v2.1 policy，formal 启动时 `HEAD==upstream` 且工作树 clean。
- policy digest/SHA=`4dfae14f69bfa2c2e62bdec64239456f0813931d5b947254c7dedde9c2d79440` / `5ed3b60ef0154a9a835175b75396b7496e7e18daaba80f0ef39a9a380c075656`；15/15 输入、37/37 implementation、R17 14/14 carry-forward 文件和 task-specific `TokenBudgetBasis` 均通过。
- attempt=`dell-rsq-03b-internal-chain-r12`；receipt time=`2026-08-27T19:43:42+00:00`。执行前 canonical attempt directory 与 public v2.1 均不存在，D盘 free bytes=`768,110,592`，高于 `536,870,912` 下限。
- GitHub transport 使用仓库级 `http.https://github.com.proxy=http://127.0.0.1:6696`；implementation 与 authority non-force push 均成功。formal 本身禁止网络。

## 2. 正式执行与 raw lineage

R12 没有重新执行检索或 embedding。它精确复用 immutable R11 raw execution SHA=`0e9e4456ba75ecd07bc2e3bd6d5deddafc1972ba19700b029b2e6793e99f7458`：5 个 frozen request、跨请求去重 `338 union / 80 final`，再以 R12 compiler 扫描 `1,888 source / 34,199 compiled objects`，形成 target-union occurrence=`794`。

R12 raw successor 先于 compile 写入，schema=`fin_ia_dell_report_internal_chain_raw_reuse_capture_v1_0`。它绑定 R11 raw capture ref/SHA/digest、R11 attempt、冻结 request/union/final 数量以及 candidate-generation equivalence proof；写盘后必须重读并重新验证才允许 compile。proof 明确记录 query payload、source/object inventory、embedding/vector、candidate union 和 raw rank 全部未变，R12 改动只发生在 post-candidate route projection、semantic compilation 和 provenance。

R12 新增 `local embedding/model/provider/generation/network/external/4B/reranker/retry/current mutation/Candidate/Evidence/gap closure=0`；upstream R11 的一次 0.6B embedding batch只作为不可变 lineage记录，未在 R12 重跑。五个 request 的 `material_set_complete` 仍只表示 request execution contract 完整，不表示六个研究 target 都已有 Evidence。

## 3. 正式结果

| target | complete source/compiled/union/final | best final rank | partial source/compiled | active external route |
|---|---:|---:|---:|---|
| Dell company/bounded configuration price | 0/0/0/0 | — | 844/951 | 2 exact IDs，必须继续 03C |
| capacity release | 0/0/0/0 | — | 381/347 | 2 exact IDs，必须继续 03C |
| capacity utilization/yield | 0/0/0/0 | — | 5/8 | 3 exact IDs，必须继续 03C |
| HBM→Dell bridge | 0/0/0/0 | — | 16/18 | 3 exact IDs，必须继续 03C |
| supplier→Dell relationship | 3/3/2/1 | 2 | 76/69 | 当前 complete；active external IDs为空 |
| Dell company-period physical units | 0/0/0/0 | — | 332/295 | 2 exact IDs，必须继续 03C |

ASP 恢复的两个 exact ID 为 `DELL-RSQ-03A-TARGET-ASP::official_issuer_regulator` 与 `DELL-RSQ-03A-TARGET-ASP::product_procurement_deployment`。五个 external-required target 的 active route set均非空、可由冻结 03A-R2 registry解析；supplier 的恒常 registry identity仍存在，但没有误开 active external execution。

六 target 共 `1,601` 条 transformation binding：`1,277 accepted / 324 failed`；unbound partial=`380`。所有六项 `complete_transformation_coverage_pass=true`，failed-complete、unbound-complete、compiled-complete-without-source、proof-rebind failure 和 local source→object repair均为0。324个 failed binding是保留的 partial/结构失败证据，不能冒充 Evidence 或 proved public-information gap。

## 4. Artifact 与 replay 完整性

- receipt digest/SHA=`d1c738a1d73969958e71b2b2b3bd6c7772e393b2f38a3ba49b60917964d3f81a` / `5e0bfa6bb943b8db25b6b67ac678410ab20f21bdeb6997577be76ae4c84bf186`。
- raw successor digest/file SHA=`eb4c50e8bc043cecad9d97961d3606ab8ac1d7fa931937a4072e96b2a90f57e5` / `7b8410d853bfd8a81cdc27f60e1ce73d943b9912699be538a090d835b1b1ebd3`；其内 raw execution SHA保持 `0e9e4456...f7458`。
- private digest/SHA=`5b4786548c9a50d413fa82c104f87e032f72177f2a12767c8db9d53cda90c1cd` / `489c87dc4f4418270c785fb9062654412d0b1cd494cc155d107c0761aa9cac56`。
- public digest/SHA=`7302201a8a24e7ac0bf96f5c6e1b7bf8718de24958adfb39b9ed21220b607fdc` / `25e873a7dc5e791c84e1dba61abe6353263d88f1bd1ca928f61671202e1fa3bb`；其 private digest/SHA、policy digest与 raw SHA精确反向绑定。
- terminal failure absent；saved-formal replay返回 `private_dict_and_bytes_equal=true`，private digest不变，没有再次消费 attempt或发生任何调用。

formal 从 receipt/raw 到原子 private/public 发布约27秒，saved replay约30秒。formal后 R12 direct regression=`130 passed in 22.17s`；Project OS=`82 passed in 10.23s`；8份 JSONL／1,369行全部解析；repository secret scan=`8,231 files / 0 findings`。结果阶段只增加 public result、运行记录、工作记录和 Project OS；没有 shared/active runtime、dependency、pytest配置或 current product pointer变化，T4 trigger=false。

## 5. 研究、模型与研报质量边界

本次 formal 证明的是 R12 作者身份、raw复用、语义编译、route identity、持久化和 public projection 完整性；不是 fresh independent engineering PASS。它没有执行五条 external source ladder，没有产生 changed candidate pool，因此 0.6B/4B mixed embedding shadow 与条件 reranker 仍未运行；CandidateDecision、Evidence admission、02B human decisions、Pack/Readiness、S2、S3与新报告都未开始。

R17 固定14文件继续为 `FAIL_GATE_OPEN_NOT_ASSESSABLE (0/1/2/1)`：reader URL=`0`、18个 report EV exact passage/locator/URL binding=`0/18`、crosswalk未绑定、operational WWC=`0/6`、Facts=`72/36 unique`、formal 8D=null、qualified-human=`0/16`。fresh reviewer必须分别签发 R12 engineering/Evidence-pipeline verdict 与 R17 report-source/content-quality carry-forward verdict；工程零 finding 不能替代研报质量或 qualified-human验收。

## 6. 下一合法顺序

1. 冻结并推送 public v2.1、本记录、model-run 与 Project OS，形成 immutable reviewed-result commit。
2. 在该 commit 上创建 hash-bound fixed audit manifest，提交并推送。
3. 启动全新 `fork_turns=none`、作者分离、只读 reviewer；禁止 formal/model/network/写入，默认不跑 pytest，先做静态与 mutation 审计，同时审 R12工程与 R17研报质量。
4. 只有 fresh R12 engineering independent PASS 后，才按五个 exact target执行 residual 03C 外源梯子；随后在真实 changed pool上做 0.6B/4B mixed embedding shadow，并仅在存在同池 eligible候选时启用 reranker。
5. 再完成 CandidateDecision/Evidence/qualified-human admission、Pack/Readiness、S2 `units/share→ASP/mix→PVM→产品利润/营运资金`、受影响 S3、不覆盖 R17 的报告 successor、reader citation appendix，以及工程、研报质量和 qualified-human三重验收。

在第3步工程独立通过前，03B independent、03C、4B、reranker、G2/G3、S1/S2/S3、report quality、formal 8D、qualified-human、product/publication/release全部 false。
