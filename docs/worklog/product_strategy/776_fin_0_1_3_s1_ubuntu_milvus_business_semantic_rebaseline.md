# FIN 0.1.3 S1 Ubuntu Milvus、业务语义错误与外源补源重基线

日期：2026-08-09
归属：FIN 0.1.3 / S1
状态：Ubuntu Milvus dependency qualification 通过；qrels 业务内容复核 current；410 build 未授权

## 1. 用户纠正与本轮目标

用户补充了三项必须长期保留的产品／工程要求：

1. 本机已有 Ubuntu，可在 Linux 文件系统验证 Windows supplemental dense R1 的 Milvus Lite 失败；
2. 此后检索汇报不能只给 `16/18`、`3/18` 等数字，必须逐条解释搜到了什么、为什么不满足对应金融研究问题；
3. 外源检索不是取消项，而是本地检索和检索工具稳定后的补源层，必须回到当前 external `4/12` blocker。

本轮因此只做一个 1-vector、零 BGE、零网络、零模型的 Milvus portability canary，并对保存的 R2／qrels v1.3 做零调用业务语义审计。没有执行 410-vector replacement、ranking successor 或外源 live。

## 2. Ubuntu／WSL Milvus 结论

官方 Milvus Lite 文档将 Ubuntu 20.04+ 列为支持环境；本轮没有直接升级到新版本，而是为了做单变量归因，在 Ubuntu-22.04 WSL2 中使用与 Windows R1 完全相同的 `pymilvus 3.0.0 + milvus-lite 3.0`。数据库放在 Linux root filesystem，不放在 `/mnt/d`。

R5 真实经过项目 `MilvusIndexWriter`：

- create database / collection=`1/1`；
- insert batch / acknowledged vector=`1/1`；
- flush=`2`；
- close 后重新建立 client；
- reopen 后 collection exists、row count=`1`；
- metadata query 精确返回合成 identity=`1`；
- network／Provider／LLM／BGE／历史库写入／Evidence=`0`。

关键对照是：Linux 与 Windows R1 的 `milvus_lite/storage/manifest.py` SHA 都是 `59b45341...fcd6`，都使用 `os.rename`。Windows 在覆盖已有 `manifest.json` 时触发 `WinError 183`；Linux 同源码完成双 flush 和重开。因此当前证据支持“Milvus Lite 3.0 的 manifest 覆盖语义是平台相关失败”，不支持把它归因给 BGE、DeepSeek、410 条业务数据或 Writer insert 逻辑。

结果物化于 `configs/releases/fin_ia_0_1_3_s1_milvus_lite_ubuntu_wsl_portability_canary_result_v1_0.json`，digest=`dba81444...8130`。Windows 3.0 路径保持不合格；Ubuntu 路径只进入 fresh production-authority decision，不自动获得 410 build 权限。

## 3. 进入 Milvus 前暴露的环境问题

R1–R4 均未进入 Milvus，也没有写业务数据：

- R1：只安装 Milvus 的隔离 venv 缺项目依赖 `pydantic`；
- R2：安装当前 `pyproject.toml` 后，导入链缺 `rank_bm25`，但它实际被索引模块直接使用；
- R3：继续导入时缺 `beautifulsoup4`，但 ingestion 模块直接使用 `bs4`；
- R4：Windows→WSL 包装命令提前把 Bash `$HOME/$db` 展开为空，preexisting-path 安全门把解析成仓库根目录的路径拒绝；
- R5：补齐直接依赖、改用 literal Linux absolute paths 后成功。

因此本轮把 `beautifulsoup4` 和 `rank-bm25` 补进 `pyproject.toml`。这不是为了“让 canary 绿”而堆依赖，而是修复包声明与实际 import graph 不一致；完整重型研究依赖仍不因本 canary被静默安装到产品 Runtime。

## 4. `dense 3/18` 具体为什么低

R2 的 dense top-10 中 wrong owner、wrong period、cross-case 均为 0，所以不能概括成“搜出了别家公司”。逐行归因是：

