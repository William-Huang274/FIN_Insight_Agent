# FIN 0.1.3 Dell Agent Server Wave 0B 资格测试与 LangSmith 采用裁决

日期：2026-09-03

状态：`ADOPT_DIRECTION_OWNER_APPROVED / OWNER_DATA_GATE_ACCEPTED / REAL_ZERO_MODEL_DATA_COMPOSITION_PASS / FRESH_R7_ZERO_MODEL_LOCAL_CONTROL_PLANE_PARITY_PASS_BOUNDED / R8_PREFLIGHT1_NOT_STARTED_PATH_NORMALIZATION_CLOSED / R8_FRESH_ATTEMPT1_FAILED_ON_HARNESS_RUN_THREAD_STATUS_LAYERING_FALSE_NEGATIVE / R8_ATTEMPT2_CORRECTION_CANDIDATE / NO_RUNTIME_FALLBACK / FIN_SERVER_IDENTITY_FULL_R8_INTEGRATION_PENDING / LANGSMITH_RUN_TRACE_PENDING / GRAPH_MODEL_DEEPSEEK_MULTI_AGENT_PRODUCT_FALSE / A03_ABSENT`

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

## 12. Owner 数据门、fresh r6/r7 与零模型本地控制面收口（2026-09-04）

### 12.1 Owner 数据门与 real composition

Owner 已接受当前 32 条 physical routes，并明确保持以下边界：SMCI E11 只作为 Q9 的 F8 supplemental；Q3 本地 F3、Q4 本地 F4 的真实缺口保持为零而不伪造；Reviewed topic map 只作 selector；Micron SEC 8-K 只有在 issuer/CIK/accession 精确绑定时才能进入 F7；五个歧义 Reviewed 项继续排除并保留审计记录。

本轮随后运行的是真实、answer-free、零模型组合，不是 mock 数量：

- Owner decision digest：`739df0f5d2880af8e27a08b5f9e31e10e894f4900fb72681e7b02e065e89b204`；
- current inventory digest：`895c4663e9a19ea790101d92f3cb9696d20d6eff6b0e6495befc6d4959eb3f41`；
- provider/source route catalog digest：`eca993bb65edb2f41c9112912532316e07dd06cf3b46e61118d0851d7bda1002`；
- 组合结果：Reviewed=`56`、S2 observations=`1,319`、external routes=`12`、local candidates=`890`；
- provider projection 只有 36 条语义 route，不暴露 D/Z 盘路径、workbench/qualification 路径或 physical selectors；
- 官方 MCP client 已在本进程内实际调用冻结的 Evidence/Finance tools；model、DeepSeek、live external provider、外网和付费调用的授权及实际次数均为 `0`。

这关闭的是 `RC-S3-105` 的零模型 inventory/compiler/data-composition 根因，并证明 local in-process frozen MCP client tool execution；它不授权 A02 retry、A03、任何 paid/model execution，也不证明 Agent Server graph 发起的 MCP、实时外源 MCP capture 或研究答案质量。

### 12.2 r6 成功及后续审查 supersession

fresh r6 在当时定义的部署合同下真实 build、启动并通过，不删除、不覆盖，也不是伪造 PASS。作者分离复核随后发现其 PostgreSQL catalog fingerprint 没有覆盖 role GUC、`rolconnlimit` 与 `rolvaliduntil`；这些状态会改变运行角色行为，却可能绕过旧 fingerprint。因此 r6 保留为 immutable 的早期成功尝试，但不再代表 current qualification。

修正仍归 `RC-S3-106` 的 deployment/schema exactness 最早责任层，没有另造新的治理 issue。新版 fingerprint 还覆盖 schema/comment/ACL、role flags/成员边、database role settings、relation/index/sequence owner/ACL/security、column/default/collation、constraint/index definition/flags、trigger/function body、default ACL 与 database privileges。current attempt 改为 fresh r7，并把这些状态纳入 exact replay 与 drift detection。

### 12.3 r7 admitted catalog projection fingerprint、fresh deployment 与 image 证据

current fresh attempt：`20260904T0140+0800-zero-model-r7`，Compose project：`finsight-dell-qualification-20260904-r7`。

