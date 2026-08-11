# FIN 0.1 S4-T05 R9 profile-result validation lineage 根因处置

日期：2026-07-28

范围：`S4-T05-DELL-R9-PROFILE-RESULT-VALIDATION-AFTER-SIX-NODE-COMPLETION-FIRST-CREDIBLE-FAILURE-ZERO-CALL-ROOT-CAUSE-DISPOSITION-DECISION`

## 结论

RC-P36-066 已从通用 `profile_result_validation` phase 收敛到确定性项目内合同漂移：

- R9 profile-v3 的 S4 input builder 本地生成五个 lineage key：
  - `S4_T02_case_pack`；
  - `S4_T02_method_contract`；
  - `S4_T03_runtime_binding`；
  - `S4_T04_source_grounded_input`；
  - `S4_research_profile_overlay`。
- trace Artifact 直接使用 `input_pack.lineage`；Provider 不生成、选择或修改这些 key/digest；
- post-Verifier `_validate_s3_three_cell_bounded_agent_result` 对所有共享 three-cell profile 无条件要求旧 S3 `T02...T07` 六键；
- 以 R9 公开 admission/profile binding/source pack 和 content-free synthetic nine-Artifact shape 走完此前 profile-result gates，精确重现：

`s3_bounded_agent_T02_T07_lineage_missing`

因此本轮失败不是 DeepSeek 指令不遵循，也不需要读取 restricted Provider text。

## 证据边界

来源：

- R9 failure result SHA=`3508fb3d068768e03d430a42b2b3f136a0b2b6d86a4ba401513a9c392e36226a`；
- R9 admission SHA=`05592e970cd1646a31c43a5e37ed0896eb2733dc818266859dc91c283241bb2c`；
- bounded executor SHA=`a7f4f145f622e720232ba7a4e8a2fecc20e71124fd921d9bcddd73002d77a0de`；
- research runtime SHA=`592e1255f9c4ef962495b01cb9f8a770ffbf2c8e03999a47ce69b926486c73fb`；
- S4 case runtime SHA=`98ba0973765321b98a12bb092fbb007e7e5657179e1b5d7c0fe6fad6125350a2`。

没有读取：

- R9 restricted captures；
- raw Provider response；
- assistant final text；
- private reasoning；
- credential；
- stack 或 raw live exception。

零调用审计脚本前两次分别因未注入 repo import path、用未初始化 receiver 调用实例方法而在目标 validator 前退出；两次都没有模型、Provider、网络、canonical 或业务写入。第三次无初始化 I/O 的 runtime object 重构命中上述 exact subtype。

## 选择的结构性合同

选择：

`fin01.bounded_agent.profile_aware_artifact_lineage_validation:v1`

未来最小实现应：

1. 由共享本地 policy 按实际 lineage family 生成并验证 exact key set：
   - legacy S3：T02–T07 六键；
   - S4 base：case pack、method contract、runtime binding、source-grounded input 四键；
   - S4 versioned research profile：在 base 上强制 overlay 第五键。
2. manifest 本地记录 lineage contract ref 与 canonical lineage digest；trace digest 必须一致。
3. S4 lineage 中 runtime binding、method contract、research profile/overlay refs 与 digest 必须和 S4 case-runtime projection 一致。
4. unknown、missing、extra、cross-family、wrong digest 或 overlay mismatch 保持 L1 hard failure。
5. profile validator 使用 allowlisted content-free subtype；保留 12 receipts/captures 与 6 node receipts，但不保存 Provider text、字段值、credential、stack 或 raw exception。
6. 不新增 Specialist/Lead/Writer/Verifier transport version，不修改历史 admission/Run。

## 拒绝与后传

- 不删除 lineage gate，也不把它降级成质量 finding；
- 不把正确 S4 lineage 伪装成旧 S3 T02–T07；
- 不增加 DELL/R9 company-specific bypass；
- 不检查 restricted R9 text 或猜模型字段；
- dependency/conflict、Writer/Verifier atomization 与全节点重构继续后传 S4-T10→S5。

## 状态

- RC-P36-064：live observability 正证据已关闭；
- RC-P36-065：profile-v3 capacity live path 已关闭；
- RC-P36-066：root cause disposed，等待独立授权 minimum zero-call implementation；
- R9：consumed/failed/immutable，不允许第二次执行；
- Artifact=0，DELL R2=false；
- paired/Human/S4-T06/S5/release/production 均未进入。

机器决策：

`configs/releases/fin_ia_0_1_s4_t05_dell_r9_profile_result_validation_after_six_node_completion_zero_call_root_cause_disposition_v1_0.json`

SHA256：

`b520fecd4b68dbc77bfe78e0e5d1191a0b6c2a113607c0e3db9a5f98e28d8b21`

下一项唯一为：

`S4-T05-DELL-R9-PROFILE-AWARE-ARTIFACT-LINEAGE-VALIDATION-AND-TYPED-SUBTYPE-MINIMUM-ZERO-CALL-IMPLEMENTATION`

本轮不授权 implementation、fresh proof、admission、model call、rerun、paired 或 S4-T06。

## 收尾验证

- decision、program backlog、S4 detailed backlog 均通过 JSON parse；
- capability/root-cause 两份 append-only JSONL 全行通过 parse；
- decision SHA256 重算=`b520fecd4b68dbc77bfe78e0e5d1191a0b6c2a113607c0e3db9a5f98e28d8b21`；
- RC-P36-064 typed envelope、RC-P36-065 capacity、R9 issuance/authority/result 与本 disposition 相邻合同测试=`32 passed`；
- 下一项 implementation scope Project OS preflight=`pass/open blockers 0`；
- preflight output=`.codex_runtime/s4_t05_dell_r9_profile_aware_lineage_implementation_project_os_preflight.json`；
- 本轮真实 model/Provider/network/source/tool call、restricted capture read、runtime patch、admission、Run、Artifact、paired、Human review 均为 0。
