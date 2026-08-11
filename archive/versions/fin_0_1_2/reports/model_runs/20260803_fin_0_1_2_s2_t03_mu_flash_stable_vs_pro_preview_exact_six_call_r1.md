# FIN 0.1.2 S2-T03 MU Flash stable vs Pro preview exact six-call R1

- 日期：2026-08-03
- 类型：paired natural-output capability canary
- 状态：`six terminal complete / WWC comparison invalid on project contract gap`
- Git：`0872f8d2cd1cb1ce5cb838881ce159638491cd1a`
- 命令：`python scripts/releases/run_fin_ia_0_1_2_s2_t03_paired_natural_output_canary.py --execute`
- 路由：DeepSeek official beta chat-completions JSON-object；thinking disabled；temperature 0；stream false
- 模型：`deepseek-v4-flash` stable、`deepseek-v4-pro` preview
- 输入：已登记 MU exact fixture；Fact/Claim/WWC 三 family 同 family paired request/equivalence digest 一致

## 运行结果

六个计划调用全部开始并终止，transport attempt 均为 1，finish reason 均为 `stop`。Fact 两模型通过，Claim 两模型通过，WWC Pro 通过，WWC Flash 在本地校验失败，code=`s4_compiled_wwc_unbound_date_alias_forbidden`。

总 usage=`9106 input / 1021 output`。逐调用 input/output：Fact Flash `1514/98`，Fact Pro `1514/160`，Claim Flash `1375/46`，Claim Pro `1375/70`，WWC Flash `1664/292`，WWC Pro `1664/355`。延迟依次为 `1095/1990/836/1616/2259/3751 ms`。按冻结费率估算 USD `0.00484938`；最终费用以 Provider 账单为准。

restricted capture/terminal=`6/6`；retry/fallback/provider hopping/prompt-only retry/replacement pair=`0/0/0/0/0`；业务 Run/Artifact=`0`。凭据、Authorization/header、Cookie、raw Provider envelope 和 private reasoning 未持久化。

## 结论

WWC Flash 的失败不能归因于模型：模型可见 schema 允许 `review_date_alias` 为 allowed alias 或 `NONE`，但本地 validator 未公开地要求非 `bound_date` cadence 必须使用 `NONE`。因此 WWC pair 是项目合同一致性缺口造成的无效测量，Pro 的通过也不能据此形成模型胜出结论。

T04 未进入；模型未选择。不可自动重试或替换。受限证据位于 `.codex_runtime/fin012-s2-t03-mu-flash-pro-paired-r1`，只供审计，不追踪、不晋升为业务事实。
