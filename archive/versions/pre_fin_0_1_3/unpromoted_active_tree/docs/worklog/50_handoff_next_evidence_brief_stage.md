# 新窗口交接文档：Evidence Brief 阶段

更新时间：2026-05-17

## Current Goal

当前项目已经从简单 RAG 检索推进到 `Raw SEC sources -> EvidenceObject -> MetricObject/TableObject/ClaimObject -> task-specific evidence pool -> LLM synthesis`。最新讨论的下一步不是继续扩大样本，也不是继续调最终中文总结 prompt，而是新增一个独立的 **Evidence Reading / Evidence Brief** 阶段：

```text
SearchTask evidence pool
-> Evidence Reading / Evidence Selection
-> Task Evidence Brief
-> Final Synthesis
-> Citation + numeric validator
```

核心目标：让模型先把筛过的材料读完，按 facet/aspect 选择哪些证据用于推理、哪些只是定义/背景/不能使用、哪些信息缺失，再让 final synthesis 基于结构化 brief 写中文答案。这样解决当前综合总结中 coverage 不足、citation 使用率偏低、caveat/counter-evidence 使用不足、比较口径不严的问题。

## Important Constraints

- 不要把当前 answer-quality report 当 teacher 或 judge；它现在明确是 `strict_diagnostic_not_teacher`。
- 不要写入云端密码、token 或临时凭据。
- 当前固定资源假设仍是单卡 RTX 4090；不要默认多卡或更大显存。
- 国内模型下载优先走 ModelScope；不要默认 HuggingFace 可用。
- 不要用 fallback 掩盖根因。invalid JSON 可以 targeted retry，但不能把 retry 包装成 repair 能力。
- final synthesis 不应直接从 raw/background evidence 临时挑事实；后续应基于 `EvidenceBriefObject`。
- 任何新效果实验前先写清楚 diagnostic-only gate：coverage、citation discipline、latency、teacher-ready 条件。

## Repository State

- Workspace: `D:\FIN_Insight_Agent`
- Branch: `feature/phase1-sec-foundation`
- Worktree: dirty，包含大量 Phase 2 scripts/reports/eval_sets/worklogs，未提交。
- 最近云端相关进程已确认无残留。
- 不要回滚未提交改动；这些是当前项目主线产物。

## Latest Accepted Artifacts

最终 synthesis：

- `D:\FIN_Insight_Agent\reports\demo\qwen9b_expanded_v0_2_cell_vllm_facet_memory_aspectfit_synthesis_16k_celljson_4500_retry6500_merged_repaired.json`

最终摘要：

- `D:\FIN_Insight_Agent\reports\logs\qwen9b_aspectfit_4500_retry6500_merged_scaleaware_summary.json`

Citation gate：

- `D:\FIN_Insight_Agent\reports\quality\sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit_citation_validation_16k_celljson_4500_retry6500_merged_repaired.json`

Cell numeric gate：

- `D:\FIN_Insight_Agent\reports\quality\sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit_metric_cell_validation_16k_celljson_4500_retry6500_merged_repaired_scaleaware.json`

Answer quality gate：

- `D:\FIN_Insight_Agent\reports\quality\sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit_answer_quality_16k_celljson_4500_retry6500_merged_repaired_scaleaware.json`

Evidence memory：

- `D:\FIN_Insight_Agent\reports\evidence_pool\sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit.json`

Query set：

- `D:\FIN_Insight_Agent\eval_sets\sec_tech_10k_expanded_eval_v0_2.jsonl`

Model run ledger：

- `D:\FIN_Insight_Agent\reports\model_runs\20260517_phase2_aspectfit_memory_celljson_synthesis_rerun.md`

## Latest Metrics

Latest run: Qwen3.5-9B, vLLM text-only, 16k context, aspectfit facet memory, 13 expanded v0.2 queries.

- Parse: `13/13 parsed`
- Model quality flags: `good=3`, `mixed=6`, `weak=4`
- Citation gate: `13/13 pass`
- Background cited as fact: `0`
- Invalid cited object IDs after repair: `0`
- Cited object precision against input: `1.0000`
- Citation object use rate: `0.4855`
- Cell gate: `70` reported cells, `66` valid reported cells
- Cell exact rate: `0.9571`
- Cell unit rate: `0.9714`
- Invalid cells: `5`
- Answer quality mean: `0.7107`
- Teacher-ready: `0/13`

