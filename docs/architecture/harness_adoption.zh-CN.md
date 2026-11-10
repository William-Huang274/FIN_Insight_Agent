# 研究工作台采用上游 harness：选型与替换边界

2026-11-02。状态：**DS Harness 固定发行包的 ACP 进程、DS/Qwen 协议和金融工具夹具已通过；隔离服务已接通 Java/BFF 恢复命令，NVIDIA 原任务完成真实历史回读，完整研究与真实压缩验收仍未通过**。Codex app-server 保留为对照实现。宿主只为迁移验收任务选择新执行路径，尚未切换全部新任务入口。此前按需研究 A/B/C/D/E 的产品能力继续保留；本文件调整其执行内核的归属，不另建第二套业务流程。

## 1. 决策与证据强度

目标是采用上游维护的 Agent 循环、会话、压缩与取消机制；FIN 负责研究工具、金融语义、成果、用户业务与费用政策。不能复制两个上游的内部实现，再长期维护第三个内核。

候选顺序：

1. **DS Harness 原生 ACP 服务进程**：当前研究以 DS 为主，并要求保留 Qwen 路由。其原生 DeepSeek Messages 适配保留 thinking/tool replay；pi-ai 插件提供其他协议扩展点；ACP 有会话创建、恢复、关闭、取消、MCP 接入和模型选择。适配层只翻译宿主命令与事件，不控制每一轮研究。
2. **Codex app-server**：工具、持久会话、压缩和取消的服务接口清晰，已完成本项目进程级无模型工具链验证。固定源码中的 WireApi 仅接受 Responses，不能把我们已有 Chat Completions 地址直接换上；DS 已提供 Responses 也不意味着所有返回字段、thinking 回传、Qwen 路由已兼容。若 DS 候选无法用公开扩展点满足准入，而 Codex 的实际供应商路径可用，再调整选择。

这是适配成本判断，不是模型质量排名。两边均已运行完整服务进程的无模型夹具。DS 使用官方 Python runtime wheel `0.2.1rc2`，二进制报告 `0.2.1-rc.2`；没有构建整个 monorepo。源码审阅 SHA 与发行二进制没有建立可复现构建对应关系，不能混称同一构建。不能把夹具通过当作供应商真实模型、研究质量或 Java/BFF 生产接入通过。

## 2. 固定来源，实际读实现

DS 源码固定 `ce7073d51254c26cd63b22a60835b8f948deb447`；Codex 固定 `eab2603712f90ec08ac44207a04eed158be293a3`。固定版本用于可复查，不表示未来应自动跟随 master。下载文件逐项记录 SHA256；不是读完所有仓库文件。

| 能力 | DS 实现证据 | Codex 实现证据 | 结论/待验 |
|---|---|---|---|
| 模型协议 | `packages/llm/llm-deepseek/src/{adapter,serialize}.ts`；`llm-pi-ai/src/{adapter,models,catalog}.ts` | `codex-rs/model-provider-info/src/lib.rs` | DS 原生 thinking/signature 与工具配对有代码；pi-ai 支持协议与兼容配置不等于 Qwen 实际请求通过。Codex Responses-only 源码明确拒绝旧 chat 配置 |
| 服务生命周期 | `packages/acp/acp/src/{index,session,model-control}.ts` | `codex-rs/app-server-protocol/src/protocol/v2/{thread,turn}.rs` | ACP new/resume/prompt/cancel 已做真实进程夹具；不能与 SDK 的 prompt/resume/wait 混为一谈 |
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

`organization_work_session.artifact_reader` 保留历史消息适配，但来源提取已归并为 `source_bound_calculator.sources_from_receipts`，原文读取抽出 `read_authorized_source`，来源恢复抽出 `artifact_reader_from_sources`。新底座可直接使用宿主保存的**成功工具观察**；旧入口也调用相同实现，不复制两套来源规则。授权检查、来源版本恢复继续由现行 navigation 承担，不把普通模型文本或摘要视为来源。原文/计算记录不依赖上游摘要保真；不新增一套“判断真值库”。

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

## 6. 固定 DS 发行包的进一步资格结果

官方 `deepseek-harness-runtime-bin==0.2.1rc2` Windows wheel SHA256：
`d38c18f5117859feedaaa791a0eea37b8644bc187118e7e6f3afa231a5381cb7`。
通过公开 profile overlay 组合最小 ACP 服务，无 core fork。关闭默认 shell、文件工具、会话日志及插件清单上传和自动重试；模型仅见 FIN 测试 MCP。

