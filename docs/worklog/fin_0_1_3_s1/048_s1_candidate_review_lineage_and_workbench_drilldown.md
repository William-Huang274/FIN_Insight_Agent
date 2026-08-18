# 048 S1 候选证据审阅 lineage 与 Workbench 对象下钻

日期：2026-08-19

状态：`safe_object_review_lineage_pass / controlled_Evidence_successor_open / qualified_human_and_S1_qualification_open`

## 这一步解决的不是“多展示一点调试信息”

上一轮产品只能说明某个研究问题卡在候选覆盖、Evidence 准入、S2 数值或 S3 范围，却不能回答最关键的业务问题：系统究竟找到了哪段官方资料、它谈的是谁、属于哪个期间、能证明什么、为什么还不能写进研报。

本轮把当前 CandidateDecision、v5 金融对象和 v2 来源记录按 digest 重新绑定，形成一个私有审阅包；Workbench 只在认证产品面投影受限字段。它不自动生成 Evidence，也不授予数字、公开信息 gap、S1 或发布权威。

## 产品面现在能看到什么

每个研究请求可展开对象级候选卡片，包含：

- 研究命题与该候选对应的 requirement；
- 本案公司与实际披露公司，避免把上游公司披露冒充本案自述；
- 官方来源类型、发布日期、报告期、章节和 URL；
- 最多 560 字的来源绑定摘录；
- Evidence Role、候选路线和排名轨迹；
- 当前 disposition、待审原因、问题分类与下一合法动作。

Workbench 不返回 compiled object ID、source record ID、私有文件路径、raw capture 或未受控全文。catalog、公开 readiness 结果、私有 full-result、review packet 和 Runtime Registry 均做 digest 校验；私有路径只能解析到 `FINSIGHT_WORKBENCH_PRIVATE_ROOT` 内，漂移、越界或缺失均 503 fail closed。

## 三案真实结果

| 案例 | 审阅条目 | 唯一对象 | 需要人工金融审阅 | 已有 Evidence 可复用 |
|---|---:|---:|---:|---:|
| DELL | 0 | 0 | 0 | 0 |
| MU | 34 | 22 | 34 | 0 |
| NVDA | 31 | 25 | 30 | 1 |

DELL 为 0 不是检索失败，而是其当前 8 个请求仍等待 S3 用自然 ResearchBlueprint 明确材料范围；在范围未定前系统拒绝把 fallback 候选伪装成正式审阅面。

MU 的对象级 lineage 证明两类重要资料已经存在于当前官方对象库：

1. Micron 披露 HBM4 已为 lead customer platform 进入 high-volume shipments，并向多个终端客户提供 qualification samples。这是履约／供给与客户需求信号，但不能自动等同为收入确认或全行业需求证明。
2. Micron 披露战略客户协议包含多年期具体数量约束，另有 take-or-pay 类安排。这是客户承诺强度证据，但仍要约束合同范围、取消条款、履约与收入确认边界。

它们此前并非“免费公开资料不存在”，也不是 DeepSeek 没有执行搜索；最早丢失点是精确对象、命题／slot 与 reviewed Evidence Pack 之间没有合法准入绑定。

NVDA 的候选面同样已能区分公司当期 Blackwell／Data Center 结果、供给与产能采购、客户资本／电力／数据中心建设节奏、出口管制和上游 HBM 供给等不同证据角色；旧期重复、通用风险、上下文不完整表格和错角色材料仍保持待审或拒绝，不能因语义相近自动晋升。

## 运行时与复证

- Runtime Registry：R25，26 个活动资源，2,548,793 bytes，canonical digest `c04f7f8d47be7c941e0d29cbbe4498a65dfa7561a3250f06b16fdc0d20713856`；
- current binding v1.2 result digest：`7a5fb837559cff61148e95b4255231fb8e06d26c30cba59abf0a4b2ce00a4c26`；
- Python 全仓：`759 passed`；
- TypeScript 与 Vite production build：通过；
- 真实挂载数据 Chromium：MU 候选下钻、DELL 无伪造候选和私有字段不泄漏均通过；
- active baseline：169 Python／8 frontend／26 Runtime／0 forbidden；
- secret scan：7,266 files／0 findings；
- 本轮网络、生成模型、付费 provider、新 embedding：0。

## 责任边界与下一步

RC-S1-042 的“产品没有安全对象级 review lineage”已关闭。新的最早内部责任层是 RC-S1-043：对已找出的 MU／NVDA 对象做命题级接受、拒绝、保留待审与精确 slot 绑定，生成受控 successor Evidence Pack，然后重物化三案 ProductReadiness。

下一步必须复用现有 reviewed Evidence Pack validator、capture-bound lineage 和 current-pack promotion seam，不允许手改 current Pack 或另造平行 builder。数值继续由 S2 NumericFact 提供；内部工程 adjudication 不能冒充 qualified-human、external blind、S1 qualification 或 release acceptance。
