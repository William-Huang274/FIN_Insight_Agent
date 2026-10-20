# 指标卡页面保存与组织发布

这批功能把公开指标浏览接到已有项目资料、组织空间和项目关联流程。Python 负责验证发布库、读取完整数据卡并保存固定快照，Java/Spring 继续维护组织空间权限及项目关联。没有新增第二套成员名单或指标存储，也不改变 Agent runtime 合同。

## 用户流程

1. 资料库 → 数据库 → 选择公司 → 指标分析。打开总览、历史列表或趋势中的数据卡。
2. 在指标卡底部点击“保存此数据卡到项目”，选择个人项目、名称及可选批注。一次保存一张完整卡；查看计算输入时需先返回指标卡，避免把输入与结果混淆。
3. 打开已保存资产，核对完整十进制数值、单位、期间、可知日、原文依据、公式输入和记录版本。页面显示小数位不影响保存精度。用户批注与原始记录分开维护。
4. 点击“发布到组织空间”，选择有管理权限的空间并明确确认。发布形成独立的组织固定副本；原文件后续修改不会自动覆盖它，组织管理员可以撤销发布。
5. 在组织项目的资料页“关联团队资料”中选择该卡。关联本身不授予源资料权限；项目成员还必须具有该空间/资源的当前读取权限。

没有组织空间权限或部署未启用此功能时，发布不能成功。个人项目保存与组织发布为两个明确动作，不因保存自动扩大可见范围。

## API 与数据合同

`POST /api/v1/data-library/metrics/query` 的单公司 `section=card` 响应增加 `capture_selection`，包括 `kind=metric`、公司、稳定记录 ID、截止日和快照摘要。旧数据卡字段及工具输出保持兼容。

`POST /api/v1/asset-workspace/captures` 接收该选择身份。服务端按配置的不可变公开发布库重新读卡，校验当前发布摘要和完整卡摘要，再写入已有 attachment/capture 事务。浏览器不能提交数值、单位或任意 SQL；额外字段拒绝。数据或发布版本变化时返回冲突，需重新打开数据卡确认。

存储仍使用 `project_source_snapshot.v1`、`kind=financial`、`selection_mode=explicit_rows`。`query.kind=metric_cards` 标识指标卡，其选择范围包含记录 ID、公司、截止日和发布库 SHA256。每张卡保留原始字段及计算输入，组织读取和正式结构化工具沿用已有快照/授权合同。没有新的 Java 表或数据库迁移。

当前范围是**公开发布库的单张指标卡选取**。团队实时 SQL 连接器、行列级数据库授权、批量选卡、发行人重述的自动替代关系、审批工作流和生产负载不在本批交付中。工程案例不能证明金融结论正确。

## 验证与复现

普通回归不依赖私有历史案例：

```powershell
python -m pytest tests/test_metric_card_capture.py tests/test_project_source_captures.py tests/test_metric_workspace.py tests/test_resource_spaces.py tests/test_organization_execution_access.py tests/test_structured_sql_acceptance.py -q
```

新增测试覆盖完整计算输入、精度、重复保存、原文不可篡改、错误公司/记录/截止日、额外数值字段、失效摘要和发布版本变更。旧捕获、组织授权与结构化回滚测试保持有效。

真实浏览器验收使用[结构化 SQL 验收](structured_sql_acceptance.zh-CN.md)生成的历史 `cases.json`，只读对应完整不可变发布库，不使用局部子集充当产品资料库。先构建本分支前端和 Java jar，再配置既有隔离栈变量，以及：

```powershell
$env:FIN_METRIC_BROWSER_QUALIFICATION = '1'
$env:FIN_STRUCTURED_SQL_CASES = '<historical-output>/cases.json'
$env:FIN_METRIC_PUBLIC_LIBRARY = '<matching-immutable-published-library.sqlite>'
$env:FIN_NATIVE_ATTEMPT_DIR = '<new-private-attempt-directory>'
$env:FINSIGHT_TEST_NODE = '<node-executable>'
python -m pytest tests/integration/test_metric_card_browser_stack.py -q
```

隔离栈使用唯一 Compose 项目、独立端口和未占用网段；只启动 PostgreSQL、Java、BFF。登录身份和组织初始化是测试设置，用户保存、发布、关联和读取经过真实页面/API，不伪造业务响应。浏览器限制访问本次服务，未启动研究或调用付费模型。

结果保存在尝试目录内：浏览器请求日志、四公司卡片身份、桌面/窄屏截图、服务日志和权限验收结果。失败尝试保留。验收结束只停止本次自有进程与容器，保留证据；不切换共享部署。

## 2026-10-20 验收结果

- 真实 Chromium → BFF → Spring Boot → PostgreSQL 场景通过，覆盖 NVIDIA、阿里、Meta、Dell 四张历史卡。浏览器点击完成保存、刷新、组织发布及项目关联；保存/发布内容与历史完整卡逐字段相等。Meta 的计算卡保留长十进制结果和两个输入。全过程无业务响应模拟。
- 项目成员缺少源空间权限时读取为 404；授予 reader 后可读；资源撤销后再次读取为 404。没有以项目关联替代源权限。
- 1440 桌面及 390 窄屏已检查截图，窄屏无页面横向溢出。
- Python 定向回归 46 项通过；空间/项目关联前端回归 10 项通过；TypeScript、Vite 构建、基线与密钥检查通过。构建保留既有主 bundle 大小及第三方注释警告。
- 真实测试先暴露了登录栏遮住数据卡保存按钮，以及组织空间列表异步返回清空已选资料的两处问题；修复层级和加载期间交互后通过正常点击验收。完整公司目录新增独立滚动，缺少开始日期不再误标为时点。

这组结果证明的是固定数据卡的用户操作及当前权限闭环。登录由测试身份替代，未验证真实 SSO；未启动研究、未评定 Agent 研究质量，也未验证生产容量。
