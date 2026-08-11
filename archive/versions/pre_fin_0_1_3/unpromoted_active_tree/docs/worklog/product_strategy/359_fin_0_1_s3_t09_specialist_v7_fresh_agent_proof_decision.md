# FIN 0.1 S3-T09 Specialist-v7 fresh Agent proof 决策

## 授权与边界

用户以“继续做下一步”授权执行当前冻结项
`S3-T09-OWNER-GRADE-SPECIALIST-V7-FRESH-AGENT-PROOF-DECISION`。
本轮只允许零调用决策：冻结全新身份、exact input、research profile、
prospective admission、预算、首错停止与审计边界。

本轮没有签发或消费 admission，没有模型、Provider、网络、source、tool、
canonical Run/Artifact、业务 Case、comparison 或 Human Review 写入。

## 独立决策

决定允许在后续独立授权下签发一次新的 Specialist-v7 exact admission。
选择继续使用 DeepSeek `deepseek-v4-pro`，原因不是其输出已被产品接受，
而是 v7 已以 deterministic fixture 证明：

- Provider 旁路只能在当前 Cell 的 exact Evidence/Numeric 集合内选择 Fact support；
- Candidate/Graph 只能作为 context；
- Prompt 和本地 validator 共用 `closed_fact_support_authority:v1`；
- 首个可信错误立即 fail-closed，不进行 normalize、drop、fallback、retry 或隐藏 rerun。

成功目标仍是六个逻辑节点和九个 Artifact；即使成功，也只进入 paired
comparison，不能直接视为 owner acceptance 或 S3-T09 通过。

## 冻结结果

- prospective admission id：
  `fin01-s3-t09-three-cell-deepseek-owner-grade-v3-specialist-v7-research-lead-v3-writer-v2-exact-admission-r1`
- prospective admission digest：
  `9657d30751eea5f24ea26b73fa9d93909b2df0c9966f96539a405a9dde1e72a6`
- predicted ResearchRun：
  `research_run_fin01_ebf0f6376cec28087151562e`
- research profile：
  `fin01.s3.research_profile.nvda_three_cell:v1`
- Specialist / Lead / Writer：
  v7 / Lead-v3 / Writer-v2
- semantic / Provider / network calls：`12 / 12 / 12`
- aggregate output tokens：`16800`
- max total cost：`USD 0.10`
- retry / fallback / rerun：`0 / 0 / 0`

两次 disposable-clone prepare 得到相同 payload digest
`111928c1ecceb03975f9ca1521e681db891110338cb590179d5e9ed4a3518b52`。
clone 前后 WorkUnit/Attempt/ResearchRun/Artifact 均为 `13/13/13/13`。
target database 与 object tree 摘要前后分别保持
`dedd7e2e...60cd8` 和 `b11b26b3...6bdc7`。

## RC-P36-038 审计纪律

target 不允许实例化 CaseService 或其他会触发 migration 的 service。
target 只可使用 direct SQLite `mode=ro`、文件摘要和 object-store read；
所有 service-backed prepare 必须在 disposable clone 中完成。

## 验证

- v7 decision + convergence contract：`18 passed`。
- 旧 segmented decision 行为断言：`9 passed`；
  另有 `2` 个历史测试仍把可变全局 backlog 固定在旧节点，属于已知 snapshot
  测试债务，不是本轮 prepare/profile/digest 行为回归。
- Python compile、JSON/JSONL、diff 与 secret scan 在收口阶段执行。

## 下一门禁

唯一下一项是
`S3-T09-OWNER-GRADE-SPECIALIST-V7-FRESH-EXACT-ADMISSION-ISSUANCE`。
它尚未授权。签发只能原样持久化已冻结 payload，不能消费或调用 Provider。

当前 `LLM_GATEWAY_TRANSPORT_RETRIES` 为 unset；未来即使 admission 已签发，
exact-live execution 前也必须显式设为 `0`，且 live execution 仍需再次独立授权。
