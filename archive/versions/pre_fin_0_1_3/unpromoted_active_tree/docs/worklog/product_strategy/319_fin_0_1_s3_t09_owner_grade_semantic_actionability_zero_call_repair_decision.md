# FIN 0.1 S3-T09：owner-grade semantic/actionability 零调用修复决策

日期：2026-07-22

## 授权与结论

用户授权继续当前唯一下一项。本轮只完成 RC-P36-037 的零调用修复决策，没有实现代码、物化 baseline、签发 admission、重跑 Agent、执行模型/Provider/网络/来源/工具或 Human Review。

结论为选择从最早错误面一直修到 Verifier，而不是只给末端加关键词规则。新主合同冻结为 `fin01.s3.bounded_agent_three_cell_output:v3`，复用现有三 Cell profile、DeepSeek segmented transport、六节点拓扑、Runtime、Registry、Writer 和 Store family。现有 v1/v2 admission、Run 与 Artifact 保持不可变。

## 根因证据

当前 v2 只对 `fact_layer` 检查 Evidence/Numeric authority；`judgment_layer` 和 WWC 仍是长度受控的自由字符串。因此 Value Specialist 可以在只有 company-total Numeric fact 的情况下写出 Data Center segment revenue-capture 的确定性判断。Lead 的 Cell head 只绑定 digest，没有分别携带 terminal class 与 Evidence/Numeric fact count，所以又把“未闭合”写成“全部 non-fact”。Writer 只校验三 section、lead digest 和 source/tool=0，可以传播 scope expansion 并把 Graph hypothesis 译成“图表假设”。Verifier 只收到 Writer body 与 Specialist/Lead digest，没有收到 Specialist/Lead body 和完整 authority surface；本地 validator 也只检查四层 shape、digest 与 decision enum，因此给出 false green。

这属于项目内 output contract、上下文与 validator 缺口，不是 DeepSeek JSON 格式失败，也不能归因于模型本身。

## 选择的修复

Specialist Judgment 改成结构化 Claim Card：每条 claim 必须携带 epistemic status、support fact IDs、context refs、entity/business scope/period/metric/attribution、qualification 和 cannot-support。公司总量 Numeric 不能授权 segment/product/cross-chain claim；Candidate/Graph 只能是 hypothesis context，不能成为 fact authority。

WWC 改成可领取任务合同，至少包含 source target、metric/observation、decision rule/threshold、time window、预期 claim 状态转换与 stop condition。缺任一项都在产生该任务的节点 fail-closed。

Lead 必须分别携带 terminal class、Evidence fact count、Numeric fact count 和 claim-state counts，不能再把“终态未闭合”等同于“没有事实”。Writer 不得创建新研究 claim，只能渲染 exact Claim Card/WWC identity，并保留 epistemic status、scope digest 和 qualification；Graph 术语固定为“研究关系图谱/关系图谱假设”。Verifier 输入升级为 full-authority body，包括 authority surface、Specialist Claim Cards、Lead 与 Writer 正文及所有 digests；本地 owner-grade semantic precommit gate 与模型 Verifier 并行约束，存在任何本地 issue 时禁止 `accept_for_internal_review`。

## 实现门槛

下一步实现必须用一个三 Cell六节点 fake-provider 正例形成现有九类 Artifact，并让十个负例在预定的最早 owner 失败。十个负例覆盖本次四项 live 漏检以及 Candidate/Graph promotion、epistemic status 冲突、Writer 新 claim/scope expansion、qualification 丢失、Verifier authority body 缺失和 false green。

预算暂保持 Specialist/Lead/Writer/Verifier=`2200/1200/1400/1000`、aggregate=`10200`。如果 v3 确定性 fixture 放不下，必须停下做独立预算决策，不能静默放宽。实现阶段仍要求 model/provider/network/source/tool/new admission/live run/baseline/Human=0。

## 下一步

唯一下一项为 `S3-T09-OWNER-GRADE-SEMANTIC-ACTIONABILITY-ZERO-CALL-REPAIR-IMPLEMENTATION`，需单独授权。通过实现门槛后，才按既定顺序分别处理 baseline 物化、新 Agent 证明、paired comparison 和 owner acceptance。
