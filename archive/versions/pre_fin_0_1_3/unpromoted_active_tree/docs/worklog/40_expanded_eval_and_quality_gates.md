# Expanded Evaluation And Quality Gates

## 目标

下一阶段不再只验证 6 个单点 query，而是用两类更接近真实金融系统的任务压测链路：

1. 高复杂度综合 insight：
   - multi-year，multi-company，跨业务模式或行业主题。
   - 目标是测试 planner / retrieval / verifier / synthesis 在高信息密度下是否还能稳定覆盖关键 facet、承认缺口、避免过度推断。
2. 财务指标和表格数据稳定性：
   - 多公司、多财年、表格化输出。
   - 目标是测试 MetricObject / TableObject 抽取、引用、数值一致性和 disclosure 口径差异处理。

当前先做 query 组和粗 baseline，不直接把这批问题当 final gold。后续要用模型输出反推 scorer 的边界样本和 validator 的修复策略。

## 新增 Query Set

文件：

- `eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl`

分组：

- `complex_insight`: 6 个 query。
- `metric_table_stability`: 7 个 query。
- 合计：13 个 query。

覆盖范围：

- 公司：MSFT, AAPL, NVDA, GOOGL, META, AMZN, AMD, ADBE, PANW, SNOW。
- 年份：2023, 2024, 2025。
- 主题：AI capex、云增长质量、广告恢复、订阅/RPO 可见性、半导体供需、服务/订阅化、表格指标。

设计原则：

- 每个 query 都有 `rough_baseline_points`，但这些 baseline 只作为专业判断和 scorer 设计参考，不进最终 synthesis prompt。
- 对表格类 query，baseline 主要规定应输出的表结构、口径 caveat 和禁止事项；具体数值必须由 SEC evidence 产生。
- 对 insight 类 query，baseline 规定应覆盖的财务逻辑和风险 caveat，不要求模型给投资结论。

## 执行步骤

1. 基于 v0.2 query set 构建 planner/search task。
   - 每个 query 拆成 `facet -> aspect`。
   - Insight query 应允许 6-10 个 facet；table query 应控制在 3-6 个 metric facet。
   - 对 multi-year / multi-company query，必须显式建 `company x year x metric` coverage memory。

2. 跑 object retrieval + BGE reranker + small verifier。
   - 先用当前 object BM25 top25 + BGE reranker。
   - 再用 Qwen3.5-4B aspect verifier 生成 direct/partial/false。
   - 输出新的 calibrated evidence pool，不复用旧 6-query pool。

3. 跑 Qwen3.5-9B final synthesis。
   - Insight query 输出中文研究结论。
   - Metric/table query 输出中文解释 + machine-readable table。
   - final prompt 不包含 `rough_baseline_points`。

4. 用模型输出设计并实现 answer-quality scorer。
   - 先人工看错误，再把稳定规则固化。
   - 不在没有输出样本前过度设计细碎规则。

5. 实现 citation validator。
   - 先做硬规则：引用存在、role 合法、ticker/year 一致、引用证据在输入 pool 内。
   - 再做 claim-support 检查：数值是否出现在 cited object，关键 claim 是否有 direct citation。
   - validator 发现问题时生成 repair request，而不是静默修正答案。

## Answer-Quality Scorer 设计

Scorer 不应只有一个总分。至少拆成两个 profile：

### Insight Profile

适用：

- `complex_insight`

核心指标：

- `facet_coverage`: baseline facets 是否都被回答覆盖。
- `company_year_coverage`: 要求的公司和年份是否没有漏掉。
- `evidence_grounding`: 每个关键结论是否有 citation object。
- `counter_evidence_use`: 是否使用了风险、成本、capex、disclosure caveat 等反向证据。
- `comparability_discipline`: 是否说明 segment / company-level / GAAP vs non-GAAP / disclosure 口径不可直接横比。
- `missing_calibration`: 证据不足时是否明确说不确定，而不是补全。
- `unsupported_claim_penalty`: 是否出现未被证据支持的经营判断、投资判断或数值。
- `synthesis_quality`: 结论是否结构化、能回答问题、没有只堆事实。

输出建议：

```json
{
  "query_id": "...",
  "profile": "complex_insight",
  "scores": {
    "facet_coverage": 0.0,
    "company_year_coverage": 0.0,
    "evidence_grounding": 0.0,
    "counter_evidence_use": 0.0,
    "comparability_discipline": 0.0,
    "missing_calibration": 0.0,
    "unsupported_claim_penalty": 0.0,
    "synthesis_quality": 0.0
  },
  "hard_failures": [],
  "notes": []
}
```

### Metric/Table Profile

适用：

- `metric_table_stability`

核心指标：

- `requested_cell_coverage`: `company x year x metric` 是否都给出或明确 NA。
- `numeric_exactness`: 数值是否和 cited object 一致。
- `unit_scale_correctness`: million / billion / percent / basis-point 口径是否正确。
- `table_shape_correctness`: 行列是否符合 query 要求。
- `source_traceability`: 每个数值是否能追溯到 object_id。
- `aggregation_discipline`: 是否避免把 segment-level、company-level、cash-flow-line item 混成同一口径。
- `na_handling`: 没披露或不可比时是否输出 NA 和原因。
- `format_validity`: JSON/table 是否可解析。

输出建议：

```json
{
  "query_id": "...",
  "profile": "metric_table_stability",
  "cell_metrics": {
    "requested_cells": 0,
    "filled_cells": 0,
    "cited_cells": 0,
    "exact_cells": 0,
    "na_with_reason": 0,
    "unsupported_cells": 0
  },
  "scores": {
    "requested_cell_coverage": 0.0,
    "numeric_exactness": 0.0,
    "unit_scale_correctness": 0.0,
    "source_traceability": 0.0,
    "format_validity": 0.0
  },
  "hard_failures": [],
  "notes": []
}
```

