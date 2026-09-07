# 068 DELL 五单元 R6 数值关系闭包与 Value 交卷失败

日期：2026-08-17

## 结论

R6 完成了五个 analysis 和五个 submission，共 10 次 DeepSeek 调用，0 retry／fallback／protocol switch／external-source network。Demand、Operating、Cash、Counterevidence 四单元通过本地合同；Value 在 `research_consumer_numeric_relation_boundary_invalid` 失败，因此综合和报告按设计未运行。

R5 的 Value-only ClaimAuthority 泄漏没有复发。四个非 Value 单元的 Prompt、Tool 与自然输出均没有越权选择 Value relation。当前失败属于 Value 单元内部的“关系—端点—证据支持”合同，而不是跨单元污染、Provider 断流或新数据缺失。

## 实际业务表现

- Demand 把订单、backlog、客户数与供给紧张识别为真实需求信号，同时明确 buy-ahead、取消／推迟和订单到收入转化风险，内容有实质判断。
- Operating 识别公司层收入、利润与现金改善，但没有把公司结果直接归因给 AI 产品；同时指出毛利率下降和产品级桥缺失。
- Cash 对经营现金流、自由现金流、资本开支和营运资金边界形成了公司层判断；“净利润是主要驱动”的措辞仍需在最终内容验收中复核。
- Counterevidence 能阻止把上游库存冒充 Dell 本案事实，但独立反证深度仍偏薄，属于后续内容质量问题而非本次合同硬失败。
- Value 原始输出的核心方向是公司层收入、毛利、营业利润与利润率同口径观察，并明确否认 AI 产品到公司利润的直接因果桥；但该输出尚未通过合同，不得进入业务结果。

## 失败链回放

1. 模型选择了五条同比 NumericRelation，却只选择其中四条关系的八个 NumericFact 端点；收入同比关系的两个端点漏选。
2. Tool 的 relation enum、两个端点和 Prompt 规则均存在，但远端 strict schema 不能表达“选关系就必须同时选两个端点”的跨字段依赖；本地正确 fail closed。
3. 零调用补齐关系端点后，下一门变成 `supported_judgment_without_evidence`。这暴露的是项目规则缺口：模型以 source-bound NumericFact／NumericRelation 支撑公司财务观察，Validator 却只把文本 EV 的 support 角色算作证据。
4. 仅为诊断绕过该规则后，唯一剩余硬失败是 Value thesis 写入 `FY2026 Q1` 和 `FY2027 Q1`。数字／日期禁止规则不放宽；该文本必须由模型重新提交，Harness 不得代写。

## 下一步边界

结构修复只允许两件事：关系 alias 本地确定性展开端点并留 receipt；source-bound NumericFact／Relation／QF 计入结构化 support。随后用 R6 capture 做 replay 和 mutation。

新的 successor 不重跑五个 analysis 或四个有效 submission。它只能绑定复用四个有效 cell、复用 Value analysis capture，给 Value 一次带 typed feedback 的新 submission，然后在五单元全部通过时执行 synthesis analysis＋submission，总预算 3 次调用。R6 失败保持不变，不能手工清洗或追认为成功。
