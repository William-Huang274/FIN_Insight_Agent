# 124 - P38 Point 01 decision resolution / resource / case / retention audit

记录时间：2026-07-11

## 用户决定

- 先按本机资源评估 PostgreSQL；若本地不适合或拖慢测试，SQLite 先行并为 PostgreSQL 保留替换边界；
- 主力模型继续使用 DeepSeek V4 Pro / Flash，后续可接 GPT API；
- 允许 gated node-level strong-model comparison；
- calibration cases 先审历史 case 表现和跨行业投研报告结构，再决定；
- 企业数据按金融行业常见合规标准设计，个人项目阶段采用可配置开发 profile。

## 审计结果

- i9-13980HX 24C/32T；RAM 15.63 GB，审计时可用约 3.02 GB；
- C/D/Z free space 约 1.27/31.47/14.01 GB；
- 无本机 PostgreSQL/psql；Docker 可执行文件存在但 service stopped；当前 compose 无 PostgreSQL；
- data 73.27 GB，indexes/staging/processed/raw 是主要空间占用；
- SQLite WAL 100k event insert 约 0.62s，1,000 task reads 约 0.24s，足以支撑首个 single-user DecisionSurface slice；
- 历史存在多套跨行业 case catalog，但 P33 15-case readiness 为 artifact ready 1、fresh all-specialist pass 0、blocking 15，不能据此宣称泛化；
- 金融记录保留期限按业务与司法辖区变化，美国 broker-dealer 常见 3/6 年，中国部分证券/期货客户和交易资料可达 20 年，因此不使用统一 7 年硬编码。

## 决策

- SQLite-first，canonical repository contract PostgreSQL-compatible；M4 前做 PostgreSQL parity/benchmark；
- TaskRun 第一阶段 binding；
- DeepSeek-first、provider-neutral、GPT-ready；
- calibration case 选择 blocked on HistoricalCasePerformanceAudit + SectorReportArchetypeAudit；
- 第一阶段 no formal Workbench UI；
- case-scoped feature-flag cutover；
- legacy projection 兼容两个 release cycles 或 60 天；
- retention 使用 record-class/jurisdiction/tenant policy，并支持 legal hold。

## 边界

- 资源/规划审计；
- 未清理大型数据；
- 未启动 PostgreSQL/Docker；
- 未运行 paid model/full-chain；
- 未修改 PRD/TECH；
- 未声称满足任何具体持牌机构的全部法规。
