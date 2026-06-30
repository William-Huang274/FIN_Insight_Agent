# P25 / B05 Pack Depth Gate

## 背景

用户要求 B05 不能再被“后续深挖”或 broad full-chain case 掩盖。进入 20-50 case 全链路质量评测前，必须先把产品证据、二级市场/资本反馈、量化实验、交付物、检索/数据刷新等 pack 的真实深度状态登记成可审计、可回放、可被 P21 gate 读取的机器合同。

本轮目标不是补齐所有数据，而是修正推进口径：如果 pack-level depth 没达到，它必须阻断 broad full-chain quality claim；只允许 deterministic node tests、pack-level tests 和 integration smoke。

## 完成内容

- 新增 `src/sec_agent/r53_r60_pack_depth_b05_gate.py`，定义 P25 pack-depth gate runtime contract。
- 新增 `scripts/engineering/build_r53_r60_p25_b05_pack_depth_gate.py`，生成 P25 schema、pack assessment rows、requirement rows、gate rows、summary、report，并写入 S1 runtime SQLite mirror。
- 新增 `tests/test_r53_r60_pack_depth_b05_gate.py`，覆盖：
  - P25 会登记 pack-depth blockers，但不会允许 broad full-chain quality eval；
  - SQL rows 能保存 pack / requirement / gate 结果；
  - P21 会读取 P25 summary，并在所有 pack 未 ready 前保持 B05 open；
  - 只有 P25 明确记录 all-pack-ready 时 P21 才能关闭 B05。
- 更新 `src/sec_agent/r53_r60_pre_full_chain_blocker_gate.py`，让 B05 closure 依赖 P25 summary：
  - `b05_status_after_p25=closed_by_p25_pack_depth_ready`
  - `broad_full_chain_quality_eval_allowed=true`
  - `blocked_pack_count=0`
  - `blocked_requirement_count=0`
  - `gate_fail_count=0`
- 更新 36 源计划、master checklist 和 worklog README，明确 P25 只关闭 blocker-registration infrastructure，不关闭 B05 数据深度缺口。

## 真实构建结果

生成摘要：`data/manifests/r53_r60_p25_b05_pack_depth_summary_v0_1.json`

- `status`: `pass_with_pack_depth_blockers_registered`
- `closeout_level`: `L4_scope_pass_for_pack_depth_blocker_registration_only`
- `release_decision`: `P25_b05_pack_depth_blockers_registered_broad_full_chain_blocked`
- `pack_count`: `6`
- `ready_pack_count`: `2`
- `blocked_pack_count`: `4`
- `blocked_requirement_count`: `4`
- `gate_fail_count`: `0`
- `b05_status_after_p25`: `open_pack_level_depth_required`
- `broad_full_chain_quality_eval_allowed`: `false`

Pack readiness：

| Pack | 状态 | 原因 |
| --- | --- | --- |
| `ai_semis_product_evidence_pack` | ready | AI/Semis `53/53` strict pass，`gap_queue_count=0` |
| `research_to_quant_lab_pack` | ready | S9 有 approved factors / backtests，且无真实交易 |
| `product_evidence_pack_all_universe` | blocked | 603 universe 仍有 `203` 家 full-depth gap |
| `secondary_market_capital_feedback_pack` | blocked | `credit_funding`、`derivatives_market_signal`、`valuation_price_in` 仍全量缺 role coverage |
| `deliverable_studio_pack` | blocked | 缺真实 customer-ready editorial acceptance |
| `retrieval_data_refresh_pack` | blocked | P14 是 control plane，不是 full crawler / production refresh |

P21 重新生成后仍保持：

- `full_chain_broad_eval_allowed=false`
- `blocker_count_open=2/5`
- B04 仍等待真实产品验收；
- B05 仍等待 pack-level depth closure。

## 验证

- `python -m pytest tests/test_r53_r60_pack_depth_b05_gate.py tests/test_r53_r60_pre_full_chain_blocker_gate.py tests/test_r53_r60_product_acceptance_b04_gate.py -q`
  - 结果：`12 passed`
- `python -m py_compile src\sec_agent\r53_r60_pack_depth_b05_gate.py scripts\engineering\build_r53_r60_p25_b05_pack_depth_gate.py tests\test_r53_r60_pack_depth_b05_gate.py src\sec_agent\r53_r60_pre_full_chain_blocker_gate.py`
  - 结果：通过

## 后续

P25 之后不应直接跑 20-50 case broad full-chain quality eval。下一步只能针对 open packs 做 root-cause-first 修复：

1. `product_evidence_pack_all_universe`：继续补 Product-KPI exact、CustomerDeployment 和少数 CapitalMarketDetail 的真实 source/parser/adapter 深度。
2. `secondary_market_capital_feedback_pack`：补 `credit_funding`、`derivatives_market_signal`、`valuation_price_in` 的公开源可得边界、商业 gap 和 adapter。
3. `deliverable_studio_pack`：做真实 customer-ready editorial review，而不是只看 deterministic render。
4. `retrieval_data_refresh_pack`：把 P14 control plane 接到真实 crawler/parser/index refresh run，并记录 lineage / qrels / performance。

只有这些 pack blockers 关闭或形成可接受的 typed public/commercial boundary 后，B05 才能关闭。