- implementation commit：`f0de87e024686660db4f5c0bfdcf85bddce1f120`；
- local image ID：`sha256:c658b11a177cb14949ee92a13b674f930dd24fb77d8265f2a59430ebee94fba6`，大小 `409,475,038` bytes；它只是本机 image ID，不是 registry-published digest；
- 040 source SHA：`dec88b731a59d696509c184cf45ea1344d5840d7aa0c07515b3902b3de9ddd00`；
- admitted/relevant catalog projection：91 rows，SHA=`28c2bb8501d78ca3b43e1a490acae050df46b8226d2c2511a34b99a1723ec4a8`；
- FIN runtime schema source SHA：`8102f5ab615bd616f64bd83f610b2e3c3206a9de023d7e27a48069f39e864209`；
- fresh Agent Server、PostgreSQL、Redis 三容器均 healthy；API 仅发布 `127.0.0.1:18127`，PostgreSQL/Redis 没有 host port；
- 六个产品数据目录全部 read-only，PostgreSQL 只有 named data volume 可写；API 未接收 DeepSeek key 或 FIN runtime URI；
- existing-volume installer 的 exact replay 返回 catalog contract match；三个数据库口令的 URL-safe、长度和两两不同门通过，相等的 dummy credentials 被拒绝；
- 事务内并回滚的 role global GUC、database-local GUC、unique constraint、function body、role membership 五类 drift 均产生不同 catalog SHA；没有留下持久变更。

本轮还对同一个本地 image 做了 host↔image exhaustive manifest 校验：249 个允许文件、`9,692,127` raw bytes，missing/extra/changed 均为 0，canonical manifest SHA=`57a08411937e0a791a38fe8e8cdae4f30dfbbf47af480c2f3437b47b42569411`。CycloneDX 1.5 inventory 为 707 components、987,816 bytes，SHA=`4ba5a4e16e9ca7a0ee0e702a5c85e5e180abbae94019acde4e17b462d4300ecd`；其 metadata 的 r5 tag 只是同一 `c658...` image 的旧 local alias，不是 r7 provenance，证据以 image ID 绑定。这只使 `sbom_inventory_generated=true`；由于尚无 CVE/license policy、signature、provenance 与 registry-published digest，`image_supply_chain_qualified=false`。镜像仍以 root 运行，当前 Compose 也没有 readonly rootfs、cap drop、no-new-privileges 或资源限制；LangSmith key 与 PostgreSQL URI 由容器 environment 传入，本地 Docker administrator 可 inspect，`container_secret_manager=false`。这些边界在 loopback 单用户 qualification 内接受，不能外推到共享或 production。

这里的 040 只对当前 FIN runtime 所承认的 91-row PostgreSQL catalog projection 做 exact binding，不是字面上的整个 PostgreSQL catalog。当前 r7 只读检查没有异常 relkind、column ACL 或 global migrator default ACL，因此不阻断本次 bounded pass；其他 relkind、column ACL 与更广 default-ACL hardening 作为 P2 保留，不能把当前证据写成 entire/full-catalog qualification。

### 12.4 FIN identity、官方 SDK thread 与 restart 证据边界

r7 上独立 FIN identity qualifier 产生 1 个 AgentSession、1 个 ResearchRun、3 个 RunInvocation；ordinal 精确为 1/2/3，同一 ordinal 3 的并发写入一胜一冲突，exact replay 幂等，连接池重建后仍存在。runtime role 对 update/delete/truncate/alter/drop trigger 的拒绝均为 SQLSTATE `42501`，migrator 对 append-only trigger 的拒绝为 `55000`；三个角色均非 superuser，migrator 为 nologin；table DML grants 只含 SELECT/INSERT，另有必要的 database CONNECT、schema USAGE 和 sequence USAGE/SELECT，没有 UPDATE/DELETE/TRUNCATE/DDL；六个保护 trigger 存在。

