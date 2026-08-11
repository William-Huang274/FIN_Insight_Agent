# FIN 0.1.2 S3-T03：NVDA primary exact-live terminal failure

日期：2026-08-04
状态：`immutable failed / admission consumed / zero-call disposition pending`

## 结论

用户新的“继续”满足 R2 的独立续行条件后，唯一 primary admission 已通过 bound parent supervisor exact-once 消费。真实链没有成功产出九件套：6 个 Specialist Provider segments 完成后，第 7 次 Research Lead 调用返回正常 JSON 和 `finish_reason=stop`，但本地语义校验以 `s3_bounded_research_lead_v3_semantic_fact_presence_summary_mismatch` typed terminal 停止。

本轮没有自动重试、fallback、replay、relaunch 或 replacement，也没有 paired assessment、Owner acceptance 或 S3-T04。失败输出已隔离，不能作为金融事实或业务 Artifact 使用。

## 执行数据

- execution identity：`fin012-s3-t03-nvda-primary-r1`。
- parent/child：parent 正常收口；child exit=2；timeout=false；launch failure=false；wall clock=63.172 秒。
- local Fact receipts / captures / Artifacts：`3 / 7 / 0`。
- calls：Specialist 6，Research Lead 1，Writer 0，Verifier 0。
- tokens：input `37,107`；output `2,310`；total `39,417`。
- 估算成本：USD `0.01815124`，低于 USD `0.06` ceiling。
- 每次 transport attempt=1；所有 Provider finish reason=`stop`。
- retry/fallback/replay/relaunch/replacement=`0/0/0/0/0`。
- result SHA：`09a0bf6b…11c`；terminal object digest：`7c6847f2…a221`。
- credential、private reasoning、raw Provider response 均未持久化。

## 失败到底是什么

真实 Claim alias 的 direct Fact 数量是：C001=0、C002=0、C003=3、C004=0。Research Lead 却把 C003 的三份 Fact 和 bounded-inference 语义多处写到了 C002：

- C001+C002 被写成 `mixed_fact_presence`，确定性真值应为 `no_facts_present`；
- C002+C004 也被写成 `mixed_fact_presence`，确定性真值同样应为 `no_facts_present`；
- dependencies、conflict narrative 和 gap narrative 里也出现 C002/C003 的相同语义互换。

所以模型确实发生了字段级 semantic alias error；这不是网络、鉴权、JSON、截断或预算问题。

## 为什么项目负主要责任

`fact_presence_summary` 完全可以从每个 involved Claim 的 `support_fact_ids` 本地计算。FIN 0.1 S4-T06 的 RC-P36-078 已经通过 Lead-v7 把该字段收归本地，并完成过 exact-live 正证明；但 FIN 0.1.2 当前 admission 又绑定 Lead-v6，使 Provider 重新生成该字段。

这说明版本整合只对了局部 v1.3 family，却没有检查“历史上后来已经证明的 ownership boundary 是否全部继承”。因此这不是简单的“DS 又不听话”，而是直接模型错误叠加项目合同继承回归。只把 enum 本地补正确也不够，因为本次输出的 C002/C003 narrative 同样互换。

## 阶段边界与建议

登记 `RC-P36-108`，仍归 S3-T03；S0-S2 不重开，产品版本不变。下一项只做一次零调用处置：

1. 对账 FIN 0.1.2 当前合同与 Lead-v7 等后来已证明资产，建立不可丢失的 capability-inheritance 检查；
2. 为同一 cell 相邻 Claim 增加 permutation 负例；
3. 决定最小的本地 Claim semantic projection 或有限 Claim-role atom，使 dependencies/conflicts/gaps 不再依赖模型自行记住 C002/C003 的支撑身份；
4. 不允许逐字段 prompt patch，也不自动签发 replacement admission。

当前 next：`FIN-0.1.2-S3-T03-NVDA-RESEARCH-LEAD-LOCAL-FACT-PRESENCE-AND-CLAIM-ALIAS-SEMANTIC-OWNERSHIP-REGRESSION-DISPOSITION-DECISION`。

## 持久证据

- tracked result：`configs/releases/fin_ia_0_1_2_s3_t03_nvda_exact_live_execution_terminal_failure_result_v1_0.json`
- current projection：`configs/runtime/fin_ia_0_1_2_current_program_projection_v2_29.json`
- restricted runtime：`.codex_runtime/fin012-s3-t03-nvda-primary-r1/`
- supervision：`.codex_runtime/fin012-s3-t03-nvda-primary-r1-supervision/`

Runtime 原始请求与最终 assistant 输出保留在受限 content-addressed captures 中；Git 只提交脱敏的结构化摘要、哈希与处置边界。

## 回归验证

- terminal/result/projection/ledger 专属审计：`5 passed`；
- terminal failure、R2 authority、launcher/supervisor、issuance、post-admission 组合生命周期：`38 passed`；
- 相邻 T02 production runtime、T03 conditional authority、fresh identity runner 首轮：`18 passed / 1 historical-current-state assertion failed`；唯一失败是历史 authority 测试仍永久要求 `execution_started=false`；
- 将该历史断言改为只接受明确的 tracked terminal successor 后，authority 文件复证：`6 passed`；未修改 Runtime、admission、失败 output 或产品门槛。
