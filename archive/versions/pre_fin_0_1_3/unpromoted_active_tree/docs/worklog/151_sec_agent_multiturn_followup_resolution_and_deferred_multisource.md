# SEC Agent 多轮信息链路收敛与多源扩展延期决策

## Prompt
- 用户希望先记录“后续扩充信息源”的方向，但当前不立刻扩源。
- 当前执行顺序调整为：先解决上一轮多轮 full-chain 暴露的问题，再补一轮 3-5 个非连续 follow-up 场景；只有效果通过后，再考虑 transcript、investor presentation 等多源扩展。

## Reasoning And Decision
- 多源扩展方向成立：SEC-only 会限制 insight 上限，尤其是管理层解释、前瞻口径、行业横向逻辑和时延/链路压力测试。
- 但当前主线还没有完全收敛：上一轮 real full-chain 虽然 `4/4` tool/dispatch/scope 通过，但 `explain_evidence` 对“第二条增长驱动”返回空 payload，说明自然语言 ordinal reference 没有稳定映射到 memo section。
- 另一个内容风险是 NVDA-only memo 的 post-gate 仍出现 `v2_semantic_contract_gate_pass=false`，失败类型为 `non_comparable_metric_comparison`。这说明链路通过不等于最终语义质量完全可靠。
- 因此多源扩展暂缓；当前阶段先把 session-aware harness、tool call、artifact replay、evidence explanation 和非连续 follow-up 稳住。

## Deferred Multi-Source Direction
- 后续优先源：
  - `earnings_transcript`：补管理层解释、Q&A、forward-looking commentary。
  - `investor_presentation` / `earnings_release`：补 KPI、业务口径、segment explanation。
- 暂不优先：
  - 普通 news、社媒、卖方研报、实时股价和 analyst consensus。
- 后续需要的 source policy：
  - SEC/XBRL 数值事实优先。
  - transcript/presentation 只能作为 management commentary 或 strategy commentary。
  - management commentary 不得被当成 reported financial fact。
  - SEC-only query 不能偷偷使用非 SEC source。
- 后续 gate：
  - 每条非 SEC claim 必须标注 `source_type`。
  - 数值类 claim 必须来自 SEC/XBRL，或明确标注非 SEC 来源和限制。
  - 冲突源需要做 source arbitration，不能只跟随管理层乐观口径。

## Current Acceptance Gate Before Expansion
- 修复 `explain_evidence`：
  - 支持 `decision_drivers`、`why_it_matters`、`what_changed`、`counterarguments`、`watch_items` 等 memo section 的 ordinal reference。
  - 支持“第二条增长驱动”“毛利率改善那条”“AMZN 广告业务增长那条”这类 claim reference。
  - 返回的 payload 不应为空；至少要包含匹配 section、item index、metric ids、evidence ids、ledger matches 或 judgment plan matches。
- 补 3-5 个非连续 follow-up 场景：
  - 已完成 session 的 evidence explanation。
  - 先 state check 再 evidence follow-up。
  - 跨用户 / 跨 session isolation。
  - source-boundary / latest / buy-sell 请求不能调用外部源。
  - partial/resume 后继续 evidence explanation。
- 通过标准：
  - controller tool routing 通过。
  - harness dispatch 通过。
  - no-rerun artifact inspection 不重跑 graph。
  - evidence explanation 不返回空 payload。
  - session/user state 不串。

## Work To Do Now
- 修复 harness 的 evidence target resolution。
- 扩充 fixture dispatch eval，覆盖 memo section-aware evidence explanation。
- 生成并运行 3-5 个非连续 follow-up 验证场景。
- 结果通过后再决定是否进入多源扩展设计。

## Work Completed
- 已修复 `src/sec_agent/tool_harness.py`：
  - `explain_evidence` 新增 `section`、`item_index`、`claim_reference` 可选参数。
  - evidence target resolution 现在会从 `decision_drivers`、`why_it_matters`、`what_changed`、`key_points`、`counterarguments`、`peer_readthrough`、`watch_items` 中解析目标项。
  - 当 `driver_index` 超过 `decision_drivers` 长度时，会按 memo section fallback，例如 `driver_index=2` 可解析到 `why_it_matters[2]`。
  - 支持“毛利率改善那条”“MSFT 云业务增长那条”“AMZN 广告业务增长那条”等自然语言 claim reference。
  - Judgment Plan matching 同时支持 `decision_drivers` 和 `drivers` 字段，避免真实 plan 结构下匹配为空。
