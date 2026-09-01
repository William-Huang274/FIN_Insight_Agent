# S1 成熟数据面迁移：资格实验门与首轮执行记录

> 状态：`AUTHORIZED / IN_PROGRESS / DIRTY BOUNDED EVIDENCE`
> 日期：2026-09-01
> 分支：`codex/fin013-dell-s1-s2-product-bridge`
> 起始提交：`86e31761798fb618fa1a473c7c028d5f8b4728fe`
> 产品边界：仅限 S1 development qualification；不构成 blind、产品、生产或发布验收。

## 1. 为什么做这轮

S1 现在能跑，但通用能力里仍有大量自研实现：PDF 版面/表格解析、SEC 文档拆分、内存式 BM25 与 dense 聚合、模型缓存和路由。它们不应该因为已经存在，就自动成为未来架构。

本轮不再问“怎样把旧实现继续补完整”，而是用真实本地材料回答四个迁移问题：

1. Arelle 能否承担 XBRL/iXBRL 的标准解析和校验，FIN 只保留 issuer、period、vintage、lineage 等领域合同？
2. Docling 能否承担通用 PDF 页面、布局、表格和定位结构，旧 `pdf_layout` 只作为回归基线和必要兼容层？
3. PostgreSQL + pgvector 能否装下当前 frozen object/embedding，并提供可过滤、可重建、可观测的 lexical/vector/hybrid candidate plane，替代继续扩张进程内自研检索？
4. 只有前三项提供了稳定 candidate/object plane 后，LangExtract + DeepSeek 是否值得作为“候选语义抽取器”进入 shadow；它不得直接产生 Evidence 或事实权威。

## 2. 预注册决策与假设

| 能力 | 成熟候选 | 现有基线 | 本轮可作出的决定 |
|---|---|---|---|
| XBRL/iXBRL | Arelle 2.44.5 | HTML/SEC 自研拆分与字段提取 | `ADOPT_PILOT` / `HOLD` / `REJECT` |
| 通用 PDF | Docling 2.124.0；MinerU 仅保留 challenger 席位 | `official_pdf.py`、`pdf_layout.py` | `ADOPT_PILOT` / `CHALLENGER` / `HOLD` / `REJECT` |
| 检索存储 | pgvector 0.8.6 + PostgreSQL 16；OpenSearch 3.8.0 仅在资源门通过后比较 | 当前 object JSONL、BM25、Qwen dense cache、custom hybrid runtime | `ADOPT_PILOT` / `CHALLENGER` / `HOLD` / `REJECT` |
| 语义抽取 | LangExtract 1.6.0 + DeepSeek strict schema shadow | 当前规则/模型候选路径 | 本轮后段才允许 `ADOPT_PILOT` / `HOLD` / `REJECT` |

核心假设：成熟通用组件通过薄 adapter 接到 FIN canonical contracts 后，可以减少自研通用基础设施，同时不牺牲 source lineage、PIT、period、unit/scale、citation locator、abstention 和人工复核边界。

### 2.1 Docling 版本 supersession

本门最初预登记的 `Docling 2.117.0` 在实际安装前被 `2.124.0` 明确取代。原因是资格环境建立时，官方最新稳定版已为 2026-08-31 发布的 `2.124.0`；旧版没有被安装、下载模型或运行 case，因此这不是看到质量结果后换版本，也不能把 `2.124.0` 的结果冒充成 `2.117.0` 的结果。

冻结后的首轮合同为：

