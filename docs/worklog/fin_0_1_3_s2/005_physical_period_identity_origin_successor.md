# S2 physical-period identity origin successor

日期：2026-08-24

## 审计推翻的旧结论

提交 `635c943f8efc562091647838132e2aedcca7f8d4` 曾把 mart 的 `superseded_by_observation_id` 当作 physical-period identity authority，并宣称 RC-S2-006 关闭。独立只读审计证明该结论不能成立：builder 把一个 physical group 的所有旧行直接指向最后一行，不是 point-in-time successor chain；更关键的是最后一份 filing 的 `fy/fp` 也可能只是当前文档 focus 对历史 comparable 的投影，而不是物理期间真相。

真实 bound mart 有 419 个 multi-vintage physical groups，90 组超过两个 vintages，最大 6；78 组出现多个 FY/FP label，43 组 latest label 与 earliest label 不同，172 个 pointer 跳过 intermediate vintage。确定性 MU `net_income / 2022-09-02→2022-12-01 / quarter_discrete / USD` 六行样本按 accepted 顺序在 FY2023/Q1、FY2022/Q2、FY2022/Q3 间振荡。旧 executor 在中间 as-of 冲突，最终又错误选择 FY2022/Q3。

旧提交、旧 pass result 和 material finding 均保持不可变。失败收据：

- `configs/financial_facts/fin_ia_0_1_3_s2_mu_supersession_pointer_independent_audit_failure_v1_0.json`

## 修正后的 authority 分离

`src/financial_facts/executor.py` 不再消费 `superseded_by_observation_id` 作为期间身份。新规则把两个问题分开：

1. physical group 仍由 ticker、metric、start/end、period role 和 unit 定义；
2. 同物理期间的 10-Q 在 period end 后 45 天内、10-K 在 90 天内 accepted，才可作为 contemporaneous fiscal identity source；
3. timely origin 的 fiscal year／period 唯一时，它冻结该 physical period identity；
4. 后续 filing copy 只有保留同一 fiscal identity 才能作为新 numeric vintage；
5. 没有 timely origin 时，全部可见 labels 必须一致，否则返回 `typed_fact_physical_period_identity_ambiguous`；
6. fiscal-year request filter 在 identity admission 后执行；同一最新 accepted time 的数值冲突继续 fail closed。

这不是把 pointer 改成 immediate chain，也不是“latest wins”。它以 contemporaneous filing context 确定 identity，后续同标签行只更新数值 vintage。

## 真实回放

`scripts/data_retrieval/materialize_s2_mu_physical_period_identity_successor.py` 对 immutable mart 重放：

- 原 MU request 仍返回 3 条 source-bound NumericFact；
- current FY2026 Q3 与 comparable FY2025 Q3 期间精确；
- FY2025 Q2 的物理区间不再冒充 Q3；
- 六个历史 research-as-of 全部稳定解析为 FY2023/Q1；
- 最终错误 FY2022/Q3 copy 从不被选择；
- predecessor failure、audit failure、SQLite、fact count、值、期间、role、accession、observation ID 和 authority inventory 均逐项绑定；
- 0 network／Provider／model call。

机器结果：

- `configs/financial_facts/fin_ia_0_1_3_s2_mu_physical_period_identity_successor_result_v1_1.json`

## 边界

RC-S2-006 的旧“通用 PIT 已关闭”状态必须更正为“旧 closure 无效，特定 current request 结果保留”。新 RC-S2-010 只关闭“final successor pointer 被提升为 period identity authority”这一 executor 根因。没有 timely origin 且 label 不一致时仍返回 typed conflict；没有猜测 issuer fiscal calendar。

当前 mart 的 accepted timestamps 全为 `+00:00`，cross-scope／missing pointer 为 0，所以审计提出的 offset normalization 和 deprecated pointer invariant 没有改变本次 bound result；它们作为非阻断 generic hardening 保留。RC-S2-004、产品 ASP／units／PVM／profit bridge、S2 qualification、S3 和 release 均未关闭。

## 仓库门禁

相关治理／实现定向 `129 passed`；全仓 `1201 passed, 2 warnings`，两条均为既有 SWIG deprecation。另通过 full compileall、10 个变更 Python 文件 pyflakes、992 份 config JSON、8 份 Project OS JSONL／1137 行、active baseline `212／8／5／28／0`、Workbench typecheck／production build、7,878-file secret scan／0 和 diff check。
