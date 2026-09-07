# FIN 0.1.3 S3 — 通用 Multi-Agent successor frontier 全工程门

日期：2026-08-20
状态：`zero_call_full_engineering_gate_pass / clean_commit_push_and_fresh_preflight_pending`

## 1. 为什么本轮没有继续造 R16／R17

R15C 是第三次发生在 Provider 之前的 successor 集成失败。继续按 attempt 名称增加 Schema、Validator 和 runner 条件，会把历史运行的差异继续固化为代码分支，却仍不能回答任意节点应该复用、重绑还是重跑。按既定止损边界，本轮没有新增 R15D、R16 或 R17 专用分支，而是实现一份 provider-neutral 的 execution frontier。

## 2. 通用 frontier 做什么

`src/sec_agent/research/multi_agent_successor.py` 只根据不可变 lineage 编译四种节点状态：

1. `exact_reuse`：原工作底稿、模型真正看到的上下文及其 digest 完全一致；
2. `derived_digest_rebind`：所有业务字段逐字节一致，只有本地派生的 `context_digest`／`workpaper_digest` 与 capture-bound 上下文不一致；重新走正式 Validator 后保存新 digest 和等价 receipt；
3. `fresh_rerun_required`：业务字段无法在原模型可见上下文下通过，或 capture 不足；
4. `pending_fresh`：该节点从未完成。

任何业务字段变化、capture／terminal SHA 漂移、节点顺序变化、角色变化、digest 变化或 completed 节点试图重跑都会 fail closed。Project OS、authority 和 live runner 消费同一份 frontier，不再分别解释历史 attempt。

## 3. DELL 真实 lineage 编译结果

- Demand repair：`exact_reuse`。模型可见 context digest 为 `1ddcce79...f0e6b`，原工作底稿 digest 与重验结果均为 `3914ddf8...47e0`。
- Cash repair：`derived_digest_rebind`。原业务 payload digest 为 `58322004...c6822`，逐字节等价；原本错误绑定本地 context `18d5f6ab...24063`，模型当时真正看到的是 `51944726...37d5f`，重验后的工作底稿 digest 为 `1f5d07a2...5109e`。这只修复 lineage，不改写任何观点、事实、数字、引用或边界。
- Supply repair：`pending_fresh`。它仍是唯一允许开始的新反馈修复节点。

frontier digest 为 `efc48ed2...d3213`。R15C authority、public result 和 private terminal failure 均保持不可变；该编译过程为 0 模型、0 Provider、0 网络、0 Candidate promotion。

## 4. Runtime 与权限边界

新的 generic authority 只允许：复用六份计划、Lead 计划、六份初始底稿和 Lead challenge partition；原样复用 Demand；按等价 receipt 使用 Cash；fresh 执行 Supply；随后最多两轮独立评估、最多两个 Evaluator 指向的局部返工和一个条件式 Writer。

明确禁止：analysis continuation、已完成节点重跑、修改研究输入、外部来源联网、Candidate 晋升、产品发布、qualified-human 自签、S1／S3／泛化／release 宣称。每个真正付费的新节点仍必须单独形成 `TokenBudgetBasis`，成本和延迟不能替代质量依据。

## 5. 验证

- 新增 exact／rebind／pending、业务字段 mutation、真实 terminal／request capture 回放和 authority 绑定测试；
- Project OS scope decision 独立校验通过；
- 定向测试 `75 passed`；
- 全仓 `905 passed`；
- `compileall` 通过；
- active baseline 校验通过：`185 Python / 8 frontend / 5 detectors / 27 Runtime / 0 forbidden`；
- repository secret scan：`7,460 files / 0 findings`；
- 新增 JSON 与两份 Project OS JSONL 均完成逐行解析，`git diff --check` 通过；
- 本轮未调用模型、Provider 或网络。

## 6. 下一步

完成活动基线、秘密扫描与 diff 检查后，做干净提交并推送；随后在 clean／synced HEAD 上执行 fresh Project OS preflight，签发唯一一次 generic successor authority 并运行。若再次出现新的 S0 lineage／authority 问题，不再新增 attempt-specific 分支；若成功，则分别报告 Supply、Evaluator、Writer、完整报告 L1 和内容质量，不能把工程成功冒充 S3 通过。
