# R9 合同成功与跨角色 L1 失败

## 执行结论

R9 在 clean／synced commit `ac898606ba626b8af94e4a24db8f6b0c151ccbca` 上通过第二次 repository-aware preflight 和 authority validator 后唯一执行。六个 Provider 节点全部 HTTP 200／`tool_calls`，0 retry／fallback：Operating analysis＋submission、Value analysis＋submission、Lead analysis＋submission。Cash、Counterevidence、Demand 复用，Supply 不变；新 S1/S2、retrieval、外源、Candidate promotion 和 Writer 均为 0。

- public result：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_repair_live_result_v1_3.json`
- public SHA-256：`09f670a3f5dc00f7f96407c828ae4382d94ca77ee632ec498726dcc6753522ea`
- result digest：`0eb687af46ca6785e592c0a1f40efcca18e3e6c1ab5192205621435b5771dcf3`
- private SHA-256：`fc294c2d48f8e04728e203b2ab6faa0084b382d6cee9049cbde9969e3b5ab070`
- private full-result digest：`497865ee3d387e81101beedbdd931d9dab68812b2595a1c7e3f36add8bc13084`
- usage：102,822 prompt token＋51,584 completion token；该统计只描述六个已授权节点，不增加验收权威。

结构状态为 `completed_contract_valid_reassessment_pending`，frontier 为 `proceed_to_independent_reassessment`。R9 Demand authority ceiling 按预期生效：claim digest `84033e8d...120d` 的 effective authority 为 `not_inferable`，文本、Evidence／NumericFact／Relation 引用和 gap 均未改变。Operating、Value workpaper 均通过 strict validation；Lead 形成一轮 catalog-bound decision。Writer 没有被调用。

## 独立 L1／L2 复评

零模型独立复评确认七项原 finding 中六项已在当前六底稿集合关闭：

- 费用桥按 `-3.4pp / +6.7pp / +3.4pp` 保留正负方向，不再写未经授权的贡献份额；
- `1.253B` 只作三行资产负债表营运资金代理，不作实测现金吸收；
- NVIDIA 客户结构与 Dell 客户集中分开；
- NVIDIA 出口管制只作有界上游情景；
- 公司毛利率在两个方向都不能证明 AI 产品定价能力；
- pull-forward／消化只保留为可能解释，既有 gap 不变。

但 `RC-S3-075` 未在全角色范围关闭。Operating 已正确写明同季订单与收入没有 cohort 桥；复用的 Demand workpaper 却在 `strongest_counterarguments[1]` 写道 `$16.1B` 已确认收入说明“订单向收入的部分转化当期已实际发生”，其 thesis 也有“收入已部分转化”措辞。该底稿同时承认无同一订单 cohort，因而这是同季共现被再次升格为实际转化的 L1 错误。R9 Lead 的 rationale 仍宣称相关 recheck 已满足，说明 Lead 也没有发现跨角色残留。

独立评估因此为：结构合同 pass；原七项 finding 全集合 `6/7` 关闭；L1 fail；L2/content fail；Writer ineligible；S3/product/release false。诊断性适用分为 `23/28`，Q8 因 Writer 未进入而 N/A。正式产品评分仍禁止。

评估文件：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_repair_R9_content_assessment_v1_0.json`。

## 最早责任层与下一门

新问题登记为 `RC-S3-087`。最早项目责任层不是数据、Provider 或 transport，而是跨角色 semantic repair coverage：R5 finding 只按原 target agent 路由，通用“同期间≠同 cohort”规则没有对每个复用角色的每个叙事字段做独立复验；Lead 又按粗粒度 challenge 状态判断已解决。

R9 terminal 与六份 capture 必须保持不可变，禁止 Writer 和自动 retry。当前只允许零调用 successor 工程：给 Demand thesis 与 `strongest_counterarguments[1]` 编译一份精确 FeedbackReceipt，复用其余五份 workpaper，证明首个 fresh frontier 为 Demand analysis；自然拓扑最多为 Demand analysis＋submission 和 Lead analysis＋submission共 4 次。任何 R10 live 仍须先通过完整 seam、全仓回归、clean commit／push、Project OS preflight、四调用 `TokenBudgetBasis` 和 fresh authority。
