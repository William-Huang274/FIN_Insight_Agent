# 121｜当前 DELL 动态单单元主链切换

日期：2026-08-23

范围：零模型工程实现；不含自然 DeepSeek 调用、内容验收或 S3 通过声明。

## 决策

旧 `scripts/research/run_s3_dynamic_single_cell_live.py` 只完成一次 Planner、一次 S1/S2 消费和固定分段交卷，不能代表当前定义的动态 Agentic Research。文件继续保留用于历史 authority 和失败结果追溯，但已退出活动基线入口。

当前权威入口改为：

- `scripts/research/run_s3_current_dynamic_single_unit_zero_call.py`：当前 Runtime、反馈、计划变化、图假设和恢复的零调用证明；
- `scripts/research/run_s3_current_dynamic_single_unit_live.py`：等待 fresh authority 的自然模型入口；
- `src/sec_agent/research/dynamic_single_unit_loop.py`：两者共享的 provider-neutral 合同编译源。

## 新 live 的真实行为

1. 初始只给模型用户问题、DELL 法定身份、截至日期和工具能力。
2. 模型从 12 条命题绑定请求中选择第一轮，Harness 真实执行 current S1/S2。
3. Harness 返回 reviewed Evidence、typed NumericFact、关系、估值／情景和可行动 FeedbackReceipt；Candidate 仍无 Evidence 权限。
4. 模型必须提交 Reflection。若选择继续，`next_request_ids` 成为第二轮受控计划；若停止，必须通过覆盖和预算门。
5. 第二轮结果再次返回模型，模型重新反思并作最终 StopDecision。
6. 最终工作底稿从两轮已审资料、反馈、PlanDelta、GraphDelta 和显式 gap 编译；Harness 绑定引用、身份、日期和数值权威，不代写观点。

最大 Provider 节点为 4：初始请求选择、第一轮反思、条件式第二轮反思、最终底稿。上限依据完整研究动作与既有 DeepSeek 推理耗尽证据设置，不以省钱或速度为删减理由。每个节点 0 retry；连接性 replacement 必须使用新 attempt/authority，业务或合同失败不得自动重标成功。

## 验证

- 新入口与合同进入 active baseline，旧 single-cell 入口退出；活动图为 205 Python、8 frontend、5 detector、28 Runtime resource、0 forbidden reference。
- 定向测试 33 passed。
- 全仓 1,074 passed；仅有既有 SWIG deprecation warning。
- 意外由前端工具生成的两个 pnpm 文件未删除，已移动到 `.codex_runtime/generated_frontend_pnpm_20260823/`，不污染权威工作树。

## 下一门

当前仍是 `live_not_run`。必须先完成 compileall、secret scan、diff check、clean commit／push 和 repository-aware fresh preflight；之后签发一份绑定干净实现提交与 current Pack digest 的 exact-once authority。自然 live 成功后还需独立做 L1 与八维内容质量评价；单单元通过不等于 multi-agent、S3 或产品验收。
