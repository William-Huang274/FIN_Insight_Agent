# P26 / ProductEvidence All-Universe Depth Split Gate

## 背景

B05 的 `product_evidence_pack_all_universe` 不能继续用五维 depth parity 粗判。旧口径把 Product-KPI exact、CustomerDeployment、CapitalMarketDetail 都混成一个 `blocked_full_universe_depth_gap`，容易让后续误以为“没有 SKU 收入/出货量，所以产品层整体失败”。这不符合当前产品图谱设计：Product-KPI exact 只是产品层证据的一类，产品画像、规格/架构、客户部署、渠道/供应链和产品关系图谱应有独立 authority 和独立边界。

本轮目标不是补假数据，也不是关闭 B05，而是把 ProductEvidencePack 的 blocker 拆到可执行粒度，并让 P25 优先消费 P26 summary。Supersession：2026-07-01 后续 B05 closeout 已把 S8/S7/P14 的剩余 pack blocker 修完，当前 B05 已由 P25 关闭；本文保留 P26 product-pack 修复记录。

## 完成内容

- 新增 `src/sec_agent/r53_r60_product_evidence_depth_p26_gate.py`：
  - 定义 `product_profile_spec_graph`
  - 定义 `product_relationship_graph`
  - 定义 `product_kpi_exact_boundary`
  - 定义 `customer_deployment_signal`
  - 定义 `capital_market_detail_cross_pack_dependency`
- 新增 `scripts/engineering/build_r53_r60_p26_product_evidence_all_universe_depth_gate.py`，生成 P26 schema、layer rows、gap rows、gate rows、summary、report，并写入 S1 runtime SQLite mirror。
- 新增 `tests/test_r53_r60_product_evidence_depth_p26_gate.py`，覆盖：
  - Product-KPI exact 缺口只阻断 exact KPI claims，不阻断产品画像/规格/关系推理；
  - CustomerDeployment 缺口仍阻断 ProductEvidence broad quality；
  - P25 会消费 P26 summary，而不是回到旧五维粗门控；
  - P26 artifacts 能被真实写出。
- 更新 `src/sec_agent/r53_r60_pack_depth_b05_gate.py`：
  - `load_p25_inputs()` 增加 P26 summary；
  - `product_evidence_pack_all_universe` 优先按 P26 的 `broad_full_chain_product_pack_ready`、`product_pack_readiness_status`、`known_gaps` 和 `blocking_gap_ids` 判断；
  - P26 缺失时才保留旧 `second_third_layer_depth_parity_summary` 诊断路径。
- 重建 P26、P25、P21，使 B05 的 product pack blocker 不再用粗 `blocked_full_universe_depth_gap` 表达，而改为可执行 pack-level blockers。初始结果暴露 `blocked_customer_deployment_signal_gap`；2026-07-01 根因修复后 CustomerDeployment 已关闭。后续 B05 closeout 又关闭了 S8/S7/P14 三个非产品 pack blocker，当前 B05 已 closed。
- 更新 36 源计划、master checklist 和 worklog README。

## 真实构建结果

P26 summary：`data/manifests/r53_r60_p26_product_evidence_all_universe_depth_summary_v0_1.json`

| Field | Value |
| --- | --- |
| `status` | `pass` |
| `closeout_level` | `L4_scope_pass_for_product_evidence_pack_depth_classification` |
| `release_decision` | `P26_product_evidence_pack_ready_for_broad_full_chain` |
| `broad_full_chain_product_pack_ready` | `true` |
| `blocking_gap_ids` | `[]` |
| `gate_fail_count` | `0` |
| `gate_blocked_count` | `0` |

Layer readiness：

| Layer | Status | 意义 |
| --- | --- | --- |
| `product_profile_spec_graph` | `ready` | 603 公司产品画像、规格/架构、PIG 基础可用 |
| `product_relationship_graph` | `ready` | 产品竞争、替代、上下游、部署、read-through 关系图谱可用 |
| `product_kpi_exact_boundary` | `ready_with_typed_exact_kpi_gaps` | Product-KPI exact `160` 家缺口已 typed，只限制 exact KPI claims |
| `customer_deployment_signal` | `ready` | 2026-07-01 根因修复后 CustomerDeployment depth `603/603` |
| `capital_market_detail_cross_pack_dependency` | `out_of_scope_for_product_pack` | CapitalMarketDetail `2` 家残余缺口归 capital/funding pack |

P25 重新生成后：

- `product_evidence_pack_all_universe`: `ready`
- `blocked_pack_count`: `0`
- `b05_status_after_p25`: `closed_by_p25_pack_depth_ready`
- `broad_full_chain_quality_eval_allowed`: `true`

P21 重新生成后的当前状态：

- `full_chain_broad_eval_allowed=false`
- `blocker_count_open=1/5`
- B04 等真实产品验收；
- B05 已由 P25 pack-depth closeout 关闭。

## 验证

- `python -m pytest tests/test_r53_r60_product_evidence_depth_p26_gate.py tests/test_r53_r60_pack_depth_b05_gate.py -q`
  - 结果：`9 passed`
- `python -m py_compile src\sec_agent\r53_r60_product_evidence_depth_p26_gate.py src\sec_agent\r53_r60_pack_depth_b05_gate.py scripts\engineering\build_r53_r60_p26_product_evidence_all_universe_depth_gate.py scripts\engineering\build_r53_r60_p25_b05_pack_depth_gate.py`
  - 结果：通过

## 当前边界

P26 不是 ProductEvidencePack 的最终数据补齐，它只是把 blocker 归因修到可执行粒度：

1. Product Profile / Spec / Relationship 已可用于产品能力、竞争、架构、供应链和 bounded thesis-driver。
2. Product-KPI exact 继续严格，缺 value/unit/period/product/citation 时不能写精确 revenue、shipment、ASP、market share、sell-through、backlog。
3. CustomerDeployment 不再是 ProductEvidence broad-quality blocker。2026-07-01 根因修复通过 non-US operating footprint routing、filing operating-footprint parser、official customer/deployment seed 和 counterparty/dedupe repair 将该层关闭到 `603/603`。
4. CapitalMarketDetail 残余 2 家不应继续阻断 ProductEvidencePack，应进入 `secondary_market_capital_feedback_pack` / capital funding pack repair。

## 后续

下一步不再是修 B05；B05 已关闭。当前应先做 B04 real product acceptance closeout，或只做 scoped full-chain diagnostic，不能把 broad full-chain 输出宣传为 full product pass。
