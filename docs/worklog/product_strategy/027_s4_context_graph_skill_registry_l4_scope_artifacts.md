# 027 S4 Context / Graph / Skill Registry L4 Scope Artifacts

## Prompt

继续推进 R53-R60 release slices，在 S3 retrieval / evidence spine 已经达到 `L4_scope_pass` 后，落地 S4 Context / Graph / Skill Registry。

## Decision

S4 的职责不是写 Workpaper 或 Memo，而是把 Research Lead 和 specialists 需要消费的 GraphPack、SkillPack、MemoryPack、ContextInjectionPlan 变成可版本化、可审计、可 replay 的 SQL-final 能力资产。S4 必须读取 S3 selected evidence refs，不能绕过 S3 直接拿 raw retrieval candidates。

本轮按以下边界实现：

- GraphPack registry 记录 graph pack version、scope、authority boundary、tenant status 和 source summary；
- SkillPack registry 记录 skill prompt digest、适用角色、输入/输出 contract、forbidden behavior 和 eval hooks；
- MemoryPack registry 记录 memory tier、provenance、TTL、staleness、permission、promotion status；
- ContextEngine lifecycle 覆盖 resolve/select/compress/inject/write/consolidate/invalidate；
- ContextCompressionArtifact 对 exact company facts 只保留 evidence ref，不做摘要改写；
- Research Lead 和 specialists 必须声明 consumed graph / skill / memory / evidence pack refs。

## Work Completed

新增：

- `src/sec_agent/r53_r60_context_graph_skill_registry.py`
- `scripts/engineering/build_r53_r60_s4_context_graph_skill_registry.py`
- `tests/test_r53_r60_context_graph_skill_registry.py`
- `configs/r53_r60/s4_context_graph_skill_registry_schema_v0_1.json`
- `data/manifests/r53_r60_s4_context_graph_skill_registry_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s4_context_graph_skill_registry_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_s4_context_graph_skill_registry_l4_scope_pass.zh-CN.md`

更新：

- `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`
- `docs/worklog/00_internal_master_checklist.md`
- `docs/worklog/README.md`

真实构建结果：

- GraphPack registry：`6`
- SkillPack registry：`16`
- MemoryPack registry：`6`
- ContextInjectionPlan：`4`
- Context lifecycle events：`7`
- Context pack selections：`61`
- Dropped context refs：`34`
- S4 gates：`12 pass / 0 fail`
- Release decision：`S4_L4_scope_pass`
- Next slice：`S5`

## Verification

已运行：

- `python -m py_compile src\sec_agent\r53_r60_context_graph_skill_registry.py scripts\engineering\build_r53_r60_s4_context_graph_skill_registry.py`
- `python -m pytest tests\test_r53_r60_context_graph_skill_registry.py -q`
- `python scripts\engineering\build_r53_r60_s4_context_graph_skill_registry.py --root .`

后续 closeout 前还需与 S0-S3 regression、`git diff --check`、secret scan 一起跑。

## Notes

本轮修复两个实现问题：

- 测试环境 root 是临时目录，skill prompt 文件在真实仓库目录，不能强行按测试 root 做相对路径；已改为 root 内相对路径、root 外绝对路径的稳定记录方式。
- industry/supply-chain actor 初版证据选择只看 `fact_domain`，而 S3 selected evidence payload 中主要可用的是 `support_surface`；已补充 customer deployment、macro industry、channel offer、capital market surface 的识别。

S4 边界：本轮不调用 LLM、不生成 Workpaper、不生成 Memo、不证明最终研究质量。S5 才负责 Workpaper / Lead Review workflow。
