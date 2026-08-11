# 021 R53-R60 Slice Gate Wording Correction

日期：2026-06-29

阶段：R53-R60 product strategy / engineering framework

状态：docs-only correction

## Prompt

用户指出 36 文档第 5 节仍写着“实现最小合同、跑 1-2 个真实 case 或 smoke、进入下一 slice”，这和“通过条件上调为企业级验收模型，不再按能跑/有输出算通过”的原则冲突。

## Reasoning

上轮虽然在 36 文档开头补入了 L0-L4 pass level 和四类 acceptance，但第 5 节保留了旧的执行节奏表述。该表述会让执行者误以为完成最小接口、跑一个 smoke 就可以推进主 slice，实际会破坏 enterprise pass-level gate。

需要把推进规则从“最小合同优先”改为“按 target pass level 和 acceptance evidence 推进”。

## Work Completed

- 更新 `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`：
  - 第 2 节把“先 L1 contract，再 L2 dogfood”改为“按 target pass level 推进，不用最低合同替代完成”；
  - 第 2 节每个 slice closeout 增加 target pass level 判定、四类 acceptance 证据和与目标等级匹配的 gate；
  - 第 5 节把旧的“实现最小合同 / 跑 smoke / 进入下一 slice”替换为 `PassLevelDecision` 驱动流程；
  - 第 5 节明确未达到目标 pass level 时只能标记 `blocked` / `partial_diagnostic` / `exception_requested`，不得当作完成；
  - 第 7 节把当前里程碑改为具体 target pass level 证据，不再只写 S0/S2-S3 达到 L1 即可。
- 更新 `docs/worklog/00_internal_master_checklist.md`，记录这次 slice gate wording correction。

## Result

36 文档现在的推进口径是：

- `L0` 只能 smoke / diagnostic，不能进入依赖；
- `L1` 只适用于合同型底座需求，且必须是完整合同和确定性测试；
- 用户工作流、Workpaper、交付物、前端、质量工程和 release candidate 必须达到对应 `L2` / `L3`；
- 每个 slice 必须生成 `PassLevelDecision`；
- 未达目标 pass level 不能进入下一主 slice，除非用户明确批准 exception 且下游不依赖该缺口。

## Verification

本次为文档更新，未运行 runtime、后端、前端或 eval case。

需要收尾检查：

- `git diff --check`
- 候选文档 secret scan
- conflict marker audit

## Follow-up

- S0 `U0-D03-pass-level-gate-matrix` 实现时，应把 `PassLevelDecision` 转为 machine-readable schema。
- 后续 release board 必须显示 target level、achieved level、gap、exception 和 blocker，而不只显示 done / todo。
