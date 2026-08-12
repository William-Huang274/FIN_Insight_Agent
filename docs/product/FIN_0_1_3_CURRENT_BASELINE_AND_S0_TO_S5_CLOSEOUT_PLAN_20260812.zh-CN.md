# FIN 0.1.3 当前基线与 S0–S5 收口计划

日期：2026-08-12
状态：`repository_baseline_complete / S1C_retrieval_stack_and_database_lane_governance_frozen / query_and_object_successor_open / product_iteration_not_closed`
## 1. 这份文件拥有哪项真值

本文件是 FIN 0.1.3 唯一当前执行计划。它取代两份已经迁入版本归档的旧计划；旧文件只保留决策和失败历史，不再拥有当前进度或下一步权限。

FIN 0.1.3 的版本目标不变：形成 FIN 0.1 Internal Alpha 的可审计纵向研究闭环。当前仓库重定基只是为后续产品工作建立一条可读、可测、可维护的主线，不等于版本产品收口。

## 2. 当前真正可用的产品

- `/workspace` 展示 DELL、MU、NVDA 三个身份和摘要均绑定的 reviewed Evidence Pack。
- `/operations` 独立展示当前运行配置、来源包、准入数据构建和已保存运行；历史作业明确标记为仅供审计。
- 无数据挂载时仍可查看案例目录，但详情入口禁用且 `/api/readiness` 返回 typed HTTP 503；不得假装数据就绪。
- 挂载 reviewed pack 后可查看 Evidence、拒绝理由、来源边界和 residual gap。
- 当前三案只有 SEC 来源，结构化数值项为 0；因此不能声称多源研究、NumericFact、动态 Agentic Research 或完整报告已经完成。

## 3. S0–S5 责任与当前状态

| 阶段 | 只拥有的责任 | 当前事实 | 通过条件 |
| --- | --- | --- | --- |
| S0 | 产品/技术合同、身份、权限、版本、仓库与运行时基线 | G01–G12 已通过并合并远端 main | 单主干、单消费者、archive 隔离、secret/CI/container/clean-main 全绿 |
| S1 | 类型化 EvidenceRequest、内外源发现、解析、chunk/object、SQL/lexical/semantic/graph 路由、rerank、Evidence Role、来源覆盖 | 当前 Pack 只来自 SEC；请求级 facet 已进入 Runtime，现成 Cross-Encoder 和规则 Evidence Role 已完成 shadow 但均未晋升；typed exact fact lane 已列为必选但当前公司财务事实 mart 不存在 | 三案及独立留出案例的 request-to-plan、required-slot target-in-pool、日期/实体/关系、route contribution 和 Evidence Role 正确；数值请求可靠路由到 S2 exact lookup，外源只补真实 residual gap |
| S2 | 公司财务事实 mart、Evidence/NumericFact 编译、PIT、单位/期间、引用和冲突 | reviewed Evidence 可读，但三案 structured numeric=0；当前活动 SQLite/DuckDB 分别只拥有运维、行情或行业数据，不是公司财务事实库 | 数值事实从权威对象确定性入库和查询，跨案/错期/错单位 fail closed，typed exact lookup 返回 NumericFact 或可信 gap，S1 新证据依赖回归通过 |
| S3 | 动态规划、工具使用、重裁决、研究综合、Workpaper/Report | 当前无活动动态 planner、模型 research chain 或完整报告产品 | 三案真实动态研究通过 L1、八维绝对质量、paired gain 与 qualified-human 内容验收 |
| S4 | 用户任务、Evidence/Gap/Workpaper/Review/Repair 产品闭环 | 只有只读 Evidence Workspace 和独立 Operations | 当前 S3 candidate 被真实 UI 消费；review/repair/lineage 可完成且不依赖旧产品面 |
| S5 | 发布、回滚、运行、成本、安全和 Owner acceptance | 未开始；本次仓库 merge 不是 S5 | RG1–RG5、clean deploy、回滚和 Owner 签署全部成立 |

失败必须回到最早责任阶段；不能在 S4 页面、Writer 或 renderer 用补丁掩盖 S1/S2/S3 缺陷。一次失败只产生新 attempt，不产生新版本。

## 4. 当前重定基完成后的执行顺序

