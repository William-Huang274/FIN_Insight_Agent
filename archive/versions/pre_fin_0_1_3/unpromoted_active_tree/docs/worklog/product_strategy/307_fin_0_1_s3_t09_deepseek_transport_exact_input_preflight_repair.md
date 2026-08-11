# FIN 0.1 S3-T09：DeepSeek 六节点 transport 与 exact-input preflight 修复

日期：2026-07-22

## 结果

用户以“继续”只授权 `S3-T09-DEEPSEEK-SIX-NODE-TRANSPORT-AND-EXACT-INPUT-ZERO-CALL-PREFLIGHT-REPAIR`。两个签发前 owned blocker 均已在零真实调用范围内修复并验证；没有签发或消费 admission，也没有执行真实模型、Provider、网络、来源、工具、业务 Case、Human Review、T10、S4、release 或 production 动作。

六节点 Provider 路线现在有唯一 DeepSeek segmented adapter 与 exact S3 admission factory。固定拓扑仍为 3 Specialist + Research Lead + no-source/no-tool Writer + Verifier；每节点只请求 native JSON object，transport attempt=1、retry=0。输出先做 duplicate-key、closed shape、authority、lineage 和 semantic 本地校验，错误在 canonical Artifact commit 前停止；每节点绑定 exact Agent/Skill version 并保存安全 usage receipt，不保存 raw provider response 或 private reasoning。单节点 token 上限和总成本上限均在 transport owner 内 fail-closed。

## exact input 生命周期

`ExecutionService` 与 `Fin01ResearchRuntime` 现在共享 WorkUnit、Attempt、ResearchRun 的确定性 identity 公式。新增只读 S3 prepare 路径，在 execution state 不存在时，用 frozen execution identity 预测三种 canonical identity，再走与正式 Runtime 相同的 T02-T07 和 S3 input compiler。EvidenceService 只在明确的 prospective preflight 入口允许不存在的 execution lineage；正式 runtime compile 仍要求真实 pending/running WorkUnit，preflight 若发现同 identity 的 WorkUnit、Attempt 或 Run 已存在则拒绝。

持久化 isolated evaluation root 已生成：`.codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1`。它绑定：

- Case：`case_ac6fce120bf27977a1b45832`，version 1；
- accepted DecisionSurface：`p02_decision_surface_fd8fca1b6e3b98886fb71109:v1`；
- as-of：`2026-07-21T00:00:00Z`；
- predicted WorkUnit：`wu_p02_5_b32274eec019e44d8982af58`；
- predicted Attempt：`attempt_fin01_8f40a1cf360e736835f65413`；
- predicted ResearchRun：`research_run_fin01_a77b165e85be8757e5855a69`；
- input digest：`ec562442781bae817fdba072cc953e86373ef3b64e78e8a9dcca8312bb5802b8`；
- preparation digest：`59d38459c8260bd8fc594c2d73917f028361b3c4f6039776f9d7382f235b1ad8`。

prepare 内部双编译完全一致，且前后 WorkUnit/Attempt/Run/Artifact 均为 0。正式 Runtime 仍会重建同一 input pack；admission digest 不匹配时在第一笔 fake provider call 前停止。

## 验证和边界

完整 fake-provider/canonical fixture 证明预测 identity 与实际 materialized identity 相同，六个节点恰好各一次模拟调用，WorkUnit/Attempt/Run 均 terminal succeeded，九类 canonical Artifact 齐全，source/tool/head write 均为 0。duplicate JSON key 与 fenced JSON 都在第一次模拟 transport 后 fail-closed；exact input mismatch 的模拟 Provider call 为 0。

兼容回归覆盖 S2 exact admission、T08、T09、LLM gateway 和 Agent registry，共得到 104 个通过项；其中一条旧 T09 测试仍把“当时缺实现”误写成“源码永远不得出现实现”，已改为保留历史决策事实同时验证授权修复后的实现存在。真实模型 job 没有运行，credential 也没有在本轮检查或持久化。

两个 owned blocker RC-P36-032/033 现在可关闭；但这只代表“签发条件中的工程前置项已具备”，不是 admission 已签发，更不是 paid three-cell artifact、研究质量或 Human acceptance 已证明。下一项是 `S3-T09-EXACT-THREE-CELL-DEEPSEEK-ADMISSION-ISSUANCE-DECISION`，必须另行授权；实际 execution 仍是之后的独立边界。
