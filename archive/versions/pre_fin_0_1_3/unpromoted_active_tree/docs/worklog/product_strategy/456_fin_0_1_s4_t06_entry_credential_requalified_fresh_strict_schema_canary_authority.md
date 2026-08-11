# 456｜FIN 0.1 S4-T06 入口 credential-requalified fresh strict-schema canary authority

日期：2026-07-28

## 结论

用户以“继续”授权执行 metadata probe 成功后的下一项 zero-call authority decision。现已签发一个全新、不可与旧身份混用的 strict-schema canary：

`fin01-s4-t06-entry-openai-strict-schema-dell-demand-credential-requalified-r1`

本轮没有调用模型、Provider 或 execution network。canary 已授权，但尚未执行或消费。

## 为什么需要新执行入口

旧 runner 将已消费 canary 的 ID、authority digest 和 result path 写死，不能安全用于新凭据后的 canary。为避免下一轮在 Provider call 前返工：

- base runner 只做 backward-compatible constant parameterization；
- 新增独立 bound runner，绑定新 authority、metadata result、旧 result immutable evidence、新 canary ID 和新 result ref；
- 共享 runtime、truth kernel、server schema、prompt 和 local validator 均未修改；
- 旧 canary 保持 consumed，不可重放。

## 冻结请求与预算

- case/cell：DELL / `demand_authenticity_and_sustainability`；
- surface：`facts_explanation_and_terminal`；
- endpoint/model：OpenAI `/responses` / `gpt-5.6-sol`；
- request template SHA：`b92911d0bb9755c3e46fc0d4cac87cb0d07486d8fba8177ca69f2785ee443d7e`；
- server schema SHA：`24cdd015fd3c6b393c1d1013ffa065eb0a2a266c691720e981c01e6db9004938`；
- semantic/provider/network/transport ceiling：`1/1/1/1`；
- output ceiling：512 tokens；
- cost ceiling：USD 0.05；
- retry/fallback/provider hopping/full-chain：0/false；
- WorkUnit/Attempt/Run/business Artifact：全部 0。

## 零调用证据

- Project OS authority scope：pass，open blocker=0；
- credential presence-only：true，值未读取/输出/持久化；
- metadata result：HTTP 200 + exact model ID match，digest 不变；
- fresh result：absent；
- current request derivation：全部 digest 与 frozen request 一致；
- bound runner zero-call preflight：pass；
- actual model/provider/execution network：`0/0/0`。

## 阶段边界

成功只能证明 `/responses` 接受 exact schema、strict parse 成功且 atoms 能通过本地 semantic validation/rendering；成功也不自动进入 T06。

失败则首错终止，禁止 retry、第三 canary、自动 repair、provider hopping、full-chain 或 DELL R12。

当前：

- RC-P36-071：closed；
- RC-P36-070：fresh canary authorized/not started；
- T05：blocked/not owner accepted；
- DELL R2：未证明；
- T06：尚未进入；
- S5/release/production：blocked。

下一项已授权：

`S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFIED-FRESH-STRICT-SCHEMA-CANARY-EXACT-ONCE-EXECUTION`

## 文件

- authority：`configs/releases/fin_ia_0_1_s4_t06_entry_openai_credential_requalified_fresh_strict_schema_canary_authority_decision_v1_0.json`；
- authority SHA256：`bb9df485efda0ffacd6ed2a6b496470bca0ed6cb7e56356e7184a9615a1ef27d`；
- runner：`scripts/releases/run_fin_ia_0_1_s4_t06_entry_credential_requalified_strict_schema_canary.py`；
- base runner：`scripts/releases/run_fin_ia_0_1_s4_t06_entry_single_node_strict_schema_canary.py`。

## 验证

- fresh authority、bound runner、旧 canary/HTTP 401 与 credential metadata 单向迁移：`21 passed`；
- 下一 exact-once execution scope Project OS preflight：`pass / open blocker=0`；
- JSON/JSONL duplicate-key parse、Python compile、secret scan、`git diff --check`：pass（ledger 仅有既存 CRLF warning）。

## Git

工作树已有大量 mixed staged/unstaged/untracked 历史变更。本轮保持同一 release slice，不清理、不 stage、不 commit；`.env` 继续 ignored/untracked。
