# 332 R12 Source-Layer Capability And Analyst-First Gate

日期：2026-06-15

## 问题

用户指出当前 full-chain 输出仍然太像“证据缺口审计”，真正有用的投研 insight 太少；同时需要检查 L2/L3/L4 源层是否已经接入、能否爬、能否解析、能否结构化、能否进入 evidence graph / specialist / memo。要求先做小阶段文档，再按文档推进，避免靠聊天记忆漂移。

## 决策

本阶段不放松事实门控，也不把 proxy 冒充为强事实。改成 analyst-first 目标函数：

- 先在可信数据边界内寻找可成立的 bounded judgment。
- L2/L3 正常可信公开源应能以 context / proxy / lead / gap 进入 evidence graph。
- L2/L3/L4 不能直接支持公司收入、份额、销量、库存等 exact facts。
- Research Lead 需要先判断缺口是否公开源可补；能补则 targeted repair，不能补才暴露 bounded/commercial gap。
- Memo quality gate 需要拒绝“满篇无法判断”和内部字段泄露。

## 完成工作

1. 新增小阶段文档：
   - `docs/architecture/agent_graph_vnext/15_source_layer_capability_and_analyst_first_optimization.zh-CN.md`
   - 定义 SL0-SL5：source-layer audit、evidence graph 进入策略、Research Lead targeted repair、role-specific selector、Memo Writer analyst-first surface、验收顺序。
   - 文档已追加本轮落地状态和未完成边界。

2. 新增 Source-Layer Capability Audit：
   - `src/sec_agent/source_layer_capability_audit.py`
   - `scripts/data_expansion/audit_source_layer_capabilities.py`
   - 生成：
     - `data/manifests/source_layer_capability_audit_v0_1.jsonl`
     - `data/manifests/source_layer_capability_audit_summary_v0_1.json`
     - `docs/internal/vnext_20260610/source_layer_capability_audit.zh-CN.md`
   - 审计结果：`44` 个 source rows，`12` 个 expected-but-missing，`5` 个 runtime-ready，`28` 个允许 context/proxy，`1` 个 exact authority ready。
   - L2/L3/L4 未接入源被显式记录为 `not_registered`，不再从系统视野里消失。

3. 接入 Research Lead：
   - `src/sec_agent/langgraph_orchestrator.py`
     - state 增加 `source_layer_capability_audit`。
     - runtime summary 暴露 `by_layer`、`by_evidence_graph_status`、`by_acquisition_status`、`by_parser_status`。
     - multi-agent artifacts 写出 `source_layer_capability_audit.json`。
   - `src/sec_agent/lead_supervision.py`
     - `LeadReviewCheckpoint.dimension_reviews[]` 增加 `candidate_source_layers` 和 `source_layer_repairability`。
     - 当维度没有 supporting claims，但 source-layer audit 显示存在 `structured_not_promoted`、`staging_parser_gate_pending`、`crawlable_not_parsed_or_not_routed`、`runtime_ready_context` 时，先标为 `retrievable_gap`，不直接 bounded。

4. 接入 eval gate：
   - `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
     - 新增 `source_layer_capability` layer check。
     - case 可用 `require_source_layer_capability_audit` / `require_l2_l3_l4_source_audit` / `required_source_layers` 要求源层审计可见。
     - gate 检查 L2/L3/L4 是否可见、状态分布是否可见、expected missing 是否暴露、L2/L3/L4 是否没有被提权成 exact authority。
   - 已存在并验证的 memo quality gate 会拒绝 gap ledger surface、产品段误用财务科目、内部字段泄露和模板化 opening。

5. 测试覆盖：
   - `tests/test_source_layer_capability_audit.py`
   - `tests/test_multi_agent_real_llm_chain_eval.py`

## 验证结果

已运行：

```powershell
python scripts\data_expansion\audit_source_layer_capabilities.py --strict
python -m pytest tests/test_source_layer_capability_audit.py tests/test_multi_agent_real_llm_chain_eval.py -q
```

结果：

- Source-layer audit strict：`pass`
- Targeted tests：`44 passed`

## 当前缺口

1. 本阶段没有跑新的 DeepSeek full-chain case；这是有意为之，先把 deterministic audit / gate 做稳，避免继续烧 token。
2. L2/L3 source-specific adapters 仍待补齐：电商、App Store、GitHub/npm/PyPI/HuggingFace、公开招投标、招聘、渠道报价、评论/下载排名等目前多为 `not_registered`。
3. Specialist selector 还没有强制每个角色拿到 L1/L2/L3 source-layer 配额；下一步应把 role-visible source-layer distribution 做成 runtime gate。
4. Parser/backfill 仍是主要瓶颈：当前系统能知道“哪些公开源应补”，但还没有把所有页面/PDF/表格稳定转成结构化 facts。

## 下一步

建议按以下顺序继续：

1. 先做 role-specific source-layer selector distribution gate，确保 product / market / supply-chain / capital specialist 能看到对应 L1/L2/L3 rows。
2. 再补 L2/L3 高优先级 parser/backfill：公司产品页、供应商/客户官方新闻、主流财经新闻、渠道报价/电商/开发者生态 proxy。
3. 再跑 1-2 个 full-chain case，看 targeted repair 是否真的把公开源补进 evidence graph，而不是只在 checkpoint 里显示候选。
4. 若 memo 仍然偏保守，再把 `source_layer_capability` gate 与 memo quality gate 接入 online eval / failure queue。
