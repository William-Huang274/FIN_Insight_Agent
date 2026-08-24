# S1 clean audit failure 与 locator ancestor successor

日期：2026-08-24

## 审计结论

全新、作者分离的只读 subagent 审计 immutable `1243b3cc...`。它确认 R3 gate 不信 caller status、program digest／五份 input SHA／DELL-MU-NVDA dev-only split 有效，本地 manifest 没有被当作上游证明，legacy 不能签新 attempt，本机 8.59GB resource block 与 `0/0/0` calls 真实；同时给出 P2：最终 model root 和 descendants 会检查 link/reparse，但 raw locator 的祖先目录没有逐 component `lstat`。普通 model directory 若位于 ancestor junction 下，原实现不能发现该 junction。

跨阶段失败收据为 `configs/audits/fin_ia_0_1_3_commit_1243b3cc_clean_independent_audit_failure_v1_0.json`。`1243b3cc` 保持 immutable，不追认为最终通过。

## successor

`model_identity` 现在用不 follow links 的绝对 locator components，从 filesystem anchor 到 model root 逐项 `lstat`；任一 symlink 或 Windows reparse point 都 fail closed。验证完成后 gate 继续只返回 canonical resolved local path，未来 loader 不得重用 raw locator。

测试同时覆盖：

- 实际 ancestor directory symlink；当前 Windows 账户无创建权限时明确 skip；
- monkeypatched ancestor component 分类，属于不跳过的 traversal regression；
- 原 final root、nested symlink、Windows reparse bit、manifest 与全文件闭包回归。

新 materializer `materialize_s1_large_model_challenger_preflight_v4.py` 保留 v1.2 preflight 与 clean audit failure，输出 `preflight_result_v1_3`。本机仍在下载前因 total/free GPU memory 阻断，两个 4B artifact absent，calls=`0/0/0`。

## 边界

这只关闭 locator filesystem boundary 的 P2。approved Hub revision、独立 acquisition receipt、24GB-class CUDA/FP16 host、candidate ceiling、embedding/reranker scoring、hidden qualification、S1 qualification 与 runtime promotion仍全部缺失。

## 工程门

联合定向 `47 passed, 2 skipped`；full repository `1221 passed, 2 skipped, 2 existing SWIG warnings`。另通过 compileall、8 个变更 Python 文件 pyflakes、1,009 份 config JSON、8 份 Project OS JSONL／1,157 行、active baseline `212／8／5／28／0`、Workbench typecheck／build、7,910-file secret scan／0 和 diff check。两个 skip 均为真实目录 symlink 权限限制；不跳过的 component-walk／reparse regressions 已通过。
