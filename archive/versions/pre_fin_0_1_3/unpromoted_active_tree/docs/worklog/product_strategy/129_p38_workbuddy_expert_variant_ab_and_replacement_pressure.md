# 129 P38 WorkBuddy Expert Variant A/B And Replacement Pressure

日期：2026-07-12

## 范围

把同题专家 / Skill 组合重跑建模为基准 case 的独立 variant：`WB-S01B` 对比 `WB-S01`，`WB-S02B` 对比 `WB-S02`。读取最终 HTML 和可观察 tool trajectory，不读取 raw CoT，不覆盖原 12-case，不晋升 WorkBuddy 事实。

## S01B

- 专家配置显著改善四层传导、What-Would-Change、gap surface 和报告组织。
- NeoData 失败后发生真实工具恢复，但轨迹仍只有一个 cli agent，没有 subagent/handoff。
- 实际调用 Skill 与 UI selected Skill 不一致；必须分别记录 selected/context-injected/invoked/accepted capability。
- Writer 丢弃 NeoData as-of、request id 和 source URL，数字 claim-local lineage 仍为零。
- 发现 Salesforce 跨期除法、Datadog 指标合并、Snowflake period binding 和 credential trace 暴露。

## S02B

- 新组合实际调用 `us-stock-analysis`、`earnings-tracker`、`deep-research`。
- HTML 从 10 张表增至 23 张表，加入两个 SVG 决策图、MISSING/STALE 和银行专属 WWC；Wells Fargo asset cap freshness 得到修正。
- 路由从旧版结构化金融查询切为 12 次 WebSearch；无 source-open、无官方 filing parser、无写后 research repair。
- 2024 存款成本比较来自低权威 search snippet。JPM 官方 2024 total deposit rate 为 2.08%，报告写 0.25%，属于 metric-definition/category error。
- 核心 Q1 数据不少方向正确，但来源集中在报告末尾，396 个数字表格单元格均无 claim-local link。

## 产品判断

通用 Agent 平台已经对零售/prosumer 研究、通用分析师初稿、公开网页公司比较和精美 HTML/dashboard 构成当前替代压力，并可能继续进入小型顾问与标准化公司监控。

FIN 不能以“会搜索、会调用几个金融 Skill、会输出漂亮报告”为护城河。后续差异化固定为 evidence/numeric control、point-in-time memory、private/licensed data、durable institutional workflow、reviewer accountability 和 cross-artifact consistency。

## 产物

- `configs/engineering_handoff/workbuddy_expert_variant_review_v0_1.json`
- `src/sec_agent/workbuddy_expert_variant_audit.py`
- `scripts/engineering/build_workbuddy_expert_variant_audit.py`
- `tests/test_workbuddy_expert_variant_audit.py`
- `data/manifests/workbuddy_expert_variant_audit_v0_1.json`
- `docs/architecture/repository/WORKBUDDY_EXPERT_VARIANT_AB_AUDIT_20260712.zh-CN.md`

## 边界

本轮未运行 FIN paid model、Writer 或 full-chain；未实现新 runtime。外部平台能力判断只对当前版本、当前任务和可观察轨迹有效。
