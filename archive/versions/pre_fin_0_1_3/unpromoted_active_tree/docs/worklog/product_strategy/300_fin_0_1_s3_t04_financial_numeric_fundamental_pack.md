# FIN 0.1 S3-T04 Financial Numeric / FundamentalDecisionCellPack

日期：2026-07-21
状态：`pass_after_independent_review / T05_ready_pending_separate_authorization`

## 问题与授权

用户要求继续当前唯一下一项 S3-T04。授权仅覆盖零模型、零外网、零外部工具、零真实业务写入的 deterministic 财务 Numeric 与 FundamentalDecisionCellPack fixture；不覆盖 T05+、新 admission、付费 Run、S4、release 或 production。

T04 处理两个最早 owner 缺口：

- `RC-P36-023`：已有公司级财务行，但缺少按 Cell/entity/segment/period/currency/unit/row-label 的 headline selector、公式血缘和业务线不可推断边界；
- `RC-P36-025`：Fundamental Specialist 上游缺少 Cell-specific 财务输入包和 typed availability。

## 决策

复用唯一 Numeric owner `src/sec_agent/canonical_runtime/parser_numeric.py`，不新建平行 Numeric store 或业务真相体系。T04 消费同一 T02 RuntimePlan、T03 Evidence route plan，以及现有 deterministic local preview 的一次只读 Gold SQL 财务结果。

T04 只认可 FY2025 NVDA 公司整体口径：

- Revenues：`130497000000 USD`；
- Gross Profit：`97858000000 USD`；
- Operating Income (Loss)：`81453000000 USD`；
- gross margin：`gross_profit/revenue*100 = 74.99%`；
- operating margin：`operating_income/revenue*100 = 62.42%`。

这些数字不能支持 Data Center/accelerator 分部利润率、AI 增量利润捕获或跨供应链经济分配。它们全部保留为 typed cannot-infer，不允许用叙事补齐。

金融方法 registry 中的 `three_statement_peer_panel` 在 T04 只推进到“公司整体利润表子集已 runtime injected + node consumed”。资产负债表、现金流、同期间 peer panel、paid artifact 和 dogfood acceptance 均未证明，因此不把完整方法描述为 S3 已激活。

## 实现

- `src/sec_agent/canonical_runtime/parser_numeric.py`
  - 新增 exact financial selector、SelectedFinancialRow、DerivedMetric、FundamentalDecisionCell、correction dependency closure 和总 pack；
  - 每个派生指标保存输入行、Evidence refs、公式版本、`decimal_half_up_2dp`、结果、support boundary 与 cannot-support；
  - consumer 重算 pack/row/metric/cell/correction digest、算术结果和依赖闭包，篡改 fail closed。
- `apps/workbench/backend/application/local_research_service.py`
  - deterministic exact fact 现在显式暴露 entity、segment、currency、unit、row label、scale 与 source coordinate，供 selector 校验；
- `apps/workbench/backend/application/research_runtime.py`
  - deterministic adapter 将 T04 pack 和三份 Cell consumption receipt 写入原 `deterministic_research_result` Artifact；
  - Runtime validator 重建并重验完整 T04 pack；
- `tests/contract/test_fin_0_1_s3_t04_financial_numeric_fundamental_pack.py`
  - 覆盖 runtime persistence/consumption、七维 selector、公式和 Evidence lineage、typed cannot-infer、选择性 correction closure 与 tamper fail-closed。

## 独立复核与修复

复核发现并修复：

1. T04 实际消费 T03 route plan，因此 backlog 依赖补入 `S3-T03`；
2. S1 deterministic spy 只有旧版最小 Numeric payload，缺少新 selector 字段；测试替身升级为与生产 deterministic preview 同一输入合同，未放宽 selector；
3. 公司整体 margin 不得描述为产品、分部或跨链利润捕获；value Cell 保留三项 typed cannot-infer；
4. T06/T07 canonical Judgment/Report heads 尚不存在；本轮只证明 correction 的 exact dependency closure，实际 canonical head invalidation=`0`。
5. 仅重算 digest 与算术仍不足以阻止整体重签名后的错误闭包；consumer 补充逐项反查 selected row 的 value/Evidence/entity/segment/period/currency/unit，并交叉核对 T03 bundle/promotion refs。

## 结果与证据

- selected financial rows：3；
- derived metrics：2；
- FundamentalDecisionCell：3；
- typed cannot-infer：5；
- local Gold SQL financial read：1；
- model/provider/execution network/source network/external tool/live business write/Evidence promotion/canonical head invalidation/admission/paid run：全为 0；
- focused T01-T04 + Project OS：`38 passed in 38.15s`；
- expanded shared Runtime/S1-S3/Workbench/Gateway/Agent Registry/Project OS：`164 passed in 99.32s`；
- final T04/Project OS/stable source digest：`13 passed in 20.37s`；
- JSON/JSONL、秘密扫描与 `git diff --check`：通过（仅 JSONL CRLF→LF normalization warning）。

## 剩余边界与下一项

`RC-P36-023`、`RC-P36-025` 与 `RC-P35-021` 仍为 full-chain blocker：T04 只证明 deterministic runtime input，未证明 live parser promotion、业务线来源充分性、Specialist 模型消费、付费研究质量或 owner acceptance。

唯一下一项为 `S3-T05-BOUNDED-GRAPH-PRODUCT-MARKET-AND-RISK-DECISION-CELL-PROJECTION`，必须另行授权。
