# Thread Handoff: P34 AI/Semis Fact-table Projection / Goldcase Availability Alignment

日期：2026-07-08

## 1. 当前目标

当前线程已经推进到 P34 AI/Semis 单 case 的 source-runtime / writer-payload 修复阶段。最新用户要求是：

> 先修复 parser/adapter row 仍是 summary、writer payload 没有财务/产品/部署/市场表格的问题；再基于当前 RAG 库和 source-route 可得性更新 AI/Semis goldcase；最后把质量评估体系更新成真正的全链路评估前置口径。在真正 full-chain eval 前，必须先返回结果让用户认可。

本线程最后完成的是：

- P34 scoped writer payload 新增 analyst-facing fact-table projection。
- AI/Semis goldcase 已按当前 RAG/SQL/Milvus/source-route 可得性重新校准。
- 只做 deterministic preview / alignment，没有跑 true full-chain、没有跑新的 paid LLM。

## 2. 新窗口启动必读

新窗口不要靠聊天记忆继续，先读以下文件：

1. `D:/FIN_Insight_Agent/docs/project_os/thread_handoff_20260708_p34_ai_semis_fact_table_alignment.zh-CN.md`
2. `D:/FIN_Insight_Agent/docs/project_os/current_context_pack.zh-CN.md`
3. `D:/FIN_Insight_Agent/docs/project_os/capability_status_ledger.jsonl`
4. `D:/FIN_Insight_Agent/docs/project_os/root_cause_issue_ledger.jsonl`
5. `D:/FIN_Insight_Agent/docs/internal/vnext_20260610/p34_lane_quality_first_source_runtime_program.zh-CN.md`
6. `D:/FIN_Insight_Agent/docs/worklog/product_strategy/115_p34_fact_table_payload_goldcase_availability_alignment.md`
7. `D:/FIN_Insight_Agent/docs/internal/vnext_20260610/p34_fact_table_projection_preview_v0_1.zh-CN.md`
8. `D:/FIN_Insight_Agent/docs/internal/vnext_20260610/p34_ai_semis_goldcase_rag_availability_alignment_v0_1.zh-CN.md`

## 3. 硬约束

- 不得在用户认可本轮 deterministic preview / alignment 前跑 true full-chain eval。
- 不得继续 paid model comparison、case expansion、release eval。
- 不得把 P34 scoped writer projection pass 误记为 full-chain pass、model comparison pass、release readiness 或 human-accepted gold workpaper。
- 不得把 source-route context row 缺 exact 数字直接写成公开源不存在；必须区分：
  - 当前 runtime row 已有；
  - current row 只是 context summary；
  - parser/adapter 没有抽出 numeric/table cell；
  - attempt-backed gap；
  - commercial gap；
  - not in current RAG scope。
- 不得用 gate/fallback 掩盖 owned parser / router / writer payload / renderer / evaluator 问题。
- 标准化 SEC/XBRL/CompanyFacts/13F 等既有结构化解析没有被判定为全局失效；本轮问题集中在 P34 AI/Semis source-route rows，很多来自官方 press/product/IR 页面。
- full-chain 前必须先跑 Project OS preflight：`python scripts/eval_multi_agent/run_project_os_full_chain_preflight.py`。

## 4. 最新状态

最新 capability：

```text
capability_id: p34_fact_table_payload_and_goldcase_availability_alignment
status: deterministic_scope_pass_user_approval_pending_full_chain_blocked
scope_pass_level: p34_scoped_writer_payload_fact_table_projection_and_goldcase_availability_alignment_not_full_chain_pass
```

最新 root-cause：

```text
issue_id: RC-P34-020-writer-payload-lacked-fact-table-surface-and-goldcase-availability-alignment
status: mitigated_deterministic_projection_pass_user_approval_pending
full_chain_blocker: true
```

关键指标：

- Indexed rows：`154,484`
- Tickers：`603`
- P34 slots：`20/20` attempted
- Accepted runtime rows：`21`
- Typed gaps：`2`
- Analyst fact tables：`7` blocks / `23` rows
- Value quality：
  - `structured_metric_context=6`
  - `specific_technical_or_deployment_fact=8`
  - `context_summary=7`
  - `attempt_backed_gap=2`

## 5. 最新代码 / 文档改动

主要改动文件：

