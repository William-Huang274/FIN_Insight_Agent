# 786 — FIN 0.1.3 三留出案当前官方源 live 与 ASML 详细披露缺口

日期：2026-08-09

归属：FIN 0.1.3 / S1 / held-out generalization

状态：`official_filing_capture_3_of_3_success_detail_sufficiency_2_strong_1_thin`

## 1. 唯一 exact-live 结果

clean／synced implementation commit=`da56362665226415f84333fe471fecc8882c0e14`。唯一 admission 已消费并 terminal success；总计 `6 network / 0 retry / 0 model / 0 provider / 0 embedding / 0 rerank / 0 Evidence`。

| 案例 | 选中文件 | 日期 | 解析字符 | capture 结论 |
| --- | --- | --- | ---: | --- |
| ORCL | FY2026 10-K `0001193125-26-277521` | filed 2026-06-22 / report 2026-05-31 | 461,795 | 完整 primary filing 已保存 |
| ASML | Q2 2026 6-K `0001628280-26-048235` | filed 2026-07-15 / report 2026-06-28 | 2,263 | 6-K cover／exhibit list 已保存，但详细 exhibit 未保存 |
| ANET | Q2 2026 10-Q `0001596532-26-000175` | filed 2026-08-05 / report 2026-06-30 | 289,288 | 完整 primary filing 已保存；10-Q 优先规则生效 |

所有 final URL 都由 SEC submissions 响应派生，policy 没有预置 accession 或成品 URL。原始 request／response 和 parsed text 在 Git 外私有 object store，public result 只保留 capture ref 与 digest。

## 2. 为什么不能直接宣布“三案资料齐了”

运行时 marker gate 证明的是“表单身份和期间命中”，不是“研究内容充分”。离线检查保存正文后：

- ORCL 有 OCI、RPO、cloud revenue、capex 和 operating cash-flow 语境；
- ANET 有 AI networking、Ethernet、revenue、gross margin、inventory 和 cash-flow 语境；
- ASML 6-K 只有结果 headline 和 exhibit 列表，包含净销售额、净利润与毛利率摘要，但 `bookings / EUV / High-NA / installed base / systems sold / cash flow` 均为 0 次。

ASML primary 没有 HTML anchor，旧 `same_accession_exhibit` locator 无法从正文直接取到附件。继续把它算作完整 current source 会再次把“抓到表单”误当成“抓到研究资料”。因此 public live terminal 保持成功（filing capture 的确成功），但 held-out product generalization、current reparse 和 index admission仍为 false。

## 3. 下一项的有界修正

不是重跑三案，也不是 broad Web Search。下一项只允许：

1. 从已保存 ASML accession 派生 SEC 同 accession `index.json`；
2. capture-first 获取目录；
3. 按 exhibit type／description 选择详细 Q2 results 附件，最多再抓 1–2 份；
4. 保留 PDF／HTML parser lineage；
5. 然后把 ORCL、ASML、ANET 一次性走 table-preserving reparse 与 BundleV2 mutation。

这是一项内容充分性 successor，不是失败 retry。已成功的 ORCL／ANET 不再访问网络，live-r1 不修改。

## 4. 机器证据

- public result=`configs/releases/fin_ia_0_1_3_s1_held_out_current_source_acquisition_result_v1_0.json`
- result digest=`65cd6601f00d331ce2ae105268b095a8cc1cc28cfb01674f00756c707bfacea2`
- public record digest=`6df6772f6b47d6795e254b1c9e099ea04d4c3766489946f56ef7eed9dc3411e2`
- terminal receipt=`success / all_targets_captured`
- private raw/parsed capture families=`15 objects`（6 request、6 response、3 parsed）

本项关闭“当前表单是否存在并可捕获”，没有关闭“详细内容是否足够形成 Evidence Pack”。
