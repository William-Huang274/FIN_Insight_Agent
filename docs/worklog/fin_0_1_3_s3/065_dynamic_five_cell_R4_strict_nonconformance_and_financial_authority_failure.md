# 065 DELL 动态五单元 R4：远端 strict 未守约，本地金融权威正确拒绝

日期：2026-08-17

## 本轮实际执行

R4 从干净、已同步提交 `05894415096b9de8d4d9fe7fba29021134a94120` 签发 fresh authority。它没有重跑 Planner、当前 S1/S2、三个已通过 Judgment 或两个已完成分析草稿，只执行价值获取和反方证据两次低思考严格交卷。

两次 Provider 请求都返回 `finish_reason=tool_calls`，总计 2 次模型调用，0 retry、0 fallback、0 protocol switch、0 外源网络、0 新 Evidence、0 candidate promotion。价值获取和反方证据均未通过本地合同，综合按 5/5 前置规则未执行；需求质量、经营表现和现金转换三份 Judgment 保持有效且未重跑。

## 为什么这次不是简单的“模型又没听话”

两份真实请求都携带 `strict=true` 和同一字符串 `pattern`。但 DeepSeek Beta 仍分别返回了带数字的 filing／期间表面。用独立 `jsonschema.Draft202012Validator` 对“请求中真实 wire Schema＋响应中真实 Tool 参数”复核：

- 价值获取在 `$.mechanism_atom` 恰有 1 个 `pattern` 错误；
- 反方证据在 `$.thesis_atom` 恰有 1 个 `pattern` 错误。

因此，之前的非金融 canary 只证明“远端接受 Schema，并在那一次自然返回了合规文字”，没有证明远端会强制执行复杂负向正则。官方文档声称 strict 输出遵循 Schema，且列出 `pattern`、`$def/$ref` 支持；R4 与该声称不一致。Provider 内部究竟是正则方言差异还是 strict 执行缺陷，当前证据无法区分。FIN 必须把远端 strict 降为形状辅助，本地完整 Validator 继续作为唯一合同权威。

## 更重要的业务问题

这次不能只删掉 `10-Q` 或 `FY27 Q1` 后追认输出，因为两个单元还有独立的金融权威问题。

### 价值获取

模型写出了“AI 优化服务器 mix 压低公司毛利率”的因果路径。当前 S2 只提供公司／分部同口径财务事实和产品收入叙事，没有产品到公司或分部毛利率的 typed bridge。句尾再补“非产品级因果证明”不能取消前面已经做出的因果判断。因此这是真正的金融 L1，不是格式问题。

### 反方证据

模型把唯一 Evidence 标成 `limit`，却同时选择 `mixed + bounded_inference`，并在 thesis 中把需求、营收、EPS 与经营现金流并存写成“新增收入能转化为利润和现金”的支持。证据角色与最终权威标签彼此矛盾。本地 `research_consumer_supported_judgment_without_evidence` 正确拒绝。

## 结构性处置

下一步仍留在 S3，不改产品版本，也不把问题推给 S4：

1. Provider strict 只做形状辅助；本地金融合同保持最终权威。
2. 分析草稿继续保留完整数字、期间和来源；低思考交卷前生成一份只去除权威表面的确定性输入投影，避免要求模型从满是数字的草稿中重新写“无数字原文”。该投影只移除表面，不替模型写观点。
3. `judgment_status` 与 `inference_authority` 由模型选择的 support／limit／context Evidence 和当前 typed gaps 本地编译，避免让模型重复选择一个可以确定计算、又可能自相矛盾的标签。
4. 新增产品／分部到利润、毛利率、营业利润率的双向因果 bridge gate；无 typed bridge 时，无论声称“促进”还是“压低”都不得通过，后置免责声明不能救回前置因果句。
5. 用 R4 immutable capture 做零调用 replay、mutation 与三案例隔离；只有完整回归、clean push、scope decision 和 fresh authority 后，才允许新 attempt 修复 value 的错误分析并重交受影响节点。

