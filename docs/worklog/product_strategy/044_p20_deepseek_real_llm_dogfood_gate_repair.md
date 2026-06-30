# P20 DeepSeek Real LLM Dogfood / Gate Repair

## 背景

用户要求判断下一步是否需要用 DeepSeek API 实测，并提供临时 API key。key 仅用于本轮进程环境变量，没有写入仓库、日志、报告或配置。

本轮目的不是重新跑大量 full-chain，而是用真实模型验证 P11-P19 的 runtime / eval / memo surface 是否真的能承接企业级验收口径，尤其检查 deterministic tests 无法覆盖的模型行为。

## 实测范围

- DeepSeek health smoke：`deepseek-chat` API 可用，延迟约 1.1s，返回正常。
- Research Lead activation 2-case smoke：通过。
  - 报告路径：`reports/r53_r60_p20_deepseek_smoke/research_lead/20260630_p20_research_lead_deepseek_chat_2case_v0_1/activation_diagnostic.json`
- Specialist real-evidence quality 2-case smoke：通过。
  - 报告路径：`reports/r53_r60_p20_deepseek_smoke/specialist/20260630_p20_specialist_real_evidence_deepseek_chat_2case_v0_1/specialist_real_evidence_quality_eval.json`
- AI infrastructure full-chain 1-case dogfood：多轮迭代到 `v0_6`。
  - 报告目录：`reports/r53_r60_p20_deepseek_smoke/full_chain/20260630_p20_full_chain_ai_infra_deepseek_chat_v0_6/`
  - 渲染报告：`reports/r53_r60_p20_deepseek_smoke/full_chain/20260630_p20_full_chain_ai_infra_deepseek_chat_v0_6/fin_run_audit_ai_infra_capex_dimension_zh/qwen/rendered_answer.md`

## 真实模型暴露的问题

1. Research Lead 第一次 full-chain 输出因为 token 上限过低被截断，导致 `invalid_agent_activation_plan`。
   - 处理：提高相关真实链路调用预算，不把截断输出当可修复计划。

2. `industry_supply_chain_analyst` 的 role-specific source-family gate 过窄。
   - 真实 runtime 给到的是 `public_source_context`、`company_product_evidence_graph`，但 gate 只接受 `industry_snapshot` / `relationship_graph`。
   - 处理：扩展 role-specific accepted source families，同时保留 exact-authority 边界。

3. Memo surface 曾泄漏内部字段和内部对象名。
   - 典型问题：正文出现 `ClaimCard` / driver-like 语言。
   - 处理：清洗 `financial_bridge`、`business_mechanism`、`counter_read` 等 writer-facing text，并把 “ClaimCard” 改成用户可读的 “verified evidence”。

4. Peer/context 证据污染 memo claim。
   - 典型问题：AMZN revenue `20.0 usd_billions` 这类非目标公司/非主论据事实被拉进 memo。
   - 处理：新增 focus/search scope role 判断；peer/context total facts 不能因为 ticker 出现在研究范围就自动进入 memo-facing ClaimCard。

5. 大额裸 `usd` 单位被误当成可读金额。
   - 典型问题：`77658.0 usd` 被渲染成 `77658美元（单位疑似有误）`。
   - 处理：大额 monetary facts 若 unit 只有 `usd/$/dollar` 且数值量级可疑，禁止进入 deterministic memo-facing claim。

6. 产品段与资本开支段职责混淆。
   - 典型问题：资本开支证据被写到“产品与产线证据”里，或者产品段用 capex 代表产品成功。
   - 处理：资本开支 claim 不再因为出现 `capacity` 被路由到产品维度；investment quality gate 新增 product-section fake-financial line 检查。

7. Gate 聚合口径不一致。
   - `v0_6` 里 investment quality 记录为 fail，但顶层 `gate_status` 仍 pass，因为只有显式 `require_investment_memo_quality` 的 case 才把该 gate 并入总门控。
   - 处理：对 deep-research / dimension memo surface / analyst-depth case 默认启用 investment quality gate；`L4_scope_pass` 不能再只靠“有输出”或“结构有段落”通过。

