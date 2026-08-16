# 050 S3 动态 counter：时间关系 L1 失败与一次性修复门

日期：2026-08-16

## 真实运行结果

DELL `value_capture` 的 dynamic R1 加 R3 successor 已经自然完成 planner、当前 S1/S2、thesis、mechanism、counter／WWC 和严格 Tool submission。R3 复用了前五个成功节点，只新增一次 counter 分析和一次交卷，最终状态诚实保持 `insufficient_evidence / not_inferable / bridge_unavailable`。

合同通过不等于金融事实通过。独立 L1 检查发现 counter 把两件各自真实、但报告期不同的事情写成了“同期”：公司毛利率比较来自 Q1 FY2027 对 Q1 FY2026；优化服务器组合压力来自 Q3 FY2026 10-Q。当前输入没有任何已编译关系证明它们属于同一财季。因此 R3 必须保持 `contract pass / L1 fail`，不能因整体叙事保守而放行。

## 根因与责任层

该问题登记为 `RC-S3-028-dynamic-narrative-temporal-relation-unbound`。最早责任层是 S3 动态 fragment／ClaimRelation 合同：旧上下文分别展示 Evidence 的日期和 NumericRelation 的期间，却没有单独表达“这两项是否可视为同期”，Validator 也没有禁止模型自行拼出这层关系。

它不是错公司检索、错误数字、网络故障或 DeepSeek Tool Call 不遵循。DeepSeek 生成了一个看似合理但未经时间绑定的叙事连接；金融控制面此前没有表示和验证这种连接。

## 结构修复

- 每个动态片段新增 provider-neutral `TemporalAuthority` 卡；
- NumericRelation 只授权其内部 current／comparison 同口径比较；
- Evidence 的发布日期或报告期本身不授权它与另一条数值关系同期；
- 只有 source-bound QualitativeFact 的期间与 NumericRelation 某一端精确相等，才编译 cross-item same-period binding；
- 中英文同期间叙事若同时连接产品主体和财务结果，却没有该 binding，则以 `finance_loop_micro_temporal_relation_unbound` fail closed；
- 历史材料仍可作为历史背景，但必须明确“不证明同期或因果”。

真实 R3 fragment 已被当前代码零调用重放并准确拒绝；确定性正向、负向和一次性 typed repair 测试通过。修复 compiler 只允许模型重交 counter fragment 一次，不新增 Evidence，不重跑 planner、S1/S2、thesis、mechanism 或 counter analysis，也不由 Harness 删除“同期”或改写观点。

工作树复证为全仓 `389 passed`；Python compileall、active baseline `131 Python / 8 frontend / 10 Runtime resources / 0 forbidden reference` 和 secret scan `6,732 files / 0 finding` 均通过。历史 v1.2 successor preflight 也改为从其 implementation commit 核对 runner blob，避免稳定 runner 演进后把已经完成的旧决策误报为当前路径漂移；旧执行 scope 已关闭，不能重新使用。

## 当前边界与下一步

当前只是 engineering repair gate。正式 clean proof、Project OS preflight 和 fresh authority 通过后，最多执行一次 non-thinking counter repair submission。修复结果仍须独立通过 L1 和适用内容质量；未通过时保留新失败，不自动扩成第二次修复循环。

即使动态单单元通过，高质量 DELL 五单元仍受 `RC-S1-019` 阻断：已审 Dell transcript 尚未同步到当前动态检索对象／来源路线。该问题归 S1，不得用 S3 预喂或放宽时间合同掩盖。
