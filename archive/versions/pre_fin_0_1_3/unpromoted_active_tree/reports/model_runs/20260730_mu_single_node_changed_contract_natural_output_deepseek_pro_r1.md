# Model Run: 20260730_mu_single_node_changed_contract_natural_output_deepseek_pro_r1

## Summary

- Purpose：验证新 judgment-atom compiled contract 的 Fact、Claim、WWC 三个 Provider family 是否会自然遵循 exact wire
- Status：terminal failed / first-failure-stop
- Run type：inference canary
- Timestamp：2026-07-30T08:45:29Z 至 2026-07-30T08:45:35Z
- Environment：本地 Windows，DeepSeek API

## Code And Command

- Entry point：`scripts/releases/run_fin_ia_0_1_s4_t06_mu_changed_contract_family_single_node_natural_output_canaries.py`
- Command：`python scripts/releases/run_fin_ia_0_1_s4_t06_mu_changed_contract_family_single_node_natural_output_canaries.py --execute`
- Authority：`configs/releases/fin_ia_0_1_s4_t06_mu_changed_contract_family_single_node_natural_output_canaries_authority_decision_v1_0.json`
- Git：branch `codex/layered-data-source-expansion`，commit `54d2e072`，dirty，ahead 5
- Seeds：Claim 与 WWC prior segments 使用 frozen local deterministic seed；自然输出不跨 family 传递

## Inputs

- Case / Cell：`MU / demand_authenticity_and_sustainability`
- Input digest：`7887b5bb447fc6a844c410751f2038a04a1c0b04dbbe7e5bde41b040135a12e1`
- Family request SHA：
  - Fact：`f96285fd64912b39b57e7f3c104186e2941fd0e61cbcf40a0888fb4591c404e1`
  - Claim：`405738388536cba288ddd46a3af5b51952bcc5f35adb76cc0b9241b4cc0cc24f`
  - WWC：`b643c574623d1ce4dfe4d0815d3f389b5b9ec0b8bf226a91e13c03818dc48f26`
- Leakage guard：每个 family 独立；Claim/WWC 不消费前一自然输出

## Model Parameters

- Provider/model：`deepseek / deepseek-v4-pro`
- Base URL：`https://api.deepseek.com/beta`
- Wire：Chat Completions `json_object`
- Temperature：`0.0`
- Thinking/reasoning effort：disabled / none
- Max output：Fact `1600`，Claim `1200`，WWC `1400`
- Timeout：每调用 `120 sec`
- Retry/fallback/replay/provider hopping：`0/0/0/0`

## Outputs

- Sanitized result：`configs/releases/fin_ia_0_1_s4_t06_mu_changed_contract_family_single_node_natural_output_canaries_exact_once_execution_result_v1_0.json`
- Restricted captures：`.codex_runtime/s4_t06_mu_changed_contract_family_single_node_canaries_exact_once_r1/captures`
- Business Artifact：0

## Results

- Fact：pass，`ok/stop`，5 atoms，compiled wire/local assembly pass
- Claim：terminal fail，`ok/stop`，native JSON 成功，但无 scope-compatible candidate
- WWC：first-failure-stop，未调用
- Calls：`2 model / 2 Provider / 2 network / 2 transport`
- Tokens：`7283 input / 360 output / 7643 total`
- Cost：USD `0.00348130`
- Latency：Fact `3754 ms`，Claim `2939 ms`
- Capture-v2：2

## Experiment Governance

- Hypothesis：限制 Provider 只返回 request-local aliases 与枚举 atoms，可使自然输出稳定通过 compiled wire 并由本地组装重要真值
- Decision target：三个 family 全部 `ok/stop`、wire pass、local assembly pass
- Ceiling：最多 3 calls、4200 output tokens、USD 0.03、360 sec
- Stop condition：任一 family 首个可信失败即停止
- Decision label：stop / zero-call disposition required
- Mainline decision：Fact 有正证据；Claim 未通过；不得进入 R7

## Runtime Efficiency

- Wall time：约 `6.7 sec`
- Throughput：2 个自然 family responses
- GPU：不适用
- Bottleneck：Claim candidate eligibility，不是 transport latency
- Serving implication：此 canary 不构成线上 SLA 或产品性能证据

## Caveats And Next Step

- 未读取 WWC natural output
- 未运行 canonical full-chain、R7、paired 或 owner acceptance
- Raw request/output 仅存 restricted capture，不在本报告复写
- 后续零调用处置已完成：唯一 Claim candidate 使用合法同案 alias，无 mixed/cross-scope；直接失败组合是 `insufficient_evidence + non-empty support_fact_aliases`
- 该条件规则只存在于 selector，没有进入 model-visible contract、wire schema 或 system instruction；因此 RC-P36-083 以 project-owned semantic-parity recurrence 重开，未建立 DeepSeek/model fault
- 下一步：只允许 Claim epistemic/support-role compiled-contract v2 的一个零调用实现包；禁止自动重试、WWC 补跑、第二次 Claim canary或 R7
