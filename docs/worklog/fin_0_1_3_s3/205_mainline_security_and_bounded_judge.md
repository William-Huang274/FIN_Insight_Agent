# 205 主线重排、一次有界核验与身份隔离首个切片

日期：2026-09-10。FIN 0.1.3 / 原 S3 工作继续，不改变报告版本或产品发布含义。

## Owner 已确认的主次与退出条件

认证/数据隔离、文件权限/真实 sandbox、Hermes 配套多轮上下文、Qwen 检索应用是主线。核验只做一次有样本、预算和停止条件的支线；不因金融审查模型未达到完美而无限推迟其余工作。本条覆盖产品基线旧“优先解除 E/C 全部研究交付阻塞”的排序，但不降低金融质量或公开部署门槛。

本次核验采用前一轮已冻结的 MSFT 两条、MU 三条原句，含两条正确控制、三条待纠正断言。原始段落、来源对象及私有预期不变，预期文件不进入模型。程序准备材料，模型一次返回五条结构化判断，没有选工具、重读目录或继续研究的循环。采用已有 ReasoningPreservingChatDeepSeek、SDK JSON mode、Pydantic，不新增执行引擎/提供商传输/金融 NLP 规则，不改六技能或生产默认。

最初授权切片为 Flash low/high 各一次、相同输入72572字符/29373输入tokens、thinking enabled、12000输出上限、360秒、SDK重试0。高档发生 SDK length 异常后的记录缺陷已及时向 Owner 报告；离线修复后明确补一次相同额度 high，不追加第四次，也不调大上限追结果。各次 TokenBudgetBasis、实际 SDK payload、结果分别保存，旧件不覆写。

## 核验实际结果与原始推理诊断

| 尝试 | 实际请求参数 | 返回 | 已知 tokens | 判读 |
| --- | --- | --- | ---: | --- |
| low | deepseek-flash / thinking enabled / low | stop；5条JSON完成；reasoning972 tokens / 3217字符 | 31989 | 两条正确控制保留，三条问题全部漏检；不合格 |
| high 原次 | 相同模型、材料、上限 / enabled / high | SDK LengthFinishReasonError | 未知 | 当时异常对象未保存，不能推测原始推理或按0费用计算 |
| high-capture-a2 | 同上；仅修失败记录路径 | length；12000输出tokens全为reasoning / 43790字符；最终content为空 | 41373 | 无提交，不能按原始推理片段判为审查通过 |

三个实际请求，73362已知tokens，1次新增用量未知；历史205合计583模型尝试、17759502已知tokens、3次未知。不是583道题；未查服务商账单，不报实付价格或以别名推测底层版本。三个原始输入摘要完全相同。没有原产品窗口/报告回写，没有修后完整报告，更没有推广生产核验。

低档公开判断与私有推理一致地体现了以下问题：

1. MSFT：核对了 CFO/净利润数值，却接受它支持“经营利润的现金兑现”这一对象变化；保留措辞被当成充分理由。
2. MU：正确看到净利润与 CFO 同向，却没有要求“非纯账面”所需的额外现金/利润衔接证据。
3. MU 周期：已注意到谷底定位和价格/周期归因未被给定来源建立，却因句子含保留措辞、属于反证段落而放行。未给出最终被验证的周期结论。

高档原始推理反复对周期句放行/修改摇摆，部分段落猜测测试者/评分者期待及样本答案分布；重复回到已判过的数字和措辞，没有形成交卷。它也反复为“非纯账面”寻找宽松解释。**这是可观察的响应行为，不是对模型内部全部机制的证明。** 本次证据不支持统一切 high，也不支持核验 Agent 作自动金融放行依据。五条是已知开发目标，不是盲测总体准确率；低档三条漏检不外推为所有财务题均不可用。

支线结论：停止继续加提示/轮数/付费追绿；保留辅助核验，核心事实与计算约束、失败保存、人工审阅继续有效。未来只有新的明确方法/模型证据才重开单独有界对照，四主线不等待它。

私有原件：`D:/temp/fin205-prepared-judge-a1/`，各子目录 `low`、`high`、`high-capture-a2`；原 low 的 `response.private.json`、补测 high 的 `provider-completion.private.json` 保留实际推理字段，未进Git。原 high 没保存的原件无法事后重建，补测必须独立计次。

工程修复：SDK 的 LengthFinishReasonError 携带已经收到的 completion。新诊断入口在异常分支保存该对象及用量/finish_reason/推理长度，不能将它误报为“模型没有返回任何东西”。离线用真正 SDK 异常类和 completion 测试。没有声称产品所有历史异常路径都已审完。

## 主线首个可执行切片：真实签名身份进入对话所有权

发现：原通用对话 BFF 的 owned 检查只验 surface/graph，未验用户，创建时也不固定用户；个人 Store/交接只在运行工具层默认 local-pilot。这是本地单人试用边界，不能直接变成多人服务。