## Citation Validator 设计

Validator 是 serving 前必须加的硬门控，不等同 answer-quality scorer。

### 硬规则

- `object_id_exists`: 引用的 object_id 必须存在于当前 synthesis input pool。
- `role_allowed`: 默认最终事实 claim 只能引用 `citation_evidence`；引用 background-only object 需要标记并触发 repair。
- `ticker_year_match`: cited object 的 ticker/year 必须与 claim 或 query scope 一致。
- `source_trace_exists`: cited object 必须有 `source_evidence_id`，并能追溯到 SEC filing。
- `no_invalid_id`: 不允许模型编造 object_id。
- `missing_not_filled`: 对 `missing_aspect=true` 的 aspect，不允许答案给出确定数值或确定结论。

### 支持性规则

- `number_supported`: claim 中的数值必须出现在 cited object text 或其 normalized MetricObject 字段中。
- `metric_name_supported`: claim 的 metric 名称必须和 cited object 的 metric/table/claim 语义匹配。
- `company_scope_supported`: 多公司比较时，引用不能跨公司支持另一家公司结论。
- `year_scope_supported`: 多财年比较时，引用不能跨年支持另一年结论。
- `claim_density`: 一个长段落若包含多个独立事实，必须至少有多个对应 citation 或拆成 key findings。

### Repair 策略

Validator 输出不直接改答案，而是生成 repair request：

```json
{
  "status": "repair_required",
  "issues": [
    {
      "type": "background_cited_as_fact",
      "claim_index": 2,
      "object_id": "...",
      "repair_instruction": "Replace with citation_evidence or mark as background context."
    }
  ]
}
```

LLM repair prompt 只允许：

- 删除 unsupported claim。
- 将确定结论降级为 missing/uncertain。
- 替换为已有 `citation_evidence` 中可支持的 object_id。
- 不允许新增 evidence pool 外引用。

## Proceed Gate

v0.2 query set 跑通后才进入 scorer 实现主线。进入条件：

- 全部 13 个 outputs 中至少 11 个 parseable，invalid citation 为 0，且 missing aspects 不被填充。
- `metric_table_stability`: 至少 90% requested cells 有 citation 或 NA reason。
- 任一 query 出现 company/year scope 严重错配，必须先修 validator，不继续调 synthesis prompt。

## 本次记录

- Problem: 用户希望下一阶段扩大样本，加入 multi-year、multi-company、行业综合 insight，并单独测试多公司多财年财务指标/表格输出稳定性；query 组设计完成后，再基于模型输出设计 answer-quality scorer 和 citation validator。
- Reasoning and decision: 先把 eval query 和粗 baseline 固化为独立 JSONL，不把 baseline 放进 synthesis prompt，避免提示泄漏；scorer/validator 先记录 profile 和硬门控方向，具体规则等 v0.2 模型输出后再收敛。
- Work completed: 新增 `eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl`，包含 6 个 complex insight query 和 7 个 metric/table query，覆盖 10 家公司和 2023-2025 财年；更新 worklog index 和 master checklist。
- Result and evidence: JSONL 校验通过，13 条记录全部可解析，cohort 分布为 `complex_insight=6`、`metric_table_stability=7`，`query_id` 唯一且必需字段齐全。
- Follow-up and safety notes: 本次没有跑云端模型或生成新 evidence pool；下一步应按本文执行步骤跑 v0.2 retrieval/reranker/verifier/synthesis，再用真实错误样本实现 scorer 和 citation validator。

## 本次记录 - v0.2 Full Chain

- Problem: 需要把 v0.2 的 13 个高复杂度 query 真正跑完整链路，并返回指标、链路耗时、中文模型输出，以及基于输出样本落地 answer-quality scorer 和 citation validator。
- Reasoning and decision: 本轮保持 `diagnostic-only`。原因是 expanded set 尚无最终人工 gold，BGE 评测缺少标签，metric/table 输出还不是机器可校验的 cell JSON；但完整链路已经足够暴露下一步要修的 production contract。
- Work completed: 将 v0.2 query 转成 object task；跑通 BGE top15、aspect evidence pool、Qwen3.5-2B strict-fast-path verifier、calibrated evidence pool、Qwen3.5-9B synthesis；新增 `scripts/validate_synthesis_citations.py`、`scripts/score_synthesis_quality.py`、`scripts/export_expanded_synthesis_trace.py`；生成中文 trace 报告。
- Result and evidence: `reports/demo/qwen9b_expanded_v0_2_synthesis_demo.json` 包含 13 个输出，12/13 可解析，模型自评为 `good=1, mixed=10, weak=2`；输入 evidence 为 143 个 citation objects、55 个 prompt-packed background objects、25 个 missing aspects；模型引用 78 个 object，其中 77 个为 citation evidence、1 个为 background-only，invalid object id 为 0。
- Citation gate: `reports/quality/sec_tech_10k_expanded_v0_2_citation_validation.json` 中 11/13 pass，2/13 repair required；硬失败为 `invalid_json=1` 和 `background_cited_as_fact=1`；数值支持 warning 为 22 个，当前属于保守诊断。
- Answer-quality gate: `reports/quality/sec_tech_10k_expanded_v0_2_answer_quality.json` 的 diagnostic mean overall 为 0.7972，min 为 0.3857，max 为 0.9429；最低分 query 是 `expanded_metric_revenue_income_cfo_table_2023_2025`，原因是 JSON 格式失败且 citation repair required。
- Runtime: 云端 resumed run 从 BGE 到 synthesis 约 1,138 秒；BGE reranker 30.3871 秒；Qwen3.5-2B verifier 总计 431.6498 秒，其中 load 36.2292 秒、generation 395.4206 秒；Qwen3.5-9B synthesis 总计 661.7082 秒，其中 load 55.2894 秒，单 query 大约 17.45-59.03 秒。
- Decision: 当前链路“可用于研究诊断和人工审查”，但不应宣称 production-ready。下一步不应继续盲目扩样本，而应先修三件事：metric/table 输出改成 cell-level JSON；增加 post-synthesis repair 处理 invalid JSON 和 background citation；numeric validator 改为直接校验 MetricObject/TableObject 字段。
- Follow-up and safety notes: 本轮没有新增训练，也没有把 baseline answer 注入 synthesis prompt；云端日志和生成物已同步到本地 reports。没有记录任何云端密码或私密 token。

