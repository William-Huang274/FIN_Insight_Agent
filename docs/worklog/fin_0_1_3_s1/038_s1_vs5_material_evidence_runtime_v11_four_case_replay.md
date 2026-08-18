# S1 VS5 Material Evidence Runtime v1.1 与四案真实回放

日期：2026-08-18

状态：`current_candidate_vertical_replay_proven / product_consumer_pending / natural_blueprint_scope_open / S1_not_qualified`

## 本轮目标

把 036 中只在 synthetic matrix 证明的材料集合合同接到当前 DELL／MU／NVDA／COST 已保存候选与金融对象上，并回答三个业务问题：

1. 当前候选 metadata 能否在不读取 qrel／答案的前提下表达“这段材料能支持什么角色、指标、产品和期间”；
2. 正式审阅窗能否先保护一项研究判断所需的整组材料，而不是简单截取单对象 top-K；
3. 确定性 fallback 在哪里能够解释请求，哪里必须停下等待自然 ResearchBlueprint，而不是靠扩充本体词表伪造泛化。

本轮为 0 network／0 generation model／0 learned vector／0 qrel or reference／0 hidden or holdout read。历史 COST R1／R2、旧 v1.0 合同和当前 Pack／Workbench 指针均未改写。

## 实现

- `src/retrieval/material_evidence_runtime.py`：新增统一 runtime seam，将 EvidenceRequest、narrative plan、shortlist feature 与 compiled object 投影为 v1.1 requirement plan 和 correlated candidate bindings。
- `src/retrieval/evidence_set_coverage.py`：保留 v1.0 默认兼容，新增 v1.1 schema、相关 binding、`single_binding／collective_axes`、错公司／请求无关候选排除和 selection-before-topK。
- `src/retrieval/retrieval_need.py`：把 period-only intent 判断变成可复用的公共确定性函数，避免年份比较短语被当成产品。
- `configs/retrieval/fin_ia_0_1_3_s1_material_evidence_runtime_policy_v1_0.json`：冻结 hard product、contextual topic、未分类主题、Evidence Role→material role 和角色绑定轴。
- `scripts/data_retrieval/run_s1_material_evidence_runtime_replay.py`：通用四案零调用 replay。VS4 从保存的完整 96 候选池先做材料 reservation，COST 复用已披露 valid-temporal R2 输入与保存结果；不加载资格 reference。
- `tests/test_s1_material_evidence_runtime_v11.py`：覆盖时间指令、v1.0 兼容、相关 binding、错实体／噪声、跨期组合、未分类 scope、collective axes 和反方角色不被主指标误杀。

## 回放暴露并关闭的最早问题

1. **长研究题被当成一个产品。** DELL 三个主题和 COST 三个主题包含客户集中、竞争、取消、营运资本、同店驱动和毛利压力等多个概念。把整句话写进 product axis 会要求一段材料逐字同时命中全部词，造成假失败。当前 fallback 只绑定已声明的硬产品概念；其余主题留下显式 Blueprint blocker。
2. **一段材料被要求同时承担表格和机制。** COST 毛利材料需要数值表和工资／损耗等解释，它们天然可能位于不同对象。`collective_axes` 允许二者共同覆盖非跨期组，但都仍只是 Candidate。
3. **先截 top20 再保材料。** DELL 营运资金反方已在完整 pool，却在普通 review 头之后。当前顺序改为完整候选池材料 reservation→有限审阅窗，避免由自身截断制造 typed gap。
4. **反方被主指标约束误杀。** 风险段能反驳毛利或现金结论，但不一定直接报告该指标。counter／context 现在不绑定 requested metric；这不会让其成为数字证据，S2 权威不变。

## 结果

| 案例 | 请求 | requirement | material-set complete | runtime-scope ready | 业务解释 |
|---|---:|---:|---:|---:|---|
| COST | 5 | 19 | 5/5 | 2/5 | 会员、同店与毛利复合主题需自然 Blueprint |
| DELL | 3 | 5 | 3/3 | 0/3 | 营运资本、发行人反方与上游约束均为复合研究范围 |
| MU | 4 | 6 | 4/4 | 4/4 | 当前请求范围可由已冻结 facet／role／hard product 解释 |
| NVDA | 6 | 10 | 6/6 | 6/6 | 当前请求范围可由同一确定性合同解释 |

全部请求 permutation stable；共 40／40 requirement 在当前已保存候选中可形成完整材料组。这里的 40／40 不是检索资格分数：没有读取 reference，也没有判定候选是否最终应晋升 Evidence。

active-baseline import graph 复证同时指出：新 seam 当前由通用 replay 与测试消费，尚未进入 Workbench 或动态 S1→S3 产品 import graph。因此本轮是“真实资产纵切回放”，不是“产品 Runtime 已集成”；下一切片必须先完成自然 Blueprint 范围，再接唯一产品消费者，不能把 replay runner 留成第二套主链。

公开结果为 `configs/retrieval/fin_ia_0_1_3_s1_material_evidence_runtime_replay_result_v1_1.json`，逐请求私有结果由公开摘要中的 path／SHA-256 绑定。

## 验证

- 新合同与相邻 retrieval／qualification 回归：`60 passed`；其中一次初始回归正确捕获 `retrieval_need.py` 冻结源码摘要漂移，已撤回该历史模块改动并在新 seam 内实现期间判断，COST R2 绑定摘要恢复不变；另增加 v1.0 selection 输出形状回归，防止 v1.1 receipt 字段污染旧摘要。
- 全仓：`657 passed`。
- `python -m compileall -q src scripts`：通过。
- active baseline：155 Python／8 frontend／16 Runtime resources／0 forbidden reference；同时确认新 seam 当前活动产品消费者为 0。
- repository secret scan：7,148 files／0 finding。
- 4 个 changed JSON／JSONL parse、四案 replay 重跑、`git diff --check`：通过；replay result digest 保持 `fd97dc27701af2c49355e869b4068d019679ac9db1462d445b6c8c45abfbd4ef`。

## 没有被证明

- DELL／COST 的自然 ResearchBlueprint material scope；
- COST request／reference qualified-human 决策；
- replacement blind valid／frozen／heterogeneous qualification；
- CandidateDecision、Evidence Gate、Pack Readiness、NumericFact／NumericRelation；
- S1 资格、完整 S1→S3 Agentic Research 或 release。

## 下一项

只实现自然 `ResearchBlueprint → MaterialEvidenceRequirementPlan v1.1` 消费 seam，并用当前四案保存请求做零调用／受控自然节点验证。该节点不得读取候选身份、qrel、reference 或答案 URL；未分类主题必须由 Blueprint 明确 material scope，不能继续扩充 DELL／COST 专用本体。随后再回放 EvidenceDecision／Gate 与 S2 权威，并另行处理人工 reference 与 replacement blind program。