- 8/18：正确 current 目标根本不在旧 Milvus，属于 index freshness，不是排序器已经看见后排错；
- 3/18：进入 top 10；
- 1/18：NVDA regulatory／financial reconciliation 的经营现金流目标只到 rank 16；
- 6/18：目标存在，但未进入 top 24，主要是同公司同期间的宽泛内容挤掉更具体证据。

业务例子：

- DELL／MSFT demand：正确目标是 Microsoft Intelligent Cloud／Azure 指标，用来支持企业 AI 基础设施需求；dense 前排却是 Microsoft 通用公司与 AI 概览。公司和期间都对，但“通用介绍”不能代替“需求证据”。
- NVDA regulatory／financial reconciliation：正确目标是经营现金流行；前排是 broader recent developments／objectives／challenges，导致具体财务 reconciliation 证据落到 rank 16。
- DELL issuer sparse：正确目标是当期业绩和管理层评论；同一 DELL 8-K 的法律、风险和泛化财务段落排在前面，目标落到 rank 12。
- MU regulatory sparse：正确目标涉及 strategic customer deposit／commitment 与扩产、资金和财务 reconciliation；宽泛制造风险、`Unaudited` 标签和通用财务段落排在前面，目标落到 rank 14。

这些错误要求不同修法：index missing 先建索引；same-company wrong section 需要 section／role 特征；具体数字表应保留 exact route；不能统一归因给 BGE，更不能只扩大 top-k 或上 reranker。

## 5. qrels 自身也有业务质量问题

Owner 之前接受 18 行，表示这些行可作为 ranking relevance label；本轮发现至少两行还不能作为 Evidence-content Gold：

- `DELL / supply / NVDA`；
- `MU / supply / NVDA`。

两行都选中 `...Q1FY27PRHTM::BLOCK_0003::CHUNK_0001`，可见预览从 `For further information, contact...` 和 disclaimer 开始，而 rationale 却声称该片段承载 manufacturing／supply counterevidence。文件、公司和日期相关，不代表这个 chunk 的业务内容足以支持该 Evidence Slot。

旧 qrels v1.3 和 R2 保持不可变、指标仍对该标签集有效；下一次正式 ranking 前必须审完 18 行，把弱目标扩邻、supersede 或退回 typed gap，不能静默改写历史。零调用审计为 `configs/releases/fin_ia_0_1_3_s1_internal_r2_business_semantic_error_attribution_v1_0.json`，digest=`cc041bf7...6b78`。

## 6. 外源检索的稳定产品拓扑

新顺序不是 local-only，而是：

`internal exact/object/BM25/dense/graph -> per-slot typed residual gap -> SourceHunter external supplement -> capture/date/identity/relationship/Evidence Gate -> unified Evidence Pack`

外源返回必须标记 `external_supplement` 与触发它的 residual gap，不能伪装成本地库原有能力。本地工具闭合后必须回到 external `4/12`，使用相同 DELL／MU／NVDA Query Facet 复验；没有完成补源闭环前，S1 与研报资料面都不能宣称完成。

## 7. 下一步

1. 先完成 18-row qrels Evidence-content requalification 与逐行错误账本；
2. 证明 WSL 能读取冻结 BGE 权重并使用 GPU／受控 CPU fallback，同时把 `pymilvus`、`milvus-lite`、Python／WSL 和 Linux DB path 全部绑定进 fresh authority；
3. 只执行一个新的 410-vector immutable build，不复用 Windows R1 working state；
4. 只读证明 410 entities 与 requalified target presence；
5. 再执行一次 unchanged-matrix sparse／dense／fusion，并按业务语义逐行报告；
6. 补齐 current-quarter exact／graph／本地工具；
7. 用真实 residual gaps 回到 external supplement；
8. 最后做 Evidence→Claim→Workpaper→Report 研究内容质量证明。

当前不应直接跑 410，因为 production authority 还没有绑定完整 Linux Runtime／BGE／Milvus Lite 指纹，qrels 内容复核也未完成。
