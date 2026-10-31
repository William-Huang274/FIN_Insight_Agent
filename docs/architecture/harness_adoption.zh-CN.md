# 研究工作台采用上游 harness：选型与替换边界

2026-10-31。状态：**选定 DS Harness / ACP 作为下一阶段集成候选，尚未通过部署准入**。Codex app-server 保留为对照实现。本次不更换实际服务、不调用付费模型、不迁移历史运行。此前按需研究 A/B/C/D/E 的产品能力继续保留；本文件调整其执行内核的归属，不另建第二套业务流程。

## 1. 决策与证据强度

目标是采用上游维护的 Agent 循环、会话、压缩与取消机制；FIN 负责研究工具、金融语义、成果、用户业务与费用政策。不能复制两个上游的内部实现，再长期维护第三个内核。

候选顺序：

1. **DS Harness 原生 ACP 服务进程**：当前研究以 DS 为主，并要求保留 Qwen 路由。其原生 DeepSeek Messages 适配保留 thinking/tool replay；pi-ai 插件提供其他协议扩展点；ACP 有会话创建、恢复、关闭、取消、MCP 接入和模型选择。适配层只翻译宿主命令与事件，不控制每一轮研究。
2. **Codex app-server**：工具、持久会话、压缩和取消的服务接口清晰，已完成本项目进程级无模型工具链验证。固定源码中的 WireApi 仅接受 Responses，不能把我们已有 Chat Completions 地址直接换上；DS 已提供 Responses 也不意味着所有返回字段、thinking 回传、Qwen 路由已兼容。若 DS 候选无法用公开扩展点满足准入，而 Codex 的实际供应商路径可用，再调整选择。

这是适配成本判断，不是模型质量排名。两边证据不对称：Codex 已运行完整 app-server；DS 仅核对核心源码并执行原始 SDK 传输模块，**尚未运行完整 ACP/Agent**。磁盘空间有限，本轮未安装整套 DS 依赖。不能把 DS 的传输测试称为其 Agent 生命周期通过，也不把本机 Codex alpha 二进制直接作为生产发行版。

## 2. 固定来源，实际读实现

DS 源码固定 `ce7073d51254c26cd63b22a60835b8f948deb447`；Codex 固定 `eab2603712f90ec08ac44207a04eed158be293a3`。固定版本用于可复查，不表示未来应自动跟随 master。下载文件逐项记录 SHA256；不是读完所有仓库文件。

| 能力 | DS 实现证据 | Codex 实现证据 | 结论/待验 |
|---|---|---|---|
| 模型协议 | `packages/llm/llm-deepseek/src/{adapter,serialize}.ts`；`llm-pi-ai/src/{adapter,models,catalog}.ts` | `codex-rs/model-provider-info/src/lib.rs` | DS 原生 thinking/signature 与工具配对有代码；pi-ai 支持协议与兼容配置不等于 Qwen 实际请求通过。Codex Responses-only 源码明确拒绝旧 chat 配置 |
| 服务生命周期 | `packages/acp/acp/src/{index,session,model-control}.ts` | `codex-rs/app-server-protocol/src/protocol/v2/{thread,turn}.rs` | ACP 的 new/resume/close/cancel 不能与 SDK 的 prompt/resume/wait 混为一谈 |
| 工具 | `packages/mcp/mcp-client/src/index.ts` | `codex-rs/app-server/src/dynamic_tools.rs`，thread/start 的 dynamicTools | 优先使用受权 MCP；Codex dynamicTools 当前为实验能力，需锁版本 |
| 持久化 | `packages/session/session-persistence-jsonl/src/{index,storage,lease}.ts` | thread/resume；本轮真实进程重启测试 | 持久文件不等于企业权限服务；工作区/租户隔离由宿主配置、工具访问验证负责 |
| 压缩 | `packages/compaction/compaction-basic/src/{index,config,summarizer}.ts` | `codex-rs/core/src/{compact.rs,session/turn.rs}` | 采用上游机制，不移植 FIN 两次摘要上限、独立历史退出器。压缩质量待真实模型验证 |
| 费用与状态 | ACP `updates.ts:usageUpdate`、SDK session.event、Agent request-error 钩子 | app-server 事件、usage；本轮夹具 token 为固定值 | ACP usage_update 仅报告当前占用 used/size，不是完整计费账本；必须补计费事件薄适配 |

