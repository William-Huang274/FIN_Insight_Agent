# 634 FIN 0.1.3 S0-02 shared Runtime admission 与 historical proof debt

日期：2026-08-06
状态：`S0_02_engineering_pass / RC_P36_115_closed / RC_P36_128_closed / S0_03_next`

## 为什么属于 S0

本项不修研究内容，也不调用模型。它修的是所有后续执行都依赖的权限消费和证明语义：同一 admission 不能靠换一个 runtime 目录再次执行；旧 decision/receipt 也不能因为今天的代码或维护中文档发生变化而被错误判死。若不先收口，这两类问题会让 S1–S5 的测试和正式运行都不可信。

## 实现

- 新增 `src/sec_agent/shared_admission_ledger.py`：
  - repository-independent SQLite control plane；
  - connection 使用 `busy_timeout=30s`、`synchronous=FULL`；不在每次并发连接上重设 journal mode，避免初始化锁竞争；
  - `admission_digest` 为唯一键；
  - `BEGIN IMMEDIATE` 原子 reserve；
  - reserve 先于 source/model/provider/business side effect；
  - reservation 本身即 consumption，崩溃后不自动释放、retry 或 replay；
  - terminal 精确绑定 admission、Run、Attempt、status、phase、code 和 result digest；
  - receipt digest mutation fail closed。
- 旧 S4-T03 runner 增加可选 compatibility hook，保持 FIN 0.1.2 历史调用形状；新增 `Fin013SharedAdmissionGuardedSearchRunner`，FIN 0.1.3 current 路径必须显式提供 shared ledger。
- current wrapper 代码级拒绝把 shared ledger 放进本次 disposable runtime root，避免调用者用错路径后重新引入跨目录 replay 缺口。
- RC-P36-128：
  - MU one-time issuance 生成测试改用测试注入的 disposable、未消费 runtime root；
  - historical scope decision 对不可变 config 继续精确重算，对历史绑定的 mutable source code 只校验 ref 与原摘要形状；
  - S5 historical decision 对 living product document 同样保留原 ref/摘要，不拿今天的文档字节重写历史；
  - 旧 decision、receipt、runtime evidence 均未改写。
- 生成 S0-02 machine decision、active-suite successor 和 runtime-resource-registry successor。

## 8 个候选复证结果

- 原摘要复用：reference-role registry v1.1、repository reference proof policy v3、typed environment semantic parity。
- 拒绝：reference-role v1.0 已被 v1.1 supersede。
- 旧 runtime resource registry 被拒绝：static detector 发现 `fin_ia_0_1_2_s4_t05_current_evidence_fact_candidate_pool_profiles_v1_0.json` 已被 runtime 使用却未登记。
- 新 canonical successor 登记 31 项资源；detector 发现的 30 个直接 runtime literal 全部在 registry 内。
- 三个旧测试不因旧 `FIN 0.1.3` 文件名晋升 current authority：reference-role 与 typed-environment 的逻辑由 canonical successor test 覆盖；固定 `29/30` 计数的旧 resource test 被拒绝。

## 验证

- canonical S0-02 contract/mutation：`9 passed`，其中两个线程同时 reserve 只有一个 winner，ledger-inside-runtime 负向测试 fail closed。
- S0-01 + S0-02 + RC-P36-128 历史债务 focused：`25 passed`。
- 加入旧 T03 runner、DELL issuance/acceptance 的相邻兼容回归：`40 passed`；新 hook 未改变未注入 ledger 的 FIN 0.1.2 返回形状。
- 同一 admission 在 runtime A 成功终结后，runtime B 在任何来源调用前得到 `shared_admission_already_consumed:terminal`。
- 模拟 crash：只 reserve 后重开数据库，同一 admission 得到 `shared_admission_already_consumed:reserved`。
- Run/Attempt mutation、terminal receipt tamper 均 fail closed。
- model/provider/network/source/business run/Artifact/historical receipt rewrite 均为 0。

## 产品与研究边界

本项只证明后续运行的 execution authority 与历史证据治理更可信。它没有修复 DELL 季度/全年错误，没有增加 Evidence/Graph，没有提升 Claim、Lead、Writer 或报告内容，也没有产生新的 R2/R3、Human acceptance 或 release pass。研究内容八维硬门禁仍是 release-blocking，后续必须按 S2/S3/S4/S5 计划实现。

## 下一步

进入 `013-S0-03`：建立 shape/integrity、financial truth、analysis quality、product usability 四类 oracle，先让季度/全年、entity、unit、scale、formula 错配在 S1 或 S3 前稳定失败，再进入 S1 真值链修复。
