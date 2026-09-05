# S3/189 Dell 多 Agent 审查与责任回派

状态：IMPLEMENTING；起点 863f7ab4（clean/pushed），FIN 0.1.3 / 同一 S3。

## Owner 方向与最小真实增量

2026-09-05 Owner 明确授权：单 Agent 跑通后继续多 Agent、完整产品，普通实现/网络问题自行修复后继续，DeepSeek 额度充足。安全/金融事实标准不放松，不无限重试或提权。

本包直接落实现有详设 Wave 3 / §§6、10、11：将 R11 原底稿和实际观察作为不可变输入，两个独立、可自主查询的 Counter / Verifier 子 Agent 并行审查；finding 回到原 Specialist 的新 revision，自主补查/修订，再复审。此包不是 R12 单 Agent 重跑，也不是 Q1–Q9 全产品 PASS。

## 实施边界（先冻结，允许据真实证据修正）

- 复用同一个 LangGraph Specialist tool loop、ToolNode、MCP、SDK、Agent Server/PostgreSQL/Redis/LangSmith。外层使用标准 StateGraph/Send；不添加依赖、scheduler、queue、rule engine 或第二种 runtime。
- 审查角色以专门 SubmitReviewAction 返回 finding；确定性层只核对 JSON、目标 revision、原文 anchor、已观察引用与责任身份。语义/完整性/因果判断交给模型，不将本作者 R11 中文复核注入模型。
- 审查可读取原 Agent 的完整已观察 source context、底稿/claim 和简短依据；不能读私有 provider reasoning。各子 Agent 的 SDK 对话隔离，同一子调用保留自身原 reasoning/tool messages。跨 Agent 移交显式 artifact，不冒充 durable conversation resume。
- 原失败及 R11 文件不修改；新修订单独保存，引用权限仍是 Reviewed / S2 / 已读 PASSAGE；不新增网络入口、Evidence admission、S2 写或发布权限。
- 首个可执行切片只审查 Q1；最多一次责任修订和一次复审，两 reviewer 每次最多 6 模型轮/8 数据动作，原作者修订最多 12 轮/16 动作。这是异常停止上限，不要求用满。每节点记录实测依据的 TokenBudgetBasis；失败不能被吞掉成为 no-material finding。
- 真实执行仍走现有一次启动 runner 和服务器身份绑定。允许在现有 authority 增加显式 workflow/seed/node budget 字段，不新建另一套执行协议。输入 seed 只读绑定文件 SHA；所有输出在新 attempt。
- 定向检查：真实 R11 移交不改原件、不同 reviewer 上下文隔离、审查权限/引用/target 绑定、finding→责任修订→复审、任一失败不能 aggregate PASS、旧单 Agent 回归。通过后实际 DeepSeek 调用并读原稿，不以测试数代替内容验收。

## 后续方向

本闭环有真实结果后继续既定动态 Lead / 并行专业 Agent / Q1–Q9 覆盖与报告，再到 Workbench/HITL/运行后交互。避免回到单个语义问题无限修补；仅将经源上下文证明的根因回归，不能把 reviewer 自评等同最终人工产品验收。

## 成熟参考

- https://docs.langchain.com/oss/python/langgraph/workflows-agents （orchestrator-worker / evaluator-optimizer）
- https://docs.langchain.com/oss/python/langgraph/use-subgraphs （子图隔离与父级持久化）
- https://docs.langchain.com/oss/python/langchain/tools （ToolNode）

## 代码候选验证

实际接入 `dell_workpaper_review_graph.py`（标准 Send/StateGraph evaluator-optimizer）、既有 Specialist graph/composition/DeepSeek adapter 的 review terminal 和 artifact handoff、既有 Agent Server 入口与一次启动 runner 的显式 review workflow。原单 Agent 五工具不变；reviewer 五工具仅以 SubmitReviewAction 替换 SubmitWorkpaperAction。没有新依赖或另一套 runner。源 seed 单文件只读挂载，逐 reviewer/repair 节点有独立 TokenBudgetBasis 和 SDK 会话；原 provider reasoning 仅续传本角色且保留在私有审计。

最终相关 11 文件测试：`215 passed in 16.28s`。包含真实 R11 原件不变/完整 observations 移交、实际 reviewer MCP catalog 返回、实际 SDK 模拟 transport 的 review 工具 schema、同角色 reasoning 续传/跨角色隔离、finding 精确目标/引用/anchor、并行 barrier、责任作者修订和二次复审，以及失败不得变 PASS。纯离线测试发现的 JSON tuple 序列化、LangGraph reducer 初始空列表、审查不应增加作者 revision 的边界均在付费前修正。Client 测试改为比较 Pydantic 显式默认值归一化，未更改 client 行为；legacy 单动作五选一 schema 保持。

2026-09-05 22:13 本地 Docker R11 三服务 healthy；磁盘 C/D/Z free=3.46/25.14/14.16 GiB。本包未删文件/改代理。当前未执行新模型；R11 的 runtime bounded PASS / 内容未 PASS 保持。此为 Q1 有界协作 qualification，不是昂贵完整 Q1–Q9 full-chain；后者仍须其专用全链 preflight/节点授权和产品门，不能用本包替代。
