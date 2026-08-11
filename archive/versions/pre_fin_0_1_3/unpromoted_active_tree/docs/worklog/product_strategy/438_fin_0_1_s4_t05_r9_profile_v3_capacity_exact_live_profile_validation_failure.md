# FIN 0.1 S4-T05 R9 profile-v3 capacity exact-live profile validation failure

日期：2026-07-28

范围：`S4-T05-DELL-R9-SPECIALIST-VALIDATED-SEGMENT-UNION-CAPACITY-EXACT-LIVE-EXECUTION`

## 结果

R9 admission 已 exact-once 消费，并通过 supervision-v2 自行收敛至一致终态：

- WorkUnit=`failed`；
- Attempt=`failed`；
- ResearchRun=`failed`；
- orphan=false；
- Artifact=0；
- runner exit=0；
- retry/fallback/replay/relaunch/patch/rerun=0。

由于没有 coherent 九 Artifact success，paired assessment 未执行，DELL R2 未证明，S4-T06 未进入。

机器结果：

`configs/releases/fin_ia_0_1_s4_t05_dell_r9_specialist_validated_segment_union_capacity_exact_live_execution_failure_result_v1_0.json`

SHA256：

`3508fb3d068768e03d430a42b2b3f136a0b2b6d86a4ba401513a9c392e36226a`

## 执行输入与边界

- admission digest=`e7b98ed203087c926e33e7e71f3e5d4d0fe5cc16df57307105fdb85679491b43`；
- profile=`fin01.s4.research_profile.dell_oem_three_cell:v3`；
- capacity contract=`fin01.s3.specialist_local_assembly_capacity.validated_segment_union_upper_bound:v1`；
- provider/local/whole caps=`6000/8192/24576`；
- model=`deepseek-v4-pro`；
- input digest=`f9868c5d7daa051adfccba1c1d2de9c1209d6781bfa76c4569aee76d640e230d`；
- WorkUnit=`wu_p02_5_0f6c8d74d2a47a5a98ffe58b`；
- Attempt=`attempt_fin01_ad16ed80b2ed788d3924c614`；
- Run=`research_run_fin01_6566beb727cded66f3d54ead`。

执行前：

- R9 authority tests=`4 passed`；
- Project OS scoped preflight=`pass/open blockers 0`；
- exact runner disposable-clone preflight=`pass_exact_zero_call_execution_preflight`；
- target counts=`7/7/7/0` 前后不变；
- credential 只确认 presence，值未读取、输出或持久化；
- Provider health probe=false；
- retry environment=0；
- supervision root fresh/absent。

## Provider 与节点结果

- model/provider/network calls=`12/12/12`；
- transport attempts=12；
- 全部 status=`ok`；
- 全部 finish reason=`stop`；
- input/output/total tokens=`68,854 / 6,574 / 75,428`；
- estimated cost=`USD 0.02832713`；
- summed Provider latency=`82,730 ms`；
- usage receipts=`12`；
- restricted captures/readback=`12/12`；
- source network/external tool/live business head writes=`0/0/0`。

六个 logical node receipt 全部保留：

1. Demand Specialist；
2. Value/Profit Specialist；
3. Bottleneck/Counterevidence Specialist；
4. Research Lead v6；
5. Memo Writer v3；
6. Verifier。

三个 Specialist 均在 profile-v3 capacity contract 下完成，证明 RC-P36-065 的历史 whole-union capacity 阻断没有复发。Research Lead、Writer 和 Verifier Provider call 也均完成。

## 首个可信失败

- issue=`RC-P36-066-s4-R9-profile-result-validation-failure-after-complete-six-node-execution`；
- phase/stage=`profile_result_validation`；
- code=`s3_bounded_profile_result_validation_failed`；
- terminal reason=`bounded_agent_profile_error:BoundedAgentExecutionError:profile_result_validation`。

typed failure envelope 保存了 6 个 completed-node receipts、12 个 usage receipts/captures 和完整调用计数；未把 raw Provider response、assistant text、private reasoning、credential、stack 或 raw exception message写入 tracked result。

当前证据只提供通用 profile validation code，没有具体 subtype、offending Artifact 或字段。因此本轮不能证明：

- DeepSeek 指令不遵循；
- 某个 Provider 输出字段有错；
- 某个本地 assembly/validator 一定有错；
- RC-P36-066 的结构性方案。

必须在下一项零调用处置中审计当前 profile validator、deterministic fixtures 与受限输出的安全 shape，定位最早 owner；不得猜字段后 patch。

## 运行证据

- runtime result SHA=`3f27db200959a8612aa90a5791a888d120929b0f197f76b2eb31afddecc2dfb2`；
- terminal inspection SHA=`6bf9bd463a32ad2c08e625c49f90953d2f154796feedb42aea0b1e88e4f2658e`；
- launch receipt SHA=`0a2ffa33c995a8a80c2a75d431d680e23e5d2c7deb7b4764b45fcb5543acd0af`；
- exit receipt SHA=`89c50f9bfb384ee53951bb3892e3bebf6e631a2abdae63bde4399cd6a4a7d878`；
- inspection additional model/provider/network calls=`0/0/0`；
- monitor mutations/signals=`0/0`。

第一次只读 status 调用遗漏 runtime/issuance 参数而由 CLI 本身退出；独立 runner 未受影响。随后所有 status 均使用完整 binding，只读且无信号。

## 状态与下一步

- RC-P36-064：typed post-provider failure observability 已获得穿过 Verifier 到 profile validation 的 live 正证据；
- RC-P36-065：profile-v3 capacity repair 已获得 live path 正证据，在新下游失败前关闭；
- RC-P36-066：open，等待零调用根因处置；
- paired/owner acceptance/S4-T06/S5/release/production：均未进入。

下一项唯一为：

`S4-T05-DELL-R9-PROFILE-RESULT-VALIDATION-AFTER-SIX-NODE-COMPLETION-FIRST-CREDIBLE-FAILURE-ZERO-CALL-ROOT-CAUSE-DISPOSITION-DECISION`

该项只能做零调用证据和代码审计，不得 patch、签新 admission、rerun、paired 或进入 S4-T06。dependency/conflict、Writer/Verifier atomization 和 general all-node redesign 仍后传 S4-T10→S5。

## 收尾验证

- failure result、program backlog、S4 detailed backlog 均通过 JSON parse；
- capability/root-cause 两份 append-only JSONL 全行通过 parse；
- failure result SHA256 重算仍为 `3508fb3d068768e03d430a42b2b3f136a0b2b6d86a4ba401513a9c392e36226a`；
- typed envelope、R8 capacity implementation/proof、R9 issuance/authority/result 相邻合同测试=`27 passed`；
- RC-P36-066 零调用处置范围 Project OS preflight=`pass/open blockers 0`；
- preflight output=`.codex_runtime/s4_t05_dell_r9_profile_result_validation_disposition_project_os_preflight.json`；
- 未执行新的 model/Provider/network call、patch、admission、rerun、paired 或 S4-T06 动作。