Runtime:

- Main 13-query run wall time: `1275.5655s`
- Model load: `68.2165s`
- Targeted retry:
  - `expanded_metric_cloud_segment_table_2023_2025`: `208.5637s`
  - `expanded_metric_revenue_income_cfo_table_2023_2025`: `112.7173s`
- vLLM logs show text-only GPU path, no CPU offload; long table tasks are output-length bottleneck.

## Completed Changes To Remember

- `scripts/build_facet_evidence_memory.py`
  - Added aspect-aware selection so YoY/% aspects prefer percent evidence and risk/caveat aspects prefer claim evidence.

- `scripts/run_calibrated_synthesis_demo.py`
  - Added facet-memory input path, metric/table cell JSON schema, citation counting for `citation_object_ids`, stricter citation-copy instruction.

- `scripts/repair_synthesis_citations.py`
  - Deterministic repair for object_id copy errors when ticker + stable suffix uniquely identifies an input citation object.
  - This does not repair invalid JSON.

- `scripts/validate_synthesis_citations.py`
  - Supports citations in `cell_table.cells[].citation_object_ids`.

- `scripts/validate_metric_table_cells.py`
  - Supports MetricObject/TableObject/ClaimObject validation.
  - Supports YoY derived cells using multiple citation objects.
  - Supports qualitative claim cells.
  - Supports cash outflow sign normalization.
  - Fixed scale-aware validation: `usd_thousands -> usd_millions / 1000`, plus restricted large `usd_unscaled / 1000` compatibility.

- `scripts/score_synthesis_quality.py`
  - Uses cell validation in strict quality gate.
  - Continues to mark all outputs diagnostic, not teacher-ready.

## Current Known Problems

### Non-table synthesis problems

- Coverage-aware synthesis is weak: many complex insight outputs have `low_required_coverage`.
- Citation use rate is low: model often uses only a few salient objects even when more relevant evidence is available.
- Comparability discipline is uneven: e.g. advertising revenue, infrastructure capex, segment operating income, consolidated operating income can be mixed without enough口径说明.
- Caveat/counter-evidence use is incomplete: risk/cancellation/consumption variability does not always affect final conclusion strength.
- Model self-rated `conclusion_quality` is not reliable; some `good` outputs still have low strict score.
- Numeric grounding in prose still has warnings (`number_not_verbatim_in_cited_text`), partly from Chinese unit conversion but not safe to ignore.

### Table / structured output problems

Remaining invalid cells:

- `GOOGL 2023 Google Cloud Revenue`: output status is `unsupported` but value `3600 usd_millions` was filled.
- `SNOW 2024 Other=-708`: table value is thousands-scale but output labels millions.
- `SNOW 2025 Federal=-6294`: table value is thousands-scale but output labels millions.
- `ADBE 2024 Jillian Forusz=50`: signature/disclosure row was treated as a business metric.
- `SNOW 2025 RPO=6900`: cited RPO definition claim, not numeric `$6.9B` claim.

Root causes:

- Need stronger numeric-claim vs definition-claim role classification.
- Need table-row business relevance filter before final synthesis.
- Need unsupported cell contract enforcement: unsupported means `value=null`.

## Recommended Next Step

Implement `EvidenceBriefObject` as the next main artifact. Start with the 6 `complex_insight` queries only; do not include metric/table tasks in the first demo.

Suggested schema:

```json
{
  "query_id": "...",
  "brief_schema_version": "evidence_brief_v0.1",
  "facets": [
    {
      "facet_id": "...",
      "coverage_status": "covered | partial | missing | conflicted",
      "core_evidence": [
        {
          "object_id": "...",
          "role": "core_fact | supporting_fact | caveat | counter_evidence | definition",
          "claim_supported_zh": "...",
          "company": "MSFT",
          "fiscal_year": 2025,
          "metric": "...",
          "comparability_note_zh": "..."
        }
      ],
      "do_not_use_as_fact": [
        {
          "object_id": "...",
          "reason_zh": "definition only / wrong year / wrong metric / partial context"
        }
      ],
      "missing_needed_evidence_zh": [],
      "facet_takeaway_zh": "..."
    }
  ],
  "required_synthesis_constraints_zh": []
}
```

