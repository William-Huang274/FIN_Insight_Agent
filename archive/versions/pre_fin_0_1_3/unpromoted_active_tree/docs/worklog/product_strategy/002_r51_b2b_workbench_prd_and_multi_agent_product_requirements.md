# R51 B2B Workbench PRD And Multi-agent Product Requirements

日期：2026-06-28

## Prompt

用户指出上一版 B 端功能设计仍过于接近 GPT / Codex 式项目对话，没有充分吸收 25 文档中扩展的数据范围，也缺少合格底稿模板、多格式输出、输入文件解析、dashboard、watchlist、知识库、关系图谱、可视化和真实企业办公工作流。用户要求先落 B 端 PRD，然后继续讨论 agent graph 如何运行、agent 如何嵌入公司工作流，以及 multi-agent 如何从固定 fanout / second pass 升级成更像真实团队协作的模式。

## Decision

将 B 端产品定义为 `Evidence-backed Financial Research Workbench / AI junior analyst layer`，不是通用金融聊天框，也不是直接替代 senior judgment 的自动决策系统。

产品文档和技术实现继续分离：

- 本轮新增 PRD，只定义用户、场景、功能、底稿、交付物、dashboard、watchlist、图谱和产品验收标准。
- multi-agent 只在 PRD 中定义产品能力要求，具体 graph、通信、上下文、工具权限、human-in-the-loop、async/sync 和成本调度需要后续拆技术文档。

## Work Completed

- 新增 `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`。
- 更新 `docs/product/README.md`，把新 PRD 纳入产品文档索引。
- PRD 明确 B 端产品形态：
  - Dashboard；
  - Research Task Center；
  - Input / Data Room；
  - Evidence Workbench；
  - Workpaper Builder；
  - Graph / Visualization Workspace；
  - Deliverable Studio；
  - Watchlist / Monitoring；
  - Human Review / Approval；
  - Admin / Governance。
- PRD 明确完整 evidence 范围需要综合 25 文档，包括基本面/披露、产品/技术/客户/供应链、行业/政策/监管、资本市场/资金面/二级市场、用户上传和机构私有材料。
- PRD 新增 `WorkpaperPack` 产品层，要求写作器不能直接从 ClaimCard 或 raw retrieval 拼最终报告。
- PRD 将输出端从 `Memo Writer` 产品语义升级为 `Deliverable Composer / Report Studio`，支持长回答、Markdown、Word、PPT、Excel appendix、PDF brief、图谱图、思维导图、时间线、客户版摘要和内部底稿。
- PRD 记录 multi-agent 产品要求：Research Lead 应作为 supervising analyst 常驻监督，specialist 围绕共享 WorkpaperPack 协作，human reviewer 能插入关键节点，agent 通信应形成结构化 artifacts。

## Result And Evidence

- 新产品文档路径：
  - `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- 产品索引已更新：
  - `docs/product/README.md`

## Verification

- `git diff --check` 已通过。
- 本轮未运行 runtime、agent graph、LLM、parser、DB、frontend 或 full-chain 测试，因为变更范围是产品 PRD 与文档索引。

## Follow-up

下一步应拆技术文档讨论：

1. 协作型 multi-agent graph 是否从固定 fanout 改为 shared workpaper event bus + Research Lead supervision。
2. Research Lead、specialist、human reviewer 和 Deliverable Composer 的职责边界。
3. agent 间通信对象：TaskContract、EvidenceRequest、WorkpaperSection、GapQuestion、ReviewComment、RepairPlan、JudgmentState、DeliverablePlan。
4. Human/lead in the loop 插入点。
5. async/sync 协作、资源调度和成本控制。
6. WorkpaperPack / DeliverablePlan / Artifact schema。
