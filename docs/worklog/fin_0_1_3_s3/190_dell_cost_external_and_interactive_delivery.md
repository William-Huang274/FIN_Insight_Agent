# Dell：成本根因、成熟外源与真实交互的顺序交付

日期：2026-09-06。产品FIN0.1.3，同分支/S3，不是新版本。源设计：`docs/architecture/research/FIN_0_1_3_DELL_AGENTIC_MULTI_AGENT_VERTICAL_DETAILED_TECHNICAL_DESIGN_20260903.zh-CN.md` §0最新顺序。起点 `e8aacc02b0c6860ba7fabf2d53a901c09150ae04` clean且与origin一致。

## Owner目标与当前范围

先查清此前约10元消耗来自试错、上下文还是prompt，再按证据优化；成熟外源必须由宿主先亲测，再通过MCP交DS；前端需真实任务/实时Agent过程/人工干预/追问，不只是换布局。Dell完整案例跑通后再做1–2个包含长任务与短问答的案例，说明任务复杂度与费用关系。允许真实DS测试及普通问题自主修复、适当Flash/Pro动态路由；不授权新框架、无限付费重试或削弱来源校验。余额已恢复（上轮只读2026-09-05T20:51:09Z available=true），旧A2保持失败，不重写资金阻断历史文件。

## 第一包：离线真实用量审计

输入仅 `Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/*/model-call-events.jsonl` 及同目录项目私有模型上下文；不是Codex live SQLite/JSONL。脚本 `scripts/qualification/dell_q1_specialist_paid_shadow/audit_token_cost.py`，脱敏聚合输出 `D:/temp/fin_dell_token_cost_audit_20260906_a1.json`；原始run不改。字符归因不伪称DeepSeek token归因；不导出原文、prompt或私有reasoning。

实际86 started请求、83有input/output用量、77有cache明细、76有reasoning明细；另1条R10 input_limit在transport前阻断，不能算第87次付费请求。合计input4,502,669/output657,392/total5,160,061；6个R3请求缺cache明细，3个provider失败缺usage，未知不是0。旧A01/A02 Planner另2请求/47,904tokens不在本次脚本范围；R14、RAG裁判、Codex和其他账户消费也不在此范围，不能与账户总扣款等同。

当前官方人民币价（2026-09-06在线读取）Pro空闲时段每百万cache_hit0.15、cache_miss4.5、output13.5；Flash分别0.05/1.5/4.5，高峰翻倍；北京时间工作日9–12、14–18为高峰。这86请求的时间均为空闲。依据：[DeepSeek价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)。搜索快照中旧促销美元价不能套用。

| 77次明细完整请求的费用重算 | CNY | 含义 |
|---|---:|---|
| 缓存输入2,928,896tokens | 0.4393 | 重复历史不是全按cache-miss计费 |
| 非缓存输入1,500,461tokens | 6.7521 | 新材料、首次大包、未命中前缀等 |
| 输出654,815tokens | 8.8400 | 包含推理和工具参数/报告正文 |
| 合计 | 16.0314 | 估计，不是供应商账单 |

R3已知用量在全部命中/全部未命中两端对应约0.0458–0.3647元；这意味着83次usage可见请求按当前价的区间约16.08–16.40元，不能推断3次无usage失败的账单。输入命中率在77次完整明细中约66.1%。有明细的reasoning489,510tokens，占对应thinking输出约74.8%；A5审查尤其明显，48,938/52,828≈92.6%。

| 调试/研究包 | 实际请求 | 已报告tokens | 明细可重算CNY |
|---|---:|---:|---:|
| R2–R10早期单Agent资格 | 24 | 876,563 | 2.42左右，另R3缺cache |
| R11单Agent完整工具循环 | 7 | 509,224 | 1.0837 |
| Q1审查/作者修复A1/A2/A4/A5 | 20 | 1,825,875 | 8.44左右 |
| Lead Q5/Q6 A1 | 18 | 1,047,944 | 2.1742 |
| Lead Q5/Q6 A2 | 17 | 900,455 | 1.9141 |

这些是事后描述性分组，不是相互独立的因果贡献：失败attempt里的成功调用仍有成本、也可能产出可复用研究。仅截断/解析失败/宿主payload拒绝的6次有用量请求约1.61元；大量返工发生在status=success请求里，不能只统计异常请求。Q1审查/修复反复读大包与生成长思考是主要成本之一；两次Lead失败约4.09元均没有已收集底稿，不能当成成功用户任务的正常定价。

输入字符累计约1303万，约59%是同Agent先前已经出现过的消息；这是正常多轮历史与重复包装共同结果，不是59%可省费用。系统prompt正文仅约17.3万字符/1.3%，不能说长system prompt是主因；工具schema字符未含在该分母。A5 reviewer首轮约15.1万字符是继承observations、1.88万是待审正文，另1.47万是能力/skill披露，说明高成本不能全归为工具结果上的几行JSON。

## 已做的最小工程修正

