# 组织项目与成员：第一阶段

2026-09-24，接续 [Java 接入产品范围](../product/java_research_intake.zh-CN.md) 和 [组织资料空间](resource_spaces.zh-CN.md)。本批只交付新组织项目元数据、成员和前端入口；共享资料、Agent 输入、结果授权、审批与历史迁移未完成。工程测试使用静态数据，不调用模型；用户手工静态案例验收另行记录。

## 权限与兼容

| 对象 | 唯一权威 | 兼容行为 |
| --- | --- | --- |
| 旧个人项目、原生研究及原资料 | Python 原 owner/project 规则 | 不迁移、不添加组织成员副本、不改变旧路由或 ID |
| 新组织项目和项目成员 | Java / PostgreSQL | UI 使用 `scope=organization`，不交给旧个人项目表或研究接口 |
| 组织、空间和发布资源 | Java / PostgreSQL | 项目权限不授予空间权限；组织个人区保持本人可见 |
| 文本/文件/原生执行 | 原 Python 存储与 Agent Server | 本批不创建组织项目的 Python 影子项目或执行线程 |

权限输入来自 BFF 验证的用户身份，内部委托继续绑定 method、path/query、请求正文和短时有效期。浏览器不能指定 actor、organization_admin 或 can_manage。Java 每次查询当前有效组织成员及项目成员，不缓存授权。

角色：组织管理员隐式具备该组织所有项目的管理权限；项目 manager 可编辑、归档和管理成员，researcher/viewer 可读项目元数据及成员名单。项目管理不能移除组织管理员的权限；非组织成员不能获授权。`research_enabled=false` 明确表示本阶段没有团队研究执行。未来 researcher 的研究操作须在第三阶段按资料权限及成果规则重新接线，当前角色名称不代表已开放执行。

组织移出只改变有效成员关系，保留项目记录、成员记录和历史审计。所有查询连接当前 `active` 成员，离开后失效；恢复已移出的组织成员尚未开放。归档用于整理，不删除、撤销成员或终止任务。读取按请求授权时点决定，不能收回已返回到浏览器的内容；刷新或导航重新请求，拒绝时清除该页内容，不宣称主动实时撤回。

个人与组织项目属于不同权威空间，即使 ID 字符串相同也不代表同一个对象；组织 URL 不回退到个人项目。原个人研究入口始终只认 Python 当前身份的个人项目，不会因 Java 成员资格获得组织资料。后续研究接口必须显式承载归属类型，不能用裸 project_id 猜测。

## 数据与接口

Flyway V3 增量新增 `organization_project`、`organization_project_member`、`organization_project_audit`，不改 V1/V2 校验和和原记录。组合外键约束成员的组织与项目组织一致，组织成员外键约束成员身份存在；有效状态由业务授权检查。迁移不依赖私人数据或开发机器路径。

BFF 仅在现有资料空间配置条件全部满足时开放：`FINSIGHT_RESOURCE_SPACES_ENABLED=1`、`FINSIGHT_AUTH_MODE=oidc_product`、已配置 Java 业务地址/共享凭证。`business/config` 增加 `organization_projects`，保留 `team_collaboration=false`。本阶段沿用同一部署开关，不另造一套登录。

| BFF `/api/v1/business/workspaces` 下的路径 | 行为 |
| --- | --- |
| GET `/projects?organization_id=&archived=false&query=&offset=0` | 当前身份可见项目，按创建时间 DESC、ID 稳定分页；每页 30，next_offset 可空 |
| POST `/projects` | 组织管理员创建；`id, organization_id, name, description` |
| GET `/projects/{id}` | 当前角色、can_manage、revision 和项目说明；不可访问 404 |
| POST `/projects/{id}` | 管理者提交 `revision, name, description, archived`；旧版本 409 |
| GET `/projects/{id}/members` | 可访问项目的有效成员及组织管理员 |
| POST `/projects/{id}/members` | 管理者提交 `revision, subject, role`；role=manager/researcher/viewer/remove |

没有该前缀下的 prepare/start/resources/access 路由。Python 白名单明确拒绝这些路径。创建失败或响应未知不自动重试；浏览器保存当前身份与内容对应的 UUID，相同内容手动重试使用原 ID。服务端保存初始语义请求摘要，与当前可变项目字段分离：重试只回读，不能覆盖后续编辑/归档。不同创建内容复用 ID 返回 409。

