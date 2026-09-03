# FIN 0.1.3 Dell Agent Server Wave 0B 资格测试与 LangSmith 采用裁决

日期：2026-09-03

状态：`ADOPT_DIRECTION_OWNER_APPROVED / DEV_ONLINE_QUALIFIED / MAINLINE_SERVER_SEAM_AND_SDK_CLIENT_IMPLEMENTED / LEGACY_RUNTIME_RETIRED / NO_RUNTIME_FALLBACK / SECURE_LOCAL_COMPOSE_STATIC_QUALIFIED / FRESH_REVIEW_P0_P1_0_0 / LIVE_BUILD_BLOCKED_BY_REGISTRY / LANGSMITH_TRACE_PENDING_KEY / RC-S3-105_OWNER_DATA_GATE_OPEN / A03_ABSENT`

分支：`codex/fin013-dell-s1-s2-product-bridge`

实现基线：

- Wave 0B fixture：`16e040cb5ddd36c821f44c7f0a47362560b679da`
- resumable-stream 修正：`a101292dfb42930502b0f970286d5e3a0acb5d37`

## 1. Owner 裁决与范围

Owner 明确要求 Dell 纵切直接采用 LangSmith/LangGraph Agent Server，不实现、不保留自研 single-worker runtime fallback。该裁决只覆盖个人作品集、本机 development/testing 和本地演示；不声明 managed deployment、长期公网服务、商业部署或 production license 已具备。

“不商用”不等于免除 key/license。本地 Agent Server 测试仍需要可访问 LangSmith 的 `LANGSMITH_API_KEY`；生产 self-host 需要 `LANGGRAPH_CLOUD_LICENSE_KEY`。免费 LangSmith 账户可以创建 API key，官方也允许本地 Agent Server 免费用于 testing/development。因此合法的 Developer PAT 是下一次本地 Compose 资格测试的配置前置，而不是改造或绕开许可证的理由。

官方依据：

