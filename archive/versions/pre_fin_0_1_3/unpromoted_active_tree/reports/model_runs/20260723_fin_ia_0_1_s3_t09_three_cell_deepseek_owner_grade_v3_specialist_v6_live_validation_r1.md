# FIN 0.1 S3-T09 Specialist-v6 live validation R1

执行日期：2026-07-23（Asia/Shanghai）

结论：未通过研究产品验收。Specialist-v6 的 local canonical scope assembly 在第一 Cell 的真实路径通过，上一轮 `FY2025-FY` 被模型简写为 `FY2025` 的问题未复现；执行随后在第二 Cell 的 Fact support authority gate 因一个 Graph context ref 被当作 Fact support 而首错停止。

## 精确执行事实

- Admission digest：`1bcd6174896646b3d6ef220bffab29ba3e1039a333705daae981a28893ba6dcd`
- WorkUnit：`wu_p02_5_810ed409df27c6bb3a1b372e`
- Attempt：`attempt_fin01_d0815e4b459dc8d9d264e323`
- ResearchRun：`research_run_fin01_4f66728b8bd8b8c502a24b07`
- Provider / model：DeepSeek / `deepseek-v4-pro`
- 调用：4 model / 4 provider / 4 network
- token：14,162 input + 2,143 output = 16,305 total
- 成本：USD `0.00758315`
- retry / fallback / rerun：`0 / 0 / 0`
- WorkUnit / Attempt / Run：`failed / failed / failed`
- Artifact：0；orphan=false
- restricted capture / readback：`4 / 4`

## 修复效果

第一 Cell 的 facts、claim cards 和 WWC 三段全部通过。Claim scope 的 entity、business-scope、period 和 attribution 由 runtime 从 validated Numeric authority 装配，Provider 没有输出这些确定性字段；旧 period-token normalization failure 未重复。

这只证明第一 Cell 的 live conformance。Value/Profit claim segment、Lead-v3、Writer-v2 和 Verifier 均未到达，不能据此宣称完整三 Cell 或 Writer 修复通过。

## 首个可信失败

失败 stage：
`domain_specialist:value_and_profit_capture:facts_explanation_and_terminal`

失败 code：
`s3_bounded_specialist_fact_authority_invalid:value_and_profit_capture`

受限结构回放显示 3 Facts 共引用 6 个 support refs：5 个属于当前 Cell Numeric authority，1 个属于 Graph context；Evidence、Candidate 和 unknown 均为 0。Graph context 不能成为 Fact authority，strict validator 的拒绝正确。

项目内最早缺口是 `fact_layer.support_refs` 没有 field-local closed authority contract。下一步需要先零调用决定 exact Evidence/Numeric allowlist、Candidate/Graph prohibition 和 content-free typed telemetry；不得直接删改失败回答或重跑。

## 审计边界

post-run 复盘误用了 service-backed target read，导致 SQLite 物理摘要改变；逻辑 WorkUnit/Attempt/Run/Artifact counts 保持 `13/13/13/13`，本 Run 八个事件保持一致，没有新增业务对象或 Artifact。该 recurrence 记为 RC-P36-038，未来审计只允许 direct `mode=ro` 或 disposable clone。

下一项：
`S3-T09-OWNER-GRADE-SPECIALIST-FACT-SUPPORT-FIELD-LOCAL-AUTHORITY-ZERO-CALL-ROOT-CAUSE-DECISION`。
本轮不授权 v7、replacement admission、rerun、comparison、owner review、T10、S4、release 或 production。
