# 264 FIN 0.1 S1-T04 完整 Agent Fixture-Shadow Cell

日期：2026-07-19
状态：`accepted_after_independent_review_repair`
授权：仅 S1-T04 fixture-shadow；不含 T05、模型/provider/network、商业数据、真实业务 Case mutation、Evidence promotion、release candidate 或 production

## 1. 问题与决策

用户明确要求继续 S1-T04。唯一 backlog 要求在现有 `Fin01ResearchRuntime` 与 `agent_fixture_shadow` profile 内，运行 NVDA“需求真实性与持续性”一个完整 Cell，形成 Lead/Specialist/Skill/Tool/Graph/Writer/Verifier events，使 Evidence、Numeric、Judgment、Workpaper、Report、Trace 共享同一 Run，并证明 Agent 失败不能被 deterministic 输出掩盖。

本轮没有新建 Runtime、Registry、Writer、store 或 gate family。实现继续复用 T02/T03 的 HTTP 202 -> BackgroundTask -> ExecutionService -> existing scheduler claim -> Attempt -> ResearchRun -> profile adapter -> RuntimeFacade commit 主链。历史 LangGraph 以 deterministic fixture injectors 执行完整节点路径；真实模型、网络和外部工具保持禁止。

## 2. 完成内容

- `src/sec_agent/langgraph_orchestrator.py`
  - 新增一个完整 NVDA fixture-shadow Cell runner，执行 Lead planning、activation/reflection、relationship fixture、Evidence fixture tool observation、Specialist、Judgment aggregation、Writer、Verifier、Renderer 和 persist。
  - fixture relationship dependency injection 改为真正 override；存在 injector 时不再先执行真实 `invoke_mcp_tool`。
  - Writer/Specialist/Verifier 提供受控故障注入点，故障携带 typed stage，不记录异常消息或私有思维链。
  - fixture 临时 artifacts 仅写入 `TemporaryDirectory`，完成或失败后自动清理。
- `apps/workbench/backend/application/research_runtime.py`
  - 同一 `agent_fixture_shadow:v1` profile 从 early slice 推进为 complete one-cell adapter。
  - 记录 9 个 Run-scoped trace events：Agent versions、Skill consumption、LangGraph validation、Lead、Specialist、Tool、Graph、Writer、Verifier。
  - 返回主 manifest 加 Evidence、Numeric、Judgment、Workpaper、Report、Trace 六个子产物。
  - commit 前预计算 canonical ArtifactVersionID，把所有 self/cross-artifact refs 与 `ResearchRunVersion:v1` 写入 payload；不再保留不可解析的 helper 逻辑 ref。
  - Writer 阶段 typed failure 转为原 Run/Attempt/WorkUnit terminal failed；不创建 Artifact，不自动 fork deterministic fallback。
- `src/sec_agent/canonical_runtime/facade.py`
  - 现有 `complete_research_run` 支持一个 profile 的多 immutable artifacts 原子 envelope/head 提交，Attempt `output_refs` 覆盖全部 7 个 ArtifactVersionID。
  - profile -> exact artifact type set、条目类型、重复 type/ID、payload self/run lineage 均 fail closed。
  - replay 接受并投影新增的 6 类 T04 trace events及全部 artifact events。
- `tests/contract/test_fin_0_1_s1_t04_complete_agent_fixture_cell.py`
  - 成功路径以禁止调用探针证明 relationship fixture 不会触发真实 MCP tool；核验 9 类 trace、7 个 artifact、same Run/Attempt、canonical cross refs、replay 和业务表零变化。
  - Writer 节点失败路径核验 terminal failure、artifact=0、output_refs=0、无 child fallback。
- T03 contract 更新为接受 T04 后同一 profile 的完整产物集合，同时保留 Agent/Skill registry、distinct Run 和 failure truth 回归。

## 3. 独立复核与一次修复

首轮实现后的联合回归为 `98 passed`。随后按本 slice 唯一一次独立工程复核发现并修复：

1. relationship fixture injector 之前仍会先进入真实 MCP lookup 决策；改为 injector-first dependency override，并用抛错探针证明零外部调用。
2. 完整 Cell 仍复用 T03 的“只做 selection、不执行 graph/tool”metadata；改为准确的 T04 complete-cell boundary。
3. complete runner 为复用准备逻辑曾先运行一次 early graph，再运行完整 graph；改为只复用 selection/contract preparation，完整 LangGraph 仅执行一次。
4. 子产物间只共享 helper 逻辑 ref，后续 Workbench 无法直接解析 canonical object；改为 commit 前 exact ArtifactVersionID binding，并在 Facade 再次验证 payload/envelope/run 一致性。

修复后 T02-T04 定向为 `9 passed`，mainline manifest 为 `4 passed`；最终联合回归：

```text
102 passed in 83.95s
```

覆盖 T02-T04、Point 02 execution/API compatibility、Point 01 facade/scheduler/recovery/checkpoint、Agent/Skill registry、历史 LangGraph routing 和 mainline manifest。

## 4. 产品与研究效果

- 产品能力增量：后端唯一 Runtime 现在可以完成一个完整 Agent fixture-shadow Cell，并得到可重放的 exact events/artifacts，而不再只停在 activation validation。
- 主线消费证据：同一 WorkUnit -> Attempt -> ResearchRun 中存在 9 个 causation-linked trace events、7 个 immutable artifacts；Artifact payload self/cross refs、Artifact envelopes、Attempt output refs 和 replay 一致。
- 失败真实性：Writer failure 保持 Agent Run failed，不会被 deterministic preview 覆盖或显示为 Agent success。
- 研究质量增量：`0`。结论、Evidence、Numeric、Graph 和 Report 都是 deterministic fixture shape，只证明合同与编排；不证明真实 Specialist、信息增量、研究深度或 Human 价值。
- 治理成本增量：扩展现有 profile、trace allowlist 和 multi-artifact completion；未增加平台家族、权限/receipt、release gate 或新 store。

## 5. 边界、回滚与下一步

- 实际计数：model=0、provider=0、network=0、external tool=0、real business Case mutation=0、Evidence promotion=0、release admission=0；fixture tool observation=1。
- exact Human Senior Review=0；RG1/RG3/RG4 不变，production readiness 仍 `not_admitted`。
- Workbench UI 仍默认 deterministic；Profile、structured events、exact artifacts 与 typed stop reason 的中文 UI/浏览器验证属于 S1-T05，本轮没有开始。
- 回滚边界是 T04 对 `research_runtime.py`、`langgraph_orchestrator.py`、`facade.py`、T04/T03 contracts 和本轮台账更新的增量；不得 reset/clean T01-T03 或用户既有工作树。
- 下一动作：等待用户明确授权 S1-T05；不得自动进入。
