# Dell Q1：3+1 数据交付小修正与 thinking 对照

日期：2026-09-05。起点 `632afb0d4eb0cc02cf206c9776817452718b47ab`，同一 `codex/fin013-dell-s1-s2-product-bridge`。本记录不创建新产品版本，不重跑 R3。

## Owner 最新授权与边界

Owner 要求先修 3+1，并允许在沙盒内按需读取内外源；引用必须挂到实际来源片段，财务数字优先 S2；保留模型推理以审查上下文使用；随后明确允许最多 1–2 次 thinking disabled/enabled 真实 Agent 测试。此次使用批准的冻结案例语料，不打开任意文件/URL/shell、不提权、不新增实时 web provider、不写 S2、不 admission Reviewed Evidence。原失败证据不改。

## 已实现

1. Reviewed：已批准 eligibility 在 BM25/top-k 前过滤；小集合允许有词项命中的零/负 IDF 得分，避免只剩 1–2 篇时错误排空。
2. 新 opt-in `source_read_enabled` Q1 profile：不再把研究分支相关性用作完整案例文档阅读 ACL。原 Reviewed 资格不改；Q1 基础来源条件改为跨动作的 F2 发行人叙述 + S2 财务数值，仍须实际引用。这只是来源结构验收，不是研究质量 PASS。
3. 财务能力披露 `observed_period_roles`，错用粒度时返回现有合法期间角色及重查建议，绝不自动补值/改口径。
4. 现有 MCP 增加 `read_source_document`，Specialist 增加 `request_source`。在已有 Document/Section/leaf tree 上提供 catalog/outline/search/read，完整块读取、明确 continuation、引用原文与 SHA/URL/section locator。搜索预览不可引用；HTML 不伪造 PDF 页码；解析器 PDF 页码与印刷页码仍分开。
5. `source_bound_passage` 只表示允许引用被实际读取的来源片段，不是 Reviewed 或 NumericFact。claim 需精确 quote 和 authority_note；允许自由正文，reasoning_summary 解释推理与上下文，语义正确性由后续审查判断。
6. 沿用 ChatDeepSeek 的 SDK transport，新增 opt-in 原生 assistant/tool message history；返回的 reasoning 原样传回。当前 pinned SDK 能接收 reasoning 但发送时漏字段，修正仅为一个消息投影方法，MockTransport 已查真实 wire。
7. thinking profile 使用 tool_choice=auto，并明确要求每步通过单一 action tool 返回；无 retry/fallback。私有 audit 保存实际输入/响应/reasoning，公开审计仍只有动作、用量与 digest；LangSmith 仍 hide input/output。
8. paid overlay 追加 `cap_drop: ALL` 和 `no-new-privileges`；模型无 shell/代码执行接口，只有只读案例数据和 typed SQL 工具。未宣称任意代码执行沙盒或生产安全认证。

## 验证

- 15 个相关测试文件合并：**213 passed in 25.32s**。compile 与 diff check 通过；不是全仓 PASS。
- 包含真实本地 MCP 搜索→原文读取→错误 SQL 粒度提示→instant 重查→来源绑定提交；假引文拒绝、原始路径/URL/跨文档节点拒绝、HTML 页码拒绝、无静默截断。
- R3 原始 4 条查询离线重放：原先漏掉的已存 GUIDANCE 现在进入结果；R3 原 Notebook 仍能校验读取，原 run 不重跑。
- SDK MockTransport 证明两轮真实请求序列保持 reasoning_content，第二轮为合法 tool message，公开审计不带私有 reasoning。此测试不是 paid proof。
- S2/Reviewed/corpus 不写。无新 parser、reranker、模型权重、通用 runtime/permission 引擎。
- Docker 29.5.2 可达；C/D/Z 空余约 4.47/25.20/20.21 GiB。旧 R3 thread 为 idle、R2 为 error，已停止这两组共六个已结束测试容器以降低占用；没有删除容器、卷或 artifact。Windows 可用内存约 2–3 GiB，运行只允许串行。

## 对照的预注册口径

- 相同代码、任务、as-of=2026-09-02、数据、工具、来源约束；只比较 thinking disabled/enabled（enabled 使用 provider 默认 high）。不是随机化 benchmark，n=1/组不作模型优劣统计结论。
- 每次最多 12 模型轮、11 工具动作；每轮 240,000 输入字符、16,000 输出 token、240 秒；是异常停止上限，不要求耗满。依据 R3 的 6 轮/75,889 tokens/43.113 s，为原文阅读、SQL 分开查与 reasoning 留空间；两组一致。
- 保留消息上下文是两组共同改进，不能把 R3→新运行的全部变化归因于 thinking。
- 首要观察：是否有有内容的底稿、来源/数字使用是否正确、能否纠错/读原文、是否保留不确定性；同时记录 tokens、耗时、LangSmith 估费（非账单）和失败。
- 宿主解析/数据失败与模型责任分开。模型合理使用错误的已解析资料可以记 Agent 行为通过，但错误金融结论不得记交付 PASS。
- 首次出现基础设施/权限/格式阻断则保留并停止，不消耗第二次做无依据的重试。新 authority 逐次创建且不可复用。

