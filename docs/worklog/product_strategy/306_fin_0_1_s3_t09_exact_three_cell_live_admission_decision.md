# FIN 0.1 S3-T09：精确三 Cell live admission 决策

日期：2026-07-22

## 授权与结论

用户以“授权”只授权 `S3-T09-EXACT-THREE-CELL-LIVE-ADMISSION-DECISION`。本轮允许冻结 provider/model、六节点预算、credential env、fresh execution identity 方案和 immutable input binding；不允许签发或消费 admission，也不允许模型、Provider、网络、来源、外部工具、真实业务、Human Review、S4、release 或 production 动作。

结论是：Provider 目标方案已选，但 admission 不能签发。原因不是模型再次失败，而是签发前仍有两个项目自有的零调用前置缺口：六节点真实 Provider node adapter 尚不存在；exact S3 input digest 尚不能在 Run 创建前通过受支持的 prepare/preflight 入口冻结。

## 独立复核事实

- `S3ThreeCellAgentNodeExecutorPort` 当前只有 T08 测试中的 `_ReadinessNodeExecutor` 实现。生产 `build_bounded_agent_executor_for_admission()` 只构造历史 S2 `DeepSeekBoundedAgentExecutor`，不能执行三个 Specialist、Lead、Writer、Verifier 六节点。
- `create_app()` 只能注入外部提供的 S3 executor，没有从 exact S3 admission 构造真实 node adapter 的 factory。
- `_S3ThreeCellBoundedAgentAdapter.execute()` 在 WorkUnit、Attempt、ResearchRun 已创建后才编译 T02-T07 和 `S3ThreeCellBoundedAgentInputPack`。该 digest 又包含三种执行 identity 的 lineage；仓库没有 Run 前 prepare API/runner 来预测 identity、编译两次并核验 parity。
- T08 的 `case_d674...` 是 isolated deterministic fixture 结果，不是可复用 live admission Case；当前环境也没有配置 `FINSIGHT_P02_FIXTURE_ROOT`。因此 exact Case、accepted DecisionSurface、as-of 和 input digest 不能诚实填值。
- `DEEPSEEK_API_KEY` 只做 presence check，值未读取、输出或持久化。

## 冻结的目标方案

- Provider/model：`deepseek / deepseek-v4-pro`，`https://api.deepseek.com/beta`，credential env=`DEEPSEEK_API_KEY`。
- Transport 方向：沿用 S2 已成功的 segmented 思路，但升级为六个 node-specific closed JSON 输出；每节点做 native JSON、duplicate-key、schema、authority 和 semantic fail-closed，不复用已退役的 strict named-tool 路线，也不放宽 canonical S3 输出合同。
- Calls：3 Specialist + Lead + Writer + Verifier，semantic/provider/network 上限均为 6；每节点只允许 1 transport attempt，retry/fallback/broad rerun=0。
- Budget：每个 Specialist 1400 output tokens、Lead 1200、Writer 1400、Verifier 1000，最大 aggregate output 7800 tokens，total cost cap USD 0.10。
- Fresh public identity：WorkUnit idempotency key=`fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1`；isolated runtime root=`.codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1`；不可复用。
- Source network、external tool、live Case head write、automatic fallback 全部关闭。

## 最早 owner 与下一步

最早 owner 仍是 `apps/workbench/backend/application/bounded_agent_executor.py`，需要实现一个 DeepSeek segmented 六节点 adapter 和 admission factory。紧邻的 input-preflight owner 是 `apps/workbench/backend/application/research_runtime.py`：应在同一 Runtime 编译器上增加只读 prepare 路径，绑定一个持久化 isolated NVDA Case、accepted DecisionSurface、as-of 和预测的 WorkUnit/Attempt/Run identity，并证明两次编译 digest 完全一致；实际 Runtime 在首个 Provider call 前必须再次核验同 digest。

下一项冻结为 `S3-T09-DEEPSEEK-SIX-NODE-TRANSPORT-AND-EXACT-INPUT-ZERO-CALL-PREFLIGHT-REPAIR`，仍需单独继续指令。修复通过后，才可以另行决定是否签发 admission；签发与执行仍是两个独立授权边界。

## 安全与未执行项

本轮 admission/model/provider/execution network/source network/external tool/live business/Human Review/paid run 全部为 0。没有修改或创建真实业务 Case，没有执行模型实验或 inference job。回滚只需移除本决策记录及测试，并把 backlog/context/ledgers 恢复到 T08 next；T08 adapter 代码和 S2 历史合同不需改写。

确定性验证结果：T09 + T08 adapter + S2 T03 compatibility 共 `82 passed in 16.80s`；release JSON 和 Project OS JSONL 全部可解析；`git diff --check` 通过（只有既有 JSONL 的 CRLF normalization warning）；changed-surface secret scan 未发现 plaintext key/private key。Project OS broad full-chain preflight 按预期返回 `blocked`，精确列出 RC-P36-032/033 两个 owned blocker；这不是测试失败，而是本决策要求的 fail-closed 结果。
