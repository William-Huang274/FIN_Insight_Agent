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
- 更新 36 源计划、master checklist 和 worklog README。初始 P25 只关闭 blocker-registration infrastructure，不关闭 B05 数据深度缺口；2026-07-01 B05 root-cause closeout 后，P25 现在记录 all required packs ready，并允许进入后续 scoped full-chain quality eval 设计。

## 真实构建结果

生成摘要：`data/manifests/r53_r60_p25_b05_pack_depth_summary_v0_1.json`

- `status`: `pass`
- `closeout_level`: `L4_scope_pass_for_broad_full_chain_pack_depth`
- `release_decision`: `P25_b05_pack_depth_ready_broad_full_chain_allowed`
- `pack_count`: `6`
- `ready_pack_count`: `6`
- `blocked_pack_count`: `0`
- `blocked_requirement_count`: `0`
- `gate_fail_count`: `0`
- `b05_status_after_p25`: `closed_by_p25_pack_depth_ready`
- `broad_full_chain_quality_eval_allowed`: `true`

Pack readiness：

| Pack | 状态 | 原因 |
| --- | --- | --- |
| `ai_semis_product_evidence_pack` | ready | AI/Semis `53/53` strict pass，`gap_queue_count=0` |
| `research_to_quant_lab_pack` | ready | S9 有 approved factors / backtests，且无真实交易 |
| `product_evidence_pack_all_universe` | ready | 2026-07-01 根因修复后 CustomerDeployment depth `603/603`；Product Profile/Spec/Relationship ready，Product-KPI exact `160` 只阻断 exact KPI claims，Capital detail `2` 转到 capital/funding pack |
| `secondary_market_capital_feedback_pack` | ready | S8/S8 follow-up 已补 credit/derivatives/valuation public context，603 issuer pack ready；实时/商业市场深度仍是非阻塞生产增强项 |
| `deliverable_studio_pack` | ready | S7 已改为 reader-facing Workpaper draft，新增 deterministic customer-readable editorial gates；仍不等于真人最终发布批准/RBAC/SLA |
| `retrieval_data_refresh_pack` | ready | P14 已新增 current accepted 603-company universe manifest-backed refresh evidence；仍不声明全网爬虫、实时刷新或生产 p95/p99 SLA |

2026-06-30 P26 update：新增 `r53_r60_product_evidence_depth_p26_gate.py` 和 P26 artifacts，P25 现在优先读取 `r53_r60_p26_product_evidence_all_universe_depth_summary_v0_1.json`。旧的五维 depth parity 只保留为 P26 缺失时的诊断路径，不再作为 ProductEvidencePack 主判定。

2026-07-01 root-cause update 1：P26 暴露的 CustomerDeployment `72` 家 blocker 已通过 non-US operating footprint route、filing operating-footprint parser、verified official customer/deployment seeds、counterparty/dedupe repair 关闭。

2026-07-01 root-cause update 2：继续关闭 B05 的三项非产品 pack blocker：

- `secondary_market_capital_feedback_pack`：S8 已补齐 credit funding、derivatives market signal 和 valuation price-in 三类 public context，603 issuer pack ready。
- `deliverable_studio_pack`：S7 不再渲染内部字段/ClaimCard 转储，Markdown/DOCX/XLSX 改为 reader-facing workpaper draft + evidence/gap appendix，并新增 `customer_ready_editorial_quality_pass=true`。
- `retrieval_data_refresh_pack`：P14 新增 `current_universe_refresh_evidence_p14`，逐项验证 603 公司公开源矩阵、P26 ProductEvidence、S8 SecondaryMarket、secondary-market public context、Gold Fact Mart、retrieval index registry 和 ProductIntelligenceGraph manifest，`current_universe_refresh_status=current_accepted_public_source_universe_ready`。

最新 P25 / P21：

- P25 `ready_pack_count=6`、`blocked_pack_count=0`、`broad_full_chain_quality_eval_allowed=true`。
- P21 `B05-depth-packs-before-broad-full-chain=closed_by_p25_pack_depth_ready`。
- P21 仍有 `B04-prd-product-acceptance-not-met=open_product_acceptance_required`，所以 broad full-chain 仍不能被宣传成 full product pass。

P21 重新生成后仍保持：

- `full_chain_broad_eval_allowed=false`
- `blocker_count_open=1/5`
- B04 仍等待真实产品验收；
- B05 已由 P25 pack-depth closeout 关闭。

## 验证

- `python -m pytest tests/test_r53_r60_deliverable_studio_dashboard.py tests/test_r53_r60_data_ingestion_retrieval_control_plane.py tests/test_r53_r60_pack_depth_b05_gate.py -q`
  - 结果：`15 passed`
- `python scripts/engineering/build_r53_r60_s7_deliverable_studio_dashboard.py --root .`
  - 结果：`status=pass`，`customer_ready_editorial_quality_pass=true`
- `python scripts/engineering/build_r53_r60_p14_data_ingestion_retrieval_control_plane.py --root .`
  - 结果：`status=pass`，`current_universe_refresh_status=current_accepted_public_source_universe_ready`
- `python scripts/engineering/build_r53_r60_p25_b05_pack_depth_gate.py --root .`
  - 结果：`status=pass`，`blocked_pack_count=0`
- `python scripts/engineering/build_r53_r60_p21_pre_full_chain_blocker_gate.py --root .`
  - 结果：B05 closed，B04 remains open
- `python -m py_compile src\sec_agent\r53_r60_pack_depth_b05_gate.py scripts\engineering\build_r53_r60_p25_b05_pack_depth_gate.py tests\test_r53_r60_pack_depth_b05_gate.py src\sec_agent\r53_r60_pre_full_chain_blocker_gate.py`
  - 结果：通过

## 后续

P25/B05 之后仍不应直接跑 20-50 case broad full-chain quality eval 并宣传产品达标，因为 P21 仍有 B04 open。下一步是先做 B04 的真实 product acceptance closeout，或只跑 scoped integration smoke / targeted full-chain diagnostic，不得把它当作产品级验收。

B05 已按 pack-depth 范围关闭；实时/商业市场深度、真人最终发布批准、生产 SLA、全网 crawler 和 p95/p99 是后续生产增强项，不再作为 B05 blocker，但仍必须在对应 release slice / PRD acceptance 中单独验收。
