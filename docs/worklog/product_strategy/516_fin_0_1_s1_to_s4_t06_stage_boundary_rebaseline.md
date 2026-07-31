# 516｜FIN 0.1 S1–S4-T06 全链能力与阶段边界重基线

## 问题

用户要求重新审计 S1 至当前 T06 的 Agent 全链能力，并按照实际工程复杂度重新划分 T06、T07、S5、下一版本和更后 roadmap 的任务归属。目标不是降低标准或减少必要工作，而是纠正“问题在哪次 live 暴露，就持续留在哪个 Case 任务修”的错误归属。

## 审计结论

- S1 fixture mainline、S2 one-cell real Agent、S3 NVDA three-cell R2 owner acceptance 均保持有效；
- S4-T01–T04 的三案 Case Pack、方法合同、source grounding、Runtime 注入和防泄漏保持有效；
- T05 已证明 DELL full Runtime 和 Agent actionability，但 DELL R2 未通过，按原任务的 honest-block 分支关闭；
- T06 已证明 MU exact source input、一次 6-node/12-call/9-Artifact success、paired L1 拒绝能力及大量 deterministic truth owner，但 MU R2 未通过；
- 最新 fact-candidate planner 是 current-worktree engineering evidence；independent proof failure 没有建立新的业务 L1；
- T06 现以 `terminal_honestly_blocked_closed` 收口，不再授权 proof、admission 或 live。

## 重新归属

- T07：一次 current-worktree 三案 regression，加最多一次另行授权的 NVDA post-transfer exact revalidation；
- T08：使用 immutable evidence 做三案只读 calibration、成本/延迟/Agent gain/Workbench value 与 L2–L4 质量审计；
- T09：真实 owner 与 qualified-senior review，不允许机器替代；
- T10：S4 pass 或 honest block closeout、ledger reconciliation 和 carry-forward；
- S5：proof package inventory、完整日志、hermetic reproducibility、Git/rollback、issue-ID 治理与 RG1–RG5；
- FIN 0.2：完整 contract compiler、Provider truth surface 收缩、DELL/MU R2 重试、Verifier 语义升级和 executor/version-family consolidation；
- 后续：未进入 Runtime 的方法、cross-sector、memory/refresh、monitoring、multi-format 和 enterprise production。

FIN 0.1 release 的三个 Case R2 与 NVDA R3 要求没有降低；当前仍 `not qualified`，允许最终 honest blocked candidate。

## 变更

- 新增机器审计：
  `configs/releases/fin_ia_0_1_s1_to_s4_t06_stage_boundary_and_task_ownership_rebaseline_v1_0.json`
- 新增阶段边界 source document：
  `docs/architecture/repository/FIN_0_1_S1_TO_S5_STAGE_BOUNDARY_REBASELINE_20260731.zh-CN.md`
- 更新 Program Plan、S4 execution plan、Detailed Design、program backlog、S4 detailed backlog 与 Project OS current context；
- 更新 capability/root-cause ledgers，使 T05/T06 终态、T07 next、RC-P36-085/S5 和下一版本归属可续接。

## 验证和安全边界

- 本轮不运行 model、Provider、network、source、exact-live、paired 或 owner review；
- 不修改 Runtime、Prompt、Validator、fake Provider、Case data 或历史 Artifact；
- 不重写历史 failed/succeeded truth；
- 边界合同测试：`4 passed`；
- 当前 `399` 份 release JSON 与 4 份 Project OS JSONL 共 `403` 个机器源严格解析，duplicate/parse error 为 `0`；
- Project OS full-chain preflight：`pass`，open full-chain blocker 为 `0`；
- touched-file `git diff --check` 与敏感信息扫描通过；
- 旧全仓 global-audit 测试仍把 release JSON 数量硬编码为 `296`，因此在 duplicate scan 前以“实际 399”失败。该测试快照不影响本轮直接严格扫描结论，归 S5 的 manifest-based package inventory / hermetic baseline 修复，不回灌 T06。

## 下一项

`S4-T07-ENTRY-SHARED-RUNTIME-CURRENT-WORKTREE-REGRESSION-AND-NVDA-POST-TRANSFER-REVALIDATION-SCOPE-DECISION`
