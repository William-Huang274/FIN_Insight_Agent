# 462｜FIN 0.1 S4-T06 入口 Sub2API public diagnostic runner 与 preflight

日期：2026-07-29

## 结果

用户授权完成零调用实现后执行一次真实 diagnostic。本项先完成实现与 preflight，没有访问 Sub2API。

新增隔离 runner：

`scripts/releases/run_fin_ia_0_1_s4_t06_entry_sub2api_public_nonsensitive_diagnostic_canary.py`

runner 不复用历史 official OpenAI runner，不读取环境变量、`.env`、OpenAI key 或 Sub2API key。它精确绑定：

- `http://43.135.174.27:8080/responses`；
- `gpt-5.5` / Responses；
- 无 Authorization/Bearer；
- 固定 actor client marker；
- fully synthetic strict JSON Schema request；
- 1 request、128 output tokens、30 seconds、retry=0；
- direct no-proxy、redirect forbidden；
- exclusive result creation；
- 只持久化 sanitized status、digest、usage、latency 和 content-free shape。

## 验证

- focused authority＋runner contracts：`9 passed`；
- Python syntax：pass；
- zero-call CLI preflight：pass；
- request body SHA-256：`46d15213...36c06`；
- strict schema SHA-256：`041d8306...d76d9`；
- result ref：absent；
- model/provider/network/transport=`0/0/0/0`；
- credential read/write=`0/0`。

## 下一项

`S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-CANARY-EXACT-ONCE-EXECUTION`

已获用户授权但尚未开始。执行前仍需 Project OS exact-scope preflight。无论结果如何只请求一次，不 retry、不 repair、不切换 Provider；结果不能关闭 plain HTTP blocker 或进入 T06。

## Git

仓库仍处于历史 mixed staged/unstaged/untracked 状态；本项不清理、不 stage、不 commit。