维护探针为 `scripts/engineering/probe_dsh_acp.py`；接入 seam 和内部合同在
[`integrations/deepseek-harness`](../../integrations/deepseek-harness/README.md)。

- DS Messages 与 Qwen Chat 两条路各通过完整进程链：各 19 次 loopback 请求、8 次工具执行、两版成果、一次进程重启恢复。6 次压缩开始，其中 5 次成功保存摘要，最后一次在取消测试中停止。不是 6 份成功摘要，也不是 19 次付费调用。
- DS thinking signature、Qwen reasoning_content 随后续工具历史回传，工具调用与结果配对正常。Qwen `enable_thinking` 实际进入请求。由夹具模拟响应，尚未证明真实供应商当前接口可用。
- 上游 `llm/stream` 公共钩子覆盖普通与压缩调用；各 19 次调用均先登记再取得终态回执。取消后继续请求被 FIN 边界拦住，供应商新增请求为 0。
- 发现原生压缩失败后可能继续尝试正常研究请求，故 FIN 薄边界在失败后停止本执行后续转发；没有改摘要内容或重写核心循环。未知用量仍需保留预留金额，不能把一个已保存的错误终态计为零成本。
- 提取成功来源观察与受权读取的公共业务函数，旧消息入口调用同一函数。原 NVIDIA 停点包含 87 条消息、56 条工具回执（51 成功、5 失败）。与修改前固定提交比较，13 份原文、5 份计算对象完全一致；未使用旧错误摘要，也未把旧历史伪装为 DS 原生历史。
- Python 相关回归 87 项、Node dispatch 测试 2 项通过。没有重做研究、embedding 或知识库发布。

仍未完成：生产请求账本端点与现有 PostgreSQL 预算/Java 授权的连接、真实受权工具与报告业务的完整接入、服务部署及 NVIDIA 真实压缩质量。夹具的 host 回执不能替代这些验收。磁盘曾出现 Z=0、D 低于 100 MB；后续证据改存隔离目录，未删除他人的资料，未在账本缺少空间时发起付费调用。

## 7. 进入正式替换前的剩余资格

2026-11-01 更新：已增加 `harness_dispatch_host` 内部 HTTP 宿主，复用现有
PostgreSQL 预算事务，接收维护中的 Java 运行准入 callable，并保留原始回执与
未知费用占用。单执行的失败阻断进入持久账本，不能靠重启清掉；正常连续调用
没有两次摘要或固定几轮的限制。实际部署仍需完成提供商原始 usage 绑定及
Java/BFF 生命周期组合，不能将 HTTP 夹具通过当作已经接上真实授权和工具。
此前 Python 回归 38 项、Node 边界 3 项通过。此次继续补上实际 provider-wire
转发与用量绑定：固定 DS 发行进程通过 loopback 接受请求，真实供应商密钥仅由
宿主持有，现有预算事务与一次性转发回执共同阻止未登记调用、SDK 重发和重启绕过。
原始事件在终态放行前落盘；缺少用量或终态保留费用预留。

2026-11-01 的 `--metered` 验证已运行实际 PostgreSQL、非特权 worker、HTTP 宿主、
传输代理及原生 ACP。DS/Qwen 各 19 次本地模拟响应、8 次工具执行、两版成果、
进程重启、6 次压缩开始（5 次完成，末次取消）；取消后额外请求为 0。数据库均保留
取消请求的未知用量预留。单独 DS 压缩失败测试也确认没有 fallback 研究请求。
这些测试的授权与价格仍是合成夹具，不能替代 Java/BFF 全链路和真实研究验收。

实际传输校验还发现旧 Qwen 压力夹具把大输入塞进 16k 声明窗口，pi-ai 将输出
额度从 2048 压到 1；原假账本没有发现。保留失败回执，将夹具改成能容纳测试输入
的 64k 窗口并提前触发压缩，未放松实际请求额度一致性校验。正式配置不使用这些
夹具数值，也不能为通过验收偷偷减小所需输出。

r7 原有容器已恢复，Agent Server 健康检查、NVIDIA 的 BFF 恢复预览和 Java
授权目录读取成功；未切换新 harness、未发起付费模型请求。真实 MCP/成果接入、
Java 命令到 ACP 的生命周期组合，以及 NVIDIA 的真实压缩仍未完成。

