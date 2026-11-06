# Congress.gov 官方记录与文本读取

核对日期：2026-11-06。此接入是既有公开网络授权下的只读工具，不新增研究流程，不依赖浏览器或人工页面交接。

## 入口与边界

`read_legislation(query, operation="record", offset=0, limit=20)` 接受 Congress.gov 法案概览、正文或动作页面地址，以及明确的 `届次/类型/编号`（如 `119/hr/1`）。不从裸编号推测届次，不支持把自然语言关键词直接发送给官方列表接口。

- `record`：核对 API 回包的届次、类型、编号，返回法案记录及 texts/actions 调用入口。
- `texts`：列出该页文本版本及格式。只对 API 实际列出的文件身份生成对应 GovInfo package 候选，再由官方 MODS 元数据核对 package、HTML rendition 和 dateIssued。返回确切的 `read_public_source` 参数，尚未读取的正文不标成已读。
- `actions`：返回该页程序动作。按 `next_offset` 翻页；当前页不能代表完整历史。

议题关键词先通过 `read_public_source` 搜索发现法案。得到法案身份后使用 `read_legislation`，选择版本，再执行其 read_call：搜索具体正文 URL，读取返回的 WEB document ID。正文仍由原有来源捕获、段落定位、引用和会话缓存管理。没有接一条旁路来把元数据当全文引用。

工具在普通会话及原生组织 harness 的既有公开网络准入处注册。组织任务关闭 public web 时不提供此工具。工具回执进入原有保存结果和上下文回读目录，不把 key 作为模型参数。

## 凭据与部署

在实际研究服务的进程环境中配置 `CONGRESS_API_KEY`。申请入口为 [Congress.gov](https://api.congress.gov/sign-up/)。密钥只随 HTTPS 请求头 `X-Api-Key` 传给固定 API 主机，不放进 URL、模型输入、缓存或日志。响应的 request echo 和 URL 中的 api_key 参数会被移除。

Windows 用户环境变量不会自动更新已经启动的服务或容器。运维应通过现有秘密注入机制传给服务，并重启目标服务；不要把本机注册表读取写进通用业务代码。未配置时明确返回缺少凭据，不静默改用演示 key。正式部署不以 `DEMO_KEY` 为默认配置。

凭据拒绝、429、HTTP 未找到、TLS、代理和连接失败分别反馈。429 后当前客户端冷却至少 60 秒，冷却内不重复派发；不立即切浏览器，也不将故障解释为没有法案。分页仅使用本地生成的固定主机路径及数字 offset/limit，不跟随带凭据的分页 URL。

## 时间与来源

立法日期、GovInfo 版本公开日、API 更新时间与采集时间分开保留。立法日期本身不充当文本公开日。版本正文必须再经原有日期检查与读取。

API 提供的是当前响应，不保证过去某日的归档状态。记录更新时间晚于任务截止时点或未知时，仅返回身份和提出日期，不披露当前标题、最新动作或支持者等可变字段；可继续读取带日期的 actions 和核定公开日的具体文本版本。动作发生日期过滤不证明该动作何时首次进入 API，回执保留这一限制。

同一任务的成功 API 响应通过现有 SQLite LocalRecords 缓存一小时，恢复复用；工具回执仍由正常 harness 保存。缓存只保存响应本身，不复制完整 Agent 状态。正文继续使用原有来源缓存。元数据导航回执不自动升级为已读全文或已确认研究结论。

## 验收范围

确定性检查包括：URL/编号解析、错误身份拒绝、密钥不进入结果、同任务恢复缓存、历史截止过滤、版本日与公开日区分、分页、429 冷却和凭据缺失时不派发。

本机真实无模型验证已通过：从 Congress.gov 正文页链接取得官方记录、1 个版本、2 条动作；版本经 MODS 绑定后，通过实际 `read_public_source` search/read 读取 23,247 字符正文。没有网页验证、浏览器、付费搜索或付费模型调用。具体题目材料仅存于本地验收记录，不写入方法或新任务输入。

这不证明主题搜索召回、模型自主选择版本或新闻研究结论已经通过。也不等于已部署到当前工作台容器；后续在固定服务版本中确认 key 注入和工具目录，再进行有预算的模型验收。

上游合同：[Bill endpoints](https://github.com/LibraryOfCongress/api.congress.gov/blob/main/Documentation/BillEndpoint.md)、[GovInfo 开发者接口](https://www.govinfo.gov/developers)。
