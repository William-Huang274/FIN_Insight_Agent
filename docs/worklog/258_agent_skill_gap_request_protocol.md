# 258 Agent Skill Gap Request Protocol

日期：2026-06-07

## 问题

扩容到 `603` 家公司后，A6 测试不能只断言答案里是否出现新增公司。更关键的问题是：当用户问 NVIDIA 基本面、行业传导或供应链时，Research Lead / Universe / Specialist 是否能判断这个问题可能需要上下游、peer、市场和行业上下文，并且知道当前 RAG / catalog 里哪些公司和 source family 可用。

如果只靠硬断言，容易把模型变成规则执行器；如果只靠自由提示，Specialist 又可能越权扩展 scope 或把缺证据写成结论。因此需要把“专业判断”写进 skill，把“可请求的补证据缺口”写进结构化合同，再让规则只做权限、证据边界和防幻觉约束。

## 决策

- Research Lead / Universe 负责 scope decision：识别问题是否需要 supply chain、peer、customer/supplier、market/industry context，并在 bounded catalog 内选择候选公司和 source families。
- Specialist 不直接调用工具、不私自扩大 universe；当它发现缺少指标、source family、公司 scope、关系确认、market field、industry context 或 counterevidence test 时，输出结构化 `evidence_gap_requests`。
- Coverage Reflection / Judgment / Memo / Verifier / Renderer 必须保留这些 gap requests：未解决的 material/blocking gap 只能作为限制、下一步证据或 repair route，不能被写成强结论。
- 规则层继续做硬边界：source family claim scope、tool ownership、exact-value authority、relationship/market/industry context-only 语义和 secret/artifact 安全。

## 完成

- 新增 shared skill 的 `evidence_gap_requests` 协议，定义 request type、owner agent、tickers、metric families、source family、blocking level、bounded-answer 标记和 reason。
- 优化 Research Lead skill，加入 professional scoping heuristics、`scope_decision` 和 NVIDIA / AI supply-chain 风格的候选 lens。
- 优化 Universe / Relationship skill，要求先读 bounded catalog / source inventory，再输出 included/excluded rationale、coverage awareness 和 budget discipline。
- 优化 Fundamental、Market、Industry/Supply-Chain、Risk Specialist skill：允许输出结构化 gap request，但禁止自行调用工具或把 context-only source 写成 reported financial fact。
- 优化 Coverage Reflection、Judgment Aggregator、Memo Writer、Verifier、Renderer skill：保留并路由 specialist gap requests，未解决时降级为 bounded answer / limitations / repair route。
- 扩展 `SpecialistMemolet` runtime contract：`normalize_specialist_memolet`、`validate_specialist_memolet`、`aggregate_specialist_judgment_plan` 和 `build_multi_agent_memo_draft` 都保留 `evidence_gap_requests`。
- Specialist LLM system/repair prompt 更新为接受 `evidence_gap_requests` 字段。

## 验证

- `python -m py_compile src/sec_agent/multi_agent_contracts.py src/sec_agent/specialist_llm.py src/sec_agent/research_skills.py`
- `python -m pytest tests/test_research_skills.py tests/test_multi_agent_contracts.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_agent_registry.py -q`
  - 结果：`84 passed`

## 未运行

- 本轮没有跑真实 DeepSeek A6 smoke/main，也没有消耗 provider token。
- 本轮只完成 skill/runtime/test 合同，不声明模型已经能稳定做 603-company 自主 scope selection。
- 本轮没有把任何 API key、密码或云端临时凭据写入文件。

## 后续

- 设计 A6 scope-decision / gap-escalation 用例：例如 NVIDIA 基本面、AI infra capex readthrough、semiconductor supply chain、market reaction + fundamentals、industry context + exact metric 混合问题。
- 在 Workbench A6 runner 下记录每个 case 的 `scope_decision`、candidate universe、selected source families、`evidence_gap_requests`、token/runtime/trace 和最终 memo quality。
- 如果真实 A6 中 gap requests 频繁出现但没有自动回流，需要把 blocking/material request 编译成 Coverage Reflection / Universe second-pass 的 deterministic route，再进入下一轮 evidence operators。
