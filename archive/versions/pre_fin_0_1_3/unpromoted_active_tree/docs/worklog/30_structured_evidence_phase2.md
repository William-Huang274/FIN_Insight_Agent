# Phase 2 Structured Evidence And Agent Roles

## Direction

The next phase moves the system from raw chunk retrieval toward structured
financial evidence and role-separated agents:

```text
EvidenceObject
-> TableObject / MetricObject / ClaimObject
-> reviewed gold set
-> reranker + small verifier
-> verifier LoRA after enough samples
-> large-model final synthesis, 9B as worker
```

## Execution Plan

### Step 1. Structured Evidence Objects

Goal: generate deterministic first-pass structured objects from the existing
EvidenceObject JSONL without re-downloading SEC filings.

Deliverables:
- `src/evidence/structured_objects.py`
  - `TableObject`: table provenance, rows, normalized text cells, candidate
    period columns, and source evidence IDs.
  - `MetricObject`: metric name, value, unit, period, segment/entity context,
    source object IDs, extraction method, and confidence.
  - `ClaimObject`: narrative claim text, claim type, polarity, source evidence
    ID, local context, and extraction method.
- `src/evidence/structured_extractor.py`
  - Table parser for `[TABLE_START] ... [TABLE_END]` blocks.
  - Heuristic metric extraction from table rows and key narrative sentences.
  - Claim extraction for risk, strategy, demand, cost, capex, visibility, and
    accounting-policy statements.
- `scripts/build_structured_objects.py`
  - Reads `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`.
  - Writes `data/processed_private/structured_objects/sec_tech_10k_tables.jsonl`.
  - Writes `data/processed_private/structured_objects/sec_tech_10k_metrics.jsonl`.
  - Writes `data/processed_private/structured_objects/sec_tech_10k_claims.jsonl`.
  - Writes a summary JSON report.
- `scripts/validate_structured_objects.py`
  - Checks anchor objects for Apple Services gross margin, Snowflake RPO and
    consumption claims, and NVIDIA supply/demand/manufacturing risk claims.

Acceptance checks:
- Script runs locally on the current evidence store.
- At least known Apple Services gross-margin tables become TableObjects and
  MetricObjects.
- At least known Snowflake consumption/RPO and NVIDIA risk sentences become
  ClaimObjects.
- Object IDs are deterministic and traceable to `evidence_id`.

### Step 2. Small Reviewed Gold Set

Goal: convert the current model-authored eval set into a compact reviewed set
that can evaluate planner, object retrieval, verifier, and synthesis.

Deliverables:
- Extend `eval_sets/sec_tech_10k_agent_reasoning_eval.jsonl` or create a
  reviewed v2 file with:
  - query facets,
  - must-have evidence object IDs,
  - acceptable partial evidence,
  - correct answer outline,
  - common wrong conclusions,
  - required caveats.
- Add a scoring script for:
  - planner facet coverage,
  - target object in candidates,
  - selected evidence coverage,
  - cited evidence coverage,
  - synthesis correctness flags.

Acceptance checks:
- 6 current queries can be scored automatically.
- Metrics report separates candidate coverage from selected/cited coverage.
- Human-review placeholders are explicit where labels are still model-authored.

### Step 3. Reranker + Small Verifier

Goal: replace prompt-only LLM verifier as the first-pass filter.

Deliverables:
- Reranker stage over `(SearchTask, structured_object)` and optionally
  `(SearchTask, evidence snippet)`.
- Small verifier stage using 0.8B/1.5B model or equivalent local model:
  - input: task + TableObject/MetricObject/ClaimObject + compact provenance.
  - output: `direct | partial | false`, key facts, missing fields.
- Keep Qwen3.5-9B only for hard cases or batch planner/synthesis smoke tests.

Acceptance checks:
- Verifier no longer depends on fixed first-1,800-character raw chunk crops.
- Adobe RPO and Snowflake RPO cannot be misread as `Revenue Per Opportunity`
  when a `MetricObject`/`TableObject` names it as remaining performance
  obligations.
- Precision-oriented filtering improves false-positive rate without hiding
  target evidence.

### Step 4. Verifier LoRA

Goal: train a small verifier only after enough high-quality labels exist.

Prerequisite:
- 200-500 high-quality verifier samples covering direct, partial, false,
  table-heavy, metric-heavy, and risk/claim-heavy evidence.

Deliverables:
- LoRA training set with task/object pairs and labels.
- Baseline comparison against prompt-only small verifier and reranker-only
  filtering.
- Frozen validation protocol before any final test claim.

Acceptance checks:
- LoRA improves direct/partial/false calibration on validation.
- It does not reduce target-in-selected coverage for critical facets.
- Latency stays compatible with online batched verification.

### Step 5. Final Synthesis Model Role

Goal: keep final synthesis on a larger model while 9B stays a worker.

Policy:
- 9B can handle planner, object extraction assistance, and diagnostic synthesis.
- Final financial answer synthesis should use a larger model until 9B proves it
  can consistently avoid terminology errors, company/segment scope mistakes,
  unsupported capex allocation, and missing evidence miscalibration.

Acceptance checks:
- Final answer quality is judged with the reviewed gold set.
- Each conclusion cites structured object IDs and source evidence IDs.
- The system can explain which evidence was unused and why.

## Current Priority

Step 2 has an auto-mapped draft and coverage evaluator. Continue with human
review of object targets and then wire retrieval/verifier predictions into the
coverage evaluator. Do not tune final synthesis or train verifier LoRA until
reviewed object-level evaluation is available.

## 2026-05-16 Initial Execution

- Created this phase plan.
- Next implementation target:
  `src/evidence/structured_objects.py`,
  `src/evidence/structured_extractor.py`, and
  `scripts/build_structured_objects.py`.

## 2026-05-16 Step 1 Execution

Implemented first-pass structured evidence generation:

- Added `TableObject`, `MetricObject`, and `ClaimObject` schemas in
  `src/evidence/structured_objects.py`.
