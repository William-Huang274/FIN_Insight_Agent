# 组织项目关联空间资料

2026-10-13。接续[组织项目与成员](organization_projects.zh-CN.md)和[资料空间](resource_spaces.zh-CN.md)，为项目资料页与资料库项目筛选提供同一套授权关系。后续已接入[组织研究输入准备](organization_research_inputs.zh-CN.md)；Agent 工具、报告及审批尚未接入，`research_enabled=false` 保持。

## 用户行为

项目管理员可在项目“资料”页选择自己有权阅读、且与项目属于同一组织的团队空间，将其中已发布的固定版本关联进项目。文件资料、知识库选取、数据库快照均可关联；它们仍是发布副本，不是实时数据库连接或整套知识库检索授权。

关联不复制正文、不重新发布、不改变源权限。一个发布资源可以关联多个项目；移除只影响指定项目的引用，原发布资料及其他项目关联保留。个人区资料须先经现有明确发布流程进入团队空间，不能直接关联来绕过个人区默认本人可见的边界。

每个成员看到的是“当前项目访问资格 ∩ 当前源空间阅读权限 ∩ 有效发布 ∩ 有效项目关联”。无源权限的条目不会出现在列表、标题、搜索结果或分页数量中，不显示带标题的锁定占位。查询为空不能推断项目没有其他受限资料。组织管理员对团队空间的现有管理资格不延伸到他人的个人区。

项目页支持类型、标题搜索、分页、只读阅读与移除关联；资料库在所选空间内支持组织项目筛选（含分页项目选项及归档项目）。切换类型保留项目条件，同组织换空间保留条件，换组织或返回现有个人资料时清除组织项目条件。项目上下文的阅读走专用接口，不能拿裸资源 ID 绕过项目检查。独立空间入口仍允许具有源权限的人阅读，即使他已离开项目；这不是项目越权，而是原本独立存在的空间权限。

归档项目仍按当前权限阅读，不能修改关联。新发布版本须显式关联，不会静默替换已有版本。资料撤销或成员撤权后，下一次读取重新检查；已返回的浏览器内容不承诺主动远程擦除。页面刷新/重新阅读失败会清除资料正文与当前列表。

## 存储与一致性

Flyway V4 新增 `organization_project_resource`，保存项目、组织、空间、发布资源 ID、操作者和关联时间。组合外键保证关联的项目与空间同组织、发布资源确属空间；增加相关唯一约束但不改 V1–V3 校验和或迁移旧个人项目。正文与固定版本继续由 Python 组织资料库保存。

修改使用当前项目 `revision`，沿用项目事务及组织行锁，再按项目、空间、发布资源顺序加锁。空间锁与成员调整互斥，资源锁与撤销互斥；取得锁后重新核验当前权限。事务内只操作业务 PG，不调用 Python。每次成功关联操作提升项目 revision 并写项目审计，复用已有关联不新增第二行。

同版本的并发修改只允许一个成功，其他返回 409。响应丢失后页面提示刷新核对，既不自动重发，也不生成另一份关联。旧请求不能在关联已被移除后恢复它；管理员重新读取新 revision 后再次操作属于新的明确意图。重复提交不是返回原响应的完整幂等协议，本批不把版本冲突称作原请求重放。

移除不要求源资料仍可见，仅允许当前项目管理员按已知资源 ID 删除本项目关系，不返回源信息；保留先前关联/读取/移除审计。已撤销发布的引用留在数据库，普通目录不泄露它的标题；该历史审计目前没有面向用户的浏览页。

读取目录和正文授权在 SQL 中同时检查项目、来源及关联，先过滤权限再分页，避免从隐藏条目数量推断资料。授权按查询快照时点生效，不承诺撤回已经授权并在途的读取。没有授权缓存，也未引入两份成员表的同步。

## 接口

