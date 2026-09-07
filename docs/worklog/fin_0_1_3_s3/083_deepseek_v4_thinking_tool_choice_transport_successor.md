# S3 Multi-Agent Preview：DeepSeek V4 Thinking Tool Choice 传输处置

## 1. R2 真实发生了什么

R2 在第一个 `Demand Quality` 规划节点发送了两次独立 Provider attempt；两次均在模型生成内容之前返回 HTTP 400：`Thinking mode does not support this tool_choice`。因此六角色规划、S1/S2 物化、工作底稿、Lead 挑战、反馈、Evaluator 和 Writer 均未开始。

该失败属于 Provider transport profile／Harness 参数投影，不是网络问题、模型研究能力、数据基建、S1 召回或多 Agent 编排失败。R2 authority、公开 terminal result、原始 request/response capture 和私有 terminal result 均保留；不能把它描述成“DeepSeek 不遵循合同”。

## 2. 官方协议依据

DeepSeek V4 thinking mode 支持工具调用，但官方适配说明明确要求 thinking 工具调用不发送 `tool_choice`；若在同一个工具回合继续请求，还必须回传 `reasoning_content` 和 assistant content。官方示例本身只发送 `tools`，不强制具体工具。

- https://api-docs.deepseek.com/guides/thinking_mode
- https://api-docs.deepseek.com/quick_start/agent_integrations/oh_my_pi/

当前 Preview 每个节点是一次模型提交、本地校验和至多一个新 successor attempt，不在 Provider 内继续执行工具回合。因此本次最小正确修复仅是：在 provider-neutral transport profile 中显式声明 thinking-mode `tool_choice` 不受支持，由 transport dispatch 省略该字段；研究 Runtime 仍要求返回唯一指定 Tool Call并在本地 fail closed。

## 3. 修复边界

- 新增 agent transport profile v1.1，记录 `thinking_tool_choice_supported=false` 以及未来 continuation 的 reasoning/content 要求；
- v1.0 profile 保持原样并继续支持历史回放；
- transport dispatch 根据 profile capability 投影，不在 S3 Research Runtime 写 DeepSeek 特例；
- DELL topology、objective、reviewed Evidence、S2、TokenBudgetBasis 和 22 节点上限不变；
- 新 scope decision v1.1 摘要绑定 R2 失败、v1.1 profile 和全部未变研究输入；
- 新 Live authority 必须使用新 attempt/output identity，R2 不重试、不覆盖。

## 4. 当前状态

Provider adapter 和 scope successor 的 52 项定向测试、全仓 836 tests、compileall、活动基线 `183 Python／8 frontend／5 detector／27 Runtime／0 forbidden`、7,364 文件秘密扫描和 diff check 已通过。下一步形成干净提交并执行 Project OS preflight；只有预检通过后才签发一次 R3 transport successor。该 successor仍不签发 S1、S3、泛化、人工、Workbench 或 release 权限。