官方 SDK 只读/空线程 probe 确认 Agent Server 只有一个 `dell_reference_vertical` graph；输入 schema 精确要求 `case_id/foundation_digest/research_as_of/research_question/run_id/snapshot_id` 六项，context 精确要求 `agent_session_id/research_run_id/run_invocation_id` 三项，均拒绝额外字段。固定 thread `433f0098-d302-5993-979c-df81574455c3` 两次 `if_exists=do_nothing` 只得到一个 idle thread，values 为 null，runs=`0`。API restart、Redis restart、整个 Compose stop/start 后均能读回同一 idle thread；FIN counts 仍为 `1/1/3`，91-row admitted catalog projection readiness 仍通过。

以上只证明 control-plane loader/schema、空 thread 的 idle readback 与独立 FIN identity persistence。当前 synthetic FIN IDs 没有映射到该 live Agent Server thread，所以 `fin_server_identity_live_integration=false`；也没有 graph run，因此 `graph_execution=false`、`run_checkpoint_restart_parity=false`、`redis_execution_state_persistence=false`、`sse_restart_replay=false`、`single_job_enforced=false`、`exactly_once=false`。当前 `N_WORKERS=1`、`N_JOBS_PER_WORKER=4` 只是一份并发上限配置，不能写成单任务或 exactly-once 证明；server 内建 retry 与未来付费副作用的幂等仍须单独验证。

### 12.5 LangSmith 与代理诊断

r7 Agent Server 日志中的 metadata POST 返回 HTTP 204，且明确是 `n_nodes=0`、`n_runs=0`；API 与全栈重启后仍可达。这证明当前 PAT、固定 project `fin-insight-dell-reference-vertical` 与 metadata endpoint 连通，但没有 run/span，故 `langsmith_run_trace=false`、`trace_privacy_qualified=false`，也没有可在 UI 中验收的研究 trace。

Docker 当前通过 `http.docker.internal:3128` 代理访问网络。在该配置下，真实 image build、三容器启动和 LangSmith metadata 均已成功，因此代理不是 current blocker。较早 Docker/PyPI TLS EOF 与代理/VPN 波动存在合理相关性，但没有当时的 packet/proxy 证据，不能把它记为确定或唯一根因。`18123` 当时不可用另由 Windows 端口保留/动态分配行为解释；current r7 使用 loopback `18127`。

### 12.6 当前通过项、未通过项与下一门

当前唯一准确的通过标签是：`ZERO_MODEL_LOCAL_CONTROL_PLANE_PARITY_PASS_BOUNDED`。实现相关 targeted deployment+identity 回归为 `24 passed`，更广的相关集合为 `195 passed`；lock freshness、compileall、五份 JSON、shell syntax、diff 与 changed implementation secret-pattern scan 均通过。作者分离终审结论为 `P0=0 / P1=0`，仅适用于上述 bounded scope。全仓 plain pytest 因未安装可选 Dagster 依赖在 collection 阶段失败；排除该单个可选 Dagster 文件后的辅助诊断为 `3,162 passed / 6 skipped / 41 failed / 23 errors`，用时 `1,666.53s`，失败主要落在 claim-authority base input、Project OS sealed SHA、VS5 policy binding 与 immutable A02 replay。由于该长跑期间 closeout 文档和 append-only ledgers 正在写入，它不是 clean isolated qualification，也没有在本轮裁决这些跨阶段失败的根因。因此 `full_repository_suite_green=false`；不能用大量通过项覆盖失败，也不把这些失败未经审计地归因于本轮 r7 实现。

已经为 true 的 MCP 边界仅是 local in-process frozen MCP client 对 Evidence/Finance tools 的真实调用。仍为 false：FIN↔server live identity binding、跨事务 create→bind orphan reconciliation、真实 graph/run/checkpoint/resume、Agent Server graph-initiated MCP、live external MCP capture、Redis execution state persistence、SSE replay、LangSmith run trace/privacy、任何 model/DeepSeek、dynamic multi-agent、HITL、最终报告、产品纵切、shared/production deployment 和完整 image supply-chain qualification。

r7 不清理，receipt 与 SBOM 保存在：

- `Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/agent_server_control_plane/attempts/20260904T0140+0800-zero-model-r7/receipts/zero-model-local-control-plane-qualification.json`；
- `Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/agent_server_control_plane/attempts/20260904T0140+0800-zero-model-r7/receipts/agent-server-image.cyclonedx.json`。

