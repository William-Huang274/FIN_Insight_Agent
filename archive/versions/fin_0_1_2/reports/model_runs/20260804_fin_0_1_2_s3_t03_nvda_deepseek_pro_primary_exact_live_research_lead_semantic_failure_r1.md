# Model Run: 20260804_fin_0_1_2_s3_t03_nvda_deepseek_pro_primary_exact_live_research_lead_semantic_failure_r1

## Summary

- Purpose: 验证 FIN 0.1.2 当前 NVDA 内部 dogfood exact input 是否能在 bounded Pro surface 下形成 9 Artifacts。
- Status: `terminal failed / research-lead semantic alias and contract-inheritance regression`。
- Run type: inference / exact-live product validation。
- Timestamp: 2026-08-04。
- Environment: local Windows parent supervisor + direct child，DeepSeek API。

## Code And Command

- Git commit: `8333a1f1a449b2008920c3b7d60bb13de6e3f50c`，执行前 clean/synced。
- Entry point: `scripts/releases/run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live.py`。
- Mode: `supervise`；execution authority=`fin_ia_0_1_2_s3_t03_nvda_exact_live_execution_authority_decision_r2_v1_0.json`。
- Admission: `fin012-s3-t03-nvda-primary-exact-admission-r1`，本次 exact-once 消费。
- Random seed: Provider natural output，不使用本地随机重采样；retry=0。

## Inputs

- Case: NVDA internal frozen dogfood fixture；as-of=`2026-07-21T00:00:00Z`。
- Complete input digest: `b9cc749d0d2351e228750343a61d3fc03abfc8a70870fa96d12c8a03f118e085`。
- Stable business digest: `a19743ffdaa63319a5381262adc9c5b04751abadc9bc4781561c1aa905b744fc`。
- Runtime family: `fin_0_1_2.common_runtime.judgment_atom_family_binding:v1.3`。
- Research Lead: `fin01.s3.bounded_agent.research_lead_owner_grade:v6`。
- Leakage guard: source network、external tool、live case head write 均禁止；Fact 本地生成。

## Model Parameters

- Model: `deepseek-v4-pro`。
- Reasoning effort: none；thinking disabled。
- Provider calls ceiling: 9；transport attempts per call=1。
- Token ceiling: input 60,000 / output 10,000；cost ceiling USD 0.06。

## Outputs

- Runtime result: `.codex_runtime/fin012-s3-t03-nvda-primary-r1/execution-result.json`，SHA `09a0bf6b…11c`。
- Captures: 7 restricted content-addressed objects；原始请求和最终 assistant 输出保留，但不提交 Git。
- Typed terminal: phase=`research_lead`，code=`s3_bounded_research_lead_v3_semantic_fact_presence_summary_mismatch`。
- Business Artifacts: 0；failed output business-promotable=false。
- Tracked summary: `configs/releases/fin_ia_0_1_2_s3_t03_nvda_exact_live_execution_terminal_failure_result_v1_0.json`。

## Results

- Provider calls / captures / Artifacts: `7 / 7 / 0`。
- Input / output / total tokens: `37,107 / 2,310 / 39,417`。
- Estimated cost: USD `0.01815124`。
- Wall time: 63.172 seconds。
- All finish reasons: stop；all attempts=1；transport/auth/JSON failure=false。
- Interpretation: C002 与 C003 的 direct-Fact/epistemic semantics 被 Research Lead 系统性互换；同时 current admission 从已 live-proven 的 Lead-v7 local fact-presence ownership 回退到了 Lead-v6 dual ownership。

## Experiment Governance

- Hypothesis: bounded surface 与 local Fact authority 足以使一次 NVDA exact-live 达到 9 Artifacts。
- Decision target: coherent terminal success、3 local Fact receipts、9 captures、9 Artifacts、0 retry，并在后续独立 L1 中保留 Agent 增益。
- Ceiling: 9 calls / USD 0.06 / 900 seconds；未超限。
- Stop condition: first credible failure；已触发并执行。
- Decision label: `stop / zero-call disposition required`。
- Mainline decision: 不重跑，不进入 paired/Owner/S3-T04。

## Runtime Efficiency

- Wall time: 63.172 seconds。
- Provider latency: 1.808s、3.866s、2.512s、4.383s、1.841s、3.914s、11.430s。
- Throughput/serving implication: 非 serving 评估；主要延迟来自 Provider，未出现 timeout。
- Bottleneck diagnosis: 当前阻断是 semantic ownership/alias identity，不是性能。

## Caveats And Next Step

- 这是内部 frozen dogfood input，不是 external user/live-source proof。
- 失败输出只能用于审计，不能晋升金融事实。
- 新增 `RC-P36-108`；下一项仅允许零调用合同继承与 Claim semantic ownership 处置。
- 未执行：Writer、Verifier、paired assessment、Owner acceptance、S3-T04、第二次 exact-live。
