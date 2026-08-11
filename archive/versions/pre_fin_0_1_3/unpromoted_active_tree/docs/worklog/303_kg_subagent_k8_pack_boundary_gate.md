# K8 KG Sub-agent Pack Boundary Gate

日期：2026-06-13

## 触发

用户要求在 K5/K6 source adapter 与 D3/D4/D5/D11 hardening 稳定后，再跑 K8 真实 case。K8 的目标不是再次扩源，也不是跑完整 G11 LLM full-chain，而是验证 KG pack / sub-agent / ClaimCard / verifier 边界是否能在 10-20 case 中闭环。

## 决策

- 新增 K8 专用 gate，而不是用 G11 full-chain smoke 代替：
  - `scripts/eval_multi_agent/eval_kg_subagent_k8_gate.py`
  - `tests/fixtures/kg_subagent_k8_cases_v0_1.jsonl`
- Gate 读取真实 materialized rows：
  - `data/manifests/evidence_fusion_context_rows_v0_1/product_evidence_rows.jsonl`
  - `Z:/FIN_Insight_Agent_data/processed_private/capital_macro_source_adapters/capital_macro_source_adapter_v0_1/*.jsonl`
- 产品规格、公开渠道、field inquiry 目前仍以 contract fixture 行验证 parser/gate 边界；不把这些 fixture 冒充为全量物化产品页/渠道数据。
- K8 通过条件固定为 10-20 case；小样本 inline smoke 即使 case 全 pass，也不能标记 K8 完成。

## 覆盖范围

12 个 case 覆盖：

- Product KPI：真实 `company_product_evidence_graph` AAPL product revenue row 支持 product ClaimCard。
- ProductSpec：公司官方产品页可生成 spec context，但不能证明 sales。
- ProductGenerationEdge：代际比较必须有 prior/current model 和 comparable dimensions。
- CompetitiveComparableEdge：竞品比较必须有 explicit dimensions；缺 dimensions 留在 rejected object。
- ChannelOffer：公开渠道/电商/订货页面只能支持 price / availability / configuration context，不支持 sell-through、market share、channel inventory。
- FieldInquiryNote：公开询价/经销商沟通只作为 qualitative lead，不是 authority fact。
- Commercial gap：IDC/Counterpoint 等商业 tracker gap 只暴露为 bounded gap，不走 weak proxy fallback。
- Capital / Ownership：真实 SEC annual debt/credit row、13F row 进入 CapitalMacroExposurePack；13F 保持 lagged context。
- Macro exposure：真实 EIA macro driver row 必须通过 CompanyExposureToDriver bridge 才能进入公司 thesis。
- Vertical official object：ClinicalTrials / openFDA / NHTSA 类官方对象只能支持监管/产品存在性上下文，不证明 commercial success。

## 修复

第一次完整运行：

- Run id：`20260613_kg_subagent_k8_pack_boundary_gate_v0_1`
- 结果：`11/12` pass
- 唯一失败：`k8_product_spec_official_surface_boundary`
- 根因：`aggregate_specialist_judgment_plan()` 会把 public/live web source 的 `product_sales` claim_type 规范化为 `public_proxy_context`，但没有保留 raw claim intent；后续 verifier 只看 normalized claim_type，漏拦了 “official product page proves product sales”。

修复：

- `src/sec_agent/multi_agent_contracts.py`
  - `normalize_specialist_memolet()` / `_normalize_observation()` 保留 `raw_claim_type`。
  - `_memo_claim_from_supported_claim()` 把 `raw_claim_type` 传到 memo claim。
  - `verify_multi_agent_memo_draft()` 和 `repair_multi_agent_memo_draft()` 用 normalized claim_type + raw_claim_type + gated metric token 并集执行 hard gate。
- 新增 regression：
  - `test_verifier_blocks_public_proxy_product_sales_after_claim_type_normalization`

这个修复没有放宽 source gate；它把 public proxy 误用拦截从“只看 normalized type”升级为“保留原始 claim 意图并 hard block”。

## 结果

最终完整运行：

- Command：`python scripts\eval_multi_agent\eval_kg_subagent_k8_gate.py --run-id 20260613_kg_subagent_k8_pack_boundary_gate_v0_2 --strict`
- Result：`12/12` pass
- Summary：`eval/sec_cases/outputs/kg_subagent_k8_gate/20260613_kg_subagent_k8_pack_boundary_gate_v0_2/kg_subagent_k8_gate_summary.json`
- 真实 capital/macro adapter 状态：
  - Target companies：`603`
  - `DebtInstrument`: `855`
  - `CreditFacility`: `1,715`
  - `OwnershipPosition`: `5,000`
  - `CapitalStructure`: `386`
  - `MacroDriver`: `155`
  - `CompanyExposureToDriver`: `2,525`
  - `VerticalOfficialObject`: `1,979`

## 测试

- `python -m py_compile src\sec_agent\multi_agent_contracts.py scripts\eval_multi_agent\eval_kg_subagent_k8_gate.py`
- `pytest -q tests\test_multi_agent_contracts.py tests\test_kg_subagent_k8_gate.py`
  - `22 passed`
- Targeted regression:
  - `pytest -q tests\test_product_spec_pack.py tests\test_capital_macro_pack.py tests\test_capital_macro_source_adapters.py tests\test_multi_agent_contracts.py tests\test_multi_agent_judgment_memo_verifier.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_kg_subagent_k8_gate.py`
  - `73 passed`
- `python -m compileall -q src scripts\eval_multi_agent`
- `pytest -q`
  - `894 passed`
- `git diff --check`
  - pass

## 边界

- K8 已完成的是 KG pack / sub-agent contract / ClaimCard verifier gate，不等同于 G11 真实 LLM full-chain。
- G11 full 12-case agent graph gate 仍未跑；应在后续 agent graph / skill 升级前或升级后作为全链路验收。
- 产品页、公开订货网站、field inquiry 的大规模真实 materialization 仍待后续 source adapter；当前 K8 只验证它们进入 KG 后的 parser/gate 边界。
- Offering / insider / 13D/G / proxy ownership raw material 仍是 K5 剩余缺口，不得由 10-K 普通描述或公开 proxy 兜底。
