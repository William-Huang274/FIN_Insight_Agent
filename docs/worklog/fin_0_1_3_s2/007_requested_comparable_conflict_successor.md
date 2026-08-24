# S2 requested/comparable identity conflict successor

日期：2026-08-24

## clean audit P1

immutable `1243b3cc...` 的 v1.4 已能让单独 no-origin group fail closed，但组合路由仍有漏洞：当最新期有 timely identity、被请求旧比较期没有 timely origin 时，旧 conflict 只有 nested `candidate_fiscal_identities`；selector 只无条件传播最新 `period_end` conflict，自动同比又读取不存在的顶层 `fiscal_year/fiscal_period`。结果可只返回当前期并标 `resolved`，derived 也可能只算当前期。

这推翻 v1.4 的 generic executor-boundary closure，但不推翻原 MU 三事实、六个 FY2023/Q1 as-of、728-group inventory、direct conflict propagation 与 role isolation。clean audit failure 已作为跨阶段不可变收据保存。

## v1.5 successor

executor 现在：

1. 在 identity conflict 中保存顶层 single label、完整 nested candidate identities、candidate fiscal years 与 explicit-request match；未知 fiscal year 不能因空 candidate set 被静默排除；
2. explicit requested fiscal-year conflict 在 latest-role selection 前直接传播；
3. automatic prior-year comparable 通过 nested candidate identity 匹配 current year - 1 与同 fiscal period；
4. identity conflict 的 filing-cohort 相关性改为“当前 accession 在 copies 中”，不再要求全部历史 vintages 只有同一 accession；
5. derived request 继续把该 direct conflict 作为 `derived_formula_input_conflict` 传播。

新增 direct 回归同时覆盖 explicit `[2026, 2027]` 与 empty-year automatic comparable；derived 回归覆盖 current gross profit + current revenue + no-origin prior revenue。三者都必须在旧期 `2025-05-02` 返回 typed conflict。

`materialize_s2_mu_physical_period_identity_successor_v5.py` 输出不可变 v1.5：11/11 checks true，包含 v1.4／clean-audit binding、原 MU facts、六 as-of、no-origin、728 population、既有 derived/role probes 与三个新 comparable probes；calls=`0/0/0`。

## 边界

该 successor 关闭 `RC-S2-017` 的 conflict-routing 根因，只证明当前 bound executor 与回归。它不重建 mart、不提供 ASP／units／PVM／产品利润桥，也不签发 S2、S3、产品、publication 或 release。

## 工程门

S2 定向 `18 passed`；跨 S1/S2/S3 联合定向 `47 passed, 2 skipped`；全仓 `1221 passed, 2 skipped, 2 existing warnings`。compileall、8 个变更 Python 文件 pyflakes、1,009 config JSON、8 Project OS JSONL／1,157 行、active baseline `212／8／5／28／0`、Workbench typecheck／build、7,910-file secret scan／0 和 diff check 均通过。
