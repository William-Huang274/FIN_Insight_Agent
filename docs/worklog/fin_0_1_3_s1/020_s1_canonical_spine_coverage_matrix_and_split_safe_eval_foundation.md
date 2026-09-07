# 020 S1 canonical spine、覆盖矩阵与 split-safe 评测基础

日期：2026-08-17

状态：`program_foundation_engineering_pass / VS1_runtime_integration_pending / S1_qualification_false`

## Owner 要求

Owner 要求先建立 canonical spine、A–J 覆盖矩阵和 S1 独立评测资产，同时要求高级助手主动审视项目方向；必要时参考成熟 RAG／Harness，不得在需求不成熟或不完整时静默照做。

## 本轮独立判断与更正

1. **canonical spine 只能是薄控制面，不能成为一条巨型物理流水线。** 正文／表格对象、SQL `NumericFact`、关系图、official／external source 必须保留并行 data plane。统一的是 identity、period、locator、schema version、payload digest、lineage、decision state 与 consumer binding。
2. **原 spine 缺少 `CandidateRanking`。** 若从 `CandidateSet` 直接跳到 `CandidateDecision`，S1-G 的 BM25／Dense／Cross-Encoder／结构信号得分会被藏进召回或 Evidence 判断，无法判断头部错误发生在召回、排序还是晋升。本轮已显式补入该 artifact。
3. **当前不能制作“最终隐藏金标”。** DELL／MU／NVDA、ORCL／ASML／ANET 和旧 qrels 都已被反复观察，只能作开发／回归。现在冻结 schema、split 角色和开发集；valid、temporal frozen test、heterogeneous holdout 保留为空，待 VS1–VS3 合同稳定后另行预注册，避免标签泄漏和为当前实现定制题目。
4. **20 个 open gap 不是 20 个独立补丁。** 它们是覆盖账本里的业务风险，由 VS1–VS5 纵切成组关闭。若逐项修，会重复过去“每个组件绿、合并再坏”的模式。
5. **不应整体迁移到 Haystack、GraphRAG 或另一套 eval 平台。** FIN 已有 capture-first、exact-once、金融 Evidence／NumericFact 权威和 Workbench 消费者；推倒 Runtime 会扩大风险。只吸收 typed seam、显式 artifact、版本化 split 和 immutable experiment snapshot 等成熟模式。
6. **现在不能冻结性能阈值。** Recall、NDCG、MRR、promotion precision 等最终阈值必须来自受审 gold、候选 ceiling 和业务容错，不应先拍一个数字再反向塑造测试集。身份、期间、单位、locator、跨案污染、critical false promotion 和 false gap 仍可现在冻结为硬门。

## 已建立的机器资产

### 1. Canonical artifact spine

`src/retrieval/artifact_spine.py` 定义 16 种 artifact：

```text
SourceRouteDecision
  → RawSourceCapture
  → ParsedDocument
  → FinancialEvidenceObject
  → ObjectManifest / IndexSnapshot / S2SiblingBinding
  → EvidenceRequest / QueryFacetPlan
  → CandidateSet
  → CandidateRanking
  → CandidateDecision
  → EvidenceCoverageState
  → EvidencePackReadiness
  → WorkbenchProjection / FrozenConsumerProbe
```

每个 envelope 内容寻址并绑定 schema、payload digest、parent lineage 和适用 scope。日期必须为真实 ISO 日期，报告期起止不得倒置；跨 case 或 as-of 的 parent／child 接缝 fail closed。policy 明确每种 artifact 的责任层、data plane 和合法 parent 关系。

### 2. A–J 当前实现覆盖矩阵

`configs/retrieval/fin_ia_0_1_3_s1_implementation_coverage_matrix_v1_0.json` 不是目标清单，而是当前代码事实快照。每个责任轴保存：

- 实际 producer／consumer；
- 当前 artifact 和测试；
- 已证明层级；
- 业务影响；
- 最早责任层；
- 应由哪个 VS 关闭；
- migration／rollback 入口。

