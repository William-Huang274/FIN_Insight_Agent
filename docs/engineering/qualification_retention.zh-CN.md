# 集成测试资源保留与退役

`fin-intake-native-*` 的随机项目名用于隔离测试，不再意味着永久保留环境。
沿用 Docker Compose 管理该项目的生命周期，不使用全局 prune。

- 成功的临时测试在最终 teardown 执行 `down --volumes --remove-orphans`。测试内的重启检查仍只 `stop`，不会清空待验证状态。
- 日志、回执、报告和原始失败记录保留在 attempt 目录。`continuous_library_copy` 登记的独立副本在成功退役后删除，原始封存输入与硬链接的其他路径保留；不递归删除整个 state 或资料目录。
- 失败测试、已接管的外部 fixture、带模型用量账本的运行，以及有 `retention-pin.json` / `retained-publication.json` 的环境保留。需要人为继续浏览或接续的测试，启动前设置 `FIN_NATIVE_RETAIN_REASON` 并填写具体原因。
- 每次最终 teardown 写入 `resource-retention.json`，包括项目身份、是否失败、原因、状态和被删除副本。保留项带七天后的 `review_after`；这是复查期限，不授权到期删除未知用量或仍被引用的成果。复查时根据当前运行状态和卷引用退役，不能只按目录日期删除。
- 已有部署不会因升级测试代码自动清理。当前生产、回退环境和封存 fixture 必须按其真实身份保留，不把过去测试创建的服务无条件当临时环境。

开发验收完成后应处理其 retention 回执。失败环境应修复接续或明确退役，不能通过不断新建同一故障的测试栈绕过恢复。持续运行的产品服务不调用测试 teardown。

离线检查：`python -m pytest -q tests/test_qualification_retention.py`。
真实 Compose 验收应使用空白临时卷，验证成功退出后卷与容器消失、失败退出后可恢复；无需调用模型或复制整套资料库。
