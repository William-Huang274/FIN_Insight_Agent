# FIN 0.1 S3-T09 Specialist-v7 fresh exact admission 签发

## 授权与边界

用户以“继续”授权执行已冻结的
`S3-T09-OWNER-GRADE-SPECIALIST-V7-FRESH-EXACT-ADMISSION-ISSUANCE`。
本轮只允许把 decision 中的 prospective payload 原样持久化为
issued/unconsumed admission。

本轮不允许消费 admission、调用模型或 Provider、发起网络/source/tool 请求、
创建 canonical WorkUnit/Attempt/ResearchRun/Artifact、比较、Human Review、
T10、S4、release 或 production。

## 签发结果

- admission id：
  `fin01-s3-t09-three-cell-deepseek-owner-grade-v3-specialist-v7-research-lead-v3-writer-v2-exact-admission-r1`
- canonical digest：
  `9657d30751eea5f24ea26b73fa9d93909b2df0c9966f96539a405a9dde1e72a6`
- status：`issued_unconsumed_zero_call_preflight_pass`
- predicted ResearchRun：
  `research_run_fin01_ebf0f6376cec28087151562e`
- research profile：
  `fin01.s3.research_profile.nvda_three_cell:v1`
- transport：
  Specialist-v7 / Lead-v3 / Writer-v2
- issued at：`2026-07-23T16:53:27+08:00`

admission 文件逐字段等于 decision frozen payload。Pydantic profile gate、
canonical digest 和 executor factory 构造均通过；factory 构造没有调用
Provider。

## Target 只读审计

签发前后只用 direct SQLite `mode=ro`、文件 SHA-256 和 object-tree digest：

- WorkUnit/Attempt/ResearchRun/Artifact：`13/13/13/13`
- prospective WorkUnit/Attempt/ResearchRun：全部 absent
- database SHA-256：
  `dedd7e2e62b9a4092cfd2af7966554a9c5313f185b4dc67c555a7b6c4de60cd8`
- object-tree SHA-256：
  `b11b26b3cc28a872e64e8f27c69c7b1ef3b9fece9f2b5d8c0e6185da5a26bdc7`

签发前后摘要与逻辑快照不变，没有实例化 target CaseService。

## 执行前置条件

当前 `LLM_GATEWAY_TRANSPORT_RETRIES` 为 unset，因此 issuance 记录中的
`transport_retry_environment_zero=false`。这不影响只签发，但明确阻止直接
进入 exact-live execution。

未来执行必须同时满足：

1. 用户单独授权 exact-live execution；
2. `LLM_GATEWAY_TRANSPORT_RETRIES=0`；
3. fresh fail-closed preflight；
4. exact-once 消费；
5. 首个可信失败立即停止，无 retry/fallback/patch/normalize/rerun。

## 验证

- v7 issuance + decision + convergence contract：`23 passed`。
- JSON、JSONL、compile、diff 与 secret scan 在收口阶段执行。
- new admission=`1`；consumption/model/Provider/network/source/tool/
  WorkUnit/Attempt/Run/Artifact=`0`。

## 下一门禁

唯一下一项是
`S3-T09-OWNER-GRADE-SPECIALIST-V7-FRESH-EXACT-LIVE-EXECUTION`，尚未授权。
