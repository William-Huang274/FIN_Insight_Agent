# 791 — FIN 0.1.3 留出案例表格语义坐标 R4 修复

日期：2026-08-10

阶段：S1／留出案例对象形状泛化与索引准入前复核

状态：R4 working-tree 零调用结果通过；clean Git archive 独立复证待完成；真实索引未授权

## 1. 为什么旧 clean proof 不能继续授权索引

上一轮 R1 clean proof 证明了代码和输入可以在干净环境中复现，却没有证明每一个被选中的财务表格单元都保留了正确的业务坐标。把 R1 的候选编译成下一版 sparse／dense manifest 时，新增的逐条业务审计发现：

- ANET 的 `Customer relationships` 是无形资产剩余使用年限，数值 `5.7` 被错误标成 `usd_millions`；
- ORCL 的 `Total Operating Margin = 20,606` 所在表明确是 `(Dollars in millions)`，但表旁的欧元 constant-currency 叙述污染了单位判断，结果只保留成 `usd`；
- ORCL 固定资产表把 `Useful Life` 与 `2026／2025` 混合表头错位，曾把 `59,634` 绑定到 Useful Life，而不是 2026；
- ORCL 权益滚存表的交易行没有逐行年份，旧 parser 把 2025 的 `Net income = 12,443` 错绑到 2026；
- 较宽表格中的压缩百分比行只给两个期间值，旧逻辑把第一个值错绑到 `(Dollars in millions)` 表头，而不是 2026。

因此 R1 的“clean reproducible”仍然成立，但它只证明可复现地生成了同一个结果；它不能继续作为索引内容安全的授权依据。R1 proof 与 result 保持不可变，索引 manifest 必须改绑后续 R4 clean proof。

## 2. 为什么经历 R2、R3、R4

本项没有调用 DeepSeek、Provider、外网、embedding、rerank、Milvus 或 Evidence Gate。R2、R3、R4 都是同一 S1 表格对象责任域内，基于三份不可变 capture 的新 Attempt；每次都保留结果，不覆盖前次。

- R2 修复了非货币维度和表内显式币种／规模优先级，关闭 `5.7 years` 与 `20,606 usd_millions` 两类错误；业务审计随后暴露混合 descriptor＋period 表头错位。
- R3 接受 exact header／value cardinality，关闭固定资产表的 Useful Life／2026／2025 左移；业务审计随后暴露 descriptor-only rollforward 与压缩行期间绑定错误。
- R4 增加 rollforward 期间推导和压缩行按 ordered candidate periods 绑定，关闭权益滚存与压缩百分比行错期。

这不是为单一 ticker 写特判，而是补齐通用 HTML 财务表的几类坐标语义：单位维度、表内币种权威、descriptor 列、rollforward 年份传播、压缩期间行。现有 mixed-scale bank table 逻辑继续保留，新增逻辑不允许用第一个币种短路含 `except` 的多尺度表。

## 3. R4 当前结果

R4 result digest：`924c656e32e5e279c12883a6374f53b7e424d5e3046c2ed18e6a4d2f11878ffc`。

| 案例 | admitted table metrics | typed rejects | projected bundles | projected Slots |
|---|---:|---:|---:|---:|
| ORCL | 1,249 | 236 | 27 | 8 |
| ASML | 18 | 0 | 13 | 5 |
| ANET | 470 | 238 | 27 | 7 |

9／9 mutation 通过，unsafe numeric bundle admission=`0`，network／Provider／model／embedding／rerank／Evidence=`0`。对拟入索引的 48 个留出案例 metric candidates 做业务抽查后：

- ANET `Customer relationships = 5.7` 为 `years`；
- ORCL `Total Operating Margin = 20,606` 为 `usd_millions`；
- ORCL 固定资产 `59,634／30,345` 分别绑定 2026／2025；
- ORCL 压缩 margin 行绑定 2026／2025；
- 2025 权益净利润不再冒充 2026 candidate。

上述对象仍是 `candidate_only_not_evidence`。数量与抽查通过不等于完整 Evidence Pack、研究结论或报告质量通过。

## 4. 当前处置和下一步

1. 精确提交并推送 R2／R3／R4 的不可变 policy/result、通用 parser 修复、合同测试和本工作记录；
2. 从该提交导出两个独立 clean Git archive，每个 archive 只注入三份 digest-bound capture，并在 fresh process 中复现 R4 digest、9 mutations 与 0 external calls；
3. clean proof 通过后，把 CandidateBundle-only sparse／dense manifest 从旧 R1 result/proof 重绑到 R4 result/proof，并启用 period/unit fail-closed mutation；
4. manifest 仍只做零调用 fake build 和内容审计。真实 BGE／Milvus 只能在 Ubuntu WSL 路径下另行签发 authority；
5. 索引、同矩阵 ranking 和本地 Evidence Pack 完成后，才把真实 residual gaps 交给外源补源；最后才让 DeepSeek 做动态追问和研究综合。

如果 R4 clean proof 不能复现，问题继续留在 S1，不得用 R1、调整门槛或直接建索引绕过。

## 5. Project OS scope 投影更正

写入 R4 blocker 后，Project OS 首次按 reparse scope 预检被 RC-P36-157 外源覆盖与 RC-P36-162 Windows Milvus 两个历史 `*` blocker 误挡。两者都不参与本次零网络、零 embedding、零存储写入的 clean proof，因此新增 typed projection，只允许 offline reparse 与后续 zero-call manifest；外源 `4/12`、Windows 不可用和真实 build 未授权均未改变。更正后未使用 override，scoped preflight 正常 pass。
