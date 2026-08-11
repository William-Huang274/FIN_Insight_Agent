# Project OS
Project OS 是跨任务恢复当前事实的最小控制面，不是无限增长的工作日志。

## 启动必读

1. `current_context_pack.zh-CN.md`
2. `senior_assistant_collaboration_policy.zh-CN.md`
3. `capability_status_ledger.jsonl`
4. `root_cause_issue_ledger.jsonl`

前两项给人读；后两项是当前机器投影。完整旧账本保存在：

`archive/versions/fin_0_1_3_prebaseline/docs/project_os/`

## 长期规则与注册表

- `full_chain_run_policy.zh-CN.md`：昂贵或全链运行边界。
- `full_chain_preflight_checklist.json`：全链预检。
- `done_definition_l4_scope_pass.zh-CN.md`：scope pass 定义。
- `token_budget_policy.zh-CN.md`：信息与调用预算。
- `STRICT_SCHEMA_TRANSPORT_API_HANDOFF.zh-CN.md`：未来新 Provider 的 transport 交接。
- `external_pattern_registry.jsonl` 与工程学习/抽取账本：外部 Agent/RAG 模式。
- `financial_research_method_registry.jsonl` 与研究学习/抽取账本：金融研究方法。

## 维护约束

- `current_context_pack` 只保留当前事实、边界、阻断和下一步；历史段落必须归档。
- capability/root-cause 主账只保存当前投影；历史不可变账本归档后通过重定向索引定位。
- 失败留在所属 S 阶段，不自动创建新版本。
- 新证据推翻旧计划时必须及时向 Owner 说明并更新规范，不能静默照做。
- 任何 historical proof、candidate、fixture 或 archived report 都不能直接晋升为当前产品能力。
