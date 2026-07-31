# FIN 0.1 分层 Agent 验收标准与 S3-T09 重审

日期：2026-07-25

## 本轮授权与边界

用户要求把“硬失败只保留给真实性、数据口径、引用、身份、权限和关键结构错误；字数、表达方式和叙事密度进入质量评分或受控编辑；模型输出判断原子，本地管理结构、ID 和 lineage；验收拆为结构完整性、证据可靠性、分析质量和用户适配性”写入概设与详设，并按新标准重新审查 S3-T09。只有 T09 真实通过时才允许放行下一步。

本轮只进行设计、合同与既有证据的只读重审。没有修改 runtime、签发 admission、调用模型/Provider/网络/来源/工具、回放 restricted capture、生成业务 Artifact、执行 paired comparison、写 owner acceptance 或进入 T10/S4。

## 新标准

新增机器合同 `fin01.agent_acceptance.layered_hard_integrity_and_quality:v1`，把验收分成：

1. L1 硬完整性：事实、证据、数字口径、范围归因、身份 lineage、权限安全、终态一致性和真实容量边界；违反时 fail-closed。
2. L2 可恢复协议：可安全保留并确定性修复的 schema、格式、枚举和表达问题；默认保留输出并路由最早 owner，只有出现歧义、身份猜测或真实容量耗尽时升级为硬失败。
3. L3 分析质量：决策相关性、因果、反证、gap、WWC、相对基线的实质增益；以 rubric 和 review disposition 管理。
4. L4 用户适配与交付：字数、语气、叙事密度、受众和视觉交付；以 profile、controlled edit 和质量债管理。

普通字符上限不再天然是 L1。只有它保护已证明的 transport、storage、security 或无法安全完成的 token/context envelope 时才是硬容量门禁。历史 canonical terminal truth 不改写；新标准改变的是重审分类和未来 runtime 行为。

## S3-T09 重审结果

最新 exact-live 的 Research Lead 返回合法 JSON/stop，全文 5,195 bytes，低于 8,192-byte Provider wire hard capacity。三条 dependency statement 的 571/533/528 和 aggregate 3,875/3,200 因未触发 transport/storage/security exhaustion，按新标准从 L1 硬失败改判为 L3/L4 质量发现。RC-P36-047 不应再单独作为 full-chain hard blocker，但 runtime 仍需后续零调用对齐，历史 failed 三态不能回写为 succeeded。

T09 仍不能通过：

- 当前 owner-grade final Run 在 Research Lead 后停止，Memo Writer/Verifier 未运行，Artifact=0，完整 L1 检查也未走完。
- 2026-07-22 的 output-v2 Run 虽 terminal succeeded 且有 9 个 Artifact，但独立审查发现公司总量 Numeric 被扩写为分部收入结论。这是事实 authority、scope 与 attribution 越权，在新标准下仍是 L1 硬完整性失败。
- 后续 Claim-Fact alias、typed Verifier、atomic terminalization、nullable owner 和 supervision-v2 已分别获得 fixture 或 live positive evidence，但它们分散在不同 Run；组件证据可以累计，不能拼装成一套从未由同一当前版本 Run 产生的完整产品。
- exact deterministic baseline 已存在，但没有一套当前 owner-grade 9 Artifact Agent 产品可供 paired comparison，owner acceptance 也未执行。

因此 S3-T09 保持 blocked，S3-T10 不放行。新的唯一下一项是 `S3-T09-LAYERED-ACCEPTANCE-RUNTIME-ALIGNMENT-ZERO-CALL-IMPLEMENTATION`；完成后仍需一条受独立授权的 coherent exact-live 生成 9 Artifact，再做只读四层比较与 owner acceptance。

## 产物

- `configs/releases/fin_ia_0_1_layered_agent_acceptance_standard_v1_0.json`
- `configs/releases/fin_ia_0_1_s3_t09_layered_acceptance_reassessment_v1_0.json`
- `tests/contract/test_fin_0_1_s3_t09_layered_acceptance_reassessment.py`
