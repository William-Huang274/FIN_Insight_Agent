# FIN 0.1 S2-T03 首阶段输出合同修复

日期：2026-07-20
状态：`fixture_proven_rerun_not_admitted`

## 目标与边界

用户授权修复 T03 第一层，即 `bounded_specialist_and_lead` 的首阶段输出合同。此次只做 repo-local 确定性修复和模拟网关回归；没有真实模型、provider、网络、外部工具、Evidence promotion、业务 Case head write、release 或 production 行为，也没有签发新 admission 或重跑失败 Run。

历史 admission `fin01-s2-t03-bounded-agent-exact-admission-v1.0` 已消费且保持不可修改。历史 canonical truth 仍是 `research_run_fin01_9239b033666398bd8dece2a5` terminal failed、0 Artifact、0 fallback、0 rerun，调用/成本仍是 `0_to_1_not_reconstructable`，本次修复不改写该事实。

## 根因复核

确定性 pre-call 诊断确认 exact input digest、单 Cell、Agent/Skill selection、retry/key/budget gates 能到达 provider 边界。DeepSeek 普通 JSON Output 只保证 JSON object，不保证嵌套字段满足本地 schema；官方说明同时要求 prompt 明确包含 JSON 指令并给出期望 JSON 示例。旧首阶段只给出 `low|medium|high`、`exact supplied id` 等伪 schema 占位符，而本地 validator 立即要求 exact enums、candidate IDs 和非空字段，因此最早 owned defect 是 provider 输出与本地强校验之间缺少可执行的版本化合同。

DeepSeek Beta strict tool calls 没有被采用，因为它会改变 base URL 和 tool-call 语义，超出历史 admission 且与当前 `external_tool_calls_allowed=false` 边界冲突。

## 修复内容

- 新增 `fin01.bounded_agent.specialist_lead_output:v2`；v1 保留作历史审计，真实 executor 在 provider 调用前拒绝 v1。
- 首阶段 prompt 改用 exact required-key/enum rules 和一份绑定实际 supplied `candidate_id` 的完整 JSON shape example。
- 本地 validator 要求 exact outer keys、contract ref、非空 thesis/counter-thesis/judgment、精确 evidence-finding keys、受限 enums 和 supplied candidate refs。
- 只允许无损结构归一化：sole wrapper 解包、enum trim/lower、单 mapping/string 包成单元素 list；不生成缺失语义、不把 `accepted` 等同义词改成 `accept`、不替换未知 candidate ID。
- provider 空输出、截断、非 stop、无效 JSON、schema/ref 失败都生成 secret-safe `failure_codes`；raw response 和 private reasoning 仍不持久化。
- manifest、trace artifact 和 specialist trace event 记录 output contract ref 与发生的无损 adaptations。

机器合同：`configs/releases/fin_ia_0_1_s2_t03_specialist_lead_output_contract_repair_v2_0.json`。

## 验证

- 首阶段 targeted deterministic regression：旧 v1 provider 前拒绝；v2 具体示例；wrapper/case/singleton 无损归一化；语义同义词 fail closed；空/截断 typed failure；secret-safe receipts。
- targeted T03：`9 passed`；内部 exact-key 收紧后，S1 主线、S2-T01/T02/T03 与 Workbench 最终联合回归：`36 passed in 35.04s`。
- 所有 provider responses 均由 monkeypatch fixture 生成。
- 真实 model/provider/network calls：0。
- 新 admission：0。
- rerun：0。

## 当前结论

第一层 owned output-contract 缺陷已修至 deterministic fixture-proven，但 T03 没有因此通过。S2-T04 继续 blocked。若要验证真实效果，必须由用户另行明确授权一个新 execution identity、exact input digest、v2 contract ref、provider/model/network/call/token/cost/secret-safe budget admission；不可复用 v1 或自动重跑。
