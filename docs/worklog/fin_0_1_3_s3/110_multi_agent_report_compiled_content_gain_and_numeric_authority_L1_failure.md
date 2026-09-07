# 110｜Multi-Agent 报告完成、内容增益与数字权威 L1 失败

日期：2026-08-21

范围：FIN 0.1.3／S3／DELL Multi-Agent Preview／终端 Writer

结论级别：正式报告合同已生成；研究内容显著改善；最终数字权威 L1 未通过；不得发布或宣称 S3 通过

## 1. 这次真实运行完成了什么

clean／synced commit `fde1d61d...` 的第二次 fresh Project OS preflight 通过后，项目签发了一次 submission-only authority。运行精确复用：

- 六份 Specialist plan；
- 一份 Lead plan；
- 六份最终工作底稿；
- 一份 Lead coordination；
- 三条已完成角色 repair；
- 六份角色 Evaluator；
- 一份跨角色 Evaluator；
- 一份 content-complete Writer analysis checkpoint。

本轮没有重新分析，也没有 analysis continuation、外源网络、Candidate promotion 或上游 Agent 重跑。唯一新逻辑节点是 Writer strict submission。

第一次提交只因 Supply section heading 为 121 字、超过共享合同 120 字而被拒绝；Runtime 在 authority 已允许的最多两次 contract attempt 内反馈精确字段限制。第二次提交缩短标题后通过。最终形成六节 DELL 报告、六条 remaining gap、八条 What-Would-Change 和中等置信度说明，report digest 为 `3ee44eda...ac43b`。

## 2. 内容为什么比旧 R7 明显更好

旧 R7 的核心失败是把已经存在的 AI revenue、orders 和 backlog 写成缺失，再把错误缺失升级为跨单元冲突。新报告没有重复这些问题：

- 把 `$16.1B` 识别为同季已经确认的 AI-server revenue；
- 把 orders、backlog、pipeline 与 realized revenue 分开；
- 不把 backlog 当作收入、现金或利润；
- Q1 FY27 毛利率变化不借用更早期间的 AI-mix 机制做当前因果归因；
- AI product profit 与 cash conversion 均保持为 unsized／unbridged；
- NVIDIA／TSMC／Micron 只作为 speaker-attributed read-through，不升级为 Dell-specific allocation；
- 反方区分条件风险和已实现损失，不声称 demand collapse。

八维诊断分为 `28/32`，旧 R7 为 `21/32`。这只能记作 material research-quality gain。两次运行不是严格同输入，且本轮仍有 L1，因此不能宣布 formal paired winner。

## 3. 为什么报告仍然是 L1 fail

本轮最重要的新发现不是 DeepSeek 又写错了数字，而是 Multi-Agent 最终 Writer 没有接上项目已经冻结的数字权威合同。

PRD 7.9 与 16.20 要求：模型可以看见并分析精确数字，但正式 artifact 中的 material number、unit、period、entity、comparison 和 citation surface 必须绑定 `NUM／REL／QF／FORM／PresentationAlias`，由 Harness 确定性渲染。来源正文里真的出现某个数字，只能改变根因归类，不能自动获得最终写入权。

当前 `report_draft_tool` 和 `validate_report_draft` 只检查：

- section 结构与长度；
- declared Evidence／Numeric ref 是否属于六份工作底稿；
- 标题、gap、WWC 等字段是否完整。

它没有检查 prose 中每个 material numeric span 是否与声明的 ref、期间、单位和展示 alias 一一对应。因此正式报告中出现了多类未保护表面：

- 执行摘要中的 AI demand stack 和公司级增长／margin 比较；
- Operating section 中的收入、利润、margin 和净利润；
- Value section 中的历史日期与年度 guide；
- Cash section 中的 AR、inventory、cash 和 financing receivable 精确余额；
- Counter section 中的 concentration percentage；
- WWC 中的季度 guide。

其中 Cash section 甚至明确说明：除 AP 外，其余 balance 只是 source-visible、未进入 NumericFact catalog。这个标签让它不是“模型伪造”，但不能让它成为正式可交付数字。

所以当前结论必须拆开：

- 研究判断与综合：显著改善；
- 当前 report JSON schema：通过；
- 正式金融事实写入权：失败；
- 产品接受：失败。

## 4. 最早责任层

根因登记为 `RC-S2-007-multi-agent-writer-bypassed-protected-numeric-surface-contract`。责任不是单独归给 S2 或 Writer：

- S2 没有从本次六底稿的 selected authority 完整编译最终可写数字／关系／别名；
- S3 Multi-Agent Writer 新建了一条 report contract，却没有复用已有 protected narrative 和 deterministic render seam；
- local L1 只做到 ref membership，没有做到 span-to-authority binding。

这是共享项目集成回归，不是 DeepSeek 研究能力失败，也不是 S1 检索资料空白。

另有一个非内容 L1 的治理问题：authority 的机器限制正确允许一个 Writer logical node、最多两次 contract attempt，人类文字却写成“exactly one strict submission”。public acceptance 因两次 attempt 把 `writer_strict_submission_executed_once` 记为 false。该问题登记为 `RC-AR-030`，后续必须分别显示 logical node 和 contract attempts，不能把一次有界格式纠错误读为多跑一个研究节点。

## 5. 下一步边界

下一项限定为零调用结构处置，不重跑当前报告：

1. 从六份 validated workpaper 与当前 S2 catalog 编译 final-report authority view；
2. 将 model-owned prose 与受保护数字／日期／比较／引用 surface 分开；
3. 只有 `NUM／REL／QF／FORM／PresentationAlias` 可以由 renderer 写入正式报告；
4. source-visible 但未授权的数字必须成为 `context_only_do_not_output`，不能靠一句提示放行；
5. 用当前 immutable report 做 span audit，并以 DELL／MU／NVDA 和留出 mutation 证明错值、错期、错单位、错公司、未绑定数字和 presentation rounding 均 fail closed；
6. 同时修正“一逻辑节点／多合同 attempt”的 Project OS 与 public result 语义；
7. 工程门通过后，最多授权一次 terminal Writer remapping successor，只做受保护 surface 映射，不重跑 S1/S2 检索、六 Specialist、Lead、repair 或 Evaluator。

在此之前，`financial_truth_L1_pass=false`、`formal_eight_dimension_acceptance=false`、`qualified_human_acceptance=false`、`S1_pass=false`、`S3_pass=false`、`Workbench publication=false`、`release=false`。

正式机器记录见 `configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_writer_terminal_submission_successor_content_assessment_v1_0.json`。