## 本轮代码修复

- `src/sec_agent/d_series_fact_selection.py`
  - 增加 focus/search scope role 识别。
  - 避免 route ticker key 污染 query objective terms。
  - 拒绝 unscored peer/context generic total facts 进入 memo-facing ClaimCard。
  - 拒绝大额裸 `usd/$/dollar` monetary facts 进入 memo-facing deterministic claim。

- `src/sec_agent/multi_agent_contracts.py`
  - 修正 `_claim_is_capital_only`，避免 capex 因 `capacity` 字样被送入 product dimension。
  - 去掉 writer-facing bridge 中的 `ClaimCard` 内部对象表达。

- `src/sec_agent/memo_llm.py`
  - 新增 memo-facing internal term cleaner，清洗 `ClaimCard`、`driver_id`、source-family 等内部对象语言。

- `src/sec_agent/agent_contracts.py`
  - 扩展 industry/supply-chain specialist 的 source-family acceptance。

- `src/sec_agent/role_evidence_selector.py`
  - 为 `industry_supply_chain_analyst` 增加显式 source policy，优先使用 relationship / product graph / public source context，但不提升 exact authority。

- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - 新增 `investment_quality_required` 规则：deep-research、dimension surface、analyst-depth case 默认纳入 investment quality gate。
  - product-section fake-financial 检查只扫描“产品/产线”编号小节，不再误扫整个“分维度分析”。
  - 扩展 product/capex 混用检查与行业供应链 source-family gate。

## 验收

- 真实 DeepSeek：
  - Research Lead activation 2-case：通过。
  - Specialist real-evidence quality 2-case：通过。
  - AI infra full-chain `v0_6`：真实输出在修复后的 investment quality evaluator 下重新打分为 `pass`。
    - `thesis_not_gap_first=true`
    - `gap_budget_ok=true`
    - `opening_information_dense=true`
    - `insight_density_ok=true`
    - `citation_backed_insight_ok=true`
    - `decision_sections_present=true`
    - `decision_sections_actionable=true`
    - `product_section_not_fake_financial_line=true`
    - `product_section_fake_financial_line_count=0`

- 非 LLM deterministic regression：
  - `python -m pytest tests\test_multi_agent_real_llm_chain_eval.py tests\test_multi_agent_contracts.py tests\test_d_series_fact_selection.py -q` -> `93 passed`
  - `python -m pytest tests\test_multi_agent_contracts.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_d_series_fact_selection.py tests\test_multi_agent_memo_llm_repair.py tests\test_multi_agent_activation_plan.py -q` -> `150 passed`
  - `python -m compileall -q src\sec_agent scripts\eval_multi_agent tests` -> pass

## 结论

这轮证明真实 DeepSeek dogfood 是必要的：deterministic tests 能证明合同和 gate，但不能提前暴露真实模型在 token 截断、角色 source-family、内部字段泄漏、同行/上下文污染、金额单位误提权、产品/资本开支混写上的行为。

当前不需要立刻再烧同一个 full-chain。更合理的下一步是：

1. 先把本轮修复提交为一个 auditable release slice。
2. 再选一个新的 fresh case 运行 1-case full-chain，验证修复不是只对 AI infra 个例有效。
3. 如果 fresh case 通过，再扩大到 2-case 或 12-case successor；如果失败，先修 root cause，再继续。

## 边界

- 本轮没有把 DeepSeek key 写入仓库。
- `reports/r53_r60_p20_deepseek_smoke/` 是生成报告目录，默认不提交 Git。
- 本轮没有重新跑 12-case / 50-case 全量，因为当前目标是验证真实模型暴露的问题和 gate repair，而不是消耗 token 做广覆盖回归。