- Added deterministic extraction in `src/evidence/structured_extractor.py`.
- Added build entry point `scripts/build_structured_objects.py`.
- Added anchor validation entry point `scripts/validate_structured_objects.py`.

Generated artifacts:

- `data/processed_private/structured_objects/sec_tech_10k_tables.jsonl`
- `data/processed_private/structured_objects/sec_tech_10k_metrics.jsonl`
- `data/processed_private/structured_objects/sec_tech_10k_claims.jsonl`
- `data/processed_private/structured_objects/sec_tech_10k_structured_summary.json`

Latest build command:

```powershell
python scripts\build_structured_objects.py
```

Latest build counts:

- EvidenceObjects: 2,842
- TableObjects: 2,187
- MetricObjects: 44,345
- ClaimObjects: 23,598
- Metrics by method:
  `table_row_heuristic=42,410`, `sentence_heuristic=1,935`

Validation command:

```powershell
python scripts\validate_structured_objects.py
```

Validation result: passed.

Anchor checks covered:

- AAPL 2024 Services gross margin: `71,050` USD millions.
- AAPL 2024 Services gross margin percentage: `73.9%`.
- AAPL 2024 gross-margin continuation table keeps period labels and does not
  assign segment to total rows.
- SNOW RPO metrics include table and sentence evidence.
- SNOW consumption/RPO claims are captured.
- NVDA supply/demand/manufacturing risk claims are captured.

Quality fixes made during validation:

- Continuation tables now inherit periods from the nearest prior table header
  instead of arbitrary narrative years.
- Table metric extraction treats group headers such as `Gross margin
  percentage:` as metric context.
- Segment assignment now prioritizes the row label, so Products, Services, and
  total rows are separated.
- Claim and metric keyword matching now uses word-boundary matching to avoid
  false positives such as matching `depend` inside `independent` or `rpo`
  inside `corporations`.

Known limitations:

- This is still a deterministic first pass. It captures useful objects for
  verifier input, but it is not a final financial table parser.
- Sentence-level metric extraction is intentionally conservative after the
  keyword-boundary change; remaining noise should be handled by the next
  reviewed gold set and verifier stages rather than by tuning final synthesis.
- No model training, model inference, reranking, or LoRA run was performed in
  this step.

## 2026-05-16 Step 2 Draft Execution

Implemented the first object-level gold-set draft path:

- Added `scripts/build_object_gold_draft.py`.
  - Input:
    `eval_sets/sec_tech_10k_agent_reasoning_eval.jsonl`
  - Inputs:
    `data/processed_private/structured_objects/sec_tech_10k_tables.jsonl`,
    `sec_tech_10k_metrics.jsonl`, and `sec_tech_10k_claims.jsonl`
  - Output:
    `eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_draft.jsonl`
- Added `scripts/evaluate_object_gold_coverage.py`.
  - With no predictions, it reports gold readiness.
  - With predictions, it expects `query_id`, `candidate_object_ids`,
    `selected_object_ids`, and `cited_object_ids`, then reports candidate,
    selected, and cited facet coverage.

Build command:

```powershell
python scripts\build_object_gold_draft.py
```

Build result:

- Query count: 6
- Facet count: 23
- Facets with object refs: 23
- Facets without object refs: 0

Readiness command:

```powershell
python scripts\evaluate_object_gold_coverage.py
```

Readiness result:

- Query count: 6
- Facet count: 23
- Facets with object targets: 23
- Facet target coverage: 1.0

Important label status:

- The generated v2 file is marked
  `draft_auto_mapped_needs_human_review`.
- Per-facet object refs are marked
  `auto_mapped_from_evidence_needs_human_review_required`.
- This file must not be treated as final human gold labels until target object
  refs have been reviewed and corrected.

Quality notes:

- The draft mapper uses `must_find` terms from the existing reviewed-style eval
  file to score objects inside each target `evidence_id`.
- It filters weak object matches by default with `--min-score 2.0`.
- It intentionally keeps table-level and claim/metric-level candidates when the
  same source evidence carries both context and exact values. Human review
  should decide which are `direct`, `partial`, or false.

Next required work:

- Human-review the v2 object refs and mark each as `direct`, `partial`, or
  `false`.
- Add retriever/verifier prediction export in the same object ID schema so the
  coverage evaluator can compare `candidate`, `selected`, and `cited` object
  coverage.

## 2026-05-16 Object Candidate Retrieval Baseline

Implemented object-level BM25 candidate retrieval:

- Added `src/evidence/structured_text.py` for object search text and previews.
- Added `src/indexing/build_object_bm25_index.py`.
- Added `src/retrieval/object_bm25_retriever.py`.
- Added `scripts/build_object_bm25_index.py`.
- Added `scripts/search_object_bm25.py`.
- Added `scripts/evaluate_object_retrieval.py`.
- Updated `scripts/evaluate_object_gold_coverage.py` to read facet-level
  predictions when available.

Commands:

```powershell
python scripts\build_object_bm25_index.py
python scripts\evaluate_object_retrieval.py --top-k 25 --variant-top-k 25 --predictions-path reports\retrieval_eval\sec_tech_10k_object_bm25_variant_predictions.jsonl --report-path reports\retrieval_eval\sec_tech_10k_object_bm25_variant_eval.json
python scripts\evaluate_object_gold_coverage.py --predictions-path reports\retrieval_eval\sec_tech_10k_object_bm25_variant_predictions.jsonl
python scripts\evaluate_object_retrieval.py --top-k 25 --variant-top-k 25 --selected-top-n 5 --predictions-path reports\retrieval_eval\sec_tech_10k_object_bm25_variant_selected5_predictions.jsonl --report-path reports\retrieval_eval\sec_tech_10k_object_bm25_variant_selected5_eval.json
```

Index result:

- Indexed structured objects: 70,130
- TableObjects: 2,187
- MetricObjects: 44,345
- ClaimObjects: 23,598
- Index path: `data/indexes/bm25/sec_tech_10k_objects`

Evaluation result:

