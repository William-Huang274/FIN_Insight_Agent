# 113｜首次 protected report remap 长度失败与 replacement 执行门

## 首次 live 的真实结果

- 提交：`a7be53cc`；run：`FIN_0_1_3_S3_DELL_MULTI_AGENT_PROTECTED_REPORT_REMAP_20260821`。
- 权限执行没有漂移：一个 Writer logical node、一个 contract attempt、零 analysis／continuation／upstream Agent／repair／Evaluator／network／Candidate promotion。
- DeepSeek 实际返回了唯一 `submit_protected_report_draft` Tool Call 和非空 `tool_call_id`，不是纯文本逃逸，也不是网络失败。
- 请求为 41,219 prompt tokens；响应达到 7,000 completion tokens 后以 `finish_reason=length` 结束。arguments 已覆盖 executive thesis、六个 section、六个 remaining gap，并写到第二个 what-would-change 中途，因此不是合法 JSON，也没有形成可渲染报告。
- 失败已完整保存在 capture、private terminal result 与 public result；旧报告仍为 L1 fail，新报告不存在。

## 最早责任层

本轮同时暴露两个项目内问题。

1. `TokenBudgetBasis` 低估了嵌套 protected report 的完整输出体积。7,000 不是成本优化，而是不能完成必需产物的错误预算。
2. runner 把 Tool Call envelope 提取与 arguments JSON 解析耦合。第一次解析已经知道 JSON 不完整；为取得 `tool_call_id` 又调用同一解析器，导致明明存在可反馈的 call ID，却被误判为不可修复。

它们属于 S0 Harness／S3 终端合同执行，不属于 S1 数据、S2 事实、Specialist 研究能力或 DeepSeek 纯粹不遵循指令。

## replacement 结构修复

1. envelope 先独立验证 call count、tool name 与 call ID，再解析 arguments；`finish_reason=length` 形成专门的 output-budget failure code。
2. 精确合同反馈允许模型在同一 logical node 内重新完整交卷；缺 call ID、错 tool name 或 transport failure 仍立即终止。
3. remap 形状进一步收敛为一个 executive clause、每个源 section 一个 clause，并要求每段只选择最少必要 lineage，禁止把整个 catalog 重复装入每段。
4. 新 profile 将 `max_tokens` 从 7,000 调整为 12,000。依据是首次真实输出在必需形状约四分之三处截断，并需保留修正余量；成本和延迟不是缩短必需输出的理由。
5. failure materialization 即使没有 draft，也保存 immutable source report digest。

## replacement 边界

首次 v1.0 authority 和 run 已终止，不能恢复、复用或改写。v1.1 决策显式绑定首次 authority、public failure、private terminal result、原始报告、typed authority、新 profile 和修复后实现 SHA。它只允许一个新的 Writer-only replacement logical node、最多两个合同 attempts，仍为零上游研究权限。

自然 replacement 成功后仍须独立 L1、八维内容质量、同输入语义保真与 qualified-human 验收；S1、S3、泛化、Workbench 和 release 不会因此自动通过。

## 提交前验证

- scope／runner／report／Project OS 定向：`76 passed`；
- 全仓：`953 passed`，仅 2 条既有 SWIG deprecation warnings；
- active baseline：`189 Python／8 frontend／5 detectors／27 resources／0 forbidden`；
- archive redirect：6,059；机器可读资产：806 JSON／8 JSONL／915 records；secret scan：7,539 files／0 finding；compile／diff check均通过。