- `docling==2.124.0`，上游 tag object `699e20f8e34748fface6005d0e9340d9011ee1d2`；
- `docling-core==2.92.0`、`docling-ibm-models==4.0.0`、`docling-parse==7.16.0`；
- Heron 的上游 `main` 解析并固定为不可变 commit `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`；
- TableFormer 的上游 `v2.3.0` 解析并固定为不可变 commit `fc0f2d45e2218ea24bce5045f58a389aed16dc23`；
- 首轮只资格化 native-text PDF：Standard threaded pipeline、`threaded_docling_parse`、Heron、TableFormer accurate、OCR/remote service/external plugin/所有 enrichment 均关闭；
- 当前固定 commit 的 Heron model card 为 Apache-2.0；当前固定 commit 的 `docling-models` model card 为 CDLA-Permissive-2.0。后来 `main` 的 dual-license 变化不能倒签到本次固定 commit。
- 两个固定 snapshot 都没有随权重提供完整 LICENSE/NOTICE 文件；README frontmatter 是许可声明证据，但还不是完整再分发许可包。TableFormer 权重若进入可分发产品，仍需随数据提供 CDLA-Permissive-2.0 正文并完成 legal review；当前只能做本地 qualification，不能签 redistribution pass。

`2.117.0` 仅保留为被 supersede 的历史预登记，不再是当前执行合同。

## 3. 冻结输入与数据隔离

本轮允许读取但不得提交内容的本地真实输入：

- DELL 2023 10-K iXBRL/HTML：`data/raw_private/sec/2023/ai_servers_enterprise_hardware/DELL/10-K.html`；
- IFX 2023/2024/2025 annual report PDF；
- TEL FY25Q4 presentation/transcript PDF；
- Tencent 复杂 PDF 已冻结原件；
- 当前 object store v5：1,888 records，文件 SHA-256 `d4c7e51790713d32fc10a9d0382b617f8ebd60861a3741d3adcee34392045d45`；
- 当前 compiled object views v9：34,199 objects，文件 SHA-256 `1c3e48486f933d23306dbabacb1641e26cb9bbc5b474da932d602752dff3fa92`；
- 当前 Qwen embedding cache：34,199 × 1,024 float16，文件 SHA-256 `6356da50cfcb53fdfb48541c72889e76f6aa7d43b4c8450e95b89a2dd8bb4b06`；
- development qrels v1.1：18 项，SHA-256 `1d56f1deef3d7082b4e308a9caae1e7b70941a66cd025620adbcc80231b7562b`。

这 18 项因历史 reference exposure 只能做 development comparison。当前 Codex 不能把自己参与过或已看过答案的集合签成 blind qualification。不得读取或改写额外 hidden/holdout expected outcomes 来制造“盲测通过”。

## 4. 指标、基线与先后顺序

### 4.1 解析

每个候选至少记录：成功/失败、页数、文本块数、表格/单元格数、page/bbox/reading-order/cell provenance 是否保留、耗时、峰值内存、产物大小、警告和可重放命令。抽样人工核对标题、段落、表格跨页、脚注和负号/单位，不以“程序没报错”视为通过。

### 4.2 检索

检索顺序固定为：

1. exact object identity 与 metadata filter 零误配；
2. frozen embedding 导入、维度和逐行 identity 对齐；
3. lexical、dense、hybrid 分别跑 candidate ceiling；
4. 才计算 development Recall@k、MRR、nDCG、延迟、内存、索引体积和重建时间；
5. 只有 target 已进入 candidate pool，才允许比较 reranker。

现有基线必须同表报告，不能只报告新候选。当前已知开发影子不是验收结论：18 项中 positive targets available 15；BM25 target-in-ranking 6、top-k 5；Qwen dense target-in-ranking 9、top-k 8；受控 pairwise reranker 12/16，但自然 candidate pool 尚不足，不能用 reranker 掩盖召回缺失。

### 4.3 LLM 语义 shadow

任何 DeepSeek 调用前必须另记 `TokenBudgetBasis`：节点用途、固定输入规模、输出 schema、质量/重要性风险、可比运行、reasoning profile、最大调用/输出、截断和停止行为。输出只进入 Candidate，必须经过 Pydantic/FIN hard validators；解析错误 fail closed；禁止 Evidence admission、事实 promotion 或报告生成。

## 5. 资源、失败和停止条件

