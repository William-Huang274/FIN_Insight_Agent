# S3/188 — 原生多工具响应修补与后续功能验证

状态：批次修补及 115 项定向检查通过；下一步 fresh 真实功能运行。R4/R5/R6 失败结论不改，不宣称研究 PASS。

## 本轮范围与 Owner 授权

2026-09-05，Owner 要求继续修复 RC-S3-114，并进一步明确：同类明确的本地实现问题自行修复、按风险验证后继续任务，不逐补丁请求意见；扩大权限、删除数据、明显增加费用或改变产品方向才暂停求授权。

本轮只补现有 single-Specialist 的 native tool batch 流转，不改 RAG/SQL 数据、不扩多 Agent、不增加工具权限。不新增通用调度、恢复、审批框架。原始 provider reasoning 仍只保留私有审计，公开 trace 不含正文。

## 具体实现

1. SDK 的一个 AIMessage 内所有 tool_calls 原样保留；内部用一个批次决定记录它，一条模型 receipt/轮次，多个数据动作。不把四个工具伪装成四轮模型。
2. 使用已固定版本的 LangGraph `ToolNode`、`StructuredTool`、`ToolMessage`。ToolNode 的标准 `max_concurrency=1` 串行执行，薄适配复用现有 MCP ports 和来源校验，不造队列或调度器。
3. 每个调用用原始 schema、当前 context、任务路由及 source-read profile 单独校验；错误按 tool_call_id 返回。模型终止/提交不与读操作混用；缺失/重复 ID 不执行。既有预算只按实际 dispatch 计数，不暗改输入或放宽来源。
4. 下一轮 provider wire 保留上一轮原 AIMessage、实际 reasoning、该批全部 ToolMessage；历史不重复塞入全量观测，不能只返回首个调用或最后一个 observation。
5. 旧单动作与 R3 notebook/receipt 仍可读取；R6 原始文件只读。使用真实 R6 四调用做离线反例回放，另测部分失败、权限、计数、终止混用和真实 MCP 数据。

## 验证与停止条件

- 定向回归：graph、provider adapter、source-read、composition、Agent Server entry；不全仓重跑。
- 离线证明必须包含实际 SDK wire 第二轮四份结果/原 reasoning，及真实本地 MCP/SQL 反馈；离线脚本不计入真实模型指标。
- Owner 最新授权后，修复及针对性验证完成可用 fresh identity 做一次真实 enabled 功能运行，沿用原任务、权限和任务规模预算依据，不称 thinking A/B；不自动增加预算或无限重试。
- 若遇新的数据/模型研究问题，先看真实内容与最早责任层；不把工具失败当公开信息缺口，不因本地修补创建产品版本。

## 离线结果

8 个相关文件共 **115 passed in 36.05s**，不是全仓回归。新增批次专项 14 项，覆盖四读请求、一轮/四动作计数、call ID 完整回传、错误参数/action tag/context/任务路由/未知工具、重复查询、source-read 禁用、动作上限、终止混用、缺失/重复 ID 与结果错配。

真实 R6 反例来自其私有审计文件及失败后的只读 state，原参数、原 context 和四个 call ID 未改。离线 SDK MockTransport → 现有本地 MCP → 下一轮 SDK wire 验证成功：Reviewed Evidence、S2 NumericFact、源文档目录实际返回；一个模型决定形成四个实际 MCP 动作/观察，下一次 wire 的四个 ToolMessage 与原调用 ID 对应，上一轮实际 reasoning 内容保持一致且不进入 graph notebook/公开 audit。第二轮是人为的离线终止 fixture；无新的网络模型调用或研究结论，旧文件字节未变。

实现只增加宿主内部批次表示及 ToolNode 薄适配，不向模型暴露第六个工具。现有单 terminal/legacy action 路由和 R3 notebook 可读性仍通过。私有 provider 历史仍为本次进程内的 SDK history；没有借此次修改声称生产级 resume 或多 Agent 上下文已完成。

依据：[LangGraph ToolNode/工具执行](https://docs.langchain.com/oss/python/langchain/tools#toolnode)。运行中继续补充真实质量、token、耗时和来源内容检查，不以离线 PASS 替代它们。

## R7 模型前部署失败与最小网络纠正

R7 implementation=9541c03ee371577b530c44de3abd81d6c818c934，authority HEAD=6fce9eec6ddd2f1a7de8ecf67fcf4811679fb0fa。fresh execution=20260905-dell-q1-native-tool-batch-enabled-r7，project=finsight-dell-q1-paid-469df916ca70，port=18178。BuildKit kbll8j7fns3n3w76j3dzpupjc 已成功导出镜像；Compose up 在 183.922 秒返回失败，项目容器/卷未创建，模型调用=0，failed-receipt 原样保留。

网络诊断明确返回 `all predefined address pools have been fully subnetted`；现有 30 个 bridge 网络耗尽默认可用分配池，历史测试网络仍有停止容器引用。这不是本次 wheel TLS 或代理故障。诊断 network create 同样失败，未新增网络。未删除任何网络/容器/卷/镜像；此前仅停止已结束 R6 的三项服务减内存。

采用 Docker Compose 原生可选 IPAM overlay 和 launcher `--subnet`（私有 IPv4 /24），不改全局 daemon、不共享历史网络、不生成网络分配框架。人工只读核对 Windows IPv4 routes 及全部 Docker IPAM 后，10.253.8.0/24 无冲突；新 R8 使用它。CLI 选择写入部署 receipt；默认不传该参数仍沿用既有 Compose 行为。R8 的模型任务、数据、五工具、权限和预算不变，此网络纠正后继续一次尚未发生的真实功能验证，不消耗无限模型重试。

官方依据：[Docker Compose IPAM](https://docs.docker.com/reference/compose-file/networks/#ipam)。

网络/launcher 这次局部修补只重跑相关两文件：**10 passed in 0.51s**，含默认无 overlay、显式私有 /24、拒绝公网/过宽/非网段地址/IPv6；没有重复 115 项、更没有全仓回归。新运行继续走原 start-once runner，未手工复用失败 R7。