Implementation order:

1. Add a schema/dataclass or typed helper for `EvidenceBriefObject`.
2. Add deterministic pre-role rules before LLM:
   - numeric claim requires numeric object or claim text with matching number;
   - definition claim cannot support numeric conclusion;
   - ticker/year/metric mismatch is `do_not_use_as_fact`;
   - background evidence cannot become `core_fact`;
   - risk/caveat objects should be preserved as caveat/counter-evidence, not dropped.
3. Add a script such as `scripts/run_evidence_brief_demo.py`.
   - Input: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit.json`
   - Limit first run to the 6 `complex_insight` queries.
   - Output: `reports/evidence_briefs/sec_tech_10k_expanded_v0_2_complex_insight_evidence_briefs.json`
4. Add a validator such as `scripts/validate_evidence_briefs.py`.
   - Check object IDs exist in input memory.
   - Check roles are valid.
   - Check each covered facet has at least one `core_fact` or explicit caveat/partial reason.
   - Check no `definition` is used as numeric support.
   - Check `missing` facets do not have fabricated core facts.
5. Modify final synthesis to optionally consume evidence briefs instead of raw facet memory.
6. Compare old aspectfit synthesis vs brief-based synthesis on the same 6 complex queries.

## Suggested Quality Metrics For Next Run

For brief quality:

- facet coverage status distribution
- core evidence count per facet
- caveat/counter-evidence inclusion rate
- definition-only rejection count
- missing evidence calibration count
- invalid object_id count

For final synthesis after brief:

- citation gate pass count
- citation object use rate
- low_required_coverage count
- comparability discipline score
- counter_evidence_use score
- unsupported conclusion count
- mean overall quality
- manual review on 2-3 hard queries

Expected useful result:

- Citation precision should stay near `1.0`.
- `low_required_coverage` may not disappear because missing evidence is real, but final answer should explicitly downgrade conclusions instead of writing around the gap.
- `citation_use_rate` should rise moderately, not mechanically maximize. The target is useful coverage, not citing everything.
- Comparability/caveat scores should improve on `ads_ai_infra`, `subscription_visibility`, and `cloud_profitability`.

## Reproduction Commands

Local validation of latest final output:

```powershell
python scripts\validate_synthesis_citations.py `
  --synthesis-path reports\demo\qwen9b_expanded_v0_2_cell_vllm_facet_memory_aspectfit_synthesis_16k_celljson_4500_retry6500_merged_repaired.json `
  --grouped-pool-path reports\evidence_pool\sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit.json `
  --output-path reports\quality\sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit_citation_validation_16k_celljson_4500_retry6500_merged_repaired.json
```

```powershell
python scripts\validate_metric_table_cells.py `
  --synthesis-path reports\demo\qwen9b_expanded_v0_2_cell_vllm_facet_memory_aspectfit_synthesis_16k_celljson_4500_retry6500_merged_repaired.json `
  --output-path reports\quality\sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit_metric_cell_validation_16k_celljson_4500_retry6500_merged_repaired_scaleaware.json
```

```powershell
python scripts\score_synthesis_quality.py `
  --synthesis-path reports\demo\qwen9b_expanded_v0_2_cell_vllm_facet_memory_aspectfit_synthesis_16k_celljson_4500_retry6500_merged_repaired.json `
  --citation-validation-path reports\quality\sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit_citation_validation_16k_celljson_4500_retry6500_merged_repaired.json `
  --cell-validation-path reports\quality\sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit_metric_cell_validation_16k_celljson_4500_retry6500_merged_repaired_scaleaware.json `
  --output-path reports\quality\sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit_answer_quality_16k_celljson_4500_retry6500_merged_repaired_scaleaware.json
```

Syntax smoke:

```powershell
python -m py_compile scripts\build_facet_evidence_memory.py scripts\run_calibrated_synthesis_demo.py scripts\repair_synthesis_citations.py scripts\validate_synthesis_citations.py scripts\validate_metric_table_cells.py scripts\score_synthesis_quality.py
```