1. 锁定 DS 可部署发行版，运行原生 ACP：同一工具链、进程重启、主动取消、重复命令及异常退出；新组件在隔离环境运行，不占用当前服务。
2. 用供应商协议夹具验证 DS/Qwen 请求、thinking、工具、usage、失败与超时；验证预算覆盖所有请求。无模型测试不等于供应商实测。
3. 接入真实受权 MCP、现有 Java/BFF 命令和成果接口；复用现有检索发布，校验撤权与版本、导出。用工具权限控制访问，不将 shell 全开作为接入捷径。
4. 用户已授权以现有 NVIDIA case 验收。新的 TokenBudgetBasis 记录原题、输入规模、所需交付、质量风险、thinking、模型能力和停止条件。采用实际模型窗口及上游压力触发；不沿用两次摘要终身上限、小窗口或几次调用后强制收尾。主模型与摘要的输出容量分别配置，遵守供应商能力。宿主持续记录费用/输入规模/新材料/成果变化；正常读取不算无进展，多轮相同动作且没有新依据或成果才考虑中断。失败、未知计费、截断和执行故障仍须停住。监督不自动授权付费重试，不重跑已成功研究。
5. 对照通过后切换唯一新建路径，删除被替代的运行时挂载和冲突配置。旧 checkpoint 的只读/运维兼容单独隔离；不维护两套活跃研究流程。

若第一/二项需要维护大量上游内部补丁，停止扩张该适配并改评 Codex 路线。不会为了兑现“选定”二字，把未验证候选强行上线。

## 7. 组织业务工具与官方 ACP 组合接入（2026-11-01）

候选代码已接到 `organization_native_runtime` 的宿主选择点：沿现有 Java 命令授权、
当前权限、根预算和来源范围，调用官方 ACP Python SDK。新路径不挂载旧 Agent 循环、
摘要 middleware 或按阶段保留历史的规则。上游负责会话历史与压缩；FIN 的 ToolNode
仅执行业务工具及持久化原始观察，不调用模型。

复用的能力包括来源目录/分页回读、来源绑定计算、方法读取、工作笔记、报告保存与
局部修改、引用绑定和交付版本。草稿校验失败保留草稿，允许只修变化字段；保存不等于
交付或独立复核。恢复命令遇到已完整保存的前序响应时直接投影成功结果，避免因主流程
落盘中断再请求模型。取消先撤销新调用/工具准入，再发 ACP cancel。

无模型证据：同版 Windows/Linux ACP 进程均完成真实 MCP 读取、计算、工作笔记保存、
进程重启、原生压缩后回读及取消。供应商响应为确定性夹具，均 8 次本地请求、1 次压缩、
4 次业务工具执行、0 付费调用。原 NVIDIA 的 87 条消息、18 个来源/计算对象经过业务
存储重启仍一致，CALC 原回执可准确回读；错误旧摘要未注入新 ACP 历史。

**剩余边界：**组合代码和进程测试不等于 Java/BFF 实际队列已经验收；付费摘要的忠实性
和研究推进仍须用原 NVIDIA 任务验证。按需子任务、独立复核未完成新底座资格；明确要求
独立复核的任务会在调用模型前报能力未就绪，不进入旧循环兜底。业务工具历史持久化的
长期磁盘增长尚未做规模验收。宿主定向绑定仅用于迁移资格，最终仍按第4节切换唯一新任务入口。

实际服务冒烟另定位一个旧路由缺陷：`catalog` 在进入元数据分支前被 lifecycle
`access()` 强制预热候选库，单次目录及回读组合耗时135.81秒。目录现在走固定发布的
document-catalog，保留当前权限、版本绑定与关闭状态检查，不打开正文或候选生成。
回归将 `prepare` 和原件读取设为一旦调用就失败，验证真实组合入口不会再隐式全库准备。

TokenBudgetBasis 的字符数和输出额度由宿主按实际模型容量、任务风险与资金预算声明，不再在共享数据结构中限制为 100 万字符或 32,000 输出 token。每次请求仍校验该任务实际声明的上限与费用预留；这不会增加预算，也不意味着模型容量能替代资金准入。原生压缩继续由底座按上下文压力调度。