## 本次记录 - Cell-Level Retrieval and Strict Quality Gate

- Problem: `expanded_insight_ads_ai_infra_2023_2025` 等综合 query 暴露三层根因：facet/aspect 太粗、每个 aspect 只保留 1 条 citation、verifier 对 `operating income` 与 `total income from operations` 等同义表格证据召回/判别不稳；同时旧 answer-quality report 过宽，不适合作 teacher/judge。
- Reasoning and decision: 不继续扩大样本或调 synthesis prompt，先修 upstream contract。把任务从“RAG 找 chunk”升级为 `company/year/metric cell -> evidence pool -> strict gate`，并把旧质量报告降级为严格诊断闸门，禁止 teacher-ready。
- Work completed: `scripts/build_expanded_object_tasks.py` 改为输出 698 个 cell/aspect retrieval tasks，保留 `parent_facet` 聚合字段；`src/retrieval/object_bm25_retriever.py` 增加过滤后 batch scoring、ticker/year 过滤和 metric period 加权；生成 `reports/retrieval_eval/sec_tech_10k_expanded_v0_2_cell_bm25_predictions.jsonl`、`reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_bm25_evidence_pool.jsonl`、`reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_bm25_aspect_evidence_pool.jsonl`。
- Result and evidence: cell-level BM25 运行 38-62 秒内完成；698 个细任务生成 6,980 条候选，其中 `metric=5,339`、`claim=1,564`、`table=77`。`GOOGL/META x 2023/2024/2025 x total income from operations operating income` 的 top1 均命中对应年度 total income from operations metric cell。
- Evidence pool policy: `scripts/export_calibrated_evidence_pool.py` 默认从每 aspect 1 条 citation 改为 3 条 citation、5 条 background，并按 ticker/year/object_type 做轻量多样性；在旧 Qwen2B verifier 输出上重导出的 multi-cite pool citation objects 从 143 增至 387，background 从 503 增至 832，但旧粗粒度 verifier 仍保留 25 个 missing aspects，说明必须用新版 cell tasks 重跑 reranker/verifier。
- Quality gate: `scripts/score_synthesis_quality.py` 升级为 `answer_quality_scoring_v0.2`，输出 `strict_diagnostic_not_teacher`；新报告 `reports/quality/sec_tech_10k_expanded_v0_2_answer_quality_strict.json` 中 13/13 `teacher_ready=false`，mean overall 从旧诊断 0.7972 降到 0.5791，主要 blockers 为 `missing_machine_readable_cell_json=7`、`citation_or_number_warning=9`、`low_required_coverage=8`、`low_citation_use_rate=5`。
- Decision: 当前修复解决了“强证据没进入候选/被 citation squeeze”的 upstream 问题，但还没有重跑 BGE/Qwen verifier 和 Qwen9B synthesis；旧综合输出不应再作为 teacher 或 judge 样本。下一步应在云端按新版 698 cell tasks 重跑 BGE/Qwen verifier，再让 synthesis 输出 machine-readable cell JSON，最后用 numeric validator 做 cell 级核对。
- Follow-up and safety notes: 本次没有运行云端大模型，没有新增训练，也没有写入任何凭据。规则 verifier sanity 只用于工程 smoke，不作为最终精排指标。

## 本次记录 - vLLM Cell Verifier and 16k Synthesis Rerun

- Problem: 旧 Qwen3.5-2B verifier 在 6,980 条 cell-level aspect candidate 上预计需要 50-60 分钟，用户要求先用 vLLM 优化吞吐，再继续全链路评估。
- Reasoning and decision: 不继续硬跑 transformers 路径。先把 verifier 切到 vLLM batched generation，确认无 CPU offload、无 JSON parse 失败、吞吐达标后，再导出 calibrated pool 并重跑 Qwen3.5-9B synthesis。synthesis 阶段发现 8k prompt overflow 和 900-token JSON 截断后，修复最终 prompt preflight、facet-balanced aspect cap、短 JSON schema，再用 16k context 重跑。
- Work completed: 新增/更新 `scripts/run_qwen_small_verifier_vllm.py` 与 `scripts/run_calibrated_synthesis_demo.py`；生成 vLLM verifier 输出、cell_vllm calibrated evidence pool、16k short-json synthesis、citation validation、strict quality report 和中文 trace。
- Result and evidence: Qwen3.5-2B vLLM verifier 写出 6,980/6,980 行，generation 147.7203 秒，47.2515 rows/sec，总 wall time 327.3133 秒；verifier label 为 `direct=2993`、`partial=2899`、`false=1088`。calibrated pool 有 698 aspects、1,426 citation objects、3,247 background objects、150 missing aspects。Qwen3.5-9B 16k synthesis 用时 578.2901 秒，12/13 parsed，citation validation 11/13 pass，strict quality mean 0.5775，teacher-ready 仍为 0。
- Decision: vLLM verifier 路径可以作为当前工程主线；最终 synthesis 仍只能用于诊断和人工审查，不能作为 teacher/judge 样本。核心原因不是 verifier 吞吐，而是 evidence memory 与表格输出 contract：16k 仍只能纳入 574/698 aspects，且 metric/table query 还没有 machine-readable cell JSON。
- Follow-up and safety notes: 需要先实现 post-synthesis repair、cell-level JSON 输出和 numeric validator，再扩大样本或生成 teacher 数据。云端密码未写入文件；失败的 8k/16k 截断输出只作为诊断，不作为主报告。

