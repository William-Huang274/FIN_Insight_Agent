# 829 — FIN 0.1.3 S1 DELL 定向补源恢复与 authority 暂停

日期：2026-08-10

状态：zero-call recovery proof passed；new source authority not ready

## 业务结论

本轮没有调用 DeepSeek，也没有重跑四条来源。TSMC 的有效 CoWoS 供给论述已从历史 immutable capture 恢复，证明上次失败属于本地 selector，而不是 TSMC 缺资料。Dell 与 Micron 的官方 document／locator 也已重新资格化为一次捕获候选。报告仍不能继续，唯一 authority 前置 blocker 是 DELL 研究截至日 2026-08-06 的市场价格路线尚未形成可执行、可捕获、无标准答案泄漏的请求合同。

## 工程修复

- fragment selector 从“每个 regex 第一次命中”改为“全部 occurrence 的确定性最小覆盖窗口”；真实 TSMC old/new span=`18,170/233`，excerpt=`912`，字符上限仍为 4,000。
- official-source capture v1.1 增加 phase 与 safe cause class；timeout、DNS、TLS、connection refused、connection terminated 和 unknown transport 由 fault injection 覆盖，底层异常文字与凭据不保存。
- PIT parser 不再比较历史策略中的 `$437.65`。测试用 capture close `$412.34` 仍通过，且最终 SourceMaterial 只包含捕获值，证明没有 expected-value acceptance。
- route qualification 区分 locator、可执行候选、authority 与 live success。Dell transcript 已满足一次捕获候选；Dell release 只覆盖订单／收入／指引部分面，不能冒充 transcript 全量。Micron deck／prepared remarks 同理。

## 零网络结果

公开 result：`configs/releases/fin_ia_0_1_3_s1_dell_targeted_source_recovery_result_v1_0.json`

- result digest=`5de25dedcc697b6fde80312e9ed6ad98907acf0e20848e9200f3a2a6025e5b65`
- TSMC capture digest=`39805472768ede6729a8c4dd168e22d5653ec5eb7560c1c55f394787c891352d`
- parser=`official_source_pdf_text_v1`；parsed chars=`65,259`
- zero-call/fault-injection targeted suite=`28 passed`
- network/provider/model/retry=`0/0/0/0`
- authority blockers=`1`：`market_point_in_time_executable_exact_date_request_unproven`

Dell IR 的 Historical Price Lookup 明确标注 LSEG，但当前项目直接读取该 GCS 页面超时，网页读取又出现 403；Q4 公开文档说明历史价格 widget 需要 exchange/symbol/date，旧 feed 还可能依赖站点 API key。因而“页面存在”不能替代“精确日期请求可执行”。Nasdaq 旧 JSON route 也没有成功 capture，不能恢复预填答案继续用。

## 决策边界

不签发 source authority，不进入 enriched Pack／DeepSeek／paired／Owner。下一步必须先取得可审计的 PIT 路线（公开站点请求合同或合格市场数据 API），或由 Owner 明确接受估值 typed gap 并缩小报告比较目标。后续 authority 只要求候选路线与 parser proof，不会循环要求 live 成功；但 authority 消费后 Dell 法说和 PIT 都必须真正 materialize，才能进入新 Pack。
