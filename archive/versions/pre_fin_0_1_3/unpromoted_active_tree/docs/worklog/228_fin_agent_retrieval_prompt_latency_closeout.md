# 228 Fin Agent 检索复用 / Prompt 压缩 / Latency 收口

## 背景

用户要求先做 BGE / 检索常驻复用、减少 route 数和二次冷启动、压 Research Lead prompt、再压 Memo Writer 输入，然后用多个行业、不同问题和不同维度 case 做真实链路测试并收口。

本轮延续 185/186 的 multi-agent 架构约束：Research Lead 只做激活和证据需求规划，Evidence Operators 真实触发 SEC BM25/ObjectBM25/BGE rerank，Specialist / Memo Writer 只能消费 bounded evidence，Verifier 保持安全门。

## 本轮实现

### 1. SEC search route coalescing

- 在 `multi_agent_runtime.py` 增加 SEC search route 分组执行：`filing_text`、`8k_commentary`、`risk_text`、`ledger_first` 进入同一 grouped SEC search execution。
- grouped 主 route 真实执行 `sec_search_filings`；member route 写入 `status="cached"` observation / ledger，不重复检索、不重复 BGE rerank。
- `tool_call_ledger.py` 的 executed / duplicate 计数排除 `cached`，避免 route 复用被误判为预算耗尽或重复调用。

### 2. Retrieval budget 和 Lead activation 收敛

- standard profile 默认预算降到更小的 real retrieval cap：`candidate_budget=180`、`rerank_budget=56`、`evidence_top_k=5`、`object_top_k=4`。
- 修复 `sector_depth_pack_path` 仅存在于上下文就把 standard case 误升级为 deep/relationship 的问题。
- Research Lead 对非 relationship query 增加激活归一化：只有显式 relationship / supply-chain / cross-entity transmission 意图才保留 `universe_relationship` 和 `relationship_graph`。
- standard investment memo 的 risk lens 更精细：风险/压力/证据缺口/valuation/market reaction 触发 Risk Specialist supporting，而不是粗暴全量激活或全量剪掉。

### 3. Research Lead 和 Memo Writer prompt 压缩

- Research Lead 使用 compact skill prompt、compact JSON source inventory、compact context，减少无关 registry / context payload。
- Research Lead 的 optional `evidence_requirement_plan` 验证失败不再强制 repair；当 activation 已合格且 evidence requirements 可 deterministic compile 时，降级为 warning + deterministic compiler。
- Memo Writer 改为消费 compact shared memo context 和 verified judgment/thesis pack，不再拉完整 raw rows。
- Memo Writer 中文输出增加 user-facing 合成约束，避免 ClaimCard / English wrapper / internal schema text 泄漏。

### 4. Focused bridge 数值和中文残句 guard

真实 LLY focused run 暴露两个输出层问题：

- ledger-first 候选可能把金额 metric 的 `percentage_rate` role 排在前面，导致 Memo Writer 把 revenue 写成百分比。
- numeric-fidelity 清洗删除未知数值后，中文 direct answer 可能残留 “营收为这些数据” 这类破句。

本轮修复：

- `multi_agent_contracts.py` 增加金额类 metric 与 rate role 兼容性判断；对 `revenue / product_revenue / rd_expense / capex / cash_flow / operating_income` 等金额指标，存在兼容金额行时过滤 `percentage_rate` 候选。
- focused ClaimCard 使用 `ledger_metric_display_value()`，金额类 metric 不接受 `% / 百分比率` 展示值。
- `langgraph_orchestrator.py` deterministic lookup 去重 key 加入 `metric_role` 和 `display_value_zh`，避免错误 percentage row 吞掉正确 total_value row。
- `memo_llm.py` 扩展中文 numeric-removal damaged sentence 检测，遇到 “营收为这些/数据/证据/披露” 等残句时回退到已验证 claim 生成的 safe direct answer。

## 真实运行结果

### Cross-sector closeout v0.7

- Run ID: `20260602_fin_agent_latency_retrieval_prompt_compaction_v0_7_cross_sector_closeout`
- Cases: healthcare LLY focused、consumer WMT/TGT standard、energy XOM/CVX standard。
- Result: `3/3 pass`，真实 retrieval，BGE CUDA metadata true。
- 延迟：LLY `96.7s`，WMT/TGT `140.2s`，XOM/CVX `140.9s`。
- 结论：route coalescing 生效；WMT/XOM standard memo 稳定到 `1` attempt；LLY focused 能给出 bounded answer，但 healthcare 外部临床/监管数据不在本地知识库，输出必须保守。

### Failed-case fix v0.6