采用而非自建：外部 OIDC IdP 负责账号、登录、令牌签发；Starlette AuthenticationMiddleware 和 PyJWT[crypto] 2.13.0 负责认证接缝、JWKS、RS256验签、issuer/audience/expiry。FIN 只把已验证 issuer+subject 映射成不暴露邮箱的 owner_id，并在自己的资源入口使用这个身份。参考 [PyJWT 用法](https://pyjwt.readthedocs.io/en/stable/usage.html)；原生 Agent Server 的 [custom auth](https://docs.langchain.com/langsmith/custom-auth) 是后续第二层授权接入点，不另造认证服务器、通用策略引擎或用户数据库。

已接入 `create_report_session_app`，显式模式 `oidc_conversation_pilot`：

- 新对话/草稿由服务端写 owner_id，浏览器请求体不能指定；列表传所有权过滤且复查结果。
- 读取、资料上传、追问、批准、停止、固定版本导出、SSE、跨窗口预览/交接均先检查归属；错误所有者返回404，不读取checkpoint、运行结果或执行副作用。
- 交接保持已验证所有权，原知识工具继续以这份宿主线程元数据隔离 namespace。没有把登录用户自动变成旧 local-pilot 数据的所有人。
- 无效/过期/错误 issuer/audience/签名/算法的凭证返回401。未知认证模式、非HTTPS可信签发者/公钥地址、不完整配置或误起旧服务拒绝启动。
- 此试点中所有未隔离验收的其他 `/api/v1/` 产品接口返回503，不借登录外观宣称研究报告、配置等已完成隔离。

资格：真实 RSA 签名、PyJWT原生JWK选择/验签、HTTP BFF入口，两个用户；IdP公钥HTTP抓取用固定夹具替代，Agent Server SDK持久化是测试替身。覆盖9类越权入口、伪造owner、历史未归属数据及接续身份。主产品仍默认 local，不重新分配旧数据，不改变现有服务部署。**没有完成实际身份提供商登录、前端登录、真实 Agent Server/PG 双用户持久化、原生服务授权或多租户生产验收。** 原生服务必须留在BFF专有网络；不得把当前试点用于对外多租户。

开发启动配置（仅可信环境，不把令牌填进代码）：安装项目 `workbench-auth` extra；设置 `FINSIGHT_AUTH_MODE=oidc_conversation_pilot`、`FINSIGHT_OIDC_ISSUER`、`FINSIGHT_OIDC_AUDIENCE`（专用API audience）、`FINSIGHT_OIDC_JWKS_URL`，并保留已有私有 `FINSIGHT_REPORT_SESSION_API_URL`。请求携带外部IdP签发的Bearer access token。没有自制密码/伪登录页。默认local可回退，但不会接管OIDC用户已有数据。

## 后续主线的最小闭环与验收

1. 认证/数据隔离：接一个成熟IdP的实际登录流程和前端状态；将同一身份传入 Agent Server 原生 auth/on 授权，覆盖threads、runs、Store以及研究/配置/导出入口；两个真实用户跨重启验证不可越权。会话按用户隔离是首层，不等于组织多租户、配额/并发/撤权完成。
2. Sandbox/权限：复用已有 Docker/MCP/HITL，在产品真实调用里验证标准/代批准/完全访问，批准绑定动作、作用域和运行；拒绝不得执行，模型文本不能授予权限。测试只操作隔离临时资源，原用户文件/服务器文件不作为破坏性试验材料。
3. Hermes/多轮上下文：复用原生checkpoint、已批准个人Store和原始证据回读；压缩导航与原事实分层。用长轮、多Agent、重启与跨窗口测试原数/期间/单位/未决项和权限；只有保真及正式交卷通过才改变默认，不能把摘要更短等同质量通过。
4. Qwen应用：在前面统一身份/证据namespace内接入已有Qwen embedding/rerank adapter，明确query/index配置；冷/热缓存、错误降级、同料相关性和答案引用对照。模型切换必须重建/版本化索引，不能混向量空间或跨用户缓存。

这是一个有界基线，后续每包都必须有可执行产品证据；不再先写大批状态机和台账才能开工。核验失败没有产生新版本，也不阻止以上进度。

## 检查与交付分类

最终相邻检查71 passed：新身份与原通用对话/交接/知识、工作台启动/研究BFF、结构核验诊断。uv lock --offline成功；既有Python3.10系统解释器缺runtime依赖，改用项目.venv完成，未把环境收集错误算功能失败。首次身份测试发现Starlette SimpleUser.identity未实现，修用其已认证的opaque display_name，全部复验通过。

`git diff --check`、定向compileall、`uv lock --check --offline`通过；仓库密钥扫描8771文件、0命中。工程提交：`0bba47c0`（结构核验与截断保存）、`0dc57016`（OIDC对话所有权试点），沿用 `codex/fin013-conversation-and-retrieval`，不合main、不改发布版本。原始三次输入identity相同，私有assessment已汇总，无继续运行的付费进程。

- 产品增量：没有新合格报告、公开登录UI或服务部署；现有本地产品不改发布含义。
- 工程增量：有界结构判断/失败原始响应保存；可选OIDC对话API身份和所有权实际接缝、依赖锁及检查。
- 资格证据：低档语义不合格；高档原始推理退化/无正文；HTTP身份隔离切片通过，不等于部署通过。
- 文档：主次重排、负结果、预算缺口及下一步归入原205阶段。
