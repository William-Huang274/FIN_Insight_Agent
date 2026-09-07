# R17 clean-checkout 与 author provenance successor

日期：2026-08-24

## clean audit 结论

作者分离 reviewer 对 tracked R17 代码／decision／public receipt 证明了两处 reversal 文本的严格四项合取：material、AI-linked、persistent、且经预声明 threshold 判定为 breach；one-off breach 与 persistent-below-threshold 都不足。implementation refs 与 public canonical digest 也一致。

但总体 audit 仍 FAIL，且 reviewer 按本轮限制没有读取 ignored/private candidate，因此 `fresh_independent_post_writer_review_pass` 不能关闭。另有两个 P2：

1. `test_R17_compile_preserves...` 无条件 compile，而 compile 会先读取 ignored R16 private predecessor；本机 pass 依赖 private state，clean checkout 会 FileNotFoundError；
2. 三个 R16 inventory／helps-distinguish paths 被写为 `Owner-authored`，durable 记录却表明 R16 由当前 Codex 编写。用户授权 continuation 证明 scope authority，不证明 exact Owner wording。

## engineering/provenance successor

- R17 compile test 现在按 decision 中 exact R16 private ref 判断：缺失则只 skip private-dependent compile；tracked decision/public receipt、conjunction与 implementation validation 始终执行；另有模拟 absent private 的不跳过 guard regression。
- 新 append-only provenance receipt 将三条路径更正为 `Owner-authorized, current-Codex-authored bounded editorial corrections`，明确 exact Owner wording receipt 不存在；R16/R17 文本、references、gaps、topology、candidate authority 与全部 acceptance flag 均不变。
- R16 failure、R17 candidate、decision 与 public/private result 全部保持 immutable，没有创建 R18，也没有调用模型、Provider、网络、Evidence 或 promotion。

## 边界

这关闭 clean-checkout test 与 author-lineage P2，不把 clean audit 的 tracked semantic positive checks冒充完整 private-content independent review。R17 fresh independent、qualified-human、S3、product、publication 和 release继续为 false。

## 工程门

R16/R17 定向 `9 passed`；联合定向 `47 passed, 2 skipped`；全仓 `1221 passed, 2 skipped, 2 existing SWIG warnings`。compileall、8 个变更 Python 文件 pyflakes、1,009 config JSON、8 Project OS JSONL／1,157 行、active baseline `212／8／5／28／0`、Workbench typecheck／build、7,910-file secret scan／0 和 diff check 均通过。
