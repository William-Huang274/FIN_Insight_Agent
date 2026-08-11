# 794 — FIN 0.1.3 manifest R3 业务期间审计与 R9 有界处置

日期：2026-08-10

阶段：S1／CandidateBundle-only sparse／dense manifest

状态：R3 工程物化保留；业务验收失败；R9 全量复跑、48-Metric 业务审计与 clean independent proof 均通过

## 1. R3 实际证明了什么

R3 绑定 R8 clean input，物化 93 个六案主索引 spec：DELL／MU／NVDA 45 个已人工资格化 candidate，ORCL／ASML／ANET 48 个结构化 Metric；19 条自动叙事 claim 留在 quarantine。fake sparse／dense 各完整接收 93 个对象，15 类 identity、lineage、期间、单位、叙事污染和 partial insert mutation 全部 fail closed。network／Provider／model／real embedding／Milvus／rerank／Evidence 均为 0。

## 2. 为什么仍然失败

逐条读取 48 个留出 Metric 后，确认 ORCL 有四个时点余额被写成 `annual`：债券 Amount、期初现金、现金及应收账款风险敞口、期末递延收入。它们都有非空 `period_role`，所以“字段完整”与 15 类结构 mutation 都无法发现；若直接建库，检索层会把资产负债表存量与损益／现金流流量混成同一时间口径。

R3 result 与私有 manifest 保持不可变；另以 `...r3_business_audit_failure...json` 撤销其下游 authority。问题发生在财务对象时间语义，不归因 BGE、Milvus、DeepSeek、外源或排名。

## 3. R9 只修一个结构根因

期间角色改为三层优先级：

1. 行级经济语义，例如期初／期末余额与纯资产敞口；
2. 列级明确 duration，例如 `Year Ended`、`Three/Six Months Ended`；
3. 表级 presentation axis，区分 `May 31 | 2026 | 2025` 的 comparative as-of 表与 duration 表；最后才允许 10-K form fallback。

实现禁止 ticker 分支，并增加债务明细、年度现金流中的期初余额、风险敞口和比较资产负债表四类 fixture。R9 必须重跑三案 source-object result、48 条人工业务 audit、clean independent proof，再由 manifest R4 重跑 93 specs 与 15 mutations。

## 4. 止损边界

R9 若仍出现新的时间坐标 L1，不进入 R10 逐词补丁；应停止并把 `period_role` 升级为含 presentation axis／anchor 的版本化时间坐标 schema。只有 R9 业务等价和 clean proof 均通过，manifest 才可再次物化。真实 BGE／Milvus、ranking、Evidence、外源补源、DeepSeek 与报告验收继续未授权。

## 5. R9 working-tree 结果

R9 result=`caee03a5...7f3e`。ORCL／ASML／ANET 的 admitted metrics=`1249／18／471`、projected bundles=`27／13／27`、Slots=`8／5／7`，9 mutations 全通过，所有真实调用为 0。对 R8 与 R9 的 48 条入选 Metric 做完整 identity diff：case／row／column／raw value／unit／period 均 `0` 差异；role 仅有上述四条 ORCL 余额从 annual 更正为 instant。R9 role 分布=`18 instant／10 qtd／8 ytd／12 annual`，无缺失。

当前只记 working-tree business semantics pass。下一步必须先提交推送，再从两个 clean Git archive／fresh process、三份 exact capture 重现 R9；通过后才可进入 manifest R4。

## 6. R9 clean independent proof

R9 已由提交 `aff1cc463bb1e8d3cd9adb5f23a5367c1839514e` 推送。两个 clean Git archive／fresh process 各只注入三份 exact digest-bound response capture，均通过 Project OS preflight 并逐字节重现 source result=`caee03a5...7f3e`；proof=`5d46ca9d...0a7c`，all calls=`0`。R9 现可作为 manifest R4 的唯一 held-out source-object 输入；仍不授权真实 BGE／Milvus。
