# Handoff - Reviewed9 Pipeline Gate And Answer Plan Next

## 当前结论

当前主线先不要切 27B，也不要直接扩大到 full benchmark。应先把 reviewed SEC benchmark pipeline 稳定跑通，再加 `Answer Plan / Judgment Plan` 层。

截至本交接，`reviewed9 + 2 trap` 的 case-filtered pipeline gate 已通过：

- 真实 Qwen3.5-9B pipeline-context 输出：`qwen_answer_ratio=1.0`
- 无 ledger repair：`qwen_ledger_repaired=0`
- 无 eligible fallback：`fallback_answered=0`
- Trap gate 通过：`trap_gate_pass=true`
- Gold-vs-pipeline 通过：`gold_vs_pipeline_pass=true`
- Answer ledger / metric role / named fact / ledger missing consistency / abstract judgment / ledger unit 全部通过
- Abstract rubric: `checked_case_count=9`，`required_dimension_count=37`，`covered_required_dimension_count=37`

这证明当前证据约束框架在 reviewed case-filtered benchmark 上能稳定产出合规答案；不能外推为 full noisy benchmark 或生产级全链路通过。

## 新窗口优先读这些文件

1. `docs/worklog/60_evidence_constraint_framework_next_stage.md`
2. `reports/model_runs/20260519_sec_benchmark_reviewed9_judgment_plan_bundle_gate.md`
3. `reports/model_runs/20260518_sec_benchmark_reviewed9_platform_pipeline_gate.md`
4. `reports/model_runs/20260518_sec_benchmark_platform_recurring_gold_qwen9b.md`
5. `reports/quality/local_reviewed9_judgment_plan_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`
6. `reports/quality/local_reviewed9_platform_strictadobe_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`
7. `eval/sec_cases/outputs/run_20260519_reviewed9_judgment_plan_plus_traps_pipeline_gate_bundle/run_summary.json`
8. `eval/sec_cases/abstract_judgment_rubric_v0_1.json`
9. `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
10. `scripts/validate_sec_benchmark_answer_vs_judgment_plan.py`

## 最近完成的关键工作

### Reviewed9 platform recurring-quality case

新增并审定了 `PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001`：

- Reviewed facts: `eval/sec_cases/reviewed_gold_facts/PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001.json`
- Reviewed context: `eval/sec_cases/reviewed_gold_context/PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001.jsonl`
- Reviewed approval: `reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json`
- Exact-value ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`

Reviewed ledger 扩到 `approved_case_count=9`，`row_count=50`。

### Platform gold-context true-Qwen smoke

输出目录：

- `eval/sec_cases/outputs/run_20260518_platform_recurring_gold_qwen9b_hf_32768_ledger50_abs_py/`

结果：

- `answer_status=answered_qwen9b`
- `qwen_output_status=valid_json`
- `ledger_text_contract_violation_count=0`
- `ledger_text_contract_sanitized_count=0`
- `score_total=8.4`

问题：

- Gold-context 答案安全但偏保守，正文没有主动使用 `display_value_zh`，`exact_value_hit_count=0`。

### Platform pipeline-context true-Qwen gate

Pipeline trace:

- `eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_context_traces_top8`
- `context_row_count=120`
- 覆盖 AAPL/ADBE/MSFT 的 2023/2024/2025。

最终采用输出：

- `eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_qwen9b_vllm_structured_5000_rubricprompt_strictadobe/`

最终 reviewed9 + traps bundle：

- `eval/sec_cases/outputs/run_20260518_reviewed9_gold_reference_qwen9b_mixed`
- `eval/sec_cases/outputs/run_20260518_reviewed9_platform_strictadobe_plus_traps_pipeline_gate_bundle`
- `reports/quality/local_reviewed9_platform_strictadobe_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`

最终结果：

- `trap_gate_pass=true`
- `gold_vs_pipeline_pass=true`
- `answer_ledger_gate_pass=true`
- `metric_role_term_gate_pass=true`
- `named_fact_gate_pass=true`
- `ledger_missing_consistency_gate_pass=true`
- `abstract_judgment_gate_pass=true`
- `ledger_unit_gate_pass=true`
- `qwen_answer_ratio=1.0`
- `qwen_ledger_repaired=0`
- `fallback_answered=0`

## 重要代码变更

### `scripts/run_sec_eval_synthesis_qwen9b_backend.py`

现在 final synthesis prompt 会读取 `eval/sec_cases/abstract_judgment_rubric_v0_1.json`，把当前 case 的 required dimensions、calibration checks 和 forbidden claims 作为 compact hard contract 注入 prompt。

动机：

- 第一版 platform pipeline 数值正确，但漏了“visibility / recurring quality 不等于 growth / margin”的抽象判断。
- 只把 `gold_points` 放进 prompt 不够硬；模型会逐条覆盖一部分，但不一定知道哪些 caveat 必须改变结论强度。

当前结论：

- Rubric prompt 后，platform case 从 `abstract_judgment 4/6` 提升到最终严格版 `7/7`。

### `eval/sec_cases/abstract_judgment_rubric_v0_1.json`

为 platform recurring-quality case 加了更严格的 Adobe caveat：

- Adobe subscription revenue 支持 visibility / recurring quality
- 但缺少可比毛利率或成本结构证据
- 因此不能完整判断盈利质量

这条是人工 review 后新增的，因为模型初版会把 Adobe 订阅可见性写得过强。

### `scripts/validate_sec_benchmark_named_fact_support.py`

修了两个 false positive：

1. Ledger-backed company metric label 可以由同一 location 的 sibling `metric_ids` 支撑。
   - 例如 `Adobe Total subscription revenue` 不一定必须由 citation text exact match 支撑，只要同一 key point 有 ADBE ledger metric_id。
2. Summary 继承 driver/key point 的 evidence_id 和 metric_id 并集。
   - 避免 `Apple Services` 这类 summary label 只因 summary 没有单独 metric_id 而变成 warning。

## 当前模型输出质量判断

从 reviewed gold 标准看，当前最终 platform answer 是合格的：

- Apple Services: 覆盖收入、毛利率、非纯订阅 caveat。
- Adobe: 覆盖 subscription revenue、递延确认、经常性/可见性，同时说明缺少毛利率/成本结构，不能完整判断盈利质量。
- Microsoft: 写成 broad cloud proxy，说明订阅/用量混合、毛利率下降和 AI infrastructure cost pressure。
- 结论强度: Apple/Adobe 是 `medium`，Microsoft 是 `weak`，没有强行横比或强排序。
- 数值: 使用 ledger display value，并有 metric_id 支撑。

仍需注意：

- 输出比早期好很多，但仍偏 contract-driven，像是在按评分表答题。
- Apple caveat 中出现过“硬件相关服务”这种偏泛表达，后续应固定为 “mixed services bundle / not pure subscription”，避免引入新解释。
- 当前结果是 reviewed9 case-filtered pass，不是 full benchmark pass。

## 关于 27B / 4090 的当前判断

用户问过是否在 4090 上先做 Qwen3.5-27B 4bit 对比。

已有历史诊断：

- `reports/model_runs/20260515_phase1_qwen35_27b_gptq_serving_diagnostic.md`
- 现有 `Qwen3.5-27B-GPTQ-Int4` 是 multimodal/hybrid artifact，不是理想 text-only 27B。
- checkpoint 约 `28.16 GiB`。
- 4090 24GB 上需要 `10-14GB CPU offload`。
- decode 约 `0.7-1.0 tok/s`。
- `offload=6GB` 即使 `max_model_len=2048` 也 OOM。

