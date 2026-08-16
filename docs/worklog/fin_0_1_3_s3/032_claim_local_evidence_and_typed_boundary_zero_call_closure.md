# S3 claim-local Evidence 与 typed boundary 零调用闭环

时间：2026-08-16

## 这轮解决的业务问题

FFJ-R3 已让 DeepSeek 自然交出 DELL `value_capture` 的三部分判断：产品盈利目标、利润机制、反方与 what-would-change。内容本身保持克制，但终局没有形成。原因不是模型又写错，而是项目把“同一来源在整份报告中的用途”当成一个全局标签。

Dell 法说在产品目标中是直接支持；在产品到公司利润机制中只能是上下文。旧代码要求二选一，导致三个片段都完成后整条失败。随后 replay 还发现，系统只承认网页式 limit，却不承认“当前没有利润桥”的 typed gap 和同口径公司毛利反向关系也是有效边界。

## 实现边界

- 每个 claim 保留自己的 `evidence_uses`；
- terminal summary 由本地确定性汇总，但不产生权限；
- required support 逐 claim 校验，禁止从报告其他位置借用；
- `bridge_not_established`／open typed gap 可提供跨层因果边界；
- 同 scope、同 basis 的 NumericRelation 可提供 counter boundary；
- boundary 不得升级成 support，Harness 不写研究观点。

## 证明结果

保存的 FFJ-R3 三个 Tool payload 原样 replay 后形成：

- `judgment_status=bounded_support`；
- `inference_authority=bounded_inference`；
- `claim_scope=multi_scope`；
- `financial_scope=multi_scope_financial`；
- `causal_bridge_authority=multi_driver_context_only`。

边界来源恰为 `typed_bridge_gap_relation` 和 `typed_same_scope_counter_relation`。模型文字逐字保留，`harness_generated_research_judgment=false`。

负向 mutation：

- 全局 support laundering → `claim_surface_required_authority_missing`；
- 删除 typed boundary → `claim_authority_multi_driver_boundary_missing`。

formal v1.3 proof 在 Provider 前失败，因为证明脚本把历史 v1.1 research input digest 与 R3 v1.2 policy 混入同一 lane。该失败没有模型、网络或产品输出，并保持不可变。v1.4 把历史 micro lane 和 R3 terminal replay lane 分开，两个 fresh process 字节等价，result digest 为 `b03de3f021cb6692db98b4485adaa770b50786a463de40f281d4684b353d0d3d`。

## 不能提前宣称的能力

这轮只关闭项目终局合同缺陷。FFJ-R3 仍是失败 attempt，未被 salvage；自然 FFJ-R4、完整 fixed-Pack 第一层、动态 EvidenceRequest→S1/S2→EvidenceResponse、DELL 五单元、异质泛化和 S3 acceptance 均未通过。

## 下一步

同步 PRD、架构、Project OS 和账本；全仓回归、clean commit/push 和真实 Project OS preflight 后，签发一个 fresh FFJ-R4。其范围仍是同一 DELL fixed Pack、6 次模型调用、3 次 fragment submission、0 EvidenceRequest、0 retry／fallback。R4 通过 L1 和内容门后，才进入 Research Truth Spine。

## 提交前复证

- claim-local／preflight／canonical runner 定向测试：`67 passed`；
- 全仓测试：`339 passed`；
- Python compileall：通过；
- active baseline：`127 Python / 8 frontend / 10 Runtime resources / 0 forbidden reference`；
- repository secret scan：`6,652 files / 0 finding`；
- 两份 Project OS JSONL 账本逐行解析通过；`git diff --check` 通过。