- 资格环境、容器卷、模型缓存和大产物只能位于 `Z:\FIN_Insight_Agent_qualification\...`；仓库只提交代码、配置、小 receipt 和聚合指标。
- 本轮起点磁盘收据：D 可用约 3.37 GiB，Z 可用约 24.49 GiB。D 低于 2.5 GiB 或 Z 低于 12 GiB 时停止新增下载/构建。
- Docker VM 上限约 8 GB；若宿主可用内存不足以保留 3 GB 安全余量，不启动 OpenSearch。不得同时运行 Docling 重任务与多个检索服务来制造不可解释的 OOM。
- 不删除 `D:\FIN_Insight_Agent\data\indexes`。只有成熟检索候选已经证明可重建、且空间确实成为阻塞时，才按 Owner 已授权的精确范围另行删除其下文件并保存 receipt；删除前必须再次验证绝对路径和依赖。
- 任何失败使用新 attempt ID，保留日志和产物；不得覆盖失败或降低 validator。
- 候选若不能保留 FIN canonical identity/lineage、需要不可接受的许可条款、无法固定版本/镜像 digest、资源超预算，立即 `HOLD` 或 `REJECT`，不进入正式依赖。
- R14 保持冻结；不创建 R15/R16，不启动 formal、Evidence/S2 authority、S3/report/product/release。

## 6. 最小实施形状

所有成熟组件通过 adapter 接入，禁止把供应商对象直接扩散到 FIN domain kernel：

```text
real source
  -> mature parser / validator
  -> S1 adapter
  -> FIN CanonicalDocument / Object / Candidate contracts
  -> mature searchable store
  -> FIN retrieval policy + hard filters
  -> Candidate (not Evidence)
```

旧实现的默认处置不是立刻删除：先 `BASELINE`，新候选胜出后转 `COMPATIBILITY/REGRESSION`，稳定迁移后才 `RETIRE`。新 adapter 必须可替换、可显式版本化、保存 upstream version/digest 和原始 locator。

## 7. 本轮交付与完成定义

本工作包只有在以下内容同时存在时才算完成：

1. 当前代码与数据合同的 `RETAIN / WRAP / REPLACE / REGRESSION / RETIRE` 矩阵；
2. 每个关键能力的成熟 longlist、shortlist、排除理由、版本/许可/资源/退出结论；
3. 至少一条真实 DELL iXBRL 的 Arelle receipt；
4. 至少一份真实财报 PDF 的 Docling 与旧基线对照 receipt；
5. 当前 34,199 objects + frozen embeddings 在候选检索底座中的导入、过滤、重建和 development retrieval receipt；
6. 若资源门允许，再有 OpenSearch challenger；不允许则明确 `HOLD_RESOURCE`，不伪造横评；
7. 一次独立只读审计、测试通过、Project OS 更新、clean commit 与 push。

首轮没有达到这些条件时，状态只能是 `IN_PROGRESS` 或 `BLOCKED_WITH_EVIDENCE`，不能写成迁移完成或产品通过。

## 8. 执行日志

- 2026-09-01：在 clean `86e317...` 上冻结本门；旧 S1 targeted baseline 为 `44 passed`。开始并行进行代码责任审计、成熟栈官方资料调研和 Z 盘 qualification inventory。
- 2026-09-01：确认 `D:\FIN_Insight_Agent\data\indexes` 不是纯缓存；当前 manifest 仍引用其中一个 `records.jsonl`，贡献 1,512 个 retrieval children。Z 盘空间仍可用，因此没有执行 Owner 预授权删除。合法顺序仍是先迁移 source artifact、更新 manifest、证明可重建，再删除真正 cache。

### 8.1 Arelle：能力可用，但当前 source capture 不完整

