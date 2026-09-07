# R16 fresh independent failure 与 R17 reversal-gate successor

日期：2026-08-24

## fresh reviewer 结论

与 R15/R16 作者分离的只读代理验证了 R16 的 7-path diff、private/public SHA/digest、reference/gap/topology preservation、cash gate 分离和 `0/0/0` calls；但 independent gate 仍 FAIL：

- `what_would_change[5]` 是 material + AI-linked + persistent + predeclared threshold 的合取；`sections[5].clauses[5]` 却写 `persist or breach`。一次性 threshold breach 或持续但未阈值裁决的事件都可能错误反转 demand-quality，属于 P1；
- R16 decision/public/private 未反向绑定 materializer、protected validator 与 renderer SHA，属于 P2 traceability；
- private receipt test 根据 tracked public 文件做 skip，clean checkout 缺 ignored private 时会 FileNotFoundError；
- inventory context 与两处 helps-distinguish 编辑是 Owner 在用户 continuation 授权下作出的保守 bounded correction，并非 R15 machine review receipt 中的 findings；旧 worklog 对 provenance 的归因过宽。

failure receipt：`configs/research/evals/fin_ia_0_1_3_s3_dell_R16_fresh_independent_review_failure_v1_0.json`。R16 保持 immutable，fresh independent pass=false。

## R17 bounded successor

用户已授权 independent finding 后迁回继续，R17 仅同步两个对应 `model_text` paths：

- reversal evidence 必须同时 `material AND AI-linked AND persistent AND evaluated as breaching a predeclared threshold`；
- one-off threshold breach 不足，persistent-but-below-threshold 也不足；
- product margin、working-capital attribution 与 reconciled cash-flow bridge 继续是独立问题。

R17 decision 与 public/private receipts 绑定 R17 script、R16 helper、protected validator 和 renderer 的 exact SHA。reference projection、remaining gaps、topology 均不变；surface/hard/quality=`0/0/0`；model/provider/network/new evidence/promotion=`0/0/0/0/0`。R16 test 也拆成 public-only 必验、private 缺失时按 public 指向的实际 private path skip。

R17 是当前 Codex 编写的本地 candidate，`fresh_independent_post_writer_review_pass=false`。它尚待一个新的 clean reviewer；qualified human、S3、product、publication 与 release 均保持 false。

## 验证

- R16/R17 与 S1/S2 联合定向：`40 passed, 1 skipped`；
- 全仓：`1214 passed, 1 skipped, 2 existing SWIG warnings`；
- compileall、14 个变更 Python 文件 pyflakes、1,005 份 config JSON、8 份 Project OS JSONL／1,148 行、active baseline `212／8／5／28／0`、Workbench typecheck／build、7,901-file secret scan／0 和 diff check 均通过；
- bundled `pnpm` wrapper 的 pre-script `ERR_PNPM_IGNORED_BUILDS` 失败、临时未跟踪 scaffold 与清理均有独立失败收据；现有 package-lock／node_modules 下的 TypeScript/Vite 直接验证通过。
