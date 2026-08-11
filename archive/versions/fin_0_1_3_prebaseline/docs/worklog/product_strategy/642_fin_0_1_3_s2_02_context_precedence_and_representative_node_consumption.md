# 642 — FIN 0.1.3 S2-02 上下文优先级与代表节点消费

日期：2026-08-06
状态：`zero_call_node_consumption_pass / natural_canary_pending`

## 问题

S2-01 扩大回归出现 `60 passed / 3 failed`。显式给 Specialist 的 Evidence 会被 repository Product Intelligence autoload 补入的内容改变排序或挤出，导致同一请求随当前工作目录的数据不同而变化。若不先修复，后续 DeepSeek canary 无法区分模型能力、合同问题与环境污染。

## 判断

- 最早责任层是低层 Agent data-view builder 的默认 autoload 语义，不是 DeepSeek，也不是 metadata compactor。
- 不能删除生产 Product Intelligence autoload；它应由 Research Lead 显式决定，而不是由低层 helper 猜测。
- S2-02 不能只恢复三条旧测试，还必须证明 S2-01 合同已经进入真实的代表性节点消费路径。

## 完成内容

1. `multi_agent_runtime._product_intelligence_autoload_arg` 在无显式策略时改为 hermetic `False`；LangGraph Research Lead 的显式 enable/disable 路径保持不变。
2. 增加 repo 工作目录与空目录的相同输入 digest 证明，并验证显式生产 autoload 仍可读取 Product Intelligence pack。
3. 新增代表节点程序：消费九个 S2-01 request，校验 alias-only Provider output，本地物化 9 个 Claim，并按 DELL/MU/NVDA 各合成一个 Lead 结果。
4. Claim、execution、Lead 均绑定 request、S1 query、Provider output 与自身 digest；跨案 alias、自由文本、autoload、Claim digest mutation 均 fail closed。
5. 在任何模型调用前预注册三 family canary：DELL demand、MU value/profit、NVDA bottleneck 各一次；最多 3 calls，0 retry，0 fallback，首个硬失败即停，不跨 request 平均分。

## 结果与证据

- 原 Specialist 套件：`60 passed / 3 failed` → `63 passed`。
- S2-02＋相邻 autoload/Product Spec/portfolio 回归：`112 passed`。
- FIN 0.1.3 canonical active suite：`161 passed / 1 historical event-time assertion deselected`。
- 节点拓扑：`9 Specialist / 9 Claim / 3 Lead`。
- 本项模型、Provider、网络、来源、业务运行：`0 / 0 / 0 / 0 / 0`。

关键文件：

- `src/sec_agent/multi_agent_runtime.py`
- `src/sec_agent/s2_representative_node_program.py`
- `configs/runtime/fin_ia_0_1_3_repair_closeout_s2_representative_node_and_natural_canary_policy_v1_0.json`
- `configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_representative_node_context_precedence_and_canary_entry_v1_0.json`
- `tests/contract/test_fin_0_1_3_repair_closeout_s2_02_representative_node_and_context_precedence.py`

## 边界与下一步

这一步证明的是 `runtime_injected + node_level_consumed`，不是自然模型输出质量，更不是最终报告研究质量。下一步只签发 clean-head 三 family natural canary admission；执行后按预注册 Rubric 区分模型能力、合同限制或上下文缺陷。S2-03 的 context economy、S3 动态 DecisionSurface 和八维研究质量仍不得提前宣称完成。
