# 824 — FIN 0.1.3 S2 数字展示与紧凑 Verifier 修复／clean proof

日期：2026-08-10

状态：S2 deterministic structure independently proven；未授权新 live

## 为什么旧 DELL 报告不能直接通过

旧 Final Writer 已形成 8 章、33 个判断点，但数字合同要求模型既引用 `NUM/FORM`，又额外选择语义重复的 `PRES`。DeepSeek 实际正确使用了 26 个 NUM 与 12 个 FORM，却没有再选 PRES，导致合法中文尺度换算被重复报错；numeric inventory 同时漏了 TSMC 77%，tokenizer 还把 `FY27` 尾数识别为数字。Verifier 则需要重抄全部 claim，最终在 4,000 output tokens 以 `finish_reason=length` 截断，没有形成合法终审。

## 本次结构修复

- 模型继续选择事实／公式 authority，Harness 根据封闭 presentation program 确定性验证等价展示；未知数字、错期间、错单位和自由 arithmetic 继续 L1。
- source numeric inventory 增至 14 条，TSMC 77% 绑定 E015；财政年度标签不再产出 material numeric token。
- Verifier 改为稳定 claim ID 的 compact view，输出仅含 claim_id、status、finding_codes 和 bounded reason；原文由本地 ID 回接。
- `finish_reason=length`、截断 JSON、重复／未知／缺失 claim verdict 均为 hard `verification_incomplete`。
- Verifier 只读取所选 Evidence、source excerpt、gap、numeric fact 与 formula，不再把完整 source universe 塞入输出合同。

## 证明结果与边界

保存的 Final Writer 回放得到 `36/36` material surfaces 确定性绑定、repaired findings=`0`；compact fixture=`3,076 chars／33 claims／0 finding`。两个 fresh Git archive worker 在 credential scrub、socket/DNS blocked 条件下逐字节一致，proof digest=`48968cda86bdd213bc381876a4d47b6c36ffd77d28a0424df9083082158117b3`。全 S2 contract 回归=`206 passed / 3733 deselected`。

这证明 S2 数字／Verifier 结构，不新增 S1 资料，不修 S3 因果、WWC 或密度，也不把旧 raw report 晋升。下一责任是 S1 对 DELL 做有界定向补源，然后重新编译完整新输入；Evidence Pack 改变后不能复用旧模型节点。
