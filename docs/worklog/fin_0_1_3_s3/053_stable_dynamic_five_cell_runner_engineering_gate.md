# 053 S3 稳定动态五单元 runner 工程门

日期：2026-08-17

## 目标

把已经通过资格化的五个研究单元真正接成一条可审计的完整 DELL 执行链，同时避免复制五份单单元 runner、避免某个单元失败后遮住其余问题，也避免 Harness 在模型之外拼出一份看似完整的报告。

## 本轮实现

1. 新增稳定五单元 Runtime。五个单元分别获得 cell-local Evidence、NumericFact、relation、RoleMethodPack、GraphContextPack 和 gap；分析草案不具有业务权威，最终 Judgment 必须经同一严格合同提交。
2. 新增跨单元综合合同。只有五个单元均通过后才允许综合；综合只能选择已由五个 Judgment 使用的 ref，并禁止自由数字、未知引用、自连接和缺单元。
3. 新增稳定 live runner。一次 planner 和当前 S1／S2 后，依次运行五组“分析＋交卷”；某单元失败仍继续后续单元。完整成功预算为 13 次模型调用，0 retry、0 fallback、0 protocol switch、0 external source network、0 product publication。
4. 私有 full result 保存模型可见输入、最终输出与逐阶段失败；公开 result 只保留 capture ref、digest、usage、失败码和验收状态，不保存模型正文、Tool 参数或私有 reasoning。
5. 修复 per-cell 审计 receipt 泄漏：原正文虽只给当前单元，但 selection 元数据仍列出全部五单元；successor 现在只保留当前 cell 并重算 digest。
6. 新建 DELL 五单元 objective，显式允许当前对象库和 reviewed Pack 已资格化的官方法说 transcript。旧 SEC-only objective 未修改。

## 验证结果

- 定向 Runtime／runner／consumer：`59 passed`。
- 全仓：`411 passed`。
- `python -m compileall -q src scripts tests`：通过。
- active baseline：`133 Python / 8 frontend / 10 Runtime resources / 0 forbidden reference`。
- 成功 fake 路径：1 planner＋5 analysis＋5 submission＋1 synthesis analysis＋1 synthesis submission，共 13 次；五单元和报告均物化。
- 单元失败 fake 路径：仍运行 5 个分析和 5 个交卷，接受 4 个 Judgment，跳过综合，partial terminal result 与失败码仍物化。
- 当前 S1／S2 的零模型预回放：旧自然 10 atoms 只作为测试形状并重新绑定新 objective；稳定选择 8、延期 2，执行 8 个 EvidenceRequest，6 个请求返回 8 条已审 Evidence，106 个未审候选保持未晋升，10 个 typed gap 保留。五个单元分别获得 `4/1/2/2/1` 条 Evidence；经营、价值捕获、现金单元分别获得 `12/8/10` 个 NumericFact。旧 planner 的 objective ID 原样复用会 fail closed，真实 live 必须重新规划。
- 本轮模型调用、Provider 调用、外部网络和产品发布均为 0。

## 边界与下一步

这是 runner engineering pass，不证明 DeepSeek 自然五单元质量，也不证明完整研报、泛化或 S3 acceptance。下一步须另做正式零调用 proof；通过并 clean commit／push 后，才能签发 fresh exact-once authority。自然 live 完成后仍必须分别做金融 L1、逐单元质量、跨单元综合、八维绝对质量、paired gain 和 qualified-human 内容验收。