| 路径 | 行为 |
| --- | --- |
| GET BFF `/api/v1/business/workspaces/projects/{project}/resources?type=&query=&offset=` | 当前可见关联，每页30，稳定按发布时间/ID排序；返回公开标题、空间名称、资源类型与固定版本身份，不返回内部binding |
| POST 同前缀 `/projects/{project}/resources/{resource}` | `{revision, linked}`；项目管理员关联/移除；归档、旧revision拒绝 |
| GET 同前缀 `/spaces/{space}/resources?project_id=&type=&query=&offset=` | 同组织项目的可见关联筛选；无效/无权项目明确404，不回退空间全部资料 |
| GET BFF `/api/v1/asset-workspace/organization-projects/{project}/resources/{resource}` | 读取双方授权后的固定正文，响应no-store；核对授权返回的项目、资源和组织身份 |
| POST Java `/v1/workspaces/projects/{project}/resources/{resource}/access` | 仅供BFF签名调用；当前联合授权后返回服务器binding；公开代理不允许访问 |

授权主体来自 BFF 登录及签名委托，不接收客户端 owner。原个人项目、原空间阅读路由保持原有权限，不能用普通 AssetRef 直接读取组织副本。启用条件沿用组织空间与 OIDC 配置，无新的身份降级。

## 静态案例与验收

1. 小王关联团队资料；小李只有项目 viewer，看不到该资料标题或正文。给小李源空间 reader 后，他能从项目和资料库两处读取同一发布版本。
2. 撤销小李源空间权限，项目目录隐藏资料，原阅读链接404；恢复源权限但移出项目后，项目路径仍404，独立空间入口按原源权限可读。
3. 同一资源关联多个项目，移除其中一个不撤销发布。个人区直接关联409，跨组织关联404。资料撤销后所有项目的新读取失败。
4. 两次同revision关联只有一次成功；随后移除关联，再重放旧关联请求409，不恢复它。原发布保持。
5. 将无权资料排在最新位置，分页仍只以可见资料计算；标题搜索与类型筛选不泄露无权记录。
6. 重启Java并重开Python存储，关联及固定正文可回读；被移出的成员仍不可读。

```powershell
# apps/business-service：真实Spring、Flyway、独立Testcontainers PostgreSQL
./mvnw.cmd verify
# 仓库根目录：离线与实际BFF签名链路（仅身份由fixture替代）
uv run --no-sync python -m pytest -q tests/test_resource_spaces.py tests/test_java_research_intake.py tests/test_project_workspace.py
$env:FINSIGHT_INTAKE_TEST_JAR=(Resolve-Path apps/business-service/target/business-service-0.1.0.jar).Path
uv run --no-sync python -m pytest -q tests/integration/test_resource_spaces_stack.py
# apps/workbench/frontend：构建后静态API浏览器案例
npm run build
npx playwright test --config playwright.recovery.config.ts
```

本批测试不调用模型、embedding或实时检索。真实PG和跨语言权限验证、浏览器合成API交互、金融研究质量分别记录；不得由本批读取通过声称团队Agent与衍生报告权限已完成。

本地工程结果：Spring/真实PostgreSQL全套17项通过；增加多项目引用隔离及V4迁移断言后，受影响2项复验通过（包含在17项内，不累计）。Python相关18项通过；实际BFF签名、Spring、PG、SQLite与服务重启链路1项通过。构建后浏览器首轮33项全过；补充“修改冲突后不接受晚到旧正文”保护及用例后，受影响5项全过，其中4项与首轮重叠。TypeScript、生产构建、活跃基线、936文件密钥扫描与diff检查通过；构建保留现有大chunk提示。已查看1440/390截图，无横向溢出。真实OIDC供应商和用户手工静态案例验收不由这些fixture替代。

部署需协调后再应用V4并构建前端。关闭入口或回退旧页面时保留V4表、业务审计及Python组织副本，不执行删除资料的down migration。未切换正在使用的部署。
