# FIN 0.1 S3-T09：output-v2 replacement live execution

日期：2026-07-22

## 结论

用户以“授权”只允许 `S3-T09-REPLACEMENT-EXACT-LIVE-EXECUTION`。唯一 output-v2 admission 已 exact-once 消费并 terminal succeeded：WorkUnit、Attempt、ResearchRun 三态一致，形成 23 个 Run events 和 9 类 canonical Artifact。没有 retry、fallback、rerun、source network、external tool 或 live Case head write。

这证明首节点 truncation 的项目内修复真实有效，RC-P36-035 可关闭为 live-proven；但 T09 尚不能最终接受，因为 `agent_fallback_comparison` 明确为 `pending_distinct_terminal_deterministic_run`，owner review 未执行。新 root cause `RC-P36-036` 记录该 paired-baseline 缺口，T10 继续 blocked。

## 执行前 runner 修复

现有 runner 只认识 consumed r1 admission 的硬编码 ID/digest/identity，并假设同一 Case store 必须全空；直接用于 replacement 会把历史 terminal r1 错判为当前 identity 已消费。修复后 runner 从 immutable issuance 加载 exact target，只检查目标 WorkUnit/Attempt/Run，同时保留旧 r1 默认路径和 consumed guard。临时共享 store 先执行旧 r1 fake failure、再执行 replacement fake failure的回归 `4 passed`，两个 identity 均独立且各自拒绝复用。

## Live 结果

- Admission：`fin01-s3-t09-three-cell-deepseek-segmented-output-v2-exact-admission-r1`。
- Run：`research_run_fin01_c24bc3ce28a3ecfafa6ce7c2`。
- Provider/model：DeepSeek / `deepseek-v4-pro`。
- Calls：model/provider/network=`6/6/6`。
- Tokens：input 14,833、output 2,850、total 17,683。
- Estimated cost：USD 0.00893187，低于 USD 0.10 cap。
- 所有 6 个节点 `finish_reason=stop`、transport attempt=1。
- Terminal：WorkUnit/Attempt/Run=`succeeded/succeeded/succeeded`，Artifact=9，events=23，orphan=false。

三 Specialist receipt 的 model-view v1 digest 与签发决策完全一致。Demand 保持 `typed_cannot_infer`，Value 为 `value_capture_unattributed`，Bottleneck 为 `typed_gap_source_followup_required`；公司整体 FY2025 数值行被保留，但没有伪造 segment/product attribution。Lead、Writer 和 Verifier 全部完成，machine verifier 的 deterministic integrity、semantic fidelity、financial coherence、visual delivery 四层均 pass，决策为 `accept_for_internal_review`。

## 研究质量边界与下一步

本轮证明 Agent 能在严格边界内完成三 Cell 工作底稿和报告，但没有 live Evidence promotion、没有新来源、没有超出冻结 numeric pack 的新指标，也没有投资 Alpha；machine verifier 不是 Human acceptance。

收口验证已完成：runner shared-store/target/non-reuse fixture `4 passed`，S3 当前状态快速合同 `35 passed`，完整 T09 admission/repair/result 合同 `44 passed`；Project OS scoped preflight 为 pass 且 open full-chain blocker=0，JSON/JSONL 解析通过，新增差异凭据扫描命中 0，Git diff check 无错误。

当前唯一下一项是 `S3-T09-REPLACEMENT-LIVE-ARTIFACT-READ-ONLY-VALIDATION-AND-PAIRED-BASELINE-DECISION`。它需单独授权，只读核验 exact artifacts 并确定是否已有 same-input terminal deterministic baseline；若不存在，必须停下再决定是否物化，不得自动进入 T10、S4、release 或 production。
