# R57 Graph / Skill / Memory Pack Operating Model

日期：2026-06-28

## Prompt

用户要求先不要进入小阶段实现，而是先想清楚 skill 和图谱的 full picture 与最终形态：skill 和图谱应当可插拔，企业内部可以按自己的业务经验和需求快速替换；同时参考 Hermes 的 self-improving skills / memory 思路，但需要明确专业性如何做好和把关。

## Decision

本轮将这部分单独列为 R57，而不是合并进 R56。

原因：

- R56 是 runtime stack：LangGraph、RuntimeFacade、ToolGateway、ContextEngine、durable execution、trace/export。
- R57 是能力资产模型：GraphPack、SkillPack、MemoryPack 如何注册、选择、注入、评测、审批、替换。
- 如果把 R57 塞进 R56，后续会把 skill / graph 误认为 prompt 或 context injection 细节，而不是企业可维护资产。

R57 同时修正了原 R53-R60 总控中对 R57 的旧定义：不再只是 `Memory & Context Lifecycle`，而是 `Graph / Skill / Memory Pack Operating Model`。

## Work Completed

新增技术文档：

- `docs/architecture/agent_graph_vnext/32_r57_graph_skill_memory_pack_operating_model.zh-CN.md`

更新索引和总控：

- `docs/architecture/agent_graph_vnext/README.zh-CN.md`
- `docs/architecture/agent_graph_vnext/27_r53_r60_engineering_execution_program.zh-CN.md`
- `docs/worklog/00_internal_master_checklist.md`
- `docs/worklog/README.md`

## Key Architecture

R57 将能力资产拆成三类：

```text
GraphPack  决定“世界如何被结构化”
SkillPack  决定“专家如何使用这些结构化世界做判断”
MemoryPack 决定“机构、团队、用户偏好和历史经验如何影响任务规划”
```

核心约束：

- `GraphPack` 不是单纯 nodes / edges，而是 graph schema、source adapters、parser、authority policy、query API、allowed/forbidden claims、eval suite 和 migration rule 的完整能力包。
- `SkillPack` 不再只是 markdown prompt，而应有 role、required graph capabilities、input/output contract、allowed tools、forbidden claims、model route、context budget 和 behavior eval。
- `MemoryPack` 不是事实库，只能影响规划、偏好、经验提醒和上下文选择，不能绕过 evidence authority。
- Agent 可以提出 `SkillPatch` / `GraphPatch` / `MemoryPatch`，但生产环境必须走 staging、eval、human approval、canary、promotion，不允许未验证自改 active production。

## Professionalism Guard

专业性不靠模型自由发挥，而靠：

- domain ontology；
- industry playbook；
- graph authority；
- claim boundary；
- behavior eval；
- human approval；
- tenant-specific overlay。

R57 明确后续 eval 不能只检查 skill prompt 是否注入，而要检查实际行为：

- Research Lead 是否选对 GraphPack；
- Specialist 是否正确消费 required GraphPack；
- 是否把 proxy 冒充 exact；
- 是否错过 retrievable gap；
- 是否按行业 playbook 组织分析；
- Memo 是否基于 MemoLogicPlan，而不是拼 ClaimCard；
- Graph edge 是否按 authority 正确进入 thesis / caveat / visualization。

## Result

R57 目前是 framework draft / living technical registry，未进入代码实现。

后续实现需求草案：

- `R57-D01-graph-capability-registry`
- `R57-D02-skillpack-registry`
- `R57-D03-memorypack-registry`
- `R57-D04-lead-graph-skill-selector`
- `R57-D05-specialist-required-pack-gate`
- `R57-D06-learning-patch-lifecycle`
- `R57-D07-behavior-eval-suite`
- `R57-D08-tenant-overlay-contract`

## 2026-06-28 Memory / Context Lifecycle Supplement

用户提醒旧 R57 还包含 `Memory & Context Lifecycle` 的具体内容，不能因为 R57 被提升为 Graph / Skill / Memory Pack Operating Model 就丢掉 memory 分层和 ContextEngine 生命周期。

本轮已补进 `32_r57_graph_skill_memory_pack_operating_model.zh-CN.md`：

- memory 分层：
  - `NodeScratchMemory`
  - `RunMemory`
  - `ProjectMemory`
  - `CompanyMemory`
  - `WatchlistMemory`
  - `TeamExperienceMemory`
  - `OrgPrivateMemory`
  - `GlobalPlaybookMemory`
- memory metadata contract：
  - provenance；
  - authority；
  - TTL；
  - staleness；
  - supersession；
  - tenant / permission；
  - promotion gate。
- ContextEngine lifecycle：
  - `resolve`
  - `select`
  - `compress`
  - `inject`
  - `write`
  - `consolidate`
  - `invalidate`
- 每次上下文注入必须生成可 replay 的 `ContextInjectionPlan`。
- 所有 node 输出只能先写 `MemoryCandidate`，不能直接写 active long-term memory。

因此 R57 后续需求扩展为 D01-D10，新增：

- `R57-D09-contextengine-lifecycle-contract`
- `R57-D10-memory-promotion-invalidation-gates`

## 2026-06-28 Context Compression Supplement

用户确认 R57 需要覆盖上下文压缩办法，但检索召回策略先放到 R58。已将 R57 的 `ContextEngine.compress()` 从原则补成正式压缩合同：

- 新增 `Context Compression Policy`：
  - `must_keep_exact`
  - `reference_only`
  - `extractive_compress`
  - `abstractive_handoff`
  - `structured_pack_compress`
  - `memory_hint`
  - `drop`
- 明确 exact facts 只能引用 row / claim / evidence ref，不能被摘要替代。
- 新增 `ContextCompressionArtifact`：
  - 记录 source refs、preserved refs、dropped refs、dropped reasons、compression method、authority / permission / staleness check 和 hash。
- `ContextInjectionPlan` 新增 `compression_artifact_ids`，确保每次注入都能 replay 到具体压缩版本。
- 新增 compression quality gate：
  - numeric / unit / period / product / issuer / citation preservation；
  - authority boundary preservation；
  - forbidden claim / bounded gap / commercial gap preservation；
  - permission / stale context check；
  - compression hallucination verifier。
- 参考方向记录为 Codex / OpenAI-style compaction、Claude Code-style focused compact、Claude memory / file memory、LLMLingua / LongLLMLingua-style prompt compression、GraphRAG / RAPTOR-style hierarchy summary；其中 retrieval / rerank / chunk expansion 的实现细节明确留给 R58。

因此 R57 后续需求扩展为 D01-D13，新增：

- `R57-D11-context-compression-policy`
- `R57-D12-context-compression-artifact`
- `R57-D13-compression-quality-gates`

## Verification

本轮为 docs-only framework update。未运行 runtime / unit tests。

待收尾前运行：

- `git diff --check`
- 文档 secret scan