- Gold draft queries: 6
- Facets: 23
- Candidate facet coverage: 1.0
- Selected facet coverage: 0.0
- Cited facet coverage: 0.0
- Lexical selected@5 selected facet coverage: 0.9565
- Lexical selected@5 selected object precision: 0.4174
- Lexical selected@5 selected target objects: 48 / 115 selected objects
- Prediction path:
  `reports/retrieval_eval/sec_tech_10k_object_bm25_variant_predictions.jsonl`
- Report path:
  `reports/retrieval_eval/sec_tech_10k_object_bm25_variant_eval.json`
- Selected@5 prediction path:
  `reports/retrieval_eval/sec_tech_10k_object_bm25_variant_selected5_predictions.jsonl`
- Selected@5 report path:
  `reports/retrieval_eval/sec_tech_10k_object_bm25_variant_selected5_eval.json`

Retrieval design:

- Each facet now uses multiple query variants:
  full query plus facet, facet plus `must_find`, and each `must_find` phrase
  as a separate query.
- Per-variant results are fused with reciprocal-rank style scoring.
- This fixed the Adobe contract-caveat miss from the single long-query
  baseline, where ARR/RPO/subscription terms dominated the shorter cancellation
  caveat sentence.

Decision:

- Candidate recall is sufficient on the current draft gold set.
- Pure lexical selected@5 keeps 22/23 facets covered but has low selected
  object precision, so the next bottleneck is selected evidence precision and
  object-level verifier calibration, not raw candidate reachability.
- The result is still conditional on human review of auto-mapped object labels.

## 2026-05-16 Object Review Export And Rule Verifier

Implemented a deterministic verifier baseline and review export for the current
object candidate pool:

- Added `src/eval/object_verifier.py`.
  - Normalizes object text.
  - Scores each `(facet need, structured object)` with exact phrase matches,
    numeric matches, and important-token partial matches.
  - Emits `direct`, `partial`, or `false` plus matched/missing `must_find`
    phrases.
- Added `scripts/build_object_review_set.py`.
  - Exports candidate review rows for human labeling.
  - Writes a JSONL review file and a CSV review sheet.
- Added `scripts/apply_object_rule_verifier.py`.
  - Reads object BM25 candidate predictions.
  - Applies the deterministic verifier.
  - Writes facet-level `selected_object_ids` and `verifier_decisions`.
- Extended `scripts/evaluate_object_gold_coverage.py`.
  - Adds candidate/selected/cited object precision counts.
  - Can write a JSON report with `--report-path`.

Commands:

```powershell
python -m py_compile src\eval\object_verifier.py scripts\build_object_review_set.py scripts\apply_object_rule_verifier.py scripts\evaluate_object_gold_coverage.py
python scripts\build_object_review_set.py
python scripts\apply_object_rule_verifier.py --output-path reports\retrieval_eval\sec_tech_10k_object_rule_verifier_predictions.jsonl
python scripts\evaluate_object_gold_coverage.py --predictions-path reports\retrieval_eval\sec_tech_10k_object_rule_verifier_predictions.jsonl --report-path reports\retrieval_eval\sec_tech_10k_object_rule_verifier_eval.json
```

Generated artifacts:

- `eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates.jsonl`
- `reports/retrieval_eval/sec_tech_10k_object_review_candidates.csv`
- `reports/retrieval_eval/sec_tech_10k_object_rule_verifier_predictions.jsonl`
- `reports/retrieval_eval/sec_tech_10k_object_rule_verifier_eval.json`
- `reports/model_runs/20260516_phase2_object_rule_verifier_eval.md`

Review export result:

- Candidate review rows: 575
- Rows that are current draft target refs: 112
- Auto label counts:
  - direct: 102
  - partial: 373
  - false: 100

Rule verifier result:

- Candidate facet coverage: 1.0
- Selected facet coverage: 1.0
- Cited facet coverage: 0.0
- Candidate object precision: 0.1948
- Selected object precision: 0.5412
- Selected objects: 85
- Selected target objects: 46

Baseline comparison:

- Lexical selected@5 selected facet coverage: 0.9565
- Lexical selected@5 selected object precision: 0.4174
- Rule verifier selected facet coverage: 1.0
- Rule verifier selected object precision: 0.5412

Decision:

- The rule verifier is good enough as a diagnostic prefilter and human-review
  export path.
- It is not a semantic verifier. It still relies on `must_find` phrase/numeric
  matching and should not be treated as final model quality.
- Next work should focus on reviewing the CSV/JSONL labels, correcting
  auto-mapped target refs, and then replacing or augmenting the rule verifier
  with a reranker plus 0.8B/1.5B small verifier.

## 2026-05-16 Codex-Assisted Object Labeling

Filled the review sheet with first-pass model-assisted labels:

- Added `scripts/label_object_review_candidates_codex.py`.
  - Reads the review candidate JSONL.
  - Loads full structured object text.
  - Applies facet-specific finance evidence rules.
  - Fills `human_label` and `human_notes`.
  - Marks rows as
    `model_assisted_review_by_codex_needs_user_spot_check`.
- Added `scripts/evaluate_object_review_labels.py`.
  - Evaluates retriever/verifier predictions against the labeled candidate
    rows.
  - Reports relevant and direct facet coverage plus selected object precision.

Commands:

```powershell
python -m py_compile scripts\label_object_review_candidates_codex.py scripts\evaluate_object_review_labels.py
python scripts\label_object_review_candidates_codex.py
python scripts\evaluate_object_review_labels.py --predictions-path reports\retrieval_eval\sec_tech_10k_object_rule_verifier_predictions.jsonl --report-path reports\retrieval_eval\sec_tech_10k_object_rule_verifier_codex_label_eval.json
python scripts\evaluate_object_review_labels.py --predictions-path reports\retrieval_eval\sec_tech_10k_object_bm25_variant_selected5_predictions.jsonl --report-path reports\retrieval_eval\sec_tech_10k_object_bm25_selected5_codex_label_eval.json
```

Generated artifacts:

- `eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates_codex_labeled.jsonl`
- `reports/retrieval_eval/sec_tech_10k_object_review_candidates_codex_labeled.csv`
- `reports/retrieval_eval/sec_tech_10k_object_rule_verifier_codex_label_eval.json`
- `reports/retrieval_eval/sec_tech_10k_object_bm25_selected5_codex_label_eval.json`
- `reports/model_runs/20260516_phase2_codex_object_review_labeling.md`

Label distribution:

- Total rows: 575
- Direct: 100
- Partial: 193
- False: 282

Rule verifier against Codex-assisted labels:

- Candidate relevant facet coverage: 1.0
- Candidate direct facet coverage: 1.0
- Selected relevant facet coverage: 1.0
- Selected direct facet coverage: 1.0
- Candidate object precision, relevant: 0.5096
- Selected object precision, relevant: 0.9294
- Selected object precision, direct: 0.6353
- Selected label counts: direct 54, partial 25, false 6

Lexical selected@5 against Codex-assisted labels:

- Selected relevant facet coverage: 0.9565
- Selected direct facet coverage: 0.9565
- Selected object precision, relevant: 0.7739
- Selected object precision, direct: 0.4435
- Selected label counts: direct 51, partial 38, false 26

Decision:

- Use these labels as a first-pass verifier development set.
- Do not call this final human gold. It needs user spot-check, especially on
  boundary cases where a row is `partial` rather than `direct`.
- The current rule verifier is now a useful prefilter baseline to beat with a
  semantic reranker or small verifier.

## 2026-05-16 Object Reranker Baseline Compare

在云端 RTX 4090 上用 ModelScope 下载模型，并在同一份 object-level BM25
top25 候选池上比较两个语义 reranker：

- `BAAI/bge-reranker-v2-m3`
- `Qwen/Qwen3-Reranker-0.6B`

本轮新增：

- `scripts/evaluate_object_reranker.py`
  - 支持 `bm25`、`cross-encoder`、`qwen-reranker` 三种模式。
  - `qwen-reranker` 使用官方 Qwen3 causal-LM yes/no logit scoring，而不是
    普通 `sentence-transformers CrossEncoder`。
- 云端结果已拉回本地：
  - `reports/retrieval_eval/sec_tech_10k_object_bm25_order_cloud_eval.json`
  - `reports/retrieval_eval/sec_tech_10k_object_bge_reranker_v2_m3_cloud_eval.json`
  - `reports/retrieval_eval/sec_tech_10k_object_qwen3_reranker_0_6b_official_cloud_eval.json`
  - `reports/retrieval_eval/sec_tech_10k_object_reranker_baseline_comparison.json`
  - `reports/retrieval_eval/sec_tech_10k_object_reranker_baseline_comparison.csv`
- 模型运行记录：
  - `reports/model_runs/20260516_phase2_object_reranker_baseline_compare.md`

Evaluation setup:

- Labels: 575 Codex-assisted object review labels across 23 facets.
- Candidate boundary: BM25 top25 per facet.
- Selection boundary: reranker selects top5.
- Gain: direct=2, partial=1, false/unlabeled=0.

Results:

| Model | Relevant P@5 | Direct P@5 | False@5 | nDCG@5 | Direct Coverage | Relevant Coverage | Scoring Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 order | 0.7739 | 0.4435 | 1.1304 | 0.7780 | 0.9565 | 0.9565 | 0.0000 |
| BGE reranker v2 m3 | 0.8609 | 0.6174 | 0.6957 | 0.9458 | 1.0000 | 1.0000 | 3.2317 |
| Qwen3 reranker 0.6B official | 0.8522 | 0.5478 | 0.7391 | 0.8857 | 1.0000 | 1.0000 | 7.8213 |

Decision:

- 两个语义 reranker 都明显优于 BM25 order，说明 object-level rerank 是有效方向。
- 当前胜出基线是 BGE reranker v2 m3：direct P@5、nDCG@5、false@5 和速度都优于
  Qwen3-Reranker-0.6B。
- Qwen3-Reranker 必须走官方 yes/no logit scoring。普通 CrossEncoder 路径能跑但
  不是官方推理格式，已作为无效诊断废弃。
- 下一步不应该继续调 BM25 排序，而是用 BGE 生成更干净的 topK evidence pool，
  再接 0.8B/1.5B small verifier 做 `direct/partial/false` 二阶段判断。

## 2026-05-16 BGE Evidence Pool And Qwen3.5 Small Verifier Smoke

实现了 BGE reranker 到 task-specific evidence pool，再到 small verifier 的二阶段
链路：

- `scripts/build_bge_evidence_pool.py`
  - 输入 BGE reranker prediction JSONL。
  - 每个 `(query_id, facet)` 保留 topK，默认 top10。
  - 输出一行一个候选对象，包含 task metadata、BGE rank/score、BM25 rank/score、
    object metadata、preview 和截断后的 `object_text`。
- `scripts/run_qwen_small_verifier.py`
  - 读取 evidence pool。
  - 调用小参 Qwen-style instruct/generation 模型。
  - 输出 `verifier_label`, `verifier_confidence`, `verifier_reason`,
    `verifier_missing_requirements`, `usable_for_synthesis`。
  - 对 Qwen3.5 当前环境的 broken `causal_conv1d` 做了禁用处理，使其能回退到
    torch implementation 加载。
- `scripts/evaluate_small_verifier.py`
  - 对比 Codex-assisted object labels。
  - 输出 accuracy、macro F1、confusion matrix、direct/partial/false class metrics、
    keep-direct 与 keep-relevant 两种策略的 precision/coverage。

Generated artifacts:

- `reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl`
- `reports/verifier/sec_tech_10k_qwen35_4b_small_verifier_smoke10.jsonl`
- `reports/verifier/sec_tech_10k_qwen35_4b_small_verifier_smoke10_eval.json`
- `reports/verifier/sec_tech_10k_qwen35_4b_small_verifier_smoke10_nothink.jsonl`
- `reports/verifier/sec_tech_10k_qwen35_4b_small_verifier_smoke10_nothink_eval.json`
- `reports/model_runs/20260516_phase2_qwen35_small_verifier_smoke.md`