- 隔离环境安装 `Arelle 2.44.5`。
- 冻结输入 `data/raw_private/sec/2023/ai_servers_enterprise_hardware/DELL/10-K.html` 为 4,274,861 bytes，SHA-256 `85034ff84bd8a913fd93d0173793a4a2f045e9c249b6a5805a08fc3391e1ec76`。
- 本地 DELL 10-K 主 HTML 产出了 2,397 行 `facts.csv`，但 `contextRef`、`unitRef` 和 `value` 非空计数均为 `0`；同一 accession 的 `dell-20230203.xsd` 和相关 linkbase/DTS 文件没有被 capture，验证另产生约 2,465 个错误。因此这不是 2,397 个可用 facts，更不能签成 XBRL validation pass。
- 不可变本地 attempt `20260901T0135Z-a1` 的 `facts.csv` SHA-256=`0022c76e4da70f817720192f597deaf7a4fe426071dc538ad1ae00f0154849d7`、`validation-log.xml` SHA-256=`b66592ee133c2e90e86f4b27fc4258a8424fe7c7296fa389cb0d202c102acfea`；日志 2,468 entries（2,465 errors／3 info），其中 2,397 `missingReferences`。这些是原始失败产物，不冒充为标准化 qualification receipt。
- 直接补抓 SEC URL 的独立 attempt 返回 HTTP 403；没有绕过 SEC 访问规则，也没有把外部补源偷偷混进当前输入。
- 不可变补抓 attempt `20260901T0142Z-a2` 的 `validation-log.xml` SHA-256=`d974ebb5555c5274b1e2c6244662fc31c87289bb1f2e58fd82ccd42bdb7b279d`，包含 3 个 `webCache:retrievalError Forbidden` 与 1 个 `FileNotLoadable`。
- 当前决定为 `HOLD_SOURCE_CAPTURE_PACKAGE`，不是 `REJECT_ARELLE`：通用解析器没有被证明有问题，最早失败层属于 source capture/package completeness。
- 下一次 Arelle 资格要求完整 accession/DTS/WARC package，并把 generic latest profile 与 SEC-compatible profile 分开；不得继续靠单个主 HTML 给 Arelle 补自研旁路。

### 8.2 pgvector：成熟存储底座通过，原生 FTS 不替代 BM25

- 固定镜像声明为 `pgvector/pgvector:0.8.6-pg16-trixie`；运行时实测 PostgreSQL `16.15`、pgvector `0.8.6`。
- `pgv1` 因 HNSW shared-memory 约束失败；`pgv2` 因资格脚本 SQL format/regex 错误失败；均保留为独立失败。
- `pgv3` 完成 storage/lexical qualification；`pgv4-restart` 在容器重启后再次读取，34,199 个 objects 的 canonical ID、payload 与 float16 embedding roundtrip 为零漂移，数据库约 194.84 MiB。receipt SHA-256 为 `378aa1b41a86d3b1eae559468551816eccf7b1b866489784e542b31ce31ec552`，result digest 为 `7442133c80e5c1afd4bfb09e3b9b2f06e1cc72269a5c8199f1a164f43ac4f264`。
- 18 条 development qrels 上，现有 Python BM25 为 top16 `13/18`、top64 `17/18`、MRR@64 `0.52577384`；PostgreSQL native FTS 为 top16 `8/18`、top64 `10/18`、MRR@64 `0.41245791`。
- 决定：pgvector relational/vector foundation 为 `ADOPT_PILOT`；PostgreSQL native FTS 仅为对照，不能替换现有 BM25。
- 证据等级限定为 `DIRTY_BOUNDED_ADOPT_PILOT_CANDIDATE / CLEAN_REPLAY_PENDING`；`pgv1` 只证明当前 HNSW shared-memory/resource profile 失败，不能写成 pgvector 产品缺陷，`pgv2` 的 runner format 缺陷已由同阶段后继 attempt 关闭。
- 边界修正：`pgv4` receipt 中的 OCI image digest 是 runner 的 expected constant，实际 runner 只从 SQL 观察到 server/extension version，没有读取 Docker image/container digest。因此目前只能签 PostgreSQL/pgvector 运行时版本与数据 roundtrip；exact OCI identity、exact replay argv 仍为 open，不能写成已证明。

