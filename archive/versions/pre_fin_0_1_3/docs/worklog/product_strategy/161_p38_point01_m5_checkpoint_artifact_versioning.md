# 161 P38 Point 01 M5 Checkpoint Artifact Versioning

日期：2026-07-12

状态：`M5.3 deterministic temporary-store checkpoint artifact fixture pass`

## 授权与范围

当前线程 user 要求继续 M5，因此实施 M5.3。范围限定为 temporary SQLite canonical store 内的 checkpoint/artifact immutable version lifecycle；不启动 worker/service、不扩大 runtime admission，也不把 checkpoint 当成无界 context persistence。

## 已实现

- `CheckpointArtifactService` 与 `RuntimeFacade.create_checkpoint_version()`：checkpoint 使用既有 `ArtifactVersionEnvelope`，`artifact_type=runtime_checkpoint`，不引入第二套 checkpoint store；
- 版本化 write：要求 leased running Attempt、WorkUnit CAS、checkpoint expected version 和准确 direct supersession parent；版本为 append-only `<checkpoint_id>:vN`；
- bounded snapshot：序列化 checkpoint snapshot 上限为 `262,144` bytes，超限在 object/row/event 之前 fail-closed；
- 原子 canonical identity：artifact row、`CHECKPOINT_VERSION_CREATED` event 与 idempotency receipt 在同一 SQLite transaction 内提交；object store failure 不会发布 row/event；
- exact read/recovery：只接受 `:vN`，同时校验 object digest、schema ref、snapshot digest、producer Attempt、input head 与 artifact identity；
- M5.2 integration：resume/fork 现在只接受 `runtime_checkpoint`，而不是任意 artifact；checkpoint v1 能在失败后被 resume 读取；
- checkpoint v2 保留 v1 可读性，stale writer fail-closed，replay/read view 显示 checkpoint version/supersession 关系。

## 验证

- M5.3 contract tests：artifact/event atomicity、object write failure、idempotency、v1/v2 supersession、stale writer、restart exact read、M5.2 resume integration；
- M5.1-M5.3 focused suite：`18 passed`；
- `scripts/engineering/run_point01_m5_3_checkpoint_artifact_fixtures.py`：`pass`，checkpoint artifact/event 均为 `2`，stale writer 被拒绝，SQLite reopen 精确读取 v2；
- JSON Schema bundle 已重新导出；M1 fixed-hash gate 随后通过，shared fast-contract regression 为 `148 passed`，compileall 与 PostgreSQL logical conformance 也通过。

## 原子性与剩余边界

SQLite canonical row/event/receipt 是原子边界；content-addressed object 写入后若 transaction 随后 abort，可能物理存在但没有 artifact row、event 或 recovery identity，因而不可被 runtime 读取。M5.3 不包含 checkpoint compaction、GC、无界 context persistence、worker/service、provider/tool、Evidence/Writer/full-chain、业务 Case mutation 或 legacy authority change。下一项 M5.4 才拥有 capability security/sandbox，M5 仍不能 closeout。
