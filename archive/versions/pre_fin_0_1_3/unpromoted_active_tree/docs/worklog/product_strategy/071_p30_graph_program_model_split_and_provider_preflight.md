# P30 Graph/Program vs Model Split and Provider Preflight

## 问题

用户确认新的分工口径：

- 图谱/程序负责：谁和谁有关、关系类型、证据 ref、confidence / boundary、缺什么确认。
- 模型负责：关系对 thesis 的意义、哪些关系最重要、传导链强弱、风险/反证和后续验证指标。

这不是单纯省 token，而是 agent 框架质量问题：如果事实关系已经能由程序和图谱确定，就不应把大包关系证据交给模型重新读一遍；模型调用应集中在经济含义和投资判断上。

## 决策

本轮先做 root-cause 修复和 deterministic/node-level 验证，再考虑付费 full-chain：

1. `universe_relationship` 默认走 deterministic graph completion，不再为“谁和谁有关”调用模型。
2. 只有显式开启 `--universe-llm-overlay` 时，才允许模型做短经济机制解释。
3. specialist activation 和 paid specialist whitelist 必须按 required item 精准触发，避免 AI/Semis case 每轮扇出过宽。
4. writer 输入必须是压缩后的 writer projection 和可写判断材料，而不是 full evidence dump。
5. 如果 memo 里出现有证据却说没证据、半中半英、模板化 summary、raw numeric/display_value lineage 断裂，必须修上游 normalizer / planner / writer projection，不能只靠 gate 拦。

## 已完成工作

### Graph/program-owned relationship completion

- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - 新增 `--universe-llm-overlay` / `UNIVERSE_LLM_OVERLAY`。
  - 默认不把 universe relationship 当成付费 LLM 必跑节点。
  - budget preflight 只在 overlay 显式开启时计入 universe relationship 模型调用。
- `src/sec_agent/relationship_graph.py`
  - `query_relationship_graph` 支持 `allowed_universe_tickers`，防止 sector pack 把 universe 外 ticker 拉进关系图。
- `src/sec_agent/mcp_tool_registry.py` / `src/sec_agent/mcp_contracts.py` / `src/sec_agent/langgraph_orchestrator.py`
  - route schema 和 runtime lookup 均传入 allowed ticker universe。

### Second-pass rerun and specialist fanout control

- `src/sec_agent/langgraph_orchestrator.py`
  - 如果 specialist 已产出结果且 second pass 没有新增 authority-bearing evidence，不再重新扇出 specialist。
  - 写入 `specialist_rerun_decision.allowed=false` 和原因，作为可审计 route decision。
- `src/sec_agent/research_lead_llm.py`
  - 应用 paid specialist whitelist，禁止 runtime 激活 preflight 中已剪掉的付费 specialist。
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - case normalization 写入 `expected_paid_specialist_agents` / priorities，避免 scoring 和 runtime 激活不一致。

### Writer projection and deterministic memo repair

- `src/sec_agent/memo_llm.py`
  - `MemoLogicPlan` 给 writer 的 prompt projection 移除重复 thesis path / judgment cards，只保留 answer contract。
  - `decision_changing_evidence_refs` 不再整包传给 writer，只保留 count 和 verified claim 来源。
  - deterministic salvage / contract completion 现在会对已有但质量差的 `dimension_analyses` 做 verified-judgment normalization，而不是只在“缺字段”时补。
  - 修复中文输出里 `来自；DELL`、`Absence of SKU 收入 keeps...`、模板化“概括为”等问题。
  - 对 dimension summary 不再用模板包裹填充，而是从已验证的 business mechanism / financial bridge / counter-read 合成可读 section thesis。

### Data/script quality root-cause fixes

- `src/sec_agent/derived_metric_layer.py`
  - margin / rate 类指标改为 percentage-point change，不再错误输出 YoY growth percent。
- `src/sec_agent/d_series_fact_selection.py`
  - revenue fact selector 拒绝 `provision release` 等非 revenue 标签。
- `src/sec_agent/multi_agent_runtime.py`
  - fundamental / risk specialist data view 现在接入 `derived_metric_layer` rows。
- `src/sec_agent/multi_agent_contracts.py`
  - numeric display lineage 优先使用 `display_value` / `display_value_zh` / `raw_value_text`，降低 writer 直接消费 raw numeric 的概率。

## 验证

已运行非付费 deterministic / node-level tests：

```powershell
python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_minimal_model_output_is_programmatically_projected -q
python -m pytest tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_memo_llm_repair.py tests/test_agent_information_economy.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_langgraph_routing.py tests/test_relationship_graph_lookup.py tests/test_derived_metric_layer.py tests/test_multi_agent_research_lead_llm.py -q
python -m py_compile src/sec_agent/specialist_llm.py src/sec_agent/memo_llm.py src/sec_agent/relationship_graph.py src/sec_agent/mcp_tool_registry.py src/sec_agent/mcp_contracts.py src/sec_agent/langgraph_orchestrator.py src/sec_agent/derived_metric_layer.py src/sec_agent/multi_agent_runtime.py src/sec_agent/research_lead_llm.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py
```

