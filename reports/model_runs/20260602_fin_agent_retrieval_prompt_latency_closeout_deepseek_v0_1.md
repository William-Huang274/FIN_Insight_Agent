# Model Run: 20260602_fin_agent_retrieval_prompt_latency_closeout_deepseek_v0_1

## Summary

- Purpose: 验证 retrieval route coalescing、BGE/CUDA reuse、Research Lead prompt compaction、Memo Writer payload compaction 和 focused output guard 对真实 full-chain 的影响。
- Status: accepted diagnostic closeout; standard/focused path 可继续迭代，尚非深度投研质量最终门。
- Run type: inference / evaluation / smoke。
- Timestamp: 2026-06-02 Asia/Shanghai。
- Environment: local Windows workspace, DeepSeek API backend, BGE reranker local CUDA path, real SEC retrieval artifacts。

## Code And Command

- Entry point: `scripts/eval_multi_agent_real_llm_chain.py`
- Main commands:
  - `python scripts/eval_multi_agent_real_llm_chain.py --cases-path tests/fixtures/fin_agent_full_chain_multiturn_cases_v0_1.jsonl --run-id 20260602_fin_agent_latency_retrieval_prompt_compaction_v0_7_cross_sector_closeout --case-id fin_full_focused_healthcare_lly_rnd_zh --case-id fin_full_standard_wmt_tgt_consumer_zh --case-id fin_full_standard_xom_cvx_energy_zh --real-evidence-operators --strict`
  - `python scripts/eval_multi_agent_real_llm_chain.py --cases-path tests/fixtures/fin_agent_full_chain_multiturn_cases_v0_1.jsonl --run-id 20260602_fin_agent_latency_retrieval_prompt_compaction_v0_10_focused_memo_guard --case-id fin_full_focused_healthcare_lly_rnd_zh --real-evidence-operators --strict`
- Config: real retrieval enabled, BGE device auto, default local ledger store `data/processed_private/ledger/sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_core_ledger.duckdb`。
- Git commit / dirty files: dirty working tree with ongoing multi-agent quality work; do not treat these runs as clean release baseline。
- Seeds: not applicable; API inference is non-deterministic.

## Inputs

- Cases path: `tests/fixtures/fin_agent_full_chain_multiturn_cases_v0_1.jsonl`
- Data profile: full238 mixed SEC / 8-K sector-depth artifacts, market snapshot, industry evidence, local ledger store。
- Candidate boundary: local SEC filing / 8-K / market / industry / relationship evidence only; no external clinical/regulatory/news fetch in focused healthcare case。
- Leakage guard: final prose must cite bounded evidence refs; raw LLM responses and API key are not saved。

## Results

### Accepted / diagnostic runs

| Run ID | Cases | Result | Key Metrics | Notes |
| --- | ---: | --- | --- | --- |
| `20260602_fin_agent_latency_retrieval_prompt_compaction_v0_6_failed_case_fix` | 2 | `2/2 pass` | XOM/CVX `213.7s`, MSFT/GOOGL `144.8s` | Fixed energy over-deep routing and software risk lens activation. |
| `20260602_fin_agent_latency_retrieval_prompt_compaction_v0_7_cross_sector_closeout` | 3 | `3/3 pass` | LLY `96.7s`, WMT/TGT `140.2s`, XOM/CVX `140.9s`, total tool calls `12` | Cross-sector smoke covering healthcare focused, consumer standard, energy standard. |
| `20260602_fin_agent_latency_retrieval_prompt_compaction_v0_8_research_onepass_smoke` | 2 | `2/2 pass`, superseded for LLY output quality | LLY `95.2s`, XOM `148.8s` | Revealed LLY revenue percentage drift in final memo surface. |
| `20260602_fin_agent_latency_retrieval_prompt_compaction_v0_10_focused_memo_guard` | 1 | `1/1 pass` | elapsed `113.8s`, tool calls `6`, Research Lead `2` calls / `9260` tokens, Memo `1` attempt / `6273` tokens | Accepted focused guard rerun; no percentage drift or Chinese dangling-value phrase. |

### Retrieval runtime

- BGE CUDA metadata was true in accepted runs.
- v0.10 SEC search grouped route: candidate generation `23ms`, BGE rerank `1139ms`, resource/model load `26581ms`, member routes cached.
- Route coalescing reduced duplicate real `sec_search_filings` calls inside a case, but does not remove BGE cold load across separate eval processes.

### Output quality

- WMT/TGT and XOM/CVX standard cases: stable `1`-attempt Memo Writer after compaction, but outputs remain bounded research memos rather than full deep reports.
- LLY focused case: v0.10 correctly states evidence boundary and avoids unsupported R&D/product-cycle claims. It is evidence-thin because local SEC/8-K data did not provide clinical/regulatory/product-cycle external facts.
- v0.9 was superseded because numeric cleanup left a Chinese dangling phrase after removing unsupported numeric conversion.

## Experiment Governance

- Hypothesis: coalescing retrieval routes and compacting prompts reduce duplicate retrieval / token cost while preserving gate pass and bounded evidence behavior.
- Decision target: real full-chain pass on multiple sectors, BGE CUDA active, no duplicate route loop break, Memo Writer stable at one attempt for standard/focused reruns, no numeric/unit drift in focused output.
- Baselines: prior standard focused runs with duplicated SEC search routes, Memo Writer repair attempts, high token cost, and LLY focused revenue-unit drift.
- Stop conditions: any gate failure, secret persistence, BGE CPU-only regression, unsupported external claims, or numeric/unit drift in rendered answer.
- Decision label: proceed with diagnostic acceptance; do not promote as final deep-investment-report quality.
- Mainline decision: keep code changes; next optimization should target Research Lead `2` calls, exact-value row selector, and persistent retrieval worker.

## Runtime Efficiency

- Wall time:
  - v0.7 cross-sector: about `382s` for 3 cases.
  - v0.10 focused LLY: `113.8s`.
- Stage timing:
  - Retrieval candidate generation is now milliseconds when ledger store is used.
  - BGE rerank is about `1.1s` for focused LLY.
  - BGE/resource load remains about `26s` for first case in a fresh process.
- Bottleneck diagnosis:
  - DeepSeek Research Lead still often consumes two calls and about `9K` tokens.
  - BGE is reused inside one graph/process but not across separate eval process launches.
  - Focused exact-value ledger rows can be too broad (`120` rows in v0.10), wasting downstream selection budget.
- Efficiency improvement:
  - Route coalescing and cached member observations reduce duplicate SEC search/BGE calls.
  - Research Lead and Memo Writer prompt compaction reduced common Memo token range to about `5K-10K`, but Lead remains high.
- Serving latency implication:
  - A product session should keep retrieval/BGE runner resident; otherwise each fresh process pays model load.
  - For API UX, focused answer path is still around 1.5-2 minutes locally under real DeepSeek; standard cases around 2-3 minutes.

## Caveats And Next Step

- Not run: full 17-case regression after v0.10 guard; avoided due token/time cost because cross-sector smoke already covered core changed surfaces.
- Known risks:
  - Research Lead second call unresolved.
  - Healthcare focused case is evidence-limited under current local knowledge base.
  - Memo depth remains bounded by ClaimCard density and source coverage.
- Reproduce:
  - Use `scripts/eval_multi_agent_real_llm_chain.py` with `--real-evidence-operators` and the run ids above; runtime credential should come from environment variable only.
- Next decision:
  - Before merge/mainline closeout, run a smaller 5-case regression covering exact lookup, focused healthcare, standard consumer, standard energy, and one multi-turn scope-revision case.
