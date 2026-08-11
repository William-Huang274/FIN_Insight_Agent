# FIN 0.1 S4-T05 R8 Specialist 三层容量根因处置

日期：2026-07-28

范围：`RC-P36-065` zero-call root-cause disposition only

结论：R8 的直接失败不能归因模型；项目把同一个 8,192-byte 值同时当作单个本地展开段与三段 union 的上限，当前合法状态空间不闭合。

## 证据与判断

- R8 历史事实保持不变：九个 Specialist Provider calls 均 `ok/stop`，第三 Cell 在三段完成后的本地 assembly 失败；三态 failed、Artifact=0、无 retry/rerun。
- 本轮未读取 restricted Provider text；R8 exact assembled byte count 仍未知，未猜测具体字段贡献。
- DELL profile-v2 把 WWC token cap 提到 1,800、Specialist cap 提到 4,600，却继承 `segment=6,000 / assembly=8,192`。
- runtime 用 `8,192` 先允许每个 locally expanded segment，再用同一个 `8,192` 校验三个 segment 的 whole union。
- 现有 WWC max-shape fixture 只证明三项 160 字符 atom 的 Provider wire ≤4,800；完整 fake chain 使用 32 字符 WWC narrative，不是 whole-output maximum fixture。
- 公开 deterministic DELL fixture 在最大声明 cardinality 与文本上限下形成三个合法 whole Specialist：`12,353 / 12,278 / 12,405 bytes`。Facts、Claims、WWC Provider-visible segments 全部 ≤6,000；WWC local-expanded segment ≤8,192；semantic/authority/identity/canonical validators 均先通过。

因此，最早项目根因是 capacity owner collision，而不是 DeepSeek 指令遵循失败，也不是需要再次逐字段减字。

## 选择的结构合同

冻结 `fin01.s3.specialist_local_assembly_capacity.validated_segment_union_upper_bound:v1`：

- Provider raw segment cap 保持 6,000 bytes；
- WWC atom wire cap 保持 4,800 bytes；
- 每个 locally expanded valid segment cap 保持 8,192 bytes；
- 三段 whole union 上限由 `3 × 8,192 = 24,576 bytes` 确定；
- Provider schema、Specialist-v8、token/cost、cardinality、authority、identity、lineage 与 canonical validators 不变；
- future DELL research profile 使用 v3；Provider wire 不变，不创建 Specialist-v9；
- overflow 仍是 L1 hard capacity failure，不降级为质量 finding；
- failure telemetry 必须持久化 segment count、各段 byte counts、whole observed/limit 和 phase，但不得持久化 raw text、private reasoning、credential、stack 或 exception message。

拒绝按 R8 未知 overage 任意扩容、截断/压缩/丢弃合法研究内容、逐字段 prompt 补丁或在 T05 扩成全节点 atomization。dependency/conflict、Writer/Verifier atomization 与 cross-provider strict schema matrix 继续后传到 S4-T10→S5。

## 本轮完成与验证

- 新增 root-cause disposition JSON；
- 新增 deterministic contract test，复现三个合法 >8,192-byte whole outputs；
- 更新 program/detailed backlog、S4/Program execution plans 与 Project OS；
- focused contract：`6 passed`；相邻 v5/v8 assembly、typed envelope 与 R8 historical pointer 回归：`29 passed`。

本轮 model/provider/execution network/source/external tool/restricted capture read/admission/Run/Artifact/paired/Human 全为 0。没有 runtime implementation、fresh proof 或 exact-live。

## 下一步

`S4-T05-DELL-R8-SPECIALIST-VALIDATED-SEGMENT-UNION-CAPACITY-AND-SAFE-BYTE-TELEMETRY-MINIMUM-ZERO-CALL-IMPLEMENTATION`

只实现三层 capacity resolver、DELL profile-v3、safe byte telemetry、maximum-cardinality full fake chain 与 over-limit negative fixture。fresh proof、admission、R9 exact-live、paired assessment、owner acceptance 和 S4-T06 均需后续独立授权。