建议：

- 当前先不要把 pipeline 切到 27B。
- 先跑通 9B pipeline 与 Answer Plan。
- 后续如果换 5090，再测 text-only 27B 4bit，先测 4k/8k/32k，无 offload 且速度足够再进 gold set。

## 未回答完的用户问题

用户最后问：

> 现在全链路下，之前的模型 verifier 还有效果吗？

这个问题还没有正式回答。新窗口应优先回答。

当前初步判断：

- SEC benchmark v1 当前跑通的 reviewed9 pipeline gate 路径主要是 `run_sec_benchmark_eval.py` 的 `pipeline_context`：
  - BM25 evidence retrieval
  - object BM25 structured object retrieval
  - final Qwen9B synthesis
  - deterministic post-gates
- 这条 reviewed9 gate 路径并没有明显使用早期 expanded v0.2 / cell-level chain 里的 Qwen2B/4B verifier 作为在线过滤步骤。
- 早期 verifier 的价值仍然存在，但更像是：
  - 构建 calibrated evidence pool
  - 诊断 object/cell relevance
  - 为 complex v0.2 chain 做 candidate filtering
- 对当前 SEC benchmark v1 reviewed pipeline，它不是主因。当前 pass 主要来自 reviewed gold / ledger / abstract rubric / deterministic validators。

新窗口应做的事：

1. 明确读取 `scripts/run_sec_benchmark_eval.py`，确认当前 `pipeline_context` 真实调用路径。
2. 对比早期 verifier 相关脚本：
   - `scripts/run_qwen_small_verifier.py`
   - `scripts/run_qwen_small_verifier_vllm.py`
   - `scripts/evaluate_small_verifier.py`
   - `scripts/evaluate_aspect_verifier.py`
   - `scripts/export_calibrated_evidence_pool.py`
3. 给用户一个清楚结论：
   - 当前 reviewed9 SEC benchmark path 里，旧 verifier 不是线上必需组件。
   - 但在更大 noisy retrieval / cell evidence pool 里，verifier 仍可能有价值。
   - 如果要验证其当前增量，应设计 ablation：BM25/object-BM25 only vs verifier-filtered evidence pack，在 reviewed cases 上比较 recall、abstract gate、final quality。

## Answer Plan 下一阶段设计

用户担心 `Answer Plan` 会不会变成手工规则堆积。当前共识：

- 不要手写答案逻辑。
- 要手写通用证据边界和判错规则。
- 模型负责生成优先级排序。
- Validator 只检查这个排序有没有证据资格。

建议下一步实现：

```text
Evidence Pack / Ledger
  -> Judgment Plan
  -> Plan Validator
  -> Final Synthesis
  -> Final Validator
```

`Judgment Plan` 应作为结构化中间产物传入 final synthesis，而不是只让模型“脑子里记住”。

建议 schema：

```json
{
  "main_judgment": {
    "claim": "...",
    "strength": "strong|medium|weak",
    "claim_type": "ranking|comparison|caveated_comparison|insufficient_evidence"
  },
  "drivers": [
    {
      "rank": 1,
      "claim": "...",
      "claim_role": "visibility|profitability|growth|risk|comparability|caveat",
      "why_ranked_here": "...",
      "supporting_metric_ids": [],
      "supporting_evidence_ids": [],
      "covered_companies": [],
      "covered_years": [],
      "metric_families": [],
      "conclusion_strength": "strong|medium|weak",
      "caveats": []
    }
  ],
  "must_downgrade_because": [],
  "do_not_overstate": []
}
```

Plan Validator 初版应检查：

- driver 是否有 evidence / metric id
- id 是否存在于 evidence pack / ledger
- claim_role 与 metric_family / metric_role 是否匹配
- proxy 是否被当 direct metric
- growth / margin 是否被错误当 visibility 主证据
- caveat 是否导致 conclusion_strength 降级
- 缺核心 coverage 是否阻止 strong conclusion
- forbidden claims 是否出现
- final synthesis 是否新增 plan 外的新判断

关键原则：

- 不要把 `Adobe 必须排第一` 这类 case-specific 答案写死。
- 要把 `proxy 不能当 direct metric`、`risk disclosure 不能当已发生业绩`、`缺核心证据不能 strong conclusion` 这类通用规则固化。

## 建议新窗口第一步

先回答用户的 verifier 问题，然后进入 Answer Plan 设计。

推荐顺序：

1. 读 `scripts/run_sec_benchmark_eval.py` 和 reviewed9 gate summary，确认当前 SEC benchmark path 中旧 verifier 的实际作用。
2. 给出 verifier 是否仍有效的工程判断。
3. 新增 `Judgment Plan` artifact builder / runner，先只在两个 complex reviewed cases 上做：
   - `CLOUD_PROFITABILITY_2023_2025_DIAG_001`
   - `PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001`
4. 新增 `validate_sec_benchmark_judgment_plan.py`，只做 deterministic hard checks。
5. 接入 final synthesis prompt，让 final answer 受 plan 约束。
6. 复跑 reviewed9 + trap gate，比较：
   - abstract judgment
   - answer ledger
   - named fact
   - final answer 是否更自然
   - 是否减少 rubric 显式依赖

## 2026-05-18 Verifier 问题核对结论

问题：当前 reviewed9 + 2 trap 全链路下，之前的模型 verifier 是否仍有效果？

核对结果：

- `scripts/run_sec_benchmark_eval.py` 的 `pipeline_context` 入口只构建 context trace：加载 `BM25Retriever` 与 `ObjectBM25Retriever`，按 case prompt 和 numeric checks 取 `pipeline_bm25` / `pipeline_object_bm25` rows。该路径没有调用 `run_qwen_small_verifier.py`、`run_qwen_small_verifier_vllm.py`、`evaluate_small_verifier.py`、`evaluate_aspect_verifier.py` 或 `export_calibrated_evidence_pool.py`。
- reviewed9 最终推理命令使用 `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py` 读取 trace，再通过 `scripts/run_sec_eval_synthesis_qwen9b_backend.py` 构造 final prompt、Exact-Value Ledger contract、abstract rubric contract，并做 ledger normalization / sanitizer / deterministic fallback。这里也没有在线调用旧 Qwen2B/4B verifier。
- 旧 verifier 仍在 expanded v0.2 / cell-level / calibrated evidence pool 体系中有价值：它把 BGE 或 cell evidence pool 标成 `direct|partial|false`，再由 `export_calibrated_evidence_pool.py` 转成 citation/background/missing-aspect evidence pool。相关历史结果在 `reports/model_runs/model_run_index.md` 中仍记录为 diagnostic/completed evidence-pool 工作。

工程判断：

- 对当前 reviewed9 SEC benchmark main gate，旧模型 verifier 不是线上必需组件，也不是本次 pass 的主要原因。本次 pass 的主要来源是 reviewed gold、Exact-Value Ledger、pipeline BM25/object-BM25 context、Qwen9B final synthesis、abstract rubric prompt 和 deterministic validators。
- 对未来 full noisy benchmark 或更大的 cell/object evidence pool，verifier 仍可能有增量价值，尤其是压低无关 evidence、构建 calibrated pool、诊断 object/cell relevance。但这需要单独消融验证，不能从当前 reviewed9 gate 直接推断。

建议后续消融：

- 在 reviewed complex cases 上比较 `BM25/object-BM25 only` vs `verifier-filtered evidence pack`。
- 指标至少包含 target evidence recall、ledger row coverage、context noise ratio、answer ledger gate、abstract judgment gate、named fact gate、最终人工可读质量和运行成本。
- 若 verifier 降低 recall 或只改善噪声但不改善 final gates，应保留为 diagnostic/audit 工具；若能在 noisy/full benchmark 上稳定提升 gate 与人工质量，再考虑接回主链路。

