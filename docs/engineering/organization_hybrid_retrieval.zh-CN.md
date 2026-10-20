# 组织授权下的已准备向量与关键词混合检索

本片验证已有资料如何通过 Java 当前权限进入 Python 检索：先限制候选资格，再排序，最后从相同固定原件生成摘要和引用。静态旧案例可以验证这条执行路径；不能证明模型研究质量或生产容量。

## 接入与范围

Java 仍是成员、项目、来源权限及执行绑定的唯一权威，沿用现有 `/v1/runtime/organization-executions/{id}/access`。不新增 Python 成员表，不让模型指定 owner、组织、索引目录或缓存身份。

`OrganizationDataFactory` 接受可选的服务器 `retrieval_root`；原生组织入口仅从宿主环境 `FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT` 注入。负责人、专家与复核经该工厂创建的 MCP 来源工具使用同一导航。没有此配置时保留原本的组织词法检索；配置后索引/查询缺失或校验失败会停止该次搜索，不回退到宿主公共库或词法结果。部署没有自动切换。

旧 v1 索引保持**已准备向量及已准备查询**的无提供方通道；新的自然语言查询会明确返回 `organization_retrieval_query_not_prepared_no_provider_fallback`。新增 v2 不可变 release 可绑定 Java 准备单，服务器显式设置 `FINSIGHT_ORGANIZATION_QUERY_EMBEDDING=qwen` 后，允许同模型的新查询向量；未配置、提供方失败或结果未知均明确失败，不自动重试或静默回退。费用回执、范围缓存、真实原生联调及并发/召回边界见[索引发布与检索验收](organization_capacity_and_retrieval_qualification.zh-CN.md)。没有启用远程 rerank。

## 数据、排序和缓存

1. Java 返回固定 manifest，Python 校验身份和摘要，并按现有原件存储校验每个 AssetRef。文档身份绑定资源和版本；索引准备使用当前组织导航的相同文本投影和节点 ID。
2. 服务器按规范组织 UUID 选择独立索引目录。发布记录模型、维度、节点/文档身份、正文摘要、向量矩阵摘要与来源说明；重复发布不覆盖旧目录，换版使用新 release root。准备工具不生成任何向量、不调用提供方。
3. 请求中的文档/节点过滤和固定输入集合共同确定可用节点。核对节点正文摘要及发布身份后，**先选取获准矩阵行，再计算余弦相似度与 top-K**。同索引内未选资料不能占用候选名额。
4. 复用现有 BM25，合并最多 24 个向量候选和 12 个词法候选，采用本地 RRF（常数 60）排序。没有远程 rerank、图扩展或全库搜索。返回候选诊断只含本次获准 ID。
5. SQLite 排名缓存只保存三组 ID（向量、词法、最终顺序）。键包含当前完整授权响应摘要、执行/项目/固定输入、索引内容摘要、查询摘要、节点版本及排序策略版本。不同组织分目录，不同执行和查询范围分键。
6. 缓存命中仍须重新核权、读取并核对原件、校验索引和候选集合；摘要现场由原文生成。缓存中的越界 ID 被拒绝，不做过滤后继续返回。引用读取仍逐次核权并检查原文身份；检索预览不能作为已读引用。

v2 索引 release 通过 BFF 校验原件投影和当前权限后在 Java 登记，准备单可选择 `retrieval_release_id`，固定模型、维度及索引/矩阵摘要；发布新版本不改写旧准备单。旧 v1 仍使用宿主显式配置，不能获得 v2 的发布版本保证。每次结果记录索引摘要，换 release 不复用旧排名缓存。索引目录需允许创建本地 ID 缓存；原件与源公共索引不被改写。

排序、缓存写入及最终输出前再次核权。扫描期间撤权导致整次工具失败；已返回的数据不能被撤回，也不声称消除了最后一次检查与响应之间的时间窗口。索引文件和缓存是宿主受控存储，不是模型可编辑的输入；本片不提供磁盘加密、恶意宿主防护或跨机器发布服务。

## 历史案例复现

`scripts/data_retrieval/prepare_organization_hybrid_cases.py` 从同一发布库的实际 `context + newline + body` 提取文本副本，并复用该索引的向量矩阵和成功查询回执。核验原库 SHA256、矩阵/映射摘要、候选正文摘要；源库、索引、提供方缓存只读。每题保留两个真实片段，挑选较弱匹配作为组织 A 的固定输入，较强匹配存在物理索引但未授权给本次执行。组织 B 固定另一个片段。

```bash
python -m scripts.data_retrieval.prepare_organization_hybrid_cases \
  --library <published-library.sqlite> --index <prepared-vector-directory> \
  --replay <historical-replay-result.json> --cases <historical-queries.json> \
  --output <new-case-directory>

python -m pytest -q tests/test_organization_hybrid_retrieval.py
# 按真实业务验收文档配置独立 Docker 子网、端口、jar、输出目录。
# FIN_ORGANIZATION_HYBRID_CASES=<new-case-directory>/cases.json
python -m pytest -q tests/integration/test_organization_hybrid_stack.py
```

真实服务案例覆盖 BFF、Spring Boot、PostgreSQL、组织发布原件、真实历史向量和本地缓存。两个组织使用独立发布身份；同查询不同结果，交叉读取拒绝，A 撤权后缓存及旧引用拒绝而 B 仍可用，首题另验自有 Java 重启恢复。原生 Agent 不启动，身份是验收替身。另用合成小向量验证缺失索引、缺失查询、错误组织、内容/矩阵损坏、缓存注入和执行中撤权，并在实际专家 MCP 组合消费该通道。

结果、失败尝试及机器路径保存在仓库外。知识质量、广泛召回率、实时任意查询和生产吞吐不由这些权限案例推断。

## 2026-10-20 验收结果

四个历史题（OpenAI/Microsoft、Talen/Amazon、NVIDIA、SK hynix）共提取 8 个实际 1024 维文本向量和 4 个成功查询向量。每题创建两个独立组织，各自发布两份副本、只选一份；全部通过候选、摘要、原文、缓存、交叉读取与单边撤权检查。较高相似度的未选资料被排除在组织 A 的候选之外。实际分数和原文摘要保留在证据文件中。

真实 BFF/Java/PostgreSQL 场景首轮约 99 秒通过；完善向量格式校验后，阻断验收驱动外网连接的复验约 108 秒通过，仍为 0 次提供方调用。两轮不累计成独立案例数量。首题自有 Java 重启恢复通过；未启动原生 Agent、未切换共享部署。

相关组织/导航/MCP 回归 66 项通过；最终向量边界和共享读取协议回归 55 项通过，2 项既有外网探针因未授权而跳过。两组有重叠，不相加；新增权限用例没有跳过。基线、密钥扫描及 diff 检查通过。
