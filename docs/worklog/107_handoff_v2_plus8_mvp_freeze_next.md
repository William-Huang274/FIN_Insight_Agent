# Handoff - v2 Plus8 MVP Freeze Next

Date: 2026-05-20

## 当前结论

当前 v2 pilot 已推进到 plus8，并且完成 MVP freeze-readiness review。

工作别名：

- `v2_plus8_mvp_diagnostic_freeze`

冻结对象：

- manifest: `eval/sec_cases/test_cases_v2_pilot_plus8_seed.jsonl`
- reviewed non-trap cases: 13
- pipeline-only trap cases: 2
- total cases: 15
- exact-value ledger: 104 rows
- final context selector: `BAAI/bge-reranker-v2-m3`
- synthesis route: BGE-M3 pipeline-context + trace-aware Judgment Plan + RTX
  5090 Qwen9B

关键判断：

- plus8 可以冻结为 MVP diagnostic pack。
- 不能宣称这是 full v2 benchmark。
- 不能进入 full mainline scored test。
- 不能在没有明确接受 freeze 决策前继续加 case。
- BGE-M3 必须继续作为 final context selector；BM25/ObjectBM25/requirement
  BM25 只能作为 candidate generators。

## 新窗口优先读这些文件

1. `docs/worklog/106_sec_benchmark_v2_pilot_plus8_mvp_freeze_readiness_review.md`
2. `reports/quality/sec_benchmark_v2_pilot_plus8_mvp_freeze_readiness_review.json`
3. `docs/worklog/105_sec_benchmark_v2_pilot_plus8_text_heavy_nvda_snow_audit.md`
4. `reports/model_runs/20260520_sec_benchmark_v2_pilot_plus8_text_heavy_nvda_snow_bge_m3_qwen9b_5090.md`
5. `eval/sec_cases/test_cases_v2_pilot_plus8_seed.jsonl`
6. `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus8_reviewed_exact_value_ledger.json`
7. `reports/quality/local_v2_pilot_plus8_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates/sec_benchmark_post_gates_summary.json`
8. `reports/quality/sec_benchmark_v2_pilot_plus8_judgment_plan_trace_seed_gate.json`
9. `docs/eval/sec_benchmark_v2_next_reviewed_batch_design.md`
10. `docs/eval/sec_benchmark_v2_generalization_plan.md`

## 已通过的冻结依据

Deterministic gates:

- readiness: 15/15 pass
- reviewed-gold mainline: 13/13 pass
- trap smoke: 2 pass, 13 skipped
- ledger-unit: 104/104 pass

Pipeline/post-gate:

- BGE-M3 context preparation: 15/15 cases
- Judgment Plan gate: 11/11 pass, 15 drivers
- Qwen eligible non-trap answers: 13/13
- trap contract fallback: 2/2 by design
- non-trap fallback: 0
- ledger repair: 0
- qwen answer ratio: 1.0
- answer-ledger: pass, 57 exact hits
- table-cell: pass, 12/12 valid cells
- named-fact: pass, unsupported token count 0
- caveat/claim: pass, 37/37 required caveats, 0/43 disallowed violations
- v2 semantic contract: pass, 14/14 checked
- answer-vs-Judgment-Plan: pass, 11/11 checked
- metric-source grounding: pass, 162 metric references

## 冻结边界

允许说：

- plus8 是 15-case MVP diagnostic freeze candidate。
- plus8 已经通过当前 active deterministic gates 和 pipeline post-gates。
- plus8 覆盖 numeric/table、peer comparison、proxy/direct、text-heavy
  no-ledger、wrong-attribution trap 和 metric-scope not-found trap。

不允许说：

- plus8 是 full v2 benchmark。
- plus8 可以代表 40-case full generalization result。
- plus8 已经进入 full mainline scored test。
- trap contract fallback 是 Qwen 自主回答。
- gold-vs-pipeline parity 已验证；本轮 gold-vs-pipeline gate 是按设计跳过。

## 已接受但不能忽视的限制

- full v2 target 仍然是 40 high-quality cases。
- partial approval 仍然阻止 full benchmark mainline scored test。
- abstract-judgment rubric 只覆盖 3 cases。
- text-heavy no-ledger cases 当前不会进入 ledger-driven Judgment Plan。
- Judgment Plan gate 有 6 个非阻塞 trace-support warning。
- named-fact gate 有 1 个非阻塞 summary warning。
- v2 semantic gate 有 6 个非阻塞 one-sided peer-comparison support warning。

## 推荐下一步

优先分支 A：接受 freeze 并创建一个稳定引用点。

- 在后续报告中统一使用别名 `v2_plus8_mvp_diagnostic_freeze`。
- 后续任何复现实验都固定使用 plus8 manifest、104-row ledger、BGE-M3
  selector、trace-aware Judgment Plan 和 RTX 5090 Qwen9B route。
- 如果只是复现，不改 manifest、不改 prompt、不改 gate contract。

分支 B：为 full v2 做补强，而不是继续盲目加 case。

- 扩 abstract-judgment rubric 覆盖到更多 L3/L4 cases。
- 单独跑 gold-context 与 pipeline-context，以恢复 gold-vs-pipeline parity
  gate。
- 再设计 plus9 或 40-case 路线，但要先写 case-family coverage matrix。

分支 C：如果用户明确要求继续扩 case。

- 先写新的 reviewed batch design 或 coverage matrix。
- 每个新 case 必须先有 validator/contract，再进入 reviewed artifact。
- 不要把 plus8 freeze 和 plus9+ 扩展结果混在一个结论里。

## 安全和操作注意

- 不要把 SSH 密码、token、临时凭证或连接命令写入任何仓库文件。
- 当前工作区仍有大量历史 untracked/generated artifacts；不要做
  destructive git 操作。
- 如果后续云端复现失败，先检查 artifact/path parity、BGE-M3 cache、
  manifest/ledger path、post-gate输入目录，再考虑 prompt 或模型问题。

## 交接状态

plus8 MVP freeze handoff 已完成。新窗口可以直接从接受 freeze、复现
plus8、扩 rubric/gold-vs-pipeline，或设计 plus9 batch 之间选择。默认建议
先接受 freeze，然后补 rubric 和 gold-vs-pipeline parity，而不是立刻加 case。

本交接未包含任何密码、token 或临时凭证。
