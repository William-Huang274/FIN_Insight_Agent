# 062 B04 Real Reviewer Closeout Packet And Temp Gate Validation

## 问题

用户要求先把 B04 做完，并把 P30 的 Workbench 产品界面问题先记录下来。

## 判断

B04 不能通过自动化或模拟数据关闭。当前 B04 的真实关闭条件是：同一真实 reviewer session 必须写入 `reviewer_session`、`deliverable_acceptance`、`defect_closeout`、`visual_acceptance`、`audit_replay` 五类 evidence，并且 P24/P21 从正式 ledger 派生出 accepted decision。P30 是 Workbench 产品界面成熟度问题，不应混入 B04 的真实验收 ledger。

## 完成内容

- 新增 `docs/internal/vnext_20260610/r53_r60_b04_real_reviewer_closeout_packet.zh-CN.md`，把 B04 验收范围、推荐 task/run/artifact、browser visual refs、待 closeout defect ids、reviewer decision 和正式 evidence 写入口径固化。
- 新增 `docs/worklog/product_strategy/061_p30_workbench_product_surface_redesign_followup.md`，记录 Workbench 需要从工程调试台升级为 analyst-facing Workbench + admin/ops console 的 P30 后续工作。
- 更新 `docs/worklog/README.md` 和 `docs/worklog/00_internal_master_checklist.md`，把 P30 作为 B04 后的产品化 follow-up 追踪。
- 用临时目录复跑 B04 closeout simulation，不写入正式 ledger，验证 P24 在拥有真实 reviewer evidence 等价结构时可以关闭。

## 验证结果

临时 B04 closeout simulation 输出：

```json
{
  "status": "pass",
  "release_decision": "P24_b04_real_human_product_acceptance_complete",
  "closeout_level": "L4_scope_pass_for_real_human_product_acceptance",
  "b04_status_after_p24": "closed_by_real_human_product_acceptance",
  "full_chain_broad_eval_allowed": true,
  "counts": {
    "dependency_count": 1,
    "dependency_fail_count": 0,
    "browser_e2e_fail_count": 0,
    "human_evidence_pending_count": 0,
    "defect_closeout_pending_count": 0,
    "accepted_decision_count": 1,
    "real_reviewer_evidence_row_count": 5,
    "gate_fail_count": 0,
    "gate_blocked_count": 0
  }
}
```

这说明 B04 的工程路径已经 ready；当前正式 B04 仍 open 的原因是正式 `r53_r60_p24_b04_real_reviewer_acceptance_evidence_v0_1.jsonl` 还没有真实 reviewer rows。

## 后续

如果真实 reviewer 接受 closeout packet，应写入正式 evidence ledger 并重跑 P24/P21。若 reviewer 拒绝，应把拒绝原因转为 P30 或上游 root-cause defect，不得用自动化 evidence 关闭 B04。
