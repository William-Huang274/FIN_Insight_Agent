# 组织研究的浏览器操作与项目阅读界面

在独立 OIDC、Java 业务服务、组织空间及组织原生工厂均已配置的环境，项目页现在提供“保存输入 → 准备执行 → 首次预研究 → 查看预研究 → 确认正式研究 → 核对未知结果”的操作。界面继续以项目为顶层，不展示项目 UUID，也不转入个人研究接口。本交付不自动切换已有部署。

## 页面行为

研究准备单保存问题、截止日和资料版本。原发起人选择自由调度或标准协作，沿用服务配置的模型与已有预算规则，准备一个执行记录；准备本身不调用模型。浏览器在派发前保存 execution ID 和原始准备内容，服务端也提供原发起人的已有执行列表，刷新或换浏览器可以找回原记录。列表读取未成功时不允许创建，已有执行优先核对，不通过生成另一个 ID 绕过未知结果。

准备完成后，同一项目的研究页显示记录列表、正文、当前阶段和下一步操作。首次启动明确提示调用模型。日期型截止日由服务端固定解释为该日 `23:59:59+00:00`，不依赖浏览器时区或当前日期；这不是历史可知日资格证明。首次运行完成后，准备正式研究只读取并检查前序记录，用户再确认才发送接续命令。该命令沿用冻结配置、问题和资料版本，不能修改研究范围或模型。

只读成员可以按项目及全部来源的当前权限阅读结果，但不会得到原发起人的执行控件。项目管理员也不能代替其他发起人操作。列表与详情刷新不提交研究；命令未知时展示核对入口，核对不重新派发。原生运行结束不等于研究成功完成：`research_needs_attention` 明确显示待处理，不能当作报告或审批通过。

事件区只订阅该执行已登记的原生 run，最多保留 80 条公开进展。连接关闭后再次核对读取权限；核对失败清空事件与正文，不自动重连或重发命令。用户可手动重新连接，从该运行的已保存事件重新读取。没有实现跨刷新保存事件游标；不宣称无损事件回放。报告、引用快照、导出仍使用原来的当前读者 API。

成果页面把当前正文对应的原生 `checkpoint_id` 同时带给引用和导出请求，避免页面看到旧报告、下载却取到新报告。历史版本仍须通过当前权限检查。旧服务未返回 checkpoint 时，正文可以显示，但下载不可用，引用也不回退最新版本；页面提示刷新，需要配套更新 BFF 才能恢复这些操作。

导出通过同源 GET 读取完整响应后下载，明确处理状态码、内容类型和空文件。401/403/404 会清空报告、引用及操作区；503、网络错误及格式不匹配仅显示失败，不下载错误页，不自动重试。切换研究、刷新或卸载页面会取消未完成的下载。该行为不能收回用户已经保存的文件，也不承诺在断网后立即感知撤权。

## 跨服务合同

浏览器前缀 `/api/v1/organization-projects/{project}`：

| 方法与路径 | 行为 |
| --- | --- |
| GET `/research-drafts/{draft}/executions` | 原发起人在当前研究及来源权限下查看已有绑定，最多 100 项；含关闭及准备状态 |
| POST `/research-drafts/{draft}/prepare` | 固定 execution ID、manifest 摘要和执行选项；Java 绑定后受理唯一准备命令 |
| GET `/research/{execution}/control` | 当前操作状态；非发起人仍须通过完整读取授权，返回 `can_operate=false` |
| POST `/research/{execution}/start` | 从 Java 固定资料日期生成首次启动请求，不接收浏览器提供的配置或截止日 |
| GET `/research/{execution}/continuation-preview` | 检查当前读/写权限、前序唯一成功运行、固定 checkpoint、预研究阶段及已知完整用量，返回待确认的前序 ID、checkpoint 与摘要；零派发 |
| POST `/research/{execution}/continue` | 将上述明确内容交给 Java 的独立接续命令；后端仍重新核验，不信任页面已检查的状态 |
| POST `/research/{execution}/reconcile/{preparation\|start\|continuation}` | 核对指定原命令，无运行创建 |

Java 新增 creator-only `execution-bindings/{id}/control` 聚合状态以及准备单的执行绑定列表。两者均复用 `materialAccess` / `preparation`，在组织/项目锁内核验当前权限；没有新增成员或权限副本。

