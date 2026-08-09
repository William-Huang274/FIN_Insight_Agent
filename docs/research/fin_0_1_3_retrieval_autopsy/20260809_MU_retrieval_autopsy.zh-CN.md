# FIN 0.1.3 MU 检索尸检

日期：2026-08-09
冻结截至日：2026-08-06
归属：S1 检索与 Evidence Pack 准备；不评价 DeepSeek

## 结论

MU 当前内源能找到当期收入／毛利、客户承诺、资本开支、部分供给紧张和下游 AI server / cloud demand，但结果被拆散在多个 chunk 中，且没有把“价格、bit shipment、HBM mix、长期协议、现金流、扩产节奏”组合成同一个 Evidence Pack。Dell/Microsoft/NVIDIA/TSMC 的材料更多是行业链条佐证，不能自动升级成 MU 的客户、份额或供给分配事实。

当前状态是 `issuer_and_regulatory_material_present / economic_bridge_and_relationship_attribution_incomplete`。

## 四路对照

### A：当前产品自动内源检索

- DELL customer-demand：目标排第 4，前排含前瞻声明和宽泛描述。
- Microsoft customer-demand：目标排第 2。
- MU issuer-results：目标排第 2，可见 Q3 指引／结果，但 price-versus-bit 和 HBM 机制不完整。
- MU regulatory：目标排第 14，top 10 不能稳定找出客户存款、资本开支和长期承诺。
- NVIDIA supply：目标排第 2，但首条偏产品发布和通用平台内容。
- TSMC supply：目标排第 1，但实际只是 Q2 财务摘要，没有 CoWoS 容量。

### B：Codex 监督、复用同一内源工具

- DELL customer-demand：第 4 升到第 2，首条更接近 AI-optimized solution 和 backlog。
- Microsoft customer-demand：第 2 升到第 1。
- MU issuer-results：第 2 降到第 7；首条变成 MCBU ASP / bit shipment，说明单个查询难以同时覆盖公司总结果和业务机制。
- MU regulatory：第 14 升到第 1，首条直接命中约 220 亿美元客户存款和承诺，证明 facet 化查询有效。
- NVIDIA supply：第 2 升到第 1，但仍是第三方制造依赖，不能证明 NVIDIA 给 MU 的订单或 MU 在平台中的份额。
- TSMC supply：第 1 降到第 2，仍未出现 CoWoS 实质材料。

同一查询优化令 regulatory 大幅改善，却让 issuer 从第 2 跌到第 7，说明当前一个长查询把多个研究问题压成一组 OR token；不是再加几个关键词就能稳定解决。

### 外源工具／capture replay

现有外源正式选择只覆盖 MU regulatory filing。issuer results、customer demand 和 supply 都没有进入 selected pack；hidden target 也未进入候选池。

### C：独立参考研究

- [Micron Q3 FY2026 业绩稿](https://investors.micron.com/node/50671)：收入 414.6 亿美元、经营现金流 253.9 亿美元；HBM4 已对领先平台高量出货，并向多家终端客户送样。
- [Micron Q3 FY2026 prepared remarks](https://investors.micron.com/static-files/631b1a32-5537-46ae-8f40-82e42fc79dfe)：16 份长期供货协议通常为五年期并带 take-or-pay，约覆盖 20% DRAM 和三分之一 NAND，RPO 约 1,000 亿美元，存款及相关承诺约 220 亿美元；但这些存款属于融资现金流，不能当作自由现金流。
- 同一 prepared remarks 显示 DRAM 增长主要由价格而非 bit shipment 驱动，HBM4 爬坡的 die-size / yield 和先进封装要求决定实际供给；新加坡 HBM packaging capacity 主要在 2027 年上半年才产生实质贡献。
- DELL 的 AI server orders/backlog 与 Microsoft 的 AI 基础设施投入证明下游环境强；NVIDIA 的平台增长和 TSMC 的先进制程／封装扩产提供产业链佐证，但都不能直接证明 MU 的客户份额。

参考判断应当同时表达：MU 的议价和供需位置很强，长期协议提高可见度；利润增长很大程度由价格与 mix 驱动；高资本开支、HBM 爬坡、客户集中和周期反转仍是主要反证。关键 What-Would-Change 包括 HBM4 量产良率、bit shipment、合同兑现、库存天数、capex/FCF 和 2027 年供给释放。

## Evidence Pack 可用性

| Required slot | 当前材料 | 手工判定 |
| --- | --- | --- |
| issuer results / management commentary | 当前收入、毛利与部分产品材料可见 | 部分；缺 price-bit-HBM 的完整桥接 |
| regulatory / financial reconciliation | B 查询能把长期协议／存款提到第 1 | 部分；库存、现金流归类和 price-volume 仍需多片段组合 |
| customer demand / deployment | DELL 与 Microsoft 的 AI 投资材料可见 | 行业佐证可用，MU 客户归因不足 |
| supply capacity / counterevidence | NVIDIA/TSMC 片段存在 | 缺 MU HBM 量产、封装瓶颈与明确平台连接 |

## 根因与归属

- S0：prepared remarks 的问答、价格／bit／HBM／合同／现金流没有被拆成带文档层级的研究对象；跨表格与跨段语境容易丢失。
- S1：一个 issuer 查询承担四个 facet，具体化后发生互相挤压；外源只稳定发现 SEC，IR 材料未进入正式 pack；关系方向不足以证明客户归因。
- S3：需要把价格、数量、mix、合同、产能与现金流重算成机制，而不是让 Writer 从零散句子自由补全。
- S4：现有 Workbench 无法展示这种缺失，因此用户只看到通用边界句。

本轮未修改产品代码、未提升候选为 Evidence、未执行模型调用。