旧执行图迁移必须区分顶层任务检查点与嵌套研究检查点。替换执行图以后，SDK 未必还能解析旧子图；不能将仅含原题的顶层状态视为完整研究交接。可由运维导出准确旧检查点，并在宿主 `legacy_receipt_import` 中绑定执行、发布身份、原检查点坐标、文件位置和 SHA256。此文件只能来自受信任宿主，禁止接收浏览器或模型指定的路径。导入核对题目与稳定消息 ID，按摘要身份幂等合并原始记录；不恢复旧摘要、旧调度状态，也不将旧历史冒充 ACP 原生会话。正式切换前须确认来源及计算对象数量、身份与回读结果一致。

工具账本是独立持久化边界。MCP 处理器即使由外层 Agent Server 任务启动，也不能继承它的 Runnable 回放配置；通过上游 `set_config_context` 创建独立调用上下文，保留金融权限 ContextVar。此边界需在实际服务上验证，单独调用工具的测试不能代替完整组合验收。

显式恢复命令可以接续工具账本中尚未完成的单项只读操作：重新检查当前权限，沿原检查点和原参数执行，仅补齐对应回执，不重放已成功操作。旧错误留在检查点历史，新恢复回执通过准确的 `read_saved_result` 入口交给会话。效果未知的笔记或成果写入仍阻断恢复，须先核对效果；恢复不能清空待执行状态来绕过该检查。

MCP 客户端超时不代表服务端操作已经结束。模型费用准入须检查业务工具是否仍在执行；若有未完成操作，停止该运行后续模型派发，保留迟到回执供恢复核对。已配对的普通选项错误仍可返回模型处理。此检查防止模型在等待超时后猜测服务状态，不以更长模型额度或重写研究提示替代执行核对。

来源版本批查询沿用当前本地权限检查，但目录 SQL 使用 `attachments_metadata` 覆盖索引。旧实现即使不选择 body/pages，按 rowid 访问大附件行以取得后置元数据仍可能触及溢出页；改为从小索引取得身份、名称、摘要和时间，再关联已有摘要表。该索引是一次性、事务性的增量迁移，后续写入由 SQLite 自动维护，不新增来源副本或权限缓存。

已读原文回读只恢复选定对象及其计算依赖，不因为读取一段原文就重验全部历史对象。完整成果校验仍检查成果使用的资料。共享计算器的回执可能没有组织扩展字段；恢复时必须通过当前授权原文与递归计算依赖重算，保留计算 ID、数值、单位和来源链的精确一致性，不自行补写组织字段。显式跨任务范围、被改动的计算、无来源的未绑定假设均不能借此获得组织来源权限。目录项保留 `document_catalog_entry` 非正文类型，兼容旧工具通道时也不升级为引用依据。

## 干净接续的分支身份

离线诊断接续可在宿主配置指定 receipt_replay_id（UUID），仅允许与 isolated_receipt_replay 和固定摘要的 legacy_receipt_import 一同使用。相同分支恢复相同原生历史和工作空间；不同分支复用完全相同的已读回执，但隔离后续原生历史与笔记。缺省配置保持原部署路径。此入口不修改用户问题、模型提案或来源，不向浏览器开放文件路径或回放权限。

## ACP 过程文本与交付正文

### 计算口径与研究意见

计算的规范回执、CALC身份与原始公式保持不变。模型视图从已验证算术的AST生成`formula_basis`，逐个列出实际除法的分子、分母表达式与操作数键；比例之差保持两个除法，不猜一个“总分母”。操作数沿原回执保留来源、已有期间单位和假设，rationale解释计算所回答的问题。旧回执经相同投影可读，不迁移存量CALC、不要求模型重填计划或口径表。精确`read_saved_result`仍返回原始JSON，展示字段不改变其JSON Pointer地址。

该结构只披露公式，不证明分子分母具有所声称的金融含义，也不自动识别正文中的范围、补数或归因。未验证或未知表达式不生成推断；旧回执照常可读。比较与取舍仍由模型负责，不能把机械拆式通过宣称为语义检查通过。

基本研究指导与现有research_loop/counter/finance/verifier方法共同要求：优先验证改变推理路径的旧前提；复核的错误诊断和建议解法分别检验；已发现的冲突落实为统一口径重算、分开呈现或撤回数量结论。复核交付核验路径而非强制替换答案。沿用现有按需方法与复核入口，不增加固定角色链、自然语言硬拦截或额外必填表。实际效果用原问题/材料的干净分支验证，并分别统计修复、漏检、新增错误；调试过的题目不能再称未见题。

