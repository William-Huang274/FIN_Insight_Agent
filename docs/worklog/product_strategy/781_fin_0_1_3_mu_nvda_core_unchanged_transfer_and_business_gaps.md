# 781 — FIN 0.1.3 MU／NVDA 不改核心迁移与业务缺口

日期：2026-08-09

归属：FIN 0.1.3 / S1

状态：`engineering_pass_core_unchanged_transfer / held_out_generalization_next`

## 1. 本项回答的问题

DELL 纵切通过后，本项不是再证明一次 DELL，也不是比较模型，而是回答：同一套金融研究内核、Evidence Slot、关系方向、三层期间和 Candidate Pack evaluator，能否只更换公司配置、来源绑定和诚实 gap，就迁移到 MU 与 NVDA。

执行期间锁定以下三份资产的 SHA，前后保持逐字节一致：通用合同、通用合同实现、DELL 已证明的本地 source/object executor。网络、Provider、模型、embedding、rerank 和 Evidence promotion 均为 `0`。

## 2. 机器结果

| 案例 | Query lanes | Candidate rows | 预审目标 | Parent sources | Contract rejection | Typed gaps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MU | 24 | 256 | 24/24 | 16 | 0 | 13 |
| NVDA | 26 | 262 | 26/26 | 13 | 0 | 13 |

两案共享 DELL 的 core fingerprint=`94af69dcc875ba285afca587d36622dfa859b092c7a2bf686141c5e43308b458`，没有新增 ticker-specific 核心分支。组合结果 digest=`a5e6382654d66a796c932df644d90371fe671ab2ecfa8c07a352e142a03a6276`，状态=`engineering_pass_core_unchanged_transfer`。

这只说明同一条候选装配链可以迁移，不说明两案资料完整，也不说明 Evidence、研报或产品验收通过。

## 3. MU 业务上得到什么、还缺什么

当前本地资料能支持：

- Q3 FY2026 公司收入、利润、经营现金流和 outlook；
- CMBU／CDBU／MCBU／AEBU 分部表现；
- DRAM／NAND ASP 与 bit shipment 方向，因此 price／volume／mix 研究面具备候选基础；
- 战略客户协议中的 `22B USD` financial commitments 与约 `18B USD` cash deposits；这些数字明确不能被写成 revenue、RPO 或 orders；
- HBM4 已进入 high-volume shipment、HBM4E 预计 2027 年量产、Tongluo 预计 2027 年中形成 meaningful shipments；
- ramp delay／underutilization、数据中心电力水资源和资本约束、出口管制等反方机制。

仍缺：产品级 HBM／AI 收入、Micron 订单或 backlog、pull-forward／客户消化、当前利用率／良率、设备与材料公司特定分配、先进封装容量、可复算失效阈值及 PIT 估值。尤其不能把整个 CMBU 收入冒充 HBM 收入，也不能把客户押金冒充已确认收入。

对象层同时暴露：8-K 的报告期与发布日期混用；当前 10-Q 仍是粗粒度 document segment，未拆成可独立绑定的 table／metric／claim；跨公司关系没有 allocation object。

## 4. NVDA 业务上得到什么、还缺什么

当前本地资料能支持：

- Q1 FY2027 revenue=`81.6B USD`、Data Center revenue=`75.2B USD`、gross margin 和下一季 outlook；
- FY2026 Q3 10-Q 中四个 direct customer 占比 `22%／15%／13%／11%`；
- Dell AI server orders 与 Microsoft AI infrastructure usage 只能作为下游需求 read-through，不能归因为 NVIDIA 自身订单；
- Micron HBM4 与 TSM 扩产只能作为供应侧 read-through，不能证明 NVIDIA 获得的具体 allocation；
- H20 相关 `4.5B USD` excess inventory／purchase obligations loss、出口管制及中国市场风险；
- 架构转换、资格认证与渠道库存风险。

仍缺：NVIDIA 自身订单／backlog、GPU 或系统 ASP 与出货量、price-volume-mix bridge、可用晶圆／HBM／先进封装的公司特定产能与良率、current FCF program、可复算失效阈值及 PIT 估值。

对象层同时暴露：Q1 earnings 8-K 的报告期与发布日期混用；本地 corpus 缺 Q1 FY2027 10-Q，导致部分供应、集中度、政策和采购承诺仍依赖 FY2026 Q3 10-Q；部分 metric child 只有年份，没有完整季度／截至日／父表语境。

## 5. 执行中发现并修正的配置问题

正式物化前的零调用诊断发现两类 case-config 问题：

1. 两个预审 excerpt 没有严格按原文连续短语书写；只修正审阅绑定，没有修改查询或核心；
2. NVDA 的 AI infrastructure orders 已被 Dell 下游 read-through 候选覆盖，但又被重复声明为 gap；删除冗余 gap，同时保留“不能归因为 NVIDIA 自身订单”的关系边界。

这些问题证明 Candidate Pack evaluator 必须同时拒绝漏报 gap 和重复 gap，而不能只看 target-in-pool。

## 6. 兼容债与下一步

冻结 executor 的内部 run scope 与 raw schema 仍保留 `DELL` 命名。当前 case-neutral wrapper 独立计算迁移验收，因此不影响 MU／NVDA 结果，但该名字不能继续扩散为长期公共合同；应在以后正式版本化 source-object runtime 时一次性重命名，不能为了本次迁移改写冻结实现。

下一项为 `S1_THREE_HELD_OUT_FINANCIAL_RESEARCH_GENERALIZATION_PROOF`。它必须在读取检索结果前冻结三类新公司身份与 Case profile，并验证新增公司只增加外部 profile／Pack 配置，不修改金融内核。只有留出验证通过后，才允许决定 successor sparse／dense 的对象集合。

## 7. 证据

- `configs/runtime/fin_ia_0_1_3_s1_mu_nvda_core_unchanged_transfer_policy_v1_0.json`
- `configs/releases/fin_ia_0_1_3_s1_mu_financial_source_object_transfer_result_v1_0.json`
- `configs/releases/fin_ia_0_1_3_s1_nvda_financial_source_object_transfer_result_v1_0.json`
- `configs/releases/fin_ia_0_1_3_s1_mu_nvda_core_unchanged_transfer_result_v1_0.json`
- `src/sec_agent/financial_research_core_unchanged_transfer.py`
- `tests/contract/test_fin_0_1_3_s1_mu_nvda_core_unchanged_transfer.py`

