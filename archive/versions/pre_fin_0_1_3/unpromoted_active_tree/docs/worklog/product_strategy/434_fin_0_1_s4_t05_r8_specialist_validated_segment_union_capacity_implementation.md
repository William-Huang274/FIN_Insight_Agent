# FIN 0.1 S4-T05 R8 Specialist validated-segment union capacity 实现

日期：2026-07-28

范围：`RC-P36-065` minimum zero-call implementation only

## 问题与实现

上一项已确认 DELL profile-v2 把 `8192 bytes` 同时用于单个 locally expanded segment 与三个 validated segments 的 whole union，导致合法状态空间不闭合。本轮没有读取 R8 restricted text，也没有调用模型或签发 admission。

实现 `fin01.s3.specialist_local_assembly_capacity.validated_segment_union_upper_bound:v1`：

- 新增 DELL research profile-v3；
- Provider raw segment 保持 6,000 bytes；
- WWC atom 保持 4,800 bytes；
- 每个 locally expanded segment 保持 8,192 bytes；
- 三段 whole union 由共享 resolver 计算为 `3 × 8,192 = 24,576 bytes`；
- inner segment validation、inner union assembly 与 executor post-node validation 共同消费同一 resolver，消除第二个旧 8,192-byte whole gate；
- Specialist-v8 wire、token/cost、cardinality、authority、identity、lineage 与 canonical validators 均未改变；
- overflow 继续使用 `s3_bounded_specialist_output_byte_budget_exceeded` L1 hard failure。

新增 typed `specialist_local_assembly_capacity` telemetry，只记录 contract、segment count、各级 limit、observed segment/whole byte counts 与 failure phase；不记录 raw text、private reasoning、credential、stack 或 exception message。

## 零调用证据

- DELL profile-v3 能通过现有 versioned case-runtime overlay 生成 effective binding；
- maximum-cardinality/high-density fake 使用每 Cell 3 Facts、2 Claims、3 WWC atoms，Facts/Claims narrative=320 字符、WWC atom narrative=160 字符；
- 完整 fake chain 达到 6 logical nodes、12 Provider callbacks、9 business Artifacts 并成功终止；
- 24,577-byte one-byte-over fault 保持 hard fail；
- 第三个 Specialist fault injection 在 9 callbacks 后终止，并保留 9 usage receipts 与 9 restricted captures；
- focused=`5 passed`；相邻 v5/v8 assembly、typed envelope 与 disposition regression=`31 passed`。

真实 model/provider/execution network/source/external tool/restricted R8 capture read/admission/WorkUnit/Attempt/Run/business Artifact/paired/Human 全为 0。

## 边界与下一步

RC-P36-065 目前只达到 `runtime_injected / node_level_consumed / fixture_proven`，尚不是 fresh proof 或 live repair。R8 历史失败保持不可变；DELL R2、paired assessment、owner acceptance 与 S4-T06 均未通过。

下一项：

`S4-T05-DELL-R8-SPECIALIST-VALIDATED-SEGMENT-UNION-CAPACITY-FRESH-AGENT-PROOF-DECISION`

dependency/conflict、Writer/Verifier atomization、general all-node judgment atom 与 cross-provider strict schema matrix 继续后传到 S4-T10→S5。
