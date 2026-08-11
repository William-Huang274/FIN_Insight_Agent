# 679 — FIN 0.1.3 S2-05 NVDA R2 与三案例 raw closeout

日期：2026-08-07

状态：`S2-05 three-case raw complete / all quality fail / deterministic boundaries complete / unified supervisor decision pending`

## R2 真实结果

唯一 R2 admission 在 clean/synced `a5f0adf9...5add` 上 exact-once 消费。DeepSeek Pro 完成 Lead＋6 Specialist＋Synthesis＋Writer＋Verifier=`10 calls/10 captures`，全部 `ok/stop`；tokens=`31,947/6,649/38,596`、USD=`0.0304715`、retry/fallback=0。terminal=`completed_layered_raw_evaluation / case_complete / raw_candidate_with_material_findings`。R1 的 `5359B→5.36T` 项目误杀未复发，RC-P36-144 的 numeric-scale 修复因此 live-proven。

## 零调用 evaluator v1.4

execution-time v1.3=`5 L1/2 L2/27 L3`。复核发现 cash-flow/P-E 只是分别出现在条件清单中，原共现规则误报 2 条 L1 与 1 条派生 L2；同时 Writer 把 `NVDA_G01–G04` 放进 `evidence_ids`，旧 evaluator 未检查 citation role 和完整 Evidence 覆盖。

v1.4 一次性补齐三案例通用 ID-role/coverage audit，并把现金流→估值语义门改为需要明确桥接措辞。三份 immutable raw 统一重放：

- DELL=`3/1/23`，新增真实 Writer pack coverage L1；
- MU=`8/2/14`，新增真实 Specialist/Writer coverage L1；
- NVDA=`4/1/27`，最终为 3 条 numeric-role、1 条 Writer citation-role、1 条 Verifier false-green、6 条空 counterevidence、21 条未校准 threshold。

raw mutations、model/provider/network calls=`0/0/0/0`。三案例 supervision boundary v1.4 分别物化为 `27/24/32` correction rows，但 supervisor model correction 和 corrected candidate 均为 0。

最终验证：focused=`39 passed`，S2-05/S2-06 broad=`98 passed / 3,201 deselected`，compileall 与 release JSON/Project OS JSONL parse 通过，R2 raw credential value hits=0，shared admission ledger 中该 run 精确 1 行。

## 阶段处置

- `013-S2-05` 三案例 raw campaign 已完成；
- DELL/MU/NVDA 均为 `complete_quality_fail`，不能用结构完整替代研究质量；
- `013-S2-06` 的 deterministic correction boundary 已完成，但 supervisor recoverability 未证明；
- formal hidden score、business promotion、release 均为 false；
- 不做 NVDA R3，也不逐案重新修 raw；下一项是单独裁决一次统一三案例 supervisor 实验。

完整机器结果见 `configs/releases/fin_ia_0_1_3_s2_05_nvda_raw_replacement_r2_and_three_case_boundary_result_v1_0.json`，运行记录见 `reports/model_runs/20260807_fin_0_1_3_s2_05_nvda_raw_replacement_r2_exact_live.md`。