## Where To Read First In New Window

1. `D:\FIN_Insight_Agent\docs\worklog\50_handoff_next_evidence_brief_stage.md`
2. `D:\FIN_Insight_Agent\docs\worklog\40_expanded_eval_and_quality_gates.md`
3. `D:\FIN_Insight_Agent\reports\logs\qwen9b_aspectfit_4500_retry6500_merged_scaleaware_summary.json`
4. `D:\FIN_Insight_Agent\reports\model_runs\20260517_phase2_aspectfit_memory_celljson_synthesis_rerun.md`

## Governance Gate For Next Experiment

- Hypothesis: adding `EvidenceBriefObject` will improve final synthesis coverage discipline and insight completeness without reducing citation precision.
- Decision target: on the 6 complex insight queries, citation gate remains 6/6 pass, background-as-fact remains 0, `low_citation_use_rate` decreases, counter-evidence/comparability scores improve on at least 3 hard queries, and manual review finds fewer unsupported broad conclusions.
- Baseline: latest aspectfit synthesis metrics in `qwen9b_aspectfit_4500_retry6500_merged_scaleaware_summary.json`.
- Stop condition: if brief objects mostly restate the final answer without improving role separation or missing-evidence calibration, do not scale to table tasks; revise brief schema/rules first.
- Decision label: diagnostic-only until manual review confirms the brief improves reasoning discipline.

## Revised Gate - Long Context First

- Hypothesis: before introducing `EvidenceBriefObject`, running Qwen3.5-9B with a native long-context budget should improve coverage and evidence-use discipline because the model can read the full facet memory instead of the 16k-compacted subset.
- Decision target: on the 6 `complex_insight` queries, first run `128k full facet_memory_aspectfit`; citation gate remains 6/6 pass, background-as-fact remains 0, parse is 6/6, and answer-quality diagnostics improve versus the latest 16k aspectfit baseline on citation use, low-required-coverage alarms, comparability, or counter-evidence use. Then test `128k citation-only calibrated pool` if it fits the true tokenizer budget.
- Ceiling / upper bound: full facet memory fits under the 128k input budget in tokenizer dry-run; citation-only calibrated pool ranges near 46k-115k tokens before final prompt overhead, so it is expected to fit most or all 6 complex queries. Raw citation+background calibrated pool ranges about 141k-407k tokens and is not expected to fit 128k.
- Baseline: latest 16k aspectfit synthesis `reports/demo/qwen9b_expanded_v0_2_cell_vllm_facet_memory_aspectfit_synthesis_16k_celljson_4500_retry6500_merged_repaired.json`, summary `reports/logs/qwen9b_aspectfit_4500_retry6500_merged_scaleaware_summary.json`.
- Leakage guard: use only calibrated evidence pool / facet memory artifacts; do not include `rough_baseline_points` or answer-quality reports in prompts.
- Stop conditions: if 128k FP16 cannot initialize on the single RTX 4090, try a Qwen3.5-9B quantized path before returning to brief compression. If long-context prompts fit but quality degrades, treat the issue as evidence ordering/attention dilution rather than context compression.
- Efficiency gate: record model load, wall time, prompt tokens, output parse status, GPU/OOM behavior, and generation speed; do not promote any output as teacher-ready.
- Decision label: diagnostic-only.

## 本次记录 - 128k Long-Context Baselines

