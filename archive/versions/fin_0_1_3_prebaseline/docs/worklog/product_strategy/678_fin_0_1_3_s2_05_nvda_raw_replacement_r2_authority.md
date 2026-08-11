# 678 — FIN 0.1.3 S2-05 NVDA raw replacement R2 authority

日期：2026-08-07

状态：`closed / authority committed / admission exact-once consumed / superseded by worklog 679`

> 后续：R2 已完成完整 raw chain，结果、evaluator v1.4 和三案例处置见 `679_fin_0_1_3_s2_05_nvda_r2_and_three_case_raw_closeout.md`。下文保留签发前权限证据。

## 问题与决定

NVDA R1 只完成 Lead，因项目 numeric compiler 未识别 `5359 USD_billion → $5.36T` 的合法单位换算而 terminal。该失败保持 immutable；零调用修复和 immutable Lead replay 已在 worklog 677 完成。用户随后明确批准单独审查、签发并执行一次 replacement。

本 authority 仍归 `013-S2-05`，不创建新产品版本，也不把 R1 追认为成功。唯一允许的差异是本地 typed numeric-scale compiler；NVDA model-visible input、Prompt、DeepSeek Pro 参数、runtime policy、调用上限和 evaluator 隔离均不变。

## 权限与公平性

- 新 authority root=`.codex_runtime/fin013_s2_05/authorities/NVDA_RAW_REPLACEMENT_R2`；R1 admission/root 禁止复用；
- 一份 admission、一次 execution、最多 12 Provider calls、0 retry/fallback；
- NVDA 仅见冻结的 `13 Evidence / 3 Numeric / 4 gaps`，case digest=`45422727...81c5`；
- DELL/MU raw、correction、supervisor prompt 与 hidden Gold 均不可见；
- S2-05 business promotion、supervisor correction、automatic R3 均为 false；
- 新 L1/transport/parse/capacity/identity failure 首错停止，不自动补跑。

## 零调用验证

- focused authority/runtime/result/supervision=`34 passed`；
- S2-05/S2-06 broad=`93 passed / 3,201 deselected`；
- authority digest=`d353cc3f...b64b`；
- model/provider/network/admission=`0/0/0/0`。

下一步先提交并推送本 authority slice；随后重新执行 clean/synced、Project OS、production 和 credential-presence preflight。全部通过才可签发并 exact-once 消费 R2。
