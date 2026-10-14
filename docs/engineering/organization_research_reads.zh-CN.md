# 组织研究的当前读取权限

组织研究使用独立的只读 API。Java 管理当前项目及固定输入的可见性，Python BFF 验证原生 thread 的冻结身份，并复用现有公开投影和报告导出器。原个人研究入口仍拒绝组织 thread；不开放组织启动、修订或接续的浏览器操作。后续已接入项目“成果”页与按权限过滤的研究列表，见[显式接续与成果入口](organization_native_continuation.zh-CN.md)。

## 权限规则

- 项目 viewer、researcher 或 manager 必须同时具有全部固定输入资料的当前访问权。项目成员资格不授予源空间权限，不能只核对被点击的那条引用。
- 读取不要求是创建人，也不要求 researcher。创建人退出后，其他符合上述条件的成员仍能读取；不能用创建人的服务身份代替读者。
- 关闭执行绑定不删除授权成员的历史读取能力。撤销项目/组织成员、源空间访问、发布资源或对应关联后，后续读取拒绝；固定版本身份变化也不能自动切到新原文。
- “可以下载”不等于“审批通过”。已经交付给用户的文件无法通过接口撤权追回。本批不实现下载文件的外部管控。

Java 内部 `GET /v1/workspaces/projects/{project}/execution-bindings/{id}/read-access` 复用准备单的单条 SQL 可见性规则，检查项目与每一项固定输入。返回 `organization_research_read.v1`、当前 reader、固定准备命令及配置摘要、Java 已关联的 run ID。这是当前检查结果，不是可缓存、转交或用于执行的 bearer 凭证。该内部路径不加入通用浏览器业务代理白名单。

## BFF 只读入口

需已配置业务服务、独立 OIDC 身份及组织空间功能；沿用现有签名委托和单机回环通信配置。前缀为 `/api/v1/organization-projects/{project_id}/research/{execution_id}`：

| 路径 | 行为 |
| --- | --- |
| `GET /`（无尾斜杠） | 公开研究状态，所有操作能力标记关闭；不读个人附件、个人记忆或私有消息 |
| `GET /report` | 当前报告；可传 `checkpoint_id` 读取该 thread 的历史快照，仍检查当前权限 |
| `GET /source?source_id=…&offset=…` | 已提交报告/综合中的保存引用，保留来源字段、期间及单位，文本每页最多16000字符 |
| `GET /report/export/{md,pdf,docx,pptx}` | 复用无模型导出器；完成渲染后再次授权，再返回文件 |
| `GET /runs/{run_id}/events` | 只接受 Java 关联的 run；支持 `Last-Event-ID`，复用公开事件过滤，不返回原始消息 |

BFF 在读取 SDK 前、读取后和响应序列化/渲染后重新核对授权；全部成功响应使用 `Cache-Control: no-store`。每次事件输出前重新核对，不因流建立成功就永久放行。若撤权或授权服务故障发生在流建立后，结束流且不发送已缓冲的下一条业务事件；无事件的空闲流不会额外启动后台权限轮询。已返回的内容无法撤回，跨 Java、原生存储和客户端之间没有全局事务承诺。

来源接口本批限定为 `saved_citation_snapshot`。它不等于重新读取完整原件；未绑定的 source ID 返回404，同一 source ID 对应冲突内容返回409。原文扩展应继续接固定组织原件导航，不能回退个人 `CaseArtifacts` 或宿主公共库。期间、单位、来源正确保留也不能证明金融结论正确。

## 可复现验收

```powershell
uv run --no-sync python -m pytest -q tests/test_organization_research_reads.py tests/test_organization_native_start.py tests/test_organization_native_drafts.py tests/test_organization_research_inputs.py tests/test_resource_spaces.py tests/test_research_session_bff.py
# apps/business-service；需要 Docker，使用临时 PostgreSQL
./mvnw.cmd verify
```

Python 用例通过实际 BFF 路由、静态 SDK 状态和真实四种导出器验证权限前后检查、历史报告、引用冲突、配置不匹配、撤权期间的事件过滤及拒绝个人入口。Java 用真实 PostgreSQL 验证 viewer 缺少源权限时拒绝、获授权后读取、不能启动、关闭绑定后读历史、创建人离开以及读者源/项目资格撤销。

`tests/integration/test_organization_graph_native.py` 继续使用隔离五服务和脚本 provider，增加真实 OIDC 替身 viewer 到 BFF/Java/原生状态的读取、服务重启后回读，以及源撤销后所有只读入口拒绝。该实际图只产出预研究，没有伪称已生成完整报告；四种报告导出另由明确标记的静态报告测试。没有真实模型调用、真实 OIDC 验收或金融质量结论。

2026-10-14 验收：119项Python相关回归通过；追加6项读取授权响应错配测试后，只读模块19项通过（合并覆盖125项，不重复计数）。Java真实PostgreSQL共29项通过，0跳过。五服务真实组织图1项113.33秒通过，含viewer授权/重启/撤源拒绝；3个原生run、5次脚本响应，0真实provider。活动基线、秘密扫描和差异检查通过，未更新现有部署。