## 本次记录 - Facet Memory and Cell JSON Contract

- Problem: 新增 cell-level aspects 后，最终 synthesis 虽然 evidence-side 覆盖更宽，但 16k prompt 仍会吞入大量原始 aspect/cell 噪声；同时 metric/table query 没有机器可校验的 `cell_table`，旧质量报告不能严格判断表格数值是否真的来自 `MetricObject/TableObject`。
- Reasoning and decision: 先做 upstream contract，不继续盲目扩大样本。把原始 calibrated pool 压成 facet-level evidence memory，让最终模型看到每个 facet 的覆盖状态、缺失项和压缩 fact；表格任务增加 `metric_table_cells_v0.1` 输出契约，并新增独立 numeric validator 作为 strict gate 输入。
- Work completed: 新增 `scripts/build_facet_evidence_memory.py`，从 grouped calibrated pool 和 structured objects 生成 facet memory；更新 `scripts/run_calibrated_synthesis_demo.py` 支持 `--facet-memory-path`、16k token preflight dry-run 估算、metric/table 专用 JSON schema 和 `cell_table` 引用统计；更新 `scripts/validate_synthesis_citations.py` 识别 `cell_table.cells[].citation_object_id`；新增 `scripts/validate_metric_table_cells.py`，校验 reported/missing/unsupported cell、引用对象存在性、ticker/year、value/unit 与 `MetricObject/TableObject` 的一致性；更新 `scripts/score_synthesis_quality.py` 接入 cell validation。
- Result and evidence: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory.json` 覆盖 13 个 query、84 个 facets、698 个 aspects，其中 548 covered、150 missing，压缩后保留 531 条 citation fact 和 359 条 background fact；16k dry-run `reports/demo/qwen9b_expanded_v0_2_cell_vllm_facet_memory_16k_dryrun_all.json` 对 13/13 query 均进入预算，近似 prompt token 范围为 10,340-14,070。旧 9B synthesis 经 `reports/quality/sec_tech_10k_expanded_v0_2_cell_vllm_metric_cell_validation.json` 检查，7/7 metric/table query 均缺失 `cell_table`，因此新 strict scorer `reports/quality/sec_tech_10k_expanded_v0_2_cell_vllm_answer_quality_16k_shortjson_cellaware.json` 继续判定 `teacher_ready=0`，并显式给出 `missing_machine_readable_cell_json=7`、`numeric_validation_failed=7`、`unit_scale_validation_failed=7`。
- Decision: facet memory 和 cell JSON/numeric gate 已作为下一轮 synthesis 主线；旧输出只能作为对照样本，不能进入 teacher/judge。下一步才适合在云端用 Qwen3.5-9B 重新跑 `--facet-memory-path` + structured JSON，并用新的 citation/cell validators 判定表格输出是否真的修好。
- Follow-up and safety notes: 本轮只做 deterministic build、dry-run packaging 和旧输出质量门重算，没有运行新的云端模型推理或训练；未写入任何凭据。`post-synthesis repair` 仍未实现，不能把 invalid JSON/background-only citation 自动修成通过样本。

## 本次记录 - Aspect-Fit Memory and Scale-Aware Cell Gate

- Problem: facet memory 首轮 cell JSON synthesis 中，强证据已进入候选池但部分 facet citation 仍选错同类对象；同时最终表格验证把 `usd_thousands` 与 `usd_millions` 的合理换算误判为数值错误，导致无法严格区分模型错、证据错和 validator 错。
- Reasoning and decision: 先修上游 evidence memory 选择和 deterministic gate，不用兜底 prompt 掩盖问题。facet citation selector 加入 aspect-aware 排序，优先把 YoY/% aspect 指向 percent 证据、risk/caveat aspect 指向 claim；post-synthesis 只做 object_id 稳定后缀唯一匹配的 deterministic repair；numeric validator 只放宽明确的 SEC 单位归一，不允许 unsupported cell 或定义性 claim 混过。
- Work completed: 更新 `scripts/build_facet_evidence_memory.py`、`scripts/run_calibrated_synthesis_demo.py`、`scripts/repair_synthesis_citations.py`、`scripts/validate_synthesis_citations.py`、`scripts/validate_metric_table_cells.py`；在云端 RTX 4090 用 Qwen3.5-9B vLLM text-only 跑 aspectfit 13-query synthesis，两个 JSON 截断表格 query 用 `synthesis_max_tokens=6500` targeted retry 后合并；同步最终 repaired synthesis、citation validation、cell validation、quality report 到本地。
- Result and evidence: 合并产物 `reports/demo/qwen9b_expanded_v0_2_cell_vllm_facet_memory_aspectfit_synthesis_16k_celljson_4500_retry6500_merged_repaired.json` 为 13/13 parsed；citation gate `reports/quality/sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit_citation_validation_16k_celljson_4500_retry6500_merged_repaired.json` 为 13/13 pass、hard failure 0、cited object precision 1.0000、background cited as fact 0。scale-aware cell gate `reports/quality/sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit_metric_cell_validation_16k_celljson_4500_retry6500_merged_repaired_scaleaware.json` 为 reported cells 70、valid reported 66、exact rate 0.9571、unit rate 0.9714、invalid cells 5。quality gate `reports/quality/sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit_answer_quality_16k_celljson_4500_retry6500_merged_repaired_scaleaware.json` 仍为 `strict_diagnostic_not_teacher`，mean overall 0.7107，teacher_ready 0/13。
- Runtime: 13-query full run wall time 1,275.5655 秒，其中 Qwen3.5-9B model load 68.2165 秒；targeted retry 中 `expanded_metric_cloud_segment_table_2023_2025` 208.5637 秒，`expanded_metric_revenue_income_cfo_table_2023_2025` 112.7173 秒。vLLM 日志显示 text-only、no CPU offload、约 21-27 output tok/s；长表格任务耗时主要来自输出长度，不是 CPU fallback。
- Error analysis: 剩余 5 个 invalid cells 分三类：`GOOGL 2023 Google Cloud Revenue` 被标 unsupported 但填了 3600；SNOW 客户/合同表里 `Other=-708` 和 `Federal=-6294` 把 thousands 当 millions；ADBE `Jillian Forusz=50` 是签名/披露人数误入业务指标；SNOW 2025 RPO 填 6900 但引用了 RPO 定义 claim，未引用 `$6.9B` 数值 claim。
- Decision: aspectfit memory 修复了此前 AMD/NVDA 等 percent/YoY 强证据错位问题，citation contract 已基本可用；但表格型任务仍不能 teacher-ready。下一阶段应先修 evidence pool 对 RPO 数值 claim、非业务表格行、unsupported cell 的选择与输出约束，再考虑扩大样本或把质量报告升级为 teacher/judge。
- Follow-up and safety notes: 本轮没有训练模型，没有把质量报告当 teacher 标签。云端凭据未写入文件。scale-aware validator 的 `/1000` 兼容仅用于 `usd_millions` 对大额 `usd_unscaled` 的 SEC 表格场景，后续仍应在结构化抽取层补全 table unit context。

## 本次记录 - External SEC Eval / Gold Plan Review

- Problem: 用户提供 `D:\downloads\fin_insight_agent_eval_plan_for_codex.md`，要求查看其中为本项目准备的测试用例、测评标准和 gold 标注方案。
- Reasoning and decision: 该方案与当前项目方向高度一致，尤其是明确不能只看 final summary 是否“像样”，而要拆分 retrieval、year/company/source、table parsing、numeric extraction、synthesis、citation 和 hallucination。最关键设计是 Gold Context Mode vs Pipeline Context Mode：前者隔离测试 9B 在正确证据下的 synthesis 能力，后者测试完整 agent 链路。如果两者结果不同，才能判断问题在模型、prompt、检索、解析还是证据构建。
- Work completed: 阅读并评审 eval plan 的公司宇宙、10 分评分规则、failure taxonomy、L1-L5 task 难度、Gold/Pipeline diagnostic matrix、starter cases、required test case schema、agent answer schema、production module boundary 和 suggested directory structure。
- Result and evidence:
  - 该方案建议的 10 家公司 `NVDA, ADBE, PANW, SNOW, AMZN, AAPL, MSFT, GOOGL, AMD, META` 与当前 SEC tech universe 基本匹配。
  - 评分维度为 retrieval correctness 2 分、factual accuracy 3 分、required coverage 2 分、synthesis quality 2 分、citation/evidence quality 1 分，适合转成我们的 strict quality gate profile。
  - failure taxonomy 覆盖 `retrieval_miss`、`wrong_company`、`wrong_year`、`table_parse_error`、`numeric_error`、`unit_error`、`unsupported_claim`、`hallucination`、`weak_synthesis`、`model_capacity_limit` 等，能直接接入当前 validator/scorer 输出。
  - Starter cases 包含 Snowflake consumption risk、NVIDIA data center driver、Amazon AWS numeric extraction、Apple/AWS wrong-attribution trap、Meta Llama internal-cost trap、Microsoft AI/cloud investment，覆盖 L1-L3 和 anti-hallucination trap；它们比当前 6 个 complex insight 更适合作为第一批 formal benchmark。
- Decision: 下一阶段应把该方案作为正式评测骨架，而不是继续只在 expanded v0.2 / complex6 上迭代。当前 expanded v0.2 仍适合作为 L4/L5 diagnostic；formal benchmark 应先从约 60 个高质量 gold cases 起步，并明确区分 Gold Context 和 Pipeline Context。
- Follow-up and safety notes: 本轮只做评审，没有创建新的 `eval/sec_cases/test_cases_v1.jsonl`、gold context 或 gold facts。后续落地时应优先 scaffold `eval/sec_cases/`，把 starter cases 转成 JSONL，并增加 runner 输出 `agent_outputs.jsonl`、`claim_verification.jsonl`、`scores.jsonl`、`trace_logs.jsonl`。

## 本次记录 - SEC Benchmark v1 and Step-1 Readiness Test

- Problem: 用户要求把外部 eval plan 结合当前项目进展，融合成新版测试用例评判 benchmark，并开始第一步测试。
- Reasoning and decision: 不直接复制外部文档。新版 benchmark 分三层：`formal_seed` 用 L1-L3 和 anti-hallucination trap 测 MVP 能力；`project_regression` 固化当前发现的 metric role / exact-value / table-cell 风险；`diagnostic_stress` 保留 complex insight 的 L4 压力测试。第一步测试先做本地 deterministic readiness，不启动 9B synthesis：如果 case schema、source availability、evidence coverage 和 structured-object readiness 不稳定，后续模型测试没有诊断价值。
- Work completed:
  - 新增 `docs/eval/sec_benchmark_v1.md`，定义 case tiers、Gold Context vs Pipeline Context、10 分 scoring、failure taxonomy、hard validators 和 MVP acceptance targets。
  - 新增 `eval/sec_cases/companies.yaml`、`eval/sec_cases/test_cases_v1.jsonl`、`eval/sec_cases/README.md` 与 gold/output 目录占位。
  - `test_cases_v1.jsonl` 包含 12 条 case：8 条 `formal_seed`、2 条 `project_regression`、2 条 `diagnostic_stress`；难度分布为 L1=2、L2=2、L3=6、L4=2。
  - 新增 `scripts/validate_sec_benchmark.py`，校验 schema、company/year/form source availability、expected section evidence coverage、structured metric readiness、gold context missing warning，并支持 BM25/object-BM25 smoke。
- Result and evidence:
  - First-step command: `python scripts\validate_sec_benchmark.py --cases-path eval\sec_cases\test_cases_v1.jsonl --output-path reports\quality\sec_benchmark_v1_step1_readiness.json --run-bm25-smoke`。
  - Report: `reports/quality/sec_benchmark_v1_step1_readiness.json`。
  - Result: `case_count=12`，`pass_count=12`，`fail_count=0`，hard failure types `{}`。
  - Warnings: `gold_context_missing=10`。这是预期，因为本轮只落 seed benchmark 和 first-step readiness，还未人工标注 Gold Context。
  - 初版 metric readiness 对 AMZN AWS revenue / PANW RPO 等 row-level string match 过严；已修正为 structured-object readiness 检查，避免把 object-BM25 可覆盖的表格对象误判为 benchmark 缺口。
- Decision: SEC benchmark v1 可以作为下一阶段正式评测骨架；当前第一步测试通过，说明 source/evidence/index 层支持这些 case。下一步应补 Gold Context / Gold Facts，然后实现 Gold/Pipeline 双模式 runner 和 claim-level scorer。
- Follow-up and safety notes: 本轮没有运行新 9B 模型推理，也没有生成 teacher-ready 样本。`gold_context_missing` 不能忽略为通过生产评测，只表示 benchmark scaffold 已准备好但人工 gold 尚未完成。

## 本次记录 - Seed Gold Context and Context-Only Runner

- Problem: 用户确认继续后，需要补第一批 Gold Context / Gold Facts，并启动 Gold Context vs Pipeline Context 的执行骨架。
- Reasoning and decision: 不能把程序检索出来的证据直接冒充人工 gold。因此本轮先生成 `seed_needs_review` 级别的 gold candidates，并实现 context-only 双模式 runner，先验证每个 case 在 gold/pipeline 两种模式下都能产出可追踪 context，再接 9B synthesis 和 claim scorer。
- Work completed:
  - 新增 `scripts/build_sec_gold_context_seed.py`：基于 filtered BM25 over `EvidenceObject` 与 ObjectBM25 over structured metric/table objects，为 `gold_context_status=needs_annotation` 的 case 生成 seed context 和 seed facts。
  - 新增 `scripts/run_sec_benchmark_eval.py`：支持 `--mode all|gold_context|pipeline_context`，输出 context-only 的 `agent_outputs.jsonl`、`claim_verification.jsonl`、`scores.jsonl`、`trace_logs.jsonl`、`bad_cases.md` 和 `run_summary.json`。
  - 更新 `docs/eval/sec_benchmark_v1.md` 和 `eval/sec_cases/README.md`，记录 seed gold 与 context-only runner 的复现命令。
- Result and evidence:
  - Seed build command: `python scripts\build_sec_gold_context_seed.py --overwrite --report-path reports\quality\sec_benchmark_v1_gold_context_seed_report.json`。
  - Seed report: `reports/quality/sec_benchmark_v1_gold_context_seed_report.json`，`created_count=10`，`skipped_count=2`，`context_row_count=614`，`fact_row_count=176`。两个 skipped case 是 anti-hallucination trap，`gold_context_status=not_required_for_trap`。
  - Post-seed readiness: `reports/quality/sec_benchmark_v1_step1_readiness_after_gold_seed.json`，`case_count=12`，`pass_count=12`，`fail_count=0`，warning types `{}`。
  - Context-only run: `eval/sec_cases/outputs/run_20260518_context_only_smoke/run_summary.json`，`trace_count=24`，`agent_output_count=22`，`context_prepared=22`，`skipped_mode_not_supported=2`；`bad_cases.md` 显示 no context-preparation failures。
  - Py-compile passed for `scripts/build_sec_gold_context_seed.py`、`scripts/run_sec_benchmark_eval.py`、`scripts/validate_sec_benchmark.py`。
- Decision: Benchmark v1 现在具备三层基础：case schema、seed gold artifacts、gold/pipeline context runner。下一步才适合接入 Qwen3.5-9B synthesis，并把 validators/scorer 绑定到 `agent_outputs.jsonl` / `claim_verification.jsonl` / `scores.jsonl`。
- Follow-up and safety notes: 当前 Gold Context / Gold Facts 仍是程序 seed，不是人工审定 gold。不能用这些 seed 直接宣称模型 benchmark 分数；必须先人工 review 或至少做一轮 validator-assisted review。

## 本次记录 - Seed Gold Manual Review Gate

- Problem: 用户要求先人工审定当前 seed Gold Context / Gold Facts，再判断是否能进入主链路测试。
- Reasoning and decision: 本轮按 case-level gate 审核，不以文件存在或 readiness pass 作为进入主链路的依据。Gold Context 必须能隔离模型 synthesis 能力，Gold Facts 必须只包含目标事实；如果 gold 自身混入 prior-period、非目标 metric 或宽泛背景，Gold-vs-Pipeline 结果会失真。
- Work completed:
  - 审阅 `eval/sec_cases/gold_context/*.jsonl` 和 `eval/sec_cases/gold_facts/*.json` 的 row count、selection method、section/ticker/year coverage、top evidence preview 和 facts preview。
  - 新增机器可读 gate：`reports/quality/sec_benchmark_v1_gold_manual_review.json`。
  - 新增人读审定报告：`docs/eval/sec_benchmark_v1_gold_review.md`。
  - 验证 `sec_benchmark_v1_gold_manual_review.json` 可被 `python -m json.tool` 解析。
- Result and evidence:
  - Overall status: `not_approved_for_mainline_scored_benchmark`。
  - Allowed next step: `validator_and_context_smoke_only`。
  - Blocked next step: `qwen9b_scored_gold_vs_pipeline_mainline_test`。
  - Case decisions: `approved_for_pipeline_trap_smoke=2`，`needs_manual_trim_before_gold_context_mode=4`，`reject_seed_facts_before_mainline=6`。
  - 主要 blocker：numeric facts 不是 reviewed target facts，而是候选 metric rows；大量 facts 混入 prior-period table columns、percentage/change values、非目标 metric；多个 text contexts 含 generic risk、audit/index、tax、revenue policy、broad business rows；L4 diagnostic cases context 过宽，不能隔离模型能力。
  - 具体样例：`AAPL_SERVICES_MARGIN_2023_2025_001` 的 12 个 fact 中 11 个 suspicious；`REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001` 的 108 个 fact 中至少 66 个 suspicious；`GOOGL_CLOUD_CONTEXT_ROLE_2025_001` 包含正确 2025 Google Cloud revenue / operating income evidence，但 target facts 混入 prior-year values。
- Decision: 当前 seed gold **不能进入主链路 scored Gold-vs-Pipeline 测试**。可以进入的是 context-only smoke 和两个 trap case 的 pipeline refusal smoke。主链路前必须先做 reviewed/trimmed Gold Context 和 deterministic cell-level Gold Facts。
- Follow-up and safety notes: 本轮没有运行 9B synthesis，也没有生成 benchmark 分数。下一步应优先构建 reviewed gold：文本类 case 保留 core/support/caveat rows；数值/table case 改成精确 company-year-metric cell gold；prior-period comparison columns 只能作为 context，不能作为 target facts。

## 本次记录 - Executable SEC Gold Gate

- Problem: seed gold 人工审定结论已经明确，但如果后续 runner 只检查文件是否存在，仍可能误把 `seed_needs_review` 文件接入 scored mainline。
- Reasoning and decision: 把人工审定结论升级为可执行 gate。`context_smoke` 允许 seed 级 context 继续用于链路准备；`trap_smoke` 只允许两个 anti-hallucination trap；`mainline_scored` 必须要求整体审定状态、case-level decision、reviewed row status 和 context 宽度同时过关。
- Work completed: 新增 `scripts/validate_sec_gold_gate.py`，读取 `eval/sec_cases/test_cases_v1.jsonl`、`reports/quality/sec_benchmark_v1_gold_manual_review.json`、`eval/sec_cases/gold_context/` 和 `eval/sec_cases/gold_facts/`，输出机器可读 gate report；更新 `docs/eval/sec_benchmark_v1.md`、`eval/sec_cases/README.md` 和 master checklist。
- Result and evidence:
  - `python scripts\validate_sec_gold_gate.py --gate context_smoke --output-path reports\quality\sec_benchmark_v1_gold_gate_context_smoke.json`：`can_enter_gate=true`，10 pass，2 skipped；warning 为 `seed_gold_context_smoke_only=10`、`seed_gold_facts_smoke_only=7`。
  - `python scripts\validate_sec_gold_gate.py --gate trap_smoke --output-path reports\quality\sec_benchmark_v1_gold_gate_trap_smoke.json`：`can_enter_gate=true`，2 pass，10 skipped。
  - `python scripts\validate_sec_gold_gate.py --gate mainline_scored --output-path reports\quality\sec_benchmark_v1_gold_gate_mainline.json`：`can_enter_gate=false`，10 fail，2 pass；overall blocker 为 `manual_review_overall_not_mainline_approved`；case blockers 包括 `manual_review_not_mainline_approved=10`、`seed_gold_context_not_reviewed=10`、`seed_gold_facts_not_reviewed=7`、`gold_context_too_wide_for_mainline=3`。
- Decision: 当前主链路 scored benchmark 继续阻断。下一步不是跑 9B scored benchmark，而是构建 reviewed/trimmed Gold Context 和 deterministic Gold Facts，然后重新跑 `mainline_scored` gate。
- Follow-up and safety notes: 本轮没有调用模型、没有使用云端、没有写入凭据。新增 gate 只做 deterministic 文件和审定状态检查，不替代后续 claim-level scorer。

## 本次记录 - First Reviewed Gold Case

- Problem: 全量 seed gold 被拒绝后，需要先证明 reviewed-gold 目录、事实 schema 和 gate 流程能工作，而不是直接跳到大批量人工标注。
- Reasoning and decision: 先选最小但关键的 numeric regression case `GOOGL_CLOUD_CONTEXT_ROLE_2025_001`。它直接覆盖此前最容易出错的 metric role 问题：Google Cloud revenue 不能和 Google Cloud operating income 混用。
- Work completed:
  - 新增 `eval/sec_cases/reviewed_gold_context/GOOGL_CLOUD_CONTEXT_ROLE_2025_001.jsonl`，只保留 5 行 reviewed context：3 行 evidence source、2 行 structured target facts。
  - 新增 `eval/sec_cases/reviewed_gold_facts/GOOGL_CLOUD_CONTEXT_ROLE_2025_001.json`，只保留 2 个目标事实：2025 Google Cloud revenue `58,705 usd_millions` 和 2025 Google Cloud operating income `13,910 usd_millions`。
  - 新增 `reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json`，明确这是 partial single-case approval，不代表全量 benchmark 通过。
  - `scripts/validate_sec_gold_gate.py` 增加 `--case-id` 过滤；partial approval 只允许在 case-filtered mainline gate 中使用。
- Result and evidence:
  - Single-case reviewed gate command: `python scripts\validate_sec_gold_gate.py --gate mainline_scored --case-id GOOGL_CLOUD_CONTEXT_ROLE_2025_001 --gold-context-dir eval\sec_cases\reviewed_gold_context --gold-facts-dir eval\sec_cases\reviewed_gold_facts --manual-review-path reports\quality\sec_benchmark_v1_reviewed_gold_partial_approval.json --output-path reports\quality\sec_benchmark_v1_gold_gate_reviewed_googl_single_case.json`。
  - Result: `can_enter_gate=true`，`status_counts={"pass":1}`，blocker/warning 均为空；context 为 5 行、seed row 为 0；facts 为 2 条、seed fact 为 0。
  - Full mainline gate 复跑仍为 `can_enter_gate=false`，10 fail / 2 pass，说明单 case partial approval 没有误放开全量 benchmark。
- Decision: reviewed-gold 流程已跑通一个 case；下一步可以按同一格式扩展 AMZN AWS、AAPL Services、PANW visibility 和 revenue/income/CFO table 等数值类 case。
- Follow-up and safety notes: 本轮没有运行模型推理，也没有生成 benchmark 分数。Reviewed context 中的数值仍依赖当前 structured object ID；如果后续重建 structured objects，需要重新验证 object_id 稳定性或做 source_evidence_id + metric tuple 对齐。

## 本次记录 - AMZN AWS Reviewed Gold and Numeric Coverage Gate

- Problem: 用户确认下一步后，需要把 reviewed gold 从 GOOGL 单 case 扩到 `AMZN_AWS_NUMERIC_2023_2025_001`，并确保 reviewed facts 不只是文件存在，而是真的覆盖 declared `numeric_checks`。
- Reasoning and decision: AMZN seed facts 的主要污染来自把 `AWS 13/19/20` 这类 YoY 百分比当成 revenue，以及混入 prior-period operating income 和非 AWS segment charge sentence。因此 reviewed facts 只保留 `Net Sales` 表里的 AWS dollar cells 和 `Operating income by segment` 表里的 AWS dollar cells。
- Work completed:
  - 新增 `eval/sec_cases/reviewed_gold_context/AMZN_AWS_NUMERIC_2023_2025_001.jsonl`，含 5 行 reviewed evidence source 和 6 行 reviewed structured target fact。
  - 新增 `eval/sec_cases/reviewed_gold_facts/AMZN_AWS_NUMERIC_2023_2025_001.json`，目标 facts 为 AWS revenue / AWS operating income x fiscal 2023/2024/2025，共 6 个 reviewed target cells。
  - 更新 `reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json`，partial approval case 从 1 个扩到 2 个：`AMZN_AWS_NUMERIC_2023_2025_001` 与 `GOOGL_CLOUD_CONTEXT_ROLE_2025_001`。
  - `scripts/validate_sec_gold_gate.py` 增加 numeric coverage gate：mainline numeric case 必须对每个 declared metric/company/year 找到且只找到 1 个 reviewed fact，并且 ticker、fiscal_year、period、metric_family、metric_role、object_id、source_evidence_id 都匹配。
- Result and evidence:
  - AMZN reviewed facts：AWS revenue = `90,757 / 107,556 / 128,725 usd_millions`；AWS operating income = `24,631 / 39,834 / 45,606 usd_millions`。
  - Case-filtered reviewed gate command: `python scripts\validate_sec_gold_gate.py --gate mainline_scored --case-id GOOGL_CLOUD_CONTEXT_ROLE_2025_001 --case-id AMZN_AWS_NUMERIC_2023_2025_001 --gold-context-dir eval\sec_cases\reviewed_gold_context --gold-facts-dir eval\sec_cases\reviewed_gold_facts --manual-review-path reports\quality\sec_benchmark_v1_reviewed_gold_partial_approval.json --output-path reports\quality\sec_benchmark_v1_gold_gate_reviewed_numeric_cases.json`。
  - Result: `can_enter_gate=true`，2 pass，blocker/warning 均为空。AMZN context 11 rows、facts 6 rows、seed row/fact 均为 0；GOOGL context 5 rows、facts 2 rows、seed row/fact 均为 0。
  - Full reviewed dirs without case filter still blocked: `reports/quality/sec_benchmark_v1_gold_gate_reviewed_full_blocked.json` 中 `can_enter_gate=false`，10 fail / 2 pass，说明 partial approval 没有误放开全量 benchmark。
- Decision: 当前允许做 **case-filtered Gold Context scored smoke** 的 numeric cases 是 AMZN 和 GOOGL；全量 benchmark 仍不允许 scored mainline。
- Follow-up and safety notes: 本轮仍未运行 9B synthesis，没有生成模型分数。下一步可继续 reviewed gold：优先 `AAPL_SERVICES_MARGIN_2023_2025_001`，然后 `PANW_SUBSCRIPTION_VISIBILITY_2023_2025_001`，最后再做 48-cell revenue/income/CFO table。
