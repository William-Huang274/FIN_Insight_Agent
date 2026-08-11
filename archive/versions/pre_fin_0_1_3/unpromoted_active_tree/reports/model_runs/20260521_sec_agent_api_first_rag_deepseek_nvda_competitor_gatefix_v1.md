# Model Run: 20260521_sec_agent_api_first_rag_deepseek_nvda_competitor_gatefix_v1

## Summary
- Purpose: validate the API-first SEC RAG chain on the representative NVDA growth + competitor free query after structural contract fixes.
- Status: completed.
- Run type: free-query inference + deterministic post-gate evaluation.
- Timestamp: 2026-05-21.
- Environment: cloud RTX 5090 instance, DeepSeek API synthesis, BGE-M3 rerank on CUDA.

## Code And Command
- Entry point: `scripts/cloud/sec_agent_interactive.py`
- Backend route: `api_model_call`
- Planner: DeepSeek API Query Contract planner.
- Summary API: DeepSeek `deepseek-v4-pro`.
- Credential handling: API key supplied through process environment only; no key written to repo artifacts.
- Important changed files:
  - `scripts/cloud/sec_agent_interactive.py`
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - `scripts/validate_sec_benchmark_v2_semantic_contracts.py`

## User Query
```text
你觉得nvda的增长势头主要是因为什么，同行业的主要竞争对手是谁
```

## Inputs
- Source inventory: current 30-company SEC 10-K inventory.
- Scope: all 30 companies available to the planner/retriever; Query Contract focused the answer on NVDA, AMD, AVGO, and INTC.
- Years: 2023, 2024, 2025.
- Source policy: SEC-only, 10-K only.
- Chain:
  1. Planner API -> Query Contract
  2. Retrieval + BM25/BGE-M3 rerank
  3. Runtime Exact-Value Ledger
  4. Evidence Coverage Matrix
  5. Judgment Plan + DeepSeek synthesis
  6. Deterministic gates as audit.

## Structural Fixes Validated
- Natural-language answer fields no longer inline raw `metric_id`; exact-value support stays in sibling `metric_ids` / `supporting_metric_ids` arrays.
- Runtime ledger rejects percentage-of-revenue tables when rows are misclassified as dollar values.
- Runtime ledger rejects `$ Change` / `% Change` columns as period-level exact values.
- Free-query semantic gate now supports `selected_companies`: `focus_tickers` can be retrieval candidates without forcing every candidate ticker into the final answer.
- Unsupported named facts are removed from prose instead of being rendered as placeholder text such as `相关命名标签`.

## Outputs
- Cloud run directory:
  - `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260521_234353_60a9e00112`
- Local synced artifacts:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_234353_60a9e00112/query_contract.json`
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_234353_60a9e00112/runtime_evidence_coverage_matrix.json`
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_234353_60a9e00112/runtime_exact_value_ledger.json`
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_234353_60a9e00112/qwen/input_output.md`
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_234353_60a9e00112/post_gates/sec_benchmark_post_gates_summary.json`

## Results
- Deterministic gates: `ok=True`, `pass=12`, `fail=[]`.
- `qwen_answer_ratio=1.0`.
- Runtime ledger rows: 62.
- Context rows: 120.
- Coverage Matrix:
  - `coverage_complete=True`
  - `primary_complete=True`
  - `answer_status=complete`
  - `support={'medium': 1, 'strong': 2}`
- NVDA R&D ledger values after filtering:
  - 2023: `7,339（百万美元）`
  - 2024: `8,675（百万美元）`
  - 2025: `12,914（百万美元）`

## Rendered Model Output
```text
NVDA的增长势头主要由数据中心业务爆发驱动，同行业主要竞争对手包括AMD、AVGO和INTC。

Driver 1. NVDA的Compute & Networking收入在2023-2025财年呈现爆发式增长，是整体增长势头的核心引擎。
   why: 数据中心收入是NVDA最大的收入来源，其高速增长直接解释了公司整体营收的扩张。
   依据数值: NVDA 2023 Compute & Networking (数据中心/计算收入): 15,068（百万美元）；NVDA 2024 Compute & Networking (数据中心/计算收入): 47,405（百万美元）；NVDA 2025 Compute & Networking (数据中心/计算收入): 116,193（百万美元）
   SEC证据: NVDA 2023 10-K Item 7；NVDA 2024 10-K Item 7；NVDA 2025 10-K Item 7

Driver 2. NVDA的毛利率持续提升，从2023财年的56.9 %升至2025财年的75.0 %，表明其产品组合向高价值数据中心产品倾斜且定价能力增强。
   why: 毛利率的显著提升反映了NVDA在AI/GPU领域的竞争优势和盈利能力的增强。
   依据数值: NVDA 2023 Gross margin (毛利率): 56.9 %；NVDA 2024 Gross margin (毛利率): 72.7 %；NVDA 2025 Gross margin (毛利率): 75.0 %
   SEC证据: NVDA 2023 10-K Item 7；NVDA 2024 10-K Item 7；NVDA 2025 10-K Item 7

Driver 3. 在AI/GPU半导体领域，AMD是NVDA的直接竞争对手，其数据中心收入在2023-2025财年也呈现增长趋势，但规模远小于NVDA。
   why: AMD在数据中心GPU市场与NVDA直接竞争，其收入规模对比反映了NVDA的市场领先地位。
   依据数值: AMD 2023 数据中心/计算收入: 6.5（十亿美元）；AMD 2024 数据中心/计算收入: 12.6（十亿美元）；AMD 2025 数据中心/计算收入: 16.6（十亿美元）
   SEC证据: AMD 2023 10-K Item 7；AMD 2024 10-K Item 7；AMD 2025 10-K Item 7

Driver 4. AVGO和INTC也是AI/GPU半导体领域的重要竞争者，但它们的业务结构和财务表现与NVDA存在显著差异。
   why: AVGO的Semiconductor solutions收入和INTC的资本支出规模反映了它们在该领域的参与度，但它们的盈利能力和增长模式与NVDA不同。
   依据数值: AVGO 2025 Semiconductor solutions (半导体解决方案收入): 30,096（百万美元）
   SEC证据: AVGO 2025 10-K Item 7

limitations:
- 分析仅基于2023-2025财年10-K文件，不包含10-Q、8-K或市场数据。
- 竞争对手选择基于AI/GPU半导体行业相关性，可能未涵盖所有潜在竞争者。
- 精确数值必须由运行时Exact-Value Ledger提供，本计划不包含具体数字。
- 增长归因分析基于管理层讨论与分析中的定性陈述，可能带有主观性。
- SEC-only evidence boundary.
```

## Interpretation
- The chain now proves the intended API-first RAG pattern for this representative prompt: broad 30-company inventory, planner-selected focus, BGE-M3 retrieval, runtime ledger, coverage matrix, DeepSeek synthesis, and audit-only deterministic gates.
- This is a stronger production path than trying to force a local 9B model to provide deep synthesis; the local model route remains useful for offline/gated benchmark work but is not the best route for high-quality free-query analysis.
- Remaining quality issue: the renderer still exposes some awkward exact-value formatting for negative capex proxy rows, and derived phrases such as `增长近7倍` should be governed as model interpretation rather than exact ledger facts.

## Next Decision
- Proceed to a small representative free-query quality set before broader production claims.
- Add an answer-quality rubric for insight depth, causal reasoning, peer selection quality, caveat usefulness, and formatting polish.
- Keep deterministic gates audit-only for free-query mode; do not let them force low-insight ledger dumps.