### 8.3 Qwen 查询向量：真实模型推理通过

- 独立环境固定 Python `3.11.14`、Torch `2.7.1+cu118`、sentence-transformers `6.0.0`、transformers `5.16.1`、tokenizers `0.23.1`、NumPy `2.4.6`。
- `qwen1` 因缺少 `rank_bm25` 失败；`qwen2` 因 package-init 耦合缺少 `bs4` 失败；均未覆盖。
- `qwen3` 在本地 `Qwen/Qwen3-Embedding-0.6B` 上生成 18 × 1,024 float32 normalized query embeddings；18 行均唯一，重复运行最大差为 `0`，峰值 GPU memory `1,406,625,280` bytes，总耗时 `6.222s`。
- inference package digest 为 `6b2038c8c4b044a7feff6909abc6c84537abd4da2ce1ace9cf84e0c75ddefe66`；输出 embedding SHA-256 为 `b2b200d57188098b20df09a0d366441d685a2adf90a01bb6229ae33ce084188f`；manifest SHA-256 为 `225fb2787fcaf769c053cf35d5b41552c0e3a1f6859e04f23599e1881ce190d9`。
- 当前 v1.9 runtime prompt 是 `instruction + query`，没有另加 separator；本 attempt 明确记录 exact prompted-input digest，不把它伪称为旧 comparison prompt parity。
- 结论：本地 query embedding component execution 通过；上游 weight revision 仍需官方 manifest 进一步完成供应链证明。
- `qwen3` manifest 内已记录本节点的 `TokenBudgetBasis`，输出权限仍为 Candidate-only；它没有 Evidence、产品路由或生产 authority。`qwen1/qwen2` 是同阶段由 `qwen3` 关闭的缺依赖失败，不另造长期组件问题。

### 8.4 dense/hybrid：candidate union 通过，朴素 RRF 不通过最终排序

- `dense1` 完成初版 development evaluation，但缺最终 decisions 与 start/end implementation binding，因此是被后续取代的 provisional evidence，不是 execution failure；`dense2` 技术运行通过但绑定的是修正前脚本；最终权威 attempt 为 `20260901T0330Z-dense3`。
- `dense3` receipt SHA-256 为 `609726772fddd5e43dd1b2ac7ba3b96e9e428d5ec82e2a722829db2e2416947`，result digest 为 `aba5d797c25d3d9f0829d004be1e926123bc10e65a81a1438cbb89d0b7b2b630`。label-free candidate artifact SHA-256 为 `38773035f0b6cb5349eeba7fd6806383837887c069173a60fe1c1954f7acc95c`；目标标签在候选冻结并重读后才 join。
- NumPy exact 与 PostgreSQL exact 全序、分数和 target rank 一致：top10 `14/18`、top16 `16/18`、top64 `17/18`、MRR@64 `0.29880212`。
- pgvector native halfvec 结果与 exact 候选相同，target loss 为 `0`，MRR ratio `1.0`。
- BM25 为 top10/top16 `13/18`、top64 `17/18`、MRR@64 `0.52577384`。
- BM25 + dense 的 product union 召回 `18/18`；但简单 RRF（k=60）为 top10 `12/18`、top16 `16/18`、top64 `18/18`、MRR@64 `0.39492918`，低于 BM25，并把多个 BM25 rank-1 case 下沉。
- 决定：pgvector exact/native halfvec 与 BM25+dense candidate union 为 `ADOPT_PILOT`；简单 RRF final order 为 `HOLD_QUALITY`。这意味着成熟底座已经能扩候选池，但 FIN 仍需拥有 hard filters、candidate policy 与最终质量门；不能把通用 fusion formula 当领域判断。
- 上述 `ADOPT_PILOT` 同样限定为 dirty bounded development candidate；18/18 是 exposed development source-target union，不是 blind、exact-object relevance、Evidence 或产品通过。HNSW=false，且没有因只有正标签而伪造 precision/nDCG。
- candidate ceiling 已到 `18/18`，因此 reranker 从“因召回不足而非法”变为后续可资格化；这不等于本门已经启动 reranker，也不授权 4B、Evidence 或 S2。

