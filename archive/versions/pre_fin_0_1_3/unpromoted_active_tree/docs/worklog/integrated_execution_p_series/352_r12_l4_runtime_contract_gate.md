# 352 R12 L4 Runtime Contract Gate

Date: 2026-06-17

## Prompt

Heartbeat automation `16-l4-vertical-lanes` 要求继续推进 16 文档，先实现 L4 runtime contract：

- `WeakSignalLead`
- `WeakSignalExclusionNote`
- `L4PromotionAttempt`
- L4 source classifier
- TTL / dedupe
- PromotionGate
- Memo / Verifier 防提权 eval

本轮只做 Step 0，不做大规模 L4 ingestion，也不把 L4 接入 ClaimCard 主证据链。

## Decision

L4 继续保持 discovery / exclusion / targeted-repair trigger 层，不是新证据层。

实现方式选择独立模块 `src/sec_agent/l4_weak_signal.py`，先把 contract、gate 和 deterministic eval 固化下来。后续 VerticalSourceLaneRegistry 和 V1 lane 接入真实 source 时，只能通过该 contract 产生 L4 lead / exclusion / promotion attempt，不能直接把弱信号写入 ClaimCard。

## Work Completed

- 新增 `src/sec_agent/l4_weak_signal.py`：
  - `WeakSignalLead`
  - `WeakSignalExclusionNote`
  - `L4PromotionAttempt`
  - `classify_l4_source`
  - `make_weak_signal_lead`
  - `dedupe_weak_signal_leads`
  - `is_weak_signal_expired`
  - `weak_signal_to_targeted_repair_plan`
  - `evaluate_l4_promotion_attempt`
  - `validate_l4_not_promoted_to_claim_cards`
  - `validate_memo_l4_usage`
  - `write_l4_runtime_objects` / `load_l4_runtime_objects`
- 新增 `tests/test_l4_weak_signal_contract.py`，覆盖 7 个 deterministic gate：
  1. verified official social route 到 L2，不进入 L4；
  2. commercial tracker / consensus route 到 commercial gap，不允许伪装成 L4 proxy；
  3. unverified forum lead 可 TTL / dedupe / repair plan，但不可 exact authority；
  4. L4 row direct promotion 被拦截；
  5. parser-backed、entity-bound L2 row 可作为 repair 后 promoted row；
  6. L3 exact-authority row 和 entity-unbound row fail-closed；
  7. L4 ClaimCard / Memo core usage 被 validator 拦截。
- 更新 `docs/architecture/agent_graph_vnext/16_l4_weak_signal_and_vertical_source_lane_framework.zh-CN.md`，记录 Step 0 当前实现状态和未做范围。
- 更新 `docs/worklog/00_internal_master_checklist.md`，将 R12 L4 runtime contract 标记为完成。
- 更新 `docs/worklog/README.md`，加入本阶段日志索引。

## Verification

Commands:

```powershell
python -m py_compile src\sec_agent\l4_weak_signal.py
python -m pytest tests\test_l4_weak_signal_contract.py -q
```

Result:

- `py_compile` pass.
- `tests/test_l4_weak_signal_contract.py`: `7 passed`.

## Boundary

本轮没有做：

- 大规模 L4 crawl / ingestion；
- 把 L4 runtime store 接入 Java gateway 或 Workbench trace；
- VerticalSourceLaneRegistry；
- V1 semiconductors / AI infrastructure lane playbook、coverage report 和 representative case eval。

这些仍按 16 文档后续顺序推进。

## Follow-up

下一步应进入 Step 1：

1. 构建 600+ 公司 `vertical_source_lane_registry_v0_1`。
2. 每家公司至少分配 primary lane，重点公司允许 secondary lane。
3. 每个 lane 记录 representative tickers、product taxonomy scope、L1/L2/L3/L4 source requirements、public data ceiling、commercial gaps 和 lane coverage gates。
4. 完成后进入 V1 Semiconductors / AI Infrastructure lane。
