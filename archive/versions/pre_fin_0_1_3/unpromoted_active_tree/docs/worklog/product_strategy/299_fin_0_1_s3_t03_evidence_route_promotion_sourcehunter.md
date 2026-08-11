# FIN 0.1 S3-T03 Cell-driven Evidence Route / Promotion / SourceHunter Boundary

日期：2026-07-21

状态：`pass_cell_driven_evidence_route_promotion_and_sourcehunter_boundary`

## 用户指令与权限

用户连续要求“继续”，本轮只执行当前唯一下一项 `S3-T03`。授权范围是零调用本地 fixture、同一 Runtime/Run 的 Evidence route 控制面、确定性测试、Project OS 和 staging；不授权 T04、模型/provider、来源网络、外部工具、真实业务 Case mutation、新 live admission、paid run、S4、release 或 production。

## 问题与根因

`RC-P36-022` 的最早缺口是已有 BM25、SQL、Graph、market/ownership 资产仍按来源槽组织，没有由 exact Cell/Branch/EvidenceRequest 驱动，也没有把 Candidate、Graph context、typed gap、promotion authority 和 SourceHunter 网络权限分开。

T03 没有把 metadata fixture 冒充 Evidence。实现明确保留：

- demand route 仍需 claim-scoped source content 和 corroboration；
- revenue route 仍需 T04 parser/Numeric lineage；
- Graph observation 只能作为 navigation hypothesis，并创建 underlying official-source follow-up；
- SourceHunter 只形成 proposal，必须另行获得 exact network admission。

## 实现

`EvidenceService` 新增 `fin01.s3.evidence_route_plan_three_cell:v1`，从 T02 RuntimePlan、accepted DecisionSurface、exact WorkUnit 和三个 Evidence Operator ContextPlan 编译：

1. demand：本地 official-disclosure Object BM25 -> materialized customer deployment context；
2. value/profit：本地 Gold SQL financial table -> official filing table address；
3. counterevidence：本地 relationship Graph navigation -> local official-source follow-up。

每个 planner step 都先生成 ToolGateway preflight，检查 registry、planning allowlist、network requirement、data scope、budget 和 input contract；结果始终是 `checks_pass_execution_not_admitted`，invocation=`not_executed`。permission 缺失会在工具前形成 typed stop。

三份 CandidateBundle 进入独立 promotion assessment。当前 accepted Evidence=0、runtime promotion=0、Writer citable=0。反证 Graph observation 生成一份 local source follow-up，但没有执行；SourceHunter boundary 为 `proposal_only_blocked_missing_separate_network_admission`。

`Fin01ResearchRuntime` 只在 deterministic profile 内消费该 plan，并将 plan 与三份 consumption receipts 写入原 `deterministic_research_result` Artifact。S2 bounded 与历史 Agent profile 不消费新计划，已消费 identity/Artifact 未改写。

## 独立复核修复

首版复核发现三项缺口：

- counterevidence 继承旧 Point03 单 route 预算，Graph 后的 official-source follow-up 未进入计划；修为本 Cell 两步预算；
- WorkUnit scope 需精确校验 tenant/project/state/DecisionSurface lineage；已补 fail-closed；
- 只校验外层 shape 不足；消费端现重算 request、tool plan、snapshot、bundle、preflight、promotion、Graph、follow-up、SourceHunter、cell route 与总 plan 的 digest/identity。

## 变更与验证

- Evidence owner：`apps/workbench/backend/application/evidence_service.py`；
- Runtime injection：`apps/workbench/backend/application/research_runtime.py`；
- composition：`apps/workbench/backend/app.py`；
- 机器结果：`configs/releases/fin_ia_0_1_s3_t03_evidence_route_promotion_sourcehunter_v1_0.json`；
- 合同/节点测试：`tests/contract/test_fin_0_1_s3_t03_evidence_route_promotion_sourcehunter.py`；
- focused Runtime/T02/T03/Project OS：`32 passed in 23.97s`；
- expanded Planning/Runtime/Gateway/S1/S2/S3/Workbench/Project OS：`160 passed in 98.20s`。

本轮 model/provider/execution network/source network/external tool/live business write/runtime Evidence promotion/new live admission/paid or live ResearchRun 全部 0。测试只在临时 isolated canonical store 中创建 deterministic fixture Run，不证明实时检索、SourceHunter、新事实、研究质量或 NVDA R2。

下一项是 `S3-T04-DETERMINISTIC-FINANCIAL-NUMERIC-AND-FUNDAMENTAL-DECISION-CELL-PACK`，等待用户单独继续。
