# 不可变知识库的 Docker 原生卷

此配置只迁移已发布 SQLite 库及 manifest，不重建 chunk 或向量。Windows 主机上的 BFF 继续读取原发布文件；容器使用经 SHA 校验的相同副本。原文件和旧镜像保留用于回退。每个发布版本使用单独命名卷，不覆盖已发布卷。

先用已有部署命令构建本地 API 镜像。准备阶段显式复制一次，联网关闭、禁止自动拉取镜像；已有卷仅验证，不改写：

```bash
python -m scripts.deployment.native_library --library /path/to/published.sqlite --volume finsight-library-release-id
```

可通过 `--image` 指定已存在的本地 Python 镜像。失败复制留下的未完成卷不被视为成功版本；检查原因后使用新的卷名，保留失败记录。不要把存在 Docker 虚拟盘当作已经使用原生卷，须查看实际容器 Mounts。

在私有 `host-settings.json` 中增加 `research_library_volume`，值为该卷名。原有 `research_library`、`research_library_rag_cache` 及 `container-settings.json` 中路径保持原值。可选 `research_library_verification_image` 指定本地验证镜像。部署 helper 会选择 `compose.research-library-native.yaml`，不能与原文件绑定 overlay 同时叠加。

`check` 和 `up` 在创建服务前完整核对卷内数据库、卷内 manifest 和主机发布版本 SHA；卷不存在、复制不完整或版本不同即失败。`build` 只构建代码，不要求卷就绪。首次验证会顺序读取整个文件，其耗时与服务就绪后查询分别报告。

```bash
python -m scripts.deployment.research_workbench check --settings-directory /path/to/settings --enable-research --fresh-only
python -m scripts.deployment.research_workbench up --settings-directory /path/to/settings --enable-research --fresh-only --no-build --api-only
```

`--api-only` 仅用于 PostgreSQL/Redis 已健康的既有环境，避免并行开发中改动它们的容器或挂载。切换前确认没有运行中的付费任务，并保存旧镜像标签及私有设置副本；服务重建不会主动重发失败模型调用。若使用 working memory 等其他 overlay，应保留原启用参数。

回退时移除 `research_library_volume`、恢复已保存的旧镜像标签，再用原绑定挂载启动 API。不要删除数据库卷、请求账本或向量缓存。只有同版本 SQL 库副本可以互换，其他版本必须按新的数据发布流程验证。向量矩阵与付费查询账本仍沿用已准备目录，不由本工具复制或重建。

冷启动、就绪后首次查询、暖查询、端到端模型调用分别计时；离线输出一致不等于金融答案正确或图关系完整。
