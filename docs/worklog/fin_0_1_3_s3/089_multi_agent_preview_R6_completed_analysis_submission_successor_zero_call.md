# FIN 0.1.3 S3 — Multi-Agent Preview R6 完整分析交卷 successor 零调用门

日期：2026-08-20
状态：`R5_failure_immutable / completed_analysis_checkpoint_pass / submission_only_successor_zero_call_pass / R6_live_pending`

## 1. 为什么需要 R6

R5 的唯一模型调用已经自然补完 R4 截断后的 Lead 分析：续写共 5,003 字，`finish_reason=stop`，完成协调问题 11—13、信息边界、停止条件和精确回执。它被拒绝并非内容不完整，而是 Prompt 要求被截断字段原地续写，Validator 却又要求重复该字段标题。

R5 必须继续记为 terminal failure；但再次调用模型重做同一内容既浪费费用，也破坏成功前缀。R6 因此只恢复完整分析并执行严格结构化提交。

## 2. 结构修复

- 分开 `completed_outputs`、最多一个 `partial_required_output` 和 `missing_required_outputs`；
- partial 必须在第一个 missing heading 前非空原地补完，且不得重复 partial heading；
- missing 字段继续要求精确 heading、原顺序和非空内容；
- terminal receipt 必须精确覆盖 partial＋missing；
- `AnalysisCompletionCheckpoint` 绑定 R4／R5 capture、authority／result、digest、长度、usage、finish reason、原 analysis TokenBudgetBasis 和合并草稿；
- `execute_checkpointed_preview_submission` 只记录本地 checkpoint reuse 并进入 strict submission，禁止新 Lead analysis／continuation。

## 3. 真实 capture replay

- R4 fragment：9,932 字；
- R5 continuation：5,003 字；
- merged analysis：14,937 字；
- merged digest：`637fd12cd29d8e0b48c79bbd74ee0ac308a468b0d0b32f132636772a1e5da49f`；
- completion checkpoint digest：`9a60c0f0bf198480087ab9199711b4cc1441931ed922facdbf7637c310bd6baa`；
- zero-call result digest：`05655990e8823363a5e8dc5825b26ba733f1c729de685563a9ce23bc15786b99`。

fake Runtime phases 为 `analysis_checkpoint_reuse → submission`；Provider attempt 为 1，Lead analysis call 为 0。empty partial、partial heading 重复、missing heading 缺失、顺序漂移、receipt 漂移、completion digest 漂移和第二 partial 全部被拒绝。

## 4. 分层归因

| 平面 | 判断 |
|---|---|
| 数据／S1／S2 | 本次无新增失败；研究输入未变化 |
| Harness | R5 失败的首要责任；partial／missing 共享规则已修复 |
| Agent／模型 | R5 continuation 实质完整，不能记为模型不遵循 |
| Evaluator | 尚未启动，不能评价最终内容和多角色增益 |

## 5. 权限边界

只允许一个 clean／synced 的 R6 submission successor：复用六份 R3 Specialist 计划、R4 fragment 与 R5 continuation；Lead analysis／continuation 新调用为 0，先执行一次 strict Lead submission，再按原 bounded Preview 继续。0 外部来源网络、0 Candidate promotion、0 产品发布、0 qualified-human 自签。

该 gate 不签发 S1、S3、泛化、Workbench 或 release。R6 下游自然结果必须继续按数据、Harness、Agent／模型和 Evaluator 分层审计。

## 6. 工程复证

- Preview 定向测试：22 passed；
- Project OS preflight 测试：42 passed；
- 全仓：855 passed；
- compileall：pass；
- active baseline：184 Python／8 frontend／27 Runtime／0 forbidden；
- repository secret scan：7,390 files／0 findings；
- `git diff --check`：pass。