- [LangGraph CLI `dev` / `up`](https://docs.langchain.com/langsmith/cli)
- [Create a LangSmith account and API key](https://docs.langchain.com/langsmith/create-account-api-key)
- [LangSmith platform setup](https://docs.langchain.com/langsmith/platform-setup)
- [Agent Server data storage and privacy](https://docs.langchain.com/langsmith/data-storage-and-privacy)
- [Agent Server streaming](https://docs.langchain.com/langsmith/streaming)
- [Agent Server changelog](https://docs.langchain.com/langsmith/agent-server-changelog)
- [LangSmith plans and pricing](https://www.langchain.com/pricing)

Developer 套餐当前为零席位费并提供基础 trace 配额，但没有 LangSmith 托管 Deployment；这不妨碍本机 Agent Server development/testing。Plus 的托管 serverless entitlement 与本机 Compose 不是同一能力。若未来把演示变为长期公网或真实用户服务，即使免费，也必须重新核 production 许可，不能沿用本记录的非生产结论。

## 2. 本轮没有做什么

- 没有 DeepSeek、OpenAI 或其他模型/provider 调用；
- 没有创建 A03、PaidFullChainExecution、ResearchRun 或 paid authority；
- 没有 S1/S2/MCP/Evidence write、报告生成或产品验收；
- 没有实现 FastAPI/SQLite runner fallback、queue、scheduler 或第二套 Agent framework；
- 没有把 `langgraph dev` 称为 production 或最终部署态。

## 3. Z 盘隔离环境

资格根：`Z:\FIN_Insight_Agent_qualification\20260903_agent_server_wave0b_v1`

固定环境：

| 项目 | 版本/事实 |
|---|---|
| Python | `3.13.7` |
| LangGraph | `1.2.11` |
| langgraph-api | `0.13.3` |
| langgraph-runtime-inmem | `0.33.3` |
| langgraph-cli | `0.4.31` |
| langgraph-sdk | `0.4.4` |
| LangSmith SDK | `0.12.1` |
| Docker Engine | `29.5.2` |
| Docker Compose | `5.1.4` |

Windows 上实测到两个 upstream 启动条件：

1. `langgraph-cli[inmem]` 在彩色 Windows terminal 路径缺少 `colorama`，资格环境补装并固定 `colorama==0.4.6`；没有修改 vendor source。
2. `langgraph-api==0.13.3` 读取包内 OpenAPI 文件时受 Windows GBK 默认编码影响，必须设置 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`；否则出现 `UnicodeDecodeError`。这被记为部署前置，不在 FIN 代码中复制 vendor parser。

正式 `dev` 命令固定为 loopback、无热重载，并将每个 worker 的 concurrent-job cap 配置为 4：

```text
langgraph dev --no-reload --no-browser --host 127.0.0.1 --port 2024 --n-jobs-per-worker 4
```

资格运行显式关闭 tracing/CLI analytics，并移除 LangSmith、LangChain 与 production license key。服务日志确认未启动 control-plane metadata loop。进程 TCP 快照只观察到 loopback established connection；这证明该快照未见外连，不是完整网络抓包或永久无 egress 证明。

## 4. 不可变失败与根因

`dev-qrun02-clean-16e040cb` 暴露真实 SSE 风险：probe 同时请求 `stream_mode=["updates", "values"]`，实际事件 ID 为：

```text
1788398716043-0
1788398716044-0
1788398716045-0
1788398716045-0
```

最后两个不同 frame 共享 ID。定向复现中，客户端若在第一帧后以该重复 ID 恢复，返回 0 个事件；因此存在“同一 ID 的两帧之间断线时第二帧丢失”的窗口。该结果拒绝 multi-mode 原生流用法，不拒绝 Agent Server。

失败回执：

`Z:\FIN_Insight_Agent_qualification\20260903_agent_server_wave0b_v1\attempts\dev-qrun02-clean-16e040cb\probe_failure_receipt.json`

SHA256：`883e8a10aa38e20880323aa507ae720ad35ffaa2eb76916c28d75526f12e814f`

修正后的正式客户端合同：

- 原生 stream 只订阅单一 `updates`；
- 完整 checkpoint/state 通过 `GET /threads/{thread_id}/state` 获取；
- live event ID 必须非空、唯一、有序；
- `Last-Event-ID=-1` 必须精确重放完整流；
- 再用真实收到的第一帧 ID 恢复，结果必须严格等于后续 suffix；
- FIN BFF 使用独立的 canonical projection sequence，不把 Agent Server 多 mode frame 当成 FIN 领域事件协议。

修正经 5 个确定性测试、compileall、diff check 和作者分离复审通过，独立结论 `P0=0 / P1=0`，随后形成并推送 `a101292d`。

`dev-qrun03-clean-a101292d` 在启动前因机械复制带入 ignored `__pycache__` 而主动废止；server 未启动、probe 未运行。它没有被删除或覆盖，abort receipt SHA256=`872fa70bb70b755d54dd7edcf752baa9fea04e8c3d5440986f59b156dd4f680f`。

## 5. `dev-qrun04` 在线资格结果

正式输入从 clean `a101292d` 逐文件复制并核对 5 个 source/config 文件 SHA256。Agent Server 成功加载 4 个零模型 graph，配置 per-worker concurrent-job cap=`4`。hardened probe 发生 69 次真实 HTTP/SSE 交换，以下全部通过。图内和跨 thread 的时间窗口重叠证明 concurrency；本次没有证明 multi-worker deployment、worker failover 或 HA：

| 检查 | 实测结果 |
|---|---|
| server surface | health/info/OpenAPI；47 paths，必需 thread/run/state/cancel/stream paths 存在 |
| assistants | 4 个 graph 全部注册 |
| thread multi-run | 同一 thread 两次 run，状态 `2 → 5`，两个 run ID 均保存 |
| interrupt/resume | interrupt 暴露 1 个结构化请求；resume 创建第二个 server run 并得到 `execute_allowed` |
| graph 内并行 | left/right 执行窗口真实重叠 |
| 跨 thread 并行 | 两个 slow run 执行窗口真实重叠 |
| 同 thread 并发 | 第二个 run 以 HTTP `409` fail closed |
| cancel | run 从 `running` 进入 `interrupted` |
| 非法输入 | unknown assistant=`404`；malformed thread=`422` |
| SSE live/replay | `metadata + updates` 两帧 ID 唯一；从 `-1` 完整精确重放；从首帧真实 ID 精确返回 1 帧 suffix；无 `values` frame |
| state companion | thread state 的 `total=1`，证明单一 updates stream 可与公开 state endpoint 组合 |

完整成功回执：

`Z:\FIN_Insight_Agent_qualification\20260903_agent_server_wave0b_v1\attempts\dev-qrun04-clean-a101292d\receipts\agent_server_zero_model_probe.json`

SHA256：`c5eb6793ff1fc1c6fe017653e4944db8a15ac449692bcb5c0fa08ec6de1f2f54`

资源快照：启动后主进程 working set/private 约 `104.74/85.48 MiB`；probe 后约 `108.08/88.21 MiB`，累计 CPU 约 `2.719s`。这只是 zero-model Windows dev 主进程快照，不代表 Docker `up`、真实模型、多 Agent 或最终产品容量。

## 6. 重启恢复：部分通过而非完全 PASS

同一 `dev-qrun04` 正常停服后，`.langgraph_api` 在 Z 盘保存 checkpoint、ops 和 store pickle。原目录重启后：

- thread state 恢复成功，原 `total=5`；
- 原两个 run ID 恢复成功；
- 原 completed resumable stream 以 `Last-Event-ID=-1` 查询时 HTTP 200，但 body 为 0 bytes；
- PowerShell `Invoke-WebRequest` 与 Python `httpx 0.28.1` 均复现空流，排除单一客户端解析问题。

重启回执：

`Z:\FIN_Insight_Agent_qualification\20260903_agent_server_wave0b_v1\attempts\dev-qrun04-clean-a101292d\receipts\restart_recovery_receipt.json`

SHA256：`e3abbaa1de31e1cf73fdcb4c747ef92af13040382cabef2d905ecf588e32dd7f`

解释：`langgraph dev` 的 in-memory 开发 runtime 足以证明在线 API、并发、interrupt/resume、cancel 和同进程断线续传，但不能证明 completed stream 在进程重启后的历史 replay。官方文档保证 `stream_resumable=true` 与 `Last-Event-ID` 的断线续传，但没有把完整 Compose 停止/重启、Redis 重启、retention TTL 之后的 replay 写成稳定保证；因此这些项目必须在固定版本、checked-in 的安全 Compose 上实测。

## 7. 身份和职责映射

| FIN 领域身份 | Agent Server 身份 | 基数/规则 |
|---|---|---|
| `AgentSession` | thread | 一个用户研究会话固定一个 server thread；产品 follow-up 可创建新的 FIN ResearchRun，但不伪造新 session |
| `ResearchRun` | 一个或多个 server runs 的领域 aggregate | interrupt/resume、责任 Agent 修复等可产生多个 server run；ResearchRun 不等于单个 server run |
| `RunInvocation` | server run | 每次 server run 对应一个不可复用 invocation；resume 是新 invocation |
| `ActionAttempt` | FIN immutable receipt | 模型/tool/外源动作仍由 FIN receipt 记录，不映射为 server 内部 task 或 queue row |

Agent Server 拥有 assistant/thread/run/task queue/stream/cancel/interrupt 执行语义。FIN 只拥有 Evidence、NumericFact、Claim、Decision、Gap、SessionEvent、权限、人工 authority、artifact reference 和审计安全 projection；业务代码不得查询 server 内部 PostgreSQL 表推导 FIN 真值。

## 8. 当前 key 与部署门

本机 Process/User/Machine 三个 scope 均未配置 `LANGSMITH_API_KEY`、`LANGCHAIN_API_KEY` 或 `LANGGRAPH_CLOUD_LICENSE_KEY`。因此本记录没有运行、也没有声称运行最终安全 Compose 或真实 LangSmith trace。

下一次部署资格测试必须：

1. 由用户在免费 LangSmith 账户创建合法 PAT，并通过本机环境或 ignored secret file 配置；密钥不得粘贴到聊天、Git、receipt 或日志；
2. 保持 `LANGSMITH_TRACING=true`，并将 `LANGSMITH_PROJECT` 唯一固定为
   `fin-insight-dell-reference-vertical`；实际产品 execution 若缺 tracing、PAT 或精确项目名必须 fail closed；
3. 固定 Agent Server image/API version，启动官方 Agent Server + PostgreSQL + Redis 三容器栈；
4. 重跑本记录 69-exchange probe；
5. 分别测试短暂客户端断线、Agent Server/API 容器重启、Redis 重启、整个 Compose 停止/启动和实际 retention 边界；
6. 每次先读 thread/run state，再验证 single-mode `updates` suffix replay；SSE 历史帧永不作为唯一 FIN 真值；
7. 保存 image digest、compose、资源、egress、数据驻留和不可变成功/失败 receipt。

这条门未通过时，Wave 4/5 serving、最终本地演示和产品验收保持 false；处理方式是修正配置或如实报告 Agent Server 边界，不是实现 fallback。

## 9. 下一合法工程入口

Wave 0B 已经完成“选哪条路”的裁决和 dev 在线语义证明；checked-in 安全 Compose 的 deployment parity 仍是并行阻断门。为避免等待 key 时再次停在文档上，下一项零模型工程工作立即回到原最早责任层 `RC-S3-105`：

1. 从当前 1,025 nodes、61 Reviewed Evidence、S2 和 r12 external pack 生成 answer-free current inventory；
2. 固化 `BaselineSourcePlan / MinimumRouteObligation`；
3. 实现 bounded `SourceFamilyCompiler`，把模型语义 intent 编译为真实物理 selector；
4. 拆分 local/reviewed/external discriminated tool schema；
5. 重放 A02 的 17 个请求，使错误成为 typed feedback；
6. 通过 nonzero、cardinality、issuer、period、role、route、authority、Reviewed-first、overwide 和 Q1–Q9 coverage 回归。

`RC-S3-105` 仍阻断 A03 和任何新模型/provider/paid successor。当前没有真实 S1/S2 tool loop、multi-agent、HITL 前端或 Dell 最终报告，不能把本轮 runtime qualification 写成产品纵切完成。

## 10. Mainline Agent Server seam 与官方 SDK 客户端（2026-09-03 13:28）

Owner 再次明确“直接使用 LangSmith，不商用，不要 fallback”。因此当前分支已经把该方向从资格结论落到 mainline 接缝，但仍没有把未批准的数据或模型调用伪装成完成：

- 根配置 `langgraph.json` 只暴露一个 product graph：`dell_reference_vertical`；
- product graph 通过 import-safe async factory 加载，checkpointer、store、thread、run、task queue、stream 和 cancel 均由 Agent Server 拥有；
- FIN 继续拥有 `AgentSession / ResearchRun / RunInvocation / ActionAttempt` 与 Evidence、NumericFact、Claim、Decision、Gap，不读取 Agent Server 内部数据库表充当业务真值；
- 官方 `langgraph-sdk==0.4.4` 客户端实现 thread 创建、start、resume、新 invocation、单一 `updates` stream、`Last-Event-ID` replay 和公开 state read；没有 direct graph invoke、FastAPI、SQLite、应用自建 queue 或运行时 fallback；
- deployment 端强制 `LANGSMITH_TRACING=true`、非空 PAT、以及唯一
  `LANGSMITH_PROJECT=fin-insight-dell-reference-vertical`；客户端逐 run project override 被拒绝，因为 Agent Server 0.13.3 会把这类 run 同时复制到 run-project 与 deployment default project，造成重复 trace 与配额浪费；
- 当前 execution 在打开 provider、MCP、corpus 或数据库之前仍以
  `dell_execution_data_authority_not_approved` 停止；这不是 fallback，而是尚未获得 Owner 数据门裁决的真实阻断。

真实 loader 复证使用固定 Z 盘环境与 `langgraph-api==0.13.3`：

- package module 成功导入；
- `/assistants/search` 只返回 `dell_reference_vertical`；
- `/assistants/{id}/schemas` 返回 6 个严格 graph inputs 与 3 个严格 FIN context IDs；
- 生成 Dockerfile 基于 `langchain/langgraph-api:0.13.3-py3.13`，先明确安装固定的 LangChain/LangGraph/LangSmith/MCP/psycopg 依赖，再以 editable local package 安装仓库；
- `langgraph validate` 通过，当前相关联合回归 `168 passed`，`uv lock --check` 与 `git diff --check` 通过。

这次 loader 只证明 mainline graph 能被真实 Agent Server 加载和 introspect。它没有 LangSmith PAT，因而没有真实 trace；也没有运行 product graph、数据工具、模型或报告。最终本地演示仍必须在 ignored `.env` 中由 Owner 配置合法 PAT，并用 `deploy/dell_agent_server/compose.yaml` 启动 Agent Server + PostgreSQL + Redis，产生一条可在 LangSmith 中核验的真实 Dell run；不提供任何无 LangSmith 的备用执行路径。

官方 CLI 0.4.31 的裸 `langgraph up` 在当前本地模式会以 noop auth 把 API 及默认凭据 PostgreSQL 端口发布到所有宿主网卡，因此自本记录此版起不再是受支持的启动命令。唯一受支持的本地 serving 配置是由同版 CLI 生成语义固化的 checked-in Compose：API 只绑定 `127.0.0.1:8123`，PostgreSQL/Redis 不发布宿主端口；真实 `.env` 的配置校验只能使用 `docker compose config --quiet`，不得把解析后的秘密打印到 stdout。

FIN identity binding 当前能逐 run 校验并返回，但尚未由产品 ingress 持久化，也没有跨进程验证 one-to-one/one-to-many 唯一性。它是下一次真实 start 前必须补齐的领域数据接缝，不能把 closure-local 声明写成 durable receipt；这不会引入第二套运行时。

## 11. 无 fallback 与安全 Compose fresh 收口（2026-09-03 14:05）

Fresh reviewer 没有沿用作者结论，而是在 repo-wide 可达性与真实部署面先后发现三项 P1；三项均在本轮按最早责任层关闭：

1. 旧 Python runner 原本仍能用 SQLite checkpointer 直接 compile/invoke/resume。它现已变成 typed tombstone，旧 `start/resume` 在读取 key、数据或 checkpoint 前以
   `dell_legacy_runtime_retired_agent_server_langsmith_required` 和 exit 78 拒绝；三份历史 PowerShell launcher 同码先行拒绝。产品源码的 compiled helper/export 已删除，离线 compile/invoke 只保留在 tests；generic `runtime_foundation` 仅为 legacy test compatibility，且静态门证明 `src/scripts/apps` 无 checkpointer 执行消费者。SQLite/Postgres saver 依赖均在 dev group，不进入 Agent Server product extra。
2. 裸 `langgraph up` 默认以 noop auth 将 API 和默认凭据 PostgreSQL 发布到所有网卡。它已被降为 unsupported。唯一 local serving 配置是
   `deploy/dell_agent_server/compose.yaml`：API 只发布 `127.0.0.1:8123`，PostgreSQL/Redis 无 host port，PG 密码必须从 ignored `.env` 注入；配置校验必须用
   `docker compose config --quiet`，不能把 resolved credentials 输出到终端或日志。
3. 官方生成 Dockerfile 原先使用 `ADD .`，会把约 19 GiB staging/manifests/Codex/runtime/capture/report 本地资产送入 context/image。当前 Dockerfile 只
   `COPY pyproject.toml README.md src`，并用同目录 `Dockerfile.dockerignore` 先 `**` deny-all、再只允许这三类输入；数据、tests、reports、captures、Git/Codex/runtime state 不进入 build context 或 image。Compose 也不再注入整份仓库 `.env`，只显式传递 PostgreSQL URI、Redis URI、LangSmith key/tracing/project 和 DeepSeek key。

官方 SDK ingress 另增加了 `DellReferenceVerticalGraphInput.model_validate`，missing/wrong/extra/bad digest 会在 server call 前 typed fail，而不是依赖 StateGraph schema 静默过滤。服务端继续固定唯一 LangSmith project 并拒绝 run-level trace replica。

作者最终相关合并回归为 `205 passed`，real Agent Server loader 再次只返回一个 graph 与正确 6-input/3-context schema；`langgraph validate`、`uv lock --check`、Compose `config --quiet` 和 `git diff --check` 通过。Fresh、作者分离终审最终为 `P0=0 / P1=0`。

真实 Docker build 已启动过一次资格检查，但 Docker Hub auth endpoint TCP timeout，且本机没有
`langchain/langgraph-api:0.13.3-py3.13` 缓存，所以在 base metadata 阶段停止，尚未处理 context，也未生成 image。正确状态是
`STATIC_CONFIG_QUALIFIED / LIVE_BUILD_BLOCKED_BY_EXTERNAL_REGISTRY_TIMEOUT`，不是 build PASS。网络恢复后仍须记录 base image digest、context bytes、image filesystem、依赖 inventory/SBOM，再启动三容器并测 persistence/restart/SSE。

终审保留的非 P1 边界：

- 合法 LangSmith PAT、唯一 project 的真实 trace/upload/flush 和 trace privacy 尚未验证；
- FIN↔server identity 只有逐 run binding，尚无 durable unique mapping 和 ownership transaction；
- raw Agent Server API 不承诺完整 Pydantic runtime validation，未来 BFF/shared ingress 必须禁止绕过官方严格 client；
- local Compose 是 loopback/noop 单用户边界；镜像 digest、SBOM 与真实 up 尚未资格化，对外或共享部署必须另加 auth；
- legacy `runtime_foundation` 只读 projection 仍增加认知成本，未来历史测试迁移后再物理移出 `src`。

Project OS 直接测试当前另有一个与本轮 changed paths 无关的既存 sealed SHA drift：
`81 passed / 1 failed`，失败为 current dynamic writer successor 绑定的
`src/sec_agent/project_os_preflight.py` SHA 与当前 HEAD 不同。该文件工作树未修改；本轮不篡改旧 authority 来制造绿灯，须由其 owning stage 另做 non-overwriting successor。

因此当前不是 Dell 纵切 PASS。下一合法动作仍是：Owner 决定 physical/Reviewed data gate；用户在 ignored
`.env` 配置合法 LangSmith PAT 与本地 PG password；随后先完成 real build/supply-chain qualification、durable identity 和 approved MCP composition，再运行第一条真实 LangSmith-traced Dell run。