Evidence pool:

- Rows: 230
- Facets: 23
- TopK: 10 per facet
- Object type counts:
  - claim: 134
  - metric: 69
  - table: 27

Qwen3.5-4B smoke:

- Model path: `/root/autodl-tmp/system_disk_backup/root/hf_models/Qwen3.5-4B`
- First prompt attempt: 10 rows, 3 parsed / 7 invalid JSON, wall time 190.3126s.
- No-think prompt attempt: 10 rows, 10 parsed, wall time 36.0561s.
- No-think metrics on `agent_daily_aapl_services_2025 / services_net_sales`:
  - accuracy: 0.7000
  - macro F1: 0.6030
  - direct precision / recall / F1: 0.2500 / 1.0000 / 0.4000
  - policy keep direct: direct precision 0.25, relevant precision 0.75, false rate 0.25

Decision:

- 链路已经打通，但 Qwen3.5-4B 当前环境暂不作为主线 verifier。
- 原因一：当前环境没有可用 fast path；`causal_conv1d_cuda` 与 torch 2.11 ABI
  不兼容，只能禁用后走 torch fallback，速度偏慢。
- 原因二：smoke 中存在 over-direct 倾向，尤其是 table object 携带周边文本时，
  模型会按可用上下文判断为 direct，而当前标签可能按对象身份更严格地判 false。
- 后续要么修好 Qwen3.5 的 FLA/causal runtime，要么换一个更稳定的小型 instruct
  checkpoint，再跑完整 230-row verifier evaluation。

## 2026-05-16 Qwen3.5 Fast Path And 2B/4B Smoke

按“不要走 fallback”的要求，在云端修复了 Qwen3.5 verifier 的 runtime fast path：

- 自编译 `causal-conv1d==1.6.2.post1` wheel：
  - torch: `2.11.0+cu130`
  - CUDA compiler: `nvidia-cuda-nvcc==13.0.88`
  - aligned `nvidia-nvvm==13.0.88` and `nvidia-cuda-crt==13.0.88`
  - target arch: RTX 4090 `sm_89`
  - wheel: `/root/autodl-tmp/wheels/causal_conv1d_torch211_cu13_sm89/causal_conv1d-1.6.2.post1-cp312-cp312-linux_x86_64.whl`
- 补齐 `cuda-cccl==1.0.0`，解决 `nv/target` header 缺失。
- 用临时 lib symlink 解决 pip CUDA runtime 只有 `libcudart.so.12`、没有
  `libcudart.so` 的链接问题。
- 更新 `scripts/run_qwen_small_verifier.py`：
  - 增加 `--require-fast-path`。
  - 当 `causal_conv1d_cuda`、Transformers causal-conv1d availability、
    flash-linear-attention availability 任一不可用时直接失败。
  - 报告 `fast_path_status`、model load timing、generation timing。

Strict sanity:

- 4B strict sanity 2 rows:
  - `causal_conv1d_cuda_import=true`
  - `causal_conv1d_available=true`
  - `flash_linear_attention_available=true`
  - `fallback_enabled=false`
  - load 78.8360s, generation 7.5353s
- 2B strict sanity 2 rows:
  - `causal_conv1d_cuda_import=true`
  - `causal_conv1d_available=true`
  - `flash_linear_attention_available=true`
  - `fallback_enabled=false`
  - load 37.9768s, generation 9.8751s

Smoke comparison on the first 10 BGE evidence-pool rows:

| Model | Parse | Accuracy | Macro F1 | Direct P/R | False P/R | Generation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-4B | 10/10 | 0.7000 | 0.6030 | 0.25 / 1.00 | 1.00 / 0.8333 | 35.7215s |
| Qwen3.5-2B | 7/10 | 0.4000 | 0.5556 | 1.00 / 1.00 | 0.00 / 0.00 | 146.9374s |

Decision:

- fast path 已打通，后续 verifier 实验可以要求 strict fast path，不再接受静默
  torch fallback 的指标。
- 4B 是当前更合理的小 verifier 候选，但仍有 over-direct 问题，尤其是 table
  object 携带周边文本时会把上下文中的强证据也算进对象判断。
- 2B 当前不适合作为主线 verifier：它更容易输出长解释，3/10 JSON 截断无效，
  且在本 smoke 切片中基本不能拒绝 false object。
- 下一步应先调短 JSON 输出和 decoder，再对 4B strict-fast-path 跑完整 230-row
  verifier evaluation。2B 只作为诊断候选保留。

Model run:

- `reports/model_runs/20260516_phase2_qwen35_fastpath_2b4b_smoke.md`

### Compact Verifier Output Update

随后把 small verifier 的默认职责收紧成分类器：

- `scripts/run_qwen_small_verifier.py`
  - 默认 prompt 只要求 `label/confidence/usable_for_synthesis`。
  - 新增 `--debug-output-explanations`。
  - 只有 debug 模式才要求并写出 `verifier_reason`,
    `verifier_missing_requirements`, `raw_output`。
  - 默认输出 JSONL 不再携带解释字段，避免 serving 路径被长解释拖慢或截断。
- 云端 Qwen3.5-4B compact sanity：
  - command profile: `--require-fast-path --max-new-tokens 64 --limit 2`
  - rows: 2
  - parse: 2/2
  - debug fields: none
  - fast path: causal-conv1d true, FLA true, `fallback_enabled=false`
  - generation: 3.0531s / 2 rows
- Artifacts:
  - `reports/verifier/sec_tech_10k_qwen35_4b_compact_sanity2.jsonl`
  - `reports/logs/qwen35_4b_compact_sanity2_20260516.log`

Decision:

- 后续 verifier 默认走 compact 分类输出。
- 只有做错误分析、样本审计、或给人看边界样本时才打开 debug explanation。

## 2026-05-16 Qwen3.5-4B Compact Full Verifier Evaluation

