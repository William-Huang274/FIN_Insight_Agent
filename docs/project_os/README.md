# FIN Insight Project OS

这个目录是 FIN_Insight_Agent 的轻量项目操作系统，用来减少跨会话记忆漂移、过早 full-chain、弱 fallback 和局部最优修复。

它不是普通工作日志。这里存放的是每轮任务启动、full-chain 预检、root-cause closeout、技术模式复用和金融研究方法复用所需的当前事实。

## 文件职责

- `current_context_pack.zh-CN.md`：每轮启动前先读的短上下文包。
- `capability_status_ledger.jsonl`：机器可读能力状态主账本。
- `root_cause_issue_ledger.jsonl`：机器可读 root-cause issue / blocker 账本。
- `full_chain_run_policy.zh-CN.md`：full-chain / expensive eval 运行策略。
- `token_budget_policy.zh-CN.md`：token 预算与信息经济策略。
- `done_definition_l4_scope_pass.zh-CN.md`：L4-scope pass 定义。
- `external_pattern_registry.jsonl`：外部 agent / RAG / workflow / observability 设计模式注册表。
- `financial_research_method_registry.jsonl`：金融研究方法注册表。
- `financial_research_method_learning_ledger.jsonl`：金融研究方法学习候选台账；只登记 source discovery / qualification，不代表已进入 active registry。
- `agent_engineering_pattern_learning_ledger.jsonl`：Agent 工程模式学习候选台账；只登记可吸收模式、边界和目标合同，不代表已完成 runtime 改造。
- `financial_research_method_extraction_ledger.jsonl`：从候选资料抽出的可执行金融研究方法；仍是候选，不等于 active playbook。
- `agent_engineering_pattern_extraction_ledger.jsonl`：从候选资料抽出的可执行 agent 工程模式；仍需 contract translation 和 deterministic proof。
- `p32_l1_coverage_matrix.jsonl`：P32 L1 source coverage matrix；说明哪些能力域已够做初始 L3、哪些仍需继续补 source。
- `p32_l3_contract_translation_ledger.jsonl`：P32 L3 contract translation ledger；把 L2 extraction rows 映射到 FIN runtime/agent/data/eval 合同。
- `p32_active_registry_promotion_ledger.jsonl`：P32 registry promotion ledger；只有通过 L4 no-paid fixture 的合同可进入 `active_registry_ready`，新增 gap-domain 合同默认保持 `deferred_pending_l4_fixture`。
- `../internal/vnext_20260610/p32_l4_ai_semis_deterministic_fixture_report.zh-CN.md`：P32-L4 no-paid deterministic fixture 报告；证明 L3 contracts 在 AI/Semis case 下能改善 thesis path / required-item plan / writer-ready material，但不证明 paid memo 质量。
- `p33_execution_plan_ledger.jsonl`：P33 execution plan ledger；把 P32 closeout、runtime assimilation、AI/Semis gold workpaper、Workbench dogfood、model comparison、vertical expansion 和 enterprise productization path 拆成可维护阶段，作为上下文压缩后的恢复锚点。
- `p34_ai_semis_lane_research_quality_rubric_v0_1.json`：P34 AI/Semis lane research quality rubric；先定义“什么叫研究质量合格”，再倒推 source route/parser。
- `p34_ai_semis_judgment_chain_registry_v0_1.json`：P34 AI/Semis judgment chain registry；把 humanmade gold answer 转成 Research Lead / specialist / JudgmentCard / MemoLogicPlan 必须回答的判断链。
- `p34_ai_semis_evidence_slot_contract_mapping_v0_1.json`：P34 AI/Semis evidence slot contract mapping；把 P33 20 条 AI/Semis source-runtime rows 映射到 judgment chain、required fields、forbidden substitutes 和 promotion rule。
- `p34_ai_semis_source_route_plan_v0_1.json`：P34 AI/Semis source route plan；把 20 条 evidence slot 绑定到 primary/fallback source route、adapter family、parser output contract 和 typed gap taxonomy。该文件是 route plan，不代表 adapter execution、parser lineage 或 live runtime readiness。
- `p34_ai_semis_adapter_fixture_report_v0_1.json`：P34 AI/Semis adapter fixture report；首批验证 SEC 8-K earnings release table、official product spec page 和 semicap bookings/backlog 三类 adapter family 的 parser contract fixture，输出 normalized runtime rows、parser lineage、authority scope、cannot-infer 和 rejected false substitutes。该文件不是 live fetch/crawler/parser readiness。
- `p34_ai_semis_no_paid_quality_audit_v0_1.json`：P34 AI/Semis no-paid quality audit；检查 route plan 与 adapter fixtures 是否足以回答 7 条 judgment chain。当前状态为 blocked，禁止 paid writer / full-chain / model comparison / case expansion。
- `p34_execution_plan_ledger.jsonl`：P34 execution plan ledger；记录 quality-first source-runtime program 的阶段、边界和下一步，不代表 runtime/source route 已完成。
- `thread_handoff_20260708_p34_ai_semis_fact_table_alignment.zh-CN.md`：当前长线程交接文档；用于新窗口恢复 P34 AI/Semis fact-table projection、goldcase availability alignment、禁止事项、最新验证和下一步。
- `p35_ai_infra_decision_surface_framework_v0_1.json`：P35 AI infra supervisor dogfood 的目标研究框架；把用户题面固化为 5 个产业链环节、12 个判断维度和 60 个 decision cells，要求每格包含判断、关键数字、source grade、numeric sanity、cannot infer 和 what-would-change。
- `p35_ai_infra_current_system_gap_audit_v0_1.json`：P35 对当前 P34 runtime rows、fact-table projection 与 WorkBuddy 9 个样本的 gap audit；记录 25 个缺失 decision-surface cells 和 5 个 root causes。该文件不代表 paid/full-chain 通过。
- `p35_ai_infra_source_supplement_ledger_v0_1.json`：P35 supervisor 为 AI 基建五链条报告补充的公开源 ledger；当前用于报告和后续 runtime ingestion 计划，状态为 `source_supplement_only`，不是 accepted runtime rows。
- `p36_agent_dogfood_ruler_v0_1.json`：P36 Codex-as-paid-model manual full-chain dogfood 的双标尺；同时约束投研质量和 agent 产品工程质量，并声明 writer 不得自发补源、supervisor 补源必须另行 ledger。
- `p36_supervisor_source_supplement_ledger_v0_1.json`：P36 Node10 supervisor 补源 ledger；记录 NVIDIA、Dell、SMCI、HPE、TSMC、SK hynix、Samsung、Micron、ASML、AMAT、LRCX、KLA 和 BIS 等公开源。状态为 `supervisor_supplement_only`，不是 accepted runtime rows。
- `p36_verifier_workbench_review_v0_1.json`：P36 Node11 verifier / Workbench 手工审查 artifact；判定 runtime-only writer 只能 bounded partial，supervisor-augmented report 可作人工报告但不算 runtime 能力，现有 verifier / Workbench 可守 claim/gap/source 边界但缺 decision-cell review surface。
- `p36_manual_full_chain_node_ledger_v0_1.json`：P36 逐节点手工 full-chain dogfood 账本；记录每个节点读过的 prompt/skill/artifact、手工输出、ruler 评分、root-cause notes 和下一节点。当前已记录 node 01 Research Lead、node 02 Retrieval/RAG/SQL/SourceRoute、node 03 Parser/EvidenceOperator、node 04 Graph/Relationship/Value-Capture、node 05 Fundamental Specialist、node 06 Product/Industry Specialist、node 07 Market/Capital/Price-in Specialist、node 08 Risk/Counterevidence Specialist、node 09 Aggregate/Judgment Planner、node 10 Writer/Report Generation、node 11 Verifier/Workbench Review；Node11 证明边界可审，但 P36 仍缺 `DecisionSurfacePack` 与 Workbench `decision_surface_cell` review surface，不能记为 runtime pass。
- `full_chain_preflight_checklist.json`：full-chain 预检 checklist。

## 使用规则

1. 不依赖聊天记忆判断项目状态。
2. 不用新 worklog 替代 source-of-truth 文档更新。
3. 不用 full-chain 发现 deterministic/node-level 能发现的问题。
4. 不用 gate/fallback 代替 root-cause 修复。
5. 不把 token 降低本身当成目标；目标是更高的信息传导效率和更好的判断质量。
6. 外部方法/技术参考必须先进入 learning ledger，再经过 extraction、contract translation 和 deterministic proof，不能因为“看过资料”就直接改 runtime 或宣布吸收完成。