1. 既有SDK audit公开记录cache_hit/miss/reasoning计数，缺失或非法明细为null，不泄露提示词/思维链；成功和已知异常统一记录。
2. 每批并行ToolMessages保留每个结果与tool_call_id，但current_context只在最后一条注入一次；不变的collaboration正文首轮给过不再每轮重发。原文、引用、错误反馈和自己模型的完整reasoning不截断，改变的审查上下文仍传。
3. 原ChatDeepSeek客户端支持用途profile的Flash/Pro与显式reasoning effort；旧配置仍Pro/high（thinking disabled时不发effort），无router模型、无新增框架、无provider fallback。接口已实现不等于Flash金融研究质量已验证。

定向验证：成本脚本、SDK、native batch真实旧R6/MCP回放、review、Lead共104passed/19.81s；随后预算路由小修再次104passed/19.15s。这是同组检查复跑，不是208个不同测试；没有全仓回归、无新真实推理、没有重写旧run。

## 成熟方案调研裁决与紧接的真实对照

- [LangChain context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)：采用既有框架的模型选择/消息投影；若后续真有上下文压力，用原生summarization middleware资格验证，不自造记忆系统。现在没有证据需要为此迁移整个runtime。
- [OpenAI compaction](https://developers.openai.com/api/docs/guides/compaction)：支持Responses压缩，是供应商能力，不能假设DeepSeek Chat API有同样端点。
- [DeepSeek thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/)：带tools的历史reasoning要完整续传，删除它既违背当前用户要求也可能破坏协议。
- [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness/blob/master/README.md)及[compaction](https://deepseek-harness.github.io/deepseek-harness/en/reference/subsystems/compaction)：MIT/官方，但developer preview并明确兼容性会变；借鉴原始日志与模型上下文分离、保持工具成对、按压力压缩，不现在再换成第二套runtime。

下一小额组件对照：从A5 reviewer第一轮的真实输入取样（无自身历史reasoning，含真实待审底稿与原文），保持相同工具schema；各一次Flash/high与Pro/low，对照归档Pro/default-high。这是已知输入的诊断，不是盲评，也不是完整Agent资格。通过现有ChatDeepSeek SDK+LangSmith请求，只观察模型下一步，不执行它提出的工具、不提交研究结果。每个节点TokenBudgetBasis：目的=比较有上下文的金融审查下一步；输入≈6–8万tokens/约19万字符真实源包；输出=合法review或合法工具请求及引用/简明理由；schema负担=现有7类以内原生工具/结构化finding；质量风险=不能漏掉重大财务误用或把可用原文说成缺口；参照=A5已归档4次审查395606tokens；profile=Flash/high或Pro/low；上限32000输出、480s、每profile1请求、不自动retry/resume/fallback，截断/非法参数保持失败；预估约0.5–1.2元合计，保守当前时段上限约1.8元（不含未知provider失败计费）。

先完成这包再接外源，前端/完整Dell/新案例仍未完成，不用本包测试数冒充产品交付。

## 第一包真实对照结果（2026-09-06 05:34–05:40 北京时间）

实现提交 `b4c8c078`，两次均经现有SDK发往DeepSeek，真实LangSmith已查到对应LLM spans；原输入187,815字符，无私有历史reasoning，工具schema相同。输出放在 `Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/20260906-cost-review-{flash-high,pro-low}-a1/`。`request.json`、`response.private.json`、`outcome.json` 分开保存，旧A5不改，未实际执行模型提出的工具/财务审查准入。

| 对照 | 输入 | 输出（其中reasoning） | 耗时 | 当前价重算 | 结果 |
|---|---:|---:|---:|---:|---|
| Flash/high本次 | 66,906 | 32,000（32,000） | 237.435s | 0.244359元 | finish=length，无tool call，失败 |
| Pro/low本次 | 66,827 | 15,023（13,312） | 166.143s | 0.503532元 | 合法SubmitReviewAction/no_material_finding |
| Pro/default-high归档首轮 | 66,906 | 19,730（19,435） | 历史异时对照 | 不作配对计费比较 | RequestSourceAction要求看完整Q1电话会 |

本次两者cache_hit均0，输入小差异是provider报告，不擅自修成相同token数。共2请求/180,756tokens，估0.747891元；没有第三次重试。LangSmith IDs：Flash `01a0737e-5413-73c3-b81e-ceac44771da2`；Pro `01a0737f-cae3-7362-9d42-1ffe048aae21`。LangSmith span的success仅指收到供应商响应，Flash项目结果明确为truncated，不能因trace success而伪称成功。

结论：**拒绝把大包金融终审直接切到Flash/high。** 便宜单价不保证便宜完成；Flash在这一输入上思考完上限仍无动作。Pro/low能形成有内容的逐项审查，包含Q1/Q2毛利率、现金流、GAAP/非GAAP、来源权威及反证检查，是可继续验证的候选，不是与Pro/high质量等价证明；两者下一步不同，且只一例、旧high并非同期随机对照。保留Flash在小范围资料选择/短任务的后续候选资格，复杂跨材料判断优先Pro；不继续为同一大包无限增加输出上限。接下去以真工具/真任务的总完成成本（含返工）选择profile。

当前产品增量仍为0份完整Dell报告；工程增量是用量可见、薄用途路由和重复context小修；研究资格新增2次真实模型证据，外源/Multi-Agent全覆盖/实时UI仍未完成。
