# P30 JudgmentCard / ThesisPath / Writer Audit Repair

## 问题

用户复核指出，P30 的 token 消耗和输出质量问题不能被降格成“省 token”或“多加 gate”。真正的问题是 agent 框架的信息传导质量：上游证据、产品图谱、财务基本面、供应链/客户部署和 specialist 分析没有稳定转化为 Research Lead thesis path、writer-ready 判断材料和最终 memo 的可读判断。

本轮围绕 6 个问题做 deterministic / node-level 修复：

1. `ClaimCard` 不能只做证据卡，需要升级成可写作、可审计的判断卡。
2. `Research Lead` 不能只派单，需要产出 thesis path 和机制边。
3. `MemoLogicPlan` 必须成为 writer 主输入，而不是旁路 artifact。
4. raw model output、normalized memo、deterministic salvage 之间必须可审计。
5. token-to-insight 不是预算问题，而是信息压缩、角色选择、传递效率和有效判断产出的质量问题。
6. 先做 AI/Semis 样板级 deterministic proof，再考虑真实单 case paid run；不再一上来烧 full-chain。

## 决策

本轮不跑付费 LLM，不跑 broad full-chain。先修 owned artifact / contract / projection / audit 根因：

- 如果上游能找到问题，就先修上游合同，不靠 writer gate 掩盖。
- 如果 writer 被 salvage，不能当成功兜底，必须记录 raw-to-normalized failure。
- 如果 token 很大但 claim / judgment yield 低，必须在 AIE 里定位为 agent framework defect。
- 如果 `ProductIntelligenceGraph`、财务、供应链、资本市场证据已经存在，writer 输入必须收到压缩后的“可写判断材料”，而不是重复 evidence dump。

## 已完成工作

### JudgmentCard / ThesisPath

- `src/sec_agent/multi_agent_contracts.py`
  - 新增 `JUDGMENT_CARD_SCHEMA_VERSION` 和 `THESIS_PATH_SCHEMA_VERSION`。
  - `aggregate_specialist_judgment_plan`、`aggregate_focused_answer_judgment_plan`、`refresh_judgment_plan_after_governance_filter` 现在生成 `judgment_cards` 和 `thesis_path`。
  - `JudgmentCard` 从 supported ClaimCards 派生，保留 evidence refs、source role、source families、authority boundary，并新增 `judgment`、`evidence_bridge`、`business_mechanism`、`financial_bridge`、`counter_read`、`what_would_change_view`。
  - `ThesisPath` 把 dimension nodes 组织成可写作机制边，例如 `product_to_financial_bridge`、`supply_chain_to_product_context`、`capital_structure_to_fundamental_bridge`。

### MemoLogicPlan 主输入

- `src/sec_agent/memo_logic_plan.py`
  - `build_memo_logic_plan` 现在携带 compact `judgment_cards` 和 `thesis_path`。
  - `validate_memo_logic_plan` 会检查 JudgmentState 中存在的 judgment cards / thesis path 是否被投影到 MemoLogicPlan。
  - writer thesis skeleton 优先使用 `thesis_path.primary_thesis`，dimension moves 带 `judgment_card_ids`。
  - compact payload 只保留 required-item answer move 计数，避免同一大段提示在 `required_item_answer_plan` 和 writer skeleton 里重复传输。

### Memo Writer raw-output audit

- `src/sec_agent/memo_llm.py`
  - `route_memo_writer_llm` 新增 digest-only `raw_output_audit`。
  - 审计记录 raw output hash、长度、parsed/normalized claim counts、deterministic gate status/error types 和 salvage trigger。
  - 不保存原始模型输出文本，避免 prompt / completion 泄露。
  - expanded / deep profile 的 supported claim cap 从 5 调整到 6，避免过度剪裁导致 writer 缺少判断材料。

### Agent Information Economy

- `src/sec_agent/agent_information_economy.py`
  - 新增 blocking issue：`memo_writer_raw_gate_or_salvage_failure`。
  - AIE 现在能把 raw gate failure / deterministic salvage 映射到 root cause：`memo_raw_output_to_normalized_writer_contract`。
  - 这使 salvage 变成可追责的质量问题，而不是静默 fallback。

### Regression tests

- `tests/test_multi_agent_contracts.py`
  - 覆盖 DELL 类 product-to-financial judgment card 和 thesis path mechanism edge。