qualification receipt 最终为 19,195 bytes，SHA-256=`c5821993bcb729c10e18c912ba4f27272afce707562a59cef4b35e83e2971ebb`；SBOM SHA-256=`4ba5a4e16e9ca7a0ee0e702a5c85e5e180abbae94019acde4e17b462d4300ecd`。仓库中的 closeout 文档以这两个摘要绑定 Z 盘证据；后续若需纠错必须创建 successor receipt，不能静默覆盖。

下一合法门不是启动 A03 或调用模型，而是：实现 live FIN↔server ingress/binding 和 remote-create→FIN-bind orphan reconciliation；验证 Agent Server retry/idempotency；运行一条真实零模型 graph，覆盖 checkpoint/resume、API/Redis/full-stack restart、SSE retention/replay，并产生可核验的 LangSmith run trace 与 privacy 结论。只有这些门关闭后，才向 Owner 提交新的 `PaidExecutionOwnerDecision` 与 task-specific `TokenBudgetBasis`，申请第一条新的 paid/model successor。

### 12.7 r8 live graph candidate 已实现、现场 attempt 尚未启动

本轮没有继续写通用 backend/runtime，而是在同一正式图和官方 Agent Server SDK 接缝上
完成最窄 r8 candidate：

- client schema 升到 v1.1；profile、当前 deployment 唯一 concrete assistant UUID、
  FIN 三层 identity digest 与 launch digest 进入 remote metadata；create 前与不确定响应
  后做 bounded exact reconciliation，分页、不稳定快照、重复、身份/assistant 冲突均
  fail closed，no-match transport exception 明确为 `outcome_unknown` 且不自动重发；
- Agent Server entry 在打开 approved data composition/MCP 前反查 FIN durable binding；
  product/qualification profile 分离，LangSmith input/output hiding 只接受 pinned client
  真正识别的字面值 `true`，入口异常不再 chain 原始输入/路径到 traceback；
- 同一 `dell_reference_vertical` 图增加固定 Q1 zero-model 路径：真实 Evidence/Finance
  MCP → content-free summary → native interrupt → ordinal 2 resume；resume 不重跑工具且
  `final_report=null`；
- 显式 qualification overlay 只用于 fresh project，并只读挂载资格 phase probe；宿主
  runner 固定 `finsight-dell-qualification-20260904-r8`、loopback `18128`、fresh named
  volume、API/Redis/full-stack restart、SSE full/suffix replay 与 LangSmith trace audit；
  runner 没有 `down -v`、volume delete、旧 attempt overwrite 或 DeepSeek 注入路径。
- pre-live review 修正三类 false-pass：SSE 按 Agent Server 0.13.3 的正常 EOF 而非伪造
  `end` 帧，并从非末帧验证非空 exact suffix；manifest 用 Owner 数据门完整 digest 与
  冻结 `2026-09-02` as-of；四次 interrupted readback、resume/final replay 逐字段等值，
  LangSmith root 必须与 FIN durable `server_run_id` 相等，且完整 span 集须连续两次稳定；
  child failure 仍保留 content-minimised command observation 与 typed phase failure。

最新相邻回归命令为 `.venv\\Scripts\\python.exe -m pytest` 加下列 13 个文件：
`test_dell_agent_server_data_composition.py`、`test_dell_agent_server_client.py`、
`test_dell_agent_server_live_r8.py`、`test_dell_agent_server_identity.py`、
`test_dell_agent_server_entry.py`、`test_dell_agent_server_deployment.py`、
`test_dell_current_capability_inventory.py`、`test_dell_reference_vertical_real_composition.py`、
`test_dell_reference_vertical_mcp_tools.py`、`test_dell_reference_vertical_graph.py`、
`test_dell_owner_data_gate.py`、`test_dell_reviewed_evidence_inventory.py` 和
`test_dell_source_family_compiler.py`，参数 `-q`。working-tree candidate 结果为
`213 passed in 20.24s`（Python `3.11.14`）；同时
通过修改文件的 `py_compile`、`uv lock --check` 与 `git diff --check`。Compose
`config --quiet` 已在独立 qualification project name 与派生本地角色口令环境下通过，
且没有渲染 secret 到 stdout。该测试是 dirty candidate 工程证据，不是 fresh live qualification，
也不代表全仓绿色；没有另造 live receipt。Docker 当前代理仍为
`http.docker.internal:3128`；同一链路已完成 r7 build/start/LangSmith metadata，因此代理
不是 current blocker。`.env` 的 PostgreSQL 本地秘密不满足 init script 的直接
URL-safe/长度合同；r8 runner 只把它当 secret seed，在内存派生三个不同 64-char
口令，不回显、不改写 `.env`、不进 receipt。

