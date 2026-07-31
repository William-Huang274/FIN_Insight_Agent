# FIN 0.1 S2-T03 v4 Exact Admission 签发

日期：2026-07-20
状态：`issued / not_executed / not_consumed`

## 用户指令与边界

用户在明确了解“只签发”与“签发并执行一次”的区别后要求“签发”。本轮因此只创建和验证一次性运行许可证，不调用模型、不发起 provider/network 请求，也不创建真实 Agent Artifact。T03、T04、S3、release 与 production 均不因签发而解锁。

## 签发结果

- Admission contract：`configs/releases/fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v4_0.json`。
- Admission ID：`fin01-s2-t03-bounded-agent-v4-strict-tool-live-validation-r1`。
- Fresh WorkUnit idempotency key：`fin01-s2-t03-bounded-agent-work-unit-v4-strict-tool-r1`。
- Isolated runtime root：`.codex_runtime/fin01-s2-t03-v4-strict-tool-live-validation-r1`。
- Case/input：冻结 NVDA `demand_authenticity_and_sustainability` 单 Cell、Case v1、as-of 与既有 exact input digest。
- Provider transport：`deepseek-v4-pro`、`https://api.deepseek.com/beta`、v4 Specialist+Lead strict named-function output carrier。
- Budget：最多 3 semantic/provider/network calls，单 call 最多 1 transport attempt，retry=0，output token caps=1600/1000/900，total cost cap=USD 0.05。
- Hard boundary：source network=false、external tool=false、live business Case head write=false、automatic execution/retry=false。

`execution_enabled=true` 表示这份 admission 具备被后续明确执行指令消费的合同能力；它不表示本轮已经授权执行命令。当前 execution_started=false、execution_consumed=false。

## 验证与事实

- Admission JSON/Pydantic contract、fresh identity、v4 output contract、beta base、budgets 与 hard boundaries 通过 deterministic tests。
- 实际 prepare/zero-call preflight=`pass_no_model_call`；admission digest=`61e9e21033eb6ab31e7400067eb455b172d63e421ba42bdd5ca2b09a978639f6`，exact input match=true，candidate count=3，output-only cost ceiling=USD 0.003045。
- 凭据只检查存在性，不持久化值；provider health check 被固定为首个 admitted semantic call，不额外发送探测请求。
- 独立复核确认 admission ID fresh、v4 contract 与 beta binding 正确、retry/hard boundaries 闭合，preflight artifact 存在而 execution result 与 gateway events 均不存在；T01/T03 合同回归=`38 passed in 1.82s`。
- model calls=0；provider calls=0；network calls=0；external tool executions=0。
- live validation=0；ResearchRun/Artifact=0；真实业务 Case mutation=0。

## 下一步

下一项为 `S2-T03-V4-LIVE-VALIDATION-EXECUTION-DECISION`。只有用户明确要求“执行”后，才允许使用上述 exact admission、WorkUnit key 与 isolated root 执行一次；成功或失败均停止，不自动重试，不直接进入 T04。
