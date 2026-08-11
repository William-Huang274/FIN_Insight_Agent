# 799 — FIN 0.1.3 PhysicalStoreArtifact v1.1 实现与五步执行门

日期：2026-08-10

阶段：S1，后续衔接 S1→S3

状态：v1.1 working-tree／full-fake 通过；真实 microcanary 尚未签发或执行；R2 尚未授权

## 为什么不能直接重跑 R2

R1 不是向量生成失败。93 个 BGE-M3 向量和 93 个 Milvus insert acknowledgement 都已发生，失败在产品把目录型 `milvus_lite.db/` 当成单文件。若只把 `is_file()` 改成 `exists()`，仍然无法回答目录中哪些文件组成有效 store、manifest 是否指向真实数据、索引是否存在、发布前后内容是否一致，以及失败时到底完成了多少 flush／count／reopen／metadata query。

因此本轮没有直接消耗新的 93-vector Attempt，而是先把“物理 store 是什么”写成后端中立合同。R1 working root、authority、attempt 和 terminal result 均保持原样，R2 使用全新的 `attempt_r2_building`、`v2` 和 collection identity。

## 已完成的结构实现

`PhysicalStoreArtifact` v1.1 现在支持两类后端：

- file：记录单文件大小和 SHA256；
- directory：按排序后的相对路径生成 canonical tree manifest，记录目录、文件大小和 SHA256，拒绝 symlink、特殊文件和 manifest 越界路径；
- Milvus 目录 profile 另外校验 collection name、`current_seq`、embedding dimension、metric/index type、manifest、schema、data file 和 index file；
- 发布前和整个 working root rename 后分别重算 artifact digest，二者必须相同；
- success／failure 共用同一份完整调用计数，包含 flush、count、metadata-query 和 reopen；
- terminal 同时保存最后已验证 phase 和各 phase 的安全 snapshot digest。

旧 v1／R1 schema 仍可读取；新实现不是把核心 Runtime 改成 Milvus 专用。后端 profile 才声明当前 pymilvus 3.0／milvus-lite 3.0 为 directory store，未来单文件或其他后端不需要改金融研究控制面。

working-tree full-fake 结果：同一 93-spec manifest 仍为 DELL／MU／NVDA／ORCL／ASML／ANET=`15／16／14／19／10／19`；ObjectBM25 和 fake dense 完整终态；file 控制组与 directory store 均通过；类型错配、缺 index、manifest 文件路径／partition 名称越界、部分写入、跨案和 Evidence 污染等 11 类 mutation 均 fail closed。修复 Windows issuer bootstrap 与 clean-proof volatile-duration comparator 后重新绑定的 proof=`898a9aae...768f`。该 proof 的真实 network／provider／LLM／BGE／Milvus 调用均为 0。

## 实验治理（在真实 microcanary 与 R2 前冻结）

### 假设与决策目标

假设：由 backend profile 声明 artifact kind，并对目录生成可重算 tree／collection receipt，可以接受当前 Milvus 3.0 的真实布局，同时拒绝缺文件、错类型、越界和发布后漂移。

决策目标分两层：

1. synthetic microcanary：1 个手工 4 维向量，不加载 BGE、不含公司或财务事实；必须完成 create／insert／double flush／count／close／reopen／identity／tree digest／whole-root rename；
2. R2：fresh 93-spec ObjectBM25＋BGE-M3／Milvus，必须生成完整 public terminal、private receipt 和 published v2 root。

### Ceiling、baseline、leakage 与停止规则

- microcanary ceiling：1 个 synthetic vector，0 network／provider／LLM／BGE／search／rerank／Evidence，0 retry；
- R2 ceiling：1 次本地 CPU BGE load、93 vectors／12 batches、1 fresh collection，0 network／provider／LLM／search／rerank／Evidence，0 retry；
- baseline：R1 的 93 embeddings／93 acknowledged inserts 与未发布 directory working root；
- leakage：此阶段不读取 qrels、不跑查询、不评分，不可能用 Gold 调索引；
- stop：microcanary 或 R2 若出现新的 storage/backend L1，Attempt 终止并保留现场，不自动进入 R3；
- efficiency：合同和 mutation 用零调用完成，真实只允许一次 1-vector microcanary 和一次 fresh R2，不逐字段 live 修补。

当前 governance decision=`proceed_to_clean_commit_then_exact_once_synthetic_microcanary`；不是 `proceed_to_r2_now`。

## 用户批准后的五步执行线

当前统一计划为：

1. 完成目录型发布修复、microcanary、clean proof 和 fresh R2；
2. 六案例真实 exact／ObjectBM25／BGE-M3／fusion 对照，逐条解释错公司、错期间、错关系、错章节或内容过泛；
3. 生成六案 Evidence Pack，先审 DELL，再在不改核心的前提下迁移；
4. 只对真实 typed residual gaps 做 official-first 外源补源；
5. 先让 DeepSeek 消费固定 Evidence Pack 测分析综合，再单独测动态工具研究。

正式计划随执行状态更新：`configs/releases/fin_ia_0_1_3_s1_to_s3_retrieval_evidence_research_execution_plan_v1_0.json`，digest=`8d170d67...91e5`；microcanary 与 clean A2 已通过，clean A1 失败保留；fresh R2 已 exact-once terminal succeeded。五步线第 1 步完成，第 2 步六案业务解释型检索评估 current。

## 当前边界与下一步

当前只证明 working-tree engineering。下一步必须先提交并推送实现；随后从 clean commit 签发一次 synthetic microcanary authority、执行一次并保留终态。microcanary 通过后还需 clean archive 复证，之后才签发 fresh R2。物理 build 成功不等于检索质量；第 2 步必须另行实测。

首次从 clean commit 调用 microcanary issuer 时，在 authority 写出前因 Windows 未显式加入 `scripts/releases` 模块路径而退出；authority／result 均未生成，WSL／Milvus／向量调用均为 0，因此没有消费 microcanary Attempt。该问题属于同一签发工具的 bootstrap 缺陷，原地补齐显式模块路径并重新生成 source-bound 零调用 proof；不得把这次 pre-authority 退出计作一次真实 microcanary，也不得绕过 clean/synced gate。
