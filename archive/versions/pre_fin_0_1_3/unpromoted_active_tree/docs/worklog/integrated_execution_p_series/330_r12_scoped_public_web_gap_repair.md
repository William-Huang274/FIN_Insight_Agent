# 330 R12 Scoped Public Web Gap Repair

## 问题

用户指出：证据缺口出现时，不能只在 prompt 或 plan 里说可以联网 repair；必须让本地代码自己能按 Research Lead 的 targeted repair 调用受控公开源、抓取证据、写回 context / ClaimCard / gap ledger，并先由我们自己测试可用，否则 DeepSeek 更无法稳定补证据。

本轮要补的五件事：

1. `TargetedRepairPlan` gap classifier：`issuer_official`、`product_surface`、`local_filing`、`market_proxy`、`capital_ownership`、`supply_chain`。
2. 每类 gap 的 web scope allowlist 和 adapter。
3. `LeadReview` 发现 `retrievable_gap` 后实际调用 repair。
4. repair 成功后写回 context rows / ClaimCards / GapLedger。
5. repair 后让 supervising analyst / memo 侧吃到新证据。

## 决策

- 保留现有 `execute_official_issuer_repair_plan(...)` 函数名，避免破坏 orchestrator；内部升级为 scoped public web gap repair executor。
- 不做无边界搜索兜底。每个 repair 必须有 `repair_type`、route、`web_scope_policy_ids`、`allowed_source_classes`、source boundary 和 not-found gap。
- 所有 live web rows 默认 `context_only=true`、`exact_value_authority=false`；只能生成 parser lead / context ClaimCard，不能直接提升为销售、订单、份额、出货、库存、融资金额、持有人比例等 exact facts。
- 失败 repair 进入 `source_gaps` 和 `bounded_gap_register`，不能在 memo 中消失。

## 完成

- `src/sec_agent/lead_supervision.py`
  - 新增六类 repair classifier、source class allowlist、scope policy、probe order、promotion gate 和 not-found gap 类型。
  - `dimension_reviews` 现在会从 gap rows 带出 ticker、company domains、官方产品 URL、产品 surfaces、metric leads、market/supply/capital URL。
  - `build_targeted_repair_plan(...)` 会把这些输入透传到 repair item。

- `src/sec_agent/official_issuer_repair.py`
  - 执行器升级为 `finsight_public_web_gap_repair_execution_v0_2`。
  - 新增 product surface、local filing、market proxy、capital/ownership、supply-chain probe 生成器。
  - 增加 source class + domain allowlist，阻断 reddit/x/blog/forum/social 等非允许源。
  - ASML/TSM/NVO profile 增补官方产品页入口。

- `src/sec_agent/langgraph_orchestrator.py`
  - `_lead_targeted_repair_context_claims(...)` 从 product-only 扩为 product/capital/market/supply/local/issuer 多类 ClaimCard。
  - successful repair 写入 `context_rows`、`supported_claims`、`memo_logic_plan`；failed repair 同步进 `bounded_gap_register`。
  - `supervising_analyst_pack` 已在 targeted repair 后构建，因此会自然吃到 repair 后的新 judgment/context。

- `tests/test_public_web_gap_repair.py`
  - 覆盖 plan 分类和参数透传。
  - 覆盖多类 scoped public web repair 执行和 ClaimCard materialization。
  - 覆盖禁用域在 fetch 前阻断。
  - 覆盖 orchestrator 状态回写 context / ClaimCard / bounded gap register。

- `scripts/eval_multi_agent/smoke_public_web_gap_repair.py`
  - 新增不依赖 LLM 的可复跑 smoke。
  - `fixture` 模式用 fake fetch 验证 executor 和 ClaimCard。
  - `live` 模式真实联网抓 ASML 官方产品页和 SEC 官方 submissions endpoint。

## 验证

- `python -m py_compile scripts\eval_multi_agent\smoke_public_web_gap_repair.py src\sec_agent\lead_supervision.py src\sec_agent\official_issuer_repair.py src\sec_agent\langgraph_orchestrator.py`：通过。
- `pytest -q tests\test_public_web_gap_repair.py tests\test_runtime_bridge_contracts.py -k "public_web_gap_repair or official_issuer or lead_supervision_routes or proactively_routes"`：`7 passed`。
- `python scripts\eval_multi_agent\smoke_public_web_gap_repair.py --mode fixture --output-dir reports\quality\public_web_gap_repair_smoke\20260615_fixture`：
  - status `pass`
  - attempted `1`
  - success `3`
  - claim types `product_taxonomy_context`
- `python scripts\eval_multi_agent\smoke_public_web_gap_repair.py --mode live --output-dir reports\quality\public_web_gap_repair_smoke\20260615_live`：
  - status `pass`
  - attempted `3`
  - success `11`
  - bounded gaps `0`
  - claim types `official_issuer_context`, `product_taxonomy_context`
- `pytest -q tests\test_public_web_gap_repair.py tests\test_runtime_bridge_contracts.py tests\test_supervising_analyst_pack.py tests\test_multi_agent_memo_llm_repair.py`：`61 passed`。

## 边界

- 本轮没有跑 DeepSeek full-chain；目标是先让本地 repair 工具链自身可执行。
- 当前不是开放式搜索引擎。未知公司若没有 issuer profile、gap-provided official URL、domain 或 source URL，仍会暴露为 bounded gap，而不是泛搜兜底。
- 真实 product sales/share/sell-through、融资金额/持有人比例、供应链订单量仍必须等 source-specific parser 或商业 tracker；本轮只把公开可得官方/受控源转成 context / parser lead。
