# FIN 0.1.2 版本合并、新起点与高级助手规范

日期：2026-08-02

任务：合并原 FIN 0.1.2/0.1.3/0.1.4，恢复 FIN 0.1.2 为当前完整 S0–S5 产品迭代；完成新起点规划和只读资产盘点；将 Codex 主动反思和及时提出需求修改建议写入跨会话规范。

结果：`planning and governance pass / asset audit complete / implementation not started / zero model calls`

## 1. 关键纠偏

原 0.1.3 与 0.1.4 没有引入新的产品范围。0.1.3 的资源、引用、环境和 proof-control 工作属于 0.1.2 S0；0.1.4 只有未执行计划。此前用一次 proof 失败冻结产品版本，是把产品版本和 execution attempt 混为一谈。

本轮恢复以下真值：

- FIN 0.1.1 保持第一轮 S0–S5 frozen internal honest-block baseline；
- FIN 0.1.2 是当前唯一开发版本，当前阶段 S0；
- 0.1.3 是 0.1.2 S0 historical recovery/acceptance attempt family；
- 0.1.4 是 historical unexecuted S0 proposal；
- FIN 0.2 仍是 Earnings Review Alpha。

历史文件、失败结果、digest 和 commit 全部保留，不把失败改写为通过。代码本来就在同一累计提交链，因此没有回滚、搬运或物理代码合并。

## 2. 新计划

新增 FIN 0.1.2 canonical S0–S5 产品计划，以及简化 S0 技术计划。阶段分工为：S0 可靠基础、S1 三案例确定性链、S2 模型能力边界、S3 NVDA 产品锚点、S4 DELL/MU 迁移和 Workbench、S5 发布判定。

修复规则改为：失败 attempt 永久保留；当前阶段根因在当前阶段修；添加回归测试后用新 attempt 重验；不变条件下不得盲目重跑；测试失败不再自动增加产品版本号。

## 3. 只读代码资产审计

审计起点 HEAD=`b1b3df84e68d5e1b651f808b794d2642782ce67b`，开始时 worktree clean/synced。

focused zero-call command：

```text
python -m pytest -q
  tests/contract/test_fin_0_1_3_s0_runtime_resource_registry_and_dependency_compiler.py
  tests/contract/test_fin_0_1_3_s0_typed_environment_semantic_parity.py
  tests/contract/test_fin_0_1_3_s0_reference_role_registry_and_collect_all_compiler.py
  tests/contract/test_fin_0_1_3_s0_exit_contract_v3_proof_control_plane.py
  tests/contract/test_fin_0_1_2_s0c_hermetic_topology_and_allowlisted_package_closure.py
```

结果：`57 passed / 3 failed`。三项共同根因为旧 manifest/current projection 与 mutable backlog/next action 漂移，错误码为 `current_projection_next_action_drift`；不是新资源 registry、六角色引用或 typed environment 单元失败。

保留：共同 Runtime 合同和十 consumer、三案例 fixture/full-fake、RuntimeResourceRegistry、六类 reference role、typed environment、capture/terminal result、历史 Workbench/九件套诊断资产。

待修：current/event ownership、hard-coded status allowlist、over-coupled proof control plane、version-specific current manifest/runner、S0/S1 测试责任混杂。

退出 current 入口但不删除：0.1.4 projection、两个产品版本迁移处置的 current authority、一次失败耗尽产品版本、no-v4 导致产品换号和未执行的复杂 lifecycle StagePlan。

## 4. 高级助手规范

新增根目录 `AGENTS.md` 和 Project OS 完整规范。Codex 必须在执行过程中持续检查已经批准的需求和方向是否因新证据变得矛盾、不实际、过度工程化或成本失衡；发现实质问题必须及时向用户说明证据、影响和修改建议。用户保留最终决定，Codex 不得静默覆盖用户目标，也不得因先前批准而隐瞒异议。

该要求同时进入 current context、Project OS README、capability ledger 和本 worklog，确保上下文压缩或任务交接后恢复。

## 5. 文件

- `AGENTS.md`
- `docs/project_os/senior_assistant_collaboration_policy.zh-CN.md`
- `configs/releases/fin_ia_0_1_2_version_consolidation_and_current_rebaseline_v1_0.json`
- `configs/runtime/fin_ia_0_1_2_current_program_projection_v2_0.json`
- `docs/product/FIN_0_1_2_CANONICAL_S0_TO_S5_PRODUCT_PROGRESSION_PLAN_20260802.zh-CN.md`
- `docs/architecture/repository/FIN_0_1_2_S0_CURRENT_BASELINE_AND_CLEAN_ENVIRONMENT_QUALIFICATION_PLAN_20260802.zh-CN.md`
- `docs/architecture/repository/FIN_0_1_2_S0_CURRENT_CODE_ASSET_AUDIT_20260802.zh-CN.md`

并更新版本谱系、原 S0/S1/0.1.3 source docs、双 backlog、Project OS、工作日志索引和机器账本。

## 6. 没有执行

没有修改 Runtime 或测试实现，没有 clean-environment acceptance、凭据读取、模型、Provider、网络、业务 Run/Artifact、exact-live、tag、release 或 production。

## 7. 本轮验证

- 新增合并契约：`tests/contract/test_fin_0_1_2_version_consolidation_and_current_rebaseline.py`，结果 `5 passed`；
- 四份新增/更新 JSON 均通过标准 JSON 解析；
- capability ledger 共 548 行、root-cause ledger 共 796 行，均逐行通过 JSONL 解析；
- `src/` 与 `scripts/` 无差异，确认本轮没有混入 Runtime 实现；
- `git diff --check` 与提交前敏感信息检查纳入最终 Git 验证。

## 8. 当前下一步

`FIN-0.1.2-S0-CURRENT-BASELINE-AUDIT-OWNER-REVIEW-AND-REPAIR-AUTHORIZATION`

Owner 审核资产分类和修复建议后，才开始 current/event ownership 与版本中性 runner 的 S0 修复。
