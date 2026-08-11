# 197 Multi-agent 188 Design Digest Correction

日期：2026-05-30
分支：`codex/api-model-call-architecture`
最近提交：`92148b1 Add multi-source SEC agent platform foundation`
状态：188 已补充 185/186 细化设计的落地映射
关联文档：`185_multi_agent_investment_research_framework_draft.md`、`186_multi_agent_tool_data_access_matrix_draft.md`、`188_multi_agent_architecture_execution_plan.md`

## 问题

用户指出 188 虽然已经有 Step11+ 的顺序和门控，但对 185/186 中 multi-agent 的具体细化做法消化不够，尤其是：

- 185 的 role-specific skill 设计。
- 186 的 agent 权限矩阵如何落地。
- 工具和数据源归属如何约束 agent 输入、输出和 claim scope。

这个判断成立。此前 188 偏执行步骤和 gate，对这些细节只分散提到，没有形成可直接执行的落地矩阵。

## 已修改

更新：

- `docs/worklog/188_multi_agent_architecture_execution_plan.md`

新增章节：

- `185/186 落地映射补充`
  - `A. Role-specific Skill 落地矩阵`
  - `B. 186 Agent 权限矩阵到代码的映射`
  - `C. 工具和数据源归属落地矩阵`
  - `D. 185 主链路到 LangGraph 节点的映射`

同步修正：

- Step 8 不再笼统写“Specialist skill 先不拆细”，改为：fake/parser gate 可先用短 role instruction；进入真实 Specialist LLM diagnostic 前必须拆成正式 `fundamental_analysis`、`market_valuation_analysis`、`risk_counterevidence` prompt 文件。
- 测评规则新增 `185/186 Digest Gate`，要求每次新增 agent/tool/source/skill/LLM route 前检查 registry、skill、source ownership、schema repair、fail-closed 和 Workbench trace。
- 产物落点新增 `multi_agent_contracts.py`、`research_lead_llm.py`、`specialist_llm.py`。

## 当前结论

188 现在不仅说明“下一步做什么”，也明确了“185/186 的设计如何落到代码和 gate”：

- Role-specific skill 必须对应 prompt 文件 / loader / registry skill id / output contract。
- 186 权限矩阵必须映射到 `agent_registry` 字段和 validator/runtime gate。
- 每个工具/数据源必须有 owner operator、downstream data view、allowed claim scope、禁止用法和 runtime gate。

## 验证

本次为文档修正，未改运行代码，未运行模型。

已执行：

```text
git diff --check
credential-pattern scan on 188 / 197 / README / master checklist
```

结果：`git diff --check` 通过；敏感凭据模式扫描无命中。

## 安全说明

- 未使用或写入外部模型凭据。
- 未写入私有路径、凭据或 raw evidence。
