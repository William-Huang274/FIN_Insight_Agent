# 059 — DELL 五单元紧凑分析与部分节点 successor 正式门

时间：2026-08-17
阶段：FIN 0.1.3 / S3
前序：R2 保持 `terminal_failed_or_partial_no_retry`，需求质量与经营表现两个 Judgment 有效；价值获取、现金转换、反方证据在分析阶段失败，综合未执行。

## 为什么不是继续提高 token

R2 的三次失败都取得 HTTP 200，并用满 8,000 completion token。两次全部被隐藏推理消耗，另一次只产生被截断的可见草案。保存请求表明，分析节点仍看见不可执行的严格交卷 schema、重复目录和完整来源 route 诊断。直接把 8,000 改成 16,000 只能增加费用，不能证明这些重复信息是必要的，也会把 DeepSeek 的当前行为固化进核心合同。

本轮先修共享责任层：由 canonical current consumer 编译一份 analysis-only 视图。它保留全部 reviewed Evidence、NumericFact、same-basis NumericRelation、RoleMethodPack、current-case GraphContextPack 和 typed gap，只移除交卷步骤才需要的 schema、动态传输诊断和重复提交说明。五单元字符减少分别为 36.5%、19.5%、26.9%、28.1%、42.1%。DeepSeek GA 16,000/max-thinking 仍只是可替换 profile；金融核心没有新增 Provider 分支或全局 token 规则。

## 节点恢复如何避免重复造 runner

没有新建 R3 runner。现有 `run_s3_dynamic_five_cell_live.py` 增加一个由 fresh authority 提供的 resume manifest：

- `reused_cell_ids` 指定已验证节点；
- `remaining_cell_ids` 指定允许新执行的节点；
- 两组集合必须不重叠且完整覆盖五个单元；
- 复用前会把 R2 原始 Tool arguments 在当前 research input 下重新运行 Validator，并核对 Judgment digest；
- 只给 remaining 节点和综合分配新的 attempt ID；
- 五个 Judgment 未全部有效时仍禁止综合。

Project OS 的 scope validator 继续精确绑定本次 DELL/R2 事实和失败码。这是资格审计，不是执行循环中的 per-cell 业务分支。以后若需要新的节点恢复，应继续使用同一 manifest 能力，不能复制 attempt runner。

## 正式零调用结果

绑定实现提交：`fecc4fedb9930b421a1fa272f585314f2d1ed540`

- proof：`configs/research/evals/fin_ia_0_1_3_s3_dell_dynamic_five_cell_partial_successor_zero_call_result_v1_0.json`
- proof digest：`1c421d34eae324d68593c50709d36ad7d15368853240bc132314f4fb4aeeb2e8`
- 两个独立 fresh process：`102 passed` + `102 passed`
- 全仓：`423 passed`
- compileall：pass
- active baseline：133 Python / 8 frontend / 10 Runtime resources / 0 forbidden reference
- secret scan：6,782 files / 0 finding
- fake partial successor：0 Planner、0 S1/S2、复用 2 个 Judgment、3 次分析、3 次严格交卷、1 次综合分析、1 次综合交卷，共 8 次新调用，0 retry/fallback/network/promotion/publication

scope decision 只允许：

`one_DELL_dynamic_five_cell_partial_successor_failed_three_plus_synthesis`

它不允许重跑 Planner、S1/S2、需求质量、经营表现，不允许新 Evidence、Responses／Anthropic 协议切换、MU/NVDA 泛化、Workbench 发布或 S3 acceptance。

## 停止规则

若自然 partial successor 再次出现同类 hidden-reasoning／visible-output budget failure，保留该 attempt，并转为以下三选一的项目级决策：

1. 改变 DeepSeek profile；
2. 进一步缩小模型分析动作面；
3. 调整分析模型与严格提交职责分工。

不得自动创建第三个 capacity patch，也不得把 token 上限继续逐轮抬高。成功运行后仍需独立完成完整五单元金融 L1、八维内容质量、paired gain 和 qualified-human 内容验收；本工程门没有提升任何产品发布状态。