当前：实现及离线检查完成，真实对照尚未启动。RC-S3-113 的 paid behavior / financial-quality 验证仍待完成；多 Agent、Verifier、前端、HITL、恢复与 RC-S3-107 不在本次完成声明内。

## R4 实际失败与有依据的测试调整（覆盖上段当前性）

- implementation `1d685b0d64ef89d6923756dd3e1577580526d3ac`，authority HEAD `be8c372b...`，execution `20260905-dell-q1-source-read-thinking-disabled-r4`。Docker 三服务 healthy，构建/启动 136.859 秒；无代理/凭据/数据库故障，容器实际 CapDrop=ALL、no-new-privileges=true。
- 1 次真实 DeepSeek disabled POST 返回成功、8,141 输入 + 463 输出 = **8,604 tokens**，模型 **7.953 秒**。模型提出了有效 Reviewed 检索参数，但以直接工具参数返回，没有再包 `{"action": <参数>}`。宿主因此 `model_structured_payload_invalid`，图停在 model_decide；**0 次实际数据工具动作、0 底稿**。这不是 RAG 或 Agent 研究能力失败，也不是通过。
- read-only 校验实际返回参数：`RequestEvidenceAction` 原样通过；外加对象层后原 `SpecialistActionPayload` 也通过，无任何内部参数修理。最早可修层是 FIN 对 provider 强加的冗余嵌套封装，不应新增语义宽松 validator。
- 原失败目录在 Z 盘 `q1_specialist_paid_shadow/attempts/20260905-dell-q1-source-read-thinking-disabled-r4`；失败 receipt、公开用量、私有完整模型响应保留。另新增只读状态捕获 `diagnostic-state-after-failure.private.json`，不 resume 原 run。run/root `01a070ca-62ee-7040-96a1-b7c0e6ba0b25`、thread `e30efa08-61ee-5e58-b918-fe7b62826536`。LangSmith 1 个成功 LLM span、root error，inputs/outputs hidden；估费 **USD 0.003944145**，不是账单。
- thinking disabled 本次未返回 reasoning_content；私有文件保留其实际消息而不伪造 reasoning。

### 剩余一次额度的调整，已在执行前向 Owner 明确说明

原“同代码两组 thinking 对照”在 R4 格式失败处停止。根据上述精确反例，移除 provider 外层 union 包装，直接使用现有 SDK `bind_tools` 暴露五个独立 object-root 工具；内部图的原五动作 union、参数/权限/来源校验不变，无 JSON 修复猜测、无新 parser/runtime。

修正后 4 个相关测试文件 **68 passed in 12.90s**，包含真实 SDK 两轮 reasoning 连续性、五个 object-root tool schema、错误工具名/动作 tag/多调用拒绝及实际 MCP。不会因此称 R4 成功。

Owner 原先最多两次真实运行的额度剩 1 次，将用于 fresh R5 thinking enabled 功能验证，不自动重跑 R4、不 retry/resume/fallback、不追加第三次。因为工具 wire schema 改变，**R4/R5 不再是严格 thinking A/B，不比较因果优劣**。两次预算上限/任务/数据不变；enabled 仍默认 high。第二次若失败仍保留并停止，若有底稿必须人工核对来源上下文而非只看结构 PASS。

## R5 构建失败与 Owner 新增一次重试授权

R5=`20260905-dell-q1-source-read-thinking-enabled-r5` 在 Docker dependency build 阶段失败，未创建 Agent Server run、未调用 DeepSeek、未执行研究工具。固定 `playwright==1.62.0` wheel 从 files.pythonhosted.org 下载时 `tls handshake eof`；Compose build 166.125 秒后失败。原失败目录、receipt 和 BuildKit record `4cxzrgce5nfewc9c5xtzcrp97` 保留。构建工具 uv 的下载重试不是 Agent/model 重试。

随后同一 wheel URL 的宿主 `curl --noproxy '*'` HEAD 与显式 `http://127.0.0.1:6696` 代理 HEAD 均为 HTTP 200；Docker 使用 `http.docker.internal:3128`。这支持网络间歇故障的可能，但不能证明具体是用户代理导致，HEAD 也不证明容器长下载可靠。没有修改代理、证书或版本。

Owner 最新明确说“docker 这个问题应该就是因为梯子或者网络波动，你可以再试一下”。因此追加一次有依据的新启动 R6，取代上段“本轮不追加第三次”的上限：**代码/依赖/任务/数据/预算与 R5 相同**，仅 fresh identity/authority；R5 保持失败，不 resume/覆盖。先成功构建才发生 enabled 模型调用。若再次失败则停，不据此继续无界重试。此追加是 Owner 新授权，不是自动消耗原两次额度。

官方依据：[DeepSeek thinking 与工具续接](https://api-docs.deepseek.com/guides/thinking_mode/)、[MCP 工具与结构化响应](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)。两者均由现有 SDK 承载，FIN 仅实现研究来源语义及薄适配。