按下一步路线，在完整 BGE top10 evidence pool 上跑了 compact Qwen3.5-4B
strict-fast-path verifier：

- Input: `reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl`
- Rows: 230
- Facets: 23
- Model: `/root/autodl-tmp/system_disk_backup/root/hf_models/Qwen3.5-4B`
- Profile:
  - `--batch-size 4`
  - `--max-length 4096`
  - `--max-new-tokens 64`
  - `--require-fast-path`
  - no debug explanations in the full run
- Runtime:
  - no fallback warning
  - 230/230 parsed
  - script generation wall time: 335.5812s

Artifacts:

- `reports/verifier/sec_tech_10k_qwen35_4b_compact_full230.jsonl`
- `reports/metrics/sec_tech_10k_qwen35_4b_compact_full230_metrics.json`
- `reports/logs/qwen35_4b_compact_full230_20260516.log`
- `reports/metrics/sec_tech_10k_qwen35_4b_compact_full230_error_analysis.json`
- `reports/metrics/sec_tech_10k_qwen35_4b_compact_full230_error_examples.csv`
- `reports/model_runs/20260516_phase2_qwen35_4b_compact_full_verifier_eval.md`

Results:

| Policy | Kept Objects | Avg / Facet | Direct Precision | Relevant Precision | False Rate | Direct Coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BGE top10 pool | 230 | 10.0000 | 0.3783 | 0.7174 | 0.2826 | 1.0000 |
| Qwen keep direct | 89 | 3.8696 | 0.7416 | 0.9551 | 0.0449 | 1.0000 |
| Qwen keep direct+partial | 159 | 6.9130 | 0.5346 | 0.8113 | 0.1887 | 1.0000 |

Class metrics:

- direct precision / recall / F1: 0.7416 / 0.7586 / 0.7500
- partial precision / recall / F1: 0.3571 / 0.3205 / 0.3378
- false precision / recall / F1: 0.4930 / 0.5385 / 0.5147

Interpretation:

- `keep_direct` 是明显有效的 precision gate：相比 BGE top10 pool，把 false rate
  从 28.26% 压到 4.49%，同时保留 23/23 facet 的 direct coverage。
- `direct+partial` 更宽，但 false rate 仍有 18.87%，不适合作为直接喂给 synthesis
  的默认策略。
- 当前 verifier 的核心问题不是解析或 runtime，而是 direct/partial/false 的定义边界。

Debug subset:

- 对 4 个 `pred_direct_gold_false` 和 2 个 `gold_direct_pred_false` 样本打开
  `--debug-output-explanations` 跑了小样本解释。
- 观察到 label/prompt 协议不一致：
  - 当前部分 gold `direct` 更像“直接支持 facet 的一个关键 aspect”。
  - prompt 可能把 `must_find` 解释成“一个对象必须满足全部 aspects”。
  - 有些 object label 对 table/claim identity 很严格，但 object_text 又携带同块上下文，
    模型会根据上下文判 direct。

Decision:

- Qwen3.5-4B compact verifier 可以作为 BGE 之后的 precision gate 候选。
- 不应马上换更大模型或微调；先要统一 label protocol 与 verifier prompt。
- 下一步更合理的是把 facet 拆到 aspect-level verifier task，或明确 direct 是
  “支持任一 required aspect”还是“完整支持全部 must_find”。然后再复跑 4B compact eval。

## 2026-05-16 Aspect-Level Qwen3.5-4B Verifier Evaluation

按上一步结论，把 verifier task 从 facet-level 拆成 aspect-level：

- 新增 `scripts/build_aspect_evidence_pool.py`。
- 新增 `scripts/evaluate_aspect_verifier.py`。
- 更新 `scripts/run_qwen_small_verifier.py`，当输入行含 `aspect` 时，prompt 明确要求只判断当前单个 aspect，不再要求一个 object 覆盖整个 facet 的所有 `must_find`。

Input/output:

- Source pool: `reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl`
- Aspect pool: `reports/evidence_pool/sec_tech_10k_bge_top10_aspect_evidence_pool.jsonl`
- Predictions: `reports/verifier/sec_tech_10k_qwen35_4b_aspect_compact_full730.jsonl`
- Metrics: `reports/metrics/sec_tech_10k_qwen35_4b_aspect_compact_full730_metrics.json`
- Retrieval review: `reports/metrics/sec_tech_10k_qwen35_4b_aspect_compact_full730_retrieval_review.csv`
- Model run: `reports/model_runs/20260516_phase2_qwen35_4b_aspect_verifier_eval.md`

Aspect pool build:

- source rows: 230
- aspect rows: 730
- facets: 23
- aspects: 73
- weak aspect labels:
  - direct: 157
  - partial: 261
  - false: 312

Runtime:

- Model: Qwen3.5-4B
- Profile: `batch-size=4`, `max-length=4096`, `max-new-tokens=64`, `--require-fast-path`
- Fast path: causal-conv1d true, flash-linear-attention true, `fallback_enabled=false`
- Parse: 730/730
- Load wall time: 76.9277s
- Generation wall time: 434.2391s
- Total wall time: 511.1668s

Metrics:

| Policy | Kept Objects | Direct Precision | Relevant Precision | False Rate | Direct Aspect Recall On Gold-Direct | Relevant Aspect Recall On Gold-Relevant |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BGE top10 aspect pool | 730 | 0.2151 | 0.5726 | 0.4274 | 1.0000 | 1.0000 |
| Qwen keep direct | 287 | 0.5087 | 0.8537 | 0.1463 | 1.0000 | 0.9851 |
| Qwen keep direct+partial | 389 | 0.3985 | 0.7481 | 0.2519 | 1.0000 | 0.9851 |

Class metrics:

- direct precision / recall / F1: 0.5087 / 0.9299 / 0.6576
- partial precision / recall / F1: 0.3627 / 0.1418 / 0.2039
- false precision / recall / F1: 0.6276 / 0.6859 / 0.6555

Retrieval review:

- aspects total: 73
- aspects with predicted direct: 70
- aspects with weak gold direct: 48
- weak-gold direct aspects recovered by predicted-direct gold-direct evidence: 48/48
- aspects with predicted direct but no weak gold direct: 22
- aspects with at least one predicted-direct weak-false object: 16

观察：

- aspect-level 拆分解决了 facet-level verifier 的一个关键误差来源：模型不再因为单个 object 没覆盖全 facet 而拒绝强证据。
- 召回/覆盖方向是对的：Qwen keep-direct 把 BGE top10 的 false rate 从 0.4274 压到 0.1463，同时保住 48/48 weak-gold direct aspects。
- 但 precision 数字不能按最终 gold 解读。当前 aspect labels 是从 `matched_must_find` / `partial_must_find` / `missing_must_find` 自动派生的弱标签，很多 semantically useful evidence 被标成 partial/false。
- 示例：AAPL Services net sales 的 advertising/App Store/cloud services、ADBE ARR/RPO contract caveats、NVDA foundry risk、AMZN AWS operating income driver 等样本，模型选到的证据对 aspect 有用，但弱标签偏保守。

Decision:

- aspect-level verifier 是后续 evidence pool 的主线语义单元。
- 当前结果暂时只作为 diagnostic，不把 direct precision 0.5087 当作最终 verifier 质量。
- 下一步应该先做人审 aspect gold subset，再用 BGE score + Qwen label/confidence 做二阶段校准；否则继续调 prompt 或换模型会被弱标签噪声误导。

## 2026-05-16 Human Gold Subset And Precision Gate Calibration

按新的金融证据判定协议做人审子集，不再只依赖脚本派生的 weak aspect label。

Added:

- `docs/worklog/35_financial_evidence_label_protocol.md`
- `scripts/build_aspect_policy_human_gold.py`
- `scripts/evaluate_aspect_policy_human_gold.py`

Artifacts:

- Human gold subset: `eval_sets/sec_tech_10k_aspect_policy_human_gold_v0_1.jsonl`
- Metrics: `reports/metrics/sec_tech_10k_aspect_policy_human_gold_v0_1_metrics.json`
- Model run ledger: `reports/model_runs/20260516_phase2_aspect_human_gold_policy_eval.md`

Review scope:

- 标注单位：`(query_id, facet, aspect, object_id)`。
- 只评估当前最接近 serving 的策略：每个 aspect 选一个 Qwen direct 候选。
- 覆盖三种 policy 的 union：
  - `qwen_direct_highest_confidence`
  - `qwen_direct_highest_rerank`
  - `qwen_direct_highest_rerank_conf90`

Manual labels:

- reviewed rows: 90
- human direct: 76
- human partial: 14
- human false: 0
- weak-label disagreement: 38/90

Policy metrics:

| Policy | Selected Aspects | Missing Aspects | Citation Precision | Broad Relevance Precision | Citation Aspect Coverage | Relevant Aspect Coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen direct, highest confidence | 70/73 | 3 | 0.9000 | 1.0000 | 0.8630 | 0.9589 |
| Qwen direct, highest rerank | 70/73 | 3 | 0.8571 | 1.0000 | 0.8219 | 0.9589 |
| Qwen direct, highest rerank, confidence >= 0.90 | 70/73 | 3 | 0.8714 | 1.0000 | 0.8356 | 0.9589 |

Missing aspects:

- SNOW `customer_metrics`: `11,159 total customers`
- SNOW `rpo_visibility`: `weighted-average remaining life 2.4 years`
- ADBE `rpo_visibility`: `approximately 65% recognized over next 12 months`

Interpretation:

- 当前 weak-label precision 确实低估了 Qwen verifier。很多 weak `partial` 应该是 citation-grade `direct`，例如 AAPL advertising、SNOW visibility、ADBE contract caveat、AMZN AWS metrics 等。
- 也有少数 weak `direct` 应该降为 `partial`，例如 AAPL App Store accounting context 不能单独证明 App Store 是 2025 Services net sales 增长驱动。
- 对最终 synthesis，不能把所有 Qwen `direct` 当同一层证据使用。更合理的是拆成：
  - `citation_evidence`: human/protocol direct，可直接引用；
  - `background_evidence`: partial，可提供上下文但不能当最终结论证据；
  - `missing_aspects`: 当前没有 citation-grade evidence，需要扩大召回或回到原文上下文。
- 最高 verifier confidence policy 在这批样本上比最高 BGE rerank 更适合作为 citation candidate selector；rerank 有时会把更宽泛的 table/context 排到更前。

Decision:

- 后续 precision gate 不做简单 keep/drop，而做 citation/background/reject 三层 evidence pool。
- 第一版 selector 可以用 Qwen `direct` 的最高 confidence，rerank 只做 tie-break；然后显式保留 partial/background 给 synthesis。
- 下一步实现 calibrated evidence pool exporter：按 query/facet/aspect 输出 citation evidence、background evidence 和 missing aspects。

## 2026-05-16 Calibrated Evidence Pool Export

实现并运行 calibrated evidence pool exporter：

- `scripts/export_calibrated_evidence_pool.py`
- `scripts/evaluate_calibrated_evidence_pool.py`

正式输出不携带 human audit label，避免后续 synthesis 泄漏人工标注：

- Aspect JSONL: `reports/evidence_pool/sec_tech_10k_calibrated_evidence_pool.jsonl`
- Grouped JSON: `reports/evidence_pool/sec_tech_10k_calibrated_evidence_pool_grouped.json`
- Export report: `reports/metrics/sec_tech_10k_calibrated_evidence_pool_report.json`
- Human-gold eval: `reports/metrics/sec_tech_10k_calibrated_evidence_pool_human_gold_eval.json`
- Model run: `reports/model_runs/20260516_phase2_calibrated_evidence_pool_export.md`

Policy:

