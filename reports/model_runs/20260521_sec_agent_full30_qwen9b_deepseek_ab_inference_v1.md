# Model Run: 20260521_sec_agent_full30_qwen9b_deepseek_ab_inference_v1

## Summary
- Purpose: compare the constrained free-query SEC agent route across local Qwen9B and DeepSeek v4-pro API on the same full-30-company AI-industry prompt.
- Status: completed; diagnostic-only for DeepSeek production promotion.
- Run type: inference / evaluation.
- Timestamp: 2026-05-21 Asia/Shanghai.
- Environment: AutoDL RTX 5090 32GB, `/root/autodl-tmp/FIN_Insight_Agent`; local artifacts synced to `D:\FIN_Insight_Agent`.

## Code And Command
- Entry point: `scripts/cloud/sec_agent_interactive.sh`.
- Commands:
  - Qwen9B: `TICKERS=ALL YEARS=2023,2024,2025 MAX_TOKENS=5000 EVIDENCE_TOP_K=5 OBJECT_TOP_K=5 MAX_CONTEXT_ROWS=180 RERANKER_TOP_K=180 LEDGER_MAX_ROWS=120 bash scripts/cloud/sec_agent_interactive.sh ask-bge-first "<prompt>"`
  - DeepSeek high-thinking diagnostic: `TICKERS=ALL YEARS=2023,2024,2025 MAX_TOKENS=5000 ... ENABLE_THINKING=1 REASONING_EFFORT=high bash scripts/cloud/sec_agent_interactive.sh ask-deepseek "<prompt>"`
  - DeepSeek no-thinking diagnostic: `TICKERS=ALL YEARS=2023,2024,2025 MAX_TOKENS=8000 PLANNER_MAX_TOKENS=2500 ... ENABLE_THINKING=0 bash scripts/cloud/sec_agent_interactive.sh ask-deepseek "<prompt>"`
- Prompt: `你看完这些财报之后你有什么感觉，尤其是AI行业从2023到2025年的发展，结合相关公司的财报指标谈谈你的看法`
- Secrets: no API keys or SSH credentials stored in files.

## Inputs
- Project inventory digest: `e413b6c9ccd0`.
- Company scope: 30 companies from the SEC 10-K manifest.
- Years: 2023, 2024, 2025.
- Filing types: `10-K`.
- Pipeline: Query Contract -> BM25/ObjectBM25 + BGE-M3 rerank -> runtime Exact-Value Ledger -> deterministic Judgment Plan -> LLM synthesis -> claim-first verifier -> post-gates.

## Outputs
- DeepSeek high-thinking artifacts: `eval/sec_cases/outputs/interactive_sec_agent/20260521_161252_b38c717195`.
- Qwen9B artifacts: `eval/sec_cases/outputs/interactive_sec_agent/20260521_161929_b38c717195`.
- DeepSeek no-thinking artifacts: `eval/sec_cases/outputs/interactive_sec_agent/20260521_162939_b38c717195`.
- Human-readable query and rendered outputs: `reports/model_runs/20260521_sec_agent_full30_qwen9b_deepseek_ab_outputs.md`.
- Logs:
  - `reports/logs/ab/deepseek_v4pro_full30_20260521_161140.log`
  - `reports/logs/ab/qwen9b_full30_20260521_161929.log`
  - `reports/logs/ab/deepseek_v4pro_no_thinking_full30_20260521_162835.log`

## Results

| route | planner | parse | gates | qwen_answer_ratio | latency | total elapsed | tokens in/out | claim-first |
|---|---|---|---|---:|---:|---:|---:|---|
| DeepSeek v4-pro high thinking | `llm:deepseek:fallback_after_error` | `parse_error_ledger_repair` | fail: `caveat_claim_gate_pass`, `qwen_answer_gate_pass` | 0.0 | 183.8s | 389.7s | 23,902 / 5,000 | 7 promoted, 4 rejected |
| Qwen9B local vLLM | `heuristic:ok` | `parsed` | all green | 1.0 | 70.9s | 236.2s | 26,335 / 3,007 | 5 promoted, 2 rejected |
| DeepSeek v4-pro no thinking | `llm:deepseek:ok` | `parsed` | fail: `v2_semantic_contract_gate_pass` | 1.0 | 70.6s | 294.9s | 21,177 / 1,948 | 5 promoted, 2 rejected |

## Interpretation
- DeepSeek should not use high-thinking mode for strict JSON contracts in this chain. The high-thinking run hit the 5,000 output-token ceiling and returned invalid/truncated JSON, forcing ledger repair.
- DeepSeek no-thinking mode is viable for Query Contract planning: it returned a valid planner contract and expanded the AI/software/security focus scope to 16 tickers.
- Qwen9B remains more stable under the current deterministic gates, but its insight density is conservative and mostly follows the limited retrieved ledger drivers.
- DeepSeek no-thinking produced a valid answer but failed the current semantic gate because the free-query case was treated like a peer case requiring mentions of many missing companies. This is a gate/query-contract alignment issue, not purely a model-quality failure.
- Both successful parsed routes still had claim-first rejections. The verifier is useful, but the evidence pack/ledger selection is still too narrow for broad industry-insight prompts.

## Decision
- Decision label: diagnostic-only.
- Do not promote DeepSeek high-thinking mode as a production route.
- Treat DeepSeek no-thinking as the preferred API route for planner/synthesis JSON until a separate two-call claim-candidate + renderer protocol is implemented.
- Before more API spend, fix:
  - planner/synthesis provider profiles so JSON routes default to no thinking;
  - semantic gate handling for free-query focus scope rather than requiring every manifest company to appear;
  - evidence-pack breadth so broad insight prompts can support more than 2-3 final drivers.
