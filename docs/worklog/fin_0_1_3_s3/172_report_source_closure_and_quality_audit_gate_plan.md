# S3 工作记录 172：上一版研报信源闭环与研报质量审计强制门

日期：2026-08-25

状态：`owner_required / plan_and_rubric_recorded / R17_read_only_quality_baseline_fail / source_closure_and_product_acceptance_open`

## 1. 用户纠正与问题

Owner 明确指出：既然上一版研报展示出的信源缺失没有全部解决，就必须把这部分加入当前规划；同时，审计 Agent 必须把研报质量列为审计内容之一。

此前的综合工程审计可以证明代码、不可变性、source/object/index/runtime 和回执没有 material finding，但该结论不能回答研报是否拥有充分、可核验、读者可读的来源，也不能关闭 R17 的四组 remaining gaps。把这两个 verdict 合并，是当前最早的治理缺口。

## 2. 当前事实基线

- R38 已关闭 reviewed public source 从 Pack 到 current runtime 的技术断链，reviewed-label missing occurrence 为 `4 -> 0`。
- DELL current Pack 仍为 `55 Evidence / 14 gaps`，`0 closed / 3 narrowed`。
- R38 bounded dynamic unit 选择 9 个 open gaps；R17 Writer 把相关边界聚合为 4 组。14／9／4 是不同层级，不是 gap 已从 14 关闭到 4。
- R17 fresh independent content pass 只证明两个修订路径关闭 R16 finding；references、四组 remaining gaps、拓扑和数字集合均未变化。
- 公司 units/share、ASP/mix、PVM、AI 产品利润、AI 营运资金归因、供应分配与需求持续性仍有 material boundary。
- current product projection 仍有 4 个请求 blocked by Evidence admission；三案 public-information-gap authority 均为 0。
- R17 读者侧引用仍依赖内部 `EV::`／`GAP::` lineage，publication-ready 的来源名、标题、时点和 locator 展示尚未验收。

## 3. 计划变更

本轮将以下内容加入 FIN 0.1.3 release-blocking 计划：

1. 建立 R17 report gap 到 current Pack／dynamic unit／Writer group 的机器可读映射和逐项状态。
2. 先完成已有候选的 CandidateDecision、Evidence Gate 与 qualified-human admission，再只对真实 residual 执行外源来源梯子。
3. 重编 Pack、Readiness 和 S2 产品价值桥；没有公司级权威时，PVM／profit／working-capital attribution 必须继续为 null/gap。
4. readiness 达标后只运行受影响动态单元，再生成不覆盖 R17 的 Writer successor。
5. 新报告必须提供逐 Claim source/authority、读者可读 citation/source appendix、反方、WWC、定量桥和显式 remaining-boundary register。
6. integrated/final audit 分别签发 engineering/evidence 与 report/research-quality verdict；qualified-human product verdict 单独保留。

对应 source-of-truth 已更新：

- `docs/product/FIN_0_1_3_CURRENT_BASELINE_AND_S0_TO_S5_CLOSEOUT_PLAN_20260812.zh-CN.md`
- `docs/eval/FIN_0_1_3_RESEARCH_CONTENT_OUTPUT_QUALITY_RUBRIC_20260806.zh-CN.md`
- `docs/architecture/retrieval/FIN_0_1_3_DELL_REPORT_BOUNDARY_DENSITY_AND_SOURCE_SUFFICIENCY_AUDIT_20260822.zh-CN.md`
- `docs/worklog/00_current_master_checklist.md`
- `docs/project_os/current_context_pack.zh-CN.md`

## 4. 审计 Agent 指令

已向现有作者分离、只读审计 Agent `/root/r35_guard_fresh_reaudit` 下达新增范围。它不得改文件、联网、调用模型或重写报告；必须检查：

- R17 引用完整性与读者可读性；
- 14/9/4 gap 映射及其不误导性；
- 逐 Claim source／authority／gap、来源等级、时点、主体和口径；
- units/share、ASP/mix、PVM、产品利润和营运资金等未解决边界；
- candidate、bundle 报价、行业样本、供应商 read-through 和研究阈值是否被冒充公司事实；
- 结论价值、因果克制、定量桥、反方、WWC、可读性和最终交付完整性；
- qualified-human、S1/S2/S3、product/publication/release 权限没有被误授。

审计必须输出 P0/P1/P2/P3 findings，并明确区分 engineering/source-consumer pass 与 report/product-quality pass。材料不足时必须保持质量门 open，不能把 0 finding 写成产品 PASS。

## 5. 本轮验证与边界

- 本轮只更新计划、Rubric、Project OS 和审计范围；没有修改 Runtime、Evidence、Pack、报告或产品代码。
- 没有运行模型、Provider、网络补源、embedding、reranker、动态 Agent 或 Writer。
- 没有重新评分 R17，也没有把审计 Agent 冒充 qualified human。
- 规划与审计门 release slice 已提交为 `e02b7e33`（`docs(audit): make report quality release-blocking`）。两次 `git push origin codex/fin013-dell-s1-s2-product-bridge` 均因无法连接 GitHub 443 失败；远端同步未完成，不能写成已推送。
- 只读审计已回报并记录在第 6 节；下一步按新清单执行 Evidence admission、残余来源闭环和报告 successor。完成前 S1／S2／S3、产品、publication 和 release 均保持 false。

