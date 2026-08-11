# 703 — FIN 0.1.3 S1-08 DELL current-search R1 终态与 discovery 根因

日期：2026-08-07
阶段：`013-S1-08`
状态：`R1 immutable failed / zero-call structural repair required / replacement not authorized`

## 1. 执行事实

clean/synced `09387ebd2714d61f0fb47268ef8f04d643689427` 上，相关回归 `37 passed`、candidate materializer byte-identical、scoped Project OS preflight=`pass / open blocker 0`，当前进程 SEC contact 格式有效且明文未回显。正式 runner 随后在进程内签发一份 fresh admission 并 exact-once 消费：

- Run=`fin013_s1_08_dell_search_run_8f988480b011d51b7172`；
- Attempt=`fin013_s1_08_dell_search_attempt_2826a701a3eee8e173cc`；
- admission digest=`d1b8c229...06e68`；
- `2026-08-07T15:38:55Z → 15:42:27Z`，elapsed=`212 s`；
- network/model/provider/retry=`19/0/0/0`；
- terminal=`failed / candidate_generation / unexpected_project_failure:RemoteDisconnected`；
- terminal digest=`9a528453...2d57b`；
- result canonical JSON digest=`b6d14578...822ce`；不使用受 CRLF/LF 影响的文件字节 SHA。

结果为 `configs/releases/fin_ia_0_1_3_s1_08_dell_current_search_canary_result_v1_0.json`。文件中 `@` 字符为 0；runtime contact 未进入 result/admission/普通 telemetry。shared ledger 已 terminal，R1 不得重放。

## 2. capture-first 审计

受限 runtime 共保留 50 个对象：

- source request=`19`；
- source response=`15`；
- typed source transport failure=`3`；
- parser capture=`13`；
- 最后一个 Microsoft Surface 文档请求只有 request capture，`RemoteDisconnected` 未被 transport 包装，故没有对应 failure capture。

正式 `candidate_result` 未形成，因此输出中的 candidate/gap 均不能解释为“真实为 0”。raw capture 只能用于审计，不能自动晋升 Evidence。

## 3. 共同根因

这不是 DeepSeek 或 Provider 问题，也不只是一个偶发网站断连。

1. **transport exception taxonomy 不完整**：`UrllibOfficialSourceTransport` 只捕获 HTTP/URL/timeout 边界，`http.client.RemoteDisconnected` 直接越过 capture client，导致 request-only 审计缺口。
2. **locator quality/currentness 不足**：IR landing 的通用 anchor scorer 把 Outlook、Microsoft Store、Surface、diversity、corporate policy 等导航链接当候选文档；SEC submissions 选择了 DELL 2022/2023 filing，未按 publication date 与 current as-of 优先。
3. **partial candidate terminalization 不完整**：前 18 次调用已有 response/failure/parser 证据，但整案异常使 partial attempts、typed gaps 和 adapter receipts 未进入正式 candidate result。
4. **效率 ceiling 暴露**：19 次串行请求耗时 212 秒仍未完成 DELL，一案 24-call ceiling 虽未越界，但当前 discovery 产出/成本比不具进入 ranking 的资格。

## 4. 下一结构包

下一项限定为一个零调用 S1-08 结构包：

- 将 `RemoteDisconnected`、connection reset/abort 等连接终止统一转成 capture-first typed transport failure；
- 用本次 immutable response capture 做 replay fixture，按 source family 过滤 IR earnings/results/filing 路径，去除 navigation/store/product/footer 噪声；
- SEC locator 按 allowed form、filing date、currentness 排序，规范化大小写/重复 URL；
- 每 target/route 先筛 locator 再 fetch，收紧无效文档预算；
- 即使单一 source 失败，也物化 partial attempts、adapter receipts、typed gaps 和真实网络计数；未知项目异常仍终止，但不得丢失已获得的审计结构。

完成后先跑 captured-replay、full-fake、DELL/MU/NVDA mutation 和效率 ceiling。是否签发一次 replacement DELL canary需要独立决定；本日志不授权 R2。ranking/NDCG/MRR/BGE/Milvus、MU/NVDA、DeepSeek/S3 继续阻断。
