# 224 Fin Agent Memo Response Language v0.7

## Prompt

用户要求采用第二种方案：把 Memo 输出中文做成链路级语言策略，而不是只在 prompt 末尾加一句“用中文回答”。

## Decision

本轮把 `response_language` 作为 shared memo context / MemoDraft contract / eval gate 的一等字段：

- 默认从显式 `response_language` / `output_language` 读取；没有显式字段时，根据 `user_query` 是否包含中文推断 `zh-CN` 或 `en-US`。
- Memo Writer 对所有 user-facing prose 使用目标语言；只保留 ticker、metric id、evidence ref、form name、数字和单位。
- Verifier 对 `zh-CN` memo 增加硬门控：`direct_answer`、`memo_claims.claim`、action fields、caveats、excluded unsupported claims、source boundary 等不能主要为英文。
- Renderer 根据 `response_language` 切中文标题和 evidence-ref 标签。

## Work Completed

- `src/sec_agent/memo_llm.py`
  - 新增 `sec_agent_response_language_v0.1`。
  - `build_shared_memo_context` 输出 `response_language`。
  - Memo Writer prompt 明确 zh-CN 下不能复制英文 ClaimCard claim prose，只能复制 `claim_id` / `evidence_refs` / tickers / metric ids / 数字单位。
  - MemoDraft normalization 写入 `response_language`，并将默认 `source_boundary` 本地化为中文。
  - 修正 numeric fidelity 中文路径：发现可疑数值时不再用英文源 ClaimCard 覆盖中文 claim。
  - 数值解析支持 `亿美元`、`百万美元`、`万美元`、`倍`、`个百分点`、`percentage points`，并支持 `$14.5-$15.5B` / `145-155亿美元` 区间等价。
- `src/sec_agent/multi_agent_contracts.py`
  - Verifier 增加 `memo_zh_response_field_not_chinese` hard error。
  - 修正 numeric verifier 的中英文单位等价和区间继承单位。
- `src/sec_agent/langgraph_orchestrator.py`
  - `_render_memo_answer` 根据 `response_language` 输出中文 section 标题与 `证据=` 标签。
- `scripts/eval_multi_agent_judgment_memo_gate.py`
  - S6-S8 gate 增加 `memo_response_language_present`、`memo_response_language_matches_query`、`memo_user_facing_language_ok`。
  - 中文 direct-answer 长度门控改为中文字符密度口径，避免用英文 token/char 习惯误判中文短段落。

## Real DeepSeek Results

通过的 v0.7 代表样例：

| Case | Run ID | Status | Profile | Memo tokens | Verifier tokens | Repairs |
| --- | --- | --- | --- | ---: | ---: | ---: |
| NVDA/AMD standard memo | `20260601_fin_agent_s6_s8_memo_language_v0_7_nvda_amd_deepseek_v0_4` | pass | expanded | 12,003 | 6,085 | 0 |
| Utilities sector-depth | `20260601_fin_agent_s6_s8_memo_language_v0_7_utilities_deepseek_v0_1` | pass | deep_research | 15,078 | 7,108 | 0 |
| Banking standard memo | `20260601_fin_agent_s6_s8_memo_language_v0_7_banking_deepseek_v0_1` | pass | expanded | 11,864 | 5,590 | 0 |
| Energy standard memo | `20260601_fin_agent_s6_s8_memo_language_v0_7_energy_deepseek_v0_3` | pass | expanded | 10,643 | 4,775 | 0 |

中间失败和根因：

- `nvda_amd v0_1/v0_2`：模型或 numeric normalizer 把英文 ClaimCard prose 带入 `memo_claims`，被中文 gate 拦截。
- `nvda_amd v0_3`：Memo Writer / Verifier 已通过，但 expanded direct-answer 英文长度门控不适合中文字符密度。
- `energy v0_1/v0_2`：`source_boundary` 过长英文未本地化；`$14.5-$15.5B` / `145-155亿美元` 区间单位解析不等价。

## Verification

- `python -m compileall src\sec_agent\memo_llm.py src\sec_agent\multi_agent_contracts.py src\sec_agent\langgraph_orchestrator.py scripts\eval_multi_agent_judgment_memo_gate.py`
- `pytest tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_judgment_memo_verifier.py -q`
- Real DeepSeek S6-S8 v0.7 representative cases: `4/4` pass, `0` repairs.

## Follow-Up

- 本轮只验证 S6-S8 artifact-reuse layer，没有重新跑 S1-S8 full chain。
- 后续 full-chain / multi-turn eval 应沿用 `response_language`，并在 rendered answer 层检查中文标题和中文 memo prose。
- 当前本地知识库覆盖限制仍存在；中文输出策略只解决语言一致性和 numeric gate 误伤，不扩展外部数据覆盖。
