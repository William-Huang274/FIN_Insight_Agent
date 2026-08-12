# 2026-08-13 FIN 0.1.3 S2 公司财务事实 Mart

## 目标

落实 Owner 对“数据库问题不能遗忘”的要求，把 S1 已编译的 `TypedFactRequest` 接到一条 source-bound、point-in-time、可保留 vintage 的公司财务事实路线；不复用旧年度单行表，也不让文本候选获得数值权威。

## 实现

- 新增 `src/financial_facts/`：事实合同、SEC capture parser、SQLite mart、PIT executor。
- 新增版本化 policy/result 和 Workbench Operations data-build catalog 入口。
- 从 DELL／MU／NVDA 已保存 CompanyFacts＋Submissions 构建 private SQLite；原始 source 未修改。
- `TypedFactRequest` 现在可执行为 `NumericFact`／`typed_gap`／`typed_conflict`。
- 使用 Decimal、accession、accepted-at、期间角色、source digest、supersession 和公式 trace。
- SQLite 读写连接均确定性关闭，避免 Windows 原子重建时文件句柄残留。

## 自然暴露并修复的问题

第一版开放期间查询按每个 period role 独立选择最新行，导致最新 Q1 与旧 Q3 YTD 可能同时进入结果。这在业务上等于把不同申报批次拼成一个“当前季度”。修复后，interim/instant 锁定同一最新 10-Q accession，最近 FY 单独来自最新 10-K；历史精确期间仍按 PIT 选择该期间的最新可用 vintage。

SEC CompanyFacts 中大量旧行在当前保存的 `submissions.recent` 里没有对应 accepted-at。当前实现选择 fail closed：只保存已绑定 filing identity 的 observation，并把覆盖缺口记录在构建结果中；不从 filed date 或 raw row 猜 accepted-at。

## 验证

- `python -m compileall -q src/financial_facts scripts/data_retrieval/build_s2_company_financial_fact_mart.py`
- `python scripts/data_retrieval/build_s2_company_financial_fact_mart.py`
- `python -m pytest tests/test_s2_company_financial_fact_mart.py tests/test_current_data_build_catalog.py -q`
- `python -m pytest -q`
- `python scripts/engineering/verify_active_baseline.py --pretty`
- `python scripts/engineering/check_repository_secrets.py`
- 结果：1,319 observations；最近财年 9/9、当前 interim 15/15；六类 mutation 全过；targeted tests 10 passed、全仓 131 passed；活动图 94 Python／7 frontend、0 forbidden ref；6,347 files secret scan 0 finding；0 network／0 model。

活动基线检查还自然暴露：Workbench catalog 通过字符串启动的脚本不会被纯 AST import closure 自动发现。检查器现以 data-build catalog 为动态入口真值，因此 Query Atom 和 S2 mart 构建器都会进入活动代码图，后续新增 catalog step 也不会被静默漏审。

## 边界与下一步

当前是 S2 engineering pass，不是产品 Runtime 或 Owner acceptance。private mart 没有进入 Runtime Registry，Workbench reviewed Pack 的 structured numeric 仍未因此自动增加。下一项只能是 DELL S1/S2/S3 纵切；纵切需要一个真实 Runtime consumer，并在研究输出中证明 NumericFact 被正确选择、引用和解释。
