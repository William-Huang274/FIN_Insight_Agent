# 112｜Writer-only protected report remap 执行门

## 本轮目的

`RC-S2-007` 的 source-bound 数值权限和 protected report contract 已通过零调用工程门，但旧报告仍是不可变 L1 负例。本轮只建立一次终端重映射的执行权限和失败物化路径，不重跑研究，也不预先宣布新报告合格。

## 实现结果

1. 新增 `multi_agent_report_remap` scope validator：逐文件绑定旧 authority／result／assessment／private result、零调用 proof、typed authority catalog、人工 source-bound review、Provider profile 和当前实现 SHA。
2. 新增 remap-only message compiler：模型只看旧报告、最终 evaluation 和 typed authority；六节顺序、每节来源角色、六个 gap、八个 WWC 保持不变。
3. 新增独立 live runner：一个 Writer logical node，最多两个 contract attempts；只有第一次 Tool Call 已到达且合同校验失败时，才反馈精确 failure code 并允许第二次交卷。
4. Provider transport failure 不进入合同修正，不做静默 retry；成功或失败都物化 private terminal/full result 与 public result，并保留 capture refs、usage、finish reason、request／response digest。
5. public execution 语义拆分为 `logical_model_node_count`、`contract_attempt_count`、两项上限、analysis／continuation／upstream／network 计数与 `scope_compliant`，不再使用含混的“exactly one submission”。
6. 发现并修复一个零调用集成缺陷：remap draft 在加入 `remap_receipt` 时错误把旧 draft digest 纳入新 digest 计算，导致 deterministic renderer 拒绝合法 remap；现已先移除旧 digest 再生成新 digest，并由真实 DELL fixture 覆盖。

## TokenBudgetBasis

- node：`AGENT::WRITER::PROTECTED_REPORT_REMAP`
- purpose：只把完成的研究映射进受保护合同，不做新研究；
- input：旧 report 14,469 canonical chars；authority catalog 70,310 canonical chars；
- required output：六 sections、六 remaining gaps、八 what-would-change，以及 claim-scoped Evidence／authority／gap refs；
- schema burden：嵌套六节 protected tool；
- materiality／quality risk：high；
- comparable evidence：前一 Writer report 的严格交卷实际使用两次 bounded contract attempts；
- profile：DeepSeek V4 Pro GA Chat Completions，thinking disabled，max output 7,000，retry 0；
- stop：首个合法合同立即停止；第二次仍被拒绝即 terminal；成本和延迟仅为次级约束。

## 验证

- Project OS、scope、report authority、runner、S2 source-bound authority 定向：`83 passed`；
- fake Provider：第一次自由数字拒绝、第二次合同修正通过；两次拒绝 terminal；transport failure 一次即 terminal；
- compileall 与 `git diff --check`：通过；
- 全仓：`951 passed`，仅保留 2 条既有 SWIG deprecation warnings；
- Workbench：TypeScript `--noEmit` 与 Vite production build 均通过；
- active baseline：remap CLI 已显式注册，`189 Python／8 frontend／5 detectors／27 resources／0 forbidden`；archive redirect：`6,059` 条一致；
- 机器可读资产：`801 JSON／8 JSONL／912 JSONL records` 全部可解析；secret scan：`7,533 files／0 finding`。

## 边界与下一步

当前为 full engineering gate pass，但仍不是产品结果。旧报告继续 `financial_truth_L1_pass=false`。下一步必须是 clean commit／push → fresh Project OS preflight → fresh authority → 唯一 Writer logical node。自然 remap 成功后仍须独立 L1、八维内容质量、同输入保真／paired 与 qualified-human；S1、S3、泛化、Workbench 和 release 继续为 false。