项目写入使用 `TransactionTemplate`。先锁所属组织行，再锁项目行，核验当前成员/角色/revision，再修改并写审计，事务内没有远程 HTTP。组织移出已有同一组织行锁，因此移出与项目授权变更串行，不能在移出已经提交之后靠旧检查完成授权。所有项目内容/成员修改提升同一个 revision，避免交叉覆盖；一个修改成功，另一个需重新读取。首阶段组织级写锁较粗，未宣称高并发吞吐；后续量测有必要时再细化锁粒度。常规读取无需该写锁。

审计保留项目、操作者、动作、目标、版本与时间；重复创建不追加重复 create 审计。当前审计用于数据库核查，没有对用户开放审计浏览页。

## 静态验收与学习入口

先使用隔离数据库和已有登录方式创建组织，准备小王（组织管理员）、小李和小陈（普通组织成员）。这些是人工合成案例，不写入默认产品或部署数据；测试中的认证主体替身不能代替真实 OIDC 供应商验收。

| 案例 | 操作与预期 | 对应概念 |
| --- | --- | --- |
| 项目归属 | 小王创建项目；小李未加入时列表和直接链接都不可见。加入 viewer 后可读，不能改名或加成员 | 认证与资源授权分离，后端校验 |
| 管理分工 | 小李改为 manager 后能给小陈授予 researcher；三种角色均无团队研究启动入口 | 业务角色、渐进开放 |
| 权限独立 | 项目 manager 仍不能读尚未获权的团队资料空间，个人项目不自动出现团队资料 | 对象边界、避免间接越权 |
| 两人修改 | 两窗口读取同 revision，分别修改；第二次 409，刷新看到第一个人的结果再决定 | 数据库事务、行锁、版本冲突 |
| 创建响应丢失 | 重试同请求/同 ID 只得到原项目；编辑或归档之后重试创建，不恢复旧字段 | 幂等语义与可变状态分离 |
| 成员离开 | 移出项目或组织后，刷新/直接 URL 失效，项目仍在；Java 重启不恢复权限 | 持久状态、每次请求核权 |
| 兼容 | 个人项目旧入口、资料和研究不变；组织项目页不会发个人项目写入或研究调用 | 渐进迁移、明确权威 |

可复现工程检查：

```bash
cd apps/business-service
./mvnw verify
# Windows: ./mvnw.cmd verify
# 回到仓库根目录，显式指定刚构建的 JAR（测试需 Docker、Java）
# FINSIGHT_INTAKE_TEST_JAR=apps/business-service/target/business-service-0.1.0.jar
uv run --no-sync python -m pytest -q tests/integration/test_resource_spaces_stack.py tests/test_resource_spaces.py tests/test_java_research_intake.py tests/test_project_workspace.py
cd apps/workbench/frontend
npm run typecheck
npm run build
npx playwright test --config playwright.public.config.ts organization-projects.spec.ts project-workspace.spec.ts resource-spaces.spec.ts
```

Java 测试使用真实 Spring HTTP、Flyway、Testcontainers PostgreSQL；跨语言测试使用实际 BFF 签名请求、Spring、PG，并检查重启和原 SQLite 资料隔离。浏览器测试使用合成 API 验证角色交互、冲突、撤权、未知响应和桌面/移动布局，不冒充实际服务全链验收。

本次结果：Maven verify 13 项通过（含已有 9 项、组织项目 3 项和 V2→V3 增量迁移 1 项）；上面 Python 命令首轮 13 项通过，其中 1 项为实际签名/重启集成。随后新增部署开关与登录模式门禁，`tests/test_resource_spaces.py` 6 项通过（包含新增 1 项）。浏览器四组相关测试首轮 17 项通过，完善组织项目切换入口与空路由提示后，受影响组织/个人项目 7 项再次通过。TypeScript、生产构建、活动基线及秘密扫描通过。构建保留已有大 chunk 与第三方 PURE 注释警告。未调用模型、embedding、检索或生产服务；这些结果不等同于真实 OIDC 供应商、多用户生产容量或金融研究质量验收。

部署仍遵循 Java 接入原配置，仅增量迁移并重新构建前端；不自动部署。回退页面/BFF后保留 V3 表和数据，不执行破坏性 down migration。联合备份需包含业务 PG 和既有 Python 存储；本批不宣称完整灾备或生产容量验收。

下一批先做项目与空间资源关联，沿用 project 权限与 source 权限分别核验；第三批再做 Agent 使用和结果范围，审批在后。