Project OS 回归为 `81 passed / 1 failed in 35.35s`；唯一失败仍是既存
`current_dynamic_writer_submission_successor` 对未由本轮修改的
`src/sec_agent/project_os_preflight.py` sealed SHA drift。本轮不重签、不修补该历史
authority，也不把它归因给 r8；因此 `full_repository_suite_green=false` 保持不变。

本段是 pre-live implementation 记录，不是 r8 PASS。现场运行前仍需：作者分离只读
review、clean commit/push、fresh project/port/volume/attempt preflight。为避免把资格跑成
时序赌博，r8 不故意制造首次 FIN bind failure；该逻辑只保留 deterministic fake tests。
因此即便现场全绿，`durable_pending_orphan_reconciled_lifecycle`、
`automatic_retry_after_unknown_outcome`、`distributed_exactly_once` 仍为 false；本轮也
继续禁止模型、DeepSeek、live external research、Evidence admission、S2 write、HITL 和
最终报告。

### 12.8 r8 preflight1 未启动与 Windows 路径规范化

clean pushed implementation commit=`b5ae2aaa0125122fa1d8da399f3a048542bec9f7` 后首次调用
runner，但在 attempt 目录与任何 Docker command 创建前被
`r8_repo_root_mismatch` 拒绝；终端 failure projection 为 `commands=[]`、
`completed_phase_names=[]`、`cleanup_performed=false`、模型/付费 authority=false。
因此该事件是 `NOT_STARTED / PREFLIGHT_BLOCKED`，不是 live r8 attempt，也没有生成
Z 盘 attempt/receipt、Compose project、容器或 volume。

最早责任层是 host preflight 的 Windows path normalization：Git 返回
`D:/FIN_Insight_Agent`，而 Python `Path` 字符串为 `D:\\FIN_Insight_Agent`；原实现只做
case-fold 后的原始字符串等值。修正改为两边 `Path.resolve()` 后比较，并增加 Git
forward-slash 返回值反例。修正后窄相邻回归=`104 passed in 9.71s`，compile/diff 通过。
必须形成新的 clean pushed commit 后才能再次进入 preflight；不得把本次未启动事件算作
唯一 fresh live attempt，也不得修改 r8 的模型/外源/付费零权限。

### 12.9 r8 fresh attempt1：真实图已到 interrupt，但 harness 混淆 run/thread 状态而失败

修复 preflight 的 clean pushed commit=`2b88bbf106d7976b3bb0c2e804188289213e6af5`。
真正 fresh attempt1=`20260904T045906+0800-zero-model-r8` 已创建且必须永久保留为
failed；manifest SHA-256=`727cd3fb8803bf2711bbb46ca0d5def39b793834160c7d7edbcd3f72a0b50b5e`，
failure receipt SHA-256=`84046a2696e301200cf535cd4222202fa64a4c866fd4225704f1d4e96e36667b`。
Compose config 与 build/up 都成功，三容器 healthy，API 只绑定 `127.0.0.1:18128`；
attempt1 project、容器和 volume 未清理、旧 receipt 未覆盖、模型/付费 authority=false。

失败码=`r8_remote_terminal_status_mismatch`。只读现场证据不是图失败：同一个
server run=`01a06914-3ab5-71f2-8e7d-5f5bf162bb36` 实际为 `success`，thread=
`43a9046a-5c49-5d4d-bfdf-5a1d04a13500` 实际为 `interrupted`，current state 为
`phase=zero_model_mcp_qualified`、interrupt count=`1`、
`next=["qualification_interrupt"]`；Agent Server 原生日志同时记录
`run_status=success / thread_status=interrupted / has_next=true`、
`Background run succeeded`。因此最早责任层是 r8 harness：它把 dynamic interrupt 的
thread 状态错误地当成 run 终态。Docker 当前仍经
`http.docker.internal:3128` 成功完成 164.016 秒 build/up，图也本地执行 8.295 秒；
LangSmith phase 尚未开始，故本次失败不能归因于梯子、Docker 网络或 LangSmith。

