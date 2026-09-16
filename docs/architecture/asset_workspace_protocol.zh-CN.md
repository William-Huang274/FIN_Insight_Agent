# 资产工作区与研究交接协议 v1

状态：首版骨架实施合同，2026-09-16。资产工作区承担日常阅读、维护与问题准备；通用对话承担轻量问答；研究工作区承担明确任务。复用 HTTP/JSON、FastAPI/Pydantic OpenAPI、原生会话/任务接口、SQLite 事务与备份接口，不新建消息总线或 Agent 间 RPC 框架。

## 身份和数据库归属

- 用户身份由认证层提供，客户端不能传 owner。项目权限仍由 ProjectLibrary.scope 校验。
- `AssetRef` 包含 `project_id / kind / asset_id / version_id / digest`。文档 asset_id 是既有版本组 identity，version_id 是不可变 UPLOAD ID；SEC asset_id 是 CIK，version_id 是快照 UUID，digest 由原始来源 hashes 确定。展示用 v1/v2 不充当引用身份。来源时间、期间和单位仍由源记录拥有。
- 本版正式适配项目文档、保存报告、SEC 快照；公共知识库和财务数据库保留既有查询入口。未来增加 source adapter 时必须保留稳定版本/查询快照和权限，不允许仅用名称或“latest”作为任务输入。实时行情/新闻尚未接入此协议。
- 项目 SQLite 继续拥有正文/原件、项目与版本关系。新增 `asset_contexts` 保存用户明确提交的问题、精确 AssetRef、个人记忆快照及协议版本；不复制资产正文、不保存模型私有推理。个人偏好复用 WorkingMemory 版本存储，在同一项目库 SQLite 中使用 owner + 个人专属 workspace/actor 隔离，不创建第二套记忆引擎。
- 原生 Agent Server 继续拥有会话、运行、checkpoint。native thread metadata 记录服务端生成的 `asset_context` 快照；实际资料沿既有 task attachments / financial snapshots 复制，并以 preparing/ready 状态控制后续运行。

## 通信与版本规则

`POST /api/v1/asset-workspace/contexts` 接收 `schema_version=asset_context.v1`、一个项目中的 refs、question 和 memory_version。服务端重新检查身份、来源版本、摘要与当前记忆版本，生成不可变 context_id。`GET /contexts/{id}` 按 owner 回读，另投影当前资料是否已有新版本/被撤销。失败不改变源资产。

`POST /research-sessions` 与 `POST /conversations/drafts` 增加可选 `asset_context_id`，消费同一个已保存协议；客户端不能另外提供相互矛盾的 question/project_materials。服务端解析 refs，通过原有副本流程创建草稿，不调用模型。提交凭证沿用已有 Idempotency-Key/SubmissionReceipts，未知请求不自动重发。

初版一次交接限定同一项目，合计最多12个引用，其中最多1个SEC快照；首版页面每次选择一个资产。版本策略为 pinned：新任务使用用户明确选择的版本，后续上传或修改不会静默切换旧任务。启动/读取仍复查来源使用权限。接收方运行上下文得到问题、引用身份和个人记忆快照，用户记忆只表示偏好/假设，不授予权限或事实权威。当前任务明确要求优先于长期偏好。单 Agent 的财务工具优先使用本任务所选快照，避免误查部署默认库；回执和数字来源记录原项目及快照身份。

用户修改个人记忆采用 base_version 乐观并发；冲突返回409，保留输入，不覆盖他人新版本。清空通过既有版本化 tombstone。首版不自动从聊天推断个人信息；已提交任务保留提交时快照，自动增量同步及运行中采用更新的阶段规则后续独立实施。

## 首版可见流程与边界

独立 `/workspace/assets`：项目资产列表按资产分组，正文/数据居中；版本历史按需展开。右侧小助手入口保存资产问题和版本化上下文，可准备研究草稿或准备通用对话；明确“准备未调用模型”，模型问答仍使用现有通用对话界面。先验证真实交接，不以伪造回答冒充助手能力。用户可主动维护个人记忆、添加Markdown资产及提交修订。

跨区后可回到原资产工作区和保存的问题；原生任务输出继续走已有报告保存路径。多轮助手对话自动提炼研究交接、所有资产类型统一编辑、实时行情/新闻、主动提醒、运行中自动定向重算尚不在本版骨架范围。

容量沿用此前本地试用限制：每项目最多12个文档版本、总原件80MiB，单文件20MiB；SEC最多12次更新。修订占用版本数，超限不会清理历史。长期大库的独立配额、分页/索引、多人共享项目与负载验收必须另行完成，当前验证的是用户隔离和并发冲突保护。该限制不应作为上线产品的长期容量设计。

## 本地持久化与恢复

新增数据落原项目数据库，利用原生事务/唯一约束/有界读取。备份使用 SQLite online backup，复制快照引用的不可变 SEC 原件并记录校验清单。恢复只到新目录，校验完整性后再由部署者切换；不覆盖运行中数据库。恢复验收覆盖项目、文档历史、个人记忆、交接记录及SEC原件。原生任务checkpoint和任务附件的生产级联合备份、跨机切换及存量绝对路径重绑定仍需另做部署资格，不能把项目库恢复称为整个研究系统容灾完成。

```bash
uv run --no-sync python -m sec_agent.research_foundation.asset_backup backup /path/to/project-library /path/to/new-backup
uv run --no-sync python -m sec_agent.research_foundation.asset_backup restore /path/to/new-backup /path/to/new-restored-project-library
```

路径必须由部署者指定；目标必须不存在，备份与恢复均拒绝覆盖。复制/校验失败保留现场，只有带完整清单且校验通过的目录可恢复。恢复不自动改应用配置，也不自动重启服务。

## 验收

真实BFF/SQLite/浏览器验证：资产分组阅读和修订；个人记忆跨浏览器读取/冲突；精确版本进入通用对话和研究草稿；另一owner拒绝；摘要伪造/未知协议拒绝；撤销后阻止交接；原生创建失败不启动模型；备份恢复到新目录后身份/版本仍一致。runtime消费使用脚本模型/定向测试，不恢复付费研究诊断。
