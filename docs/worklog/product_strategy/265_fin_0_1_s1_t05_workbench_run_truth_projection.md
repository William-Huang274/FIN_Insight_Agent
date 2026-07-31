# 265 FIN 0.1 S1-T05 Workbench Run Truth Projection

日期：2026-07-20
状态：`accepted_after_independent_review_repair`
授权：仅 S1-T05；不含 T06、模型/provider/network、商业数据、真实业务 Case mutation、Evidence promotion、release candidate、production 或 S2

## 1. 问题与决策

T04 已在同一 `Fin01ResearchRuntime` 中形成完整 NVDA 单 Cell `agent_fixture_shadow` Run，但中文 Workbench 只能看到 deterministic preview 和合成事件，不能检查 exact Profile、Run status、9 条 Agent trace、7 个 immutable artifacts 或 typed stop reason。

T05 没有新增 Runtime、store、Registry、Writer 或 gate family。实现只在现有 `ExecutionService` 增加一个 tenant/project/case scoped 的只读 projection，并让 Workbench Next 消费该 projection。Workbench 的新执行动作只允许 `agent_fixture_shadow_entry`，仍要求 accepted planning checkpoint；deterministic preview 保持只读。

## 2. 完成内容

- `GET /api/v1/cases/{case_id}/execution-projection`
  - 投影 exact ResearchRunVersion、WorkUnit、Attempt、Profile、state、typed terminal reason、Run-scoped events、Attempt output refs 和 immutable Artifact payload。
  - Event 必须与同一 Run/WorkUnit/Attempt 绑定；Artifact 集合必须与 Attempt `output_refs` 完全相等，否则 fail closed。
  - payload 通过 ObjectStore digest 校验后读取；private chain-of-thought、hidden/private reasoning、internal monologue 和 scratchpad 类字段递归遮蔽，并明确 `private_chain_of_thought_included=false`。
- Workbench Next
  - 明确区分“本地确定性预览”和“Agent 编排影子（Fixture）”，展示 exact profile ref 和 Run 状态。
  - accepted checkpoint 下可发起唯一 Agent fixture-shadow WorkUnit；不提供模型、网络、retry/resume 或 deterministic operational run 权限。
  - 运行页展示全部 canonical lifecycle events，并把其中 9 条 Agent trace 单独计数；每条事件可展开检查结构化字段，不显示私有思维链。
  - “运行检查”支持 Run 切换、typed stop reason、7 个 Artifact 列表、ArtifactVersionID、digest、producer Attempt、input refs 和 exact JSON payload。
  - 失败 Run 显示真实 terminal reason、0 Artifact，并明确“未复用确定性输出”。

## 3. 独立复核与一次修复

首轮 API、前端合同和 production build 通过后，独立工程/视觉复核发现并在同一次 repair iteration 内关闭：

1. Artifact 列表按钮继承旧全局白色文字，在浅色背景对比度不足；新 Profile/Run/Artifact 控件显式锁定正文色。
2. 390px 移动视口下长 typed stop reason 与三列 outcome action 造成横向溢出；移动布局改为两列换行，long token 可断行。
3. projection 最初按 Attempt 聚合 Artifact，但没有再次证明其集合等于 Attempt output refs；增加 exact set equality 和 event WorkUnit/Attempt lineage fail-closed。
4. private-field filter 扩展到 hidden/private reasoning 和 reasoning trace，并增加递归遮蔽合同测试。

## 4. 验证

合同与相关回归按等价三组执行，避免单进程超过本地 120 秒上限：

```text
T02-T05 + P02 API/Workbench:                         26 passed in 48.30s
canonical facade/scheduler/recovery/checkpoint:      36 passed in 11.76s
Agent/Skill/LangGraph + code mainline manifest:      79 passed in 53.42s
合计（无重叠）:                                     141 passed
```

TypeScript strict 通过；Vite production build 为 `1695 modules transformed`。chunk size warning 是既有 bundle-size debt，不是 T05 功能失败。

Playwright 使用本机 Chrome，通过正常 UI 控件完成：

- desktop `1600x900`：Profile 切换、Agent run、9 Agent trace、结构化事件展开、7 Artifact 切换、Report/Trace exact payload 与 stop reason 均可检查。
- mobile `390x844`：Profile cards、Run timeline、Artifact list/detail 和长 ID/digest 可读；Artifact inspector `scrollWidth=clientWidth=390`，无元素越界。
- Agent success：`terminal_reason=agent_fixture_shadow_complete_cell_succeeded`，9 Agent trace / 23 lifecycle events / 7 artifacts。
- Agent failure（旧非 NVDA demo Case）：`terminal_reason=agent_fixture_shadow_profile_error:ValueError`，7 lifecycle events / 0 artifacts / no deterministic fallback。
- JS `pageerror=0`。专用 NVDA success seed 没有 T05 之外的 Evidence/Workpaper/Deliverable read models，因此浏览器按既有 optional-view 机制记录相应 404 并在“可选视图错误”中诚实显示；execution projection、Run/Event/Artifact 检查本身为 200 且不受影响。

本地截图（不纳入仓库）：

- `C:\Users\hht13\.codex\visualizations\2026\07\19\019f7a6e-49de-7623-ba66-0f17e50c8a38\t05\t05-desktop-run.png`
- `C:\Users\hht13\.codex\visualizations\2026\07\19\019f7a6e-49de-7623-ba66-0f17e50c8a38\t05\t05-desktop-artifact-inspector-fixed.png`
- `C:\Users\hht13\.codex\visualizations\2026\07\19\019f7a6e-49de-7623-ba66-0f17e50c8a38\t05\t05-mobile-run-fixed.png`
- `C:\Users\hht13\.codex\visualizations\2026\07\19\019f7a6e-49de-7623-ba66-0f17e50c8a38\t05\t05-mobile-artifact-inspector.png`

## 5. 产品与研究效果

- 产品能力增量：用户现在可以从中文 Workbench 发起并检查一个完整 Agent fixture-shadow Run，辨认它与 deterministic preview 的 Profile 差异，并回放 exact events/artifacts/stop reason。
- 研究质量增量：`0`。该 Run 仍是 deterministic fixture shape，不证明真实 Agent、Specialist 信息增量、研究深度或 Human 价值。
- 主线消费证据：Browser -> existing ExecutionApiClient -> API v1 -> ExecutionService -> existing single Runtime -> canonical Run/Event/Artifact -> Workbench read projection 完整闭环。
- 治理成本增量：一个只读 projection、现有 Workbench 两个局部 surface 和一个 T05 合同测试；未增加平台、store、gate、registry 或权限家族。

## 6. 边界与下一步

- model/provider/network/external tool/real business Case mutation/Evidence promotion/release admission 均为 0；fixture tool observation 仍为 1。
- exact Human Senior Review=0；RG1/RG3/RG4、release 与 production 状态不变。
- S1 尚未关闭。下一项仅为 S1-T06：fast/component/browser 最小 closeout、调用/写入计数核验和独立 S1 收口；必须等待用户明确指令。
- 不得把 T05 写成真实 Agent 质量、S2、release proof 或 production readiness。
