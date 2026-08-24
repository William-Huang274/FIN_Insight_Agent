# S1 fresh audit：gate、递归闭包、split isolation 与 acquisition 边界

日期：2026-08-24

## 审计结论

全新只读代理对 immutable `5f35b116...` 复核后，确认本机 8.59GB RTX 4060、两个 4B 目录 absent、下载前 resource block 与 `0 network / 0 Provider / 0 model` 都真实；但 R2 不得给未来 attempt 签权：

1. shared gate 只信 caller 的 `identity_bound_v3` 字符串；
2. gate 不校验 approved program、DELL/MU/NVDA 与 COST/hidden split 或 bound input digest；
3. `Path.rglob` 会静默跳过 symlink directory，Windows junction/reparse 也可能逃出闭包；
4. 旧 v1.0 preflight 因 shared gate 硬切 v1.1 schema 无法历史回放；
5. R2 把含 `holdout_unseen_case` ORCL/ASML/ANET 与 heldout pack bindings 的整份 role eval 文件列为 development input，和自身 hidden-load 禁令冲突；
6. local acquisition manifest 只绑定 upstream provenance claim，不是 Hub 返回 commit 的独立 attestation。

失败收据为 `configs/retrieval/fin_ia_0_1_3_s1_large_model_gate_status_bypass_independent_audit_failure_v1_0.json`。R1/R2 的 resource receipt 保持不可变，但 generic attempt eligibility 作废。

## R3 successor

- gate 自己根据 program-bound model ID、artifact kind 与绝对目录重算 identity；caller status/digest 仅作诊断；
- explicit scan 不 follow links，并拒绝 root、manifest、文件或目录的 symlink／Windows reparse point；
- program 的 canonical digest 被代码钉死；split 必须精确为 DELL/MU/NVDA development、COST/hidden/frozen/holdout 禁止；五份 executable input 均按路径、SHA 与 case inventory 重验；
- mixed role eval 不再是 executable input。新 materializer 只复制 18 个 `primary_three_case` DELL/MU/NVDA query，明确不复制 holdout rows、heldout pack bindings 或 source bound inputs；
- v1.0/v1.1 schema 只允许 historical replay；即便 legacy artifact 状态满足，也返回 `historical_identity_contract_not_authorized_for_new_attempt`；
- local manifest 不再被称为 upstream attestation。当前 program 的 approved revision 与 acquisition receipt 均为 `null`，所以即便字节闭包完整，仍以 typed blocker 等待 separate acquisition attempt 与 owner-approved immutable commit。

当前收据仍为 `resource_blocked_before_download`，两个 artifact absent，calls=`0/0/0`。这不是 Qwen3-Embedding-4B、Qwen3-Reranker-4B、BGE Gemma 或任何其他大模型的质量结论。

## 验证与失败保留

- targeted S1/S2/S3 联合最终为 `40 passed, 1 skipped`；skip 仅因当前 Windows 账户不能创建真实目录 symlink，Windows reparse-bit 分类另有不跳过测试；
- acquisition gate 接入后首次组合回归为 `1 failed, 39 passed, 1 skipped`：旧断言只期望 embedding incomplete blocker，未计同时存在的 reranker revision-approval blocker；实现正确 fail closed，断言随后修正；
- 全仓为 `1214 passed, 1 skipped, 2 existing SWIG warnings`；
- 最终联合定向复跑为 `40 passed, 1 skipped`；compileall、14 个变更 Python 文件 pyflakes、1,005 份 config JSON、8 份 Project OS JSONL／1,148 行、active baseline `212／8／5／28／0`、Workbench typecheck／build、7,901-file secret scan／0 和 diff check 通过；
- bundled `pnpm` wrapper 曾在脚本执行前因 `ERR_PNPM_IGNORED_BUILDS / esbuild@0.28.1` 失败，并临时写入两个未跟踪 scaffold；失败收据已保留，精确核验后删除可再生成文件。随后用现有 package-lock／node_modules 与同一 bundled Node 直接运行 TypeScript/Vite，typecheck 与 build 均通过；
- S1 qualification、hidden／temporal qualification、runtime promotion、publication 与 release 均为 false。

下一有效步骤不是在 8GB 本机强跑或量化替代，而是在满足冻结 24GB-class CUDA/FP16 profile 的主机开一份独立 acquisition attempt，记录 snapshot invocation、Hub-returned commit、下载闭包、implementation refs 和 receipt digest；Owner 批准 exact revision 后再开 program successor。