- 已修复 `src/sec_agent/tool_controller.py`：
  - `explain_evidence` 路由会把 evidence 问句原文作为 `claim_reference` 注入 tool args，供 harness 做 topic-aware resolution。
- 已扩充 fixture eval：
  - `scripts/evaluate_sec_agent_tool_harness_dispatch_fixtures.py` 新增 section ordinal 和 claim reference 两个分发用例。
- 已新增非连续 follow-up 小套件：
  - `eval_sets/sec_agent_multiturn_noncontiguous_followup_eval_v1.json`
  - 覆盖 completed-session no-rerun inspection、session isolation、partial/resume 三类非连续场景。
- 已补一个窄的 semantic-gate 防线：
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py` 在答案存在趋势/比较语义但缺少可比性 caveat 时，向 `source_limitations` 补入“不同指标、公司或披露口径不可直接比较”的限制。
  - 目标是降低上一轮 `non_comparable_metric_comparison` 类失败的复发风险；该修复仍需下一次 cloud synthesis rerun 验证。

## Validation
- 语法检查：
  - `python -m py_compile src/sec_agent/tool_harness.py src/sec_agent/tool_controller.py scripts/evaluate_sec_agent_tool_harness_dispatch_fixtures.py`
  - 结果：通过。
- Fixture dispatch eval：
  - 输出：`reports/quality/local_tool_harness_dispatch_fixtures_section_aware_v1.json`
  - 结果：`7/7` 通过。
- 真实上一轮 artifact replay：
  - 输出：`reports/quality/local_real_artifact_explain_replay_section_aware_v1/real_artifact_explain_replay_summary.json`
  - 输入：上一轮 NVDA-only / 2024 t2 artifacts；仅调用 `explain_evidence`，不重跑 graph。
  - 结果：`driver_index=2` 成功解析到 `why_it_matters[2]`，返回 NVDA gross margin metric/evidence IDs，`ledger_match_count=1`，`judgment_plan_match_count=1`，`rerun_required=false`。
- Controller route eval：
  - 全量 reviewed route set 输出：`reports/quality/local_tool_controller_reviewed_v1_route_heuristic_section_aware_v1.json`
  - 结果：`18/18` tool pass，`18/18` arg pass。
  - 非连续 follow-up 小套件输出：`reports/quality/local_tool_controller_noncontiguous_followup_route_heuristic_section_aware_v1.json`
  - 结果：`3` scenarios / `11` turns，`11/11` tool pass，`11/11` arg pass。
- Semantic normalizer smoke：
  - `python -m py_compile scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - 结果：通过。
  - Inline smoke 确认趋势/变化文本会补入可比性 source limitation。
