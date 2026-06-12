# D-series Database Closeout Gate

## Prompt

用户明确要求：D4.1、D5.1 这类 SQL / 数据库部分现在可以先不做，但 D 系列全部做完后，需要上数据库的部分必须补齐，不能遗漏。

## Decision

把该要求升级为 D12 收口 gate，而不是只保留在聊天上下文：

- D1-D11 可以先采用 per-run JSON / artifact-backed runtime projection 快速落地。
- D 系列收口前必须逐项判断哪些层需要 SQL / DB-backed store。
- 需要数据库化的层必须补 schema、migration/backfill、artifact-to-database parity tests。
- 不需要数据库化的层必须写明理由，不能默认跳过。

## Work Completed

- 更新 `docs/worklog/00_internal_master_checklist.md`：
  - 新增 `D12`：D-series closeout 前统一补齐 D1-D11 中需要 SQL / DB 化的 stores、migration、backfill、schema migrations 和 parity tests。
- 更新 `docs/architecture/agent_graph_vnext/08_legacy_planning_docs_absorption_and_data_governance_plan.zh-CN.md`：
  - 新增 `D12 D-series Database Closeout`。
  - 明确回补范围包括 D1.1、D3.1、D4.1、D5.1、D9 gate history、D11 research memory。
  - 把 D12 加入优先级序列，放在 D11 后、K2-K8 前。

## Result And Evidence

本轮是 docs / roadmap governance 更新，只运行格式检查：

```text
git diff --check
```

结果：pass。

## Boundary And Follow-up

- 本轮没有实现 SQL / DB-backed stores。
- 后续 D6/D7 仍可继续按 artifact-backed v0.1 推进，但 D 系列关闭前必须执行 D12。
