# 463｜FIN 0.1 S4-T06 入口 Sub2API public diagnostic HTTP 401 终态

日期：2026-07-29

## 真实结果

在 authority、隔离 runner、focused tests、zero-call CLI preflight 和 Project OS exact-execution scope preflight 全部通过后，执行了唯一一次真实 synthetic diagnostic。

终态：

- route：`http://43.135.174.27:8080/responses`；
- model alias：`gpt-5.5`；
- HTTP：`401`；
- status：`terminal_failed_no_retry`；
- latency：`321 ms`；
- request / Provider / network / transport attempts：`1/1/1/1`；
- input / output / total tokens：`0/0/0`；
- retry / provider hopping / automatic repair：`0/0/0`；
- credential read/write：`0/0`；
- WorkUnit / Attempt / Run / Artifact / business write：`0`。

exact-once identity 已消费，不可重放。

## 解释

HTTP 401 在 generation 前发生。模型输出、response status、strict-schema parse 和 exact-value validator 均未到达，因此：

- 不能归因于模型不遵循指令；
- 不能评价 `gpt-5.5` 是否支持该 strict schema；
- 不能证明或否定研究质量；
- 不能进入 T06。

已发送截图提供的 no-Bearer API Key Mode route 和固定 client marker，但服务端仍拒绝独立客户端。当前证据只能说明截图连接信息不足以建立 FIN Insight raw client 的访问资格；可能还需要未公开的客户端注册、会话、额外认证或服务端 allowlist，具体 subtype 未知。

## 数据边界

结果文件只保存 HTTP/status、request digests、usage、latency 和 content-free shape。未保存 raw response、provider output、headers、marker value、stack、private reasoning、credential 或公司/金融内容。

RC-P36-074 的 plain HTTP mainline blocker 不变。新增访问控制边界 RC-P36-075，下一项只能进行零调用 program disposition；不自动尝试第二个 header、key、兼容模式、Provider 或请求。

## 验证

- 全部 S4-T06 contract tests：`93 passed`；
- Project OS post-result disposition exact scope preflight：pass，open blocker=`0`；
- result SHA-256：`aaba2e03...2d301`；
- JSON/JSONL syntax 与 duplicate-key：pass；
- Python syntax、secret-pattern 和 scoped diff：pass；
- 本轮真实请求总数保持 `1`，没有第二次执行。

## Git

历史 mixed worktree 保持不变；不清理、不 stage、不 commit。
