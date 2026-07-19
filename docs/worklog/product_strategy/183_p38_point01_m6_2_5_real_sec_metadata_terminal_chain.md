# 183 P38 Point 01 M6.2-M6.5 Real SEC Metadata Terminal Chain

日期：2026-07-13

## 已批准且实际执行的范围

total reviewer `william（工号003）` 的 fixed-store one-shot receipt 在北京时间 15:47 被原子消费。经用户明确同意，唯一请求使用一次进程内 `SEC_USER_AGENT`（未写入配置或 store），访问唯一允许端点：

```text
https://data.sec.gov/submissions/CIK0001045810.json
```

没有 fallback、retry、provider、模型、document/HTML 下载、Evidence/Writer、Domain Judgment、full-chain、业务 Case mutation 或 legacy authority change。

## 实际 receipt 链

| Point | 实际结果 | Exact ref | 外部调用 |
| --- | --- | --- | --- |
| M6.2 | HTTP 200；SEC filing-header metadata；budget consumed；terminal succeeded | `tool_invocation_a80a2cc063561dcca1c1e3c6:v4` | 1 |
| M6.3 | `retrieval_exhausted`；period/neighbor section/table context 缺失；candidate=0 | `candidate_bundle_5716ecd622b8d8558d8b:v1` | 0 |
| M6.4 | terminal RepairTicket；`attempt_budget=0` | `repair_ticket_4d16c591107d82a6ab62:v1` | 0 |
| M6.5 | no-parser/no-numeric typed stop；parser/fact/trace=0 | `parser_numeric_stop_f6084fb175bb7a917be0:v1` | 0 |

关键 audit digest：

```text
M6.2 terminal receipt digest: d4fbf78caada4a6ed7040f2fb88cdcfff520359fc2e037fc70fb2f4ac59a6857
M6.2 source metadata digest:  c490f8e0ee9b401ee755e9559787c467ab2401db60e7ccc3014ba39d2da142c2
M6.2 receipt version digest:  44deb9d5829e0b24de213bd4bd9e1684825ca9377f98dc3ea14b1aebe08ed02f
M6.3 bundle version digest:   9ba76f141ad185a1994235b169c43986f6b99bc127ef7ee4c4227be530670d2d
M6.4 ticket version digest:   f5782557f2ed130d6632ca8f97c4672190f32ec46a2301932570d6c91795e168
M6.5 stop version digest:     d623c864a72e7f3f3e5c9638e748ceaa4d8d7b4a24c79601b55f159ccee3e7d8
```

对 M6.3-M6.5 的 exact ref 重放全部 `pass` 且 `reused_idempotent_result=true`、`store_write_count=0`、`external_call_count=0`；没有形成第二次网络调用或重复 terminal artifact。

## 结论与边界

本链真实证明了 narrow SEC route、global one-shot receipt、M5.4 admission、M5.5 budget、durable receipt 与 M6.3-M6.5 no-invention terminal behavior 可以共同运行。

它没有证明 RAG/SQL/graph recall、context expansion、SourceHunter、document/table parser、numeric extraction、Evidence Gate promotion 或 Agentic Research 成功。因此 M6 未完成；M6.6 仍只可作为 fixture gate，M6.7-M6.10 不得自动推进。下一次正向 retrieval/parser pilot 必须另行设计、授权与审计，且不得以已经 consumed 的 one-shot receipt 重发请求。
