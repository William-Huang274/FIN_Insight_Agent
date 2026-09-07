# 067 DELL 五单元 R5 跨单元合同泄漏与结构修复

日期：2026-08-17

## 结论

R5 不是 DeepSeek 不遵循合同，也不是需求研究内容先被金融门拒绝。项目把只属于“价值获取／利润”单元的 ClaimAuthority、ClaimRelation 和 QualitativeFact 字段复制进了“需求真实性”单元的提交 Prompt 与严格 Tool Schema。DeepSeek 从服务端明确列出的合法菜单中选择了三条利润关系；随后本地 Validator 又错误地假设需求单元一定有 `allowed_qualitative_fact_refs`，触发未捕获 `KeyError`，使进程在生成 terminal result 前退出。

R5 权限已消费，不能复用同一 Run／Attempt ID。两次真实调用、四份 capture 和原始 Tool Call 保持不可变；模型输出不 salvage、不进入 Evidence、Artifact、Workbench 或任何业务结论。

## R5 实际发生了什么

1. Demand analysis 正常完成：HTTP 200、`finish_reason=stop`，总计 6,982 tokens。
2. Demand submission 正常完成：HTTP 200、`finish_reason=tool_calls`，一个 `submit_research_judgment` Tool Call，总计 10,424 tokens。
3. 旧 Demand Tool 错误暴露了 `claim_scope`、`financial_scope`、`causal_bridge_authority`、`claim_relations`、`qualitative_fact_refs`，并列出：
   - `CR::DELL::COMPANY_MARGIN_OBSERVATION`
   - `CR::DELL::HISTORICAL_MIX_PRESSURE`
   - `CR::DELL::PROFIT_BRIDGE_GAP`
4. DeepSeek 只选择了这个错误 Tool 菜单中存在的 alias；因此主因不能记成模型伪造未知 ref 或违反服务端形状合同。
5. 旧本地代码在需求单元索引不存在字段时崩溃。其他四个单元、跨单元综合和报告均未执行；0 retry／fallback／外源网络／协议切换。

R5 后补的公开失败终态为 `e8e13386...b20b4fc`，明确记录原 runner 没有生成 private full result，且后补记录不冒充原运行自然完成。

## 结构修复

1. `compile_current_research_messages` 按本次选中的 cell 资格编译合同。只有 `CELL::value_capture` 看见 ClaimAuthority／ClaimRelation；其他四单元看不到相关字段、QF catalog、规则或 relation alias。
2. `bounded_finance_loop` 统一使用 cell-scoped Judgment contract。普通 loop 与 five-cell submission 不再分别维护两种投影逻辑。
3. 混合资格 cell 不允许塞进同一个提交表面。五单元 runner 必须逐 cell 编译 Tool，避免一个全局 union 菜单污染其他单元。
4. Validator 按 cell 计算精确字段集合；非资格 cell 即使提交服务端旧菜单中的利润字段也 fail closed。
5. runner 对未分类项目异常先保留已完成 capture，再物化 `cell_unexpected_project_exception` 终态；以后不会因一个 KeyError 丢失整次运行的 terminal result。
6. 没有改变 Evidence、NumericFact、ClaimRelation 的金融含义，没有让 Harness 替模型写判断，也没有放宽 `RC-S2-004` 的产品到利润桥。

## 验证

- Demand 正向：基础字段通过，提交 Prompt 和 Tool 均不含 Value-only 字段或 alias；
- Value 正向：五个 Claim／QF 字段和合法 relation alias 仍完整存在；
- R5 形状 mutation：把 Value-only 字段和三条关系塞进 Demand，以 `research_consumer_output_cell_fields_invalid` 拒绝；
- 异常 mutation：Validator 抛出 KeyError 时 runner 继续其余 cell，并生成公开／私有 terminal result；
- 同一目标测试两个 fresh process：`138 passed`＋`138 passed`；
- 全仓：`468 passed`；
- compileall：pass；
- active baseline：`135 Python／8 frontend／11 Runtime resources／0 forbidden reference`；
- secret scan：`6,821／0`；
- model／Provider／external network／candidate promotion：`0／0／0／0`。

正式零调用结果 digest 为 `4537d7e1...1bf24`。这只关闭跨单元合同泄漏和 terminal materialization 的工程门。

## 下一步边界

下一步不是复用 R5，也不是直接宣称 DELL 五单元接近通过。应另建一次 fresh R6 范围决策，仍复用 R4 已证明的 Planner 与 current S1/S2，但重新执行五个 analysis、五个 submission 和两次 synthesis；新 Run／Attempt ID、0 retry、0 新 Evidence、0 外源网络。

R6 成功后仍须做金融 L1、逐单元内容、跨单元综合、八维绝对质量、paired gain 和 qualified-human 内容验收。只有 DELL 完成这些门，才进入 MU／NVDA 与异质留出案例泛化。若 R6 出现新的跨单元 L1 或要求改变模型／数据采购／产品范围，应回到 Owner 决策，不继续逐字段无限修复。
