# FIN 0.1.3 S1-08 腾讯云 WSA 输入资格审查与单调用权限

日期：2026-08-08

阶段：`013-S1-08`

归属问题：`RC-P36-157-fin-0-1-3-s1-08-operational-provider-and-candidate-coverage-insufficient`

## 1. 用户输入与安全边界

用户提供了一组腾讯云 AK/SK，并要求先看清技术文档再测试。凭据没有写入代码、配置、工作日志、Git、request capture 或 terminal；runner 只允许在交互式隐藏输入中读取，并在进程内对错误及返回值再次执行逐值脱敏。

这组凭据已在聊天中以明文出现。无论测试成功与否，测试后都应在腾讯云控制台轮换；后续生产接入应使用最小权限子账号或服务 API Key，而不是长期复用这组通用云 API 密钥。

## 2. 官方合同核对

仅使用腾讯云官方资料完成资格审查：

- [腾讯云标准方式](https://cloud.tencent.com/document/product/1806/121802)：AK/SK、官方 Python SDK 与 `WsaClient` 示例；
- [SearchPro API](https://cloud.tencent.com/document/product/1806/121811)：endpoint、请求／响应、示例与业务错误；
- [请求结构](https://cloud.tencent.com/document/api/1806/121814)：HTTPS 与就近接入；
- [接入方式概述](https://cloud.tencent.com/document/product/1806/130616)：AK/SK 与服务 API Key 两种模式；
- [计费概述](https://cloud.tencent.com/document/product/1806/121798)：轻量／标准／尊享／旗舰按量价分别为 18／46／60／80 元每千次。

冻结合同为：

- endpoint=`wsa.tencentcloudapi.com`；
- Action=`SearchPro`；Version=`2025-05-08`；Region 不要求；
- 必填仅 `Query`；可选 `Mode/Site/FromTime/ToTime/Cnt/Industry/Freshness/Deeplinks`，其中部分参数受套餐限制；
- 返回 `Query/Pages/Version/Msg/RequestId`，`Pages` 每项为 JSON 字符串；
- 首次调用只发 `Query + Mode=0`，不发送任何套餐依赖过滤；
- 业务错误 `ResourceNotFound/ResourceUnavailable/UnauthorizedOperation` 等必须 typed terminal，禁止 retry。

官方 SDK `tencentcloud-sdk-python==3.1.152` 只安装在 `.codex_runtime/tencent-wsa-sdk`，没有加入项目生产依赖；离线 introspection 的 request/response 字段与文档一致。

## 3. 零调用工程与失败

新增候选 Provider profile、secret-safe SearchPro normalizer、candidate-only locator 边界和 exact-once runner。测试覆盖：

- URL canonicalization、duplicate、invalid JSON 与 schema drift；
- date/Version/RequestId 投影；
- locator 不能获得 Evidence、Writer、Numeric 或生产权；
- error message 含运行时凭据时必须脱敏；
- Project OS scope 注册、authority digest、profile／runner SHA 绑定；
- provider/network ceiling=`1`，retry/model/document/Evidence=`0`。

首次本地验证在 API 调用前发现两个项目缺陷：runner 引用了不存在的 preflight convenience helper；v2_202 wildcard 权限误挡历史 S0-04G 治理自检。两者已在同一 pre-transport 包中更正，失败未被解释为腾讯或搜索质量问题。最终本地验证=`19 passed`、compile pass、Project OS preflight pass，真实 API 调用仍为 `0`。

## 4. 已签发但未消费的唯一权限

authority=`fin013-s1-08-tencent-wsa-single-call-diagnostic-r1`，仅允许：

- 一个固定 DELL semantic query；
- 一次 SearchPro provider/network call；
- 0 retry、0 model、0 document fetch、0 Evidence promotion；
- 请求前保存无凭据 safe capture；
- response 或 error 到达后先保存本地 credential-free raw capture，再解析；
- 成功或失败都物化 terminal 并停止；
- 文档最高单次价格上界按旗舰版计为 `0.08 CNY`。

它回答的是“签名／权限／服务／schema／一条查询的 locator 与日期情况”，不是三案例质量 comparator。成功不会自动接入 SourceHunter，失败也不会自动补跑。

## 5. 当前下一项

在干净提交上消费这一个 authority。运行后按结果二选一：

1. 若鉴权、服务或资源失败：保留 typed terminal，停止；用户去控制台修权限／开通服务／轮换凭据，不重试；
2. 若成功：先独立评估 locator 数量、日期、issuer／主流媒体覆盖、重复率和 schema，再决定是否值得另行设计 DELL/MU/NVDA 三案 comparator。

SearXNG 不重跑；DELL R4、ranking、MU/NVDA transfer、DeepSeek、S3、Workbench 和 release 继续 blocked。
