# 235 Layered Data Source Expansion Execution Plan

## Prompt

用户要求在已落好的分层数据源扩容框架文档基础上，继续落下一阶段的具体执行文档。同时要求下一阶段不能忘记上一阶段未完成的关系图谱任务：

1. `relationship_edges` schema 和 edge confidence rubric。
2. 从当前 238 家 SEC evidence 抽 direct named customer / supplier / partner / contract edges。
3. 做 entity resolution：公司别名、子公司、ticker、CIK。
4. 加 verifier gate，防止把 exposure 写成 customer / supplier。
5. 接入 Relationship Router 和 Industry Specialist。

用户允许先执行数据源扩容，但强调扩容后接入向量数据库时必须把这 1-5 点修复考虑进去。

## Decision

新增执行文档，把数据扩容和关系图谱收尾拆成并行但有依赖的阶段：

- E1/E2 可以先做公司池和 SEC / 8-K / earnings 主证据扩容。
- R1-R5 必须在扩容数据提升为主线 typed vector / Hybrid retrieval 前完成。
- V1 typed vector DB 接入必须区分 relationship edge、relationship context、paraphrase context、event lead，不能简单扩大 top-k。

## Work Completed

- 新增 `docs/architecture/layered_data_source_expansion_execution_plan.zh-CN.md`。
- 更新 `docs/architecture/README.md`，加入执行文档入口。
- 更新 `docs/architecture/layered_data_source_expansion_plan.zh-CN.md`，从框架文档链接到执行文档。

执行文档包含：

- E0-E2：主线冻结、数据源配置、公司池和主证据扩容。
- R1-R5：关系边 schema、关系边抽取、实体归一、Verifier、Router/Specialist 接入。
- V1：扩容数据接入 BM25/ObjectBM25/BGE/Milvus typed vector 的规则。
- F1：分层回归和小批 full-chain。
- X1：是否接外部供应链数据源的决策门控。

## Verification

- 本轮是执行文档落地，未运行代码测试。
- 文档未写入 API key、SSH 密码或私有 token。

## Next

下一步开始实现时，建议先做：

1. `configs/data_sources/universe_tiers.yaml`
2. `configs/relationships/relationship_edge_schema_v0_1.json`
3. `configs/relationships/relationship_confidence_rubric_v0_1.json`
4. `src/sec_agent/relationships/edge_schema.py`
5. `tests/test_relationship_edge_schema.py`

在这些合同落地前，不应把扩容数据直接提升为主线向量库。
