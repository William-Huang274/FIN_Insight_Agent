# P38 Point 01 M2.2 Full Serializer / Readback

日期：2026-07-12

状态：`m2_2_full_implemented / calibrated_atomic_readback_multiversion_corpus / shadow_only`

## 完成

- 新增 `DecisionSurfaceBundleAssembler`、`DecisionSurfaceArtifactSerializer` 和 `DecisionSurfaceReadbackVerifier`。
- envelope 同时保留 validated input、exact PackResolution/Case Delta、selection rationale、composition/fact-to-slot/WWC lineage、compiled slot/typed gaps、legacy semantic migration/information-loss review 和 compiler observations。
- 利用 M1 的单事务写 Contract/Cell/Slot/Gap、Artifact、Attempt/WorkUnit 与 events；object-store failure 不产生 canonical artifact 或终结 Attempt。
- 增加 canonical store version read，并让 `get_decision_surface(contract_id, version)` 正确读取同一 contract 的历史 Cell/Slot/Gap 版本。

## 校准与验证

- M2.2 fixture 覆盖 Case Delta、10 cells、typed parser gap、atomic commit/readback、object-store failure、selection mismatch、typed-gap drop、legacy direct-equivalence 和 v1/v2 historical replay。
- targeted M2/M1 runtime contract suite：`38 passed`；之后纳入 M2.10 aggregate gate。
- 没有模型、外部检索、Evidence/Writer、legacy write 或 authority change。

## 边界与回滚

- 只完成 deterministic artifact serializer；不把 prefilled fixture 或 envelope 当作 model compiler。
- 回滚为移除 serializer/readback layer 并保留 append-only historical rows；legacy TaskRun 不受影响。
