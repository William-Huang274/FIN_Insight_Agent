# 061 P30 Workbench Product Surface Redesign Follow-up

## 背景

当前 B04 的工程入口已经基本齐备：Workbench 能展示 P27 reviewer package、session readiness、evidence form、candidate refs 和 trace/drilldown。但用户指出现有 Workbench 仍然太像工程调试台，和 Codex、Claude Code、Coze、Dify 等成熟产品的前端体验相比差距明显。

这个判断成立。当前前端主要证明 API、manifest、gate、trace、package 和 evidence 写入路径可用；它不等于 B 端 analyst 每天愿意使用的产品工作台。

## 记录决策

P30 最初作为 B04 之后的产品化 follow-up 记录，不阻塞当时的 B04 真实产品验收推进。当时优先级仍是完成 B04 real reviewer acceptance。

2026-07-01 update：用户已明确认可 B04 closeout packet，因此 B04 formal evidence 写入
`data/manifests/r53_r60_p24_b04_real_reviewer_acceptance_evidence_v0_1.jsonl`，P24 重新构建为
`closed_by_real_human_product_acceptance`，P21 重新构建为 `blocker_count_open=0` /
`full_chain_broad_eval_allowed=true`。P30 随后进入首版实现，不再只是后续记录项。

## P30 问题定义

现有 Workbench 的主要问题：

- analyst 主界面和 admin / ops console 混在一起；
- 太多 raw gate、manifest、package_status、artifact_ref_id 暴露在用户主流程中；
- task progress、agent workstream、evidence、gap、repair、deliverable、review 的关系不够直观；
- reviewer 虽然能提交 evidence，但产品体验不像真实审稿/批注/退回/批准流程；
- Deliverable Studio、Workpaper Builder、Evidence Drawer、Gap/Repair Queue 还没有形成成熟 UI；
- 当前视觉和交互只能支撑工程验收，不适合直接作为最终 B 端产品验收标准。

2026-07-01 front-end product debt after P30 v0.1：

- 真实任务数据下的密集态设计还未验证：full-chain 任务可能产生几十个 ClaimCards、evidence rows、typed gaps、review actions、deliverable artifacts 和 concurrent tasks；当前 UI 只证明少量/空态可读，尚未证明高密度下的分组、过滤、折叠、排序、pin 和搜索足够好用。
- 图谱/证据可视化未完成：后端已有产品关系、供应链、客户部署、竞争、资本、source authority 等图谱/边，但前端仍主要是表格和文字；用户还不能直观看到 `thesis -> claims -> evidence -> source authority -> gaps/counter evidence` 或 `company/product -> customer/supplier/competitor/read-through`。
- 批注体验仍偏原型：现在是 textarea + approve/repair/comment；真实审稿需要对 memo 段落、ClaimCard、evidence row、gap item 单独批注、指派、降权、退回，并写入 append-only WorkpaperEvent。
- 统一设计系统未完成：旧工程面板、新 P30 面板、表格、按钮、状态 pill 仍混在同一页面；需要统一 TaskCard、EvidenceRow、ClaimCard、GapItem、GateStatus、ArtifactCard、颜色语义、spacing、加载/空态/错误态。
- 信息层级还不够彻底：analyst 默认应先看到任务状态、核心判断、关键证据、关键缺口和下一步动作；source id、artifact ref、gate row、trace、raw manifest 等应默认进入 admin/ops drilldown，而不是挤在主流程里。

## 初步方向

后续 P30 应拆成两个界面层：

1. Analyst Workbench
   - Dashboard / Watchlist；
   - Research Task Center；
   - Task Detail；
   - Workpaper Builder；
   - Evidence Drawer；
   - Gap / Repair Queue；
   - Deliverable Studio；
   - Review / Approval。

2. Admin / Ops Console
   - trace；
   - eval；
   - parser status；
   - source coverage；
   - token / cost / latency；
   - queue；
   - incident；
   - raw manifests。

## 首版实现

P30 v0.1 把 `R53R60WorkbenchPanel` 从 raw engineering table surface 改成四个明确 surface：

- `Analyst`：Task queue + Workpaper canvas + Evidence drawer，优先展示 Lead judgment、Judgment state、Workpaper outline、ClaimCards、Typed gaps 和 Review actions。
- `Review`：Product acceptance evidence、reviewer package、pilot dogfood window，继续保留真实 reviewer evidence 写入路径。
- `Deliverables`：Deliverable Studio、Dashboard Projection、quality gates 和 artifacts。
- `Ops`：Ops projection、gate rows、scope gate 和 system-health style metrics。

同时修复一个 P30 root-cause UI 问题：当 runtime task ledger 暂无投影任务时，旧代码会提前返回“等待 S6 投影”，导致新产品工作台完全不渲染。现在 P30 壳层始终可见，并在 task rail 中显示明确空态，避免后续 QA 误判为前端缺失。

## 验收记录

- TypeScript + Vite build：通过。
- Playwright element-level visual QA：通过。
- 已验证 surface：`Analyst` / `Review` / `Deliverables` / `Ops`。
- 已验证旧空态移除：`等待 S6 投影` 不再出现在 P30 面板 body 中。
- 定向后端回归：`tests/test_r53_r60_product_acceptance_b04_gate.py`、`tests/test_r53_r60_b04_reviewer_acceptance_package.py`、`tests/test_workbench_backend.py` 共 `44 passed`。
- 回归中暴露并修复一个非 P30 UI 的 deterministic fixture 问题：`test_workbench_backend_prunes_terminal_run_history` 过去依赖秒级墙钟生成两个 terminal run 的排序，运行跨秒时会把 `keep_latest=1` 的保留对象反转。现在测试显式设置 `created_at` / `updated_at` / `started_at` / `finished_at`，保持生产 `updated_at` pruning 语义不变，同时让测试稳定可复现。
- 截图：
  - `D:/temp/finsight_p30_qa/p30_panel_desktop_analyst.png`
  - `D:/temp/finsight_p30_qa/p30_panel_desktop_review.png`
  - `D:/temp/finsight_p30_qa/p30_panel_desktop_deliverables.png`
  - `D:/temp/finsight_p30_qa/p30_panel_desktop_ops.png`
  - `D:/temp/finsight_p30_qa/p30_panel_mobile_analyst.png`

## 与 B04 的关系

B04 已由真实产品 owner 明确认可并进入 formal evidence ledger。P30 不再作为 B04 blocker，而是作为产品可用性首版修复：它解决“可审计链路已经可用，但前端还像工程调试台”的问题。

边界：P30 v0.1 只改造 R53-R60 Workbench panel 的 analyst/review/delivery/ops 信息架构和可视化空态，不等于完成完整 B 端设计系统、watchlist 首页、图谱可视化、批注协作和多格式办公交付 studio 的最终 UI。