本次未运行新推理、训练或 benchmark job；只是基于代码路径和现有 reviewed9 gate artifact 做静态核对。

## 2026-05-18 BGE/Qwen Reranker 路线核对结论

问题：早期日志显示 BGE/Qwen reranker 的召回/排序效果更好，为什么后面 reviewed SEC benchmark 主线没有继续接这条线？

核对结果：

- 这条线不是因为 reranker 指标差而被放弃。`reports/model_runs/20260516_phase2_object_reranker_baseline_compare.md` 显示，在 object BM25 top25 候选池上，BGE reranker v2 m3 明显优于 BM25 order 和 Qwen3-Reranker-0.6B：direct P@5 `0.6174`、nDCG@5 `0.9458`、false@5 `0.6957`、direct/relevant coverage `1.0`，且比 Qwen reranker 更快。该 run 的决策是 `proceed with BGE as current reranker baseline`。
- 后续 `expanded_v0.2 full chain` 仍用了 BGE + Qwen small verifier + calibrated evidence pool + Qwen9B synthesis，但结果暴露的 blocker 已经不主要是 reranker 排序：13 query 中 12/13 parsed、11/13 citation pass、mean diagnostic quality `0.7972`，但存在 invalid JSON、background-as-fact、numeric warning，以及 metric/table 输出不可机器校验。日志明确说 BGE 在 expanded set 上缺少最终标签，不能把 reranker 指标当成最终质量证明。
- cell-level 重构后，问题从 168 aspect 变成 698 cell/aspect tasks、6,980 candidates。vLLM verifier 后产出 1,426 citation objects、3,247 background objects、150 missing aspects；16k synthesis 仍只能纳入 574/698 aspects，strict quality `teacher_ready=0`。工作日志判断核心原因不是 verifier 吞吐，而是 evidence memory 与表格输出 contract。
- aspect-fit memory + cell JSON 后，citation gate 已 13/13 pass、reported cell exact rate `0.9571`，但 `teacher_ready=0/13`，剩余错误来自 unsupported cell 填值、单位/scale、签名行误入业务指标、RPO 定义 claim 误当数值 claim。这说明排序/筛选仍有价值，但不足以解决 final-answer 可审计性。
- 后面方向切到 formal SEC benchmark v1：先区分 Gold Context vs Pipeline Context，人工 reviewed facts/context，Exact-Value Ledger，deterministic post-gates。目标变成先证明在 reviewed case-filtered 边界内，Qwen9B + ledger/rubric/validator 能稳定合规；不是继续在 noisy expanded v0.2 上堆 reranker。

工程判断：

- BGE/Qwen reranker 线应描述为 `deprioritized / bypassed for the reviewed benchmark path`，不是技术失败或永久放弃。
- 当时真正让主线转向的是：缺少 full human gold labels、metric/table cell contract 不稳、numeric/unit/metric-role 漂移、上下文承载压力、以及 final synthesis 不能 teacher-ready。
- 当前 reviewed9 pipeline 没接 BGE reranker，是为了先收敛 evidence contract 与 answer validator；但未来做 full noisy benchmark 或 reviewed retrieval ablation 时，应把 BGE reranker 作为强 baseline 重新接入比较。

建议后续恢复方式：

- 不要直接把旧 expanded v0.2 BGE pool 接进 reviewed9 主线。
- 应在当前 reviewed SEC cases 上做小型 ablation：`BM25/object-BM25 only` vs `BGE reranked object topK` vs `BGE + verifier-filtered evidence pack`。
- 评价同时看 retrieval 指标和 final gate：ledger row coverage、target evidence recall、context noise、answer ledger、named fact、abstract judgment、人工可读质量、runtime。
- 如果 BGE 能在 reviewed retrieval ablation 中提升 coverage/noise 且不损害 final gates，再作为 pipeline_context 的候选排序层重新接入。

本次未运行新推理、训练或 benchmark job；只是基于既有 worklog、model run ledger 和 retrieval reports 做静态决策链复盘。

## 2026-05-18 BGE/Qwen + Verifier Evidence Pack 进入 Answer Plan 的执行结果

用户要求：

> 直接看看 BGE/qwen reranker + verifier-filtered evidence pack 的效果如何，如果 ok 的话就继续往 answer plan 下面做。

结论：

- BGE/Qwen reranker + verifier-filtered evidence pack 可以作为候选证据源 / retrieval-rerank baseline 继续使用。
- 不能直接替换当前 reviewed9 mainline，因为早期 full-chain blocker 已经转移到 metric-family/table-context、numeric relation、cell/table contract 和 abstract judgment calibration。
- 因此本次推进方式是：不把旧 verifier pool 直接并入生产路径，而是先新增 `Judgment Plan` 中间产物和 deterministic validator，让后续 final synthesis 只能引用通过计划 gate 的 driver / metric / caveat。

新增代码：

