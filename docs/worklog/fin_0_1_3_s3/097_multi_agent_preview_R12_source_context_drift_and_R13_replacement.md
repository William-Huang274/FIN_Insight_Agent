# FIN 0.1.3 S3 — R12 source-context drift 与 R13 replacement

日期：2026-08-20
状态：`R12_terminal_failure_preserved / zero_provider_calls / exact_source_context_replay_full_engineering_gate_pass / clean_commit_preflight_pending`

## 1. R12 实际结果

R12 使用 commit `73db3778121ab2087d37c186dd608f84361e0590`，通过 fresh Project OS preflight 后签发。authority 已消费，运行在任何模型调用前以 `multi_agent_bound_workpaper_digest_invalid` 终止：

- 新模型节点：0；
- Provider attempt：0；
- analysis／submission：0／0；
- 外源网络：0；
- Candidate promotion：0；
- 产品发布：false。

R12 authority、公开结果和私有 terminal 均不可变；0 Provider attempt 不代表 authority 可以复用。

## 2. 为什么 4U 修过后仍然失败

4U 修的是“模型字段与 Harness 派生字段混在一起校验”：持久化底稿先去除 `context_digest`／`workpaper_digest`，再走模型 exact validator，最后重算两个 digest。这一修复在 R12 确实生效，旧 `multi_agent_workpaper_identity_invalid` 没有再次出现。

R12 暴露的是更深一层、不同的错误：完成节点的上下文被重新编译。R10 Demand repair 的底稿绑定了 R10 当时的 SpecialistContext；其中 FeedbackReceipt 含原 session identity、时间、challenge 和 prior workpaper。R12 恢复 payload 后，为 Demand 新建 R12 session 和 FeedbackReceipt，再拿这个新 context 校验旧底稿。新 context 本身合法，但它不是原 context，因此 workpaper digest 必然不同并正确 fail closed。

最早责任层登记为 `RC-AR-013`，归 S0 Agent Runtime checkpoint context lineage，不归 DeepSeek、S1 数据、Cash／Supply 内容、网络或 Provider transport。

## 3. 修复原则

完成节点的恢复单位改为完整不可变三元组：

1. 已验证业务 payload；
2. 原始模型可见 context；
3. request／capture／attempt／checkpoint lineage。

运行时从 R10 Demand analysis 的 `model_visible_request.json` 恢复原 system／user 消息和 SpecialistContext，验证：

- capture 为无凭据模型可见请求；
- run／attempt 与 R10 terminal receipt 一致；
- request body 的 canonical digest 等于 request digest；
- Agent、FeedbackReceipt、challenge 和 prior workpaper 与 R10 coordination checkpoint 一致；
- context digest 和最终 workpaper digest均与持久化绑定一致。

完成节点不再产生 R13 FeedbackReceipt，也不重新进入模型；Cash／Supply 等 pending 节点继续按当前 run 建立新 session。

## 4. 零调用结果和边界

定向测试 `36 passed`：原 R10 Demand context／workpaper 精确回放通过；request digest、context digest、workpaper digest mutation 均被拒绝；把完成节点改绑新 session 后重新计算 context，也会因 workpaper digest 不同而被拒绝。

本轮没有改变研究资料、Provider budget、角色顺序或完成节点内容，没有模型、网络或付费调用。完整工程门结果为：

- 综合定向：`112 passed`；
- 全仓：`890 passed`，仅两条既有 SWIG 弃用 warning；
- compileall：pass；
- active baseline：`184 Python／8 frontend／5 detectors／27 Runtime／0 forbidden`；
- JSON：728 份 configs 有效；Project OS：8 份 JSONL／820 行有效；
- secret scan：7,434 files／0 finding；
- `git diff --check`：pass。

下一步只剩 clean commit／push 和 fresh preflight，之后才可签发一次 R13 replacement。

R13 若执行，仍只延续当前 DELL bounded Preview。它不自动证明 S1、S3、跨案例泛化、qualified-human、Workbench publication 或 release。
