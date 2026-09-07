# S1-C 检索栈与数据库通道治理

日期：2026-08-12
状态：`Owner 接受顺序 / 文档与机器合同完成 / 实现和模型执行未开始`

## 问题

原下一项只写了拆混合 query 和对象编译器，没有把 embedding、reranker、微调、检索组合方式和数据库精确查询放进同一决策。若直接实现，后续模型对照或 S2 NumericFact 可能再次迫使 S1 重做。

## 只读审计结果

- 当前 BM25=`17/18`、BGE-M3 dense=`14/18`、RRF=`16/18`；候选并集可覆盖 `18/18`，但 BGE reranker 仍出现 NVDA 改善、DELL 恶化的业务反转。
- 当前 BGE-M3 只运行 dense，没有测试 learned sparse 和 multi-vector。
- 当前活动数据库只有 Operations SQLite、行情 DuckDB 和行业 DuckDB；不存在新对象合同下的公司财务事实 mart。
- 归档旧 SQL successor 曾达到 annual `9/9`，current-quarter 仍为 `0/6`；旧结果不可晋升当前能力。
- ORCL／ASML／ANET 的结果已经被观察，不能继续承担纯净 final test。

## 决策与完成内容

1. 新建技术来源：`docs/architecture/retrieval/FIN_0_1_3_S1C_RETRIEVAL_STACK_AND_DATABASE_LANE_DECISION_20260812.zh-CN.md`。
2. 新建机器治理合同：`configs/retrieval/fin_ia_0_1_3_s1c_retrieval_stack_governance_v1_0.json`。
3. 新建确定性合同测试：`tests/test_s1c_retrieval_stack_governance.py`。
4. 明确 S1 负责 typed route plan，S2 负责公司财务事实 mart 与 NumericFact，S3 负责自然问题和动态追问。
5. 冻结 BM25、BGE-M3 三模式、Qwen Embedding、BGE/Qwen Reranker 与独立 Evidence Role 的有界对照；当前无模型和训练权限。
6. 数据库路线成为必选路线，不再以工作日志待办形式后传。
7. 预注册 HPQ／AVGO／INTC 的 issuer-time `test_precut`，冻结 payload digest=`d205b3d8...be37`；它们尚未抓取、标注或运行模型。
8. 将聚合指标必须附带业务语言错例写进机器合同，避免再次只汇报 `x/18` 而不解释错在哪里。

## 未执行

- 未下载模型、未访问网络、未运行 embedding/reranker、未建索引或公司财务 mart。
- 新 test issuer 已预注册，但未获取来源或创建标签；身份来自 SEC company-ticker 目录，后续仍需在 source build 前独立复核。
- 未实现 query family、object compiler 或 S2 exact lookup。

## 下一步

先建立新 `test_precut` manifest 和业务错误 taxonomy，再实现 query family＋claim/table/context compiler。通过确定性测试后才允许同语料多检索器对照。
