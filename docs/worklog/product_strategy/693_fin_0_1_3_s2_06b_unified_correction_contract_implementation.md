# FIN 0.1.3 S2-06B 统一 correction 合同实现

日期：2026-08-07

状态：`engineering_implementation_pass_independent_fresh_proof_pending`

## 1. 本轮完成

- corrected node 不再只看到 correction ID/action，而会看到 finding code、severity、node/path、tokens、required resolution、closure rule 与 unresolved policy。
- 每个 corrected node 返回 typed envelope；每项 correction 必须生成 `CorrectionClosureReceipt`，虚假 closed、缺 gap 的 typed unresolved 和漏项均 fail closed。
- 模型可以看见并选择本案精确数字，但重要数值叙事只能使用 `[NUM:<alias>]`；Harness 依据 `NumericFactView` 写入值、单位、期间和显示面。未知或跨案 alias、原始百分比/金额和 placeholder residue 均拒绝。
- 原始响应先 capture 再解析/校验；失败输出和 rejected receipt 保留，但不得晋升 candidate。
- candidate freeze 前重新运行完整 evaluation，并要求所有 objective 有有效 receipt 且 `material_failure=false`。
- DELL R2 U3/U4 保存为去凭据的 immutable regression fixture；历史 R2 runner 因合同代际变化 fail closed，不能复用旧 authority。

## 2. 验证结果

- 聚焦 Runtime 与历史入口：`32 passed`。
- S2-05/S2-06 全部合同回归：`152 passed / 3201 deselected`。
- 覆盖 DELL/MU/NVDA full-fake、false closed、空反证、raw/unknown/cross-case numeric、拓扑变化、capture-first 与 exact-once。
- 模型、Provider、网络、admission、paid candidate：`0`。

## 3. 诚实边界

这证明新合同在当前工作树上确定性成立，不证明 clean-commit 可复现，也不证明 DeepSeek 会自然遵循。RC-P36-148 只能记为 implementation pass，必须等 S2-06C 独立复证后才可记 engineering repaired；研究内容质量、业务晋升和 release 均未成立。

## 4. 下一步

严格进入 `S2-06C`：在 clean commit 的两个独立 archive/process 中回放 U3/U4，并证明三案例 full-fake/mutation。只有 06C 全绿，才允许签发一次最小自然节点 canary；canary 后再做是否值得执行正式 DELL 监督证明的零调用决定。
