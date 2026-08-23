# FIN 0.1.3 S3：动态多 Agent 入口的图容量与角色隔离

日期：2026-08-23
状态：`six-role current materialization proven / dynamic behavior not yet proven`

## 1. 为什么旧入口不能直接运行

把 current DELL 48 条 reviewed Evidence 接到旧 Multi-Agent Preview 时，模型尚未调用就被 `research_context_graph_capacity_exceeded` 拦截。审计显示 `counterevidence` 单元自然形成 17 条关系边，而历史模型视图上限为 16。多出的不是一条新事实，而是同一批 Evidence 对多个近义关系方向的重复表达。

这属于 Harness 的上下文选择缺口，不属于 DeepSeek、S1 检索失败或公开资料缺失。把上限从 16 随手调大只会推迟下一次溢出，也会把更多重复图语义送进模型。

## 2. 本次有界修复

- 完整 reviewed Evidence Pack、NumericFact 和关系权威保持不变；
- 图只作为角色导航和上下文视图，按命题主槽位、补充槽位、facet、来源权威和主体覆盖做确定性选择；
- 被省略的边和实体生成不可变 `selection_receipt`，但不作为研究事实暴露给模型；
- `Supply Relationship` 与 `Counterevidence` 虽共享 canonical cell，但最终再按各自 Evidence refs 和职责槽位投影，禁止互相看到无关图假设；
- 输入未超限时仍保持原 v1.0 输出和 digest，避免无理由改写历史输入。

## 3. current 六角色真实材料化结果

当前 Runtime 以 0 模型、0 网络运行 12 条角色对齐 EvidenceRequest：12 个检索 lane 中 11 个非空，得到 29 个唯一叙事候选、192 个混合候选选择、85 个 NumericFact、25 个 resolved typed fact 和 25 个 typed gap。Dense 路线使用现有 `Qwen3 Embedding 0.6B CUDA/FP16`，没有回退 CPU。

六个专业角色均获得非空 current authority；所有角色图的 outside Evidence ref 为 0。Supply 得到 12 条 Evidence／10 条角色图边，Counterevidence 得到 10 条 Evidence／10 条角色图边，两者不再共享彼此的全部关系面。

## 4. 这一步证明了什么、没证明什么

已证明：current S1/S2 能在当前 DELL Pack 上材料化六个角色；图容量有界且可审计；角色图不会扩大权威或跨职责串线；排列变化结果稳定。

尚未证明：六个角色会自行选工具、接收 FeedbackReceipt、改变计划或停止；Lead 会解决冲突和回派补证；任何多 Agent workpaper、完整报告、Writer、MU/NVDA、异质留出或 S3 验收。

因此下一项不是运行旧 `run_s3_dynamic_five_cell_live.py` 或恢复历史 Preview attempt，而是建立 current dynamic multi-agent loop：每个专业角色拥有独立 Session，在自己职责范围调用 current S1/S2，反思并提交工作底稿；Lead 再消费独立工作底稿、冲突和 gap，决定局部返工或停止。

## 5. 复证入口

- 定向测试 `124 passed`；全仓 `1107 passed`，仅两条既有 SWIG deprecation warning；`compileall` 与 `git diff --check` 通过；
- active baseline 为 `207 Python／8 frontend／5 Runtime detector／28 Runtime resource／0 forbidden`；secret scan 为 `7,732 files／0 finding`；
- 公共零调用结果：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_entry_zero_call_result_v1_0.json`；
- 新根因：`RC-S3-065-current-multi-agent-graph-context-all-in-projection`。
