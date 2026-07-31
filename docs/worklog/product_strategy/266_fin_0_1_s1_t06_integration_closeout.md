# FIN 0.1 S1-T06 独立集成收口

日期：2026-07-20
任务：`S1-T06 independent_S1_integration_closeout`
Disposition：`pass_S1_fixture_mainline_connected_no_real_agent_quality_or_release_claim`

## 1. 问题与授权

用户明确授权只执行 S1-T06：完成当前 slice 的 fast/component/browser 收口，核验模型、网络、外部工具和真实业务写入仍为 0，确认成功与失败 Run 的事实一致，并在 S1 closeout 停止。未授权 S2、真实模型/provider/network、付费或商业数据、真实业务 Case mutation、release candidate 或 production cutover。

T06 不新增产品功能或平行 Runtime/Registry/Writer/store/gate family；目标是独立判断 T01-T05 形成的主线能否以 fixture-only 范围关闭。

## 2. 首轮独立评审与唯一修复

首轮 fast/component 回归和成功 Run browser 检查通过，但旧大 Case 的失败事实虽然正确，Workbench 会被一个历史 `pending` WorkUnit 触发每 700ms 整包刷新。失败检查器短暂显示 `FAILED / agent_fixture_shadow_profile_error:ValueError / 0 artifacts / no deterministic fallback` 后重新进入 loading，DOM 无法稳定截图或人工检查。

最早 owned root cause 位于 `NextCaseWorkspace` 的轮询条件：它把 Case 下任意 `pending|running` WorkUnit 都当作当前 S1 执行，不区分历史 dormant WorkUnit 与本页刚入队的 ResearchRun。

唯一一次修复：

- 自动轮询仅在 canonical ResearchRun 为 `pending|running` 时继续；
- Run 尚未建立的短暂窗口，仅允许本页刚成功入队的执行开启轮询；
- 当前执行终止后自动关闭 polling；
- 历史无关 pending WorkUnit 不再使只读成功/失败投影反复卸载。

新增 `tests/contract/test_fin_0_1_s1_t06_integration_closeout.py` 固定该边界。修复后失败检查器跨 4 秒稳定窗口保持同一 DOM/事实，点击“刷新当前视图”完成完整 loading -> ready 周期后仍稳定。

## 3. 收口回归

修复后按三组非重叠集合完整复跑：

```text
S1 T02-T06 + Workbench/P02 execution fast:          27 passed in 41.50s
canonical facade/scheduler/recovery/checkpoint:      36 passed in 12.56s
Agent/Skill/LangGraph + code mainline manifest:      79 passed in 65.41s
合计（无重叠）:                                     142 passed
```

前端：

- TypeScript strict：pass；
- Vite production build：`1695 modules transformed`；
- 既有大 chunk warning 保留为 bundle-size debt，不影响本 slice 正确性。

第一次直接执行 `npm run build` 因当前 PowerShell 无全局 `npm` 而未运行；随后使用 Codex 工作区自带 Node 分别执行 TypeScript 与 Vite，二者均通过。这是环境路径问题，不是代码失败。

## 4. Browser 功能、视觉与探索性复核

使用本机 Chrome 与正常 UI 控件完成 desktop `1600x900`、mobile `390x844` 检查：

- 成功 NVDA Agent fixture Run：`succeeded`，停止原因为 `agent_fixture_shadow_complete_cell_succeeded`，9 Agent trace、23 lifecycle events、7 exact artifacts；
- 主清单可见 exact digest、producer Attempt、RunVersion/input refs 和 payload；
- 失败 Run：`failed`，停止原因为 `agent_fixture_shadow_profile_error:ValueError`，7 lifecycle events、0 artifacts，并明确显示未复用确定性输出；
- 通过刷新控件验证失败页完整 loading -> ready -> 稳定周期；
- 通过 Profile 控件在 deterministic failed 与 Agent succeeded 间来回切换；
- 通过 Artifact 控件切换到 Trace 并确认 payload 与 digest 精确对应；
- desktop/mobile 均无页面级横向溢出，page errors=`0`；mobile `scrollWidth=clientWidth=390`；
- 未发现 clipping、不可读对比、长 ID 页面级溢出或失败态被 fallback 覆盖。

截图（本地视觉证据，不纳入仓库）：

- `C:\Users\hht13\.codex\visualizations\2026\07\19\019f7a6e-49de-7623-ba66-0f17e50c8a38\t06\t06-desktop-success-manifest.png`
- `C:\Users\hht13\.codex\visualizations\2026\07\19\019f7a6e-49de-7623-ba66-0f17e50c8a38\t06\t06-desktop-failure-fixed.png`
- `C:\Users\hht13\.codex\visualizations\2026\07\19\019f7a6e-49de-7623-ba66-0f17e50c8a38\t06\t06-mobile-success-top.png`
- `C:\Users\hht13\.codex\visualizations\2026\07\19\019f7a6e-49de-7623-ba66-0f17e50c8a38\t06\t06-mobile-success-manifest.png`

Playwright session 已关闭；进入 T06 前已存在的本地 Workbench dev server 在当前代码上重启并继续保留，fixture store 未清空。

## 5. 实际调用与写入计数

成功 Agent fixture manifest 与合同测试共同给出：

```text
model_calls                    0
provider_calls                 0
network_calls                  0
external_tool_calls            0
fixture_tool_observations      1
business_writes                0
adapter_direct_canonical_writes 0
real_business_case_mutations   0
evidence_promotions            0
release_admissions             0
```

“真实业务写入为 0”不等于所有持久化写入为 0。S1 的目的就是验证 canonical execution ledger：成功链预期并确实写入 WorkUnit、Attempt、ResearchRun、23 events 和 7 artifacts；这些写入由既有 RuntimeFacade/store owner 完成，adapter direct canonical writes 为 0。T04/T06 回归在已建立 fixture Case/plan 后比较业务表快照，证明执行没有修改真实业务 Case 对象。

## 6. 效果与裁决

- 产品能力增量：S1 的一条浏览器 -> API v1 -> `ExecutionService` -> `Fin01ResearchRuntime` -> canonical Run/Event/Artifact -> Workbench projection 主线现在可稳定检查成功与失败事实；
- 研究质量增量：`0`。Agent 输出仍是 deterministic fixture shape，没有真实信息增量、研究深度或 Human value 证据；
- 主线消费证据：成功与失败使用同一 runtime/profile/lineage 规则，失败无 artifact、无 deterministic fallback；
- 治理成本增量：一个轮询 root-cause 修复、一个 focused T06 合同和本工作日志；未新增平台或 authority family。

S1-T06 acceptance=`3/3`，S1 以 `fixture_mainline_connected_only` 关闭。S1 不是真实 Agent 质量证明、RG1/RG3/RG4 证明、release proof 或 production readiness。

## 7. 后续与回滚

当前必须停止，不进入 S2。S2 的第一次 bounded real-agent cell 仍需用户单独明确授权 model/provider/network/budget preflight。

若轮询修复需要回滚，只回退 `WorkbenchNext.tsx` 的 `executionPolling` 限定和对应 T06 合同；canonical store、Run/Event/Artifact、fixture Case 数据和 API authority 均无需回滚。Git worktree 在进入 T06 前已有未提交 S1 改动，本轮保持未暂存、未提交，避免混入未经用户指定的仓库提交。
