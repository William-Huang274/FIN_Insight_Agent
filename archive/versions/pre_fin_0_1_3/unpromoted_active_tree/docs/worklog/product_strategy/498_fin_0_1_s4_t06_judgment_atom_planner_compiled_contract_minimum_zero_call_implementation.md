# FIN 0.1 S4-T06 judgment-atom planner / compiled-contract 最小零调用实现

日期：2026-07-30

## 结论

冻结的唯一结构包 `fin01.s4.deterministic_judgment_atom_planner_and_compiled_contract_invariants:v1` 已注入共享 Runtime，并通过 DELL、MU、NVDA 三案例完整 fake 链与 mutation/fault-injection 证明。

本项只证明代码与确定性 fixture。它不是独立 fresh-agent proof，不是 DeepSeek 自然输出 canary，不是新 admission、正式 exact-live、paired assessment 或 owner acceptance。MU R6 正式失败保持不可变，诊断结果继续隔离且不可晋升。

## 实现范围

- Provider 的三个变更合同家族收窄为 request-local alias、有限枚举和 judgment atoms：
  - `specialist_fact_atoms`
  - `claim_candidate_atoms`
  - `what_would_change_atoms`
- 本地 Runtime 负责：
  - alias、类型和本案 scope 校验；
  - validity-aware subset selection 与稳定排序；
  -重要数值、报告期、日期、阈值、身份和最终 clause 的确定性渲染；
  -最终 task/claim/fact 结构与 lineage 组装。
- model-visible contract、wire schema、validator、fake fixture、selector、renderer、capacity、budget unit、typed failure descriptor 和 capture-safe index 从同一 typed policy 生成。
- Provider wire 的 `4,800 bytes` 上限与本地渲染的 `2,048 chars/item` 上限分离，不再把 Provider narrative 限制错误继承给本地确定性结构。
- projected input cost 使用明确标注的 token estimate；实际调用后的 usage hard cap 保持不变，UTF-8 bytes 不再直接当作计费 token。
- post-Provider 失败仍先保留 capture；R6 capture-v2 缓存输出不能冒充新 atom wire。

## 验证

- implementation + disposition：`17 passed`
- DELL / MU / NVDA：各 `6 nodes / 12 callbacks / 12 captures / 9 Artifacts`
- mutation/property：
  - unknown、cross-case、wrong-kind alias fail-closed；
  -任意 Provider narrative extra field fail-closed；
  -重要数值只能由绑定 alias 本地渲染；
  - mixed-scope 高优先候选先拒绝，再选择低优先合法候选；
  -候选排列不改变最终选择；
  -未知日期 alias fail-closed；
  -多字节 prompt 不再按 UTF-8 byte 数直接计价；
  - post-Provider fault 保留 capture；
  - R6 capture-v2 replay 被新 wire 拒绝。
- 邻接历史回归：`45 passed / 1 failed`。唯一失败是历史阶段快照测试的 `current_next` allowlist 未包含本次新阶段名；未建立 Runtime 行为回归，也没有改写历史快照。
- `py_compile`：pass
- `git diff --check`：pass
- `ruff`：当前 workspace runtime 未安装
- Project OS postflight：`pass / open blockers 0`
  - `.codex_runtime/s4_t06_mu_judgment_atom_compiled_contract_implementation_postflight.json`

## 运行与权限边界

本项 model / Provider / network / source / external tool 调用均为 0；新 admission、正式 exact-live、业务 Artifact 晋升、paired assessment、owner acceptance、S4-T07 entry 均为 0。

## 下一项

`S4-T06-MU-DETERMINISTIC-JUDGMENT-ATOM-PLANNER-AND-COMPILED-CONTRACT-INVARIANT-HARDENING-FRESH-AGENT-PROOF-DECISION`

下一项应在独立 disposable Runtime 中重算当前代码绑定、MU exact input、三案 full-fake、mutation、capture/failure 语义和 prospective identity。只有该零调用 proof 通过，才可另行进入最多三个 changed-family natural-output canary；之后仍只有一次新的 MU formal exact-live 额度。
