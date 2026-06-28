# 391 R26 Second / Third Layer Acceptance And Fundamental Peer Panel

## Prompt

用户追问第二层、第三层后续应如何定义通过标准，如何保证公开可得数据覆盖和解析足够；同时指出第三层计划里缺少三大表、报表科目、多企业/同行业联动分析。

## Decision

把第二层和第三层从“数据源接入计划”升级成 acceptance contract：

- 第二层必须用 ProductSpec / ProductKPI / ProductRelationship / ProductDeployment 四类 gate 验收，不能只算产品页 URL 或 generic product taxonomy。
- 第三层必须用 CapitalFlowPack、条款级 SEC parser、ownership / market-liquidity boundary gate 验收，不能把 filing metadata 当作 exact capital fact。
- 财报分析必须新增 `FundamentalPeerStatementPanel`，把三大表、同行同口径、行业重点指标、派生指标、产品财务桥和资本融资桥作为 Fundamental / Capital / Memo 的强制输入。

## Work Completed

- 更新 `docs/architecture/agent_graph_vnext/23_non_financial_signal_authority_and_multidimensional_research_basis.zh-CN.md`：
  - 新增 `第二层与第三层通过标准`。
  - 新增第二层 product/spec/KPI/relationship/deployment coverage gates。
  - 新增第三层 capital/funding/ownership/market-liquidity coverage gates。
  - 新增 `FundamentalPeerStatementPanel` 定义和财报分析通过条件。
  - 更新 Phase 4，使 Capital/Funding/Ownership/Market Liquidity Layer 显式包含三大表、同行、行业 focus、派生指标、产品/资本桥接。
- 更新 `docs/worklog/README.md`。
- 更新 `docs/worklog/00_internal_master_checklist.md`。

## Result

R26 当前是标准合同冻结，不是实现完成。后续实现必须按以下口径验收：

- 第二层：每家公司 product family slot 可解释；重点 family 有 schema；spec rows 必须有 `spec_name/value/unit_or_enum/version/citation`；relationship graph 必须有 edge type、authority、confidence 和 forbidden claims；Product-KPI gap 必须分类为 exact ready、business segment、spec/deployment/channel/benchmark signal、commercial tracker gap 或 attempt-backed boundary。
- 第三层：公司级资本/营运资本基础字段尽量全覆盖；offering、Form 3/4/5、13D/13G、proxy 只有解析出条款/股数/比例/表格字段后才能 exact；13F/N-PORT/short interest/options/ETF/factor/rates 保持 market/liquidity context，不得证明经营事实。
- 财报分析：标准 memo 至少覆盖两张表，深度 memo 必须覆盖三大表和同行同口径 panel；行业 focus policy 必须影响指标选择；财务判断必须和产品、行业、资本层桥接。

Verification:

- 本轮仅改文档，没有运行数据构建或单元测试。
- 后续执行前应补 deterministic tests / fixture gates：product spec schema coverage、capital event parser exactness、FundamentalPeerStatementPanel peer coverage、memo dimension-balance gate。

## Follow-up

- R26 implementation：AI/Semis product spec schema + source-route parser-backed rows。
- R27 implementation：ProductRelationshipGraph v2 edge typing and source authority gates。
- R28 implementation：Form 3/4/5 XML、13D/13G schedule、offering、proxy parsers。
- R29 implementation：FundamentalPeerStatementPanel runtime object and specialist/memo consumption gates。
