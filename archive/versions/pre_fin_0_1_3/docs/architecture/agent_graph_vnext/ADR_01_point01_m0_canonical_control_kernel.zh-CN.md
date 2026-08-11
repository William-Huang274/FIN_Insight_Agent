# ADR_01：Point 01 M0 Canonical Control Kernel

日期：2026-07-12

状态：`accepted_for_m0_foundation_only / feature_flag_off / no_runtime_cutover`

上游：SCHEMA_01、DB_01、API_01、MIGRATION_01。

## 1. 决策

Point 01 M0 在 `src/sec_agent/canonical_runtime/` 建立隔离的 canonical control kernel，包含：

- Pydantic v2 canonical schemas 与 JSON Schema export；
- backend-neutral repository/object-store ports；
- SQLite WAL adapter 与 PostgreSQL-compatible logical contract；
- in-process `RuntimeFacade` command/event boundary；
- 默认关闭、仅允许 `shadow` 的 feature flag；
- deterministic contract tests、replay 与 rollback drill。

M0 不修改 `r53_r60_runtime_task_spine.py` 的业务状态模型，不让 canonical lane 成为全局 TaskRun authority。Legacy integration 只能通过显式 adapter/binding 发生。

## 2. 模块边界

```text
canonical_runtime.models       typed immutable contracts
canonical_runtime.protocols    repository/object-store/facade ports
canonical_runtime.store        SQLite adapter and migrations
canonical_runtime.facade       command validation and transactions
canonical_runtime.feature_flags shadow admission and kill switch
canonical_runtime.schema_export deterministic JSON Schema artifact
```

Domain/application code不得接收 `sqlite3.Connection`、绝对文件路径或 backend-specific SQL。Object identity 使用稳定 ID；large payload identity 使用 content digest + portable object key。

## 3. Authority 与安全边界

- M0 canonical authority：ActorSnapshot、Attempt、EventEnvelope 及 shadow-lane execution metadata。
- Legacy authority：TaskRun 和既有 planning/output consumer。
- DecisionSurface：只可 shadow 写入，不可进入 Writer、Evidence runtime 或正式 Workbench accepted surface。
- `off` 是默认状态；M0 不支持 `canonical_for_lane`。
- canonical command 失败时 fail closed；禁止静默 fallback 成 legacy mutation。
- raw private CoT、credentials、API tokens 不进入 event、SQL 或 object payload。

## 4. 数据与事务

SQLite 首阶段使用 WAL、foreign keys、busy timeout 和显式 transaction。Repository 采用 compare-and-swap、append-only event/version policy 和 transactional outbox。Object payload 先 content-addressed put，SQL 事务随后原子发布 ref；SQL 失败留下的 orphan 不是 committed artifact。

所有 timestamps 必须是 timezone-aware UTC。Schema evolution forward-only；已发布 version 不原地覆盖。

## 5. Replay 与 determinism

Projection replay 只读 events/artifacts，不重新调用模型、网页、API、工具或外部写操作。相同 EventEnvelope 序列和 artifact versions 必须生成相同 projection；未知 state-mutating event schema 必须阻断。

## 6. 未选择方案

- 直接扩展 legacy runtime spine：会继续复制状态模型和 authority。
- M0 直接 PostgreSQL：本机资源与当前 fixture 速度不支持该必要性；M4 前仍有 parity gate。
- 先实现 HTTP/MCP/queue：M0 只需要 service-neutral facade，会扩大非必要 surface。
- 允许 shadow output 被 Writer 消费：违反 MIGRATION_01 和 P36 writer no-source/control boundary。
- 一次实现 Evidence/Numeric/Judgment/Review：超出 first slice owner contract。

## 7. 退出与回滚

任一条件触发 kill switch 并停止 canonical writes：identity split-brain、event sequence 不连续、digest mismatch、shadow leakage、无法解释的 replay drift、legacy latency/material regression。回滚只切回 legacy read/authority；canonical audit rows 保留，不做 destructive reverse migration。

## 8. M0 完成定义

M0 只在以下条件下完成：机器 schema 可生成、SQLite conformance tests 全通过、RuntimeFacade 最小命令可回放、feature flag 默认关闭、rollback drill 通过、Project OS 记录为 `L1_contract_pass` 或相应有限状态。不得据此声称 Agentic Research、DecisionSurface compiler 或产品 runtime 已完成。
