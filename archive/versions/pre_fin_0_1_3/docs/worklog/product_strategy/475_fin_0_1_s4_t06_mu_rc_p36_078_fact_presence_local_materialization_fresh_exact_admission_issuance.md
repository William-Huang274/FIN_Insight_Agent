# FIN 0.1 S4-T06 MU RC-P36-078 fresh exact admission issuance

日期：2026-07-29<br>
状态：R2 admission 已签发、未消费；exact-live authority decision 待执行<br>
当前下一项：`S4-T06-MU-RESEARCH-LEAD-CONFLICT-FACT-PRESENCE-LOCAL-MATERIALIZATION-R2-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT-AUTHORITY-DECISION`

## 本轮边界

用户在 fresh-agent proof 已冻结且下一项明确为 admission issuance 时说“继续”。本轮只允许把 proof 中冻结的 MU R2 admission 原样物化，并证明真实 runner 可加载且 identity 仍 fresh；不允许消费 admission、启动 supervision、调用 DeepSeek、生成业务 Artifact、执行 paired assessment、进入 T07 或恢复 strict-schema transport。

## 实现

新增签发器：

- `scripts/releases/issue_fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_materialization_fresh_exact_admission.py`

签发器先验证 admission 与 issuance 均不存在，再完成：

1. 校验 frozen proof SHA，并重新运行 `build_decision()`；
2. 校验 prospective payload、canonical digest 与 JSON round-trip；
3. 校验 MU、DeepSeek Pro、beta endpoint、Lead-v7、Specialist-v7、retry=0 和禁止 source/tool/live-head write；
4. 校验 fact-presence local-materialization policy；
5. 用 forbidden Provider callback 构造 executor 并确认调用为 0；
6. 校验 fresh R2 identity 不存在、已消费失败 R1 保持不变；
7. 校验六项 code binding 和目标 SQLite/object/logical state；
8. 原子写入临时 admission/issuance，真实 runner load 通过后再替换正式文件；
9. 写盘后重新验证 admission 未消费、execution 未开始。

fresh-proof 测试也调整为 issuance-aware：历史 proof 仍必须声明当时 prospective file absent；若 admission 后续已签发，则校验其 bytes 与 frozen payload 完全相同。

## 冻结结果

- admission ID：`fin01-s4-t06-mu-research-lead-fact-presence-local-materialization-fresh-exact-admission-r2`
- WorkUnit：`wu_p02_5_43322e55457b647277d2297a`
- Attempt：`attempt_fin01_217f2f2aaaa051080a540f2a`
- ResearchRun：`research_run_fin01_1920b03b8205e9861dfb5676`
- admission digest：`55fb08cac25b3a03109b13ae645d858b90b2074873f5355e6ed47ac93c6cd65c`
- admission SHA256：`da4be08131d1115507e3fb0ad440d26a2e17d8fdc42a8e3479a061dea5aee365`
- issuance SHA256：`0323a74dee570566a2294ddbbd6c7904576a72c70a43717b1517db0af12ee1dc`
- issuer SHA256：`780fbdd1b695914080c4ad14122edf748edceeda3a7ee30d3b64134805a4f945`

签发状态为 `issued=true / consumed=false / execution=false`。新增 admission=1；WorkUnit、Attempt、ResearchRun、Artifact、model、Provider、network、source、tool、paired 和 Human 均为 0。目标 SQLite、object tree 和 logical snapshot 不变。

## 验证

- 发行物 JSON：有效
- focused issuance + fresh proof：`11 passed`
- 完整 S4-T06：`161 passed`
- compile：`pass`
- 下一 authority scope Project OS preflight：`pass / open blockers 0`
- preflight ref：`.codex_runtime/s4_t06_mu_fact_presence_local_materialization_R2_exact_live_authority_project_os_preflight.json`
- credential：未检查
- model/provider/network/source/tool：`0/0/0/0/0`

## 后续

下一项只允许零调用 exact-live authority decision。该决策需要重新验证 admission bytes、runner load、fresh identity、credential presence、retry=0、host supervision、`12/12/12 calls / 16800 output tokens / USD 0.10` envelope 和 success-only paired assessment。通过后才可另行消费一次 admission；首个可信失败必须停止，不能自动 R3。

完整回归首次出现 15 个历史 next-action compatibility 失败；它们只把 fresh admission issuance decision 注册为 DeepSeek 主线最远合法后继。更新仅把当前 R2 exact-live authority decision 登记为合法后继，并同步 RC-P36-078 当前状态与未消费断言；未修改 schema、validator、L1 gate、Provider request 或 runtime 行为。重跑后 `161 passed`。
