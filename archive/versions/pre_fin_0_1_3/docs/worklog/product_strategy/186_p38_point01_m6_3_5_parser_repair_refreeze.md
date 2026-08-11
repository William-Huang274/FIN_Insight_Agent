# 186 P38 Point 01 M6.3/M6.5 Parser Repair And Package Refreeze

日期：2026-07-13

## 审批处置

```text
decision = rejected_pending_parser_repair_and_package_refreeze
```

本轮仅获准修复 parser、增加 read-only compatibility gate 并重新冻结 package。未获准登记 one-shot receipt 或执行 live SEC GET。

原 package/manifest/scope：

```text
8bf39724... / 3d7fc60f... / da47cba1...
```

均已 superseded，不得使用。

## Root-cause repair

- 原实现只在全文件检查 heading/unit，无法把其绑定到候选 table；MD&A 摘要与正式财务报表会同时满足部分文本条件。
- 原实现按 `Year Ended January ...` 字面匹配，不能处理 `Year Ended` + `Jan 26, 2025` 多行 header。
- 原实现把目标 period index 直接当数值列，遇到 `[$, 130,497]` currency/value split 会读取错误 cell。
- 修复后保留 rowspan/colspan logical grid；每个候选 table 都必须具有独立的、紧邻 table 的 exact heading 与 unit blocks，并满足 `consolidated_primary_financial_statement` role。
- parser 将 month name/abbreviation 归一为 ISO period，在 `Year Ended` semantic group 内要求唯一 numeric cell 和 currency marker；事实 period 改为 `YYYY-MM-DD`。
- xbrl concept hint 继续被 lineage 记录，但不允许代替 table/row/period/unit/source coordinate 选择。

## Deterministic evidence

- 新增 sanitized actual-shape fixture：MD&A summary 与正式 statement 都含 Revenue，且保留 multi-row header、rowspan/colspan 与 currency split。
- 新增 actual-shape parser gate、wrong-table/duplicate-table/malformed-colspan/month/currency negatives 和 live hard-deny regression。
- reviewer-side local read-only compatibility gate：source SHA-256 `dae19486be264fd26eb00a7f920dc641041a261c81bc8c03b678eea947de4856`，唯一选中 `table[21]`，输出 `USD_millions`、period `2025-01-26`、post-parse value `130497`。raw filing 未写入 Git/canonical store；该值没有进入 policy、request、selector 或 parser 输入。

## Refrozen package

```text
package_ref:      point01-m6-3-5-nvda-10k-positive-retrieval-parser-package-v2-parser-repaired
package_digest:   c190b420ec316595b541f4df3de04168d0cc0a88d5f52bae5523dbc162c4b39c
manifest_digest:  ed4067fc83f9b46d78588c678c0ee7611a6bd2049003e096b98f353e5f6e20c6
scope_digest:     8a3a55399aa855782a78ad905d707cc8a3b0680f3a57ffadd02b3da6b9ddd29c
status:           package_refrozen_pending_total_reviewer_reapproval_no_receipt
```

package manifest 现绑定 runtime、design lint/test、actual-shape gate/test 和 sanitized fixture。mutable receipt template 与 reviewer-local raw source 均不进入 package hash。

## Verification

```text
python -m pytest tests/contract/test_point01_m6_3_5_actual_shape_parser_gate.py tests/contract/test_point01_m6_3_5_positive_sec_document_execution.py tests/contract/test_point01_m6_3_5_positive_sec_document_pilot_design.py -q
# 18 passed

python scripts/engineering/run_point01_m6_3_5_positive_sec_document_pilot_design_lint.py
# pass

python scripts/engineering/run_point01_m6_3_5_actual_shape_parser_gate.py --source data/raw_private/sec/2025/ai_gpu_semiconductor/NVDA/10-K.html --source-kind reviewer_local_read_only
# pass; external_call_count=0

$files = Get-ChildItem tests/contract -Filter 'test_point01_m6_*.py' | Select-Object -ExpandProperty FullName; python -m pytest $files -q
# 78 passed

python -m pytest tests/contract/test_point01_sqlite_store.py tests/contract/test_point01_runtime_facade.py -q
# 28 passed
```

未运行：receipt registration、new User-Agent scope confirmation、live SEC GET、Evidence promotion、Writer、Domain Judgment、M6.7、provider/model、full-chain、业务 Case mutation 和 legacy authority change。

## Current hard gate

authority policy 现在为 `not_authorized_pending_total_reviewer_reapproval`。runner 会在读取 User-Agent、创建 store 或发网前 fail-closed；receipt recorder 也拒绝执行。下一步只能由 total reviewer `william（003）` 对新 package/manifest/scope digest 作新的审批决定；未经该决定不得登记 receipt 或重开 live send。
