# FIN 0.1.1 / 0.1.2 PRD 能力对账与阶段重基线

日期：2026-08-04

## 问题

用户要求确认 FIN 0.1.1 是否实际做过 RAG、Agentic Search 和 Agentic Research，还是这些能力原本属于 FIN 0.2；并要求把冻结的 0.1.1、当前 0.1.2 与 PRD 五个产品平面、13 个功能模块、F01–F15 重新对账，有遗漏时重排 0.1.2 及后续版本的 S0–S5。

## 审计结论

- RAG、Agentic Search、Agentic Research 原本属于 FIN 0.1 bounded scope，不是统一留给 FIN 0.2；FIN 0.2 保持 Earnings Review Alpha。
- FIN 0.1.1 有本地 RAG/SQL/Graph/official-asset 候选、Evidence/Numeric/Trace、历史 real evidence operator 和 multi-agent run，也有 NVDA historical S3 R2；但没有 current three-case、Workbench、Human Review 和 release-level Agentic Search/Research acceptance。
- FIN 0.1.2 S0–S3 对 Runtime、hermetic proof、三案真值、模型 surface 和 frozen-evidence 九件套规划充分，但没有把 F01–F15、自然 Case、真实检索、bounded Graph、Workbench、Human Review 逐项放入 stage gate。登记 `RC-P36-110`。
- 当前 S3 明确 `source network/external tools = 0`，因此未来 S3 success 必须标记 `F05 not assessed`。

## 完成的规划修正

- 新增产品级完整对账：`docs/product/FIN_0_1_1_0_1_2_PRD_CAPABILITY_ALIGNMENT_AND_S0_TO_S5_REBASELINE_20260804.zh-CN.md`。
- 新增机器决策：`configs/releases/fin_ia_0_1_1_0_1_2_prd_capability_alignment_and_s0_to_s5_rebaseline_v1_0.json`。
- 更新 canonical plan，保持当前 S3 不扩项，将尚未执行的 S4 重排为 8 项、S5 重排为 6 项。
- 更新 PRD allocation、版本谱系、program backlog 和 current context pack。
- 为 FIN 0.2–0.5 补充统一 S0–S5 模板；不改变各版本原产品定义。

## 验证与边界

- 本项模型、Provider、source network、external tool、业务 Run/Artifact：全部 0。
- 没有执行新的检索实验；沿用前一只读审计刚完成的当前分支 retrieval regression：`34 passed`。
- 后续仍按 current next 先处理 S3-T03 replacement admission authority；本规划不授权 admission、DeepSeek、第三次 exact 或逐字段维修。
- `RC-P36-110` 只在 planning 层修复；真实能力仍需 S4/S5 执行后关闭。