- Problem: 用户指出 16k 上下文下继续设计 `EvidenceBriefObject` 会变成玩具上下文优化，要求先在 Qwen3.5-9B 原生长上下文下跑 baseline，并在不行时再考虑量化 9B。
- Reasoning and decision: 暂停小模型 brief 主线，先验证 128k FP16 是否能在单卡 RTX 4090 上服务，并比较两条不依赖 brief 的路线：`full facet memory` 与 `raw citation-only calibrated pool`。保持 diagnostic-only，不把 answer-quality report 当 teacher/judge。
- Work completed: `scripts/run_calibrated_synthesis_demo.py` 增加长上下文 packing 开关 `--memory-pack-profile full`、`--raw-pack-profile citation-only-all|full-all`；在云端用 Qwen3.5-9B FP16/vLLM 跑 6 个 `complex_insight` query；生成 synthesis、citation validation、answer-quality report 和汇总 JSON；新增 model run ledger `reports/model_runs/20260517_phase2_longctx_128k_complex6_baselines.md`。
- Result and evidence: 128k FP16 初始化成功，模型加载占 16.8 GiB，GPU KV cache 为 139,914 tokens，对 131,072 tokens/request 的最大并发为 1.07x。`128k full facet memory` 为 6/6 parsed、citation 6/6 pass、mean quality 0.7107；`128k raw citation-only calibrated pool` 为 6/6 parsed、citation 6/6 pass、mean quality 0.8017。旧 16k aspectfit baseline 在同 6 个 complex query 上 mean quality 为 0.6181。
- Follow-up and safety notes: 云端没有发现 9B 量化模型，只有 Qwen3.5-27B GPTQ Int4 和 Qwen3.5-9B FP16；由于 128k FP16 已可运行，本轮未下载或运行量化 9B。下一步应人工审查 raw citation-only 与 facet-memory 在 2-3 个 hard query 的答案差异，再决定是否加入 selected background 或 evidence role table；不要把 `EvidenceBriefObject` 作为当前优先主线。

## 本次记录 - 128k Baseline Manual Review

- Problem: 自动 scorer 显示 `128k raw citation-only` 明显高于 16k 和 128k facet memory，但需要人工判断是否真是覆盖改善，而不是 scorer 偏差。
- Reasoning and decision: 对 6 个 complex query 逐条比较旧 16k、`128k full facet memory`、`128k raw citation-only` 的中文答案、key findings、missing/uncertain 和引用对象数。人工判断重点放在 ideal facets、required caveats、counter-evidence、口径说明和数值/指标混用。
- Work completed: 人工检查了 `reports/demo/qwen9b_expanded_v0_2_cell_vllm_facet_memory_aspectfit_synthesis_16k_celljson_4500_retry6500_merged_repaired.json`、`reports/demo/qwen9b_longctx_128k_facet_full_complex6.json`、`reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6.json`。
- Result and evidence: `128k raw citation-only` 在 5/6 query 上人工覆盖最好，尤其是 `ads_ai_infra`、`ai_semiconductor_durability`、`cloud_profitability_comparison`、`platform_services_recurring_quality`、`subscription_visibility`。它更完整覆盖了 Reality Labs、AI capex/折旧压力、Snowflake consumption caveat、PANW subscription revenue、NVIDIA 2023-2025 增长和客户集中度等。`128k full facet memory` 比 16k 好，但在 `ai_capex_monetization`、`cloud_profitability_comparison`、`subscription_visibility` 中出现更多压缩后 metric/fact 口径混淆，例如将 `Total, net`/表格行或局部 metric 当成可横比 capex/收入结论。旧 16k 在多个 query 上明显漏公司或漏年份，`ai_capex_monetization` 基本退化为 MSFT-heavy answer。
- Follow-up and safety notes: `128k raw citation-only` 仍不是 teacher-ready。残留问题主要是输出 contract 太短，模型面对 89-217 条 citation 仍只引用 8-15 个对象；部分 broad finding 只用 2-3 个 citations 支撑跨公司结论。下一步更应调 final synthesis 输出结构（例如 facet-by-facet findings / 更多 findings / 每 facet citation coverage），而不是优先做小模型 brief。

## 本次记录 - Long-Context Final Contract v2

