# WorkBuddy 多行业 Calibration 审计

日期：2026-07-11

状态：`pass`。审计 12 个正式 HTML 与 12 条完整 trajectory；未运行 FIN paid/full-chain。
模型边界：`deepseek-v4-pro`，按 non-strong calibration model 处理；`status=pass` 只表示审计输入完整，不表示研究质量通过。

## 总体结果

- Agentic loops observed：12/12。
- Model calls：200；tool calls：399；WebSearch：98。
- 总 trajectory wall time：70.68 分钟；平均每 case：5.89 分钟。
- Cumulative input tokens：16177682；cached：14921600（92.2%）；uncached：1256082；output：286137。
- External links：222；primary/government/issuer links：30；ratio：13.5%。
- All required surfaces pass：10/12。
- Machine-readable claim lineage：0/12。

## Case Matrix

| Case | Sector | Type | Calls | Tools | Search | Links | Primary | Surfaces | Trace |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| WB-S01 | technology_software_services | company_comparison | 16 | 28 | 12 | 16 | 3 | 7/7 | ok |
| WB-S02 | banks_financials | company_comparison | 19 | 47 | 0 | 7 | 0 | 7/7 | ok |
| WB-S03 | healthcare_pharma_medtech | company_comparison | 13 | 37 | 6 | 13 | 6 | 7/7 | ok |
| WB-S04 | retail_consumer | company_comparison | 18 | 38 | 0 | 0 | 0 | 7/7 | ok |
| WB-S05 | energy | company_comparison | 18 | 28 | 11 | 28 | 3 | 7/7 | ok |
| WB-S06 | utilities_power | company_comparison | 19 | 36 | 12 | 22 | 1 | 7/7 | ok |
| WB-S07 | industrials | company_comparison | 24 | 39 | 6 | 15 | 3 | 7/7 | error |
| WB-S08 | cybersecurity | company_comparison | 14 | 25 | 12 | 16 | 3 | 7/7 | ok |
| WB-T01 | retail_consumer | earnings_event_update | 16 | 38 | 11 | 23 | 4 | 6/7 | ok |
| WB-T02 | healthcare_pharma_medtech | valuation_price_in | 15 | 32 | 1 | 12 | 2 | 7/7 | error |
| WB-T03 | auto_mobility | policy_shock | 11 | 20 | 13 | 37 | 4 | 6/7 | ok |
| WB-T04 | cybersecurity | counter_thesis | 17 | 31 | 14 | 33 | 1 | 7/7 | ok |

## 同 Prompt 重复运行

WB-T04 有两个完成版本，source-domain Jaccard 仅 `4.4%`。两个版本均覆盖所需结构，但主版本比重复版本多 `13` 个外链、表格数差异 `4`。这说明结构服从度较稳定，source selection 与 quantitative framing 的可复现性较弱。

## Visual QA

在 `1440x900` 使用 local Microsoft Edge via Playwright 抽查 WB-S02, WB-S03, WB-T03, WB-T04：横向溢出 `0`，console errors `0`。银行、GLP-1 和反证报告的 canvas 实际渲染；政策报告以静态表格为主。

## 审计覆盖与盲区

本轮实际覆盖 artifact/trace 存在性、调用计数、prompt-conditioned surface 关键词、最终 HTML 链接域启发式、6 个孤立数字 spot checks、4 个桌面渲染 smoke 和 1 组同 prompt 来源域比较。

本轮没有系统审计 cell 语义质量、完整 claim correctness/entailment、数字单位期间与公式、source freshness/conflict、query/tool/observation usefulness、repair 因果与 stop rule、上下文重复与信息产出、handoff/version consistency、图表数据绑定、行业判断深度或 client readiness。后续 DefectAndPatternCandidateMatrix 前必须补这层复审。

## 结论

WorkBuddy 12-case 只证明 DeepSeek V4 在这些 prompts、工具和独立上下文条件下产生了多轮调用及可渲染报告；它没有证明推理、取证、判断、repair 或上下文管理已经成熟。

因此 FIN 应把这些案例当作跨行业 defect and improvement baseline：逐项判断 retain-with-independent-evidence、redesign、repair 或 reject。不能默认吸收其研究循环、报告结构或轨迹；任何进入 pack 的模式都必须先通过独立 rubric、语义复审、FIN provenance/numeric contracts 和 shadow comparison。

## 轨迹边界

- WorkBuddy raw reasoning 存在于本地 project logs，本审计不复制或展示。
- `trace_status=error` 但 HTML 完成的 case 必须记录为 artifact complete / trajectory degraded，而不是简单 pass。
- Spot checks 只验证少数高影响数字，不构成整份报告事实验收。
- WorkBuddy HTML 和 trace 是 calibration input，不是 FIN runtime evidence。
