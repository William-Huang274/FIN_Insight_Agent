# FIN 0.1 S3-T09 nullable-owner＋supervision-v2 最终 exact-live 失败

日期：2026-07-25

## 授权与结论

用户明确授权依次进入新 admission、最终 exact-live 和 T09 整体验收。fresh proof 与 admission issuance 已通过后，唯一允许的 admission `854a29f299c1d86f1cb86d75f97b0f344f13f9275a04298120789e44d9734f31` 通过 supervision-v2 exact-once 消费。

本次运行在 Research Lead 首错终止，不能进入九 Artifact 检查、paired comparison 或 owner acceptance。没有进行 retry、fallback、patch、replay、relaunch 或 rerun。

## 运行事实

- WorkUnit：`wu_p02_5_870d16faa31ee622a270a581`
- Attempt：`attempt_fin01_747d6459f09956ced4a50f2e`
- ResearchRun：`research_run_fin01_6594b12567cdebecd441d31d`
- model/provider/network calls：`10/10/10`
- input/output/total tokens：`38,849/4,914/43,763`
- estimated cost：USD `0.01797197`
- transport attempts：`10`，每次调用一次
- restricted capture/readback：`10/10`
- source network/external tool/live business head writes：`0/0/0`
- terminal states：`failed/failed/failed`
- orphaned run：`false`
- canonical Artifact：`0`

九个 Specialist segments 均完成；Research Lead 是第 10 次调用。Memo Writer 与 Verifier 没有被调用。

## Research Lead 安全审计

受限 capture 只读取结构与长度，不把模型正文复制到 release result 或 worklog。Research Lead 返回 native JSON，顶层四个字段与基数均合法，`finish_reason=stop`，输出为 1,103 tokens、5,195 UTF-8 bytes。

profile-v3 明确绑定：

- 单项质量目标：320 字符，超出只形成非终态 quality observation；
- 单项硬上限：512 字符；
- 全部 narrative 合计硬上限：3,200 字符。

三个 `cross_cell_dependencies.statement` 的长度分别为 571、533、528，超出硬上限 59、21、16 字符；全部 narrative 合计 3,875，超出总上限 675。runtime 因 `s3_bounded_research_lead_v3_text_item_over_max_unicode_characters` fail-closed，并正确报告 `failing_item_count=3`。

这是对明确 Provider-visible 长度合同的直接模型输出不合规，不是 output-v4 Verifier request/validator schema drift，也不是 supervision 问题。`RC-P36-047-s3-research-lead-v5-per-field-narrative-length-contract-gap` 因 profile-v3 硬安全边界被真实触发而重新成为最早 blocker；本轮不自动选择 repair 或 Provider route。

## Supervision-v2 fresh-live 证据

supervision-v2 直接启动 actual runner，无中间 wrapper。launch 与 exit receipt 的 PID 和 Windows creation FILETIME 完全一致；runner 在 top-level finally 自行写出 exit receipt，退出码 0，runtime 结果和 stdout/stderr 摘要均完整。监督器未发送 signal，retry/fallback/replay/relaunch 均为 0。

因此 `RC-P38-053-windows-detached-wrapper-exit-receipt-loss` 的 supervision-v2 路线获得 fresh-live 正证据。Verifier 未到达，所以 nullable `repair_owner` state-machine-v2 仍不能宣称 fresh-live 通过。

## T09 验收状态

T09 的整体验收前置条件是 terminal succeeded 与九个 canonical Artifacts。本轮是 terminal failed、Artifact=0，故：

- 九 Artifact 产品检查未开始；
- paired deterministic baseline comparison 未执行；
- owner acceptance 未执行；
- S3-T09 仍 blocked；
- T10、S4、release 与 production 不得进入。

下一项仅为：

`S3-T09-FINAL-EXACT-LIVE-RESEARCH-LEAD-HARD-NARRATIVE-NONCONFORMANCE-DISPOSITION-DECISION`

该项需要用户决定 blocked closeout/carry-forward，或另行授权新的 generalized repair/proof 路线；当前不允许第二次 live execution。
