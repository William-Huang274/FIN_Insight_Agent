# Model Run: 20260521_sec_agent_free_query_deepseek_full30_taskbalanced_plan_v2

## Summary
- Purpose: validate the constrained full30 SEC free-query chain after task-balanced Judgment Plan compaction and evidence-id backfill.
- Status: completed; all deterministic post-gates passed.
- Run type: inference + deterministic gates.
- Timestamp: 2026-05-21 Asia/Shanghai.
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, RTX 5090 host; artifacts synced back to local `D:\FIN_Insight_Agent`.

## Code And Command
- Entry point: `scripts/cloud/sec_agent_interactive.py`
- Backend: DeepSeek API `deepseek-v4-pro`, thinking disabled.
- Query planner: LLM planner with project inventory injection.
- Retrieval: BM25/ObjectBM25 + BGE-M3 rerank on CUDA.
- Scope: `TICKERS=ALL`, `YEARS=2023,2024,2025`, 30 companies, 90 10-K filings.
- Prompt:
  - `你看完这些财报之后你有什么感觉，尤其是AI行业从2023到2025年的发展，结合相关公司的财报指标谈谈你的看法`
- Local changed files:
  - `scripts/cloud/sec_agent_interactive.py`
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - `scripts/validate_sec_benchmark_v2_semantic_contracts.py`
  - `scripts/run_sec_benchmark_eval.py`
  - `src/sec_agent/*.py`

## Inputs
- Project inventory digest: `e413b6c9ccd0`
- Search scope: all 30 companies.
- Focus tickers from Query Contract:
  - `NVDA, AMD, AVGO, AMAT, MU, INTC, QCOM, MSFT, GOOGL, AMZN, META, ADBE, SNOW, CRWD, PANW, CSCO, TXN`
- Filing boundary: SEC 10-K only, years `2023,2024,2025`.

## Outputs
- Main run directory:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_182029_b38c717195`
- Logged user query and model output:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_182029_b38c717195/qwen/input_output.md`
- Query Contract:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_182029_b38c717195/query_contract.json`
- Runtime ledger:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_182029_b38c717195/runtime_exact_value_ledger.json`
- Judgment Plan:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_182029_b38c717195/runtime_judgment_plan.json`
- Gate summary:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_182029_b38c717195/post_gates/sec_benchmark_post_gates_summary.json`

## Results
- Post-gates: `ok=True`, `pass=12`, `fail=[]`
- `qwen_answer_ratio`: `1.0`
- Answer ledger gate: pass.
- V2 semantic contract gate: pass.
- Answer-vs-Judgment-Plan gate: pass.
- Metric source grounding gate: pass.
- Ledger unit gate: pass.
- Runtime ledger rows: `36`
- Ledger family distribution:
  - `data_center_revenue=6`
  - `semiconductor_solutions=3`
  - `cloud_revenue=10`
  - `capital_expenditure_proxy=10`
  - `semiconductor_systems=3`
  - `operating_cash_flow=4`
- Judgment Plan drivers after compaction: `8`
  - Coverage: `AVGO`, `GOOGL`, `AMD`, `NVDA`, `AMZN`, `AMAT`, `MSFT`, `ADBE`

## Runtime Efficiency
- Total elapsed: `497.6225 sec`
- DeepSeek synthesis latency: `200.948 sec`
- DeepSeek usage:
  - input tokens `44,992`
  - output tokens `6,017`
  - total tokens `51,009`
- Observed bottleneck:
  - Full30 BGE/context preparation plus large synthesis prompt dominate wall time.
  - DeepSeek synthesis quality is materially better than Qwen9B bare/local constrained outputs, but latency is still multi-minute for broad full30 prompts.

## Interpretation
- The structural fix worked: the broad prompt no longer collapses to 2-4 insight points or a semiconductor-only answer.
- The model now sees a task-balanced plan and produces drivers across AI hardware, cloud revenue, capex, operating cash flow, semiconductor equipment, and software proxy evidence.
- This is a stronger production direction than trying to hand-code every insight rule, because fixed code supplies evidence contracts and model calls supply flexible synthesis.

## Caveats And Next Step
- Current gates ensure exact values come from the ledger and evidence IDs exist, but do not yet enforce sentence-level support completeness for multi-company prose.
- A next gate should bind each sentence or bullet to the exact metric/evidence IDs it uses, especially when one sentence compares AMZN, MSFT, and GOOGL together.
- The saved output is suitable for qualitative review, but not yet a final production answer format.

## Qwen9B A/B Check
- Control run directory:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_183136_b38c717195`
- Backend: local vLLM `qwen9b`, heuristic planner, same full30 scope and task-balanced plan compaction.
- Total elapsed: `332.5428 sec`
- Qwen synthesis latency: `156.544 sec`
- Token usage:
  - input tokens `50,711`
  - output tokens `6,500`
  - total tokens `57,211`
- Result:
  - `answer_status=answered_qwen9b_ledger_repair`
  - `qwen_answer_ratio=0.0`
  - failed gates: `caveat_claim_gate_pass`, `answer_vs_judgment_plan_gate_pass`, `metric_source_grounding_gate_pass`, `qwen_answer_gate_pass`
- Interpretation:
  - Even after the same retrieval, ledger, and task-balanced plan improvements, Qwen9B still hit the output cap and failed JSON contract, so the visible answer came from deterministic ledger repair rather than usable model synthesis.
  - This supports using Qwen9B as a local diagnostic/smoke backend and using stronger API models for production-quality free-query insight synthesis under the current single-GPU constraint.