## 6. 作者分离的 R17 只读质量基线结果

审计目标为 immutable commit `aae2cccffc27ae2e8b56fe0f4c49e0329213d8ba`、tree `fc599bdc0c7eef91c83836f7a8e59deb8de42d17`。审计开始时 HEAD／index／worktree clean；审计期间本作者并发更新本计划，reviewer 没有写文件，因此最终 shared worktree dirty 不属于 reviewer。

固定结果：

- P0/P1/P2/P3：`0/1/2/1`；
- `engineering_and_evidence_pipeline_verdict=PASS_BOUNDED`；
- `report_research_quality_verdict=OPEN/NOT_ASSESSABLE`；
- `qualified_human_product_verdict=FALSE/NOT_GRANTED`；
- 正式八维：`OPEN/NOT_ASSESSABLE`，不得复用 R15 同作者 diagnostic `27/32`。

Findings：

1. **P1 读者侧引证不可独立核验**：R17 rendered report 的机器绑定完整，但 reader-facing surface 只有内部 EV/GAP；缺来源标题、发行人、发布日期、报告期、页／节、URL／locator 和 bibliography/source legend。两个带 Facts 的 WWC 没有可见 Sources。该项阻断 Q2/Q8 和 publication readiness。
2. **P2 14/9/4 层级映射缺失**：R17 四行是 10 个 GAP ref 的主题聚合；R38 9 个是 active-unit 子集；current 14 还含四个其他 facet。R17 没有字面声称关闭，但没有 crosswalk，不能作为 current report 使用。
3. **P2 WWC 不可执行**：六组 WWC 多数缺冻结的 metric/event、窗口、阈值、owner 和完整证据路线；reversal conjunction 依赖未声明的 predeclared threshold，Q7 仍 open。
4. **P3 重复和 Facts 密度**：section 与顶层 WWC 重复，执行摘要和 confidence 重复展示大量 typed facts，降低 senior-reader 可用性。

通过项也必须保留：18 个被用 Evidence 的主体、时点、来源等级和 supplier read-through 方向机器绑定完整；units/share、ASP/mix、PVM、AI 产品利润、营运资金归因、供应分配和需求持续性均没有被伪关闭；行业 estimate、bundle 样本、同季订单／收入／backlog 和现金／营运资金 proxy 的边界总体克制。这些通过项不能补偿 P1/P2，也不能授予产品权限。

## 7. Program-level execution plan 已补齐

Owner 进一步要求：继续实现前，必须把第 3 节的七项拆成需求票、依赖图、输入输出、验收测试、
停止条件和责任阶段；细项不能只审工程，还要审模型各环节输出和最终研报输出。

已新增：

- `docs/architecture/research/FIN_0_1_3_DELL_SOURCE_CLOSURE_MODEL_AND_REPORT_QUALITY_EXECUTION_PROGRAM_20260825.zh-CN.md`

该程序把七项拆成七个交付 epic，加一个治理前置，共 34 张 ticket，并建立 E/M/R 三条互不替代的 Definition of Done：

1. E：工程、数据、Evidence、数值、不可变性和 replay；
2. M：embedding/reranker、动态 Agent、Writer 各节点的实际输出质量与 TokenBudgetBasis；
3. R：逐 Claim 来源、定量桥、counter、WWC、可读 citation/source appendix、八维质量和最终交付。

程序同时把 4B embedding 放入混合 challenger，保留独立 reranker bake-off；历史 4B reranker 失败
不被改写，任何 challenger 都必须先过 candidate ceiling、同池、逐案稳定性和 report-material gain。
第一张实现票固定为 `DELL-RSQ-00A` baseline manifest；本记录更新仍是文档／治理工作，没有修改
Runtime、Evidence、Pack、模型、报告或产品代码，没有网络、embedding、reranker、Provider、动态
Agent 或 Writer 调用，也不代表任何 stage 或产品门通过。

## 8. DELL-RSQ-00A—01C 实现 successor

Owner 已授权计划完成后开始实现。确定性首片已在 commit `43e3a555...a2d2` 建立 baseline manifest、
质量协议、逐节点权限模板、provider-neutral crosswalk compiler、materializer 和 17 个 mutation／合同
测试，并在该 clean commit 上物化 R1。完整记录见：

- `docs/worklog/fin_0_1_3_s3/173_DELL_RSQ_00A_01C_baseline_quality_and_crosswalk_materialization.md`。

R1 content digest=`10fefe2f...54d17`，精确计数 `14 Pack / 9 dynamic / 4 Writer groups / 10 Writer
refs / 4 S2 bridge`；closed 与 proved boundary 均为 0。实现把 technical chain、unit selection、research
disposition 和 next action 分成正交状态，防止把 14→9→4 写成 gap closure。fresh author-separated
crosswalk review 尚未完成，因此 `G1=false`；本计划记录不能被引用为独立验收。