- Cloud DeepSeek r3/r4 validation:
  - r3 输出：`reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r3_section_aware_cu128/summary.json`
  - r3 结果：`4/4` tool pass，`4/4` dispatch pass，`all_pass=true`；NVDA-only post-gates 全部转绿，但 coverage 暴露了一个 planner/coverage 污染：非金融 NVDA scope 混入 `rate_sensitive_bank_metrics`，导致 `deposits/loans/net_interest_income` 出现在 missing metric families。
  - 已修复 `src/sec_agent/query_contract.py`：非银行/非金融 focus scope 会剔除银行专属 decomposed task 和 bank-specific metric families，避免 NVDA/semiconductor 场景被 banking metrics 污染。
  - r4 输出：`reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r4_nonbank_filter_cu128/summary.json`
  - r4 结果：`turn_count=4`，`tool_pass_count=4`，`dispatch_pass_count=4`，`failure_count=0`，`all_pass=true`，`elapsed_sec=405.771`。
  - r4 NVDA-only coverage：`coverage_complete=true`，`primary_task_support_complete=true`，`answer_status=complete`，`task_count=7`，`missing_metric_families=["semiconductor_solutions","subscription_revenue"]`，不再包含 banking metric families。
  - r4 post-gate replay：`answer_ledger`、`named_fact`、`v2_semantic_contract`、`answer_vs_judgment_plan`、`metric_source_grounding`、`ledger_unit`、`qwen_answer` 均通过。
  - 已修复 `scripts/validate_sec_benchmark_v2_semantic_contracts.py`：v2 semantic gate 的 `_answer_text` 现在读取 memo schema 的 `what_changed`、`why_it_matters`、`peer_readthrough`、`counterarguments`、`watch_items` 和 `source_limitations`，避免漏看 memo-only caveat。
  - r4 evidence replay：`reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r4_nonbank_filter_cu128/explain_evidence_recheck_v2.json` 显示“第二条增长驱动”解析到 `why_it_matters[2]`，返回 gross margin + operating cash flow metric ids、4 个 evidence ids、`ledger_match_count=3`、`judgment_plan_match_count=1`、`rerun_required=false`。

## Remaining Caveats
- 已重新跑云端 DeepSeek full-chain r3/r4；当前主验证通过。
- r4 原 graph-run stdout 中在 validator 修复前曾记录 `v2_semantic_contract_gate_pass=false`，原因是 gate 没读 memo `source_limitations`；修复 validator 后，已对同一 r4 输出重放 post-gates 并转绿。
- 多源扩展仍处于延期状态，不进入当前实现。

## 2026-05-23 Broad Non-Contiguous Suite
- 已把非连续 follow-up / session isolation / resume route suite 从 `3` scenarios / `11` turns 扩到 `6` scenarios / `23` turns：
  - 保留 completed-session no-rerun inspection、双 session isolation、partial resume。
  - 新增 reformat-only 场景，覆盖 style-only request 只应重写/记录 rendered output，不应重跑 retrieval/ledger/coverage/Judgment Plan。
  - 新增 AMZN/META -> NVDA 回切场景，覆盖跨 session 来回切换、显式“不要用刚才 NVDA/AMZN/META”的隔离约束，以及 latest/stock-price source-boundary 请求。
  - 新增 resume -> reformat -> explain_evidence -> get_session_state 场景，覆盖 partial resume 后继续非连续 follow-up。
- 已扩充 fixture dispatch eval：
  - 新增第二个 completed fixture session：`fixture_dispatch_completed_alt` / `fixture_ans_amzn_meta_2025`。
  - 新增 alt session state read、alt coverage read、AMZN advertising claim evidence resolution、alt wrong-user rejection。
  - Harness fixture case 从 `7/7` 扩到 `11/11`。
- 本地验证：
  - `python -m py_compile src/sec_agent/tool_harness.py src/sec_agent/tool_controller.py scripts/evaluate_sec_agent_tool_harness_dispatch_fixtures.py scripts/evaluate_sec_agent_tool_controller.py`：通过。
  - `reports/quality/local_tool_harness_dispatch_fixtures_broad_noncontiguous_v1.json`：`11/11` 通过。
  - `reports/quality/local_tool_controller_noncontiguous_followup_route_heuristic_broad_v1.json`：`6` scenarios / `23` turns，tool pass `23/23`，arg pass `23/23`。
- 云端验证：
  - `reports/quality/cloud_tool_harness_dispatch_fixtures_broad_noncontiguous_v1.json`：`11/11` 通过。
  - `reports/quality/cloud_tool_controller_noncontiguous_followup_route_deepseek_broad_v1.json`：DeepSeek route-only，`6` scenarios / `23` turns，tool pass `23/23`，arg pass `23/23`，`controller_status=routed` 为 `23/23`，没有 fallback。
- 这轮只验证 controller routing 和 harness fixture dispatch，不跑真实 DAG，不消耗 GPU。真实 full-chain 仍以 r4 scope-revision run 作为当前最新端到端证据。

## Safety Notes
- 本条记录不包含任何云端密码、API key 或临时凭证。
- 多源扩展是后续路线，不作为当前阶段的立即执行项。