- `scripts/build_sec_benchmark_judgment_plan.py`
- `scripts/validate_sec_benchmark_judgment_plan.py`
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py` 新增可选 `--judgment-plan-path`
- `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py` 新增可选 `--judgment-plan-path`

新增输出：

- `reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json`
- `reports/quality/sec_benchmark_v1_reviewed_complex2_judgment_plan_seed_report.json`
- `reports/quality/sec_benchmark_v1_reviewed_complex2_judgment_plan_validation.json`
- `reports/model_runs/20260518_sec_benchmark_bge_qwen_verifier_pack_answer_plan_gate.md`

Gate 结果：

- Judgment Plan seed: `plan_count=2`、`driver_count=6`、`proxy_driver_count=2`、`plans_with_downgrades=2`
- Plan validator: `can_enter_gate=true`、`pass_count=2`、`fail_count=0`
- py_compile 通过：`build_sec_benchmark_judgment_plan.py`、`validate_sec_benchmark_judgment_plan.py`、`run_sec_eval_synthesis_qwen9b_backend.py`、`run_sec_benchmark_vllm_synthesis_from_traces.py`
- Prompt smoke 通过：platform case 的 prompt 可读到 Judgment Plan，`plan_driver_count=3`

当前 plan 的关键行为：

- Cloud case:
  - AMZN / GOOGL 具备 `cloud_revenue + operating_income` 三年 ledger support，driver strength 为 `strong`
  - MSFT 使用 `cloud_revenue_proxy + gross_margin`，driver strength 为 `weak`，必须 caveat，不能直接横比 segment operating income
- Platform case:
  - AAPL `services_revenue + gross_margin` 为 `medium`，必须说明 Services 不等于纯 subscription
  - ADBE `subscription_revenue` 为 `medium`，必须说明缺少毛利率 / 成本结构，不能完整判断盈利质量
  - MSFT `cloud_revenue_proxy + gross_margin` 为 `weak`，必须说明 proxy 和 contract visibility 限制

剩余 warning：

- `supporting_evidence_id_not_seen_in_trace=7`，集中在 platform case。原因是这些 id 在 reviewed ledger 里存在，但不一定都进入那次 pipeline trace topK。
- 这不是 plan gate hard fail，但提示后续接 synthesis 时要明确：ledger evidence 是允许的 support source，不能只把 trace topK 当唯一 evidence universe。

下一步：

1. 在 cloud/4090 上用 `--judgment-plan-path reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json` 复跑 Cloud + Platform 两个 complex reviewed cases。
2. 加一个 final answer-vs-plan validator，检查 final answer 是否新增了 plan 外的核心判断、是否把 plan 的 weak/medium driver 升级成 strong。
3. 若 complex2 通过，再考虑把 Judgment Plan 接入 reviewed9 + 2 trap bundle；然后才做 BGE/verifier pack 的 reviewed retrieval ablation。

## 2026-05-18 Answer-vs-Judgment-Plan Gate 执行结果

在 Judgment Plan seed/gate 之后，继续补了 final answer 层的 plan adherence gate。

新增代码：

- `scripts/validate_sec_benchmark_answer_vs_judgment_plan.py`
- `scripts/run_sec_benchmark_post_gates.py` 新增可选参数：
  - `--judgment-plan-path`
  - `--skip-answer-vs-judgment-plan-gate`

Validator 当前检查：

- final answer 的 `decision_drivers` 必须能匹配 Judgment Plan driver。
- final answer 的 `supporting_metric_ids` / `supporting_evidence_ids` 必须在 plan 内。
- driver-local evidence 不能借用另一个 plan driver 的 evidence。
- final answer 不能把 plan 的 `weak/medium` driver 升级为 `strong/medium` 等更强结论。
- proxy metric driver 必须带 proxy / 口径 / 不能直接比较 caveat。
- weak plan support 不能在局部文本里无 caveat 地写成强结论。

Smoke 结果：

- Cloud 旧 rubric-only 输出被新 gate 拦下：
  - `answer_driver_evidence_id_not_in_matched_plan_driver=1`：Google driver 混入了 AMZN evidence id。
  - `answer_driver_strength_exceeds_plan=1`：MSFT proxy driver 从 plan `weak` 被写成 answer `medium`。
  - `proxy_answer_driver_missing_caveat=1`
- Platform 旧 rubric-only 输出被新 gate 拦下：
  - `answer_driver_evidence_id_not_in_plan=3`
  - `answer_driver_evidence_id_not_in_matched_plan_driver=3`
  - `answer_support_evidence_id_not_in_plan=6`
- Post-gate integration smoke 路径：
  - `reports/quality/local_platform_answer_vs_judgment_plan_post_gate_smoke/sec_benchmark_post_gates_summary.json`
  - 旧 gates 仍通过：answer ledger、metric role、named fact、ledger missing consistency、abstract judgment、ledger unit。
  - 新 `answer_vs_judgment_plan_gate_pass=false`，证明它补上了之前 gates 没覆盖的 plan adherence 问题。

本地环境限制：

- 本地 `vllm` 不可用。
- 本地不存在 `data/models_private/modelscope/Qwen/Qwen3___5-9B` 或 `data/models_private/modelscope/Qwen/Qwen3.5-9B`。
- 因此本轮没有运行新的 true-Qwen inference。需要在 4090/cloud 环境复跑。

云端下一步命令：

```bash
python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260518_reviewed8_pipeline_context_traces_top8 \
  --output-dir eval/sec_cases/outputs/run_20260518_cloud_pipeline_qwen9b_judgment_plan \
  --case-id CLOUD_PROFITABILITY_2023_2025_DIAG_001 \
  --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B \
  --max-model-len 32768 \
  --max-tokens 5000 \
  --structured-json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json

python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_context_traces_top8 \
  --output-dir eval/sec_cases/outputs/run_20260518_platform_pipeline_qwen9b_judgment_plan \
  --case-id PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001 \
  --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B \
  --max-model-len 32768 \
  --max-tokens 5000 \
  --structured-json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json
```

## 2026-05-18 Cloud True-Qwen Judgment Plan Complex2 复跑结果

按上面的云端命令实际复跑了 Cloud + Platform 两个 complex reviewed cases。

云端环境：

- Repo: `/root/autodl-tmp/FIN_Insight_Agent`
- Python: `/root/miniconda3/bin/python3`
- Model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`
- vLLM: available
- 上传的本轮脚本在远端已 `py_compile` 通过；覆盖前备份到 `.tmp_judgment_plan_backup_20260518`
- 未把 SSH 密码或任何 token 写入 repo / logs

远端 Judgment Plan validation：

- `reports/quality/sec_benchmark_v1_reviewed_complex2_judgment_plan_validation_cloud.json`
- `can_enter_gate=true`
- `pass_count=2`
- `fail_count=0`
- warning: `supporting_evidence_id_not_seen_in_trace=7`，与本地一致

True-Qwen 输出：

- Cloud:
  - `eval/sec_cases/outputs/run_20260518_cloud_pipeline_qwen9b_judgment_plan`
  - `answer_status=answered_qwen9b`
  - model load `63.6566s`
  - total elapsed `155.9582s`
  - final summary 说明 AWS / Google Cloud 有 direct revenue + operating income，Microsoft 是 weak proxy，直接盈利排名不可行
- Platform:
  - `eval/sec_cases/outputs/run_20260518_platform_pipeline_qwen9b_judgment_plan`
  - `answer_status=answered_qwen9b`
  - model load `61.1203s`
  - total elapsed `163.2889s`
  - final summary 说明 Apple / Microsoft / Adobe 都有增长证据，但受口径差异、毛利率压力和缺失盈利质量证据限制，无法得出强结论

Post-gates：

- Cloud:
  - `reports/quality/cloud_judgment_plan_post_gates/sec_benchmark_post_gates_summary.json`
  - answer ledger / metric role / named fact / ledger missing consistency / abstract judgment / answer-vs-plan / ledger unit 全部通过
  - answer-vs-plan: `pass_count=1`, `fail_count=0`
- Platform:
  - `reports/quality/platform_judgment_plan_post_gates/sec_benchmark_post_gates_summary.json`
  - answer ledger / metric role / named fact / ledger missing consistency / abstract judgment / answer-vs-plan / ledger unit 全部通过
  - answer-vs-plan: `pass_count=1`, `fail_count=0`

本次小的 gate 词表修正：

- Cloud abstract rubric 增加 `不可行`，用于识别“直接盈利排名不可行”这类等价表达。
- answer-vs-plan proxy caveat 词表增加 `用量` / `usage` / `不同`，用于识别 Microsoft Cloud proxy 中“包含用量型收入”这类等价 caveat。
- 这是同义表达补全，不改变 evidence / metric / strength 约束。

当前决策：

- `Judgment Plan -> Final Synthesis -> Answer-vs-Plan Gate` 在两个 complex reviewed cases 上已经可行。
- Judgment Plan 路径已经接入 reviewed9 + 2 trap bundle。没有 plan 的 case 保持空 plan / skip answer-vs-plan，不能硬套 complex2 plan。
- 下一步应扩大 reviewed gold set，专门考察 Judgment Plan + pipeline gate 的泛化能力，再决定是否推进 full noisy benchmark。

## 2026-05-19 RTX 5090 / 32GB vLLM 适配

用户更新云端资源为 RTX 5090 32GB，数据仍在迁移中；要求先适配 vLLM 和 32GB 显存，同时保留 4090 配置。

已完成：

- 新增 `configs/vllm_hardware_profiles.json`，并保留 `rtx4090_24gb` 与新增 `rtx5090_32gb` 两套 profile。
- 新增 `scripts/vllm_hardware_profiles.py`，各 vLLM 入口可通过 `--hardware-profile` 或 `FIN_VLLM_HARDWARE_PROFILE` 启用 profile；显式 CLI 参数仍优先。
- 新增 `scripts/check_vllm_blackwell_env.py`，用于检查 GPU、compute capability、torch CUDA build 和 vLLM availability。
- 接入 profile 的入口包括 SEC resident synthesis、small verifier、Query Contract planner、Driver Pack planner、long-context synthesis 和旧 planner/evidence demo。
- 远端 `/root/autodl-tmp/FIN_Insight_Agent` 已同步这些文件；覆盖前备份到 `.tmp_5090_profile_backup_20260519_125528`。