1. **S0 仓库基线（已完成）**：G01–G12 已通过，远端 `main` 已从第二份 clean-main 工作树完成复证。
2. **S1-A 已完成——类型化本地检索纵切**：已建立 provider-neutral 金融内核、9 slot / 17 facet 查询、身份/截至日/source-role 约束和真实 Workbench 候选消费者；三案同核心迁移通过。它只证明工程纵切，不代表 S1 产品通过。当前历史候选库对 DELL/MU/NVDA 的 reviewed target 对照分别只命中 4/0/6，三案 PIT 行情角色均缺失。
3. **S1-B 已完成——current source/object 重建**：当前 store 为 28 parent / 1,805 child，含 NVDA 当前 10-Q、DELL/MU 当前 SEC、TSM 6-K 与三案 PIT market role；表边界、child 大小、身份和截至日硬门通过。Dell/Micron 官方法说 PDF transport、TSM 先进封装和新鲜估值仍为 typed gap，不阻断对象层工程关闭。
4. **S1-C successor 与请求入口已完成**：Owner 四条 successor 已另存应用，18/18 映射；缓存复跑 BM25=`17/18`、BGE-M3=`14/18`、RRF／旧规则=`16/18`。`EvidenceRequest → 按需 facet → QueryFacetPlan` 已进入当前 Runtime，固定 pack 继续作为部件回归。自然语言理解仍归 S3，交互仍归 S4。
5. **S1-C Cross-Encoder／Evidence Role shadow 已完成**：现成 BGE reranker 与 BM25 同为 `17/18`，MRR 有增益但逐题仍有严重反转，未晋升。规则角色门把三案显式错角色减少，却将 Recall 压到 `13/18`；留出正例约七成 abstain，禁止上线。第一版错误的 cross-slot 负例合同保留为失败证据，校正后留出 Cross-Encoder top3=`17/17`，角色门 top1 仍退化。
6. **S1-C 对象级角色数据合同已完成开发复核**：24 个源绑定 object／35 个 query relation 已明确 claim、metric table、parent context、多标签 role、fact state、directness 和 positive／hard negative／unjudged；标签与模型可见 surface 分离，三案例开发批次没有读取 ORCL／ASML／ANET 留出。固定模型复核为 pairwise `0.50`、top1 `0.60`，旧规则角色 F1=`0.507936`，故没有微调、训练或 Runtime 晋升。
7. **S1-C0 检索栈、数据库通道和 test-precut 治理（已完成）**：已冻结 SQL/typed exact lookup、BM25、BGE-M3 dense/learned-sparse/multi-vector、Qwen Embedding、typed graph、BGE/Qwen Reranker 和独立 Evidence Role 的分层边界；HPQ／AVGO／INTC issuer-time test-precut 已在新模型结果出现前绑定，ORCL／ASML／ANET 降为已观察 validation。当前没有模型、训练或 Runtime 晋升权限。
8. **当前下一门——S1-C1 query family 与对象编译器 successor**：拆开 reported results、guidance、counterevidence、cash conversion、regulatory exposure、supply execution 和 customer read-through；把财务表投影成表头、期间、单位、metric row 和父章节，并把 source segment 编译成 source-bound claim/table/context。同时把 exact metric/period/unit/PIT intent 编译到 typed fact request；混合请求必须拆成同 cell 的 fact/evidence sibling requests。
9. **S1-C2/C3 多检索器与 Cross-Encoder 有界对照**：同语料、同硬过滤、同预算比较 BM25、BGE-M3 三模式和 Qwen Embedding；随后只在同一候选并集比较 BGE/Qwen Reranker。评测必须报告真实业务错因、独有有效候选、延迟和显存，不能只报 Recall/MRR。
10. **S1-C4 Evidence Role＋abstain 与微调处置**：独立判断候选能证明什么；模型分数不授予 Evidence 或数值权威。只有查询、对象、现成模型对照后仍存在稳定残差，并达到数据与独立留出门，才重新讨论微调。
11. **S1-D residual-gap 补源（尚未授权执行）**：S1-C successor 通过后，只处理已证明的真实缺口；当前最明确的是 TSMC CoWoS／先进封装产能、良率和分配，随后才是 Dell/Micron PDF transport 与 PIT 估值。不能用 broad search 掩盖 query、对象、数据库或 ranking 错误。
12. **DELL S1/S2/S3 纵切**：先用 provisional winner＋shadow challenger；S3 产生真实 EvidenceRequest，S1 执行文本/图检索并路由 fact request，S2 从当前公司财务事实 mart 返回 NumericFact，S3 再综合和暴露产品级残差。该纵切决定 S1 product gate，而不是离线排名数字。
13. **S2 三案扩展与依赖回归**：把 S1 的新 Evidence 编译成有权威、期间、单位、公式和 lineage 的 Evidence/NumericFact；不重跑无关控制面。
14. **S3 三案动态 Agentic Research**：把用户问题编译成 `Research Objective / DecisionSurface / EvidenceRequest`，并由同一 Runtime 完成规划、内源检索、缺口判断、外源补证、重裁决和报告；模型负责研究判断，本地控制面负责事实、权限和确定性渲染。
15. **S4 产品闭环**：提供真实任务输入、澄清、计划查看和人工修改界面，并把通过验收的研究结果接入当前 Workbench；补齐 human review、repair 和 artifact lineage。
16. **S5 release**：扩大案例与对抗测试，执行发布、回滚、成本和 Owner acceptance。

## 5. 防止再次膨胀的工程规则

1. 新能力必须先说明归属 S 阶段、真实用户消费者和替换对象；没有消费者的 runner/config/test 不进入活动树。
2. 同一合同只有一个编译源；Prompt、validator、fake、live、renderer 和 UI 不能各自维护一份结构。
3. 单次 run/attempt 的实现、admission、capture 和 proof 默认进入运行数据或版本归档，不能成为永久模块名。
4. Workbench 是常驻产品与验收入口；不得用一次性脚本代替最终用户链。
5. 测试分为确定性工程门、自然模型 canary、产品内容验收；不得为每个字段重复 live。
6. 新模型通过统一 profile/canary 获得不同自主权；provider 特殊拐杖不能进入核心金融合同。
7. 每个阶段结束时同步 PRD、当前计划、技术图、Project OS 和机器 manifest；当前投影保持短小，完整历史归档。
8. SQL/typed exact lookup、文本检索和关系图是并列通道：embedding 或 reranker 可以定位数值披露，但不能替代 S2 的事实 mart、期间/单位/PIT 和 NumericFact 权威。

## 6. 明确不偷换的边界

- 仓库基线通过，只说明后续开发不再带着多主线和 attempt 债务；不说明研究质量已经通过。
- 三份 reviewed Pack 通过，只说明身份、摘要、来源和 gap 可以审阅；不说明 Evidence 完整或结论可靠。
- 数据构建脚本存在，只说明有受维护入口；不说明网络、授权、索引或数据已经就绪。
- S1/S2/S3 的历史 proof 仍可用于诊断，但只有当前 Runtime、当前数据和当前产品消费者的复证才能成为新能力证据。
- 固定 case 的 9 Slot／17 facet 查询包只证明下游检索部件；在 S3 自然语言规划与 S4 用户入口接通前，不得称为真实用户查询链。