同一 R8 的最小根修正是分层验收，不另造 runtime：START 与 RESUME 的 remote run 都须
为 `success`；START/readback 的 thread 必须为 `interrupted`，current state 必须只有
`next=["qualification_interrupt"]` 与唯一资格 interrupt；RESUME/final 的 thread 必须
为 `idle`，next/interrupt 必须为空且 decision 合法。thread 与 next 的安全投影进入
跨 API/Redis/full-stack restart exact continuity。由于 failed attempt1 的 project/volume
必须保留，successor 使用 fresh project=`finsight-dell-qualification-20260904-r8a2`、
fresh volume 与可绑定 loopback `18129`；只有修正回归、作者分离复核、clean commit/push
后才能创建新的 attempt2。它仍是 r8，不创建 R15/R16/A03，也不放开模型、DeepSeek、
live external、Evidence admission、S2 write、HITL 或报告。

修正后的直接 r8 测试=`11 passed in 2.41s`，13 文件相邻回归=
`215 passed in 21.74s`；compile、lock、Compose quiet config、JSONL parse 与 diff check
通过。作者分离只读复核确认原 P1 已按 Run/Thread/State 三层关闭，当前 successor diff
未发现新 P0/P1。Project OS 重跑=`81 passed / 1 failed in 22.79s`，唯一失败仍是既存
dynamic-writer sealed SHA drift，本轮不重签历史 authority，故 full repository green=false。
successor 仍须先形成 clean pushed commit，不能在 dirty tree 上启动 attempt2。

### 12.10 r8 fresh attempt2：本地全链完成，LangSmith 查询契约误用而失败

Run/Thread/State 修正以 clean pushed commit=
`587853944cf6610d9f38edcf3c65be2dd7b8aa1c` 冻结后，fresh attempt2=
`20260904T052346+0800-zero-model-r8` 在独立 project=
`finsight-dell-qualification-20260904-r8a2`、loopback `18129` 与 fresh volume 上执行。
attempt manifest file SHA-256=
`e5e54964e574c3c156c3599200062d4f92c7385057d5aec3a5b9759eefa42bb7`，
failure receipt SHA-256=
`04986641acb8a922710fea39ffb100d0051cad2bbae6def2fba85c9447c9801d`。
该 attempt 必须保留为 immutable failed；`cleanup_performed=false`、
`prior_attempts_modified=false`、`model_or_paid_call_authorized=false`，旧 project、容器和
volume 没有复用或删除。

attempt2 不是“什么都没跑”。receipt 中 `start`、`api_readback`、
`redis_readback`、`full_stack_readback`、`resume` 与 `final` 六个 phase 均返回 0；实际
完成三容器 healthy、真实 Q1 zero-model Evidence/Finance MCP、native interrupt、API
restart、Redis process restart、同 project stop/start、resume 和 final exact replay。
关键耗时为 build/up=`96.062s`、START=`12.594s`、API readback=`2.672s`、Redis
readback=`2.719s`、full-stack readback=`2.344s`、RESUME=`9.625s`、final=
`2.656s`。但 host 尚未越过最后 LangSmith phase 和最终 cross-phase/receipt 断言，因此
这些只能写成已观察到的 phase-local 成功，不能把 attempt2 或完整 r8 写成 PASS。

唯一失败为 `r8_langsmith_query_failed`，LangSmith phase=`62.719s`。同一个 API 容器的
只读诊断证明 DNS 可解析 `api.smith.langchain.com`，Agent Server 日志已记录 metadata
上传成功；`Client.list_runs(limit=1)`、精确 root `limit=100` 均成功，而 `limit=101`
和 `limit=500` 稳定返回 HTTP 400。Docker daemon 同时仍配置
`DockerHTTPProxy/DockerHTTPSProxy=http.docker.internal:3128`，但 build、Git push、
Agent Server、metadata upload 和合法 LangSmith query 都已通过。因此当前失败与梯子/
代理无因果关系，最早责任层是项目 harness 把 `500` 误作可接受的 `/runs/query` limit，
并把同一确定性 400 按 polling 延迟重复执行。