远端只读环境核对：

- GPU: `NVIDIA GeForce RTX 5090`, `32607 MiB`, driver `580.76.05`, compute capability `12.0`
- Python: `/root/miniconda3/bin/python`, Python `3.12.3`
- Torch: `2.11.0+cu130`, CUDA build `13.0`, CUDA available, device `sm_120`
- vLLM: `0.21.0`
- `scripts/check_vllm_blackwell_env.py --expected-profile rtx5090_32gb --json` 返回 `compatible=true`

当前 5090 profile 取值：

- SEC benchmark synthesis: `max_model_len=65536`, `max_tokens=6000`, `gpu_memory_utilization=0.92`, `cpu_offload_gb=0.0`, `max_num_seqs=1`
- Long-context synthesis: `max_model_len=131072`, `synthesis_max_tokens=8500`, `gpu_memory_utilization=0.94`
- Small verifier: `max_num_seqs=96`, `prompt_batch_size=768`, `gpu_memory_utilization=0.90`, `dtype=bfloat16`

未运行：

- 本次没有跑新的 Qwen inference、verifier batch、benchmark 或 post-gates；原因是云端数据仍在迁移中。

下一步：

- 迁移完成后先跑环境 checker，再用 `--hardware-profile rtx5090_32gb` 跑一个 reviewed-case resident vLLM smoke。
- 如果 9B 路径稳定，再按 4k / 8k / 32k 无 CPU offload 重新测 27B 4bit text-only 可行性。

后续状态：

- 该 5090 smoke 已完成；见本文末尾 `2026-05-19 RTX 5090 Corrected Profile Smoke` 和 `docs/worklog/80_cloud_5090_vllm_profile.md`。
- 初始 import workaround 被更正：不要用 `python -O` / `PYTHONOPTIMIZE=1` 跑生成；当前 profile 使用 `TORCHDYNAMO_DISABLE=1` 和 `VLLM_USE_FLASHINFER_SAMPLER=0`。

## 2026-05-19 Reviewed9 + 2 Trap Judgment Plan Bundle Gate

本轮把 Cloud / Platform 两个 complex reviewed case 的 Judgment Plan true-Qwen 输出合入 reviewed9 + 2 trap pipeline bundle，并跑完总 post-gates。

新增 bundle：

- `eval/sec_cases/outputs/run_20260519_reviewed9_judgment_plan_plus_traps_pipeline_gate_bundle`
- `trace_count=11`
- `agent_output_count=11`
- `answer_status_counts={"answered_qwen9b":9,"answered_contract_fallback":2}`
- 替换 case:
  - `CLOUD_PROFITABILITY_2023_2025_DIAG_001`
  - `PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001`

总 post-gates：

- `reports/quality/local_reviewed9_judgment_plan_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`
- `trap_gate_pass=true`
- `gold_vs_pipeline_pass=true`
- `answer_ledger_gate_pass=true`
- `metric_role_term_gate_pass=true`
- `named_fact_gate_pass=true`
- `ledger_missing_consistency_gate_pass=true`
- `abstract_judgment_gate_pass=true`
- `answer_vs_judgment_plan_gate_pass=true`
- `ledger_unit_gate_pass=true`
- `qwen_answer_ratio=1.0`
- `qwen_ledger_repaired=0`
- `fallback_answered=0`

关键计数：

- answer ledger: `case_count=11`, `pass_count=11`, `exact_value_hit_count=35`
- named fact: `pass_count=9`, `skip_count=2`, `unsupported_token_count=0`
- ledger missing: `missing_statement_count=5`, `false_missing_statement_count=0`
- abstract judgment: `checked_case_count=9`, `required_dimension_count=37`, `covered_required_dimension_count=37`
- answer-vs-plan: `checked_case_count=2`, `pass_count=2`, `skip_count=9`
- ledger unit: `ledger_row_count=50`, `pass_count=50`

决策：

- Judgment Plan 作为 gated planning/synthesis constraint 已通过当前 reviewed9 + trap 诊断边界。
- 这个结果仍然是 case-filtered diagnostic-only；不能外推为 full noisy benchmark。
- 下一阶段优先扩 reviewed gold set，用更多 case 检验 Judgment Plan、named-fact、ledger-missing、abstract-rubric 与 answer-vs-plan gate 的泛化稳定性。

## 复现命令

Reviewed9 + 2 trap Judgment Plan bundle final post-gates:

```bash
python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260518_reviewed9_gold_reference_qwen9b_mixed \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260519_reviewed9_judgment_plan_plus_traps_pipeline_gate_bundle \
  --output-dir reports/quality/local_reviewed9_judgment_plan_plus_traps_pipeline_gate_bundle_post_gates \
  --min-qwen-answer-ratio 1.0 \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json
```

Reviewed9 final post-gates:

```bash
python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260518_reviewed9_gold_reference_qwen9b_mixed \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260518_reviewed9_platform_strictadobe_plus_traps_pipeline_gate_bundle \
  --output-dir reports/quality/local_reviewed9_platform_strictadobe_plus_traps_pipeline_gate_bundle_post_gates \
  --min-qwen-answer-ratio 1.0 \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json
```

Platform pipeline trace:

```bash
python scripts/run_sec_benchmark_eval.py \
  --mode pipeline_context \
  --output-dir eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_context_traces_top8 \
  --case-id PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001 \
  --evidence-top-k 8 \
  --object-top-k 8
```

Final platform cloud vLLM run command is recorded in:

- `reports/model_runs/20260518_sec_benchmark_reviewed9_platform_pipeline_gate.md`

## Safety Notes

- Do not record cloud passwords or tokens in repo files.
- Current results are diagnostic-only.
- Do not directly run full noisy benchmark until Answer Plan / Plan Validator is added and reviewed case coverage is expanded.

## 2026-05-19 SEC Benchmark v1 Reviewed10 Gold Table Closeout

本轮把 v1 最后一条未审核的非 trap case 收成 reviewed10：

- `REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001`
- 任务：给 Microsoft / Alphabet / Meta / Amazon 生成 2023-2025 consolidated total revenue、operating income、net income、net cash provided by operating activities 表格，并逐 cell 引用。
- 原 seed 状态：224 context rows / 108 fact candidates，不能作为 gold。
- 新状态：approved for case-filtered `gold_context` scored smoke。

新增 / 更新 artifacts：

- reviewed facts: `eval/sec_cases/reviewed_gold_facts/REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001.json`
  - `fact_count=48`
  - 4 companies x 3 years x 4 metrics
  - metric families: `total_revenue`, `operating_income`, `net_income`, `cash_flow`
  - unit: `usd_millions`
- reviewed context: `eval/sec_cases/reviewed_gold_context/REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001.jsonl`
  - `row_count=56`
  - 48 reviewed table-cell rows + 8 compact table source rows
- case spec: `eval/sec_cases/test_cases_v1.jsonl`
  - numeric checks now include `net_income`
  - total revenue metric family corrected to `total_revenue`
- approval: `reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json`
  - reviewed non-trap case count updated to 10
- ledger unit validator: `scripts/validate_sec_benchmark_ledger_units.py`
  - now accepts reviewed ledger facts backed by `TableObject` ids when no `MetricObject` exists.

Validation evidence：