### 8.5 Docling：环境与模型已落盘，真实 PDF 尚待 clean replay

- 在 `Z:\FIN_Insight_Agent_qualification\20260901_s1_mature_data_plane_v1` 建立独立环境 `docling-2.124.0-torch2.7.1-cu118-py311`；没有修改 Qwen 环境。两套环境的大型 Torch DLL 使用 NTFS hardlink 复用。
- Docling 环境实测版本：Python `3.11.14`、Docling `2.124.0`、docling-core `2.92.0`、docling-ibm-models `4.0.0`、docling-parse `7.16.0`、Torch `2.7.1+cu118`、torchvision `0.22.1+cu118`；CUDA 可见但首轮 profile 固定 CPU。
- Heron 与 TableFormer accurate 已按上文不可变 commit 下载到 Z 盘，仅保留首轮所需 10 个非 cache 文件，共 `384,533,273` bytes；Heron weights SHA-256 为 `00333a43451945aaf89db8ca9c0a17e75d1537c17db60fdb91aa95f4c7929e0c`，TableFormer accurate weights SHA-256 为 `2a7d6c924b3cd12fb99a09280ca9c33a89c5d60b93253617d2e088c1a40374d9`。runner 对非 cache runtime tree 使用 exact allowlist，拒绝第二个 `tableformer_*.safetensors` 被 loader 不确定选择。
- 重新逐文件校验后的模型包 canonical digest 为 `c4cae17766d435a59ba701b8f496dbe08d25dce1e19219dee595e20815d29653`；冻结环境完整 104-distribution manifest digest 为 `ed0163bde48d7d4ccfe17b9cf108aeb84af3fc2bdf7c820bb84e456fdcd2abcd`。独立复核发现 `docling` 本身只是元包，真实 `docling/*` 运行时代码由 `docling-slim==2.124.0` 提供；runner 现绑定其 RECORD SHA-256=`5bdbcfda3a1459be02bc0de9494b002a664281ccf0eb328d3da8b3346d05fc57`，验证 `docling.__init__` 的分发归属，并逐一复算 269 个带 hash 文件（2,982,187 bytes）为零 mismatch。
- 没有下载 OCR、picture classifier、code/formula、VLM 或 TableFormer fast weights；首轮结果不能外推为 scanned/OCR PDF 通过。
- 真实控制输入已冻结为 DELL FY26 results：9 页、683,251 bytes、SHA-256 `17be3981929167a2c6033a75abe24159e4de624bbbb7261b66fd8b189680e2f9`。后续顺序为 DELL full control → Tencent targeted smoke/full → TEL landscape；IFX 2025 作为已有 human-reviewed anchors 的质量确认 slice。
- 当前尚未运行 Docling PDF conversion。原因不是继续规划，而是正式 runner/合同需要先进入 clean commit，且当时宿主可用内存低于 3 GiB safety line。资源不足时必须产生 typed `HOLD_RESOURCE`，不能冒 OOM 风险后把崩溃当组件质量。

### 8.6 当前证据等级与下一步

