# Model Run：MU DeepSeek Pro Fact candidate cardinality failure

## Summary

- Run ID：`20260731_fin_ia_0_1_s4_t06_mu_deepseek_pro_fact_candidate_cardinality_failure_r1`
- Purpose：执行独立零调用复证后的唯一一次 replacement MU exact-live
- Status：`terminal failed / Fact candidate pool cardinality L1`
- Run type：inference
- Timestamp：2026-07-31 00:43:09–00:43:35 +08:00
- Provider/model：DeepSeek / `deepseek-v4-pro`

## Inputs And Boundaries

- Case：MU，as-of=`2026-07-26T00:00:00Z`
- Input digest：`7887b5bb447fc6a844c410751f2038a04a1c0b04dbbe7e5bde41b040135a12e1`
- Admission digest：`8efb005c4c0e519ff805c3b6c8d997cd146a7c8ed5ec6f6335ea167ba4033f40`
- Candidate contract：Provider maximum=6；local final maximum=3
- Retry/fallback/replay/relaunch/rerun：全部 0
- Source network、external tools、live business head writes：disabled

## Result

- Terminal states：`failed / failed / failed`
- Completed nodes / calls / captures / Artifacts：`1 / 4 / 4 / 0`
- Calls：semantic/provider/network=`4/4/4`
- Tokens：input/output/total=`23,862/1,855/25,717`
- Cost：USD `0.00845999`
- Failure：
  `s3_bounded_segmented_specialist_contract_invalid:value_and_profit_capture:facts_explanation_and_terminal:s4_compiled_fact_atom_shape_invalid`

前三次调用均通过。第四次调用返回合法 native JSON、`finish_reason=stop`，输出为 3,696 UTF-8 bytes，未超过 4,800-byte 上限；但 `fact_atoms` 有 22 项，等于请求中暴露的全部 22 个合法 support aliases，超过明确声明的 `provider_candidate_maximum=6`。

## Attribution

本轮确实存在模型的数量指令不遵循；同时也建立了项目自身的鲁棒性缺口：系统把 22 个合法候选全部暴露给模型，却把模型一次性只选最多 6 个当作 L1 前提。只强调 prompt、扩大上限、静默截断或重试都不能消除这个结构依赖。

项目级处置选择：Fact candidate generation 交给本地确定性 planner。先基于 Cell、evidence role、numeric authority、typed gap、scope 与稳定 tie-break，把 Provider 可见候选池缩到最多 6 个；模型只返回这些 request-local aliases 的有限判断枚举，本地再选择最多 3 个并完成渲染。

## Governance

- 唯一 replacement admission 已消费；
- 不进行第二次 replacement、R8/R9、字段补丁或 prompt retry；
- 无 Artifact，因此 paired assessment 与 owner acceptance 不具资格；
- T06 保留 `engineering_pass`，但 `live_product_pass=false`，不得进入 T07；
- successor=`S4-SHARED-RUNTIME-DETERMINISTIC-FACT-CANDIDATE-POOL-PLANNER-SEPARATE-AUTHORITY`。