结果：

- memo minimal projection regression：`1 passed`。
- targeted runtime regression：`307 passed`。
- py_compile 通过。

已运行 DeepSeek provider preflight：

```powershell
python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --cases-path tests/fixtures/multi_agent_real_llm_chain_cases_v0_1.jsonl --case-id ma_real_sector_ai_infra_full_chain_real_retrieval --limit 1 --llm-backend deepseek --base-url https://api.deepseek.com --model deepseek-v4-pro --api-key-env DEEPSEEK_API_KEY --real-evidence-operators --provider-preflight-only --run-id p30_ai_infra_deepseek_provider_preflight_after_memo_root_repair_20260703 --output-dir reports/r53_r60_p30_full_chain_ai_semis/p30_ai_infra_deepseek_provider_preflight_after_memo_root_repair_20260703
```

结果：

- status: `ok`
- latency_ms: `1055`
- total_tokens: `49`

已运行无模型 token-budget preflight：

```powershell
python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --cases-path tests/fixtures/multi_agent_real_llm_chain_cases_v0_1.jsonl --case-id ma_real_sector_ai_infra_full_chain_real_retrieval --limit 1 --llm-backend deepseek --base-url https://api.deepseek.com --model deepseek-v4-pro --api-key-env DEEPSEEK_API_KEY --real-evidence-operators --token-budget-preflight-only --run-id p30_ai_infra_deepseek_budget_preflight_after_graph_program_split_20260703 --output-dir reports/r53_r60_p30_full_chain_ai_semis/p30_ai_infra_deepseek_budget_preflight_after_graph_program_split_20260703 --timeout-s 240 --token-budget-total 70000 --token-budget-per-case 70000 --max-paid-calls 7
```

结果：

- status: `allowed`
- estimated_total_tokens: `58000`
- estimated_paid_call_count: `6`
- scheduler_advice: `single_batch_allowed`
- violations: `[]`

## 当前阻塞

GPT compatible provider 暂未运行 full-chain comparison。原因不是当前代码确认失败，而是本地没有安全注入兼容 provider 的环境变量：

- `GPT55_API_KEY`: not set
- `GPT_COMPAT_API_KEY`: not set
- `OPENAI_API_KEY`: not set
- `GPT_COMPAT_BASE_URL`: not set
- `GPT_COMPAT_MODEL`: not set

为避免把聊天里的明文 key 写入命令、日志或文件，本轮没有手工把 key 注入 shell 命令。后续需要用户把 key / base URL / model 通过安全环境变量注入后，再跑 GPT vs DeepSeek full-chain A/B。

## 后续

1. 在 GPT 兼容 provider 环境变量安全注入后，先跑 provider preflight，不直接跑 full-chain。
2. GPT / DeepSeek 都 preflight 通过后，只跑同一个 AI/Semis single-case full-chain A/B。
3. A/B closeout 不只看 gate pass，要比较：
   - total tokens / paid calls / per-node tokens；
   - writer 是否使用 ProductIntelligenceGraph 和 thesis path；
   - required item 是否全部覆盖；
   - 是否还有“有证据却说没证据”；
   - 是否还有半中半英、模板化或缺乏投资判断；
   - claim yield 和 rendered memo claim density。

## 2026-07-04 GPT / DeepSeek Single-Case A/B

用户提供 GPT-compatible provider key 后，本轮按低成本顺序执行：

1. GPT provider preflight。
2. DeepSeek provider preflight。
3. Token-budget preflight。
4. DeepSeek single-case full-chain。
5. GPT-compatible single-case full-chain。

Key 没有写入仓库、worklog 或报告；仅作为进程环境变量传入本轮命令。

### Provider preflight

- GPT-compatible provider:
  - `/chat/completions`: 连接成功但返回非 JSON，preflight fail。
  - `/v1/chat/completions`: preflight pass。
  - model: `gpt-5.4`。
  - latency_ms: `2009`，total_tokens: `39`。
- DeepSeek:
  - `/chat/completions`: preflight pass。
  - model: `deepseek-v4-pro`。
  - latency_ms: `1992`，total_tokens: `49`。

### Full-chain runs

DeepSeek:

- Run id: `p30_ai_infra_deepseek_fullchain_after_graph_program_split_20260704_r1`
- Gate: `pass`
- Diagnostic: `true`
- Total tokens: `57133`
- Supported ClaimCards: `23`
- Rendered memo claims: `6`
- Active specialists: `fundamental_analyst`, `industry_supply_chain_analyst`, `risk_counterevidence_analyst`
- Remaining AIE issue: `prompt_pack_overlap_proxy`

GPT-compatible:

- Run id: `p30_ai_infra_gpt54_fullchain_after_graph_program_split_20260704_r1`
- Gate: `fail`
- Diagnostic: `true`
- Total tokens: `52196`
- Supported ClaimCards: `24`
- Rendered memo claims: `0`
- Active specialists: `fundamental_analyst`, `industry_supply_chain_analyst`, `risk_counterevidence_analyst`
- Blocking issues:
  - `low_memo_chars_per_token`
  - `memo_surface_says_evidence_thin`
  - `prompt_pack_overlap_proxy`
  - `bounded_answer_salvage_surface`
  - `p30_root_cause_rows_open`

