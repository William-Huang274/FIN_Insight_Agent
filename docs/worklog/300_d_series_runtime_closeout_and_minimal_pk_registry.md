# D-Series Runtime Closeout And Minimal P/K Registry

日期：2026-06-13

## 问题

用户确认先按顺序把 D 系列做到闭环验收，再讨论全量 P/K 和 agent graph / skill 升级。执行顺序为：

- D12.1d + D6.1 / D9.1 / D10.1 先推进。
- 同时做 07 文档里的 P0 / K1 / K2 / K3 最小版本。
- 然后补 D7.1 / D8.1。
- D3.1 / D4.1 / D5.1 作为底座并行补，但 SQL / DB 强化后续仍要记账。

## 决策

本轮不展开全量 KG、全量行业 playbook、Product / Technology sub-agent 或 agent graph / skill 改造。先关闭 D 系列 runtime governance loop：

- Memo 前只允许 D6 resolved 且 D9 gate 未阻塞的事实进入 ClaimCards。
- D10 derived metrics 只有公式、输入 lineage 和 gate 状态满足要求时才能进入 Memo。
- D12.1d 提供 D3-D8 / D10 / D11 的 DB-default research context reader，让 Research Lead / shared context 能读取跨 run 治理上下文。
- Minimal P0/K1/K2/K3 只作为 D7/D8 的机器可读 registry，不宣称完成 full P/K。
- D3/D4/D5 本轮补 closeout foundation：entity 扩展字段、provenance checksum/materialized artifact refs、as-of time-basis mismatch gate；更重的 SQL resolver、object-store provenance、真实 macro/market vintage history 继续作为 DB hardening follow-up。

## 完成内容

- 新增 `src/sec_agent/d_series_fact_selection.py`，实现 pre-Memo fact selection：
  - approved / rejected reconciliation facts。
  - approved / rejected derived metrics。
  - bounded gap links。
  - blocked evidence / candidate / gate refs。
  - 将被阻塞的 supported claims 移入 unsupported claims。
- `langgraph_orchestrator` 接入：
  - D12.1d `read_d_series_research_context`。
  - aggregate_judgment_plan 阶段先生成 D4-D10 治理层，再做 pre-Memo selection。
  - artifact refs 写入后刷新 raw provenance，避免最终 provenance 缺少 run artifact lineage。
  - summary / checkpoint / artifacts 增加 D-series reader 和 pre-Memo selection 统计。
- 新增 `configs/kg_minimal_p0_k1_k2_k3_v0_1.yaml` 和 `src/sec_agent/kg_minimal_registry.py`：
  - P0 Company / Segment / ProductFamily / ProductKPI 最小图。
  - K1 行业 KPI 字典。
  - K2 product spec ontology / channel offer boundary。
  - K3 public buyer observer / source-family boundary。
- D7/D8 接入 minimal registry：
  - metric ontology 从 K1 加载行业 KPI overrides 和 commercial gap metrics。
  - source router 使用 K3 source boundaries，阻止 context-only / public proxy 支撑 exact company fact。
- D3/D4/D5 foundation repair：
  - entity master 支持 brands、subsidiaries、product_aliases、ADR/common share、domain、country、source priority。
  - provenance store 对 local source / artifact refs 物化 sha256 checksum，并统计 parser lineage / license / robots policy。
  - as-of / vintage layer 的 market snapshot fiscal-period 混用会在 D9 period_alignment_gate 标记 `warn/time_basis_mismatch`。

## 结果与证据

- `python -m py_compile` 覆盖本轮改动的 D-series / KG / graph / contract 模块：通过。
- D3/D4/D5 targeted regression：`11 passed`。
- D-series focused regression：`32 passed`。
- Graph contract regression：`92 passed`。
- D-series + multi-agent merged regression：`195 passed`。
- Full pytest：`863 passed`。
- `git diff --check`：通过。

## 边界

已关闭的是 D-series runtime closeout，不是 full P/K 或 full agent graph / skill upgrade。

仍需后续继续的部分：

- 全量 P/K：KG Matrix Registry、ProductModel / ProductSpec / ProductGenerationEdge / CompetitiveComparableEdge / ChannelOffer / FieldInquiryNote、capital / ownership / macro exposure 等。
- DB hardening：Entity Master 真 SQL-backed resolver、D4 object-store provenance / license / robots registry / before-after diff、D5 真实 macro / industry vintage store 与 market snapshot as-of table、D11 memory 的 vector / graph-backed retrieval。
- Agent graph / skill：反思插入点、联网工具权限、Research Lead planning skill、专家 sub-agent skill、共享上下文边界、async/sync 协作策略仍待下一阶段讨论和实现。

## 回滚与安全

- 本轮未写 `.env`、未提交 raw data、未提交 Milvus 向量库或运行输出。
- Minimal K3 明确禁止伪装身份、认证绕过、虚假下单或提交资质表单；public buyer observer 只允许读取公开产品页、公开价格/库存/订货页、公开文档和公开经销商页面。
