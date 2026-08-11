# Output Appendix: 20260521 Full30 Qwen9B vs DeepSeek A/B

## User Query
```text
你看完这些财报之后你有什么感觉，尤其是AI行业从2023到2025年的发展，结合相关公司的财报指标谈谈你的看法
```

## DeepSeek v4-pro High Thinking
- Artifacts: `eval/sec_cases/outputs/interactive_sec_agent/20260521_161252_b38c717195`
- Status: invalid JSON repaired to ledger-safe output.

```text
data_center_revenue 从 2023 年的 15,068（百万美元） (INTERACTIVE_20260521_161252_b38c717195::NVDA::2023::data_center_revenue::total_value::compute_networking) 到 2025 年的 116,193（百万美元） (INTERACTIVE_20260521_161252_b38c717195::NVDA::2025::data_center_revenue::total_value::compute_networking)。 cloud_revenue 从 2023 年的 90,757（百万美元） (INTERACTIVE_20260521_161252_b38c717195::AMZN::2023::cloud_revenue::total_value::aws) 到 2025 年的 128,725（百万美元） (INTERACTIVE_20260521_161252_b38c717195::AMZN::2025::cloud_revenue::total_value::aws)。 research_and_development 从 2023 年的 38,483（百万美元） (INTERACTIVE_20260521_161252_b38c717195::META::2023::research_and_development::total_value::research_and_development) 到 2025 年的 57,372（百万美元） (INTERACTIVE_20260521_161252_b38c717195::META::2025::research_and_development::total_value::research_and_development)。 该结论仅使用 Exact-Value Ledger 中的数值。

1. INTC 2023 data_center_revenue total_value = 8,721（百万美元） (INTERACTIVE_20260521_161252_b38c717195::INTC::2023::data_center_revenue::total_value)
2. AMZN 2025 cloud_revenue total_value = 128,725（百万美元） (INTERACTIVE_20260521_161252_b38c717195::AMZN::2025::cloud_revenue::total_value::aws)
3. AMZN 2024 cloud_revenue total_value = 107,556（百万美元） (INTERACTIVE_20260521_161252_b38c717195::AMZN::2024::cloud_revenue::total_value::aws)
4. AMZN 2023 cloud_revenue total_value = 90,757（百万美元） (INTERACTIVE_20260521_161252_b38c717195::AMZN::2023::cloud_revenue::total_value::aws)
5. META 2025 research_and_development total_value = 57,372（百万美元） (INTERACTIVE_20260521_161252_b38c717195::META::2025::research_and_development::total_value::research_and_development)

limitations:
- Qwen 输出不是可解析 JSON；精确数值只保留 Exact-Value Ledger 中的行。
- Claim verifier removed 4 unsupported candidate claim(s) before rendering.
```

## Qwen9B Local vLLM
- Artifacts: `eval/sec_cases/outputs/interactive_sec_agent/20260521_161929_b38c717195`
- Status: parsed; all deterministic gates passed.

```text
AI 行业在 2023 至 2025 年间呈现分化态势，部分公司云业务与数据中心收入显著增长，而另一些公司则面临研发成本上升与市场竞争加剧的挑战。

1. AMZN 云业务收入从 2023 年的 90,757（百万美元） (INTERACTIVE_20260521_161929_b38c717195::AMZN::2023::cloud_revenue::total_value::aws)增长至 2025 年的 128,725（百万美元） (INTERACTIVE_20260521_161929_b38c717195::AMZN::2025::cloud_revenue::total_value::aws)，显示其在 AI 云市场的强劲增长。
2. META 研发投入从 2023 年的 38,483（百万美元） (INTERACTIVE_20260521_161929_b38c717195::META::2023::research_and_development::total_value::research_and_development)增加至 2025 年的 57,372（百万美元） (INTERACTIVE_20260521_161929_b38c717195::META::2025::research_and_development::total_value::research_and_development)，反映其在 AI 领域的持续投入。
3. INTC 仅在 2023 年披露了数据中心和 AI 业务收入为 8,721（百万美元） (INTERACTIVE_20260521_161929_b38c717195::INTC::2023::data_center_revenue::total_value)，缺乏后续年份数据，限制了对其 AI 业务表现的全面评估。

limitations:
- SEC-only evidence boundary.
- AI exposure differs by company; segment labels are not always directly comparable.
- Precise values must come from runtime Exact-Value Ledger only.
- 模型输出中的未支持命名事实已被删除或泛化；命名产品、KPI 和英文标签仅保留当前引用证据支持的内容。
- Claim verifier removed 2 unsupported candidate claim(s) before rendering.
```

## DeepSeek v4-pro No Thinking
- Artifacts: `eval/sec_cases/outputs/interactive_sec_agent/20260521_162939_b38c717195`
- Status: parsed; failed `v2_semantic_contract_gate_pass`.

```text
基于SEC 10-K证据，AI行业在2023至2025年间呈现显著的投资扩张与收入增长，但各公司披露口径差异较大。

1. META的Research and development费用从2023年的38,483（百万美元） (INTERACTIVE_20260521_162939_b38c717195::META::2023::research_and_development::total_value::research_and_development)增长至2025年的57,372（百万美元） (INTERACTIVE_20260521_162939_b38c717195::META::2025::research_and_development::total_value::research_and_development)，管理层指出增长主要来自与AI计划相关的员工薪酬和基础设施成本。
2. INTC的Data Center and AI分部在2023年录得经营亏损( 530 )（百万美元），而该分部净收入为15,521（百万美元） (INTERACTIVE_20260521_162939_b38c717195::INTC::2023::operating_income::total_value)，表明其在AI领域的投入尚未转化为盈利。
3. INTC 2023 operating income（经营利润/运营利润） 为 15,521（百万美元） (INTERACTIVE_20260521_162939_b38c717195::INTC::2023::operating_income::total_value)；INTC 2023 operating income（经营利润/运营利润） 为 19,445（百万美元） (INTERACTIVE_20260521_162939_b38c717195::INTC::2023::operating_income::total_value::3)。

limitations:
- 仅基于2023-2025年10-K SEC文件，不包含10-Q、8-K、财报电话会或市场数据。
- 各公司AI相关业务披露口径不同，部分公司未单独列示AI收入，需依赖管理层讨论与业务描述推断。
- 2025年10-K可能尚未覆盖完整财年，部分公司财年截止日不同，跨公司比较需注意时间对齐。
- 精确数值必须由运行时Exact-Value Ledger提取，本分析不提供未在Ledger中列出的数字。
- SEC-only evidence boundary.
- Precise values must come from runtime Exact-Value Ledger only.
- 必要限制：精确数值必须由运行时Exact-Value Ledger提取，本计划不提供具体数字。；精确数值必须由运行时Exact-Value Ledger提取，本计划不提供具体数字。
- Claim verifier removed 2 unsupported candidate claim(s) before rendering.
```