- Citation candidate: Qwen verifier label is `direct` and confidence >= `0.90`.
- Citation selector: `verifier_confidence + 0.20 * rerank_score`，然后按 confidence/rerank/pool rank 打平。
- Max citation per aspect: 1。
- Background: 剩余 Qwen `direct` 或 `partial`，每个 aspect 最多 3 条。
- Missing: 没有 confident Qwen direct candidate。

Result:

- queries: 6
- facets: 23
- aspects: 73
- citation evidence: 70
- background evidence: 178
- missing aspects: 3

Missing aspects:

- SNOW `customer_metrics`: `11,159 total customers`
- SNOW `rpo_visibility`: `weighted-average remaining life 2.4 years`
- ADBE `rpo_visibility`: `approximately 65% recognized over next 12 months`

Human-gold audit:

- reviewed citation rows: 70
- human direct: 65
- human partial: 5
- citation precision: 0.9286
- broad relevance precision: 1.0000
- reject rate: 0.0000

Policy sweep on the reviewed subset:

| Selector | Citation Precision | Selected Aspects |
| --- | ---: | ---: |
| highest confidence | 0.9000 | 70/73 |
| highest rerank | 0.8571 | 70/73 |
| confidence + 0.20 * rerank | 0.9286 | 70/73 |

Interpretation:

- 这个 exporter 已经把“可引用证据”和“背景证据”拆开了，后续 synthesis 不应再把 partial/background 当硬引用。
- 0.20 rerank weight 是小样本校准值，不应过度包装成最终结论；它目前只是第一版可用 selector。
- 当前主要瓶颈不是噪声，而是 3 个 missing aspects。下一步 synthesis 应该显式报告缺口，或者触发 context expansion / wider recall。

## 2026-05-16 Calibrated Evidence Pool Synthesis Demo

实现并在云端 RTX 4090 上运行最终中文 synthesis demo：

- `scripts/run_calibrated_synthesis_demo.py`
- 输出：
  `reports/demo/qwen9b_calibrated_synthesis_demo.json`
- 模型运行记录：
  `reports/model_runs/20260516_phase2_qwen35_9b_calibrated_synthesis_demo.md`

运行配置：

- Model: Qwen3.5-9B, vLLM text-only mode, no CPU offload。
- Context: `max_model_len=8192`，`synthesis_max_tokens=1200`。
- Evidence input: calibrated grouped evidence pool，只把 `citation_evidence`
  当可引用证据，`background_evidence` 只作上下文。
- Leakage guard: final prompt 不包含 `reference_answer_points`，human-gold
  audit label 不进入 synthesis prompt。

结果：

- queries: 6
- parse success: 6/6
- model quality flags: 5 `good`, 1 `mixed`
- evaluated facets/aspects: 23 / 73
- prompt-packed citation evidence: 70
- prompt-packed background evidence: 47
- input missing aspects: 3
- model cited objects: 38
- cited citation objects: 37
- cited background-only objects: 1
- invalid cited object IDs: 0
- citation object use rate: 0.5286
- cited object precision against input pool: 1.0000
- total wall time: 263.5841s
- model load: 69.5204s
- per-query generation after resident load: about 28.3-39.6s

质量观察：

- AAPL, AMZN, NVDA, MSFT/GOOGL 的中文总结能围绕关键财务事实和风险
  caveat 组织，并引用 evidence object。
- SNOW 被模型标为 `mixed` 是合理的：当前 evidence pool 缺少 `11,159 total
  customers` 和 `weighted-average remaining life 2.4 years` 两个 citation-grade
  aspects，模型在最终答案里明确列为缺口。
- ADBE 也明确报告了 `approximately 65% recognized over next 12 months` 缺口。
- 第一轮 900-token output budget 在 NVDA 和 MSFT/GOOGL 长答案上导致 JSON 截断；
  最终运行通过压缩 prompt metadata 并把 output budget 提到 1200 解决。

Decision:

- calibrated evidence pool 可以作为后续 final synthesis 的默认输入 contract。
- 当前结果仍是 diagnostic，不是最终金融质量评测；下一步要加 query-rubric
  answer scorer，并对 3 个 missing aspects 做 context expansion / wider recall。

## 2026-05-16 Cell-Level Table Extraction Repair

问题：

- 原始 TableObject 只保留 `rows`，MetricObject 通过简单 row heuristic 抽数，容易把 header/year/% change 列当成普通指标。
- 表格单位只看表格前后文本，漏掉表内 `(in millions, except percentages)`，导致部分金额单位标成 `usd` 而不是 `usd_millions`。
- 下游 metric/table query 无法用严格 `row x column/year x value/unit/citation` 做 numeric validator。

完成：

- `TableObject` 新增 `cells` 字段，保存 cell-level JSON：`cell_key`、`row_label`、`column_label`、`period`、`raw_value`、`value`、`unit`、`cell_kind`、`active_group`。
- `structured_extractor` 增加逻辑单元格解析，合并 `$ 196,175`、`22 %` 这类拆散单元；年度值标为 `period_value`，同比/变化列标为 `change_value`。
- `MetricObject.metadata` 增加 `cell_key`、`cell_kind`、`logical_column_index`；年度金额 cell confidence 提高到 0.82，change cell 降为 0.64。
- `structured_text` 为检索文本加入 cell text 和常见金融同义词：`operating income / income from operations`、`headcount / employees`、`capex / purchases of property and equipment` 等。

验证：

- 重建结构化对象：`table_count=2,187`、`metric_count=41,939`、`claim_count=23,598`。
- META 2025 广告收入表现在含 `advertising__2025`、`advertising__2024`、`advertising__2023` cell，单位为 `usd_millions`；`2025 vs 2024 % change` 被标为 `change_value`，不再冒充年度值。
- 重建 BM25 对象索引：`records=67,724`，其中 `table=2,187`、`metric=41,939`、`claim=23,598`。

Decision:

- 上游表格抽取已达到 cell-level numeric validator 的输入形态。
- 还没完成的是 final synthesis 的 machine-readable cell JSON 输出 contract，以及基于 `MetricObject/TableObject.cells` 的 post-synthesis numeric validator。