固定 `langsmith==0.12.1` 的 public `Client.list_runs` 会把非空 limit 同时传给后端并作为
整个 iterator 的截断值；简单改成 `100` 仍可能静默漏掉第 101 个 span。successor 因而
不另造查询框架：省略 API limit，继续使用 pinned public cursor pagination；host 只消费
`maximum+1` 个对象作为上界哨兵，root 最多承认 2 条、单 trace 最多承认 100 spans，
第 3/101 条分别 typed overflow。确定性 LangSmith 错误立即失败；SDK 暴露的 connection、
408、429 和 5xx 类才允许现有有界重试。另增加 trace ID、span ID 唯一性、唯一 root 与
parent closure 校验。

同一现场无 limit 查询得到 START=`5` spans、RESUME=`3` spans。START 的唯一非空 error
位于非 root `qualification_interrupt` chain span；其首行/末行与唯一 fully-qualified
marker 精确对应 `langgraph.errors.GraphInterrupt`。固定 LangGraph 源码明确首次
`interrupt()` 通过该异常保存 checkpoint，且 `GraphInterrupts are not considered
failures`；START root、其余 children、RESUME root/children 均无 error。因此原“所有
span error-free”断言同样是 harness false negative。修正只允许 START trace 中恰好这一
个精确控制流 error，其他任何 error 继续拒绝，原 traceback 不落盘。

现场 GraphInterrupt traceback 不含 credential、PostgreSQL/Redis URI、D/Z host path 或
数据挂载路径，但会按 Python 正常 traceback 暴露容器源码路径
`/deps/FIN_Insight_Agent`。在已采用 LangSmith 的本地非商用观测范围内，把“不得出现任何
容器源码路径”设为 privacy PASS 会让 native interrupt 天然不可验收，且 LangSmith 的
input/output hiding 不承诺隐藏 traceback code path。故 claim 收窄为：本次 trace 的
input/output hiding 已观察、credential 与数据 locator scan 通过、预期 GraphInterrupt
count=`1`、unexpected error=`0`；不得写成全部 payload/error/metadata 隐藏或完整 privacy
qualification。`Client.list_runs` 的 2027-01-31 removal 是后续 SDK migration debt，不在
本次失败上扩成 runtime 重写。

successor 继续属于同一 R8，使用 fresh project=
`finsight-dell-qualification-20260904-r8a3`、fresh volume 与 loopback `18130`；必须在
回归、作者分离复核、clean commit/push 后才能创建 attempt3。attempt1/attempt2 均不得
修改或清理；R7 仍是 current accepted baseline，模型、DeepSeek、live external、付费、
Evidence admission、S2 write、完整 multi-agent、HITL 和报告仍未授权。

本轮 Project OS 回归=`81 passed / 1 failed in 28.60s`；唯一失败仍是未由本轮修改的
`src/sec_agent/project_os_preflight.py` 与历史
`current_dynamic_writer_submission_successor` sealed SHA 不一致。本轮不重签该历史
authority，因此 full repository green=false，且该既存失败不归因于 r8 或代理。
LangSmith 修正的直接测试=`19 passed in 2.37s`，13 文件相邻回归=
`223 passed in 27.11s`；compile、`uv lock --check`、Compose quiet config、两份 JSONL
逐行解析、added-line secret-shape scan 与 `git diff --check` 均通过。
作者分离只读终审结论=`P0=0 / P1=0`；另以禁用 pytest cache/pyc 的直接 R8＋部署
组合复核 `34 passed in 2.98s`。P2 仅保留 pinned `list_runs` 的 removal debt、100-span
有意 fail-closed ceiling、限定模式而非 blanket privacy，以及未来若声称字段级稳定应扩大
stable signature；均不阻断本次 clean pre-live commit，也不构成 r8 PASS。
