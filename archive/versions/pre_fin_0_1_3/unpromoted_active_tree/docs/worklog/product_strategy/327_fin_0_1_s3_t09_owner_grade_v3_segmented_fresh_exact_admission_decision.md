# FIN 0.1 S3-T09：owner-grade v3 segmented fresh exact admission 决策

日期：2026-07-22

## 结论

用户以“授权”只允许 `S3-T09-OWNER-GRADE-V3-SEGMENTED-SPECIALIST-FRESH-EXACT-ADMISSION-DECISION`。决策已通过，admission 尚未签发；模型、Provider、网络、source、tool、canonical Run/Artifact、paired comparison 和 Human Review 均未执行。

## 决策证据

Project OS scoped preflight 为 pass。目标 runtime 当前精确包含四个历史 Run：旧 Agent failed、output-v2 succeeded、same-input deterministic baseline succeeded、consumed monolithic output-v3 failed；后者仍为 0 Artifact，不允许复用。

所有 Runtime/Service 初始化与 exact input prepare 都在 disposable clone。两次 prepare 结果完全一致，冻结：

- execution identity：`fin01-s3-t09-three-cell-deepseek-owner-grade-v3-segmented-live-validation-r1`；
- WorkUnit：`wu_p02_5_188c135034fd8ab3a921ba08`；
- Attempt：`attempt_fin01_753df78d2dd4eed1940beb09`；
- ResearchRun：`research_run_fin01_613dad1d30f9ce5357213b21`；
- input digest：`41179ecdca0853e0e4d1a49af6ada129cb5bfae5913891b0a184eb900a60dd05`；
- prospective admission digest：`8ac50f35b786f954db11d36b851145f8e476653a2be887124c7ad33fdafc17a9`。

新 identity 与四个既有 Run 全部不同，业务 input-head、Case/version、DecisionSurface、as-of 和三 Cell 不变；deterministic baseline 的 body/artifact 不进入 Provider input。

## 冻结的 admission 合同

prospective admission 使用 DeepSeek `deepseek-v4-pro`、canonical output-v3 和 `fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v1`。每个 Specialist 三段预算为 1600/1200/1400，三个 Specialist 加 Lead/Writer/Verifier 的 aggregate 为 16,200；semantic/provider/network 上限均为 12，USD cap=0.10，transport attempt=1，retry/fallback/repair/rerun=0。任一 parse、shape、schema、semantic 或 length failure 都必须立即 terminal fail-closed。

prospective schema、factory 和 digest 已在不触发 callback 的情况下复验。目标 canonical DB digest `91ea473f...f39c`、Object digest `00ac740b...a75` 及逻辑快照前后不变。当前环境的 `LLM_GATEWAY_TRANSPORT_RETRIES` 仍是 unset/nonzero，因此即使未来签发，执行前也必须单独设置为 0 并重新 fail-closed 预检。

决策、clone reproduction、历史 current-backlog 与 segmented transport 相关回归共 `82 passed`，prepare script compile 通过。

## 下一步与边界

当前下一项为 `S3-T09-OWNER-GRADE-V3-SEGMENTED-SPECIALIST-FRESH-EXACT-ADMISSION-ISSUANCE`，需独立授权。下一步只能把本轮冻结的 payload/digest 原样写成 admission；不能消费、执行模型、创建 Run/Artifact、比较 baseline、Human Review 或进入 T10/S4/release/production。
