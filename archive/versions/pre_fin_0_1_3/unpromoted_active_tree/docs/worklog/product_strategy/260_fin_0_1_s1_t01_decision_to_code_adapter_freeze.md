# 260 FIN 0.1 S1-T01 决策到代码适配冻结

日期：2026-07-19
状态：`superseded_by_v1_1_after_independent_review_repair`

> 2026-07-19 独立复核首轮给出 `changes_requested_before_acceptance`。原机器清单 v1.0 已由 v1.1 替换；修订内容和二次复核见 `261_fin_0_1_s1_t01_review_repair_and_reacceptance.md`。本文件保留首轮 freeze 事实，不作为当前接受合同。

## 问题

按 FIN 0.1 Program Plan 第一个可执行项 S1-T01，核验当前 Workbench UI、API v1、application services、canonical runtime 与历史 Agent/Skill/Tool/Graph 的真实 producer/consumer 关系，把 D02-D14 决策冻结为 retain/refactor/absorb/retire adapter map，并确认唯一 Runtime/API/UI 写入主线。

本轮授权仅限 fixture/shadow adapter 设计与确定性检查；不允许模型、provider、network、paid/full-chain、商业数据、真实业务 Case mutation、release candidate 或 production cutover。

## 判断与决策

1. 当前真实执行写入口是 `ActivityTrace -> ExecutionApiClient -> API v1 execution -> ExecutionService -> RuntimeFacade`；Workbench Next 主要聚合读取并合成事件，不拥有 exact ResearchRun/Profile。
2. `P36LocalResearchService` 是 `bounded_local_read_only / bounded_local_deterministic_preview`，代码明确声明 model/network/external tool/canonical write 均为 0；它只能进入 `deterministic_fallback` adapter。
3. 历史 LangGraph、Agent Registry、Research Skills、Lead/Specialist/Memo LLM、Tool Controller 和 relationship graph 未被当前 API v1/Workbench Next 消费；它们保留为 reuse candidates，经 `agent_fixture_shadow` adapter 接入，不能成为另一产品入口。
4. 唯一产品 runtime 冻结为 planned `apps/workbench/backend/application/research_runtime.py::Fin01ResearchRuntime`。它是 existing `RuntimeFacade` 上的 application adapter；profile adapters 必须 canonical-write-pure，只有 Runtime 可以统一提交 exact Run/Event/Artifact。
5. existing `SQLiteCanonicalStore`、`FileCanonicalObjectStore`、Evidence Gate、Agent/Skill Registry、ContextEngine、Writer/Verifier 和 RG1-RG5 families 全部复用；不新建平行 family。
6. standalone DeepSeek runner 继续只是 release reproducibility tool；HumanBaseline 继续隔离，不自动成为 canonical review 或 R3 evidence。

## 完成工作

- 新增人工可读 adapter map：`docs/architecture/repository/FIN_0_1_S1_DECISION_TO_CODE_ADAPTER_MAP_20260719.zh-CN.md`；
- 新增机器清单：`configs/releases/fin_ia_0_1_s1_adapter_map_v1_0.json`；
- D02-D14 共 13 项均记录 current producer/consumer、逐资产 disposition、target modules、输入输出合同、unique owner、依赖、最小测试、风险与非目标；
- 冻结唯一写入路径：`Workbench -> Execution API v1 -> ExecutionService -> Fin01ResearchRuntime -> profile adapter -> existing RuntimeFacade/store/object store -> run-scoped projections -> Workbench`；
- 明确 T02/T03 只可在独立复核接受后解锁，当前 T02-T06 均不执行。

## 结果与证据

- S1-T01 disposition：`pass_for_independent_review_no_implementation_claim`；
- 当前产品主线仍为 `deterministic_local_p36_workbench_preview`；
- `agent_mainline_consumed=false`；
- 本轮 `model_calls=0`、`provider_calls=0`、`network_calls=0`、`commercial_data_calls=0`、`business_case_mutations=0`、`runtime_implementation_changes=0`；
- 没有创建 Runtime/Registry/Writer/store/gate family，没有删除或移动 Point 01 digest/path-stable assets；
- backlog 只推进 S1-T01 到 `ready_for_independent_review`，不把 T02/T03 改成 ready。

## 验证

计划并执行的最小检查：

- PowerShell `ConvertFrom-Json` 解析新 manifest 与现有 release contracts/backlog；
- D02-D14 exact id、允许的 disposition、required fields、非空 owner 和 single-mainline invariant；
- backlog stable source SHA-256 复核；
- referenced existing path 存在性检查，planned path 明确排除在 exists gate 外；
- `git diff --check`；
- candidate 文件的敏感信息模式扫描。

实际结果：5 份 JSON 和 2 份 JSONL 可解析；D02-D14 exact 13/13；stable source digest 9/9；existing path 34/34；T02/T03 均仍为 `pending`；`git diff --check` 无输出；S1-T01 新增记录未命中敏感信息候选模式。机器清单 SHA-256 为 `bf1ca153e583b2c6c68d3320b3c8499faea655ece9ebb701ffe828b1dfc74941`。

未运行：Python 产品测试、浏览器、模型、provider、network、paid/full-chain、真实 Case、商业数据、Human review、RG1-RG5 或 release job。原因是本任务是 docs/manifest freeze，且这些动作不在当前授权内。

## 后续与安全边界

独立复核应先检查：

1. `ExecutionService` 是否确实应继续作为唯一 API command owner；
2. `Fin01ResearchRuntime` 是否只是 existing `RuntimeFacade` 的 application adapter，而非第二 authority；
3. `ResearchRunVersion` 是否可在 existing store 内扩展且不破坏 Point 01 path/digest；
4. D03/D06 的 `relationship_graph` registry/test drift 是否按当前合同保留并修复测试；
5. 所有 profile adapter direct canonical business writes 是否保持 0。

复核接受后才可按 backlog 进入 T02/T03。S1 closeout 后仍必须停止并等待 S2 的模型/provider/network/预算单独授权。
