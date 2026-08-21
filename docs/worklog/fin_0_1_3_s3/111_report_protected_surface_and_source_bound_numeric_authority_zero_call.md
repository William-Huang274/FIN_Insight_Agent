# 111｜最终报告受保护表面与 source-bound 数值权限零调用收口

日期：2026-08-21

范围：FIN 0.1.3／S2 数值权威／S3 Multi-Agent Writer terminal

结论级别：结构工程通过；旧 DELL 报告仍为 L1 fail；一次 Writer-only 重映射具备前置条件

## 1. 这次真正修了什么

旧 Multi-Agent 报告的研究内容已经明显进步，但最终 Writer 可以把来源中看见的金额、百分比和日期直接写进 prose。引用列表只能证明“这份材料存在”，不能证明“这个具体数字、期间、单位和展示精度已经获得正式写入权”。

本轮新增两条共享能力：

1. S2 source-bound authority compiler：只根据人工复核的 source quote／value／metric／period／unit／qualifier 决策，重新绑定已有 NUM，或编译新的 exact、bounded、temporal authority；
2. S3 protected report contract：模型负责文字与选择 typed ref，本地 renderer 负责最终金额、比例、日期和比较表面。

这不是本地替模型写研报。模型仍然看见并分析数字；Harness 只控制正式 artifact 中数字如何被引用和显示。

## 2. DELL 实际回放发现了什么

16 个重点 material amount surface 中：

- 部分本来已在 S2 NumericFact catalog，只是 Specialist 没把 ref 传到最终 claim；
- 部分只存在于 reviewed official Evidence，需要新增 source-bound authority；
- guidance、approximately 和 concentration 只能以 bounded presentation 输出，不能冒充无条件精确事实；
- 一条日期需要明确 temporal review，不能从来源 metadata 自动获得权威。

最终 18 条 review decision 形成：13 条 exact／existing NumericFact、4 条 bounded presentation、1 条 temporal authority，覆盖 7 个 claim。审计列出的 16 个 material amount surface 均已有确定性渲染路径。

实现过程中主动拒绝了一条危险捷径：最初考虑从 Evidence metadata 自动带出 reporting-period 日期；真实 replay 发现部分 8-K 行的该字段实际混入发布日样值，因此删除自动晋升，改为逐条明确裁决。

## 3. 旧报告为什么仍然失败

旧 artifact 没有被修改。它在标题、执行摘要、正文、remaining gap 和 WWC 共 11 个字段路径中仍含未绑定的自由数字／日期／季度表面，因此保持：

- `artifact_complete_under_current_schema=true`；
- `material_research_gain=true`；
- `financial_truth_L1_pass=false`。

新的工程能力只证明可以安全生成 successor，不能事后给旧报告补发合格证。

## 4. 泛化与故障门

DELL、MU、NVDA、ORCL 使用同一 compiler、validator 和 renderer。测试覆盖：

- raw numeric surface 留在 model prose 时 fail closed；
- 跨 claim／agent／case 借用权限时 fail closed；
- source quote 与 normalized value 不一致时 fail closed；
- 未复核的来源数字不会自动晋升；
- source metadata 日期不会自动晋升；
- guidance／approximation 不能升级为 exact；
- 输入排列变化不改变 digest；
- final renderer 只从 typed authority 写值。

定向测试 `18 passed`。完整门禁为全仓 `946 passed`、compileall、Workbench TypeScript／production build、active baseline `185 Python／8 frontend／5 detectors／27 Runtime／0 forbidden`、archive redirect `6,059`、798 份 JSON 与 8 份 JSONL 可解析、7,525-file secret scan／0、diff check通过。

## 5. 下一步和不可越过的边界

下一次只允许一个 Writer terminal remapping logical node：复用现有六 Specialist、Lead、三条 repair、六角色评审、跨角色评审和完整 Writer analysis，把内容映射为“无受保护数字的 model text＋typed surface refs”。

禁止：

- 重跑检索或上游研究 Agent；
- 新增 Evidence、NumericFact、观点或因果机制；
- 以提高字符／数字容忍度替代合同；
- 把 source-visible 当作 final-output-authorized；
- 在新 artifact 通过 L1、内容质量和人工验收前宣布 S3 或 release 通过。

机器证据：`configs/research/evals/fin_ia_0_1_3_s3_multi_agent_report_surface_authority_zero_call_result_v1_1.json`，result digest=`09c4d60b...0958`。
