# FIN 0.1.3 S3 — R7 空引用合同失败与 R8 五底稿 checkpoint 门

日期：2026-08-20
状态：`R7_terminal_failure_preserved / five_workpapers_revalidated / R8_downstream_successor_zero_call_pass`

## 1. R7 实际运行到哪里

R7 复用了已经验证的六份 Specialist plan 和一份 Lead plan，没有重新调用这些前缀。它实际保存了：

- 5 次 Specialist 可见分析；
- 6 次严格交卷；
- 11 次 Provider attempt；
- Demand、Operating、Value、Cash 四份当场有效 workpaper；
- Supply 的完整分析和两次交卷输出。

运行没有访问外源网络，没有晋升 Candidate，也没有进入产品发布。Counterevidence、Lead coordination、repair、Evaluator 和 Writer 尚未开始。

## 2. 为什么 R7 失败

Supply 角色的 current context 有 10 条 reviewed Evidence，但合法 NumericFact 和 numeric relation 都是 0。旧 Tool Schema 对空引用集合生成了可见占位 enum `__NO_VALID_REF__`，同时又把该数组设为 `maxItems=0`。模型在第二次交卷中选择了 Schema 明示的占位符，本地 Validator 却把它当成真实引用并以 `multi_agent_workpaper_ref_out_of_scope` 拒绝。

同时，旧反馈只检查 workpaper 顶层引用，没有指出 `sourced_claims[*].numeric_refs` 等嵌套路径。第一次交卷的 stop reason 超长虽被反馈后自然缩短，但第二次仍无法从模糊错误中识别这个 Harness 自相矛盾。

所以最早责任层是 S0 Harness 的合同编译和反馈，登记为 RC-AR-008；不是资料缺失、召回／排序、网络连通或 DeepSeek 不会研究。

## 3. 本轮结构修复

同一引用合同现在同时驱动 Schema、Validator、fake／replay 和 model feedback：

- 合法引用集合非空时，未知引用继续 fail closed；
- 合法引用集合为空时，只接受 singleton `__NO_VALID_REF__` 作为传输占位，并在进入业务对象前规范化为真正的空数组；
- 任何其他占位组合或越权引用继续拒绝；
- 递归反馈返回精确嵌套字段路径，避免模型只能猜顶层错误；
- Prompt 可表达“没有合法引用”，而最终 workpaper 不保存伪引用。

使用 R7 原始 capture 零调用重放后，Supply 第二次交卷可合法物化，workpaper digest 为 `7b896715c03471e6f356bf569dc9881882157836f69b8bf870908204fac8459b`。R7 的历史 result 和 terminal failure 不改写。

## 4. 五底稿 checkpoint

当前 checkpoint 绑定：

- R7 authority、public result 和 private terminal result；
- 五个角色的原始 attempt、request／response digest；
- 五份 workpaper digest；
- 六份 Specialist plan 和一个 Lead plan 的 predecessor lineage。

checkpoint digest 为 `a378d83e364911a79a7cc123df5f3977f489a367071565cca9f3050ee37b7b36`。completed agents 为 Demand、Operating、Value、Cash、Supply；唯一 pending agent 为 Counterevidence。

## 5. R8 successor 的有界范围

零调用 proof 使用 current Runtime 重新物化出 12 个 EvidenceRequest、192 个候选、44 个 typed fact request（27 resolved／17 gap）和 87 个 NumericFact；六个角色的视图均非空，说明 checkpoint 没有绑定旧输入或跨案例污染。

R8 只允许最多 10 个新模型节点：

1. Counterevidence workpaper 1 个；
2. Lead coordination 1 个；
3. 最多 3 个 challenge repair；
4. 最多 2 轮 Evaluator；
5. 最多 2 个 evaluation repair；
6. 条件式 Writer 1 个。

前五份 workpaper 和所有 plan 禁止重跑。每个付费阶段分别记录输入规模、职责、Schema 负担、研究质量风险、历史证据、reasoning profile 与停止规则；成本和延迟不是删减研究工作的依据。

## 6. 当前能力边界

本轮证明的是 checkpoint 恢复、空引用合同和下游 runner 的工程一致性。它没有证明 Counterevidence、跨角色协调、Evaluator 或 Writer 的自然表现，也不构成 S1、S3、跨案例泛化、qualified-human、Workbench 发布或 release。R8 形成报告后，仍必须独立执行事实／数字／引用 L1、八维内容质量和人工内容验收。

## 7. 工程复证

- checkpoint／runner／Project OS 定向回归：`74 passed`；
- 全仓：`865 passed`，仅两条本地向量库 SWIG 既有弃用 warning；
- Python `compileall`：通过；
- active baseline：`184 Python / 8 frontend / 27 Runtime / 0 forbidden`；
- repository secret scan：`7,406 files / 0 finding`；
- 8 份 Project OS JSONL：完整解析；
- `git diff --check`：通过。

这些结果允许把实现、失败证据、checkpoint、scope decision 和工作记录提交为一个干净工程门；真实 R8 authority 必须在该提交之后另行绑定，不能预先写死未冻结的代码身份。