宿主 binding 可通过 `preloaded_research_methods` 选择已有方法 ID，按配置顺序将完整正文及资源摘要加入模型 system；缺省为空，不改变已有行为。正文与 `get_research_method` 共用维护资源，不新增题目分类、必经流程或权限。方法选择错误在模型调用前报告；对照试验须另开干净会话，固定原问题、材料及模型配置，并检查真实请求中的方法内容。提前加载仅证明输入可见，不能代替研究质量验收。

ACP 的 `agent_message_chunk` 同时包含工具之间的公开说明和末轮回答，不能将整个 prompt 的所有文本直接拼成最终成果。适配层以新工具调用为消息段边界：调用前的文本保留在 `progress_text` 与完整事件日志中；最后一次新工具调用之后的文本分片组成 `text`，供现有交付与引用绑定消费。没有工具时保留全部文本；晚到的完成更新或同一工具的重复通知不能清空正文。工具执行后没有新回答时，不能把之前的过程说明自动算作已交付答案。中断/截断仍按原停止状态处理。

`acp_terminal_text.v1` 仅改变交付投影，不改变原生历史、模型措辞或研究结论。恢复旧版完整回执时，核对会话身份与完整事件拼接是否等于原回执，再采用相同分段逻辑；不覆盖原始记录、不重调模型。缺少事件或记录不一致时明确报恢复证据问题，不猜测正文边界。实时公开文本事件继续保留，最终成果仅消费 `text`。

## 追加预算与完成状态的运维边界

预算追加沿同一 budget_id 保存不可变的授权 credit，不改原 limit_micros、不重新建包迁移余额。`ModelDispatchStore.add_credit` 与 `scripts/engineering/authorize_model_budget_credit.py` 仅供 provisioner 使用，要求金额、币种、唯一授权 ID 和授权记录引用；不作为模型工具或自动补发机制。相同 owner+授权 ID 重放幂等，改金额、引用或移到其他预算会拒绝。available=原上限+credits−实际费用−未结预留；既有未知请求仍占预留且不得自动重发。没有跨包转移或重新解释旧授权。

升级时先由迁移所有者在专用预算数据库执行 `005_model_budget_credit_v1.sql`，再部署新的 store。新库的显式 `install()` 执行003+005，随后004授权初始化；已有004无需重跑。005幂等重放，更新受限费用视图，worker只读credit，provisioner可追加但不能改删，原预算不可变触发器保留。不得让runtime自动执行DDL或持有provisioner凭证。旧limit字段仍表示初始上限，新增authorized_micros表示当前累计授权，不把两者混用于展示或准入。

Java命令 `received` 和其 result 中的 `pending` 是派发回执，reconcile核实是否派发，不追写最终运行结果。运行完成应检查准确run_id的实时状态，以及BFF成果的task_outcome/回答；不能据静态回执触发恢复或重跑。执行已提交、来源绑定通过、独立复核通过分别表达，来源句柄存在不证明对应句子的推论成立。

## 明确授权后的未知用量恢复

失败请求没有用量回执时，原始记录和预算预留继续保留，默认禁止接续。用户明确批准该次补发后，运维可运行 `scripts/engineering/authorize_failed_run_recovery.py`，提供 audit-root、thread-id、run-id、唯一 authorization-id 及 authorization-ref。命令使用宿主 `FINSIGHT_ORGANIZATION_RUNTIME_SECRET` 签署24小时有效的恢复授权，保存于审计根下独立的 operational-recovery-authorizations 目录；不调用模型、不改费用、不将部分结果标成成功。

授权精确绑定旧运行、全部未知失败请求ID和公开调用账本摘要。只有已有明确失败outcome、审计完整的请求可以授权；仅有started、审计损坏或缺失仍阻断。BFF预览与实际派发使用同一校验，只有recover动作可以消费；当前权限、最新运行、活动任务、Java持久命令和检查点校验照常执行。创建后继运行后，旧授权不再能为新的失败提供准入。没有向模型或浏览器暴露签署入口；不能把它当成自动重试策略。正常新请求仍从同一预算扣除原未知预留后申请额度。

