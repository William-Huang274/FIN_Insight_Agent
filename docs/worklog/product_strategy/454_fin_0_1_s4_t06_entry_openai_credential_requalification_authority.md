# 454｜FIN 0.1 S4-T06 入口 OpenAI credential requalification authority

日期：2026-07-28

## 结论

用户授权执行 credential requalification authority decision。新 OpenAI Key 已通过安全 Platform 流程创建，并替换仓库忽略的 `.env` 中 `OPENAI_API_KEY`；本轮只验证存在性与 Git 边界，没有读取、输出或持久化 Key 值，也没有调用 Provider。

下一步被缩小为一次只读 Models API 元数据探针，而不是直接重跑昂贵的 strict-schema canary。

## 新凭据本地边界

- Key name：`Codex`；
- organization：`Personal`；
- project：`Default project`；
- local env：`OPENAI_API_KEY`；
- `.env`：existing、Git untracked、Git ignored；
- usable shape：present；
- temporary key material：removed；
- authentication/model visibility：尚未验证。

旧 canary `fin01-s4-t06-entry-openai-strict-schema-dell-demand-r1` 保持 consumed，不可重放。聊天中曾暴露的旧 Key 仍建议在 Platform 撤销。

## 授权的 future probe

- probe ID：`fin01-s4-t06-entry-openai-credential-gpt-5p6-sol-model-metadata-r1`；
- method/endpoint：`GET /v1/models/gpt-5.6-sol`；
- network/transport ceiling：`1/1`；
- timeout：30 秒；
- retry/fallback/provider hopping：0/false；
- inference/semantic/Responses/Chat Completions：全部 0；
- tokens/cost：`0 / USD 0`；
- WorkUnit/Attempt/Run/business Artifact：全部 0。

成功只能证明：

1. 新凭据通过认证；
2. 当前 project 可见 exact model ID `gpt-5.6-sol`。

成功不能证明 Responses exact schema、strict parse、local validator、研究质量或 T06 entry。失败则记录脱敏 HTTP/failure class 后停止，不自动换 Key、第二探针或新 canary。

## 当前状态

RC-P36-071 更新为 `credential_requalification_probe_authorized_not_started`。RC-P36-070 的 static/fixture proof 保持，但 live endpoint 仍未到达；RC-P36-067 仍等待 live semantic requalification。

T05 仍 blocked/not passed/not owner accepted，DELL R2 未证明，T06 尚未进入，S5/release/production blocked。

下一项：

`S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFICATION-EXACT-ONCE-METADATA-PROBE`

该下一项已获 authority，但尚未执行。

## 验证

- authority、历史 401 closeout 与 canary authority 单向迁移：`11 passed`；
- 下一 metadata-probe scope Project OS preflight：`pass / open blocker=0`；
- JSON/JSONL duplicate-key parse、Python compile、current-artifact secret scan、`git diff --check`：pass。

## Git

工作树在本轮前已有大量 mixed staged/unstaged/untracked 历史变更。本轮保留这些状态，不 stage、不 commit；`.env` 不进入 Git。
