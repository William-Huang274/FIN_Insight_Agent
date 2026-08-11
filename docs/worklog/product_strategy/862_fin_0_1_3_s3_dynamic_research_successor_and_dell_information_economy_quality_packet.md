# 862 — FIN 0.1.3 S3 dynamic-research successor 与 DELL 信息经济质量包

日期：2026-08-11
阶段：S3 研究规划、补证回流与内容质量
结论：`zero_call_successor_engineering_pass / formal_S3_blocked`

## 为什么做

入口审计已证明既有 S3-01～05 组件分别存在，但它们没有形成产品闭环。若继续分别补 Prompt、字段或固定九次调用，只会重复 FIN 0.1.1／0.1.2 的局部修补。当前任务因此限定为：复用既有资产，建立动态 cell、EvidenceRequest、证据观察、受影响重裁决、机制／WWC 和内容质量包之间的连接层；同时用真实 DELL same-input 候选检验“报告是否把证据转化成决策”，不调用模型或网络。

## 实现了什么

- 新增 `s3_dynamic_research_successor.py`，把三案编译成 `38` 个有业务角色的动态 cell；没有固定 Agent 调用次数。
- 从现有 gap 中选择 `5` 个 material、可检索 repair request，全部复用 canonical `EvidenceRequestCompiler`，且在本 scope 中保持 `shadow / not_admitted / 1 tool-call ceiling / no fallback`。
- accepted observation 只使目标与传递依赖进入 `needs_readjudication`；rejected／typed gap 不晋升 Evidence。changed Judgment 必须完整覆盖 affected-set 并引用新 Evidence。
- 编译 `9` 条 mechanism chain、`13` 个 WWC；未绑定数值阈值明确返回 `cannot_operationalize_numeric_threshold_with_current_evidence`。
- 新增信息经济 evaluator：在不公开保存 DELL 原文的前提下，记录 section／point 数、引用指纹、重复、摘要过载、决策／边界密度、hard failure 和 quality finding。
- 物化三案 successor program 与最小零调用实现结果，全部 digest-bound。

## DELL 真实业务观察

同一份 fixed Evidence Pack 下，baseline 有 `42` 个观点，Agent 有 `30` 个。这个变化不是简单少写：它说明 Agent 已经开始筛选和综合证据，而不是逐条搬运。但报告仍有三类产品问题：

1. 两个 executive points 塞入过多事实和判断，用户难以看出最重要的决策结论；
2. counter-thesis 与 what-would-change 仍有一组实质重复；
3. decision-marker point ratio 只有 `0.4333`，不少段落仍是在说明材料而不是回答“所以应如何判断”。

此外，历史候选的两条数值权威 L1 失败继续保留。紧凑和综合增益不能覆盖事实引用失败，所以没有执行八维正式评分，也没有把历史 terminal 改标。

## 验证

- focused successor：`12 passed`；
- 既有 S3 五组件＋successor：`47 passed`；
- model／provider／network／source／retry／business promotion：`0/0/0/0/0/0`；
- mutation：cross-case、非法 admission、部分重裁决、无新证据改判、未绑定数值阈值、非法 Evidence 晋升、digest drift 均 fail closed；
- private raw DELL prose 未进入公开 successor program，只保存不可逆摘要、引用集合和 digest。

## 边界与下一步

本轮只证明 connector Runtime 和真实候选诊断可以工作。RC-P36-157 外源覆盖、RC-P36-165 估值与 issuer-specific supply 语义、RC-P36-172 WWC／机制／重复／决策密度继续阻断 formal S3。post-repair report、paired gain、qualified-human acceptance、Owner 和 release 均为 false。

下一项固定为 `S3_MINIMAL_NATURAL_PLANNER_OR_REPAIR_CANARY_NECESSITY_VALUE_COST_RISK_ZERO_CALL_DECISION`。先判断一次最小自然 planner／repair canary 能否带来足够信息价值；只有单独授权后才可执行，不能从本次 engineering pass 自动进入完整 DeepSeek 报告 live。

## 主要证据

- `src/sec_agent/s3_dynamic_research_successor.py`
- `tests/contract/test_fin_0_1_3_s3_dynamic_research_successor.py`
- `configs/releases/fin_ia_0_1_3_s3_dynamic_research_successor_program_v1_0.json`
- `configs/releases/fin_ia_0_1_3_s3_dynamic_research_successor_minimum_zero_call_implementation_and_proof_v1_0.json`
