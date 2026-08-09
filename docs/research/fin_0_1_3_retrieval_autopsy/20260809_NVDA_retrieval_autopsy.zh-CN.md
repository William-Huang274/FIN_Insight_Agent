# FIN 0.1.3 NVDA 检索尸检

日期：2026-08-09
冻结截至日：2026-08-06
归属：S1 检索与 Evidence Pack 准备；不评价 DeepSeek

## 结论

NVDA 是三案里“看起来最像能写报告、实际仍缺机制闭环”的案例。公司收入、数据中心收入、毛利率、China outlook、出口限制、客户需求和部分供应链风险都在当前材料中，但自动结果没有把客户集中、库存／采购承诺、架构切换、HBM 和 CoWoS 约束组合起来，也不能把 Dell/Microsoft 的需求直接归因给 NVIDIA。

当前状态是 `broad_material_presence / decision-grade_mechanism_pack_absent`。

## 四路对照

### A：当前产品自动内源检索

- DELL customer-demand：目标排第 5，前排含公司定义和前瞻声明。
- Microsoft customer-demand：目标排第 2。
- NVIDIA issuer-results：目标排第 4，首条反而是安全港／第三方制造依赖。
- NVIDIA regulatory：目标排第 2，但第 1 只是 `Unaudited`，显示 chunk 和模板噪声仍会占位。
- Micron supply：目标排第 2。
- TSMC supply：目标排第 1，但内容是 Q2 财务摘要而非先进封装容量。

### B：Codex 监督、复用同一内源工具

- DELL customer-demand：第 5 升到第 2，首条更接近 AI backlog。
- Microsoft customer-demand：第 2 升到第 1，能看到 AI infrastructure investment。
- NVIDIA issuer-results：第 4 升到第 2，首条变成 China revenue 被排除在 outlook 之外。
- NVIDIA regulatory：第 2 降到第 7；首条变成出口控制。它提高了一个 facet，却把现金流 target 往后推，证明单查询不能完成多 facet reconciliation。
- Micron supply：第 2 降到第 10，仍只有行业供给紧张和产品爬坡。
- TSMC supply：第 1 降到第 2，仍缺 CoWoS 定量。

### 外源工具／capture replay

现有外源 selected pack 对 NVDA 只覆盖 regulatory filing 和一份来自 MU 10-Q 的 supply 候选；issuer、customer 仍缺，TSMC 先进封装未进入 pack。外源总共只有一个 source family，不能达到研究所需的来源多样性。

### C：独立参考研究

- [NVIDIA Q1 FY2027 业绩稿](https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-First-Quarter-Fiscal-2027/default.aspx)：收入 816.15 亿美元、Data Center 752 亿美元、毛利率 74.9%；Q2 指引 910 亿美元，明确不假设中国数据中心计算收入。
- [NVIDIA Q1 FY2027 10-Q](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000052/nvda-20260426.htm)：三家直接客户分别占收入 21%、17% 和 16%；库存 257.97 亿美元，excess inventory purchase obligations 31.21 亿美元。第三方部件、封装和长提前期不可取消采购会放大需求判断错误。
- 同一 10-Q 显示 Rubin 预计在 FY2027 下半年出货；年度架构切换可能造成现有产品延迟购买、库存拨备和收入波动。出口限制此前也已造成 H20 库存／采购义务损失。
- [Microsoft FY2026 Q3 电话会](https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q3)与 DELL Q1 FY2027 披露能验证 AI 基础设施建设和服务器订单强劲，但不能据此计算 NVIDIA 的具体订单份额。
- [TSMC Q2 2026 业绩与电话会](https://investor.tsmc.com/english/quarterly-results/2026/q2)：HPC 已占 66% 收入，2026 capex 提升到 600–640 亿美元；先进封装仍在扩建，但公司没有披露可直接分配给 NVIDIA 的 CoWoS 单位容量。

参考判断应是：需求和盈利能力很强，但客户集中、China exclusion、不可取消采购、库存、数据中心电力／资本约束和 Rubin 切换共同决定风险。需要监测 hyperscaler capex 的实际上线、客户集中变化、inventory/purchase obligations、出口许可、Rubin 交付和 HBM/CoWoS 供给。

## Evidence Pack 可用性

| Required slot | 当前材料 | 手工判定 |
| --- | --- | --- |
| issuer results / management commentary | 当前结果和 China outlook 可见 | 部分；outlook、产品切换和管理层机制分散 |
| regulatory / financial reconciliation | 现金流、出口风险、集中度、采购义务各自可找到 | 部分；当前查询只能把其中一个 facet 推到前面 |
| customer demand / deployment | DELL、Microsoft 信号较强 | 只能证明下游需求，不足以做 NVIDIA 客户归因 |
| supply capacity / counterevidence | MU 与 TSMC 有行业信号 | 缺 HBM/CoWoS 数量及对 NVIDIA 的分配关系 |

## 根因与归属

- S0：10-Q 表格、风险段和 earnings material 被切成彼此孤立的对象；TSMC 只有 3 个粗粒度当前片段。
- S1：查询把收入、outlook、集中度、现金流、出口风险塞在一条 OR 风格语句里；graph 的期间不可用；外源发现只稳定覆盖 SEC。
- S3：需要针对 residual gap 继续追问，并明确区分行业 demand confirmation、客户归因和供应商分配；当前没有证明这种动态研究。
- S4：当前报告中的通用判断原子是 Evidence Pack 不完整的下游表现。

本轮未修改产品代码、未提升候选为 Evidence、未执行模型调用。
