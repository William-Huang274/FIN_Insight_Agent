# FIN 0.1.3 S1-08：腾讯 fresh credential 与关系感知同矩阵 comparator 零调用实现

日期：2026-08-08

## 结论

Windows 用户环境和当前 Codex 进程均检测到 `TENCENTCLOUD_SECRET_ID`、`TENCENTCLOUD_SECRET_KEY`；只判断是否存在，没有打印、散列、记录或回写值。按用户完成轮换后配置新凭据的上下文，选择腾讯 WSA `semantic_open_web` 24-query successor。该选择不重跑旧腾讯 comparator：旧结果使用修复前的 subject＋generic-slot 查询；本轮首次让腾讯消费与 Firecrawl R1 完全相同的 relationship-aware 24-query 矩阵。

本项只完成 decision、runner/evaluator、wire parity 和 full-fake/mutation 零调用实现，尚未签发或执行网络请求。

## 工程实现

- 复用 immutable Firecrawl 24-query plan 的 `intent_id/digest`、query text、owner、slot、direction 和 evaluator-only Gold；
- 重新从 canonical SearchIntent 和 ProviderWireProjection 编译 Tencent semantic units，证明 24/24 query text 完全一致，wire body 只有 `Query`；
- runtime 只从环境变量读取 AK/SK，safe request、raw response/failure、call terminal 和 aggregate terminal 均不得含凭据；
- `AuthFailure`、未授权、资源未开通／不可用和限流属于 systemic stop：当前调用保存 typed failure，剩余 identity 无网络终态化；
- 每个 identity 最多一次 Provider/network attempt，0 retry/model/document/Evidence/reranker；
- 复用冻结的 Firecrawl 共同指标计算 useful@10、target-in-pool、日期、来源多样性和 p50/p95，再叠加腾讯 `Version=standard` 与 1.104 元成本门；
- comparator pass 只允许进入独立 SourceHunter adapter integration authority 决策，不直接接入、不晋升 Evidence。

## 官方合同复核

腾讯 2026-06-30 更新的官方 API 文档仍定义：endpoint=`wsa.tencentcloudapi.com`、Action=`SearchPro`、Version=`2025-05-08`、必填字段仅 `Query`；返回 `Pages` JSON 字符串数组与 `Version/RequestId`，page 包含 `title/date/url/passage/site/score`。标准版按量价格仍为 46 元／千次，因此 24 次 ceiling 的文档价为 1.104 元。实现不发送 `Mode/Site/FromTime/ToTime/Cnt/Industry/Freshness/Deeplinks`。

## 零调用验证

- 凭据 presence=`2/2`，value output/persistence=`0`；
- Tencent/Firecrawl semantic query parity=`24/24`；
- Tencent request body fields=`Query only`；
- focused full-fake/mutation=`7 passed`；
- provider/network/model/document/Evidence=`0/0/0/0/0`；
- precise units=`0`，combined 46-unit run=`not authorized`。

## 当前边界与下一项

当前状态是 `zero_call_engineering_pass / clean authority pending`。这不证明新凭据有效、套餐为 standard、腾讯召回优于 Firecrawl、日期准确、SourceHunter 可接入或研究报告质量通过。

下一项仅为：

`S1_08_TENCENT_RELATIONSHIP_AWARE_SEMANTIC_SAME_MATRIX_CLEAN_AUTHORITY_ISSUANCE`

必须先通过专项、S1-08 回归、Project OS scoped preflight、secret scan 和 clean commit/push；之后才可签发一份 24-call ceiling、0 retry 的 exact-live authority。
