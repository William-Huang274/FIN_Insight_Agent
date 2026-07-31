# 455｜FIN 0.1 S4-T06 入口 OpenAI credential requalification metadata probe 成功

日期：2026-07-28

## 结论

用户以“继续”授权执行上一项已经签发的 exact-once metadata probe。全部零调用前置条件通过后，唯一一次 `GET /v1/models/gpt-5.6-sol` 返回 HTTP 200，响应为 JSON object，且 model ID 精确等于 `gpt-5.6-sol`。

因此新 `OPENAI_API_KEY` 已证明：

1. OpenAI API authentication accepted；
2. 当前 project 可见 exact model `gpt-5.6-sol`。

RC-P36-071 可按该有限证据关闭。该结果不证明 `/responses` 接受当前 strict schema，也不证明 strict parse、本地 semantic validator、研究质量或 T06 entry。

## 执行合同与实际计数

- probe ID：`fin01-s4-t06-entry-openai-credential-gpt-5p6-sol-model-metadata-r1`；
- method/endpoint：`GET /v1/models/gpt-5.6-sol`；
- terminal：`succeeded`；
- network/transport attempts：`1/1`；
- retry：0；
- inference/semantic/Responses/Chat：全部 0；
- input/output/total tokens：`0/0/0`；
- cost：USD 0；
- WorkUnit/Attempt/Run/business Artifact：全部 0；
- latency：1744.43 ms。

未持久化 raw response、credential、Authorization header、organization/project ID、stack trace 或模型输出。

## 阶段边界

- T05：仍为 blocked/not passed/not owner accepted；
- DELL R2：未证明；
- T06：尚未进入；
- S5/release/production：继续 blocked；
- 旧 canary：保持 consumed，不可重放；
- DELL R12：继续禁止。

RC-P36-070 的 static/fixture/documented-request proof 保留，但 live `/responses` schema endpoint 仍未证明。下一步只能另行决定是否授权一个全新 canary ID 和 result ref：

`S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFIED-FRESH-STRICT-SCHEMA-CANARY-AUTHORITY-DECISION`

本轮没有授权或执行该 canary。

## 持久化证据

- result：`configs/releases/fin_ia_0_1_s4_t06_entry_openai_credential_requalification_exact_once_metadata_probe_result_v1_0.json`；
- result SHA256：`ba1368b9ab3cba319f89e6de96f2d3949a5a59b86b87c6471b013dc2d874766c`；
- source authority：`configs/releases/fin_ia_0_1_s4_t06_entry_openai_credential_requalification_authority_decision_v1_0.json`。

## 验证

- metadata result、credential authority、历史 HTTP 401 closeout 与旧 canary authority 单向迁移：`14 passed`；
- 下一 zero-call authority scope Project OS preflight：`pass / open blocker=0`；
- JSON/JSONL duplicate-key parse、Python compile、result secret scan、`git diff --check`：pass（ledger 仅有既存 CRLF warning）。

## Git

工作树在本轮前已有大量 mixed staged/unstaged/untracked 历史变更。本轮仅追加本次结果和状态迁移，不清理、不 stage、不 commit；`.env` 继续保持 ignored/untracked。
