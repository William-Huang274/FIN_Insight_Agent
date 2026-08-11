# 253 Expanded A1-A5 Local Layered Gate And Cloud Blocker

日期：2026-06-07

## Prompt

承接 `252` 后继续按 `expanded_universe_retrieval_agent_framework_v0_1.zh-CN.md` 的第 7 步推进：先跑 A1-A5 分层 gate，不直接跑 expanded full-chain；同时同步本地、工作日志和云端产物状态，避免与前一会话断档。

## Work Completed

- 读取并核对前序 worklog、architecture 文档和云端产物记录，确认 `247-252` 已完成：
  - expanded Object SQLite FTS / ObjectHybrid retrieval-only A/B 已过。
  - Market/Industry source inventory context-only 边界已接入。
  - `milvus_semantic` route、MCP contract、expanded catalog path、source-family bundle、Research Lead cost-aware route choice、Specialist Market/Industry source boundary 已完成。
- 跑本地 A1-A5 分层回归，严格复用分层 artifact，不跑 full-chain：
  - A1/S1 Research Lead cost-aware route gate：`5/5` pass。
  - S2 Universe / Relationship LinkMap gate：`1/1` pass。
  - A2/S3 Evidence Operator gate：本地 full238 real retrieval `4/4` pass。
  - A3/S4 Coverage / Reflection gate：`4/4` pass。
  - A4/S5 Specialist source-family bundle gate：`2/2` pass，`7` Specialist routes，`0` repair。
  - A5/S6-S8 Judgment / Memo / Verifier gate：`2/2` pass，Memo/Verifier `2/2`，`0` repair。
- 修复 A3 期间发现的脚本回归：
  - `scripts/eval_multi_agent/eval_multi_agent_coverage_reflection_gate.py` 的 `_s3_args_from_summary(...)` 未还原 `market_catalog_path`、`industry_snapshot_db_path`、`milvus_db_path`、`milvus_collection_name`、`milvus_vector_kinds`、`milvus_top_k`、`embedding_model` 等新增 S3 runtime config，导致新版 S3 artifact 进入 S4 时 AttributeError。
  - `scripts/eval_multi_agent/eval_multi_agent_evidence_operator_gate.py` 的 summary runtime config 补充保存 `milvus_top_k`、`embedding_model`、`market_snapshot_id`、`market_as_of_date`。
  - 新增 `tests/test_eval_multi_agent_gate_config_roundtrip.py`，覆盖 S3 summary -> S4 args 的 expanded runtime config roundtrip。

## Verification

- A1/S1：
  - Command：`python scripts\eval_multi_agent\eval_multi_agent_research_lead_activation.py --run-id 20260607_expanded_a1_research_lead_cost_aware_route_gate_deepseek_v0_1 --require-evidence-requirements --strict`
  - Result：`5/5` pass；mode / validation / required agents / budget / evidence requirements 均 `5/5`，forbidden activation `0`，tokens `27411`。
- S2：
  - Run ID：`20260607_expanded_s2_relationship_link_map_gate_deepseek_v0_1`
  - Result：`1/1` pass；lookup relationships `42`，plan relationships `42`，fallback `0`，tokens `10371`。
- A2/S3 本地 full238 回归：
  - Run ID：`20260607_expanded_a2_local_full238_evidence_operator_regression_v0_2`
  - Result：`4/4` pass；tool calls `14`，context rows `146`，runtime ledger rows `259`，market rows `4`，industry rows `10`，SEC pre-rerank candidates `550`，BGE candidates `433`。
- A3/S4：
  - Run ID：`20260607_expanded_a3_local_full238_coverage_reflection_regression_v0_2`
  - Result：`4/4` pass；second pass allowed/ran `1`，added rows `120`，missing requirements `2`。
- A4/S5：
  - Run ID：`20260607_expanded_a4_local_full238_specialist_source_bundle_regression_deepseek_v0_1`
  - Result：`2/2` pass；Specialist count `7`，real evidence quality `2/2`，tokens `51519`，repair `0`。
- A5/S6-S8：
  - Run ID：`20260607_expanded_a5_local_full238_judgment_memo_verifier_regression_deepseek_v0_1`
  - Result：`2/2` pass；Memo route `2/2`，Verifier `2/2`，tokens `32221`，repair `0`。
- Unit / compile：
  - `python -m pytest tests\test_eval_multi_agent_gate_config_roundtrip.py tests\test_multi_agent_operator_permissions.py -q` -> `20 passed`
  - `python -m pytest tests\test_multi_agent_specialist_llm.py tests\test_research_skills.py -q` -> `46 passed`
  - `python -m pytest tests\test_multi_agent_research_lead_llm.py tests\test_sec_agent_retrieval_plan.py -q` -> `36 passed`
  - `python -m py_compile scripts\eval_multi_agent\eval_multi_agent_evidence_operator_gate.py scripts\eval_multi_agent\eval_multi_agent_coverage_reflection_gate.py scripts\eval_multi_agent\eval_multi_agent_specialist_layer_gate.py scripts\eval_multi_agent\eval_multi_agent_judgment_memo_gate.py` -> pass

## Cloud Status

- 云端 expanded 数据产物仍按 `247-252` 记录存在于 `/autodl-fs/data/fin_agent_milvus_bge_m3`，但本轮无法继续执行 true expanded A2-A5：
  - `ssh -p 12353 ...` 在认证前返回 `Connection closed by 116.172.66.188 port 12353`。
  - Paramiko 和 PuTTY/plink 也在 SSH protocol banner / pre-auth 阶段被远端关闭。
- 因此本轮没有把脚本修复同步到云端，也没有跑 603-company expanded real retrieval / Specialist / Memo gate。

## Decision

- 本轮 A1-A5 只能认定为“本地 full238 分层链路回归通过 + 新 expanded runtime config roundtrip 修复通过”。
- 不能把 true expanded A1-A5 标记为完成；不能进入 expanded 10-20 case full-chain / multi-turn。
- `milvus_semantic` 仍是显式 typed semantic recall supplement。当前真实 S1 cost-aware 输出没有主动选择 `milvus_semantic`；Milvus route 本轮由 operator contract/unit gate 覆盖，不是由 full S1-S5 真实路径触发。

## Next

1. 云端 SSH 恢复后，先同步本轮 `scripts/eval_multi_agent/*` 修复和 `tests/test_eval_multi_agent_gate_config_roundtrip.py`。
2. 在云端用 expanded manifest / BM25 / Object SQLite FTS / combined or verified ledger / market catalog / industry snapshot DB / Milvus typed collection 显式跑 A2-A5。
3. 只有 true expanded A1-A5 通过后，再跑 10-20 case expanded full-chain / multi-turn。
