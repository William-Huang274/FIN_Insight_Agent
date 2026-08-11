# FIN 0.1.3 S1-08 腾讯云 WSA R1 `illegal Mode` 终态

日期：2026-08-08

阶段：`013-S1-08`

## 1. 实际运行结果

干净提交 `0b4d2eb842100a545592c5c2457a54fd3b012a48` 上，唯一 authority exact-once 消费：

| 项目 | 结果 |
| --- | --- |
| query | 固定 DELL semantic query |
| provider / network | `1 / 1` |
| retry / model / document / Evidence | `0 / 0 / 0 / 0` |
| elapsed | `276 ms` |
| terminal | `failed / tencent_wsa_single_call_typed_failure` |
| Tencent error | `InvalidParameter / illegal Mode` |
| locator / date | `0 / 0` |
| credential persisted | `false` |

safe request、raw failure 和 terminal 均在 `.codex_runtime` 或 tracked credential-free result 中留存。SecretId、SecretKey、签名与 Authorization 没有进入任何版本化文件；generic secret scan 无命中。

## 2. 原因

腾讯官方 SearchPro 文档与服务 API Key 文档都将 `Mode=0` 定义为“自然检索结果（默认）”。官方 SDK `3.1.152` 的离线序列化确认显式 integer 0 会成为 `"Mode": 0`。真实 API 却对这一值返回 `illegal Mode`，并生成 RequestId。

因此这是一个双边合同问题：

- 外部：腾讯官方文档与 live 服务对显式 `Mode=0` 的行为不一致；
- 项目内：首个 provider-specific compiler 不应为了表达“默认值”而显式发送可选字段；最兼容的最小请求应只有 `Query`。

这不是 DELL 查询内容、搜索质量、DeepSeek、RAG、reranker 或研究能力失败。请求到达业务参数校验层，说明签名／CAM 大概率已经通过；但参数先失败，因此仍不能证明 WSA 服务资源已开通或可用。

## 3. 为什么没有继续跑

R1 authority 明确是 1 call、0 retry，任何失败都 terminal。项目没有把“去掉一个字段再试”伪装成同一次运行，也没有自动追加第二次付费请求。官方计费文档称失败服务调用不计费，但本项目没有读取账单，实际费用仍以腾讯云账单为准。

## 4. 下一步建议

若 Owner 希望继续，应先轮换已经在聊天中明文出现的 AK/SK，然后单独批准一个 replacement Attempt：

1. request body 只含 `Query`；
2. 不传 `Mode` 及任何其他 optional field；
3. 仍为 1 call、0 retry、0 model、0 document、0 Evidence；
4. 如果再次失败，直接停止并按新错误决定是服务开通、CAM、资源还是 Provider 问题；
5. 只有成功返回 `Pages` 后，才评价 locator/date/source quality；不能提前签三案 comparator。

当前 R1 immutable；Tencent WSA production、三案 comparator、SourceHunter integration、DELL R4、ranking、MU/NVDA、S3 和 release 均未授权。
