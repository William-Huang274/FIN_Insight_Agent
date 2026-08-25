# Model Run: FIN013-S1-DELL-03B-INTERNAL-CHAIN-CEILING-R2

## 摘要

- 状态：`executed_success / candidate_ceiling_materialized / independent_quality_audit_pending`。
- 新 attempt：`dell-rsq-03b-internal-chain-r2`；R1 保持 terminal failed，禁止重试、复用分数或改名为成功。
- 唯一修复：source-store 只接受 canonical `evidence_id`；compiled object 继续使用其对象层投影
  `source_record_id`。两层身份不可混用，也不接受 alias 宽松回退。
- 执行范围不变：5 个 request、6 个 unoverlapped target、3 个 held target 执行数为 0。
- 调用边界不变：最多 1 个本地 Qwen3-Embedding-0.6B query batch；network、Provider、生成模型、
  external capture、4B embedding、reranker、retry、promotion、gap closure 全部为 0。

## R1 失败与 R2 修复合同

R1 已进入 current R38 检索并消费唯一 query batch，之后才在 source population validator 抛出
`dell_03B_source_record_id_missing`。真实 source store 的 1,888 行全部有 `evidence_id`，0 行有顶层
`source_record_id`；34,198 个 compiled object 则通过 `lineage_source_record_ids` 引用全部 1,888 个
source identity。

R2 将 source/object SHA、1,888 个非空且唯一的 `evidence_id`、34,198 个非空 object lineage 以及
receipt 的 zero-outside／zero-missing 集合等式全部放到 embedding 前置门。任何漂移在 query batch 前终止。
编译阶段再次复核相同集合等式，避免前置门和结果编译之间出现语义分叉。

## TokenBudgetBasis

- node purpose：用同一 5 个冻结请求完成 R1 未能编译的 03B candidate-ceiling 定位。
- input scale：34,198 个 digest-bound object、1,888 个 source record；document embedding cache 只读复用，
  只允许 1 个全新 query batch。
- required outputs：每 target 的 corpus／union／useful@10／final 语义计数、rank trace、earliest loss、
  source-lineage 等式及 4B／reranker／03C 的互斥 eligibility。
- schema burden：绑定 immutable R1 policy、R1 failure receipt、03A R2、R38 registry／receipt、请求程序、
  implementation SHA 和非覆盖式 private/public digest。
- materiality/quality risk：广义 server ASP、美元 shipments、供应商自身扩产、泛 yield 风险或泛 OEM 关系
  不能冒充 Dell AI-server ASP、物理台数、观测 yield 或 supplier-to-Dell allocation。
- comparable evidence：R1 只有入口与失败事实，没有可复用 result／score；R30 的 12/12 仍只是候选材料轴完整，
  不是本轮 6 个研报 target 的命题充分性。
- reasoning profile：本地非生成式 embedding；target 分类由预注册 conjunctive deterministic gates 重放。
- stop/truncation：dirty 或 unsynced Git、任一 predecessor／failure／implementation／input SHA 或 digest 漂移、
  identity 非唯一、source-lineage 集合不等、held target、请求数或 batch 超限、output collision、任何越权调用或
  mutation 立即停止；union=96、final=16、useful cutoff=10 不扩大。

## 研报质量判定接口

R2 只回答“完整目标对象在本地语料、候选 union 和 useful@10 的哪一层出现”。它不能直接把 candidate 写入
研报。后续必须逐 target 进入 CandidateDecision／Evidence Gate，并按公司、产品、期间、口径、角色、方向、
分母和禁止推断审查。只有被 admission 的证据才能进入 citation/source appendix；未找到完整对象时只能证明
“当前本地语料缺对象”，不能直接宣称公开信息不存在。

## 实际执行结果

- clean/synced implementation commit：`53ea34a1cef5a28c640693fadd15876e877aa4f5`；
- recorded at：`2026-08-25T12:47:13+00:00`；
- 5 requests、6 targets、3 held target executions=`0`；
- 1 个本地 Qwen3-Embedding-0.6B query batch，34,198 个 cached document embeddings 只读复用；
- 339 个 request-level hybrid union candidates、80 个 final selected candidates、795 个 target-scoped union
  occurrences；
- network/provider/generation/external/4B/reranker/candidate promotion/Evidence promotion/gap closure=`0`；
- public digest=`6c8159ed...132496`，SHA256=`2c8f3c13...7b46ef`；private digest=`eaa604ad...7d65df`，
  SHA256=`40bbccba...6e56e53`；public 无 `model_text` 和 URL。

| target | complete corpus | partial corpus | complete union/final | partial union/final | earliest limitation | next eligibility |
|---|---:|---:|---:|---:|---|---|
| ASP | 0 | 84 | 0 / 0 | 6 / 3 | local corpus missing complete target | 03C |
| capacity release | 0 | 2 | 0 / 0 | 0 / 0 | local corpus missing complete target | 03C |
| capacity utilization/yield | 0 | 3 | 0 / 0 | 0 / 0 | local corpus missing complete target | 03C |
| HBM supply | 0 | 15 | 0 / 0 | 4 / 2 | local corpus missing complete target | 03C |
| supplier→Dell read-through | 0 | 7 | 0 / 0 | 2 / 0 | local corpus missing complete target | 03C |
| Dell AI-server units | 0 | 3 | 0 / 0 | 2 / 1 | local corpus missing complete target | 03C |

作者侧抽查与 target contract 一致：ASP 命中为 traditional server／consumer／commercial ASP，不含 Dell
AI-server 单位分母；units 只有 shipments 时序，没有物理台数；capacity/HBM 只有供应商自身扩产或风险，
没有 Dell allocation；yield 只有泛制造风险，无观测比例；relationship 是无关合作或泛 allocation 文本，
没有 supplier→Dell bridge。该抽查仍须由作者分离 reviewer 复核。

## 当前边界

R2 成功不等于 02B human decision、03C acquisition、03D 4B／reranker、Evidence admission、gap closure、
G3、S1/S2/S3、Pack/Readiness 重编、新研报质量、产品验收、publication 或 release。实际执行只能发生在完整
工程门通过、implementation commit clean 且与 upstream 相等之后。当前结果只把 6 项都路由为 03C
eligible；它没有授权 03C，也没有证明公开信息边界。
