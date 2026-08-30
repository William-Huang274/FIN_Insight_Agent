# S1 工作记录 130：成熟栈优先纠偏、旧自研协议收口与 Steps 1–3 启动

日期：2026-08-30
状态：STEP 1 MATERIALIZED / STEPS 2–3 ACTIVE / NO PRODUCT OR COMPONENT PASS YET

## 1. Owner 纠正

Owner 指出：产品全面迁移的第二层工程治理和第三层运行时本来应大量借鉴或直接采用成熟技术栈，但工作却再次被扩写成一套自研计划执行协议；连续一天主要在制定 Phase 0–7 文档，成熟组件测试和真实产品工作尚未开始。

Owner 随后授权：先把成熟栈优先、反无限自研和进度止损融合成 Codex 的长期 guideline，再立即开始此前说明的第一至第三步：

1. 终止并收口旧自研协议方向；
2. 用真实 FIN slice 资格验证成熟项目运行底座；
3. 完成/复核 S1–S5 全产品能力和迁移审计。

## 2. 出发点反思

旧方向的原始动机是保护 R14 的真实高风险边界：失败不可隐藏、阶段责任不后传、删除要可恢复、不可逆动作要有证据。这些原则本身仍正确。

错误发生在实现层：把针对删除和高风险运行的强控制推广到读取、计划、review、Git 和隔离实验；又把“计划可审计”误解为“必须先自研一套能授权计划本身的 runtime”。每次 review finding 继续增加状态、ticket、CAS、receipt 和 successor，最终控制面成为主要交付，产品工作被推迟。

纠正不是降低准确性，而是把通用准确性、恢复和并发交给成熟工程系统，把 FIN 的严格性集中到金融事实、Evidence、PIT、citation、人审和 release。

## 3. Step 1 已落盘的结果

- 根 `AGENTS.md` 新增成熟栈优先、三层分责、复杂度预算、docs-only 止损、按风险分级和进度分类规则；
- 新增 `docs/project_os/mature_stack_first_and_complexity_budget_policy.zh-CN.md`，作为跨任务长期记忆；
- 原 `FIN_0_1_3_PRODUCT_WIDE_ARCHITECTURE_REBASE_AND_MATURE_STACK_MIGRATION_EXECUTION_PROGRAM_20260830.zh-CN.md` 顶部标记 `SUPERSEDED / AUDIT-ONLY / NO EXECUTION AUTHORITY`，完整保留历史，不再修订其自研状态机；
- 新增一份合并的架构决定与 bounded execution baseline，记录停止原因、仍有效的不变量、重新提出有限自研的证明条件和真实 Steps 1–3；不复制运行时状态机。独立只读复核曾提醒不要让纠偏本身增加过多文档，因此没有保留分开的 ADR 与 baseline。

这部分属于治理/文档增量，不冒充成熟组件已经安装、代码已经迁移或产品能力已经增加。

## 4. Git 与不可变事实

开始时：

- canonical checkout=`D:\FIN_Insight_Agent`；
- branch=`codex/fin013-dell-s1-s2-product-bridge`；
- HEAD/upstream=`1472ecef4f02adfb51f5fcd1474dc844554ab5dd`；
- 既有未提交变更只有旧超大执行程序草案，本轮保留并原位 supersede，没有 reset 或丢弃。

R14 继续保持：

- implementation freeze=`7e25cad95ee84b39fb2a51063100405bc27da6e5`；
- preview=`27,026 total / 26,787 pass / 239 fail`；
- event/assertion=`228/11`；event mismatch=`277`；
- RC-S1-109/110 open；
- R15/R16=false，formal=false，Evidence/S2/report/release=false。

`D:\FIN_Insight_Agent\data\indexes` 未删除、未修改。只有后续实测证明 D 盘空间是 qualification blocker 时，才可按 Owner 已给出的严格有限范围另行执行。

## 5. 当前真实进度

- 产品增量：0；
- 工程集成增量：0；
- 资格实验结果：前检进行中，尚无 candidate PASS；
- 治理/文档增量：Step 1 已物化；
- 下一真实动作：在 Z 盘创建隔离环境，使用同一 FIN fixture 实际运行成熟 workflow/metadata/experiment/trace slice，并并行校准现有 S1–S5 审计。

如果下一工作包仍只有计划而没有可执行结果，应按新规范立即停止并报告，而不是继续补协议。