## 业务检查点与历史归档

### 派发前准备失败的恢复

缺少调用日志不能直接解释为零费用。若运行在宿主配置检查等准备阶段失败，运维须核对准确的终止运行、原始错误证据和预算数据库的该运行派发记录。`issue_preparation_recovery` 只有在该运行没有派发记录、也不存在模型调用审计文件时才签署单独的24小时恢复回执。它不生成虚假的模型调用、不改运行失败状态、不补记零用量，也不释放其他请求的未知费用。

此回执是可信运维对派发前失败的核实，不是通过错误文字自动推断安全；不向模型或浏览器开放签署。BFF仅在最新失败运行的recover准入中接受，当前权限、检查点、Java命令和后续预算校验仍执行。出现新的模型审计、后继运行或签名过期时不得沿用。真实已派发但缺少用量的请求仍使用前述未知用量授权流程。

原生 ACP 继续拥有会话、压缩及接续；FIN 不因暂停、预算中止或恢复再导出一套全量状态。业务工具仍使用 LangGraph ToolNode 与 AsyncSqliteSaver 的执行、pending writes 和恢复协议。`checkpoint_objects.ObjectSerializer` 通过正式 serializer 扩展点将业务大对象保存在同一任务的 `business-objects.sqlite`，检查点及 pending writes 保存内容引用。隔离回放分支共享不可变对象，但会话、检查点、工作笔记和后续变更仍隔离。对象引用不授予跨任务或跨组织的读取权限。

对象事务先提交，随后才提交引用它的检查点；中断最多留下未引用对象，不能把部分写入标成完成。读取只验证实际使用的对象，不扫描整个资料库。旧原生序列化行仍可读，启动不做全库重写。每次写入仍需遍历当前业务状态来识别变化，这次优化保证不重复落盘大内容，不承诺消除全部序列化 CPU 或重建内存开销。

离线转换使用 `PYTHONPATH=src python scripts/engineering/compact_business_checkpoints.py --source OLD --output NEW --objects OBJECTS`，逐行保留检查点 ID、元数据及 pending writes，并验证还原后的原生序列化相等。输出必须为新文件；切换前停止写入者、验证恢复，再保留旧库作为迁移回退。`business-checkpoint.sqlite` 与任务对象库必须共同备份，不可只复制前者。不能将已使用引用格式的库交给不认识该格式的旧服务。需要回滚时一并还原旧库和旧代码，且不得丢弃切换后新增结果。

没有自动 TTL 删除或对象 GC。删分支不能直接删共享对象库；只有所有保留检查点、pending writes 和成果引用都解除后才可回收对象。原始失败响应、未知计费、已接受提案和来源/计算/版本身份照常保留。

历史目录去重使用 `scripts/engineering/archive_state_duplicates.py` 的 `build`、`verify --check-originals`、`restore --path RELATIVE`。标准 ZIP 每份相同字节只存一次，manifest 绑定所有旧相对路径、SHA-256 和长度。构建及验证不删除原件；恢复可写回原路径或测试目录，拒绝越界路径及覆盖不同内容。大规模退役只能依据本次已验证的逐文件清单，不可按 `offline-*`/`live-*` 名称整删。归档、manifest、恢复工具是原路径退役后的必要依赖；旧脚本启动前先恢复它所需的路径，不伪装成可直接读取 ZIP 的原生历史。

原文回读每页最多返回 12,000 字符。请求更大的窗口会收到第一段及可用的 next_offset。运维监督运行可在服务端 execution binding 中启用 stop_on_tool_error。错误回执仍写入业务检查点，同批后续成功动作可保存；下一次预算预留和实际网络派发均使用当前运行的工具状态检查。新运行可从显式恢复入口接续。

受监督复核恢复时，宿主根据前一次原生运行中失败的 MCP 回执 ID 匹配业务检查点。计算器的来源错误记录具体操作数、提交的引句与数值。只有历史搜索结果中可准确对应的原文读取入口才会返回给模型；多个候选保留为选项，无法对应时提供已观察来源目录。候选定位本身不产生引用。历史回执保留，恢复反馈附在原回执旁。