- pgvector/Qwen/dense-hybrid 的成功 attempts 发生在 HEAD `86e317...`、但 qualification runner 尚未提交的 dirty 工作树上，因此是强 development diagnostic evidence，不是 clean replay 或独立最终资格。
- 复杂度纠正：四个本轮 qualification runner 合计 `4,445` 行，四个 targeted test 合计 `653` 行；它们是用于复现外部组件资格证据的 lab harness，不是“薄产品 adapter”。禁止 `src/` 或产品 runtime 导入这些脚本，禁止把 receipt/orchestration 机制演化为新的产品平台。后续真正集成必须另建可替换的薄 FIN port/adapter；一旦 clean shadow 和必要回归已由标准测试承接，本 lab harness 应缩减或退出，而不是变成常驻架构。
- 四个资格执行器已按仓库 `requires-python >=3.10` 修正 UTC 时间写法；Python 3.10 下语法编译通过，四组 targeted tests 合计 `27 passed`。冻结 Docling Python 3.11.14 环境另外完成完整 distribution manifest、`docling-slim` 269-file runtime bytes 与 10-file model allowlist 复核；独立 API smoke 在不初始化 pipeline/不加载模型/不创建 attempt 的前提下 29/29 配置断言通过。Docling runner 还以原子 attempt claim、terminal receipt exclusive-create 关闭并发覆盖 P1，要求 `python -B` 禁止冻结环境 `.pyc` 写入，把 `sys.pycache_prefix` 与 TEMP/TMP/TMPDIR 收口到 attempt-local Z 盘缓存，并在 conversion 后重算 runtime binding。上述检查只证明执行器合同与 API 构造，不等于 PDF conversion pass。
- 作者分离最终复核确认上述并发覆盖、`docling`元包误绑与相邻`.pyc`读取三个P1均已关闭，修后版本 P0/P1=`0/0`；复核未运行真实 PDF、未读取 hidden/holdout expected outcomes、未修改文件。
- 下一步不是再扩写协议：完成独立只读代码/API 复核与最小 Project OS 投影，把本轮 runner 与本日志提交并推送形成 clean implementation；随后在资源门通过时运行 DELL 9 页控制 case，并与旧 `official_pdf.py` / `pdf_layout.py` 基线做结构、表格、provenance、耗时和资源对照。
- 在 Docling 控制 case 和 baseline comparison 形成前，不做 PDF adapter cutover；在 clean replay 与供应链/许可边界补齐前，不签 `ADOPT_PILOT_NATIVE_LAYOUT`。
- R14 继续冻结；不创建 R15/R16，不进入 formal、Evidence、S2、S3/report/product/release。

### 8.7 Clean提交后的首次Docling预检：资源门正确止损

- 四个qualification runner、四个targeted test与本日志已作为commit `dd84b0dd97402c8d3c93a62796384f9d26e8c655`推送到`origin/codex/fin013-dell-s1-s2-product-bridge`；执行前branch、HEAD、upstream一致，工作树干净。因此11:48所述dirty/untracked实现边界已被clean implementation替代，但先前pgvector/Qwen/dense attempts本身仍是其原始dirty-bound development evidence，不能被事后改签为clean replay。
- 首个clean Docling attempt为`Z:\FIN_Insight_Agent_qualification\20260901_s1_mature_data_plane_v1\attempts\docling_pdf\dell_fy26_results\20260901T042108Z-preflight1`，模式明确为`preflight`。它重新验证了DELL 9页输入、runner、Git、104-distribution runtime manifest、`docling-slim` 269个带hash运行时文件和10个模型文件；全部身份检查通过。
- 预检时D盘可用`3.349308 GiB`、Z盘可用`54.546925 GiB`，均高于冻结线；宿主可用物理内存为`2.435715 GiB`，低于`3.0 GiB`运行安全线。因此terminal status=`HOLD_RESOURCE`，reason=`free_memory_below_runtime_safety_line`，component execution=`NOT_STARTED`，adoption=`NOT_DECIDED`。
- 该attempt没有初始化converter、没有加载模型、没有解析PDF，conversion count仍为0；attempt内仅有`receipt.json`与空的attempt-local `runtime-cache/pycache`、`runtime-cache/temp`目录。receipt文件SHA-256=`b2c7e1c9c956d3fca11f9d39189433f113a1cc3f82dc6c829b3d180977b448ff`，内部result digest=`bf18655b31910c286a22e4ab68baf7a948c7bf2141caaf33dcf51b0a1281060a`。
- 结论不是`REJECT_DOCLING`或质量失败，而是宿主资源尚未达到已冻结的安全运行条件。不得降低3 GiB安全线、不得终止用户应用/WSL/Codex来制造通过、不得因为等待资源而转回自研parser。资源等待期间只做低资源、只读的本地完整DELL accession/DTS搜索与现有`official_pdf.py`／`pdf_layout.py`基线定位；可用内存自然恢复后必须使用新的attempt ID执行真实conversion，不得复用或覆盖`preflight1`。