- `tests/test_memo_logic_plan.py`
  - 覆盖 MemoLogicPlan 对 judgment cards / thesis path 的投影和 compact payload。
- `tests/test_multi_agent_memo_llm_repair.py`
  - 覆盖 Memo Writer deterministic salvage 时的 raw output audit。
- `tests/test_agent_information_economy.py`
  - 覆盖 AIE 对 raw gate / salvage failure 的阻断和根因归类。

## 验证

已运行：

```powershell
python -m compileall -q src/sec_agent/multi_agent_contracts.py src/sec_agent/memo_logic_plan.py src/sec_agent/memo_llm.py src/sec_agent/agent_information_economy.py
python -m pytest tests/test_multi_agent_contracts.py tests/test_memo_logic_plan.py tests/test_multi_agent_memo_llm_repair.py tests/test_agent_information_economy.py -q
```

结果：

- `compileall` 通过。
- targeted regression：`128 passed in 7.05s`。

## 边界

- 本轮没有调用付费 LLM。
- 本轮没有跑 full-chain。
- 本轮证明的是 P30 1-6 点的信息传导合同和 deterministic audit 已修复，不证明真实模型 memo 质量已经达标。
- 下一次 paid run 只能先跑一个 AI/Semis single case，并且必须先通过 data/script audit、AIE preflight、route observability 和 token-budget gate。

## 后续

1. 对新生成的真实 single-case artifact 验证：
   - `judgment_cards` / `thesis_path` 是否进入 `JudgmentState`、`MemoLogicPlan`、writer payload。
   - `raw_output_audit` 是否能解释 raw -> normalized -> salvage 过程。
   - AIE 是否通过 token-to-insight 和 raw/salvage failure gate。
2. 如果 memo 仍浅，要先定位：
   - Research Lead thesis path 是否弱；
   - ProductIntelligenceGraph 是否没有被主骨架使用；
   - specialist 是否输出了判断而不是事实罗列；
   - writer 是否忽略 JudgmentCard；
   - 数据/解析器是否有 owned gap。
3. Broad 20-50 case 继续禁止作为产品质量 closeout，直到 single-case 样板输出达到可读、有判断、有证据、有边界。

## 2026-07-03 后续无付费验证：role-specific prompt-overlap repair

在上述 1-6 点 deterministic 修复后，新的 no-paid semicap mock artifact 进一步暴露出 `prompt_pack_overlap_proxy`：不是检索没数据，而是 product / industry / risk specialist 仍重复读取同一批 refs。该问题已作为 agent 信息传导根因继续修复，而不是靠放宽 AIE gate 通过。

本轮追加修复：

- product specialist prompt 输入限定为产品画像、规格、Product-KPI、channel/field-inquiry 和商业缺口，不再读取 customer deployment / supply-chain edge。
- industry specialist prompt 输入限定为行业、关系图、客户部署、订单、供应链、渠道和上下游信号，不再读取普通 product profile。
- risk specialist prompt 输入限定为真实 risk / constraint / counterevidence 行，不再通过宽泛 counterclaim-slot 匹配读取普通 revenue / gross margin 行。
- `ProductSpecPack` 的 product prompt projection 排除 `customer_deployment_signals` 和 `supply_chain_signals`；原始 pack 仍保留这些 sections 供审计和 industry lens 使用。

验证：

- `python -m pytest tests/test_multi_agent_specialist_llm.py tests/test_product_spec_pack.py tests/test_agent_information_economy.py -q`
  - `69 passed`
- `python -m pytest tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_routing_fixtures.py tests/test_memo_logic_plan.py tests/test_multi_agent_contracts.py -q`
  - `131 passed`
- no-paid mock + real-evidence artifact：`p30_mock_semicap_role_specific_prompt_overlap_repair_20260703`
  - `agent_information_economy_audit.status=pass`
  - `prompt_pack_overlap.overlap_detected=false`
  - `duplicate_prompt_evidence_ref_count=0`
  - `data_script_quality_audit.status=pass`

边界：

- 没有调用付费 LLM。
- 这证明 role-specific prompt transfer 根因已在 deterministic / mock artifact 层闭合；仍不证明真实模型 memo 输出质量达标。
- 下一次真实 paid run 仍只能先跑单个 AI/Semis case，并且必须先通过 data/script、AIE、real-evidence、route/fanout、role-overlap 和 token-budget preflight。
