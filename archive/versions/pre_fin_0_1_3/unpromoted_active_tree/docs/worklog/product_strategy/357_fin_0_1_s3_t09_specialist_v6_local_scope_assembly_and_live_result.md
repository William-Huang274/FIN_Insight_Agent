# 357 — FIN 0.1 S3-T09 Specialist-v6 local scope assembly 与 fresh live 结果

日期：2026-07-23

用户授权继续修复并执行一次真实调用。Project OS 复核确认 RC-P36-043 的最早可控根因不是 strict validator，而是 Specialist-v5 要求 Provider 复述 `entity_ref / business_scope / period / attribution` 等确定性 authority token。真实回答把 `FY2025-FY` 简写为 `FY2025`，说明该职责分配不稳定。

本轮新增显式 Specialist-v6。Provider 的 Claim scope 只输出 `metric_or_mechanism`；runtime 从 validated `support_fact_ids → Fact support_refs → Numeric authority` 精确装配 entity、business-scope kind/ref、period 和 attribution。多个 Numeric authority 的确定性字段不一致时 fail-closed；无 Numeric 支持时绑定 `unknown/unknown/unknown/unknown/none`；Provider 若仍输出 period 等本地字段则按 shape error 拒绝，禁止静默 normalize。v1-v5 保持不变。

deterministic 验证覆盖精确 `FY2025-FY` 装配、Provider 擅自输出 `FY2025` 的拒绝、三段 Specialist node、六逻辑节点/12 fake calls/9 Artifact 完整路径，以及 v5、Lead-v3、Writer-v2、capture/terminal 共享回归，结果为 `76 passed, 5 deselected`。fresh double-prepare 前后 WorkUnit/Attempt/Run/Artifact=`12/12/12/13`，目标数据库和对象树不变；Project OS scoped preflight 与 runner exact preflight 均通过。

新 admission `1bcd6174896646b3d6ef220bffab29ba3e1039a333705daae981a28893ba6dcd` 只消费一次。第一 Cell 的三个 Specialist segments 全部通过，说明 v6 local scope assembly 已进入真实路径，旧 period-token failure 未复现。第 4 次调用的 Value/Profit `facts_explanation_and_terminal` 段被 strict Fact authority gate 拒绝。

受限回放仅做结构分类：输出含 3 Facts、6 个 support refs；其中 5 个为合法 Numeric、1 个为 Graph context，Evidence/Candidate/unknown 均为 0。最早新项目缺口是 facts 段的 `support_refs` 仍只有泛化“exact authorized ref”，没有像 claim `context_refs` 一样在字段旁绑定 exact Evidence/Numeric allowlist、禁止 Candidate/Graph、并提供 content-free subtype/count。登记 RC-P36-044，禁止通过删掉 Graph ref 或放宽 gate 让旧回答过关。

最终 WorkUnit/Attempt/Run=`failed/failed/failed`，orphan=false，Artifact=0；调用=`4/4/4`，tokens=`14162/2143/16305`，成本 USD `0.00758315`，retry/fallback/rerun=0。四份 final assistant outputs 均受限持久化并可回读。

收口审计另触发 RC-P36-038 recurrence：为读取 capture 实例化 target `CaseService`，改变了 `canonical.sqlite` 物理摘要；逻辑 counts 仍为 `13/13/13/13`，本 Run 事件仍为 8，没有新增业务对象或 Artifact。以后 post-run audit 只能使用 direct SQLite `mode=ro` 加对象存储读取，或 disposable clone，不能复用 service-backed target helper。

S3-T09 继续 blocked。下一项冻结为
`S3-T09-OWNER-GRADE-SPECIALIST-FACT-SUPPORT-FIELD-LOCAL-AUTHORITY-ZERO-CALL-ROOT-CAUSE-DECISION`；
未经新授权不得实现 v7、签发 admission、调用模型、rerun、比较、Human Review、T10、S4、release 或 production。
