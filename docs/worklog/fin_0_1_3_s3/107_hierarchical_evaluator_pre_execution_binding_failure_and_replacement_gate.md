# FIN 0.1.3 S3 — 分层 Evaluator 启动绑定失败与 replacement gate

## 发生了什么

分层 Evaluator 的零调用证明、完整工程门、clean commit／push 和 fresh Project OS preflight 均已通过，随后签发了第一次真实 successor authority。运行在任何 DeepSeek 节点开始前终止：执行器构造通用 successor lineage 时引用了仅存在于 authority 校验函数内部的 `scope_projection`，触发 `NameError`。

这不是 DeepSeek 合同不遵循、角色评审能力不足、S1 数据缺失或网络故障。最早责任层是 S0 Runtime 的“校验结果进入执行阶段”绑定错误。该 attempt 已被视为消费，不得复用。

## 不可变失败留存

旧 authority 和公共结果均已保存。对应 capture root 在失败时为空；private terminal result 明确记录：

- authority 校验已完成；
- 失败阶段为 `pre_execution_binding`；
- 新模型节点 0；
- Provider attempt 0；
- 外部来源网络 0；
- Candidate promotion 0；
- 产品发布 0。

因此该失败不能用于评价自然 Evaluator、Writer、报告内容、S1、S3 或模型能力。

## 根因修复

执行器不再读取 validator 局部变量。层级 proof 现在从 authority 已绑定的 proof 文件和 successor frontier 重新验证，并编译成显式 execution binding。通用 successor 的 checkpoint／frontier／proof lineage 也抽成一个可直接测试的编译边界。

同时新增 pre-execution terminal materialization：authority 已通过、capture root 已建立、但尚未进入模型节点时发生的非合同异常，会原子保存稳定 failure code、失败阶段、0 Provider／0 网络计数和 private terminal result。它不能覆盖已有输出，也不能把无效 authority 伪装成已授权运行。

## 复证

- 通用 successor authority、frontier、proof 和 execution binding 定向测试：110 passed；
- 全仓：914 passed，只有既有 SWIG deprecation warnings；
- compileall：通过；
- active baseline：185 Python／8 frontend／5 detectors／27 Runtime／0 forbidden；
- configs：757 份 JSON 可解析；
- Project OS：8 份 JSONL／871 行可解析；
- secret scan：7,476 files／0 findings；
- `git diff --check`：通过。

## 下一步边界

本修复只恢复“能够安全开始分层 Evaluator”的资格。必须 clean commit／push，再执行 fresh Project OS preflight，并签发全新 run／capture／private／public identity。旧 authority、空 capture root 和失败结果保持不可变。

replacement live 才能回答：六个单角色自然审查能否产生可见 finding、跨角色审查是否稳定、是否需要局部修订、Writer 能否运行以及最终 DELL 报告内容是否改善。当前 S1／S3／泛化／qualified-human／Workbench／release 仍未通过。
