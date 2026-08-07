# 677 — FIN 0.1.3 S2-05 NVDA raw R1 terminal 与 numeric-scale 修复

日期：2026-08-07

状态：`R1 immutable terminal failed / project false positive repaired zero-call / replacement authority pending`

## 真实运行

唯一 NVDA admission 在 clean/synced `32b03a8d...3b57` 上 exact-once 消费。DeepSeek Pro 的 Lead 调用=`ok/stop`，tokens=`3,603/1,179/4,782`，USD=`0.0041661`，latency=`20,551 ms`；retry/fallback=0。runtime 随后以 `experiment_a_unbound_numeric_surface` 在 Lead 终止，calls/captures=`1/1`，后续 Specialist、Synthesis、Writer、Verifier 均未执行，business promotion=0。

首次命令把已有 `runs` 父目录传给要求 exclusive-create 的 `--runtime-root`，在 root creation 和 ledger reserve 前失败；核验 admission ledger row=None、run-specific root absent、Provider calls=0，因此它不是受治理 execution，也没有消耗 admission。随后只修正为全新的 run-specific root，才发生上述唯一正式运行。

## 根因

Lead 在问题中写 `$5.36T`。冻结 NVDA_E13 的 typed authority 是 `market_cap=5359 / USD_billion`，statement 也写约 `5.359 万亿美元`。模型没有造数，只做了合法的 billion→trillion 换算与两位小数舍入。

本地 `allowed_numeric_surfaces` 只生成 `5359B`，没有生成 `5.359T/5.36T/5.4T`，因此是项目门禁误杀。零调用修复只扩展等价单位表面，不放宽未知数字；immutable Lead 重新执行 `_validate_lead` 已 pass。execution-time evaluator SHA=`7d0d0d5b...b862` 保留在 authority，repaired SHA=`0d3361d8...dc80`，R1 terminal/raw 均不改写。

## 验证与处置

- focused evaluator/authority/result/supervision=`33 passed`；
- S2-05/S2-06 broad=`88 passed / 3,201 deselected`；
- raw capture/terminal SHA 与 exact-once receipt 已记录，secret-pattern scan=0；
- raw chain complete=false，hidden/formal score=false；
- DELL/MU=`raw_complete_quality_fail`，NVDA=`incomplete_project_gate_false_positive`；
- supervisor、corrected candidate、automatic replacement、business promotion 均未执行。

下一步先提交推送本零调用修复与失败证据。若仍要完成三案 raw campaign，必须另行审查一次 NVDA replacement authority；不得复用已消费 admission，也不得把 DELL/MU correction 或 hidden Gold 注入 replacement。