定量措辞核对按句对比当前稿与同一原生分支已交付版本，保存工作笔记时则用保存回执中的版本定位前稿。多项比例共享一个金额时，利用原 CALC 的分子、分母、引句、舍入精度与回读句柄提供对照；若作者已明确写出特定范围未拆分，在同一范围上直接作金额扣减会提示检查分配依据。假设场景可保留。工具 check_quantitative_changes 可在交稿前按需用于相关句子。终稿投影也记录提示；此检查是覆盖部分可识别表达的建议，不认证自由文本的语义，也不改变作者原文或要求全稿复核。

写工作笔记、局部自查或交付修订稿时，变更句中直接引用的可回读原文及已验证计算可以与此前使用同一引用的表述一同呈现。定性句也适用。回执区分原文、作者旧判断、以及算式给定分母下的百分数；分摊或因果是否成立由作者结合材料判断。未绑定引用的数量概括不由运行时猜测其分母。
## 显式导入的公共来源目录

宿主按执行身份、资料清单、原题及文件摘要校验旧业务记录后，联网工具可复用其中逐条验证的公共来源目录。授权精确到回执摘要和原任务身份，不放行该旧任务的其他记录。恢复时仅生成当前执行的导航绑定，保留原消息、候选 ID、URL 和来源正文；日期范围不一致的目录不自动沿用。普通会话没有这项导入授权，仍拒绝跨任务目录。导入校验在启动时完成，不等模型付费调用联网工具后才发现不兼容。

业务 MCP 就绪检查：私有 HTTP 服务在启动原生模型进程前，使用维护中的 MCP 客户端完成带授权的初始化与工具目录核对。原生派发插件还在首笔模型请求前验证业务工具已进入底座工具定义；失败不预留预算、不请求提供方。仅服务健康或插件配置 failOnStartupError 不足以证明工具已激活。通过后的原生压缩调用仍可不携带工具，不引入固定工具调用或自动研究重试。启动失败和先前错误交付保留原记录。

## 原生会话存储与包缓存

宿主可配置 `FINSIGHT_HARNESS_NATIVE_STORAGE_ROOT` 指向已挂载的持久目录。在 Windows Docker 部署中应使用 Linux 命名卷承载原生会话热数据与上游包缓存。该配置同时用于作者和委派任务，不依赖某个 case ID。未配置时保持原目录兼容；逻辑工作目录、业务审计、任务身份和来源入口不变。

原生 `DSH_HOME` 按逻辑任务目录的 SHA-256 隔离于 `sessions/`，包缓存使用共享的 `package-home/`。此配置不迁移业务检查点，也不转发提供方密钥到子进程。已有会话尚未迁移时继续使用原原生目录与包缓存；绑定存在但新旧原生目录均不存在时启动拒绝。运维必须停止写入者，逐文件校验迁移后的原生历史与旧历史相同，再恢复。会话卷与业务审计必须共同备份；包缓存可重新安装，会话不能当缓存清理。回滚前必须保存切换后产生的新历史，不得直接使用落后的旧副本。

MCP 服务记录初始化、工具目录与调用阶段的耗时及 HTTP 状态，不记录凭据或工具参数。Python 客户端就绪不代表原生客户端已连通，实际验收仍需运行固定底座的初始化、工具调用、恢复和取消链。

来源回读区分证据段落、网页文档和工具回执。误将 `WEB::` 文档或 `fin-tool-` 回执交给证据段落读取器时，反馈给出相应的 `read_public_source` 或 `read_saved_result` 参数，保留模型提交的完整 ID；目标读取器仍需核对任务权限与已观察身份。此路由不确认来源存在，不自动取证或生成引用，也不要求模型重新搜索已有材料。
## 网页读取参数与多语种原件

搜索引擎、检索语言和发布日期过滤仅适用于不带文档 ID 的全局搜索。读取或文内搜索误带这些参数时，工具保留原参数、返回应移除的字段，由模型自行重提；不会代选来源，也不会把此类参数错误升级为整次研究失败。权限、存储、计费与来源身份故障仍阻止派发。历史失败回执保持原样，恢复时另外附上当前有效的参数反馈。

网页字节解码复用 Beautiful Soup 的 UnicodeDammit，识别显式 HTTP charset、BOM、HTML 编码声明和字节编码。Requests 对无 charset HTML 默认采用的 Latin-1 不再当作发布者声明。既有原件、引句和计算身份不回写；再次读取生成新正文摘要，缓存契约升级，后续读取不再命中旧解码缓存；旧缓存按原有到期策略退役，不删除历史研究证据。
