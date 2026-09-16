# 本地及受控试用的服务备份恢复

0.1.4 的维护工具协调既有项目/任务资料集备份、工作底稿 SQLite、HTTP 提交回执、私有运行审计，以及原生执行和模型派发预算 PostgreSQL。它使用 [SQLite 在线备份](https://www.sqlite.org/backup.html)、[pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html) 与 [pg_restore](https://www.postgresql.org/docs/16/app-pgrestore.html)，不新增执行队列或恢复调度器。

这是**停止写入后的维护快照**。它不提供跨库在线事务、增量 WAL/PITR、备份后的数据零丢失或生产高可用保证。恢复结果保持离线，只有检查通过后才由维护者重新开放服务。备份包含个人内容及私有模型审计，存放在受控、加密的外部备份位置，不能提交 Git；本工具不另造加密或云同步系统。

## 创建快照

1. 停止新请求入口、导入与同步，等待或明确暂停当前任务，解决原生 pending/running 状态；保留未知模型派发及其占用，不自动重试、清账。
2. 停止 BFF 和所有 Agent Server worker，包括另一 worker/设备的写入实例，保持数据库服务运行。工具要求 PostgreSQL 没有其他连接，拒绝原生排队/执行中的 run；SQLite 与审计在快照期间发生变化会使整个备份没有完成标记。此检查不替代维护者对所有实例的控制。
3. 明确实际路径，不依据目录名猜测。working_memory 取运行环境 FINSIGHT_WORKING_MEMORY_PATH；submission_receipts 取 BFF settings 所在目录下 submission-receipts/records-v1.sqlite；audit_root 取实际 settings。项目库、任务资料、公共知识库和财务库也取同一部署配置。已有原始来源包/外部数据卷需用其既有备份机制保留；本工具仅备份明确配置的公共检索文件、财务 SQLite 和已纳入项目/任务的原件，不推测其他数据卷。
4. 在私有 JSON 中填写下例，用新的目标目录执行。数据库客户端版本须与源 PostgreSQL 主版本兼容。宿主使用 libpq 的 PGPASSFILE/连接环境；Docker 可用 `prefix: ["docker", "exec", "-i", "你的postgres容器"]`，利用容器本地连接。不要把密码写进 prefix 或 Git。

```json
{
  "project_root": "/service/project-library",
  "task_root": "/service/attachments",
  "working_memory": "/service/working-memory/notes.sqlite",
  "submission_receipts": "/service/submission-receipts/records-v1.sqlite",
  "audit_root": "/service/calls",
  "public_library": "/data/retrieval_nodes.jsonl",
  "financial_mart": "/data/company_financial_facts.sqlite",
  "target": "/backups/new-service-snapshot",
  "maintenance_confirmed": true,
  "databases": {
    "native": {"database": "postgres", "user": "backup_operator"},
    "budget": {"database": "fin_budget", "user": "backup_operator"}
  }
}
```

```bash
uv run --no-sync python -m sec_agent.research_foundation.service_backup backup /private/backup-settings.json
```

完成的外层 manifest.json 才代表全部组件均已保存。失败目录保留排查，不在同名目录续写或拼接不同时间的快照。工具仅输出状态，不输出 PostgreSQL stderr；出现原生工具警告时停止，由维护者在私有终端诊断同一组件，不能把警告当成功。

## 恢复和启用

在隔离环境通过现有部署的角色初始化与预算 SQL 迁移建立**同名角色与权限成员关系**，用新密码；pg_dump 不备份集群角色和密码。恢复工具保留 dump 中的对象 owner 和 ACL，不使用 --no-owner/--no-acl。目标必须是两个尚不存在的数据库，不能复用线上库。Redis 仅作为临时通知，不用旧通知触发任务。

```json
{
  "backup": "/backups/new-service-snapshot",
  "target": "/recovery/new-service-root",
  "databases": {
    "native": {"database": "restored_native", "user": "restore_operator"},
    "budget": {"database": "restored_budget", "user": "restore_operator"}
  }
}
```

```bash
uv run --no-sync python -m sec_agent.research_foundation.service_backup restore /private/restore-settings.json
```

先校验所有文件摘要，再恢复资料关系并创建新数据库。任何失败都不会写外层 restore-result.json；已产生的部分目录/新数据库保留诊断，不自动删除，也不启用。成功状态为 restored_offline，不是服务已在线。

启用前按恢复结果配置：项目/任务目录位于 target/assets 下；BFF 的 settings 文件放在返回的 settings_directory（target/assets），提交回执已恢复到同目录的 submission-receipts，符合 BFF 的实际寻址规则。工作底稿和审计使用返回的 working_memory/audit_root，公共资料/财务路径见 assets.restore-result。更新原生、预算 DSN 以及宿主/容器资源挂载；不要混用原服务回执，也不要批量改写 checkpoint 或历史引用中的身份。

核对至少一条真实任务的 owner、thread/run/checkpoint、项目分配、资料版本/旧引用、底稿当前版与旧版；对照提交回执与账本的 received/unknown、known/held。恢复后的未知派发仍禁止重发；备份后曾继续运行的源服务产生的账单必须先单独核对，旧快照不能证明它们不存在。只有这些检查通过才显式开放入口、按任务恢复，不能“启动全部旧任务”。

## 工程证据与适用范围

隔离原生 Agent Server 资格使用两个 owner、并发读、同版本竞争修改、暂停检查点及预算/回执记录；新数据库恢复后检查角色权限与未知占用不变，再显式恢复原生暂停节点。图内无模型调用，故只验证工程恢复，金融结论及新资产在研究中的语义使用仍由真实研究任务验收。单机 SQLite 支持这一受控访问模式；跨主机共享写入和多人共同编辑同一项目的授权产品规则未由此实现。
