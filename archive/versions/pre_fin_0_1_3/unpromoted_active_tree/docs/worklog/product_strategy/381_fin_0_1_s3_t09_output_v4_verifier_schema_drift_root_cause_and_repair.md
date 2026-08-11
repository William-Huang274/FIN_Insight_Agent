# FIN 0.1 S3-T09 output-v4 Verifier schema drift 根因与修复

日期：2026-07-24

## 授权和顺序

用户要求先修复 exact-live 当前最早 blocker，再执行一次 fresh exact-live；只有完整链成功并生成九类 Artifact，才进入 T09 成品检查、配对比较和 owner 验收材料。禁止自动 retry、fallback 或第二次 replacement live。

## 根因

RC-P36-049 是项目内 request/validator schema drift：

- output-v4 Verifier request 仍声明旧 `layer/status/issues` finding；
- 本地 output-v4 validator 要求 `layer/status/issue_codes/artifact_or_claim_refs/repair_owner`；
- Provider 严格遵循请求，因此不是模型不合规；
- fake Provider 直接返回预制五字段对象，没有核对 `required_output_schema`，掩盖了漂移。

## 最小修复

- 新增共享 `S3_TYPED_VERIFIER_OUTPUT_CONTRACT_REFS`，同时包含 output-v3/v4；
- request builder 和 validator 消费同一集合；
- 不放宽 validator，不增加 normalize/fallback，不修改 v1/v2；
- fake Provider 在 Verifier 节点检查预制输出字段是否与 request schema 一致；
- 历史失败测试改为验证持久化事实，不要求已修复 bug 在当前代码中继续复现。

## 初步验证

ClaimFactLinkPolicy、历史 live-result 和 segmented-owner-grade 三组聚焦回归合计 `32 passed`；扩大到 output-v4 scoped identity、Lead-v5、Writer/Verifier、capture 与九 Artifact fake path 后为 `95 passed`。output-v4 full fake 继续达到六逻辑节点、12 calls、9 Artifacts，并由测试断言 Verifier request 使用五字段 typed schema。真实 model/provider/network/source/tool/admission/Run/Artifact 均为 0。

## 后续门槛

扩大 deterministic regression 通过后，生成全新不可复用 proof/admission；process-local retry=0，exact-once 实跑，首个可信硬失败停止。只有 terminal succeeded、12 calls、9 Artifacts、ClaimFactLinkPolicy/typed Verifier/identity/capture 全部通过，才进入 T09 配对比较。Owner acceptance 必须由用户确认，Codex 不代签。

## 后续实跑结果

fresh admission 已 exact-once 消费，12 个阶段均完成 Provider `stop`，Verifier typed schema 修复未复发；但外层执行控制器在 Verifier capture 后、canonical Artifact/成功终态事务前中止，留下 0 Artifact 的运行态孤儿。该孤儿已通过零模型 typed closeout 收敛为三态 failed，未 retry/fallback/rerun。详情见 `382_fin_0_1_s3_t09_output_v4_verifier_schema_repair_exact_live_orphan_closeout.md`。因此 RC-P36-049 获 live-path positive evidence，但 T09 完整产品和验收 gate 仍未关闭。