- Problem: 旧 `128k raw citation-only` 虽然覆盖最好，但最终 answer contract 太短，模型面对 925 条输入 citation 只引用 65 个对象，且 broad finding 容易把多个公司/年份/facet 压成一句。
- Reasoning and decision: 不引入 `EvidenceBriefObject`，先把最终 synthesis contract 本身改成更适合长上下文的结构：保留 `answer_zh` 和 `key_findings`，新增 `facet_findings`、`comparability_caveats_zh`、`missing_evidence_by_facet`；同步更新 prompt、citation extractor、validator、scorer 和 deterministic repair，让新增字段进入同一套质量门。
- Work completed: 修改 `scripts/run_calibrated_synthesis_demo.py`、`scripts/validate_synthesis_citations.py`、`scripts/score_synthesis_quality.py`、`scripts/repair_synthesis_citations.py`；云端 4090 用 Qwen3.5-9B FP16/vLLM 跑 6 个 `complex_insight` query；本地执行 deterministic citation repair、citation validation、answer-quality scoring；新增 run ledger `reports/model_runs/20260517_phase2_longctx_contract_v2_complex6.md` 和摘要 `reports/logs/qwen9b_longctx_128k_contract_v2_complex6_summary.json`。
- Result and evidence: `--synthesis-max-tokens 2500` 的 v2 首跑只有 2/6 parsed，raw tail 显示是 JSON 截断；把输出预算提高到 6500 后 6/6 parsed。修复前有 1 个 object_id copy error（`ITEM8` 写成 `ITEM7` 对应证据的错位），`repair_synthesis_citations.py` 用唯一 stable suffix 匹配修复后 citation gate 6/6 pass、hard failures 0。新 contract 引用对象从旧 raw baseline 的 65/925 增至 116/925，citation use rate 从 0.0703 升至 0.1243；每条 query 产生 4-8 条 key findings、4-10 条 facet findings、3-4 条 comparability caveats。自动 mean quality 为 0.7228，低于旧 raw 的 0.8017，主要因为 scorer 现在会扫描更长的 facet findings 并触发 19 个 conservative numeric warnings，不能直接解释为覆盖退步。
- Manual review: 覆盖确实更好，尤其 `ads_ai_infra`、`ai_semiconductor_durability`、`cloud_profitability_comparison`、`platform_services_recurring_quality`、`subscription_visibility` 的 facet/caveat/missing-by-facet 更清楚。风险也更明确：长输出增加数值/单位表述错误概率，`platform_services_recurring_quality` 中 Apple/Adobe 服务或订阅收入的精确数值口径需要后续专门约束；`ai_capex_monetization` 仍偏 broad，需要更清晰地区分 capex、cloud monetization、margin pressure 和 cash-flow pressure。
- Follow-up and safety notes: 当前主线继续保持 `128k raw citation-only + richer final contract`，不要回到小模型 brief 作为默认下一步。下一步应加 numeric/unit phrasing rule，例如要求 exact value 必须按引用 object 的单位/scale 原样表达，或者把 exact value 放进结构化 metric snippets 后再生成趋势判断。所有结果仍是 diagnostic-only，0/6 teacher-ready。

## 本次记录 - Long-Context Final Contract v3

- Problem: v2 覆盖更好，但仍然“每个 facet 平均铺开”，且长输出带来数值/单位/metric role 风险。用户要求把答案 contract 改成两层：`thesis_zh` 一句主判断，`decision_drivers` 最多 3 条且排序，`secondary_context` 最多 3 条，`limiting_caveats` 写削弱结论的缺证/口径问题，`facet_findings` 仅作为 supporting appendix；同时继续收紧数值/单位/metric role 控制。
- Reasoning and decision: 不回到小模型 brief，也不扩大样本；继续在 6 个 `complex_insight` query 上验证 128k raw citation-only 的最终输出 contract。把“判断优先级”做进 schema/prompt/scorer，把精确数字做进 `numeric_claims`，并让 validator 不只看 object_id，还看 raw value、unit、metric_role 和正文是否把 period change 当总额趋势使用。
- Work completed: 修改 `scripts/run_calibrated_synthesis_demo.py`、`scripts/validate_synthesis_citations.py`、`scripts/score_synthesis_quality.py`、`scripts/repair_synthesis_citations.py`；云端 Qwen3.5-9B FP16/vLLM 生成 v3 输出；本地合并首 3 条和 detached remaining 3 条；执行 citation repair、citation validation、answer-quality scoring；新增 `reports/model_runs/20260517_phase2_longctx_contract_v3_complex6.md` 和 `reports/logs/qwen9b_longctx_128k_contract_v3_complex6_summary.json`。
- Result and evidence: v3 6/6 parsed，repair 后 citation gate 6/6 pass、hard failures 0、invalid object IDs 0。结构上达到目标：18 条 `decision_drivers`、18 条 `secondary_context`、18 条 `limiting_caveats`、62 条 `numeric_claims`；`decision_priority_discipline=1.0` on all six queries，v2 current-gate reference 仍为 6/6 `weak_decision_priority`。但 numeric gate 未过：warning types 包括 `number_not_verbatim_in_cited_text=27`、`numeric_claim_raw_value_not_in_cited_text=7`、`numeric_conversion_without_role_check=6`、`metric_role_mismatch_period_change_in_narrative=3`；mean strict quality 为 0.5236，teacher-ready 仍为 0/6。
- Manual review: Insight 质量方向正确：模型能先给主判断，再解释 2-3 个真正支配结论的证据，明显少了平均铺 facet 的问题。但 `platform_services_recurring_quality` 仍有实质数值风险：模型在 `numeric_claims` 和 caveat 中承认 Apple FY2023 `$7.1 billion` 是 `period_change_amount`，却在 driver 的正文里写成“从 2023 年的增量 71 亿美元增长至 2025 年的 1091.58 亿美元”，把 period change 和 total value 放进同一个趋势句。新的 `metric_role_mismatch_period_change_in_narrative` 已经能自动抓到这个问题。
- Follow-up and safety notes: v3 不应升为 teacher-ready，也不应扩到全 13 query。下一步只需 rerun 失败 query 或小范围 6-query rerun，重点改 exact-value rendering：要么强制最终答案只引用预格式化 metric snippets，要么加 post-generation numeric rewrite/check stage，把 period_change、total_value、percentage_rate 分开表达。