- `D:/FIN_Insight_Agent/src/sec_agent/p34_lane_quality_runtime.py`
  - `build_ai_semis_scoped_writer_payload()` 新增 `analyst_fact_table_blocks`。
  - 新增七类 fact table block：
    - `financial_bridge_table`
    - `product_spec_architecture_table`
    - `customer_deployment_oem_table`
    - `capex_demand_pool_table`
    - `semicap_readthrough_table`
    - `market_counter_boundary_table`
    - `attempt_backed_gap_table`
  - 修正 DELL orders/backlog row 的 value quality，不因 `authority_scope` 包含 margin gap 就误归为 gap。
  - market price-in / counter-thesis 保持 `context_summary`，避免误提权。

- `D:/FIN_Insight_Agent/src/sec_agent/langgraph_orchestrator.py`
  - renderer 在 `核心判断` 后优先渲染 `关键数据表`。
  - required-item answer 分成 judgment / boundary / what-would-change。
  - 避免一句话里先下判断再立刻免责，导致阅读体验混乱。

- `D:/FIN_Insight_Agent/src/sec_agent/memo_llm.py`
  - Memo Writer 不再要求正文保留 raw metric id。
  - metric id 只应出现在 evidence ref / table audit context；正文要翻译成 analyst-readable label。

- `D:/FIN_Insight_Agent/scripts/eval_multi_agent/run_p34_scoped_memo_writer_payload_preflight.py`
  - 新增 checks：
    - `analyst_fact_tables_present`
    - `product_spec_fact_table_present`
    - `attempt_backed_gap_table_present`

- `D:/FIN_Insight_Agent/scripts/eval_multi_agent/run_p34_fact_table_projection_and_goldcase_alignment.py`
  - 新增 no-paid deterministic runner。
  - 生成 fact-table preview 和 goldcase/RAG availability alignment。

- `D:/FIN_Insight_Agent/tests/test_p34_scoped_memo_writer_payload.py`
  - 新增 fact-table payload / renderer projection regressions。

主要新增/更新产物：

- `D:/FIN_Insight_Agent/docs/internal/vnext_20260610/p34_fact_table_projection_preview_v0_1.zh-CN.md`
- `D:/FIN_Insight_Agent/docs/project_os/p34_ai_semis_goldcase_rag_availability_alignment_v0_1.json`
- `D:/FIN_Insight_Agent/docs/internal/vnext_20260610/p34_ai_semis_goldcase_rag_availability_alignment_v0_1.zh-CN.md`
- `D:/FIN_Insight_Agent/docs/worklog/product_strategy/115_p34_fact_table_payload_goldcase_availability_alignment.md`

## 6. 最新验证

已运行：

```powershell
python -m py_compile src/sec_agent/p34_lane_quality_runtime.py src/sec_agent/langgraph_orchestrator.py src/sec_agent/memo_llm.py scripts/eval_multi_agent/run_p34_scoped_memo_writer_payload_preflight.py scripts/eval_multi_agent/run_p34_fact_table_projection_and_goldcase_alignment.py
```

通过。

```powershell
python -m pytest -q tests/test_p34_scoped_memo_writer_payload.py tests/test_p33_memo_projection_replay.py tests/test_p34_ai_semis_live_route_attempts.py tests/test_p34_ai_semis_no_paid_quality_audit.py
```

结果：`15 passed`。

```powershell
python scripts/eval_multi_agent/run_p34_scoped_memo_writer_payload_preflight.py --run-id p34_scoped_memo_writer_payload_fact_tables_20260707_r2 --strict
```

结果：`gate_status=pass`，且以下检查为 true：

- `analyst_fact_tables_present`
- `product_spec_fact_table_present`
- `attempt_backed_gap_table_present`
- `full_chain_not_allowed`

```powershell
python scripts/eval_multi_agent/run_p34_fact_table_projection_and_goldcase_alignment.py
```

结果：

```text
status: goldcase_aligned_to_current_rag_and_route_availability_before_full_chain
full_chain_run: false
paid_llm_run: false
```

```powershell
git diff --check
```

结果：通过；只有既有 CRLF/LF warning，无 whitespace error。

## 7. 当前事实判断

这轮不是“最终投研输出质量已达标”。准确判断是：

1. **writer payload / renderer surface 的 owned defect 已修。**
   - 之前 writer 只拿 claims / required-item answers，容易写成边界说明。
   - 现在先给 analyst fact tables，再进入判断和边界。

2. **goldcase 已对齐当前 RAG/route 可得性。**
   - 不能要求 agent 输出当前 runtime row 没有的 exact 数据。
   - AI/Semis goldcase 现在区分 `available/runtime`、`context_summary`、`attempt_backed_gap`、`commercial_gap`、`not_in_current_rag_scope`。

