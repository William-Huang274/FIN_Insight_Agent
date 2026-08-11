# 历史 Case 表现审计

日期：2026-07-11

状态：`pass`。本审计未运行 paid model 或 full-chain。

## 核心结论

- Catalog/source memberships：122；去重 case：137。
- Artifact-backed cases：15，其中 gold-exemplar-backed 14，case-specific AI/Semis pack 1。
- No-paid fresh specialist fixture proven：1；真实 node-level fresh specialist proof：0。
- Explicit full-chain proven：0。
- Explicit human-accepted：0。
- 跨行业可比表现 case：0；泛化状态：`not_proven`。

历史 case 数量说明测试意图覆盖较宽，但不能证明 agent 已跨行业稳定运行。只有显式 readiness、node/full-chain gate 和 reviewer record 才能提升成熟度。

需要同时保留一个正向事实：旧 SEC benchmark 曾在 cross-industry10 和 combined40 上通过 deterministic diagnostics。这证明旧链路的 SEC 检索、exact-value ledger、Judgment Plan 和受约束合成有可复用资产，但它不是当前 DecisionSurface / agentic-research runtime 的泛化证明。

## Readiness 权威记录

| Source | Status | Cases | Artifact ready | Fresh specialist | Contract ready | Blocking |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| p33_multicase_readiness | blocked_until_multicase_artifact_depth_and_fresh_specialists_pass | 15 | 1 | 0 | 15 | 15 |
| p34_multicase_readiness | blocked_until_multicase_artifact_depth_and_fresh_specialists_pass | 15 | 1 | 0 | 15 | 15 |
| p33_multicase_no_paid_audit | pass | 15 | 15 | 1 | 15 | 0 |

## 成熟度分布

- `catalog_only`：98
- `exemplar_artifact_backed`：14
- `fixture_defined`：24
- `fresh_specialist_fixture_proven`：1

## 历史运行证据

| Run | Generation | Scope | Result | Boundary |
| --- | --- | --- | --- | --- |
| legacy_sec_cross_industry10_20260520 | legacy_sec_benchmark_pipeline | 10 cross-industry SEC cases | diagnostic_pass | Proves legacy SEC retrieval, exact-value grounding, Judgment Plan and bounded synthesis diagnostics; does not prove current multi-agent DecisionSurface or agentic-research runtime. |
| legacy_sec_combined40_20260521 | legacy_sec_benchmark_pipeline | 40 mixed SEC cases including 4 traps | diagnostic_pass | Valid legacy regression baseline with deterministic gates; not a current full-chain research-agent or client-ready report proof. |
| p20_ai_infra_full_chain_20260630 | pre_decision_surface_multi_agent | 1 AI infrastructure full-chain dogfood case | diagnostic_pass_after_gate_repair | Real-model AI-infrastructure dogfood only; later review corrected diagnostic/smoke completion language and requested a fresh case. |
| p30_ai_semis_two_case_20260701 | pre_decision_surface_multi_agent | 2 AI/Semis full-chain smoke cases | diagnostic_pass_with_material_defects | Both CLI gates passed with diagnostic_only=true, while memo correctness, core-ticker evidence, token cost and Workbench projection defects remained. |
| p33_single_gold_paid_attempt_20260705 | pre_decision_surface_multi_agent | 1 scoped paid AI/Semis case | failed_writer_verifier | Research Lead, reflection and specialist quality passed, but writer/verifier failed; no accepted gold workpaper. |
| p36_codex_manual_11_node_dogfood_20260708 | manual_codex_as_paid_model | 11-node manual AI infrastructure dogfood | manual_observation_complete_runtime_fail | Manual chain completed, but supervisor supplements are not runtime evidence and the result explicitly fails as runtime capability. |

## 对首批 Calibration 的影响

1. P36/AI infrastructure 只能作为 artifact-backed anchor，不能作为泛化证明。
2. SaaS、Healthcare、Banks 应作为 shadow calibration case，引入不同经济机制和估值本体。
3. 第一轮只校准 DecisionSurface compiler、cell 粒度、sector required cells 和 forbidden substitutions。
4. 不用新 paid/full-chain run 补审计证据；后续单节点 paid run 必须经过 deterministic 与人工 gate。

## 审计边界

- `catalog_only`：只有题目/预期合同。
- `fixture_defined`：有行业 fixture，但不表示 runtime 消费。
- `contract_ready`：合同已编译，不表示 evidence/artifact 质量通过。
- `exemplar_artifact_backed`：gold exemplar 已编译成 pack，不表示 live source/runtime。
- `live_artifact_backed`：存在 case-specific evidence artifact，但仍不等于 fresh specialist/full-chain。
- `fresh_specialist_fixture_proven`：no-paid specialist fixture 通过，不表示真实模型节点或 full-chain。
- 输出目录或历史文件名不自动晋升成熟度。
