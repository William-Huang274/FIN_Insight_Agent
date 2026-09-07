# S2 strict origin 与 derived conflict boundary successor

日期：2026-08-24

## 两轮追加审计

`5f35b116...` 已正确停止把 final supersession pointer 当期间身份，但本轮自审发现“没有 timely origin、所有晚期 copies label 一致”仍不构成 authority。真实 mart 的 728 个 physical groups 中，40 组没有及时 origin，34 组只有一个一致 label；其中 19 组出现显然的 role/label 不一致（12 个 quarter-discrete 标 FY、7 个 fiscal-ytd 标 FY）。因此 agreement among non-authoritative copies 不能替代 contemporaneous source。

随后 fresh reviewer 又发现：

- `_execute_derived` 把 direct input 的 `typed_conflict` 降成 `derived_formula_input_missing` gap；
- 请求 role 没有候选时，无关 role 的 identity conflict 可能在 granularity filter 前触发假 conflict。

上述分别记录在 self-audit 与 independent failure receipts；特定 MU current 三事实与六个 as-of 因均有及时 origin，结果保持正确。

## successor 行为

1. physical period identity 必须由同 physical key 的 10-Q 45 天／10-K 90 天及时 source 唯一给出；无 timely origin 一律 typed fail closed，即使所有晚期 copies 一致；
2. fiscal-year filter 仍在 identity admission 后执行，later numeric vintage 只在 canonical label 下可用；
3. formula input 只要有一个 authoritative conflict，derived request 就返回 typed conflict，并保存 input side、metric、request ID、conflict code 与 nested conflicts；只有完全无 conflict 的缺失输入才能形成 gap；
4. candidate SQL 在 identity admission 前按 requested granularity 限定 period role，无关 annual／instant 行不能制造 quarter conflict。

最终 v1.4 receipt 对原 MU 三事实、六个 FY2023/Q1 as-of、DELL no-origin counterexample、728-group population、derived-conflict synthetic probe 与 unrelated-role synthetic probe共八项检查全部为 true，calls=`0/0/0`。

## 不可变失败链

- strict-origin 改动后的第一次定向：`2 failed, 11 passed`，原因是两个 synthetic comparable fixtures 自己没有 contemporaneous origin，却期待 comparable authority；补 origin rows 后 `13 passed`；
- v1.2 materializer 的业务检查均真，但 failure-receipt shape comparison 写错，结果固定为 failed，未覆盖；
- v1.3 修正 receipt shape 并证明 strict origin；fresh audit 的 derived／role finding 出现后另开 v1.4，不覆盖 v1.3；
- 最终 S2 文件定向 `15 passed`，联合定向 `40 passed, 1 skipped`，全仓 `1214 passed, 1 skipped, 2 warnings`。

联合收口的 compileall、14 个变更 Python 文件 pyflakes、1,005 份 config JSON、8 份 Project OS JSONL／1,148 行、active baseline `212／8／5／28／0`、Workbench typecheck／build、7,901-file secret scan／0 和 diff check 均通过。前端 `pnpm` wrapper 的 pre-script tooling failure 已单独保存在 `configs/engineering/fin_ia_0_1_3_fresh_audit_frontend_pnpm_wrapper_failure_v1_0.json`，不冒充 TypeScript/Vite 结果。

这只关闭 executor identity/conflict boundary。它不重建 mart，不补 ASP／units／PVM／profit bridge，不签发 S2 stage、S3、产品、publication 或 release。
