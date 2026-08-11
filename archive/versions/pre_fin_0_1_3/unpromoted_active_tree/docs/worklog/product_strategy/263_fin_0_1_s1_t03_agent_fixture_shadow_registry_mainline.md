# FIN 0.1 S1-T03 Agent Fixture Shadow / Registry Mainline

日期：2026-07-19
状态：`accepted_after_independent_review_repair`
范围：仅 S1-T03；不进入 T04、模型、网络、商业数据、真实业务 Case mutation、release 或 production。

## 结果

T03 已把历史 Agent 资产窄接入现有单一 `Fin01ResearchRuntime`：API v1 可通过 admitted `agent_fixture_shadow_entry` WorkUnit 选择 exact `fin01.execution_profile.agent_fixture_shadow:v1`；existing scheduler 创建独立 Attempt，existing RuntimeFacade/SQLite/ObjectStore 提交独立 ResearchRun、Run-scoped Events 与 `agent_fixture_shadow_result` Artifact。deterministic profile 的 API 返回形状、WorkUnit identity 和默认 Workbench 行为保持不变。

Agent shadow 真实调用 `src/sec_agent/langgraph_orchestrator.py`，但按 T03 边界只执行：

`load_session_state -> research_lead_plan -> validate_activation_plan`

它选择 `research_lead` 与 primary `industry_supply_chain_analyst` handoff，同时为 8 个 activation-plan Agent 读取现有 registry 合同并生成 content-addressed AgentDefinitionVersion；从现有 16 个 reviewed Skill 文件生成 SkillDefinitionVersion / SkillPackVersion。exact Agent/Skill refs、digest、Run/WorkUnit/Attempt/causation refs和 selected/injected/consumed 状态进入 3 个 canonical Run-scoped trace events及最终 Artifact。没有新增 Runtime、Registry、Writer、Graph、store 或 gate family。

## 真实性边界

- model/provider/network/external-tool calls：`0`
- adapter business Case mutation / Evidence promotion / release admission：`0`
- Agent failure：Run、Attempt、WorkUnit 保持 `failed`，不创建 Artifact，不自动生成 deterministic fallback
- deterministic 与 Agent shadow：不同 WorkUnit、Attempt、ResearchRun、Artifact 和 profile ref
- T03 不执行 Tool、Graph traversal、Specialist reasoning、Writer、Verifier 或 Renderer；这些仍属于 T04
- research quality delta：`none`

## 独立复核与一次工程修正

独立复核在同一允许的工程修正轮内关闭：

1. Case query 实际由 `CaseControlSummary` 持有，adapter 改为读取 exact summary ref，避免错误读取 ResearchCase。
2. 新 trace event 加入 deterministic replay schema，并投影到 `research_run_traces`。
3. 历史图早停仍会写 checkpoint summary；输出改到自动回收的临时目录，避免污染仓库。
4. 双 profile pending 调度改为后端内部按刚创建的 WorkUnit type 定位，不改变冻结的 P02 API v1 response fields。
5. deterministic WorkUnit ID 保持历史 canonical identity；仅 Agent shadow identity 增加 WorkUnit type，保证 distinct lineage。
6. RuntimeFacade 在 object write 前校验 profile 与 artifact type，trace event 标记为非状态推进事件。
7. 关闭已记录的 Agent Registry 测试漂移：`product_technology_analyst` 的只读 `relationship_graph` source-family 与现行合同一致；未授予工具、网络或写权限。
8. profile result 的 canonical commit 异常现在落同一 Run/Attempt/WorkUnit terminal failed，不再遗留 running 真相。

## 验证

- Python compile：通过
- T02 + T03 主线与失败真实性：`6 passed`
- T02/T03/P02 API compatibility 定向：`10 passed`
- T02/T03、P02 API/Frontend、RuntimeFacade、M5 scheduler/recovery/checkpoint、Agent Registry、Skill Registry、LangGraph routing：`96 passed in 84.67s`
- `git diff --check`：通过（仅既有 JSONL line-ending warnings）

## 后续

T03 disposition：`pass_agent_fixture_shadow_registry_and_early_langgraph_slice_connected_no_complete_cell_or_quality_claim`。

下一项是 S1-T04，仅在用户明确指令后运行一个完整 NVDA“需求真实性与持续性”fixture-shadow cell，并要求 Lead/Specialist/Skill/Tool/Graph/Writer/Verifier events 与同一 exact Run artifact lineage。当前不得把 T03 写成完整 Agent cell、Agent 质量、RG1/RG3/RG4、release 或 production proof。
