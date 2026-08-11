# 720 — FIN 0.1.3 中段 PRD／TECH／Runtime／Product Evidence 对齐、反思与重排

日期：2026-08-08

状态：`alignment_complete / plan_rebased / no_runtime_or_external_execution / S0_04G_current_next`

## 1. 本项目标与权限

用户要求在当前中间阶段重新对齐 PRD、技术文档与实际项目进度，基于真实工程暴露的问题做一次项目反思，并重排下一步。该任务只允许只读审计、文档／账本更新、机器计划校准和 Git 收口；没有授权 network、model、Provider、formal admission、ranking、live 或 release。

审计基线为 clean/synced `cef5323db230138ebaf95f4e984542d46ccc5f5c`。当前最新直接证据包括：

- S1-08 P2C：clean Git archive/fresh Python process，10 个显式文件 `70 passed / 0 failed / 0 skipped`；
- DELL 最近 live：`16 network / 1 unique source / target-in-pool 0`；
- S2：deterministic correction guard pass，DeepSeek natural correction closure fail；
- S3：minimum engineering anchor only，无产品级内容质量通过；
- S4/S5：尚未在 FIN 0.1.3 current candidate 上开始。

## 2. PRD—TECH—Runtime—产品实证对齐结果

| 产品承诺 | 技术合同 | 当前实证 | 结论 |
| --- | --- | --- | --- |
| 可控、可复现、可追责 | exact-once、capture、permission、lineage | 失败证据和 clean proof 强；未知 state/scope 曾 fail-open | 控制骨架成立，shared governance 未收口 |
| Agentic Search | provider→candidate→ranking→promotion→utilization | v3 deterministic repair independently proven；live target-in-pool 仍为 0 | S1-08 未通过，ranking 不准入 |
| 模型研究判断 | provider-neutral contract＋profile | Harness 可拒错；DeepSeek natural closure 失败 | S2 只冻结能力 profile/autonomy，不宣称产品通过 |
| reviewer-ready 研报 | dynamic DecisionSurface、research methods、Workpaper/Report | 当前只有 minimum anchor 和历史薄内容投影 | S3 必须激活方法并过内容质量；S4 只做 current candidate |
| Internal Alpha | current dogfood＋RG1–RG5 | 0.1.3 S4/S5 未开始 | release blocked |

PRD 的数据来源、Agentic Search/Research、Evidence/Numeric、Workbench 和内容质量要求没有缩减；FIN 0.1.3 与 FIN 0.2 的版本定义没有改变。

## 3. 项目反思

### 3.1 做对了什么

- immutable failure、capture-first、exact-once、source SHA、clean archive/fresh process 和 typed gap 避免了“失败即丢失”和错误追责；
- 财务数值、日期、公司身份、引用和 promotion 权回到确定性控制面，避免模型幻写成为事实；
- 搜索、模型遵循、研究内容和产品验收已被拆成独立 failure domain，工具缺陷不再自动算模型缺陷；
- 用户多次纠正“结构绿灯不等于研报质量”后，八维内容质量和 qualified-human acceptance 已成为 release hard gate。

### 3.2 需要改进什么

1. **治理 proof 过度串行。** S1-08 从 implementation、authority、successor、preflight 到 projection 形成过多微步骤。它们保留了证据，但 P2C 通过后仍要手工 allowlist，说明 RC-P36-156 已成为交付瓶颈。
2. **工程成熟度和产品成熟度不平衡。** 当前更擅长证明链不乱、失败可追，而不够擅长证明资料找得全、判断有深度、报告对 senior 有用。
3. **方法 registry 被高估。** thesis-path、product-to-financial bridge、customer/supplier read-through 等多停留在 documented/contract；没有 runtime injection、node consumption、paid artifact 和 human acceptance，不能算产品能力。
4. **DeepSeek 适配曾过于字段化。** deterministic guard 有价值，但继续逐字段扩 Prompt/Validator 会形成 Provider 专用迷宫；应改为 capability profile、judgment atom、protected narrative 与有界 autonomy。
5. **固定九次调用被误当产品目标。** 九次只能证明最小 harness topology。真正研究预算应由开放 Cell、Evidence Slot、repair ticket 和 stop condition 决定。
6. **Workbench 曾先于内容成熟。** 页面投影存在，但通用 atom 和边界说明过多；S4 不应在 renderer 中补研究，而应等待 S3 substantive candidate。

