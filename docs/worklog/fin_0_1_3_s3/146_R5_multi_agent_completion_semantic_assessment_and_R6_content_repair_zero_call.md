# FIN 0.1.3 S3：R5 多 Agent 完成、独立语义审查与 R6 内容返修零调用门

时间：2026-08-23

状态：`R5_contract_complete / independent_L1_L2_fail / R6_content_repair_zero_call_proven / exact_Project_OS_scope_ready / clean_preflight_pending`

## R5 自然运行实际完成了什么

R5 精确复用 R3／R4 的 17 份不可变 Provider capture，没有重跑已完成研究；只让 Cash、Operating、Value 完成三份已批准返修，并执行 Lead R2。新增 8 次 DeepSeek 调用全部完成，0 retry、0 fallback、0 外源网络和 0 Candidate promotion。至此六份 Specialist workpaper、两轮 Lead 决策和完整 lineage 均通过结构合同。

公开结果为 `configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_submission_successor_live_result_v1_4.json`，result digest=`35709b3b40fb7ff8d35ac18bf9640a2266d108d746f0eedce0fbd79329b63f7d`。这证明动态多 Agent 编排、独立会话、局部返修和 Lead 复核能自然完成，但不等于金融研究内容合格。

## 独立审查发现的真实业务错误

独立审查没有调用模型、检索或新增资料。身份、引用存在性、capture lineage 和合同结构通过，但 L1／L2 失败，共发现七项 material 问题：

1. Operating 把费用率改善约 `+6.7pp`、毛利率拖累约 `-3.4pp`、经营利润率净改善约 `+3.4pp` 错写成费用端贡献“约 100%”；
2. 把同季度 AI 订单与同季度已确认收入读成同一订单批次的转化关系；
3. 把应收＋库存－应付的资产负债表存量变化写成精确现金吸收；
4. 用 NVIDIA 的 hyperscaler 客户结构推断 Dell 客户结构近似同构；
5. 把 NVIDIA 出口管制风险直接升级成已证明的 Dell 暴露；
6. 把公司整体毛利率当成 AI 产品定价权的必要检验；
7. 把客户为供应不确定性提前锁定基础设施的描述升级成已发生且必然反转的需求前置。

Supply 角色通过，但信息密度偏低；这属于当前材料边界，不是本次七项错误的直接原因。诊断性适用分为 `18/28`，Q8 Writer 交付维度不适用。正式八维评分、Writer 和 S3 acceptance 继续禁止。

评估结果固定在 `configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_R5_content_assessment_v1_0.json`。

## 根因与结构处置

这些问题不是新的 S1 信源缺口或 S2 数字缺失。DeepSeek 生成了表面合理的金融叙事，但压扁了五类可复用区别：有符号桥接与贡献比例、同期间共现与同批次转化、存量代理与现金流、公司毛利与产品定价权、披露主体与目标公司暴露。Lead 基于相同自由叙事复核，因此重复了部分错误。

处置没有增加 DeepSeek 专用核心分支，也没有让 Harness 替模型写观点：

- 新增 provider-neutral 金融语义关系规则，注入各角色研究方法；
- 把七条独立 finding 编译为 immutable challenge／FeedbackReceipt；
- 只返修 Demand、Operating、Value、Cash、Counterevidence 五个责任角色；
- Supply 底稿与全部 Evidence／NumericFact／Relation／gap 权限保持不变；
- 返修后只允许一轮新的 Lead 复核，再进行独立 L1／L2 审查。

## R6 零调用复证

R6 zero-call 使用 R5 public／private digests 与独立评估逐项绑定，编译出 7 条 challenge、5 个 repair context 和 5 个 compact submission view。全部检查通过：

- exact five-role target set；
- Supply 不返修；
- 旧 context 迁移到新方法规则时仅改变 rules 与 digest，不扩大证据权限；
- 0 模型、0 Provider、0 网络、0 S1/S2 request、0 Candidate promotion；
- Writer、S3、发布和 release 保持禁止。

公开 proof 为 `configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_repair_zero_call_result_v1_0.json`，result digest=`836924eb75ccc7bd206032d0adbf349199146045323158eb2369d0c7c40a6b93`。

新自然拓扑由实际任务编译为 12 次 Provider 上限：五个角色各一次分析草稿＋一次 strict submission，共 10 次；Lead 一次分析＋一次 strict submission，共 2 次。0 retry、0 fallback、0 新检索、0 外源和 0 promotion。每类付费节点必须在 authority 中记录 task-specific `TokenBudgetBasis`。

## 验证与下一门

- 定向测试：`21 passed`；
- 全仓测试：`1133 passed`，仅两条既有 SWIG deprecation warning；
- Python compileall、pyflakes：通过；
- Workbench TypeScript typecheck 与 Vite production build：通过；
- active baseline：`211 Python / 8 frontend / 5 detectors / 28 Runtime / 0 forbidden`。

## R6 Project OS 精确范围门

旧的 current multi-agent scope decision 仍描述最初六角色全链上界：29 次 Provider attempt、13 个 S1/S2 request 和 12 轮检索。它是历史 R1 全链决策，不能拿来为当前只修七项语义错误的 R6 签权。一次只读预检因此只用于发现范围漂移，没有据此签发 authority，也没有调用模型。

当前新增独立的 `content_repair_scope_decision_v1_0`，并把预算编译器从 runner 移到 provider-neutral repair Runtime 供 Project OS 与执行器共同引用。该门只允许：

- Demand、Operating、Value、Cash、Counterevidence 五个责任角色各一次分析和一次严格提交；
- Supply 原底稿与全部 Evidence／NumericFact／Relation／gap 权限保持不变；
- 一次 Lead 分析和一次严格提交；
- 总计最多 12 次 Provider attempt，0 新 S1/S2、0 检索、0 外源、0 retry、0 fallback、0 Candidate promotion；
- Writer、S3 acceptance、泛化、产品发布与 release 继续禁止。

反向测试证明把调用数改为 13、替换任一责任角色或漂移绑定摘要都会 fail closed。全仓回归随该门更新为 `1136 passed`，仍只有两条既有 SWIG deprecation warning。正式 repository-aware preflight 必须等这份决策与验证代码形成 clean／synced commit 后再执行。

签发器还必须把该精确 scope decision 作为 authority 的受摘要保护输入；只复制同一组 12 次预算而没有这份 Project OS 决策，不能获得执行资格。

下一门是完成账本与工程检查、clean commit／push、current decision-bound Project OS preflight，再签发唯一一次 R6 content-repair authority。自然 R6 完成后仍必须独立复核七项问题和全角色新输出；只有 L1／L2 与内容质量通过，Writer 才能解冻。R5 不会被追认为内容通过，R6 也不授权新资料、MU／NVDA、异质留出、Workbench publication 或 release。
