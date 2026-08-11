# FIN 0.1 S3-T09：owner-grade semantic/actionability 零调用修复实现

日期：2026-07-22

## 结论与边界

用户授权继续上一项已经决定的 RC-P36-037 零调用实现。本轮完成 output v3 合同和本地 fail-closed 门禁，没有物化 baseline、签发或消费 admission、调用模型/Provider/网络/来源/工具、重跑真实 Agent、做 paired comparison、Human Review 或进入 T10/S4。

实现结果为通过确定性门槛，但不是 live 研究质量通过。历史 output v1/v2 admission、Run 和 Artifact 均未改写；原 v2 false green 仍是有效的历史根因证据。

## 上游到末端修复

Specialist 的 Judgment 不再是自由字符串，而是 Claim Card：每条 claim 明确 epistemic status、support fact IDs、Candidate/Graph context、entity/business scope/period/metric/attribution、qualification 与 cannot-support。本地 validator 从 T04 Numeric selector/derived metric 重建 authority surface；公司总量事实不能授权 segment/product/cross-chain claim，Candidate/Graph 也不能被提升为 supported claim authority。

WWC 改成 exact claim-bound 任务，必须携带 source target、metric/observation、decision rule、threshold/observable condition、as-of/trigger/deadline、预期 claim transition、fallback stop 和 routing authority refs。

Lead 的三个 Cell head 现在由 Specialist body 重算 Evidence/Numeric fact count、terminal class 与四类 claim-state count；terminal state 与 fact presence 分离。Variant、gap、dependency 和 conflict 都绑定 exact claim/WWC identity。

Writer 只能渲染 upstream claim/task，必须提交完整 claim/task identity 集合、claim surface digest、lead digest、每条 claim 的 status/scope digest 和 qualification-preserved 证明；顶层摘要只能按 section claim rendering 确定性拼接，limitations 只能投影 upstream cannot-support，不能绕过 section 创造新主张；Graph 不能译成“图表假设”。source/tool calls 继续固定为 0。

Verifier 输入现在包含按 Cell 的完整 authority surface、fact/Claim Card/WWC body、Lead body、Writer body 及 digests；finding 具有 typed issue code、artifact/claim refs 和 repair owner。任何本地 semantic issue、review-required/fail 或非空 issue code 都禁止 `accept_for_internal_review`。

## 验证

一条三 Cell 六节点零调用正例 terminal succeeded，并保留现有九类 Artifact family。十个负例分别命中范围越权、context promotion、epistemic 冲突、不完整 WWC、Lead fact-state 冲突、Writer unknown claim/scope、Graph 术语、qualification 丢失、Verifier body 缺失和 false green，全部在约定的最早 owner 拒绝。

Focused implementation + decision tests 为 `18 passed`；相关 v1/v2 adapter/model-view/transport compatibility 为 `21 passed`。Python compile 通过；当前 workspace Python 未安装 Ruff，因此如实记录为未运行。model/provider/network/source/tool/admission/live/baseline/Human counts 均为 0。

## 下一步

按用户此前批准的顺序，下一项回到已决定但未执行的 `S3-T09-PAIRED-DETERMINISTIC-BASELINE-MATERIALIZATION`，仍需单独授权。其后才可分别处理 fresh v3 Agent proof、paired comparison 与 owner acceptance。RC-P36-037 只达到 implementation fixture-proven，必须等待 fresh Agent Artifact 证明后才能关闭。
