# R14 terminal 与独立 Writer 接管边界

更新时间：2026-08-24

## 结论

R14 在 clean engineering commit `490b4dbd56ce1fbedc6914304b64dc8f4e172956`、repository-aware preflight 和 authority-only commit `5ef12af7ff920c4b5af54cfe8f9a7dddcc96ed66` 上完成唯一授权 submission。Provider 返回完整 HTTP 200 Tool call，但本地 protected-report 合同失败；runner 原子封存 terminal，0 retry、0 fallback。按预先登记的硬止损线，DeepSeek Writer successor 已停止，不得再调 Prompt、profile、ceiling 或发起自动重试。

## 授权与执行证据

- preflight SHA=`f4e59adf...aebae`，签权前 `model_calls=0`、`provider_calls=0`，repository clean/synced；
- authority SHA=`a1176319...f732`，digest=`25c3bafe...483b7`；analysis=`0`、submission ceiling=`1`、retry=`0`；
- public terminal：`...R10_protected_writer_submission_successor_live_result_v1_0.json`，SHA=`d9c66826...fb4b`，result digest=`bd4a9602...016a`；
- private terminal：`data/workbench_private/fin_0_1_3_s3_current_dynamic_multi_agent/dell-R10-protected-writer-submission-successor-live-r14/full_result.json`，SHA=`007fb464...c4b`，full digest=`3030e108...d5f5`；
- capture：HTTP 200、`finish_reason=tool_calls`、prompt=`73,305`、completion=`9,402`、reasoning=`0`、response complete；
- execution：Provider=`1／1 HTTP 200`、analysis=`0`、submission=`1`、retry／fallback／upstream／S1/S2／retrieval／external source／promotion=`0`。

## 两层非晋升诊断

第一层直接失败为 `multi_agent_protected_report_identity_invalid`：Tool arguments 顶层只有 `arguments`，而七个报告字段被再次编码成该字段内的 JSON 字符串。外层 JSON 长 `32,556` 字符；拆包仅为内存诊断，不得晋升。

第二层字符串可解析为七字段报告，但仍非有效 Candidate：

- 仍有 3 个 spelled-numeric／ordinal 表述路径：`sections[1].clauses[1]`、`sections[2].clauses[2]`、`sections[4].clauses[3]`；
- 4 个 hard reference finding：`sections[3].clauses[0]` 跨 Agent 且 Evidence／authority 越界，`sections[3].clauses[1]` authority 超出所选 claim，`what_would_change[0]` claim 跨 Agent，`what_would_change[2]` claim ref 未知；
- 9 个非阻断质量 finding：executive thesis 和 confidence 密度过高、confidence 重复 gap、gap register 过密，以及多个 gap 跨 surface group 重复。

完整零调用评估为 `...R14_failure_assessment_v1_0.json`，SHA=`5225e45e...1610`，assessment digest=`3e9a6c4f...4ed8`，model／Provider／network／promotion 均为 0。

## 处置

`RC-S3-091` 的 DeepSeek successor 路线按设计终止。不能把双层 JSON 拆包、三处文字替换或局部 ref 修补当作 R14 成功，也不能覆盖其 public/private terminal。

用户此前已明确授权在停止审计后迁移到当前任务继续，因此下一步只允许一个单独治理的 independent Writer takeover：绑定 R14 terminal、failure assessment、R10 authority catalog／protection 和四项 hard finding，由当前任务重新核对所有 clause reference；不得新增 Evidence、NumericFact、Relation、gap、外部来源或 Provider call。形成的任何本地 Candidate 仍须独立 post-Writer L1／L2 和八维质量评估；S3、产品、泛化、publication 和 release 均继续为 false。
