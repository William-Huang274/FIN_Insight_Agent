# 675 — FIN 0.1.3 S2-05 MU raw exact-live 与 S2-06 boundary

日期：2026-08-07

状态：`MU raw complete-quality-fail / evaluator v1.3 / supervision v1.1 / NVDA authority pending`

## 真实运行结果

唯一 MU admission 在 clean/synced commit `ddbaf2cd...c208` 上 exact-once 消费。Lead、六 Specialist、Synthesis、Writer、Verifier 共 `10 calls / 10 captures`，全部 `ok/stop`；input/output/total=`32,372/7,019/39,391`，估算 USD=`0.0313555`，retry/fallback=`0/0`。terminal=`terminal_completed_layered_raw_evaluation`，raw chain 完整、hidden-scoreable，business promotion 始终 false。

## 为什么 runtime 的 10 个 L1 不能直接照单全收

运行时 evaluator v1.1 报 `10 L1 / 2 L2 / 14 L3`。零调用对照发现 `100B/22B/33%/1B` 都来自已批准的 `USD_billion_approx / percent_approx / USD_billion_lower_bound` 数值，只是 evaluator 对 unit 使用精确字符串匹配；条件段中的历史估值证据请求也被当成当前事实。v1.2 用单位族和条件语义修复后只剩 14 个 L3，但这暴露出另一个问题：机器没有检查通用会计/估值不变量。

v1.3 增加三类通用门禁并覆盖 Specialist、Synthesis、Writer：trailing P/E 不能被改写为单季度倍数；combined deposits/commitments 不能被无权改写成现金或可退款预付款；平均 FCF margin 不能直接当边际收入敏感性。最终同一 raw 为 `6 L1 / 2 L2 / 14 L3`。DELL 同步重放仍为 `2/1/23`，未通过新规则洗绿。

## 内容表现

正面：六研究家族完整、MU 公司专属、HBM 产品进展与 DRAM/NAND 量价、现金流、估值和 gap 有连接，Writer 可读，hidden target 的四个主题均有覆盖或部分覆盖。

失败：三类财务语义错误在六个 surface 传播；Verifier 仍零 finding 接受；6/6 Specialist 无 counterevidence；WWC 阈值多为模型自拟；结构升级与传统内存价格周期虽然都出现，但没有成为被明确裁决的核心 conflict。因此不发 formal score，不建立 corrected candidate，也不能用于产品晋升。

## S2-06 处置

MU correction ledger 共 22 rows：3 financial semantic return、3 source-scope return、6 research-content return、6 uncalibrated scenario、2 uncalibrated valuation reference、2 Verifier false-green。raw 不改写，deterministic runtime 不代写研究，hidden Gold 不进入 correction prompt。DELL/MU 均为 `raw_complete_quality_fail`；为保持 benchmark 公平，等 NVDA raw 完成后再做 supervisor model correction。

下一步只允许单独审查 NVDA raw authority；不自动签发、不自动运行。完整 Experiment A、S2-06 三案能力边界、formal score、paired、qualified-human acceptance 和 release 均未完成。

## 提交前复证

focused evaluator、supervision、authority 与 result contract=`27 passed`；S2-05/S2-06 broad contract=`80 passed / 3,201 deselected`。Python compile、JSON/JSONL 解析、result/code/capture/supervision digest、raw secret scan 和 `git diff --check` 另在提交前逐项复核。
