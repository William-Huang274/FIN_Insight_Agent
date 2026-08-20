# FIN 0.1.3 S3 — 分层 Evaluator 零调用实现与资格门

## 为什么做这一项

DELL Preview 的六份专业底稿、Lead 协调和三条反馈修订已经真实完成。随后两次独立 Evaluator 都得到 HTTP 200 完整响应，却把 16,000 completion token 全部用于思考，最终没有任何可见评审意见。第一次输入约 31,732 prompt token；把权威收敛到实际引用后，第二次仍有 24,591 prompt token，并以完全相同的方式失败。

这说明继续删字段或提高全局上限不会解决根因。一个节点同时审六个研究主题、经济机制、反方、WWC、跨角色矛盾和责任归属，任务跨度本身不合格。

## 本轮实现

评审链改成四层，但不重做任何已经成功的研究 Agent：

1. 本地完整 L1 检查身份、期间、引用、数字、数值关系、跨案污染和 case-level absence。
2. 六个角色分别接受一次内容审查，只读取自己的最终底稿和实际使用的权威材料。
3. 一次跨角色审查只读取六份审查结论、底稿摘要和 Lead coordination lineage，检查矛盾、重复计算、口径冲突和综合缺口。
4. 最多两条阻断 finding 返回最早责任角色；只重审受影响角色，再做一次跨角色复核。通过后才允许 Writer。

角色审查和跨角色审查不能新增 Evidence、NumericFact、因果关系或研究观点，只能判断、归责和阻断。数据／工具或 Harness failure 不得路由成模型修文。

## 真实 capture replay

零调用脚本重新物化当前 S1/S2 输入，并从不可变 checkpoint／capture 恢复六份最终底稿及其精确上下文。结果为：

- Cash：16,611 字符，5 Evidence／7 NumericFact／3 NumericRelation／1 gap；
- Counter：11,274 字符，6／0／0／2；
- Demand：12,066 字符，10／0／0／1；
- Operating：16,546 字符，2／12／6／0；
- Supply：17,621 字符，10／0／0／4；
- Value：18,365 字符，4／10／5／3；
- 跨角色审查：45,252 字符、6 个角色，不重复携带完整金融权威目录。

本地 absence blocking finding 为 0。这里更正了一个真实误报风险：当底稿已明确绑定 typed gap 或 bridge gap 时，自然语言中的“不存在／无法确认”由内容 Evaluator 判断是否越界，不再被词面分类器直接当作 case-level absence；没有任何 gap／bridge 权威时仍然硬阻断。

## 故障注入与预算

六类 mutation 全部 fail closed：缺角色、目标角色错误、未解析权威引用、底稿顺序变化导致不稳定、frontier 预算被篡改、无关角色被要求复审。

确定性 fake 路径为：

- 全部通过：6 role audit + 1 cross audit + 1 Writer = 8 个逻辑节点；
- 最多两处修订：13 个逻辑节点；
- 第三处修订：15 个节点，超过已批准上限，必须停止。

本轮 0 Provider 模型调用、0 网络、0 付费工具调用；但真实物化加载了本地 Qwen 检索模型，因此不把它误写成“没有任何模型参与”。

## 权限与边界

`successor_scope_decision_v1_2`、future authority 和 runner 必须同时绑定 frontier 与零调用复证的 ref／sha256／result digest。文件存在但未被权限链绑定，不能执行 live。

若任一单角色自然审查仍耗尽全部 reasoning 且没有可见输出，必须停止并做 Evaluator 模型／profile 选择；不得继续削减金融权威、扩大 token ceiling 或增加 DeepSeek 专用字段分支。

当前仍未证明：自然 Evaluator findings、Writer、完整 DELL 报告、独立八维质量、paired gain、qualified-human、S1／S3、跨案例泛化、Workbench 发布或 release。

## 工程门结果

- 分层 Evaluator／successor／runner／Project OS 定向回归：109 passed；
- 全仓：913 passed，只有既有 SWIG deprecation warnings；
- compileall：通过；
- active baseline：185 Python／8 frontend／5 detectors／27 Runtime／0 forbidden；
- configs：755 份 JSON 全部可解析；
- Project OS：8 份 JSONL／867 行全部可解析；
- secret scan：7,473 files／0 findings；
- `git diff --check`：通过。

完整工程门不等于自然评审通过。当前只剩 clean commit／push、fresh Project OS preflight 和一次 exact-once 层级 Evaluator live。