### 8.8 DELL accession/DTS本地闭包审计

- 作者分离、只读搜索覆盖`D:\FIN_Insight_Agent`和当前Z盘S1 qualification lab；没有联网、没有修改文件、没有读取hidden/holdout expected outcomes。结果是本机没有可直接离线重放的DELL FY2023 10-K完整accession/DTS package。
- filing身份由`data/raw_private/sec/2023/ai_servers_enterprise_hardware/DELL/10-K.metadata.json`绑定：1,306 bytes，SHA-256=`977736652b5f99d038ea14efdaa288c56f7906265e7dc83ab819e15106d6342c`，accession=`0001571996-23-000007`，SEC path segment=`000157199623000007`，primary document=`dell-20230203.htm`，filing date=`2023-03-30`，report date=`2023-02-03`。同目录只有该metadata和已冻结的`10-K.html`。
- 主HTML唯一直接DTS入口是`dell-20230203.xsd`；获准范围内没有该XSD、常见`_pre/_cal/_def/_lab.xml` company linkbases、DELL XBRL sidecars、该accession的WARC/WACZ/ZIP/TAR或完整filing目录。现有非环境归档的成员名复核也没有该package；其他披露ZIP明确属于DART公司，不是DELL。
- 当前Arelle环境还没有本地SEC/FASB 2022 taxonomy cache，`plugin/validate`没有EFM validator，a1亦报告`Disclosure System "efm" not recognized`。这是公司DTS缺失之后的次级环境/profile缺口，不能覆盖最早责任层。
- 因此不得继续用单HTML重跑Arelle。下一合法输入是通过合规来源取得并冻结完整accession package，然后按公司XSD中的`import/include/linkbaseRef`递归求闭包；逐文件记录relative path/bytes/SHA、accession/canonical locator/capture metadata与整包manifest digest。补齐匹配的SEC/FASB taxonomy和EFM profile后，先做完全离线DTS closure preflight，再以新attempt分别报告generic XBRL parse与SEC EFM validation。当前决定保持`HOLD_SOURCE_CAPTURE_PACKAGE`。

### 8.9 既有PDF parser基线审计与最小执行选择

- 同一冻结DELL FY26 9页PDF没有既存legacy parser artifact；仓库按文件名和精确SHA只命中新Docling runner/test/worklog，Z lab只存在`preflight1`的`HOLD_RESOURCE` receipt。已有page 1/2 PNG不是9页parser baseline；现有complex-PDF canonical artifact属于IFX，不能冒充DELL对照。
- 当前最低资源、可直接复用的基线是`src/ingestion/official_pdf.py::parse_captured_official_pdf`：只依赖当前`.venv`已有的pypdf 6.16.2，读取683,251-byte PDF并逐页输出text、character count和digest；权限明确停在`parsed_source_only_not_evidence`。下一步不写新script，只作一次性函数级执行并将产物写入Z盘新attempt。
- layout-rich旧基线仍应复用`src/ingestion/pdf_layout.py::parse_captured_pdf_layout`，它能输出words/lines/bbox/table regions/footnotes/text blocks与quality receipt；但当前`.venv`缺`pdfplumber`及OCR闭包，且函数会在native text不足时自动进入OCR，不能虚构成native-only pass。待使用已经存在且可固定的依赖环境后再运行，不为本对照新增长期harness。
- `scripts/data_retrieval/parse_captured_official_pdf_layout.py`要求现成response-capture/source-spec并会复制raw body、编译objects；本case没有这两项，为跑对照而伪造它们是多余治理。`run_s1d_official_pdf_successor.py`会跨入Evidence/pack/S2，明确超出当前权限，禁止使用。