## 不做的事

- 不把 R4 被拒参数手工清洗后当成业务事实；
- 不为每个字段再加一段 Prompt；
- 不重跑 Planner、S1/S2 或三个有效单元；
- 不因为远端 strict 不可靠而取消本地金融门禁；
- DELL 五单元、完整研报、MU/NVDA／留出泛化、qualified-human 和 S3 acceptance 均未通过。

## 证据

- authority：`configs/research/evals/fin_ia_0_1_3_s3_dell_dynamic_five_cell_node_successor_chat_live_authority_v1_0.json`
- public result：`configs/research/evals/fin_ia_0_1_3_s3_dell_dynamic_five_cell_node_successor_chat_live_result_v1_0.json`
- failure assessment：`configs/research/evals/fin_ia_0_1_3_s3_dell_dynamic_five_cell_node_successor_chat_live_failure_assessment_v1_0.json`
- private full result：`data/workbench_private/s3_dynamic_five_cell/FIN013-S3-DELL-DYNAMIC-FIVE-CELL-R4/full_result.json`
- public result digest：`73c3a577446d11a5f1fe3035317aadfbc3dae1c17eaa1bce9ccaa6882a468766`
- private full result digest：`ddb85d920b3a51a55c12da51092d0786da4ce2ff16647725ad95c19d0f977f32`

## 后续证据更正（2026-08-17）

R4 的 Provider strict 不守 `pattern`、本地 no-digit 校验正确拒绝，以及反方单元“只选 limit 却提交支持性结论”的判断均保持不变。但本记录把价值获取单元写成“当前材料完全没有 AI 服务器组合与公司毛利率方向关系”，范围过宽，必须更正。

当前 reviewed Dell `10-Q` 原文中确实存在一句由公司披露、绑定 FY2026 Q3 的历史方向关系：`The decreases in gross margin percentage and non-GAAP gross margin percentage were primarily driven by a shift in mix towards our AI-optimized server offerings.`。它能够支持“公司在该历史期间把毛利率下降主要归因于 AI 优化服务器组合变化”这一带归属、带期间的历史陈述；它不能自动外推 FY2027 Q1，不能证明独立因果，也不能提供产品毛利、ASP、台数、PVM 或利润分配。

R4 当时没有看见这句原文，不是因为 Evidence 不存在，而是当前 Evidence Pack 只把来源前 1,200 字符投影给模型；该句位于原文 2,273–2,433 字符处。模型只看见人工复核中文摘要，导致“来源存在、审计可追溯、模型不可见”。最早责任层因此修订为 S1/S3 之间的 reviewed Evidence projection，而不是简单归为 S2 bridge 全缺失。

后续结构处置为：

1. claim 对象通过内容寻址的 reviewed anchor catalog 暴露经过复核的精确原句，而不是扩大所有来源的通用前缀上限；
2. 新增 `issuer_attributed_historical_directional_relation`，强制绑定公司、Evidence、source digest、item digest、期间和原句 anchor；
3. analysis 仍可见精确原文、数字和期间；submission 只接收去除 URL、内部 ref、日期和数值表面的同一模型草稿，不替模型写判断；
4. 同一 Evidence 可以分别以 support 与 limit 使用一次，但模型仍须明确提交判断状态，本地 Validator 继续检查叙事是否超出所选 Evidence；不采用 Harness 自动推导 status 的方案，因为它可能把一段实质上无支持的正面叙事伪装成合法状态；
5. 新 successor 只复用 R4 的 planner 与 current S1/S2 结果，五个分析、五个交卷和两次综合全部重跑，不复用 R4 单元草稿或 Judgment。

因此 `RC-S2-004` 仍未关闭，但边界改为：历史、发行人归属的期间内方向关系可用；跨期间、独立因果、产品到分部／公司的利润与现金桥仍不可用。R4 仍是 immutable failure，不能因本次更正被追认为通过。
