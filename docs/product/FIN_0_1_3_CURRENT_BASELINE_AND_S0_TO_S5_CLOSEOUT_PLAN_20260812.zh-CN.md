# FIN 0.1.3 当前基线与 S0–S5 收口计划

日期：2026-08-12
状态：`repository_baseline_complete / S3_budget_contract_engineering_pass / S1C_saved_planner_input_audited / S1D_source_intake_engineering_pass / S1D_automatic_TUN_path_blocked / operator_upload_ready / S1_S2_S3_product_open / product_iteration_not_closed`
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
| S1 | 类型化 EvidenceRequest、内外源发现、解析、chunk/object、SQL/lexical/semantic/graph 路由、rerank、Evidence Role、来源覆盖 | 保存的自然 Planner atoms 已执行 8 个 request／128 个 Qwen＋BM25 候选并逐项归责；两个新 ranker 与 Evidence Role 均未晋升。共同 Source Intake 与操作员官方 PDF 上传已接入 Workbench；唯一 automatic R1 的 Dell/TSM 两条请求均在 HTTP status 前失败，Fake-IP 均经 `okz` TUN，仍为 0 PDF | 三案及独立留出案例的 request-to-plan、required-slot target-in-pool、日期/实体/关系、route contribution 和 Evidence Role 正确；数值请求可靠路由到 S2 exact lookup，外源只补真实 residual gap |
| S2 | 公司财务事实 mart、Evidence/NumericFact 编译、PIT、单位/期间、引用和冲突 | private mart 已从三案 SEC capture 建立，1,319 observations、24/24 精确事实查询及 mutation 通过；DELL 受控纵切为 7/7 typed request resolved、21 NumericFacts、0 gap/conflict | 数值事实从权威对象确定性入库和查询，跨案/错期/错单位 fail closed，typed exact lookup 返回 NumericFact 或可信 gap；自然 planner、研究消费和三案依赖回归证明产品价值 |
| S3 | 动态规划、工具使用、重裁决、研究综合、Workpaper/Report | provider-neutral Objective／planner atom／EvidenceRequest 合同和预算分层已接通；R1 保存 atoms 已进入 S1/S2，但没有合格 Evidence Pack，因此研究综合与报告尚未执行 | 三案真实动态研究通过 L1、八维绝对质量、paired gain 与 qualified-human 内容验收 |
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
8. **S1-C1 query family、对象编译器与 typed fact route（已完成工程门）**：17 facet 已且仅映射到 11 类问题；混合请求拆成同 cell 的 narrative／fact sibling。1,805 个 current child 编译出 20,340 个去重 claim／metric-row／context 候选，2,425 个重叠切块重复已合并并保留 lineage；高管年龄表等 228 张非金融数值表已拒绝。标签回放进一步修复空表吞掉 TSMC claim、Micron 重复 Revenue 行缺少业务单元上下文，以及 8-K filing date／issuer reporting period 混用。24 类指标可路由到 typed fact request；mart 不存在时返回 S2 typed gap，存在时交给 S2 executor，始终不把表格行冒充 NumericFact。
9. **S1-C2 多检索器有界对照（已完成 shadow，无产品晋升）**：同 20,340 对象上，BM25、BGE-M3 三模式与 Qwen Embedding 已完成有界对照；Qwen 模型资产后续通过合格本地路线取得。Runtime Query Atom 中 Qwen 前十正例为 8/15、BM25 为 5/15，二者在真实 DELL results／cash 请求上表现互补，因此 provisional 产品方向修订为 `Qwen semantic + BM25 lexical candidate union`，不是 winner-take-all，也不是当前 endpoint 已晋升。
10. **S1-C3/C4 Runtime Query Atom 模型 shadow（已完成，无 Runtime 晋升）**：18 个原子问题上，BM25／BGE／Qwen Embedding 前十正例分别为 `5/15`、`0/15`、`8/15`，自然共享池为 `10/15`，未过 0.80 门。Qwen Reranker 受控 pairwise=`12/16`，但自然 top10=`7/15`，没有超过 Qwen Embedding；BGE Reranker=`8/16`。因此冻结 `Qwen Embedding provisional + BM25 fallback`，Qwen Reranker 仅 shadow。Evidence Role 正例 compatible=`10/16`、负例拒绝/abstain=`15/18`、F1=`0.5818`，禁止上线和微调。残缺片段及错误关系 qrel 保留为 S1 复核问题，不能通过改标签追分。
11. **S1-C 保存 Planner 输入审计完成、S1-D Source Intake 工程通过但内容仍阻断**：10 条保存 atoms 稳定选择 8、延期 2；8 个真实 request 返回 128 个候选、19 resolved／9 typed gap／45 NumericFacts。共同 Source Intake、私有 raw CAS、自动 driver 与操作员官方 PDF 上传已接入 Workbench。新的 automatic R1 中 Dell timeout、TSM transport exception，均未取得 HTTP status；两域 Fake-IP 均经 `okz` TUN，故仍为 0 PDF、0 Evidence、禁止自动 R2。Micron 与估值没有偷塞进本轮。
12. **S2 公司财务事实 mart（受控纵切 engineering pass）**：已从 2026-08-06 DELL／MU／NVDA CompanyFacts 与 Submissions 原始 capture 建立 1,319 条 observation，按 accession、accepted-at、vintage、期间角色、单位、taxonomy concept、source digest 和 supersession 保存；最近财年 9/9、当前 interim 15/15，PIT、跨案、季度/YTD、公式和 disclosure-cohort mutation 全过。DELL 受控纵切执行 7 个指标请求并全部 resolved，共返回 21 个 NumericFact、0 gap/conflict；private mart 仍不进入 Git，自然 planner、报告与前端消费未证明，故不宣称 S2 产品关闭。
13. **DELL S1/S2/S3 零调用纵切（已完成工程门）**：当前 Runtime 已把受控 Research Objective／planner atoms 编译为 5 个 EvidenceRequest；S1 使用 `Qwen semantic + BM25 lexical candidate union` 返回 80 个候选，S2 返回上述 NumericFact。该结果证明给定正确 atoms 时链路和数据库可协同运行，但没有证明 DeepSeek 能自然规划、候选已成为 Evidence 或研报质量通过。
14. **自然 Planner Canary R1（已执行并 terminal failed）**：DeepSeek Pro exact JSON、DELL 身份、5/5 required slot、10/10 facet 和全部 canonical metric/family 均正确，但返回 10 个 atoms，超过授权上限 8，故在 S1/S2 successor 前停止。没有 retry、fallback、手工裁剪或报告调用；这不是数据库失败。
15. **proposal/execution budget 分层处置（已完成）**：R1 10 条合法提案全部校验，本地按 required-slot 和 provider-neutral priority 稳定选择 8、延期 2；R1 失败 capture 保留，未重跑 Planner。
16. **保存 atoms 的 S1-C 产品输入审计（工程切片完成，产品门未关）**：Harness 已派生多 owner，owner-balanced 候选保护已实现；两个新 ranker 均因真实业务退化被拒绝，Evidence Role 仅 advisory。候选池可审计，但候选仍不是 Evidence。
17. **S1-D residual-gap 补源（intake ready / automatic path blocked）**：只尝试 Dell 与 TSM 两份官方 transcript。provider-neutral intake 与人工绑定 route 已可用，但本机 automatic path 仍未取得 PDF；当前不得 broad search 堆量、复制搜索摘要或自动重试。下一步优先上传官方 PDF；若必须恢复自动下载，由用户可见地做同 URL domain DIRECT／临时关闭 TUN A/B。取得 PDF 后仍须 parser、Evidence Gate、Pack 复编译和有限 S2 回归。
18. **S2 三案有限依赖回归（等待新 Evidence）**：只有 S1 取得并晋升新 Evidence 后才重编 NumericFact/lineage；当前没有新材料，不重跑无关 S2 控制面。
19. **S3 三案动态 Agentic Research**：保留已经完成的 DELL Planner R1，不重复付费证明相同能力；在合格 Evidence Pack 和 NumericFact 上继续动态缺口判断、重裁决和报告。模型负责研究判断，本地控制面负责事实、权限和确定性渲染。
20. **S4 产品闭环**：提供真实任务输入、澄清、计划查看和人工修改界面，并把通过验收的研究结果接入当前 Workbench；补齐 human review、repair 和 artifact lineage。
21. **S5 release**：扩大案例与对抗测试，执行发布、回滚、成本和 Owner acceptance。

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