## 本次记录 - Contract v3 Numeric-Safe Patch

- Problem: v3 的两层判断结构有效，但 `ai_capex_monetization` 和 `platform_services_recurring_quality` 触发 `metric_role_mismatch_period_change_in_narrative`，说明 prompt 允许模型把 period-change amount 放进 total-value 趋势句。
- Reasoning and decision: 不扩样本，不重跑全量；只加强 exact-value rendering prompt 并 rerun 这两条。新增约束是：`thesis_zh` 和 `decision_drivers` 优先写判断，尽量少放精确货币数；如果正文必须出现 exact value，数字附近必须写清 metric role；`period_change_amount` 不能和“从/至/到/增长至/达到”等总额趋势词共句。同步修正 validator 的一个 false positive：货币 raw value 出现在含 `effective tax rate` 的句子中时，不能仅凭 `rate` 把它推断成百分比。
- Work completed: 云端 Qwen3.5-9B FP16/vLLM rerun 两条 query；本地拉回 `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex2_contract_v3_numeric_safe_8500.json`，执行 repair、citation validation、answer quality scoring；将两条 rerun 结果 patch 回 6-query v3 诊断文件；新增 `reports/model_runs/20260517_phase2_longctx_contract_v3_numeric_safe_patch.md` 和 `reports/logs/qwen9b_longctx_128k_contract_v3_numeric_safe_patch_summary.json`。
- Result and evidence: 两条 rerun 均 parsed，citation gate 2/2 pass，repair count 0。patched six-query report 仍为 6/6 parsed、6/6 citation pass；`metric_role_mismatch_period_change_in_narrative` 从原 v3 的 3 个降为 0；mean strict quality 从 0.5236 升到 0.6311。`ai_capex_monetization` numeric discipline 从 0.0 升到 0.6；`platform_services_recurring_quality` 从 0.0 升到 0.6667。teacher-ready 仍为 0/6，主要剩余 warnings 是 `number_not_verbatim_in_cited_text=21`、`numeric_claim_raw_value_not_in_cited_text=7`、`numeric_conversion_without_role_check=2`。
- Manual review: `platform_services_recurring_quality` 的核心错误已修复：Apple FY2023 `$7.1 billion` 现在作为服务收入增长额和 caveat 出现，不再作为 2023 服务总收入基点与 FY2025 总收入做“从 X 到 Y”趋势比较。答案结构也保持了 v3 的判断优先级。但 exact numeric 仍不够稳，部分表格 raw value 没逐字复制，中文单位换算仍触发保守检查。
- Follow-up and safety notes: prompt-only 已能压住特定 period-change narrative 错误，但不能解决全部 exact-value 可靠性。下一步不应继续堆 prompt，而应做结构化 exact-value layer：由系统预先生成可引用的 metric snippet/display value，模型只能选择 snippet 并写结论，避免自由复制 raw table value。
