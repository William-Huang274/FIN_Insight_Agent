# 220 - Fin Agent S5 Shared Context 与 Slot-Aware Specialist 压缩

日期：2026-06-01

## 1. 问题

上一版 S5 Specialist layer 已通过，但成本偏高：`2` 个 case / `7` 个 Specialist 合计 `65,251` tokens，其中 input tokens `56,331`。根因不是单个模型输出失控，而是每个 Specialist 都重复携带通用 scope / coverage / source-boundary，上游 data view 又按较宽 row cap 直接进 prompt，导致模型在不必要时也要读大量候选 rows。

本轮目标：

1. 增加 Specialist shared context，公共上下文只构造一次，并在 runtime ledger 中可观测。
2. 在不降低 S5 route / real-evidence quality 的前提下做 prompt-level 压缩。
3. 优先通过 role-specific skill 和 prompt 指导模型按 `required_claim_slots` / `counterclaim_slots` 精读证据，而不是简单拉大候选池。

## 2. 实现

### Shared Specialist Context

- `src/sec_agent/specialist_llm.py`
  - 新增 `build_shared_specialist_context()`，输出 `sec_agent_shared_specialist_context_v0.1`。
  - 内容包括 user query、execution mode、focus/search scope tickers、coverage sufficiency、source boundaries、relationship context 和 prompt policy。
  - 每个 shared context 写入 `context_digest`，route summary 记录 `shared_context_digest`，方便判断同一 case 的 Specialist 是否共享同一上下文。
  - `route_specialists_from_env()` 每个 case 只构造一次 shared context，再传给各 Specialist request。

### Slot-Aware Row Selection

- `build_specialist_request_from_state()` 现在把 `assigned_task_card`、`required_claim_slots`、`counterclaim_slots` 传入 prompt row selector。
- 新增 row ranking：
  - 根据 ticker、metric、source_family、relationship_type、summary 与 claim slots / task card 的匹配度排序。
  - Fundamental 优先 primary SEC / company-authored rows。
  - Market 优先 market snapshot rows。
  - Industry 保留 relationship_graph rows，并继续保证 relationship rows 不被 industry rows 挤掉。
  - Risk 继续做 source-family balance，但按风险/缺口/冲突词和 slots 排序。
- Prompt-visible row budget 收紧：
  - deep primary：`16` rows，Industry 为 `18` rows。
  - deep supporting：`12` rows。
  - deep conditional：`8` rows。
  - standard primary：`12` rows。
  - standard supporting：`8` rows。
  - deep relationship summary：`8` rows。
- Summary char budget 收紧到 v0.2 compact：SEC / market / industry / relationship rows 均按 source family 分层截断。

### Skill / Prompt 更新

- 四个 Specialist skill 增加 shared context 与 Evidence Selection Discipline：
  - 先读 `shared_context` 的 scope / coverage / source boundary。
  - 先从 required/counterclaim slots 找证据。
  - slot 已有足够直接支持时停止扩展，除非新 row 改变投资含义或揭示 caveat。
  - `known_evidence_refs` 不再鼓励模型扫描完整 refs 列表，改为只引用当前可见 bounded rows / relationship summary 的 refs。
- `_build_messages()` 不再把完整 refs 列表、coverage summary、source boundaries 在每个 Specialist prompt 里重复展开；validator 仍保留完整 refs 集合做 fail-closed 检查。
- repair prompt 也改用 shared context + visible refs，避免 repair 阶段再次重复大 payload。

## 3. 真实运行结果

Run ID：`20260601_fin_agent_s5_shared_context_slot_aware_compression_deepseek_v0_1`

| Metric | Previous S5 | This run | Change |
| --- | ---: | ---: | ---: |
| Gate status | pass | pass | unchanged |
| Specialist cases | `2/2` | `2/2` | unchanged |
| Specialist routes | `7` | `7` | unchanged |
| Real-evidence quality | `2/2` | `2/2` | unchanged |
| Repair attempts | `0` | `0` | unchanged |
| Input tokens | `56,331` | `44,778` | `-20.5%` |
| Output tokens | `8,920` | `8,183` | `-8.3%` |
| Total tokens | `65,251` | `52,961` | `-18.8%` |

Case 级结果：

| Case | Previous tokens | This run tokens | Prompt-visible evidence behavior |
| --- | ---: | ---: | --- |
| `ma_nvda_amd_market_standard` | `20,000` | `17,836` | Fundamental prompt rows `12`，Market `2`，Risk `8`；route / refs / source-family gate 全部通过 |
| `ma_ai_capex_supply_chain_deep` | `45,251` | `35,125` | Fundamental prompt rows `16`，Industry `18` + relationship summary `8`，Market `5`，Risk `16`；Industry relationship pack gate 继续通过 |

关键判断：

- 压缩不是砍掉上游 data view。S5 artifact 仍保留 data-view row counts：标准 case Fundamental `24` / Risk `16`；deep case Fundamental `32` / Industry `32` / Risk `32`。本轮压缩的是进入 LLM prompt 的 role-specific visible rows。
- Industry Specialist 仍看到并引用 `technology_ai_infrastructure_depth` relationship refs，说明 relationship evidence gate 没被压坏。
- `0` repair 表明 prompt 更短后没有引发结构化输出不稳定。

## 4. 验证

单测与编译：

```text
python -m pytest tests/test_multi_agent_specialist_llm.py -q
result: 30 passed

python -m pytest tests/test_multi_agent_universe_relationship.py tests/test_multi_agent_real_llm_chain_eval.py -q
result: 16 passed

python -m compileall src/sec_agent/specialist_llm.py scripts/eval_multi_agent_specialist_layer_gate.py
result: pass
```

真实门控：

```text
python scripts\eval_multi_agent_specialist_layer_gate.py ... --run-id 20260601_fin_agent_s5_shared_context_slot_aware_compression_deepseek_v0_1 --max-tokens 2000 --max-repair-attempts 1 --strict
result: pass
```

输出 artifact：

- `eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260601_fin_agent_s5_shared_context_slot_aware_compression_deepseek_v0_1/specialist_layer_diagnostic.json`
- `reports/model_runs/20260601_fin_agent_s5_shared_context_slot_aware_compression_deepseek_v0_1.md`

## 5. 后续

1. 继续保留 S5 的 route success 与 real-evidence quality 分离门控。
2. 下一轮应把 shared context 思路推进到 Aggregator / Memo Writer：上游 Specialist outputs 已经是 ClaimCards，Memo Writer 不应重新读取大 payload。
3. 若继续压 token，应优先优化 task-card 和 claim-slot 质量，让 selector 更准；不要先盲目降低 row cap。
4. 对 Memo Writer 层增加“每 token 产出 memo claim / thesis slot”的质量效率指标，避免只看总 token。

## 6. 风险与安全

- DeepSeek key 只从环境变量读取，没有写入代码、文档或 artifacts。
- 当前 S5 只证明 Specialist layer 在压缩后仍合规，不代表最终 memo 已达到成熟投研报告质量。
- `eval/sec_cases/outputs/` 为生成 artifact，默认不纳入提交。
