# SEC Agent Resume Closeout Eval v1

## 目标

这个评测集用于第一版投简历前的全链路收口，不是单点 smoke。它检查用户 query 进入系统后，从 Planner、source scope、retrieval、Exact-Value Ledger、Evidence Coverage Matrix、Judgment Plan、DeepSeek synthesis、deterministic gates、renderer、session/context/resume 的连续可靠性。

核心原则：

- 不把局部 smoke 当全链路质量结论。
- 不用兜底逻辑掩盖 planner、retrieval、coverage 或 synthesis 问题。
- 私有数据、云端模型输出、API key 不进入仓库；只记录路径、摘要和可复跑命令。

## 评测入口

本地聚合入口：

```powershell
python scripts/eval_context/evaluate_sec_agent_resume_closeout_readiness.py
```

默认输出到：

```text
reports/quality/resume_closeout/<timestamp>_resume_closeout_readiness_local_v1.json
```

该入口默认运行：

- `context_state_replay`
- `context_api_smoke`
- `context_managed_dispatch_replay`
- `tool_harness_dispatch_fixtures`
- source/period/market 相关 pytest
- local heuristic planner diagnostic
- local 10-K/latest 10-Q + market_snapshot main-chain smoke
- 多 case main-chain suite：full-source、broad scan、SEC-only negative control、8-K explanation、market valuation peer
- request-level ContextManager 小压测：默认 `40` requests / `4` concurrency
- local latency profile：BM25/ObjectBM25、candidate generation、market attach、ledger cache、coverage timing
- 可选 saved full-source DeepSeek run inspection

云端 full-source DeepSeek 跑完后，用下面形式把产物接入同一份评测：

```bash
python scripts/eval_context/evaluate_sec_agent_resume_closeout_readiness.py \
  --saved-full-source-run-dir /root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/<full_source_run>/<run_id> \
  --require-full-source-artifacts
```

`--require-full-source-artifacts` 会把缺少 10-K/latest 10-Q/8-K/market_snapshot 私有产物升级成 blocker；本地没有云端私有 8-K manifest 时，默认只标 warn/skipped。

## 多用例覆盖

主评测集：`eval_sets/sec_agent_resume_closeout_eval_v1.json`

Planner 诊断子集：`eval_sets/sec_agent_resume_closeout_planner_eval_v1.jsonl`

覆盖用例：

| case | 目的 |
| --- | --- |
| `closeout_full_source_ai_market_001` | full-source 投研 memo：SEC 10-K/latest 10-Q/8-K/market_snapshot 同时进入链路 |
| `closeout_full30_broad_scan_002` | broad universe scan：检查 planner 任务压缩、coverage 表达和证据边界 |
| `closeout_sec_only_cloud_003` | negative control：用户明确不要 market data 时不能污染 source scope |
| `closeout_8k_management_explanation_004` | 8-K 管理层解释：8-K 可解释但不能进入 audited ledger |
| `closeout_market_valuation_peer_005` | market snapshot/valuation：工具算市场视图，模型解释基本面和市场分歧 |
| `closeout_followup_context_006` | 多轮上下文：复用 active session/answer，避免重跑全链路 |
| `closeout_resume_partial_007` | 中断恢复：检查 next_ready_node、artifact_state 和 post-gates 一致性 |
| `closeout_cross_industry_full_source_008` | AI 以外的跨行业 full-source 稳定性 |
| `closeout_context_short_long_memory_009` | 短期 turn intent + 长期 artifact refs 的多轮记忆 |
| `closeout_small_pressure_010` | request-level ContextManager 小压测 |
| `closeout_release_public_scope_011` | 公开范围、demo 入口和不公开数据/密钥边界 |

## 维度标准

`source_inventory`：
full-source 环境必须有 10-K、latest 10-Q、8-K earnings release、market_snapshot。市场快照必须有 `snapshot_id`、`as_of_date`、价格/收益/回撤/波动/估值/事件窗口字段。

`planner_contract`：
Planner 必须输出可解析 JSON，选择正确 `filing_types`、`source_tiers`、`market_snapshot` 和 `market_analysis_tools`；不能把 market snapshot 当 SEC filing，不能把 8-K 当 audited ledger fact。

`retrieval_coverage_judgment`：
检索按 Query Contract 拉对应证据；ledger 保留 QTD/YTD/TTM/annual `period_role`；Coverage Matrix 和 Judgment Plan 只使用覆盖内证据。

`model_synthesis_post_gates`：
模型输出投研 memo，不输出裸 JSON；renderer 显式区分 SEC、8-K、market snapshot 边界；所有 deterministic gates 通过，且没有 fallback/repair 被当作正常模型输出。

`session_context` / `request_api_context` / `tool_call_dispatch_context_update`：
同一 session 可恢复，多 session 隔离，跨 user 拒绝；follow-up 能基于 active answer 调 artifact inspection；reformat 只 invalidate rendered answer。

`p0_performance_resource`：
提交前必须有非 LLM 环节耗时报告，至少覆盖 BM25/ObjectBM25、candidate generation、ledger cache、coverage。SLA 不达标时保留 warn/fail 和瓶颈字段。

`p0_stage_timing_observability`：
真实 full-source run 需要保存 stage-level timing、run performance、run data fingerprint；没有 saved run 时只能标 skipped/warn。

`p0_data_index_versioning`：
10-K/latest 10-Q/8-K/market snapshot/DuckDB/BM25/ObjectBM25 必须能追溯 manifest 或 snapshot 摘要；本地缺 full-source 私有产物时 readiness 报告不得静默通过。

`p0_state_consistency`：
JSON store 当前只证明 single-process request lock 小压测可行；多进程生产并发仍需 SQLite/Postgres/Redis/file-lock 事务化后再声明。

`p0_failure_recovery`：
fixture 已覆盖 partial artifact state 和 no-rerun follow-up；真实 stage-level resume 仍需要通过 saved cloud run 或专门 partial replay 验证。

## 当前解释方式

聚合报告的状态含义：

- `pass`: 该维度所有映射检查通过。
- `warn`: 诊断性检查失败、可选云端产物缺失，或 full-source 数据不在本地。
- `skipped`: 用户显式跳过，或需要的私有产物未提供。
- `fail`: critical check 失败，或提供的 saved full-source run 未通过 post-gates/coverage/renderer 基本检查。

第一版收口标准建议：

1. 本地 critical checks 必须 `pass`。
2. 至少一个云端 full-source DeepSeek run inspection 必须 `pass`。
3. broad scan、source negative control、8-K explanation、market valuation peer 四类用例至少各有一条真实运行记录。
4. 所有报告只记录路径和摘要，不记录 API key、密码或原始私有数据。

## 提交前建议命令

本地不依赖 API key 的收口检查：

```powershell
python scripts/eval_context/evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600
```

只跑较快的 contract/fixture 检查：

```powershell
python scripts/eval_context/evaluate_sec_agent_resume_closeout_readiness.py --skip-main-chain-case-suite --skip-context-load-smoke --skip-latency-profile
```

接入云端真实 full-source DeepSeek 产物：

```bash
python scripts/eval_context/evaluate_sec_agent_resume_closeout_readiness.py \
  --saved-full-source-run-dir /root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/<run>/<case> \
  --require-full-source-artifacts \
  --timeout-s 900
```
