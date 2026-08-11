# FIN 0.1.3 S1-08 腾讯云 WSA Query-only R2 签名失败终态

日期：2026-08-08

阶段：`013-S1-08`

## 1. Exact-live 结果

clean/synced `ff25e92fbf5d0813ea4ab6f0dde1def73e881c8b` 上，唯一 R2 authority exact-once 消费：

| 项目 | 结果 |
| --- | --- |
| request body | 仅 `Query` |
| optional fields | 8 个全部省略 |
| provider / network | `1 / 1` |
| retry / model / document / Evidence | `0 / 0 / 0 / 0` |
| elapsed | `129 ms` |
| terminal | `failed / tencent_wsa_query_only_typed_failure` |
| Tencent error | `AuthFailure.SignatureFailure` |
| RequestId | 已保存 |
| locator / date | `0 / 0` |
| credential persisted | `false` |

第一次启动交互 runner 时，Windows Store `pwsh.exe` 在创建进程前被系统拒绝；没有 Python runner、safe request、provider 或 network。随后改用系统 PowerShell 启动同一命令，才形成上述唯一正式 Attempt。该启动环境失败不计 API 重试。

## 2. 原因分型

R1 的 `Mode=0` 问题没有复发：safe capture、terminal 和 SDK request 共用同一个 Query-only 编译对象。腾讯在 SearchPro 业务参数校验前就拒绝 TC3 签名，因此本轮不能判断 CAM、服务是否开通、资源是否可用或搜索质量。

当前没有证据证明 successor 的签名算法回归：R2 与 R1 使用同一官方 SDK `3.1.152`、`wsa.tencentcloudapi.com`、TC3 sign method、empty region 与 client profile；R1 用前一组凭据曾经到达 `illegal Mode` 业务参数校验。腾讯官方签名文档说明 `AuthFailure.SignatureFailure` 可能来自签名与实际内容不一致或 SecretKey 错误；本轮实际内容由 SDK 自己序列化并签名，所以优先怀疑：

1. 从截图人工输入时，大小写或 `I/l/O/0` 至少有一处歧义；
2. 新 SecretId/SecretKey 不是活跃匹配对或随后被禁用；
3. 其他凭据侧问题。

这些都是最可能解释，不是已经证明的根因；没有执行第二次请求来验证。

## 3. 两种认证不是一回事

- 截图中的 `SecretId/SecretKey` 是腾讯云标准 AK/SK，走 TC3 与 `wsa.tencentcloudapi.com`；
- WSA service API Key 是产品控制台单独签发的 Bearer token，走 `api.wsa.cloud.tencent.com/SearchPro`；
- 两种方式不能混用，也不能在一次 Attempt 内自动 fallback。

官方参考：

- <https://cloud.tencent.com/document/product/1806/130616>
- <https://cloud.tencent.com/document/product/1806/130615>
- <https://cloud.tencent.com/document/product/1806/121811>
- <https://cloud.tencent.com/document/product/590/73730>

## 4. 处置

R2 immutable、authority consumed、0 retry。当前不授权第三次请求、三案 comparator、SourceHunter integration 或 production。

下一步先删除已经在聊天截图中暴露的新 Key。若继续，优先避免截图抄录：由用户精确复制新 AK/SK 并通过本地隐藏输入交付；或者改为 WSA service API Key，但必须先做独立零调用 profile/transport 资格审查。两条路线均需新的 Owner 决定和 authority。
