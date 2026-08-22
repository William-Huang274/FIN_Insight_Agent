# 056｜DELL 命题覆盖、内外源执行与动态单单元门

日期：2026-08-22
阶段：FIN 0.1.3 / S1（S2 仅做受影响重编译；S3 尚未获模型执行权限）

## 决策目标

证明 DELL 的价格／配置、销量、PVM、客户需求、供应链、价值池和反方七类命题，能从同一产品入口经历本地 SQL、对象、原文、BM25、Qwen CUDA dense、可用图路线、完整外源阶梯、CandidateDecision、Evidence Gate 和 S2 重编译。只有达到当前任务的 EvidencePackReadiness，才允许一个动态研究单元获得模型调用权限。

## 为什么现在执行

最近的 Actionable Uncertainty 与四来源 successor 只把缺口变成可追踪 Action，并证明了四个 exact source 的 capture／解析／准入；它们没有执行全部 Action，也没有证明产品能主动覆盖七类研究命题。现有单请求 Workbench 接口仍只查询不可变 snapshot 与 S2，而 BM25＋Qwen 当前 Runtime 只挂在 controlled-plan 入口。这会制造“当前对象库已有候选、单请求却看不到”的假阴性，因此最早实现先统一直接 EvidenceRequest 产品入口。

## 假设与可证伪条件

1. 当前对象库和 SQL 能覆盖一部分命题，但不会覆盖价格／销量／价值池等全部研究面。
2. BM25＋Qwen CUDA 能增加候选，但排序不能自动授予 Evidence 权限。
3. typed relationship graph 当前未配置；GraphContextPack 只能帮助定位，不能冒充 S1 图查询成功。
4. 外源必须从官方一路扩到行业、产品／采购／渠道／客户部署、可信媒体／公开 analyst 与反方；“只抓四个官方页面”不算完整阶梯。
5. 若公开材料只支持区间或线索，S2 应生成可复算 estimate／scenario；只有执行完可用路线仍无法获得关键权威时，才允许 typed gap。

## 执行边界

- 内源阶段：0 模型、0 网络、0 付费；向量计算必须 CUDA／FP16 fail closed。
- 外源阶段：capture-first；发现服务只定位原始来源，不能直接成为事实。任何付费或有配额工具先记录目的、请求规模、停止条件和预算依据。
- Candidate 不是 Evidence；rank、Embedding、Reranker、模型判断均不能授予事实或数字权限。
- 失败保留原 Attempt，修最早责任层后用新 Attempt；不得因一次失败新建产品版本。
- 当前不授权多 Agent、Writer、MU／NVDA 或留出案例执行。

## 交付物

1. 七类命题和原子 EvidenceRequest 的机器可读执行程序。
2. 同一产品入口的 SQL／snapshot／BM25／Qwen／graph route receipts 与 CoverageState。
3. 完整外源阶梯的 capture、候选、失败归责和 GapEligibilityReceipt。
4. CandidateDecision、Evidence Gate、current Pack successor 与受影响 S2 重编译。
5. EvidencePackReadiness 决策；通过后才签发一个 DELL 动态单单元。

## 停止条件

- 本地对象、SQL、parser、召回、排序或 admission 故障未归责：停在 S1/S2 修最早层，不能开始模型测试。
- 需要购买数据、改变模型主路线、改变研究范围或使用受限商业材料：返回 Owner 决策。
- 外源发现能定位但传输／解析失败：保留 capture 与 typed failure，修来源适配；不得记为公开 gap。
- 任务相对 Pack 未达到 readiness：不签发动态单元。

## 当前状态

执行程序和 12 条原子 EvidenceRequest 已冻结。直接 EvidenceRequest current-runtime 产品入口已实现：同一个公开产品方法顺序执行 snapshot／原文对象视图、S2 SQL、BM25、Qwen CUDA／FP16、route truth 与 candidate ceiling；返回的排序结果仍只具有 Candidate 权限。批量入口的定向合同、API、重复 request ID、旧资源漂移和 S3 历史回放隔离测试均已通过。

首次探索性执行确认 12 条请求均可越过合同编译并实际加载 CUDA dense，但该次结果只输出到终端、没有不可变物化，不能作为正式证明。已经新增正式物化器；它要求 clean worktree，绑定 commit、R30 Runtime registry、程序 digest、完整私有 projection 与公开七命题汇总，防止再次用终端数字代替可追溯结果。

## 本轮提前发现并修正的阶段漂移

新增 `downstream_demand_context` 时，最初把 current S3 planning policy 也从 v1.1 晋升到 v1.2，导致旧 fixed-Pack 的 research-input digest 变化，60 个历史 S3 测试失去原资格。该做法已被否决：S1 显式 EvidenceRequest 可以先使用新增 facet，但不代表 S3 Planner 已获权自动提出它。

当前兼容方式为：

- current S1 kernel／route 使用 v1.3；
- current S3 planner 继续使用 v1.1，只能选择其已经批准的 facet 子集；
- v1.2 planner 仍作为未来显式 S3 successor，不静默晋升；
- 历史 fixed-Pack canary 使用其原 snapshot／kernel／route／planner，不能从 mutable `current` 别名重编旧输入；
- 新 planner 不得包含未知 facet，v1.2 仍必须覆盖完整 current route surface。

该处置保留了 S1 的新业务检索面，也保护了历史 S3 证据 lineage；不是为了让旧测试变绿而重标结果。

## 仍未完成

- clean commit 后的正式 DELL AI-free 内源 attempt；
- 逐命题 CandidateDecision 与人工／规则 Evidence review；
- 完整外源阶梯，而非仅官方四来源；
- current Evidence Pack successor 和受影响 S2 派生／区间／情景；
- EvidencePackReadiness 与动态单单元 authority；
- 任意自然模型、网络、付费调用、Writer 或产品发布。
