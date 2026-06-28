# 333 R12 Role Source-Layer Distribution Gate

日期：2026-06-15

## 问题

上一轮 SL0-SL4 已经让系统知道 L1/L2/L3/L4 源层能力和缺口，但 specialist 侧仍可能只看到 generic evidence bundle。这样会继续出现两个问题：

1. Product / Market / Supply-chain / Capital 等角色不知道哪些 L2/L3 公开源理论上可用、哪些已接入、哪些还只是 parser/backfill 缺口。
2. 缺 source layer 时容易被静默 cap 成证据不足，而不是形成可审计 selector gap。

本轮目标是先把 role-visible source-layer distribution 做成 runtime contract 和 eval gate，再进入 L2/L3 parser/backfill。不能因为 parser 还没全量完成，就把可补公开源直接暴露为 bounded gap。

## 完成工作

1. 新增 role-specific source-layer selector distribution：
   - `src/sec_agent/role_evidence_selector.py`
   - 新增 `build_role_source_layer_distribution(...)`。
   - 按 specialist role 匹配 `specialist_slots`，输出每个角色的 required layers、candidate rows、selected rows、selected_by_layer、status distribution、missing required layers、exact-authority violation sources。
   - `coverage_status` 分为 `pass` / `gap` / `fail`：显式缺口是 `gap`，L2/L3/L4 被误提权为 exact authority 是 `fail`。

2. 接入 Specialist runtime：
   - `src/sec_agent/specialist_llm.py`
   - Shared specialist context 现在会从 `source_layer_capability_audit` 生成 `role_source_layer_distribution`。
   - Specialist request、first-round prompt payload、repair payload、route summary、fanout barrier 都带上 compact source-layer distribution。
   - Prompt 明确要求 specialist 使用 L1/L2/L3/L4 source-layer 分布判断证据边界；显式 selector gap 要写成 unsupported / bounded gap，不能静默忽略。

3. 接入 LangGraph summary：
   - `src/sec_agent/langgraph_orchestrator.py`
   - `graph_barriers.specialist_fanout.source_layer_distribution` 现在可被 run summary / eval / Workbench trace 读取。

4. 新增 eval gate：
   - `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
   - 新增 `role_source_layer_distribution` layer check。
   - 支持 `require_role_source_layer_distribution`、`require_role_visible_source_layer_audit`、`expected_role_source_layer_roles`、`fail_on_role_source_layer_gaps`。
   - gate 允许显式 selector gap，但拒绝：
     - 缺失 role distribution；
     - 预期角色没有分布；
     - role distribution 静默为空；
     - L2/L3/L4 exact-authority promotion。

5. 官方 web repair context rows 补 source-layer metadata：
   - `src/sec_agent/official_issuer_repair.py`
   - targeted web repair 产生的 context rows 现在携带：
     - `source_layer_id`
     - `source_layer`
     - `parser_status=snapshot_context_parser_pass`
     - `structured_fact_status=context_row_materialized`
     - `evidence_graph_status=runtime_ready_context`
     - `context_or_proxy_allowed`
     - `can_support_company_exact_fact=false`
     - `source_layer_claim_boundary`
     - `source_layer_memo_usage`
   - 这表示官方/可信公开源能进入 context/proxy，不表示产品销量、订单、份额、ASP、库存等 exact facts 已经可用。

6. 补充测试：
   - `tests/test_runtime_bridge_contracts.py`
   - `tests/test_multi_agent_specialist_llm.py`
   - `tests/test_multi_agent_real_llm_chain_eval.py`
   - `tests/test_public_web_gap_repair.py`

## 验证结果

已运行：

```powershell
python -m pytest tests/test_runtime_bridge_contracts.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_public_web_gap_repair.py tests/test_source_layer_capability_audit.py -q
python -m pytest tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_contracts.py -q
python scripts\data_expansion\audit_source_layer_capabilities.py --strict
python scripts\eval_multi_agent\smoke_public_web_gap_repair.py --mode fixture --output-dir reports/quality/public_web_gap_repair_smoke/source_layer_fixture
git diff --check
```

结果：

- Targeted tests：`111 passed`
- Routing / contracts：`57 passed`
- Source-layer audit strict：`pass`
- Public web gap repair fixture smoke：`pass`
- Diff whitespace check：`pass`

## 当前边界

1. 本轮没有跑新的 DeepSeek full-chain case；这是有意控制 token。现在完成的是 runtime contract / prompt input / eval gate / fixture smoke。
2. L2/L3 source-specific parser/backfill 仍未全量完成。待补重点包括：
   - 电商/渠道报价；
   - App Store / marketplace 排名；
   - GitHub / npm / PyPI / HuggingFace；
   - 公开招投标 / 公开订单；
   - 招聘与岗位 proxy；
   - 平台评论 / 下载排名；
   - 主流财经新闻和行业协会数据。
3. 当前 official web repair context rows 是 snapshot context/parser pass，不是结构化产品表现事实。后续必须继续把 HTML/PDF/XLS/table 解析成 bounded context/proxy facts。

## 下一步

进入 `R12 L2/L3 parser and backfill tranche`：

1. 先选高价值、低噪声的 L2/L3 official/public routes：
   - company product pages / official product docs；
   - supplier/customer official news；
   - mainstream financial news；
   - developer ecosystem routes；
   - tenders/orders/hiring/channel offer routes。
2. 为每一路补 parser schema、row normalization、claim boundary 和 fixture/live smoke。
3. 通过后再跑 1-2 个 full-chain case，看 Research Lead targeted repair 是否能把具体公开源 rows 补进 evidence graph，而不是只暴露 capability rows。
