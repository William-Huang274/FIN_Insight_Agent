# R7 部分内容返修与 R8 精确 submission-resume 门

## 结论

R7 实际发生 6 次 DeepSeek Provider 调用，全部 HTTP 200／`tool_calls`，0 retry。Cash 与 Counterevidence 的自然分析和 strict submission 均通过；Demand 自然分析完成，但 strict mapper 把一个没有 Evidence／NumericFact／Relation 权限的边界陈述写成 `bounded_inference` claim，被本地 Evidence Gate 正确拒绝。Operating、Value 与 Lead 均未调用。

R7 还暴露一个独立 Harness 缺陷：`MultiAgentPreviewError` 没有进入 content-repair runner 的 terminal catch，导致 capture 已保存但 public/private terminal 未自动物化。该缺陷不等于模型失败，也不改变 Demand payload 应被拒绝的结论。

## 处置

- 用签发 commit 的 Git blob、R7 checkpoint 和 6 份 immutable capture 做零 Provider 重放，物化 R7 terminal；没有补写或晋升失败的 Demand submission。
- terminal 明确保留 2 个完成 repair、5 个可复用语义节点、1 个被拒绝节点；Writer 继续冻结。
- normal runner 现在捕获本地 workpaper contract error，并把失败 capture ref、完整 manifest 和 terminal result 一并保存。
- strict submission 接口可接收结构化 validation feedback；反馈只能要求把该表面降为 `not_inferable` 或保留 existing gap，明确禁止新增 authority 或改变自然草稿的金融判断。

## R8 精确续跑证明

零调用 proof 逐摘要绑定 R7 authority／public／private，排除失败的第 6 份 Demand strict submission，只复用：

1. Cash draft＋submit；
2. Counterevidence draft＋submit；
3. Demand natural draft。

首个 fresh Provider frontier 精确为 Demand strict submission。后续只允许 Operating／Value 两个分析＋submission 对和一个 Lead 对，共最多 7 次；0 S1/S2、retrieval、外源、promotion、retry、fallback 和 Writer。

## 证据

- R7 terminal：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_repair_live_result_v1_1.json`
- R8 proof：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_repair_submission_resume_zero_call_result_v1_0.json`
- R8 scope：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_repair_submission_resume_scope_decision_v1_0.json`
- 根因：`RC-S3-081`、`RC-S3-082`、`RC-S3-083`

## 尚未证明

R8 尚未签发或执行。Demand strict 重交、Operating、Value、Lead、七项 finding 的独立 L1/L2 与内容质量复评均未完成；Writer、S3、泛化、Workbench publication 和 release 全部仍为 false。
