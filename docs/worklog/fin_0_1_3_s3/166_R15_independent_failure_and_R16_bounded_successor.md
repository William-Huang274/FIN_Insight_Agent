# R15 独立内容失败与 R16 bounded successor

日期：2026-08-24

## 独立结论

独立只读代理复核 immutable R15 private/full public receipt，确认 source hash、protected numeric surface、公司／产品与跨公司边界总体正确，但发现一个 material content finding：R15 的需求质量反转条件没有要求事件达到 materiality、明确归属于 AI 产品、具有持续性或按预冻结阈值裁决；同一表述还可能把 product-level working-capital stock evidence 当成关闭 cash-conversion bridge，而 R15 自己保留了产品归属、幅度和 cash-flow reconciliation 缺口。

因此 R15 的 independent post-Writer gate 明确失败；R15 不改写。收据：

- `configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_R10_protected_writer_independent_takeover_R15_independent_review_v1_0.json`

审计还记录了几项非 material 表达债务：company revenue/profit co-growth 被写成 conversion；derived FCF 没有明确标成 OCF-minus-capex 的 non-GAAP derivation；绝对库存余额被赋予过强 AI 风险识别力；`resolves competing explanations` 过强。

## Owner 的 R16 范围决定

这些 finding 不需要新增事实、检索或付费 Writer，可以在不扩 authority 的前提下确定性修正。用户已授权在独立审计后迁移并继续，因此开 R16 bounded successor，但 R15 failure receipt 和旧 candidate 保持 immutable。

R16 只允许改 7 个 `model_text` 路径：两个 What-Would-Change 条目及其 section 对应面、company co-growth、derived FCF、inventory context。所有 source_claim／Evidence／authority／gap refs、remaining gaps、section topology 和 protected numeric surfaces 必须完全不变。预算为 0 model／Provider／network／new Evidence／promotion。

范围决定：

- `configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_R10_protected_writer_R16_bounded_successor_scope_decision_v1_0.json`

materializer：

- `scripts/research/materialize_s3_R16_bounded_writer_successor.py`

## 本地 R16 结果

R16 明确要求：只有 material、AI-linked、persistent 且按 predeclared threshold 评估的 cancellation／impairment／realized loss 才可反转 demand-quality judgment；product margin、working-capital attribution 和 reconciled cash-flow conversion 是三个独立问题，不得互相替代。其余改动只收紧表达，不新增研究结论。

materialization 结果：

- changed model-text paths 精确为 7；
- reference projection、remaining gaps 和 topology 全部 unchanged；
- protected surface finding=`0`；contract hard／quality finding=`0/0`；
- calls=`0/0/0`，new evidence/promotions=`0/0`；
- public receipt：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_R10_protected_writer_R16_bounded_successor_candidate_result_v1_0.json`；
- private full result 继续留在 ignored workbench-private 路径，并由 public SHA／digest 绑定。

R16 仍由当前 Codex 编写，不能自我关闭 independent gate。下一门是第二个全新、只读、与 R15/R16 作者分离的审计代理；在其结论前，independent／qualified-human／S3／product／publication／release 全部为 false。

## 仓库门禁

R16 与原 takeover 定向 `6 passed`，联合治理／S1／S2／S3 定向 `129 passed`；全仓 `1201 passed, 2 warnings`。另通过 full compileall、10 个变更 Python 文件 pyflakes、992 份 config JSON、8 份 Project OS JSONL／1137 行、active baseline `212／8／5／28／0`、Workbench typecheck／production build、7,878-file secret scan／0 和 diff check。上述仍是本地 engineering／content-contract proof，不代替独立或 qualified-human review。
