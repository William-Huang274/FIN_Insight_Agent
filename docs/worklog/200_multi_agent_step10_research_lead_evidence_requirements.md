# 200 Multi-agent Step 10 Research Lead Evidence Requirements

日期：2026-05-30
分支：`codex/api-model-call-architecture`
最近提交：`92148b1 Add multi-source SEC agent platform foundation`
状态：Step 10 schema / validator / diagnostic flag 已落地；真实 strict LLM run 待环境变量中的模型 key
关联文档：`188_multi_agent_architecture_execution_plan.md`、`199_multi_agent_185_186_replan_step9_data_view_gate.md`

## 问题

Step 10 的目标是让 Research Lead LLM 不只输出 `AgentActivationPlan`，还要能输出结构化 `EvidenceRequirementPlan`。该计划仍必须是业务证据需求，不能直接决定物理索引、DuckDB path、BM25 path 或 tool-call arguments。

## 已完成

代码：

- `src/sec_agent/research_lead_llm.py`
  - `ResearchLeadLLMConfig` 新增 `require_evidence_requirements`。
  - 支持模型输出两种格式：
    - 旧格式：单个 `AgentActivationPlan`。
    - 新格式：`{"activation_plan": ..., "evidence_requirement_plan": ...}`。
  - EvidenceRequirementPlan 先过 raw source/operator mismatch 预校验，再进入 `build_multi_agent_evidence_requirement_plan()`。
  - 当 `RESEARCH_LEAD_REQUIRE_EVIDENCE_REQUIREMENTS=1` 时，缺失或无效 EvidenceRequirementPlan 会触发 repair / fail closed。
  - 缺省兼容旧 activation-only gate；若 graph state 有 `query_contract`，可使用 deterministic compiler fallback，并在 `routing_trace.evidence_requirements_source` 标记。
- `src/sec_agent/langgraph_orchestrator.py`
  - Research Lead route result 若包含 `evidence_requirement_plan`，写入 graph state。
  - `compile_evidence_requirements` 优先复用上游 Lead evidence plan，再编译 retrieval plan。
- `scripts/eval_multi_agent_research_lead_activation.py`
  - 新增 `--require-evidence-requirements`。
  - 诊断输出新增 evidence requirement validation summary。
- `tests/test_multi_agent_research_lead_llm.py`
  - 新增 activation + EvidenceRequirementPlan 通过测试。
  - 新增 invalid operator owner repair 测试。

## 验证

已通过：

```text
pytest tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py -q
21 passed

python -m compileall -q src/sec_agent/research_lead_llm.py src/sec_agent/multi_agent_runtime.py src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent_research_lead_activation.py
```

## 未执行

- 未执行真实 DeepSeek strict run。
- 未把用户聊天中出现过的 key 写入环境、文档、fixture 或脚本。

后续真实诊断应只读取环境变量，例如：

```text
python scripts/eval_multi_agent_research_lead_activation.py --strict --require-evidence-requirements
```

## 下一步

进入 Step 11：

- Coverage / Reflection 输入应包含 EvidenceRequirementPlan、coverage matrix、source gaps 和 tool ledger summary。
- `second_pass_requests` 必须绑定 requirement id / source family gap。
- Second-pass 仍回到 deterministic compiler，不能由 Reflection 直接调用工具。