- reviewed10 gold gate:
  - `reports/quality/sec_benchmark_v1_gold_gate_reviewed10_text_numeric_cloud_platform_table.json`
  - `can_enter_gate=true`
  - `case_count=10`
  - `status_counts={"pass":10}`
- reviewed exact-value ledger:
  - `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`
  - `approved_case_count=10`
  - `row_count=98`
- ledger unit gate:
  - `reports/quality/sec_benchmark_v1_reviewed10_ledger_unit_gate.json`
  - `can_enter_gate=true`
  - `pass_count=98`
  - `fail_count=0`
  - no warnings
- context-only smoke:
  - `eval/sec_cases/outputs/run_20260519_reviewed10_gold_context_table_case`
  - `trace_count=1`
  - `agent_output_count=1`
  - `status_counts={"context_prepared":1}`

Decision：

- v1 non-trap gold set is now reviewed10 for case-filtered gold-context work.
- 本轮没有跑 true-Qwen synthesis；因此这不是 pipeline 泛化结论。
- Full noisy benchmark 仍不应直接推进。下一步应该先在 reviewed10 上补 pipeline-context / Judgment Plan 适配验证，再扩新 gold cases 做泛化。

## 2026-05-19 Reviewed10 Pipeline Table Bundle Gate

本轮继续把 reviewed10 表格 case 跑完 pipeline-context true-Qwen，并合入 reviewed10 + 2 trap bundle。

关键代码/契约变化：