浏览器组织命令与通用 business 代理一样，不经过 Python 的本地响应回执缓存。Java 已拥有持久命令、唯一约束和 CAS 领取；如果 BFF 缓存旧响应，会在核对后继续返回 unknown，甚至绕过当前授权。每次页面命令都实际访问 Java；内部 Java→Python 委托路径仍保留原签名及核权先于回执的保护。新增命令使用既有浏览器写入标识与同源校验，模型派发仍只发生在已准入的内部流程。

## 界面调整

项目工作区显式设置无衬线字体和继承规则；采用约 270px 的研究列表与自适应正文区，减少等宽卡片和重复边框。正文、阶段标签、主操作、次要核对和引用各有层级；操作控件有键盘焦点，窄屏回到单列，保留已有主题变量和项目导航。调整仅覆盖项目工作区，未重做公司光谱、数据库、通用对话等页面。

## 验证及边界

复验入口：Python `test_organization_research_commands.py`、既有只读/接续/回执测试，Java `ResearchIntakeTest`，浏览器 `organization-research-inputs.spec.ts` / `organization-research-results.spec.ts`。真实隔离服务测试 `tests/integration/test_organization_graph_native.py` 已改为使用上述浏览器接口完成准备、启动、预览接续、提交接续和核对；保留当前读者、服务重启、重复提交、盗用运行和撤权检查。仅 provider 与登录边界是静态替身，不调用付费模型，不修改现有部署。

此片不开放专家补跑、失败重试、报告修订、交接、审批或多实例生产运行。完整原件扩展、真实企业 SSO、静态人工业务验收和金融研究质量需要各自验收。测试中的正式研究停在待处理，不能将传输成功写成报告完成。

## 分阶段收口顺序

先完成现有业务闭环，再补数据库和运行验证。各阶段保留自己的证据；未满足退出条件时不标记完成。第一阶段固定在 Java/Python 集成分支推进，研究运行时仍在变化的其他分支先单独完成自身验证，之后按明确提交整合，不能直接覆盖组织工厂、冻结配置与准入检查。

| 阶段 | 退出条件 | 当前边界 |
| --- | --- | --- |
| 1：现有业务接入 | 同一项目、固定资料、同一次执行可完成准备、首次启动、刷新恢复、明确接续、结果与引用读取、导出；重复请求与未知回执不新增运行；撤权有效 | 2026-10-19 真实浏览器/BFF/Java/数据库/队列案例通过，报告生产明确使用静态替身；见[真实服务业务验收](organization_business_delivery.zh-CN.md)，不代表模型完整研究通过 |
| 2：数据库证据 | 真实 PostgreSQL 下确认约束、并发竞争、状态更新和查询计划；给出数据规模、执行计划、改动前后指标及限制 | 尚未作为这一阶段交付；既有幂等/锁测试不替代查询性能验证 |
| 3：运行验证 | 明确健康/故障观测、部署与恢复步骤，在隔离环境验证多实例或故障场景并保留原记录 | 按已完成的业务路径选择场景；不以本机测试声称生产容量 |

第一阶段的静态复现入口：

```bash
python -m pytest -q tests/test_organization_research_reads.py tests/test_organization_research_commands.py
cd apps/workbench/frontend
npm run typecheck
npm run test:public -- organization-projects.spec.ts organization-research-inputs.spec.ts organization-research-results.spec.ts
```

Python 测试使用当前源码与已安装 qualification/workbench 依赖。浏览器仅启动独立 Vite，全部研究 API 是合成响应，四种下载的字节也是静态夹具；它验证用户操作、文件名/内容、版本参数和拒绝后的页面行为。`test_organization_research_reads.py` 使用真实四格式渲染器，另验证读者权限和导出前再次核权。两层结果不可相加成“真实服务端到端报告已通过”。真实容器入口仍为 `tests/integration/test_organization_graph_native.py`，需要满足其显式隔离开关、镜像、临时网络和输出目录条件。

同一真实服务链上的静态报告与浏览器验收已由 `test_organization_delivery_stack.py` 补齐，复现及替身边界见[真实服务业务验收](organization_business_delivery.zh-CN.md)。下一阶段是数据库专项验证；研究分支整合另行固定提交后再验收。输出必须位于独立目录，禁止复用运行中的服务、已有研究数据或自动重提未知请求。
