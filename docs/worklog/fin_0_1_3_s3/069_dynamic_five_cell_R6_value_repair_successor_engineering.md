# 069 DELL 五单元 R6 Value 修复 successor 工程闭环

日期：2026-08-17

## 结论

R6 保持为不可变失败。当前代码已把它暴露的三个表面统一收敛成一个 provider-neutral 的“依赖权威编译”问题，而不是继续逐字段补 Prompt：

1. 模型选择 NumericRelation 后，Harness 本地绑定该关系已经授权的两个 NumericFact 端点并留下 receipt；模型不再重复选择同一事实。
2. 模型选择 ClaimRelation 后，Harness 本地绑定该 alias 已审定的 QualitativeFact，并按 thesis／mechanism／counterargument 的实际用途校验局部 Evidence 角色；不能要求反方把一份全局 `limit` 资料伪标成 `support`。
3. source-bound NumericFact、NumericRelation 和 reviewed QualitativeFact 可以支撑它们各自的精确结构化观察；它们不能因此获得更宽的产品因果权威。

自由叙事中的日期、数字、单位、URL 和内部引用门禁没有放宽。R6 Value 原始 Tool Call 在新合同下稳定重放为 `research_consumer_thesis_atom_invalid`，因此仍须由模型交一次新的无日期 thesis；Harness 不改写模型观点。

## 真实 R6 回放

- Value analysis 的请求、响应、finish reason、正文和摘要均与 immutable capture 一致，reuse digest 为 `076efa18...fa18`。
- R6 原始 Value arguments digest 为 `028f0f49...6388e`，没有被提升为业务结果。
- Demand、Operating、Cash、Counterevidence 四个有效 Judgment 的历史 digest 在 v1.4 输入下保持不变。
- 零调用合规 Value fixture 只用于证明编译路径：本地补入两个收入同比端点，并绑定 reviewed margin QF；五单元 Judgment、workpaper、synthesis 和 internal report 均可完整物化。
- cross-case ClaimRelation、capture 摘要漂移、原始日期 thesis 和未闭合五单元均继续 fail closed。

## 工程与治理结果

- 新 claim-surface policy 使用 v1.4；R6 使用的 v1.3 保持不可变。
- stable five-cell runner 新增一条通用 successor 模式：复用四个有效单元和 Value analysis，只允许一次 Value typed repair submission；通过后才允许一次 synthesis analysis 和一次 synthesis submission。
- execution budget 固定为 3 次模型调用、3 次 transport、2 个 Tool Call、0 retry／fallback／协议切换／外源网络／当前产品指针变更。
- 两个独立零调用进程均为 126 tests passed；随后全仓 477 tests、Python compileall、active baseline `135 Python / 8 frontend / 11 Runtime resources / 0 forbidden reference`、secret scan `6,829 files / 0 finding` 与 `git diff --check` 全部通过。formal proof 和 scope decision 均不授予模型权限，真实 authority 仍须在 clean push 与 repository-bound preflight 后另行签发。
- 根因账本保留 RC-S3-037 单一结构家族，并纠正了 preflight 中曾写错的 issue ID；没有为每个依赖字段新建一个补丁型根因。

## 当前边界与下一步

下一步只能：完成全仓复证、同步 Project OS、clean commit/push、执行真实 repository-bound preflight，再签发一次 fresh R7。R7 不重跑 Planner、S1/S2、五个 analysis 或四个有效 Judgment；最多执行 Value repair submission、synthesis analysis、synthesis submission三次调用。

若 R7 完成报告，随后必须独立做金融 L1、八维绝对内容质量、与旧同证据结果的 paired comparison 和 qualified-human review。只有这些通过，DELL 五单元才可能关闭；MU、NVDA 与留出案例泛化、S3 acceptance、Workbench 发布和 release 仍为 false。
