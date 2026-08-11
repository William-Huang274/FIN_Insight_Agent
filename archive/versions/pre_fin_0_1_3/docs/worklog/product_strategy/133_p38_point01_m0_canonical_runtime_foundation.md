# P38 Point 01 M0 Canonical Runtime Foundation

日期：2026-07-12

状态：`m0_foundation_fixture_proven / legacy_authoritative / no_runtime_cutover`

## 1. 目标

在 SCHEMA_01/DB_01/API_01/MIGRATION_01 冻结后，完成 Point 01 的实施准入和最小 canonical control kernel，不扩展旧 runtime spine，不进入 M1/M2 compiler 或下游研究域。

## 2. 实施

- 准入：ADR、test manifest、default-off shadow flag、rollback runbook/result、implementation admission。
- 合同：15 个 canonical Pydantic objects、Command/Result envelopes、deterministic JSON Schema bundle。
- 存储：SQLite WAL、显式事务、append-only version/event tables、outbox、idempotency、CAS、portable content-addressed object store。
- Facade：create Case/legacy binding、create WorkUnit、start Attempt、atomic shadow DecisionSurface bundle commit、event listing/replay、kill switch。
- 安全边界：shadow consumer allowlist；Writer/Evidence 等 forbidden consumers；canonical failure 不回落为 legacy mutation。

## 3. 根因修复

首轮测试发现同一事务内批量预构造多个 events 会重复读取相同 sequence。实现改为逐 event 分配 sequence 并立即 append；保留 `(task_run_id, sequence_no)` 唯一约束。

## 4. 验证

```text
python -m pytest -q -m fast_contract tests/contract
14 passed

python -m pytest -q -m fast_contract tests/contract tests/test_runtime_bridge_contracts.py tests/test_r53_r60_runtime_task_spine.py
31 passed
```

同时通过 `compileall`、JSON parsing 和 focused `git diff --check`。未调用模型、web、paid LLM 或 full-chain。

## 5. 未完成

- API_01 剩余 bind/fail/cancel/comparison/review/cutover commands；
- DecisionSurface compiler model adapter 与 pack compilation；
- PostgreSQL parity；
- Evidence/Numeric/Judgment/Writer/Review/Monitoring；
- M1-M4 authority migration/cutover。