3. **仍未解决 deeper parser/source exact 问题。**
   - DELL AI server margin bridge 仍缺 exact row。
   - market price-in exact positioning 仍缺 exact row。
   - semicap bookings/backlog/customer allocation 仍需要更深 source/parser。
   - 一些官方 press/product/IR 页面虽然可达，但当前 adapter 没把全部数字表格抽成 `value/unit/period/product/citation`。

4. **RAG/Milvus 的角色要说清楚。**
   - 本轮 P34 scoped writer case 是 source-route/runtime-row replay，不是 Milvus/rerank-driven full-chain retrieval run。
   - Milvus/RAG 仍是 broader discovery/retrieval substrate；true full-chain eval 时才测试召回/rerank/chunk。

## 8. 当前工作树状态

工作树很脏，包含大量历史 P30-P34 / R53-R60 相关 tracked/untracked 改动。不要在新窗口盲目 reset、checkout 或 bulk cleanup。

本轮最后一次检查到的相关状态包括：

- `src/sec_agent/p34_lane_quality_runtime.py` 当前在 git status 中显示 untracked，因为 P34 文件整体仍未正式提交。
- `scripts/eval_multi_agent/run_p34_fact_table_projection_and_goldcase_alignment.py` 为本轮新增。
- `docs/project_os/` 下大量 P31-P34 ledgers/artifacts 仍未提交。
- 既有 tracked 改动覆盖 Workbench、R53-R60、P33/P34 runtime、tests、docs 等大量文件。

新窗口如果要提交，必须先做 scoped `git status` / `git diff -- <paths>`，只 stage 本次确认范围，不要把所有 dirty 文件一锅端提交。

## 9. 推荐下一步

新窗口第一步不要直接跑模型。先向用户确认是否认可这两个产物：

- `D:/FIN_Insight_Agent/docs/internal/vnext_20260610/p34_fact_table_projection_preview_v0_1.zh-CN.md`
- `D:/FIN_Insight_Agent/docs/internal/vnext_20260610/p34_ai_semis_goldcase_rag_availability_alignment_v0_1.zh-CN.md`

如果用户认可，有两个合理方向：

### 方向 A：继续 parser/source 深挖

优先补：

1. DELL AI server margin bridge：
   - AI server mix；
   - GPU pass-through cost；
   - AI server gross margin；
   - backlog conversion。
2. Market price-in exact positioning：
   - valuation percentile；
   - holder/ETF/13F/insider；
   - short/options/borrow cost；
   - event price reaction。
3. Semicap read-through：
   - ASML/LRCX/AMAT/KLAC bookings/backlog；
   - HBM / advanced packaging exposure；
   - China exposure；
   - customer allocation。
4. Source-specific numeric/table parser：
   - official press release tables；
   - IR PDF tables；
   - official product spec tables；
   - investor deck tables。

### 方向 B：先用当前 fact-table payload 做 scoped writer rerun

前提：用户明确认可当前 fact-table surface，并接受剩余 exact gaps 被写成 bounded decision gaps。

限制：

- 只允许 scoped node，不允许 true full-chain。
- 跑前仍要 payload preflight。
- 输出后必须人工审，不可自动判 pass。

## 10. 禁止误判

- 不要说“P34 已经 full-chain 通过”。
- 不要说“换模型可以解决当前问题”。
- 不要说“RAG/Milvus 没用”；本轮只是没有走 Milvus retrieval。
- 不要说“parser 连 SEC 都抽不出来”；当前问题是 P34 source-route rows 中页面/PDF source-specific numeric extraction 不够深。
- 不要说“当前 memo 已达到 gold-set”；当前只是 deterministic fact-table preview + availability alignment。
- 不要把 `structured_metric_context` / `context_summary` 当 exact evidence。
- 不要把 `attempt_backed_gap` 写成 public source absent。

## 11. 可直接复用的用户汇报口径

可以这样向用户说明：

> 这轮已把 P34 writer payload 从 claim/required-item answer 改成先投影 analyst fact tables，并把 AI/Semis goldcase 对齐当前 RAG/route 可得性。当前 deterministic preview 有 7 个表、23 行；不跑 paid LLM、不跑 true full-chain。结果比之前更接近 workpaper surface，但还不是最终投研质量 pass。核心剩余问题是 source-specific numeric/table parser 深度：DELL AI server margin bridge、market price-in exact positioning、semicap bookings/backlog/customer allocation 等还没有 exact runtime rows。下一步需要你确认：是先接受当前 fact-table surface 做 scoped writer rerun，还是优先继续深挖 parser/source exact rows。
