# 755 — FIN 0.1.3 S1-08 DeepSeek query-atom canary clean authority

日期：2026-08-09

## 决策

raw/local A/B 与 query-atom exact-once Runtime 已在 clean/synced implementation commit `cca1490f57f8b82f36b0bf677e3a4b7ff8c152d4` 上复核。零调用 implementation proof digest=`12867a30560c2c1788f45d3318ce61a654fb43c95e6ebd151184b41c598f16c5`；因此签发一次自然 DeepSeek Pro 查询原子观察权限。

## 唯一允许的动作

- 18 个英文 typed plan 组成一个 batch；
- DeepSeek `deepseek-v4-pro` 最多 1 次 Provider call／1 次 transport attempt；
- 最多 18 atom、每 plan 最多 1 个；允许 `atoms=[]`；
- 0 retry、0 fallback、0 document fetch、0 retrieval、0 embedding、0 rerank、0 Evidence promotion；
- fresh admission、shared exact-once ledger、完整模型可见 request 与 assistant/gateway capture；
- 凭据、Authorization/Cookie 与私有 reasoning 不保存；
- 有效或空输出只进入本地 compiler 和三路评估；非法输出 terminal fail/no-retry；
- 不自动启用 model-assisted variant，不自动进入 external combined live 或 internal retrieval。

authority decision digest=`6469a67a27e521f1905deb848a5e43a9903aa918f56393e2ab4d589a705453d0`。本决策自身真实 provider/network/model 调用=`0/0/0`。

authority、Project OS scope 迁移及历史 scope fail-closed 回归合计 S1-08=`255 passed`。

## 下一步

Project OS 只切换到 `S1_08_QUERY_FACET_DEEPSEEK_ATOM_CANARY_EXACT_LIVE_EXECUTION`。先 issue 一份短时 fresh admission，再消费一次并保存终态；随后把自然 atom 重新编译进第三路 evaluation。combined live、内源 exact/BM25/dense/graph、qrels/candidate ceiling 与 BGE/fusion/rerank 均未授权，但仍按已登记顺序接力。

## Replacement authority after portable admission repair

A1 在 Provider 前暴露 Windows 文件名缺陷后，旧 authority 因 runner SHA 变化失效。portable repair 与 replacement proof 已在 clean/synced `a852bbbda3c71b441c3f8253568245f422984dc2` 上重新绑定；replacement authority digest=`360ec6c4c7c2a83e21b9d388159c06414ec8709cfe45b2422fcbb8cd636a1b55`，replacement proof digest=`897191599b93429dd50fc3201cbeeccea20eb1f509106883e6d0ab06f778bafc`。授权边界不变：只允许新 A2、一次 batch、0 retry/fallback，不复用 A1，不自动激活模型或进入 combined live。