矩阵共 10 个轴、20 个 open gap；没有一轴被标为 `S1_qualified_stable`。最重要的四组业务风险是：

- 扫描 PDF、跨页表格和脚注可能在检索前已经丢失；
- 历史 chunk、新金融对象、sparse／dense index 和 S2 sibling 尚未统一绑定一个 snapshot；
- rerank 与 Evidence Role 还没有在同一 CandidateSet、同一 split 上被证明，候选也没有统一持久决策账；
- 系统尚不能完整证明一个 gap 是本地数据丢失、路线没执行、排序／晋升失败，还是免费公开资料确实不存在。

### 3. Split-safe 评测基础

`eval_sets/fin_0_1_3_s1/` 已建立：

- JSON Schema；
- program manifest；
- runtime-visible input 与 evaluator-only reference 的物理分离；
- SHA-256 绑定；
- 8 条 train-internal 开发样例；
- valid／temporal frozen test／heterogeneous holdout 三个保留 split；
- 防止 gold label 被塞进 Runtime input 的递归校验。

8 条样例覆盖日期语义、parent／child lineage、关系方向 query、通用公司话术拒绝、当期结果直接性、false public gap、跨案身份污染和 Workbench consumer binding。它们只证明基础合同可测，不证明 S1 泛化。

## 外部成熟模式的采用边界

- Haystack：采用 typed component seam 与 component／end-to-end 两层评测思想；不引入框架依赖。
- Microsoft GraphRAG：采用显式 documents／text units／entities／relationships 等 artifact 分责和多 query mode 思想；不引入 LLM 图索引，也不把 Graph 当金融事实权威。
- Arize Phoenix／OpenAI eval：采用版本化 dataset／split、运行时输入与 gold 分离、实验 snapshot；自动生成问题只能扩展开发集，不能直接成为隐藏金标。

这些模式已记录到 `external_pattern_registry.jsonl`，含采用、拒绝和已知边界。

## 验证结果

- foundation validator：10 个责任轴、16 种 artifact、20 个 open gap、8 个开发样例、3 个保留 split；`qualification_ready=false`、`s1_qualified=false`；
- foundation tests：`10 passed`；
- 相邻 S1／S2／Workbench 回归：`69 passed`；
- 全仓：`498 passed`；
- Project OS：`31 passed`；
- compileall：pass；
- active baseline：`141 Python／8 frontend／11 Runtime resources／0 forbidden reference`；
- secret scan：`6,887 files／0 findings`；
- JSON／JSONL 与 `git diff --check`：pass；
- 0 model／Provider／network／source promotion／index rebuild／full-chain。

## 真实能力与边界

本轮新增的是可执行的项目控制面与评测地基，不是用户可见的检索质量提升。现在系统终于可以机器化回答“这个结果由谁产生、消费了什么、属于哪个 case／期间、排序在哪里发生、为何晋升或拒绝、当前责任层证明到哪一步”；但实际 Runtime 尚未全面产出这些 envelope，Workbench 也尚未展示完整 source→Pack 差异，因此不能宣称 VS1、S1 或完整产品链通过。

## 下一步

下一项应严格进入 VS1，而不是继续扩 schema：

1. 选择当前可回放的官方 HTML／文本 PDF／transcript 与一组真实 Evidence Need；
2. 给现有 producer 加最薄 adapter，使当前真实 artifact 进入 canonical envelope，不复制 parser、retriever 或 runner；
3. 实现 `CandidateRanking → CandidateDecision → EvidenceCoverageState` 的持久账与 reviewed binding；
4. 让 current Evidence Pack 和 Workbench 消费同一 lineage；
5. 运行局部 mutation、接缝、真实纵切、跨案回归和 migration／rollback 六门；
6. 只有纵切通过才记 `vertical_slice_integrated`，随后再进入 VS2 复杂 PDF／OCR／表格。

若 VS1 实施发现现有 artifact 无法通过 adapter 接入，先修最早合同断点；不得另造一套平行 canonical Runtime。
