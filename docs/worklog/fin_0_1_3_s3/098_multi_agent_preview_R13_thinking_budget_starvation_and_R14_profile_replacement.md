# FIN 0.1.3 S3 — R13 thinking budget starvation 与 R14 profile replacement

日期：2026-08-20
状态：`R13_terminal_failure_preserved / source_context_replay_naturally_passed / provider_profile_root_cause_confirmed / R14_full_engineering_gate_pass / clean_commit_push_preflight_pending`

## 1. R13 做到了什么

R13 在 clean／synced commit `1e9dfb11...` 与 fresh Project OS preflight 下执行。它没有重跑 Specialist plan、Lead plan、六份初始底稿、Lead coordination 或已完成 Demand repair；Demand 使用 R10 原 `model_visible_request`、FeedbackReceipt 和 workpaper lineage 精确恢复。

运行越过 R12 的 `multi_agent_bound_workpaper_digest_invalid`，证明 RC-AR-013 的 source-context replay 修复有效。随后只启动 Cash repair 的 analysis continuation：1 个新模型节点、1 个 Provider attempt、0 submission、0 网络、0 Candidate promotion。

## 2. 真实失败

R13 以 `multi_agent_preview_analysis_continuation_finish_reason_invalid:length` 终止。usage 为：

- prompt tokens：30,656；
- completion tokens：4,000；
- reasoning tokens：3,705；
- 可见输出：1,249 字符；
- finish reason：`length`。

旧 profile 写 `reasoning_effort=low`，但 DeepSeek V4 Pro 官方语义把 low／medium 映射为高思考。这个补齐节点因此把绝大多数 completion budget 用于再次推理，而不是输出 checkpoint 已列明的缺失字段。官方参考：[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode)。

这不是 S1 资料不足、Cash 角色拒绝反馈、上下文丢失或 strict submission 失败。submission 尚未开始；原 Evidence、NumericFact、Role、challenge 和 815 字片段均保持不变。

## 3. 零调用修复

新增独立 provider profile，显式 `thinking.type=disabled`，只用于已经完成高思考分析后的 checkpoint completion。Runtime 的 TokenBudgetBasis 同步记录实际 `thinking=disabled`，不再把无 reasoning_effort 的档位误写为 provider default。

R14 authority validator 必须绑定 R13 authority、公开失败、私有 terminal、请求／响应 capture、usage、旧／新 profile 和零调用处置；任何 digest、调用数、finish reason 或 replacement constraint 漂移均 fail closed。

R14 仍只允许一个 Cash continuation，不能重跑完成节点、改变资料或晋升 R13 残稿。若 R14 再次失败，同一 Cash 节点不得获得第三次 profile／Prompt replacement。

## 4. 工程验证

- 综合定向：`77 passed`；
- 全仓：`891 passed`，仅两条既有 SWIG 弃用 warning；
- compileall：pass；
- active baseline：`184 Python／8 frontend／5 detectors／27 Runtime／0 forbidden`；
- configs JSON：732 份有效；Project OS：8 份 JSONL／827 行有效；
- secret scan：7,439 files／0 finding；
- `git diff --check`：pass。

当前仍需 clean commit／push 和 fresh preflight，之后才可签发 R14。S1、S3、跨案例泛化、qualified-human、Workbench publication 和 release 全部仍为 false。