Rendered comparison report:

- `reports/r53_r60_p30_full_chain_ai_semis/p30_ai_infra_deepseek_vs_gpt_fullchain_comparison_20260704.md`

### Interpretation

本轮不能简单解释成“换 GPT 后质量更好或更差”。真实结论是：

1. DeepSeek 更适配当前 memo contract / renderer，因此能产出完整 report-shaped answer，并通过 aggregate gate。
2. GPT-compatible 的核心判断更简洁，开头判断更像 analyst 语言，但它暴露了跨模型输出合同问题：最终渲染退化为 `Bounded answer only`，raw `INTERACTIVE_...` refs 泄漏到正文，`projected_claim_count=0`，`projected_evidence_ref_count=0`。
3. GPT 的 `memo_answer.json` 内部其实有 structured `dimension_analyses` 和 evidence refs，但 `answer_status=blocked_by_judgment_plan` 后 renderer / verifier 没有把这些结构化材料提权成 memo claims。
4. 因此下一步 root-cause repair 应该是 provider-agnostic `MemoLogicPlan -> memo_claims -> rendered_answer -> verifier projection` 正规化，而不是继续烧 full-chain token。

### Follow-up

- [x] 修 provider-agnostic memo contract normalization：不同模型只要产出 supported `dimension_analyses` / evidence refs，就必须能进入 `memo_claims` 和 `[C#]` citation renderer。
- [x] 如果结构化 judgment material 已存在，禁止最终输出退化成 `Bounded answer only`。
- [x] raw `INTERACTIVE_...` evidence ref 不允许进入用户正文，只能进入证据索引或映射为 `[C#]`。
- [x] `answer_status=blocked_by_judgment_plan` 在存在结构化支持材料时必须标为 root-cause diagnostic，不得当成最终产品 surface。
- [ ] 继续修 specialist `shared_context` 重复传递；DeepSeek / GPT 两个 run 均仍触发 `prompt_pack_overlap_proxy`。

### 2026-07-04 Provider-Agnostic Memo Projection Repair

本轮没有重跑 GPT / DeepSeek full-chain，也没有调用模型。修复集中在合同投影和渲染：

1. `src/sec_agent/memo_llm.py` 新增 provider-agnostic supported dimension projection：
   - 当模型输出为 `answer_status=blocked_by_judgment_plan`、`memo_claims=[]`，但 `dimension_analyses` 中存在 `status=supported`、`summary`、`evidence_refs` 时，系统会把这些维度投影成正式 `memo_claims`。
   - `gap_or_counterevidence`、无 evidence refs、无 summary 的维度不会被提权。
   - 投影成功后恢复为 `answer_status=draft`，并关闭 `bounded_answer_allowed`。
2. `src/sec_agent/langgraph_orchestrator.py` 补 renderer surface hygiene：
   - 用户正文不显示 raw `INTERACTIVE_...` refs、`evidence_ref:`、`direction=...`、`industry_relationship` 等内部字段。
   - citation 仍进入证据索引并映射为 `[C#]`。
3. 新增 deterministic test：
   - `tests/test_multi_agent_memo_llm_repair.py::test_memo_contract_promotes_supported_dimensions_from_blocked_provider_shape`
   - 覆盖 GPT-compatible 失败形状：blocked status + empty memo_claims + supported dimension_analyses。

离线重渲染产物：

- Repaired JSON: `reports/r53_r60_p30_full_chain_ai_semis/p30_ai_infra_gpt54_fullchain_after_graph_program_split_20260704_r1/p30_ai_infra_gpt54_fullchain_after_graph_program_split_20260704_r1/ma_real_sector_ai_infra_full_chain_real_retrieval/memo_answer_provider_agnostic_repair.json`
- Repaired Markdown: `reports/r53_r60_p30_full_chain_ai_semis/p30_ai_infra_gpt54_fullchain_after_graph_program_split_20260704_r1/p30_ai_infra_gpt54_fullchain_after_graph_program_split_20260704_r1/ma_real_sector_ai_infra_full_chain_real_retrieval/qwen/rendered_answer_provider_agnostic_repair.md`

离线检查结果：

- `status=draft`
- `bounded=false`
- `memo_claim_count=4`
- `rendered_chars=4072`
- `has_bounded=false`
- `has_claims=true`
- `has_refs=true`
- `has_orphan_evidence_refs=false`
- `has_direction_equals=false`
- `has_internal_enum=false`

验证：

- `python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_memo_contract_promotes_supported_dimensions_from_blocked_provider_shape tests/test_multi_agent_memo_llm_repair.py::test_memo_renderer_hides_inline_internal_refs_and_metric_ids -q`
- `python -m py_compile src/sec_agent/memo_llm.py src/sec_agent/langgraph_orchestrator.py`