- `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`：为 `metric_table_stability` 增加专用 structured schema。
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`：表格任务使用 compact `cell_table` 输出，只要求模型返回 `metric_id + status`，再由 ledger deterministic expansion 补全公司、年份、指标、数值、单位和 evidence。
- `scripts/validate_sec_benchmark_table_cells.py`：新增 table-cell deterministic gate，验证 expected metric_id 是否完整、唯一、与 ledger 一致。
- `scripts/run_sec_benchmark_post_gates.py`：接入 table-cell gate。
- `scripts/validate_sec_benchmark_named_fact_support.py`：把 `JSON` 加入 generic token，避免 fallback/format token 误报。

主要输出：

- pipeline trace top20: `eval/sec_cases/outputs/run_20260519_revenue_income_cfo_pipeline_context_traces_top20`
- pipeline true-Qwen table run: `eval/sec_cases/outputs/run_20260519_revenue_income_cfo_pipeline_qwen9b_vllm_structured_6000_table_metricids`
- gold true-Qwen table run: `eval/sec_cases/outputs/run_20260519_revenue_income_cfo_gold_context_qwen9b_vllm_structured_6000_table_metricids`
- reviewed10 gold reference bundle: `eval/sec_cases/outputs/run_20260519_reviewed10_gold_reference_qwen9b_mixed`
- reviewed10 + 2 trap pipeline bundle: `eval/sec_cases/outputs/run_20260519_reviewed10_judgment_plan_table_plus_traps_pipeline_gate_bundle`
- single table post-gates: `reports/quality/local_reviewed10_revenue_table_pipeline_qwen9b_post_gates/sec_benchmark_post_gates_summary.json`
- reviewed10 full bundle post-gates: `reports/quality/local_reviewed10_judgment_plan_table_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`
- model run ledger: `reports/model_runs/20260519_sec_benchmark_reviewed10_pipeline_table_bundle_gate.md`

结果：

- top8 pipeline trace 漏了 Microsoft cash-flow source；top20 trace 覆盖 48/48 reviewed source cells。
- full-row table schema 两次触发 raw JSON truncation；compact metric-id schema 成功，`answer_status=answered_qwen9b`、`parse_status=parsed`、`finish_reason=stop`。
- table-cell single-case gate: `expected_cell_count=48`、`reported_cell_count=48`、`valid_cell_count=48`。
- reviewed10 + 2 trap bundle:
  - `trap_gate_pass=true`
  - `gold_vs_pipeline_pass=true`
  - `answer_ledger_gate_pass=true`
  - `metric_role_term_gate_pass=true`
  - `table_cell_gate_pass=true`
  - `named_fact_gate_pass=true`
  - `ledger_missing_consistency_gate_pass=true`
  - `abstract_judgment_gate_pass=true`
  - `answer_vs_judgment_plan_gate_pass=true`
  - `ledger_unit_gate_pass=true`
  - `qwen_answer_ratio=1.0`
  - `qwen_ledger_repaired=0`
  - `fallback_answered=0`

当前决策：

- reviewed10 + 2 trap 是当前 case-filtered diagnostic baseline。
- 这仍然不是 full noisy benchmark 通过；下一步必须扩 reviewed gold set 来测泛化。
- table schema 的经验应沿用到后续 table cases：模型只输出 compact id/status，canonical cells 由 ledger 扩展。

## 2026-05-19 下一批 Gold Case 扩展建议

下一轮不建议只加同类 numeric extraction；应覆盖 reviewed10 没充分验证的四类风险。

优先 case：

1. `SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001`
   - 来源：`expanded_insight_ai_semiconductor_durability_2023_2025`
   - 公司：NVDA / AMD
   - 目的：验证 Judgment Plan 对新 peer set、新公司 AMD、强增长与风险 counter-evidence 的泛化。
   - 重点 gate：不能只写 NVIDIA；不能把 risk factor 当已发生事实；必须说明 NVIDIA/AMD segment label 不可直接等同。

2. `CAPEX_FCF_TABLE_2023_2025_DIAG_001`
   - 来源：`expanded_metric_capex_fcf_table_2023_2025`
   - 公司：MSFT / GOOGL / META / AMZN
   - 目的：验证 table-cell contract 是否能处理 OCF、PP&E/capex、derived FCF proxy 和符号方向。
   - 重点 gate：不能用 total investing cash flow 代替 capex；计算 FCF proxy 必须同时引用 OCF 与 capex inputs。

3. `SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001`
   - 来源：`expanded_insight_subscription_visibility_2023_2025`
   - 公司：ADBE / SNOW / PANW
   - 目的：验证 SaaS/security revenue visibility 口径：ARR、RPO、billings、deferred revenue、consumption model 不可互相替换。
   - 重点 gate：Snowflake consumption caveat、PANW billings/RPO/deferred revenue 定义、Adobe ARR/RPO exclusion/cancellation caveat。

4. `ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001`
   - 来源：`expanded_insight_ads_ai_infra_2023_2025`
   - 公司：GOOGL / META
   - 目的：验证广告恢复、AI infrastructure capex、operating leverage 的综合判断。
   - 重点 gate：不能把所有 technical infrastructure capex 归因到 ads；不能声称 AI 直接驱动广告增长，除非 SEC evidence 明确支持。

执行顺序建议：

- 先做 `SEMICONDUCTOR_DURABILITY` 与 `CAPEX_FCF_TABLE`：一个检验 Judgment Plan 泛化，一个检验 table-cell/derived-cell contract 泛化。
- 再做 `SUBSCRIPTION_VISIBILITY_COMPARISON`：它能复用现有 ADBE/SNOW/PANW context，但会测试更复杂的 metric-definition caveat。
- `ADS_AI_INFRA_GROWTH_QUALITY` 放第四个，适合作为 L4 judgment/rubric 泛化 case。

治理门槛：

- 每个新增 case 先进入 `seed_needs_review`，不能直接进入 approved reviewed set。
- Reviewed facts/context 完成后，先跑 gold gate、ledger-unit gate、context-only smoke。
- 只有前两步通过，才跑 pipeline trace、true-Qwen synthesis、post-gates。
- 若新增 case 需要 new validator，例如 derived FCF proxy gate 或 NA-definition gate，应先补 validator，再跑云端 true-Qwen。

## 2026-05-19 v1.1 Gold Expansion Seed Scaffold

已按上面的优先级创建独立 expansion case 文件，保持 `test_cases_v1.jsonl` 作为 reviewed10 baseline 不变：

- `eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl`

包含 4 个 L4 seed-only case：

- `SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001`
- `CAPEX_FCF_TABLE_2023_2025_DIAG_001`
- `SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001`
- `ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001`

Seed 生成结果：

- report: `reports/quality/sec_benchmark_v1_1_gold_expansion_seed_report.json`
- `case_count=4`
- `created_count=4`
- `context_row_count=526`
- `fact_row_count=208`

Per-case seed size：

- Semiconductor durability: 83 context rows / 29 fact candidates
- Capex/FCF table: 222 context rows / 120 fact candidates
- Subscription visibility comparison: 121 context rows / 37 fact candidates
- Ads/AI infra growth quality: 100 context rows / 22 fact candidates

Readiness / source-index smoke：

- report: `reports/quality/sec_benchmark_v1_1_gold_expansion_readiness.json`
- `pass_count=4`
- `fail_count=0`
- `hard_failure_types={}`
- `warning_types={}`

重要边界：

- 这些仍是 `seed_needs_review`，不能进入 reviewed approval。
- 本轮没有跑 true-Qwen、gold gate、ledger rebuild 或 post-gates。
- 下一步建议先 review 两个 case：
  - `SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001`：测 Judgment Plan 泛化。
  - `CAPEX_FCF_TABLE_2023_2025_DIAG_001`：测 table-cell + derived FCF proxy 泛化。

## 2026-05-19 RTX 5090 Corrected Profile Smoke

本轮在用户更换到 RTX 5090 32GB 云端后，先修正 vLLM Blackwell 运行方式，再跑 reviewed10 单 case smoke。

关键结论：

- 不能用 `python -O` / `PYTHONOPTIMIZE=1` 作为 5090 vLLM 入口 workaround。它会禁用 vLLM 的 Python asserts，导致 Qwen3.5 hybrid KV-cache grouping 被错误合并，生成阶段暴露为 `MambaSpec` / full-attention backend mismatch。
- 正确方式是在保持 Python asserts 的情况下使用 `TORCHDYNAMO_DISABLE=1` 绕过 torch inductor duplicate-template import bug，并暂时设置 `VLLM_USE_FLASHINFER_SAMPLER=0`。
- `configs/vllm_hardware_profiles.json` 已保留 `rtx4090_24gb`，新增/修正 `rtx5090_32gb` profile-level runtime env。

已跑 smoke：

- trace: `eval/sec_cases/outputs/run_20260519_revenue_income_cfo_pipeline_context_traces_top20_5090`
- Qwen output: `eval/sec_cases/outputs/run_20260519_revenue_income_cfo_pipeline_qwen9b_vllm_structured_6000_table_metricids_5090_torchdynamo_off`
- gates: `reports/quality/cloud5090_reviewed10_revenue_table_pipeline_qwen9b_post_gates_torchdynamo_off/sec_benchmark_post_gates_summary.json`
- ledger: `reports/model_runs/20260519_sec_benchmark_reviewed10_5090_table_smoke.md`

结果：

- `answer_status_counts={"answered_qwen9b":1}`
- profile applied runtime env: `TORCHDYNAMO_DISABLE=1`, `VLLM_USE_FLASHINFER_SAMPLER=0`
- `total_elapsed_sec=124.4674`, `load_model_sec=31.9281`
- single-case gates passed: answer ledger、metric-role、table-cell、named-fact、ledger-missing consistency、abstract judgment skip/pass、ledger-unit
- table-cell: 48/48 valid
- ledger-unit: 98/98 pass
- `qwen_answer_ratio=1.0`, `qwen_ledger_repaired=0`, `fallback_answered=0`

边界：

- 这是 5090 hardware/profile single-case smoke，不是 5090 full reviewed10 + 2 trap bundle。
- Trap、gold-vs-pipeline、answer-vs-Judgment-Plan gates 本轮故意跳过。
- 下一步仍应回到 Answer Plan 下面做 reviewed-gold expansion/generalization；不要把这次 5090 smoke 当 full noisy benchmark。

## 2026-05-19 v1.1 Reviewed2 Gold Expansion Gates

本轮把 v1.1 seed expansion 中的前两个 case 收成独立 reviewed-gold artifacts，保持 reviewed10 v1 baseline 不变：

- `SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001`
- `CAPEX_FCF_TABLE_2023_2025_DIAG_001`

新增/更新的脚本：

- `scripts/build_sec_benchmark_v1_1_reviewed_gold.py`
  - 为两个 case 生成 reviewed context、reviewed facts 和 v1.1 partial approval。
  - 不改 `eval/sec_cases/test_cases_v1.jsonl`，也不覆盖 v1 reviewed10 approval。
- `scripts/validate_sec_benchmark_derived_metrics.py`
  - 新增 FCF proxy 派生公式 gate。
  - 当前公式：`free_cash_flow_proxy = cash_flow.total_value + capex_or_ppe_purchases.total_value`。
  - 这里 capex/PPE purchases 按 SEC cash-flow table 的负向现金流表示。

主要产物：

- partial approval: `reports/quality/sec_benchmark_v1_1_reviewed_gold_partial_approval.json`
- gold gate: `reports/quality/sec_benchmark_v1_1_gold_gate_reviewed2_semiconductor_capex.json`
- exact ledger: `reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json`
- ledger unit gate: `reports/quality/sec_benchmark_v1_1_reviewed2_ledger_unit_gate.json`
- derived metric gate: `reports/quality/sec_benchmark_v1_1_reviewed2_derived_metric_gate.json`
- model run ledger: `reports/model_runs/20260519_sec_benchmark_v1_1_reviewed2_gold_gates.md`

Reviewed 内容：

- Semiconductor durability:
  - 17 reviewed context rows。
  - 6 facts。
  - NVIDIA 使用 `Compute & Networking` revenue 作为 Data Center 相关 proxy，必须保留和 AMD `Data Center net revenue` 不完全同口径的 caveat。
  - 同时保留 AI demand、Hopper/Blackwell transition、customer concentration、export controls、supply constraints 等风险上下文。
- CAPEX/FCF table:
  - 41 reviewed context rows。
  - 36 facts。
  - 24 个 reported input facts：OCF 与 PP&E purchases/capex cash outflow。
  - 12 个 deterministic FCF proxy facts：按 OCF 加负向 capex/PPE cash outflow 计算。

Gate 结果：

- Gold gate:
  - `can_enter_gate=true`
  - `case_count=2`
  - `status_counts={"pass":2}`
  - `overall_blocker_count=0`
- Exact ledger:
  - `approved_case_count=2`
  - `row_count=42`
- Ledger unit gate:
  - `can_enter_gate=true`
  - `ledger_row_count=42`
  - `pass_count=42`
  - `fail_count=0`
- Derived metric gate:
  - `can_enter_gate=true`
  - `derived_row_count=12`
  - `pass_count=12`
  - `fail_count=0`

当前决策：

- 这两个 case 可以进入 case-filtered pipeline-context true-Qwen smoke。
- 这不是 full noisy benchmark，也不是 retrieval/pipeline 泛化结论；本轮没有跑 true-Qwen、post-gates、trap bundle。
- v1.1 partial approval 明确阻止 full mainline scored test，只允许这两个 case 做 case-filtered smoke。

下一步建议：

- 先跑这两个 v1.1 reviewed cases 的 pipeline trace + true-Qwen + post-gates。
- 如果 pipeline 能稳定回答且 gates 过，再继续 review `SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001`。
- `ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001` 适合作为第四个 L4 judgment/rubric 泛化 case。

## 2026-05-19 v2 Generalization Design Absorbed

用户提供的 v2 generalization gold set 设计已吸收到项目内评测文档：

- `docs/eval/sec_benchmark_v2_generalization_plan.md`

吸收后的项目决策：

- v2 的长期目标仍是 40 个高质量泛化 case，但当前不直接一次性创建 40 个 reviewed cases。
- v2 设计先作为下一轮 gold-set expansion 的规范，核心要求包括：
  - numeric case 必须 cell-level reviewed gold；
  - text context 标注 `core/support/caveat`；
  - synthesis case 必须有 `required_caveats` 和 `disallowed_claims`；
  - peer comparison 默认 2 家公司，最多 3 家；
  - trap/not-found case 专测 source policy；
  - proxy、不可比口径、弱证据强结论必须能被 gate 捕获。
- 项目内 schema 继续优先沿用现有 runner 兼容字段：`case_id`、`evaluation_modes`、`source_policy`、`gold_context_status`、`numeric_checks.metric_families`、`numeric_checks.metric_roles`。
- 外部设计中的 `id/modes` 等字段暂不直接替换当前 runner schema；未来若要引入，先写 deterministic migration。

v2 pilot 建议：

- 先做 6-8 个 pilot，不直接做 full 40：
  - 2 个 L2 single-company summary；
  - 1 个 L3 cross-year trend；
  - 1 个 numeric/table cell；
  - 1 个 L4 peer comparison；
  - 1 个 trap/source-policy。
- 优先候选：
  - `META_REALITY_LABS_2024_001`
  - `PANW_RPO_BILLINGS_NUMERIC_2023_2025_001`
  - `GOOGL_META_ADS_REGULATION_PRIVACY_2023_2025_001`
  - `MSFT_YOUTUBE_REVENUE_TRAP_001`

新增 validator 待办：

- `required_caveats` coverage gate。
- `disallowed_claims` violation gate。
- `core/support/caveat` text context role bounds。
- peer entity-separation gate。
- proxy-as-direct metric gate。
- non-comparable metric comparison gate。
- prior-period / percentage-change target-value gate。
- trap source-policy / wrong-attribution gate。

执行顺序不变：

1. 先跑当前 v1.1 reviewed2 的 pipeline-context true-Qwen + post-gates。
2. 再根据结果决定是否 review 余下两个 v1.1 seed cases。
3. v2 pilot 在上述边界稳定后开始，不抢当前 pipeline smoke 的位置。

## 2026-05-19 v1.1 reviewed2 BGE-Reranked Pipeline Smoke

用户指出当前 pipeline 仍在用 BM25，而不是前面已经测过效果更好的 BGE/Qwen reranker 线。本轮复核后确认：

- 旧 runner 的 `pipeline_context` 仍以 BM25/ObjectBM25 排序进入 prompt pack。
- 前期 BGE/Qwen reranker 线已在 `reports/model_runs/20260516_phase2_object_reranker_baseline_compare.md` 记录过，BGE reranker v2 m3 是当时对象 rerank 最强 baseline。
- 这条线之前没有被否定；实际问题是 reviewed SEC benchmark runner 后续推进 gate/prompt/table contract 时没有把 BGE reranker 接进当前 pipeline-context 路径。

本轮修正：

- `scripts/run_sec_benchmark_eval.py`
  - 新增 `--context-reranker bge` 及模型、设备、batch、doc length、candidate limit、top-k 参数。
  - BM25/ObjectBM25 只作为 first-stage candidate generator。
  - BGE cross-encoder 负责最终 context row 排序和 prompt pack 选择。
  - structured object row 现在使用 `structured_object_search_text(record)` 作为 reranker 文本，避免只喂短 preview。
  - 增加 requirement-query candidate 扩展，用于把 gold points / traps / task-specific phrasing 变成候选池召回补充；它不是最终排序器。
- `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`
  - 表格 case schema 判断改为复用 Qwen backend 的 cell-table hard gate 逻辑。
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - 将 CAPEX/FCF table case 纳入 cell-table 输出契约。
  - 对表格型 case 增加 prose canonicalization：公司、年份、数值、引用只由 `cell_table.cells` 承载，summary/driver/key_points 不再枚举多家公司名，避免 named-fact gate 因“同一 driver 混合多个公司但只绑定部分 evidence/metric”失败。
  - 扩展 semiconductor high-value caveat 关键词，包括 customer concentration、10% customer、supply constraints、export controls、Hopper/Blackwell 等。

主要运行：

- BGE trace:
  - `eval/sec_cases/outputs/run_20260519_v1_1_reviewed2_pipeline_context_bge_top120`
  - 2/2 case `context_prepared`
  - 每个 case 120 条 context rows，全部带 reranker metadata。
  - semiconductor trace 命中旧 BM25 prompt pack 缺失的关键 customer-concentration/context sources：
    - `AMD_2025_10K_ITEM8_BLOCK_0005_PART_01_OF_02`
    - `NVDA_2025_10K_ITEM7_BLOCK_0008_CHUNK_0001`
- RTX 5090 true-Qwen synthesis:
  - `eval/sec_cases/outputs/run_20260519_v1_1_reviewed2_pipeline_bge_qwen9b_vllm_5090_tableprompt3`
  - `answer_status_counts={"answered_qwen9b":2}`
  - no ledger repair, no fallback.
- Post-gates:
  - `reports/quality/local_v1_1_reviewed2_pipeline_bge_qwen9b_5090_tableprompt3_post_gates/sec_benchmark_post_gates_summary.json`
  - `qwen_answer_ratio=1.0`
  - `answer_ledger_gate_pass=true`
  - `metric_role_term_gate_pass=true`
  - `table_cell_gate_pass=true`, `expected_cell_count=36`, `reported_cell_count=36`, `valid_cell_count=36`
  - `named_fact_gate_pass=true`, `unsupported_token_count=0`
  - `ledger_missing_consistency_gate_pass=true`
  - `ledger_unit_gate_pass=true`, `pass_count=42/42`
  - `abstract_judgment_gate_pass=true` but 2/2 skipped because v1.1 reviewed2 cases 尚无 abstract rubric。
- CAPEX/FCF derived metric gate:
  - `reports/quality/local_v1_1_reviewed2_pipeline_bge_qwen9b_5090_tableprompt3_post_gates/sec_benchmark_derived_metric_gate.json`
  - `derived_row_count=12`
  - `pass_count=12`
  - `fail_count=0`

当前决策：

- BGE reranker 线恢复为 SEC benchmark pipeline-context 的主选择器：BM25 只负责候选召回，不再代表最终排序/pack。
- v1.1 reviewed2 两个 case 的 BGE-reranked pipeline true-Qwen smoke 可以收为 diagnostic-only pass。
- 这仍不是 full noisy benchmark，也不是泛化结论；它只说明 BGE-reranked path 在当前两个 reviewed v1.1 case 上满足 gate。

模型运行记录：

- `reports/model_runs/20260519_sec_benchmark_v1_1_reviewed2_bge_pipeline_5090.md`

下一步建议：

- 继续 review v1.1 剩余两个 seed case 中至少一个：
  - `SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001`
  - `ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001`
- 在扩 case 前先补 v2 要求的 validator 中最关键的两个：
  - `required_caveats` coverage gate。
  - `disallowed_claims` violation gate。