来源入口：

- [DS ACP 实现](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/acp/acp/src/index.ts)
- [DS 原生序列化](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/llm/llm-deepseek/src/serialize.ts)
- [DS 多供应商配置](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/llm/llm-pi-ai/src/catalog.ts)
- [Codex provider 协议](https://github.com/openai/codex/blob/eab2603712f90ec08ac44207a04eed158be293a3/codex-rs/model-provider-info/src/lib.rs)
- [Codex thread 合同](https://github.com/openai/codex/blob/eab2603712f90ec08ac44207a04eed158be293a3/codex-rs/app-server-protocol/src/protocol/v2/thread.rs)
- [Codex 服务文档](https://learn.chatgpt.com/docs/app-server)

DS 为 MIT、Codex 为 Apache-2.0；发行时保留相应通知及依赖许可。此处不作法律合规认证。

## 3. 最小 FIN 适配，不再制造执行内核

### 3.1 任务入口和事件

保留 Java/BFF 当前业务授权、命令身份、取消和成果接口。内部记录业务 command/run 与上游 session/turn/request 的映射；浏览器不能提交上游历史或冒充来源。正常状态由上游事件投影，不能另起状态机反复猜测模型是否已提交。

ACP session/cancel 是当前工作的取消；业务“关闭研究执行”另有永久授权状态，两者不得混淆。客户端取消一个 RPC 等待不代表远端任务已停。准备/入队/完成/保存成功分别表示不同事件，按真实含义映射。

### 3.2 工具与金融成果

保留现有原文查询、SQL、来源绑定计算器、工作笔记、稿件保存与版本校验、报告导出。上游调用 MCP 或工具适配器；宿主身份与资料权限不由模型传入。FIN 工具返回合理大小的正文窗口、结果和准确回读入口，不在工具内另做会话压缩。

当前 `organization_work_session.artifact_reader` 等路径从 LangChain 消息/artifact 恢复观察。采用新底座时须改为读取宿主保存的**成功工具观察**，复用现有来源记录/存储，不把普通模型文本或摘要视为来源。原文/计算记录不依赖上游摘要保真；不新增一套“判断真值库”。

已有 `WorkingMemory` 和 `calculate_from_sources` 可脱离 Agent 循环执行，本轮验证了这点。尚含 `ToolRuntime`/`Command(update=...)` 的交付、操作与委派边界需要抽出其业务服务，不能把整个 LangGraph Agent 当作每个 DS 工具的隐式后继。

### 3.3 预算和故障

保留根预算、失败/未知计费账、授权重试政策。它们在供应商请求前预留、请求后结算，包括子 Agent 与压缩，不向模型不断广播剩余回合数。

仅凭 ACP prompt 前检查一次余额不够：一次 prompt 可产生多个供应商请求。必须找到并验证覆盖普通请求、压缩、委派的统一上游扩展点；如果只能 fork 核心才能覆盖，应重新选型，不能通过隐藏未记录调用放行。

ACP 公共活动可能包含 thought 更新，产品不直接透传整个流；公开进展、内部诊断、来源回执分别消费。原始诊断保存在受权的运维线，既不伪装成研究正文，也不混进下轮研究指导。

## 4. 替换清单与兼容

| 现有模块/职责 | 处理 |
|---|---|
| `model_context.RequestSummaryMiddleware`、`conversation_summary.py`、continuous_context 配置 | 新路径退出，由选定上游负责压缩及窗口。现存业务记录保留；不在上游外再包一层自动摘要 |
| `continuous_context_surface.py` / 自定义旧历史退出 | 通用退出与计量交给上游；确有价值的来源去重转到工具响应层，需证明不隐藏材料 |
| `on_demand_research.py`、`conversation_agent` 的模型循环 | 被上游 Agent 循环替代；其中成果目录、保存、交付等业务逻辑抽成服务，不整文件盲删 |
| `organization_work_session.py` 的消息恢复/模型装配 | 替换为 session 驱动与成功工具观察适配；保留组织数据工厂和授权检查 |
| 专业操作、委派 | 主 Agent 按需选择；子任务执行采用同一上游底座。旧固定后继图不重新挂入新路径 |
| `source_bound_calculator.py`、工作记忆/稿件版本、财务库、检索服务 | 保留可追溯业务能力，复用存储。参数兼容应局部、无歧义、保留原输入 |
| Java/BFF、导出与费用账本 | 保留业务职责；替换执行驱动。无须更换数据库、知识库或重新 embedding |

不在线改写旧 LangGraph checkpoint 成 DS/Codex 原生日志。历史运行保留原版只读与运维恢复能力；新任务切换后只有一个默认新建入口，不按故障悄悄回退另一套 harness。迁移现有研究时以已保存成果、原题和可读来源建立明确的新会话；记录血缘，不能声称是原生无损续跑。

## 5. 本轮无模型验证

复现工具：`scripts/engineering/probe_harness_tool_boundary.py`。显式传入 Codex 二进制和**尚不存在**的输出目录。隔离 CODEX_HOME，供应商仅为 loopback 确定性 Responses 服务，不使用用户模型密钥。资料是合成夹具；计算器和 SQLite 工作笔记使用现有维护代码；动态工具由测试宿主派发。

链路：读合成资料 → 来源绑定计算 → 保存 v1 → 关闭进程 → 同一 thread 恢复 → 读 v1 → 追加保存 v2 → 连续三次手动压缩 → 再读 v2 → 中断在途回合。

结果：Codex `0.166.0-alpha.5.1`，13 次本地确定性供应商响应，6 次工具执行，0 付费调用。计算来源/期间/单位及 CALC ID 保留；过期版本写入不覆盖 v2；另一 owner 不能读到正文。首轮原工具未在恢复后重做。三次手动压缩均完成，没有两次终身上限。压缩后准确回读保存的成果。

失败和修正也保留：第一版探针在 contextCompaction 条目结束时过早开新 turn，收到 ActiveTurnNotSteerable；修为等待 turn/completed 后通过。扩大检查时曾错误期待跨 owner 读取抛异常，实际合同返回 found=false；修正探针，未修改业务实现。

`scripts/engineering/probe_dsh_transport.mjs` 使用上游原始 transport.ts，验证并发 RPC 关联、结构化内容、错误、等待取消及关闭。还明确验证：取消客户端等待后远端工作仍会完成，所以真正取消必须使用 ACP session/cancel。**这是传输层测试，不能代替 DS 完整 ACP、会话恢复或金融工具链验收。**

这些结果不证明 DS/Qwen 模型协议实测通过，不证明摘要忠实、自动压缩阈值合适、研究质量提升或实际费用下降。Codex 源码审阅 SHA 与本机二进制并未建立构建一一对应，不作同版本证明。

可重复执行（替换明确的本机二进制、上游源文件和新输出路径，不读运行中任务）：

```text
python scripts/engineering/probe_harness_tool_boundary.py --codex <codex-executable> --output <new-output-directory>
node --experimental-transform-types scripts/engineering/probe_dsh_transport.mjs <pinned-upstream-transport.ts> <result.json>
python -m pytest -q tests/test_working_memory.py tests/test_source_bound_quantity_literals.py tests/test_calculator_format_compatibility.py
```

本轮相关维护组件测试 70 项通过，active baseline、秘密扫描和 diff 检查通过。探针是显式运行的工程资格入口，不进入安装、CI 的默认依赖，不下载模型、不要求私有资料，也不注册生产服务。

## 6. 进入正式替换前只补这些资格

1. 锁定 DS 可部署发行版，运行原生 ACP：同一工具链、进程重启、主动取消、重复命令及异常退出；新组件在隔离环境运行，不占用当前服务。
2. 用供应商协议夹具验证 DS/Qwen 请求、thinking、工具、usage、失败与超时；验证预算覆盖所有请求。无模型测试不等于供应商实测。
3. 接入真实受权 MCP、现有 Java/BFF 命令和成果接口；复用现有检索发布，校验撤权与版本、导出。用工具权限控制访问，不将 shell 全开作为接入捷径。
4. 按新的 TokenBudgetBasis 才开始有界真实研究，检查自然工具选择、跨压缩接续和研究质量；不得借选型授权重跑旧 case 或自动重发失败付费调用。
5. 对照通过后切换唯一新建路径，删除被替代的运行时挂载和冲突配置。旧 checkpoint 的只读/运维兼容单独隔离；不维护两套活跃研究流程。

若第一/二项需要维护大量上游内部补丁，停止扩张该适配并改评 Codex 路线。不会为了兑现“选定”二字，把未验证候选强行上线。
