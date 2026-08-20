# FIN 0.1.3 S3 — R11 Provider 前 projection 失败与 R12 replacement

日期：2026-08-20
状态：`R11_terminal_failure_preserved / zero_provider_calls / projection_fix_full_engineering_gate_pass / R12_commit_preflight_pending`

## 1. R11 实际执行到哪里

R11 使用 clean commit `1f03c2f9cbd3564052d1ac5de4d4304b8efa1c22`，通过 repository-aware Project OS preflight 后签发。它正确读取 R3 Specialist plan、R6 Lead plan、R8／R9 六份底稿、R9 Lead coordination、R10 downstream progress 和 Cash analysis fragment 的绑定关系，但在恢复已完成 Demand repair 时停止。

本次没有进入 Provider：

- 新模型节点：0；
- Provider attempt：0；
- analysis／submission：0／0；
- 外源网络：0；
- Candidate promotion：0；
- 产品发布：false。

因此不能把失败归因于 DeepSeek、Cash 续写、Evaluator、Writer 或研究内容质量。R11 authority 已被消费，失败结果必须不可变保留。

## 2. 精确根因

Demand repair 的持久化底稿由两类字段组成：

1. 模型在 strict Tool Call 中提交的业务字段；
2. Harness 校验后派生的 `context_digest` 和 `workpaper_digest`。

原 `validate_specialist_workpaper` 是模型提交入口，故意要求 exact field set。R11 checkpoint replay 直接把第二类派生字段也传入该入口，导致有效底稿被当成“模型多交了字段”拒绝，并以 `multi_agent_workpaper_identity_invalid` 终止。此前把现象概括为“五份 checkpoint 与六份最终底稿混用”不够精确；数量 lineage 是完整的，真正错误是模型字段与持久化绑定字段没有投影分层。

最早责任层登记为 `RC-AR-012`，归 S0 Harness checkpoint replay／projection，不归 S1、数据、网络、Agent 角色分工或 DeepSeek。

## 3. 修复与零调用证明

新增 `revalidate_bound_specialist_workpaper`：

1. 从持久化对象中暂时取出两个派生 digest；
2. 仅将模型原始字段交给现有 exact validator；
3. 使用当前绑定 context 重新生成完整对象；
4. 分别要求重新生成的 `context_digest` 与 `workpaper_digest` 等于持久化值。

R10 真实 Demand repair 已按原模型可见 context 精确回放：

- agent：`AGENT::DEMAND_QUALITY`；
- node：`AGENT::DEMAND_QUALITY::COUNTER_REPAIR`；
- workpaper digest：`3914ddf8e0fde4ba7b82933795ada3feee70701f609fce901af684dcbeaf47e0`；
- context digest：`1ddcce797a2fac8566024a3c2dd1ea1eb31c837637a3352bb7dac6d37f1f0e6b`。

业务字段改写、workpaper digest 改写和 context digest 改写均被拒绝。局部精确回放测试为 `33 passed`；包含 Preview Runtime 与 Project OS 的定向套件为 `96 passed`。

完整工程门随后通过：全仓 `887 passed`，仅保留两条既有 SWIG 弃用 warning；`compileall`、active baseline `184 Python／8 frontend／5 detectors／27 Runtime／0 forbidden`、8 份 Project OS JSONL、7,430-file secret scan 和 `git diff --check` 均通过。

## 4. R12 边界

R12 不是 R11 原地 retry。新 authority 必须绑定：

- R11 authority SHA；
- R11 public failure SHA／digest；
- R11 private terminal SHA／digest；
- 本次 pre-provider zero-call disposition；
- 原 R11 全部 research／checkpoint／profile 输入。

R12 继续禁止重跑已完成的 Specialist plan、Lead plan、六份初始底稿、Lead coordination、Demand repair 和 Cash 初始 analysis。只允许一次 Cash continuation，随后按原预算执行 Supply、最多两轮 Evaluator、最多两次 evaluator 指定局部修订和条件式 Writer。研究输入和 Provider budget 均不改变。

R12 只有在 full repository、compileall、active baseline、Project OS JSONL、secret scan、diff check、clean commit／push 和 fresh preflight 全部通过后才能签发。即使形成报告，也不自动构成 S1、S3、泛化、qualified-human、Workbench publication 或 release acceptance。
