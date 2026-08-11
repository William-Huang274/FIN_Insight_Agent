# FIN 0.1.2 S4-T04 R3 exact-live 与独立产品验收

日期：2026-08-04

结论先行：唯一 R3 exact-live 已成功，正式生成九件 Artifact，独立 L1 通过，RC-P36-117 以 live positive evidence 关闭；但 T04 还不能作为产品验收通过，因为独立检查发现最终交付表面 L4 失败。没有执行 R4、重试、paired assessment 或 owner acceptance。

R3 共完成 9 次 DeepSeek Pro 调用、9 份 capture、3 份本地 Fact receipt 和 9 个正式 Artifact。累计 input/output 为 55,906/3,038 tokens，成本 USD 0.02696216；所有调用 finish reason 为 `stop`，每次 transport 只尝试一次。Verifier input 从 R2 的 19,726 降至 12,578，全链 input 也从 63,419 降至 55,906，容量问题未复发。

独立 L1 检查确认：terminal success、Artifact 集合完整、六条 Claim、九项 WWC、Lead 的 1 dependency/2 conflicts/3 gaps、capture-first、三份本地 receipt、无 DELL/MU 跨案污染、无凭据或 private reasoning 持久化均成立。

但机器 Verifier 的四层自报 pass 不能直接等同于产品验收。最终本地 report 仍显示 `__company_total__`、`FY2025-FY` 等内部标识，出现 `USD 130497000000 USD` 这种重复币种单位，中文 limitations 中残留英文句子；更关键的是 Verifier 只绑定 Writer/Lead digest，没有绑定本地最终渲染后的 delivery preview。因此它实际上没有看见并验证用户最终拿到的表面。

该缺口登记为 RC-P36-118，归 S4-T04 最终产品表面与验收绑定，不归因 DeepSeek。下一步不需要新模型调用，也不应重跑 exact-live；先零调用决定并实现一个有界本地 renderer 收敛和 final-preview digest Verifier binding，再从已保存的 R3 九件套重渲染并做 paired L1-L4。只有 paired 通过且 owner 明确接受，才能把 current source-grounded NVDA R2 记为 true 并进入 T05。
