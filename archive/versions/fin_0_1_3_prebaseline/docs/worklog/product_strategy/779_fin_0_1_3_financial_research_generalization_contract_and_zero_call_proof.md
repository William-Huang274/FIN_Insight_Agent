# 779 — FIN 0.1.3 金融研究泛化合同与零调用证明

日期：2026-08-09

归属：FIN 0.1.3 / S0 前置依赖、S1 主 owner

状态：`contract_frozen_zero_call / DELL_vertical_slice_next`

## 1. 用户授权与目标

用户批准按以下顺序继续：先冻结“通用金融研究内核＋Evidence Slot 库＋插件接口＋行业 Pack 边界”，再做 DELL 纵切；随后 MU／NVDA 不改核心迁移、三个留出案例、sparse／dense 重建、residual-gap 外源补源，最后进入 DeepSeek 动态追问和研究综合。

本轮只完成第一项。没有把合同通过写成检索、Evidence、研报或泛化能力通过。

## 2. 实现

- 新增 provider-neutral `FinancialResearchKernel`：固定 subject、evidence owner、relationship direction、period/as-of、source authority、candidate/Evidence boundary、citation/lineage、coverage/conflict/gap。
- 新增 9 类通用 Evidence Slot；其中经营表现、需求、price-volume-mix、产能投入、现金转换、关系归因、监管政策、反证／WWC 是当前 AI infrastructure 必需项，capital allocation/valuation 遵循 PRD 保持 optional。
- 新增 `industry-ai-compute-infrastructure:v1`，行业差异只表现为可选 facet、query atom、mechanism、source role 和 forbidden substitution。
- DELL／MU／NVDA 只通过 CaseResearchProfile 绑定别名、财年、截至日、关系端点与行业 facet；核心代码无 ticker/product 条件。
- 冻结四个稳定插件接口：SourceAdapter、ParserAdapter、CandidateRetriever、EvidencePackEvaluator。
- 新增 deterministic multi-candidate evaluator：按多个候选聚合 facet，canonical source 去重，拒绝 cross-case／wrong-period／关系反转／越权 Evidence state，显式保留 conflict 和 typed residual gaps；最高状态仅为 `candidate_complete_pending_evidence_gate`。
- 冻结三个 evaluator-blind 留出 archetype：美国非半导体、non-US 20-F／6-K／本币／PDF、披露稀疏 honest-gap。真实身份和答案尚未选择。

## 3. 结构性纠正

本轮修正了一个旧 Project OS 合同错误：RC-P36-165 曾把 `owner_stage` 写成校验器不认识的 `S0_S1`，并引用四个未注册 scope。该 issue 的业务根因确实包含 S0 数据对象和 S1 检索，但治理必须只有一个主 owner；现改为 `owner_stage=S1`、`upstream_dependency_stages=[S0]`，并映射到已注册 scope。没有放宽 preflight。

同时新增本计划后续五个 S1 scope，避免 DELL 纵切再次依靠自由文本授权。

## 4. 验证

- 零调用 proof digest：`44f85bad8514724979c3a3fb1827a814a418c10deba1e3d0c335234c465c9645`。
- DELL／MU／NVDA 三案编译为相同 core fingerprint、不同 compiled digest。
- 每案 `8 required + 1 optional` Slot；synthetic multi-candidate shape 可达 candidate-complete，但 Evidence promotion 固定为 false。
- Industry Pack 放宽 authority、Case 越过 Pack 新造 facet 均 fail closed。
- 相关合同与历史 QueryFacet／cell composition／Project OS 回归：`45 passed`。
- `py_compile` 通过。
- network／Provider／model／document fetch／retrieval／embedding／rerank／Evidence promotion 全部为 `0`。

## 5. 产品与技术文档同步

- PRD 新增 16.9，明确四层产品结构、模型权限和 FIN 0.1.3 valuation optional 边界。
- TECH_03 新增第 24 节，定义插件、multi-candidate evaluator、chunk/index 关系和泛化证明。
- FIN 0.1.3 计划新增 7Q，把旧 410 build 后移到 DELL／transfer／held-out 之后；旧 specs 与失败现场保留。

## 6. 当前边界与下一步

当前只证明合同可执行、案例差异可被配置表达、错误边界能 fail closed。没有读取真实 DELL 候选形成新 Pack，也没有证明 source/chunk/query 已改善。

下一项为 `S1_DELL_FINANCIAL_SOURCE_OBJECT_AND_EVIDENCE_PACK_VERTICAL_SLICE`：使用现有真实本地资料与尸检参考需求，逐 facet 暴露 source、document object、chunk、typed query lane、candidate 和 residual gap；先不建 dense、不调用模型、不访问外网。