### 3.3 为什么不是“偷懒降标”

新计划减少的是重复 authority/proof、字段级修补和无意义 full-chain，不减少 candidate recall、数值真值、Evidence promotion、研究内容或 human review 标准。节省的预算转向真正尚未通过的搜索覆盖、研究方法激活、内容质量和产品 dogfood。

## 4. 更新后的 S0–S5 归属

| 阶段 | 当前保留责任 | 出口 |
| --- | --- | --- |
| S0 | typed blocker state、versioned RunScopeRegistry、unknown fail-closed | RC-P36-156 关闭；P2D 注册 scope 可用，未授权 live 明确拒绝 |
| S1 | provider truth、candidate ceiling、ranking、promotion、current Evidence Pack | 三案 SearchQualityCard 可解释；失败有 provider/product-scope 决策 |
| S2 | ModelCapabilityProfile、DeepSeek profile、AutonomyGrant、最小 family canary | 当前模型动作面冻结，不逐字段 repair |
| S3 | 动态 research、method-to-runtime、EvidenceRequest/repair、内容质量 | 三案 substantive artifact、八维门、paired gain、human acceptance |
| S4 | current Workbench dogfood、repair/review/trace、review burden | 同一 exact Case 完成 analyst/senior workflow |
| S5 | RG1–RG5、rollback、known gaps、版本决策 | close／conditional／blocked |

## 5. 新执行顺序与止损

1. 当前唯一下一项：`FIN_0_1_3_S0_04G_TYPED_BLOCKER_STATE_AND_RUN_SCOPE_REGISTRY_MINIMUM_ZERO_CALL_IMPLEMENTATION`。
2. S0-04G 通过后才执行 P2D；P2D 通过后，以独立 Attempt 执行唯一 DELL R3，预算仍为 `<=16 network / 0 model-provider-retry / no R4`。
3. R3 pass：复用共同 transfer contract 验证 MU/NVDA，随后才准入 ranking/Evidence Pack。
4. R3 fail：禁止 R4，转为运营 Provider、受控动态页/站内搜索、licensed source 或缩小 Internal Alpha source claim 的产品决策。
5. 冻结 Evidence Pack 上完成 DS-A1/A2/A3；该准备可与 S1 transfer 有界并行，两者在 S3 join。
6. S3 激活研究方法并完成三案 Experiment B；S4 只消费内容合格 current candidate；S5 最终裁决。

普通 deterministic change 不再机械拆成四轮 proof。只有权限、成本、外部副作用或可移植性真实改变时才单独做 authority/clean proof。同一 model contract family 最多一次结构修订和一次自然 canary。

## 6. Durable 更新

本项更新：

- 产品源：PRD 第 16 节；
- 版本计划：FIN 0.1.3 主计划新增 7C 并重写 current next；
- 技术源：TECH_00A、TECH_02、TECH_06、TECH_09、TECH_10；
- 机器计划：`fin_ia_0_1_3_prd_tech_runtime_mutual_alignment_and_replan_v1_0.json`；
- Project OS：current context、root-cause projections、capability projection；
- 工作记录：本文件、Worklog README、内部 checklist。

## 7. 本项明确未执行

- 未修改 `src/`、`scripts/`、Runtime contract 或测试；
- 未运行单元／集成／full-chain 测试，因为本项没有 Runtime 变更；
- 未访问外部来源；
- 未调用 DeepSeek、OpenAI 或其他模型／Provider；
- 未签发或消费 formal admission；
- 未执行 P2D、DELL R3、ranking、MU/NVDA transfer、S3、S4 或 S5。

本项只在 JSON/JSONL、文档引用、Project OS scoped preflight 和 Git hygiene 层做验证。

## 8. 验证结果

- machine replan JSON：parse pass；
- root-cause ledger：`1030` 行逐行 JSON parse pass；
- capability ledger：`723` 行逐行 JSON parse pass；
- Project OS scoped preflight：新 S0-04G scope=`pass`；旧 P2D scope=`blocked`；direct DELL R3 issuance/execution scope=`blocked`；
- `git diff --check`：pass；
- 未运行 Runtime test suite，原因是本项没有 `src/`／`scripts/`／Runtime contract 变更。