- Run ID: `20260602_fin_agent_latency_retrieval_prompt_compaction_v0_6_failed_case_fix`
- Cases: energy XOM/CVX、AI/software MSFT/GOOGL。
- Result: `2/2 pass`。
- 修复点：energy 不再被 `sector_depth_pack_path` 误推成 deep relationship；MSFT/GOOGL 能正确保留 risk lens。

### Focused unit guard v0.9 / memo guard v0.10

- v0.9 修复 revenue 百分比漂移，但真实输出仍出现中文残句，标记 superseded。
- v0.10 Run ID: `20260602_fin_agent_latency_retrieval_prompt_compaction_v0_10_focused_memo_guard`
- Case: healthcare LLY focused。
- Result: `1/1 pass`，elapsed `113.8s`，tool calls `6`。
- Research Lead: `2` calls，`9260` tokens。
- Memo Writer: `1` attempt，`6273` tokens，rendered `1677` chars。
- SEC search: grouped route 真实执行一次，member routes cached；candidate generation `23ms`，BGE rerank `1139ms`，BGE device `cuda`，resource load `26581ms`。
- 输出质量：无 percentage drift、无 “营收为这些” 残句；但该 case 最终只形成毛利率锚点，正确声明研发投入 / 产品周期风险缺证，质量审计标记 `memo_surface_says_evidence_thin=1`。

## 当前链路表现

- Retrieval 层：真实 SEC search、BM25/ObjectBM25/BGE rerank 已跑通；route coalescing 明显减少同 case 内重复检索和 rerank。
- BGE：真实走 CUDA；但在单独 eval process 中仍有首个 case model/resource load，当前不是跨进程常驻服务。
- Research Lead：能做 cost-aware activation，standard case 不再粗暴 deep route；但真实 DeepSeek 仍常见 `2` calls，说明 activation-plan hard validation / repair 仍有优化空间。
- Evidence Operators：ledger store 接上后 candidate generation 从百秒级降到毫秒级；但 `sec_query_exact_value_ledger` 对部分 focused case row_count 仍偏高，需要后续做 metric-family / metric-role top-k 限制。
- Memo Writer：token 已从早期 19K+ 降到 5K-10K 常见区间，standard case稳定 `1` attempt；但 focused / evidence-thin case 的 memo 仍更像 bounded answer，不是深度投研报告。
- Verifier：安全门有效，但主要是防乱写，不负责提升深度。

## 未关闭问题

1. Research Lead 仍常见 `2` calls；optional evidence requirement fallback 没完全消灭二次调用，后续应定位 activation-plan hard validation 的 repair 触发字段。
2. BGE “常驻复用”目前只做到同 process / 同 case route reuse；每次独立 eval 启动仍会加载 BGE。若要产品化，应做独立 retrieval worker 或长期运行的 in-process session runner。
3. Focused healthcare case 暴露本地数据覆盖边界：SEC/8-K 可支持财务锚点和风险披露，但无法证明临床、监管、专利周期等外源事实。
4. Memo 质量仍受 upstream ClaimCard 密度制约；standard case 已可生成有边界 memo，但距离高密度、深度投研报告还需要更好的 external data / relationship graph / thesis planning。
5. `sec_query_exact_value_ledger` 在部分 focused case 返回 rows 偏多，后续要按 metric_role、period_role、requested metric family 做更强 exact-value row selector。

## 验证

- `python -m compileall src/sec_agent/multi_agent_contracts.py src/sec_agent/langgraph_orchestrator.py`
- `python -m compileall src/sec_agent/memo_llm.py src/sec_agent/multi_agent_contracts.py src/sec_agent/langgraph_orchestrator.py`
- `pytest -q tests/test_multi_agent_contracts.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_memo_llm_repair.py` -> `62 passed`
- 真实 DeepSeek eval:
  - `20260602_fin_agent_latency_retrieval_prompt_compaction_v0_6_failed_case_fix` -> `2/2 pass`
  - `20260602_fin_agent_latency_retrieval_prompt_compaction_v0_7_cross_sector_closeout` -> `3/3 pass`
  - `20260602_fin_agent_latency_retrieval_prompt_compaction_v0_8_research_onepass_smoke` -> `2/2 pass`，但 LLY 输出暴露 revenue percentage drift，已被 v0.9/v0.10 supersede
  - `20260602_fin_agent_latency_retrieval_prompt_compaction_v0_10_focused_memo_guard` -> `1/1 pass`

## 安全说明

- 真实运行使用环境变量读取 runtime credential。
- 未保存 API key，未保存 raw LLM response。
- 本轮新增文档只记录 run id、metrics、路径和质量结论，不包含 secret。
