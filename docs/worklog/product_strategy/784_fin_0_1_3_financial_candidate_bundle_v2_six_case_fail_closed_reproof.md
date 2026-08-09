# 784 — FIN 0.1.3 FinancialCandidateBundleV2 六案 fail-closed 复证

日期：2026-08-09

归属：FIN 0.1.3 / S1

状态：`bundle_v2_engineering_pass_fail_closed_current_sources_pending`

## 1. 为什么这是 successor 而不是改写旧结果

三个留出案例已经证明 v1 candidate 不能把 child object 当成独立事实，尤其 ASML 出现 EUR 父表、`usd_millions` child 和错误 remuneration parent。旧 DELL／MU／NVDA／ORCL／ASML／ANET 结果均作为不可变输入保留；本项只新增 v2 投影层，没有改写 v1 金融内核、旧 executor、candidate、capture 或业务复核。

v2 的最小检索单位为：

`source authority + child object + parent text + table marker/header + row/column path + three periods + currency/unit provenance + relationship direction`

任何字段不足都只能产生 typed gap，不能靠 case 默认值或渲染层修成“看起来正确”的数值。

## 2. 六案真实投影结果

| 案例 | v1 candidates | v2 bundle | typed rejection | 主要拒绝原因 | 当前期状态 |
| --- | ---: | ---: | ---: | --- | --- |
| DELL | 265 | 265 | 0 | 无 | observed |
| MU | 256 | 256 | 0 | 无 | observed |
| NVDA | 262 | 262 | 0 | 无 | observed |
| ORCL | 130 | 113 | 17 | parent source missing 14；table path missing 3 | `source_absent_gap` |
| ASML | 112 | 104 | 8 | currency conflict 3；invalid numeric cell 5；unit authority missing 2；table path missing 1 | `source_absent_gap` |
| ANET | 154 | 139 | 15 | parent source missing 11；numeric/unit/table context | `source_absent_gap` |

总计 1,179 条候选全部被投影或拒绝，`unsafe_numeric_bundle_admissions=0`。结果没有把 rejection 计成“召回失败”，而是区分：

- `source_absent_gap`：冻结截至期没有合格官方资料；
- `object_context_gap`：源存在，但 parent／table／currency／numeric cell 不足以安全使用；
- `retrieval_quality_gap`：对象存在，但当前检索结果不够回答业务问题。

## 3. ASML 的具体保护效果

对真实 ASML 20-F，v2 没有把 child 的 `usd_millions` 静默改成 EUR，也没有让模型或 renderer 猜币种。父表中 `(€, in millions)` 与 child unit 冲突时，candidate 被 `currency_unit_conflict` 拒绝；把 “Earnings per share (2024: €19.25)” 错解析为数值 `-2024` 的 child 被 `numeric_cell_parse_invalid` 拒绝。

正向 fixture 同时证明：当父表、row／column、原始数值和 child 的 `eur_millions` 一致时，可以形成带 table ID 和稳定 cell key 的 bundle。因此这不是“一律禁用非美公司”，而是要求来源语义一致后才放行。

## 4. 这一步解决了什么、没解决什么

已解决：

- 旧三案不因 v2 增加 ticker 特判，真实 candidate 全部兼容；
- child／parent／table path 成为一个原子投影；
- currency／unit 冲突、坏 numeric cell 和错 lineage 可在 Candidate 层 fail closed；
- 失败输出明确落到 source、object context 或 retrieval quality，而不是笼统“没搜到”；
- v1 历史结果、核心 SHA 和 Evidence 边界保持不变。

未解决：

- ORCL FY2026 Q4／全年、ASML Q2 2026、ANET Q2 2026 官方资料尚未入本地 inventory；
- 被拒绝的历史 ASML child 尚未重解析为正确对象；
- alias／多语言／ADR-local ticker／PDF-only 仍需结合新 current source 复证；
- sparse／dense、BGE、Milvus、rerank、Evidence、DeepSeek 和报告质量均未执行。

## 5. 下一步

保持 S1／held-out generalization，不跳版本：

1. 对 ORCL、ASML、ANET 做 exact official-current source discovery 与 capture；
2. capture-first 后用 v2 parser/object path 解析，不能直接信任旧 child unit；
3. 同一批六案重跑 bundle gate 和 ASML mutation；
4. 只有对象语义与迁移通过后，才冻结 successor sparse／dense object manifest。

官方 current source ingestion 是本地 source inventory 的补齐，不等于稍后的 broad-web residual-gap supplement。后者仍只处理本地 Evidence Pack 形成后的真实剩余缺口。

## 6. 机器证据

- policy=`configs/runtime/fin_ia_0_1_3_s1_financial_candidate_bundle_v2_policy_v1_0.json`
- result=`configs/releases/fin_ia_0_1_3_s1_financial_candidate_bundle_v2_result_v1_0.json`
- result digest=`b0600233509f9a79a67b079e7eb8b2522ffbf5e775300129811385ad6748a24a`
- focused and adjacent tests=`22 passed`
- network／provider／model／embedding／rerank／Evidence=`0/0/0/0/0/0`

本项是 engineering pass，不是 held-out product pass 或 index admission。
