# P31 Agent Self-Hardening / Project OS

日期：2026-07-04

## 问题

用户指出，当前 Codex 在长线程中会出现四类系统性问题：

- 记忆无法稳定固化，上下文压缩后容易漏掉前序要求；
- 做着做着只盯局部修复，忽略产品质量和全局研究目标；
- full-chain / paid eval 用得太早，拿昂贵模型调用发现 deterministic/node-level 能发现的问题；
- skill 和 worklog 容易变成摆设，不能保证在合适时刻被调用。

## 决策

新增 P31 Project OS，不把项目事实写死在 skill 里，而是拆成三层：

- skill：提醒 Codex “应该怎么做”；
- repo ledgers：记录 “项目事实是什么”；
- preflight guard：阻止 “已知 blocker 下乱跑 expensive/full-chain”。

## 完成内容

新增两个轻量个人 Codex skills：

- `Z:/CodexHome/.codex/skills/fin-insight-global-stewardship/SKILL.md`
- `Z:/CodexHome/.codex/skills/fin-insight-project-os/SKILL.md`

新增 `docs/project_os/`：

- `README.md`
- `current_context_pack.zh-CN.md`
- `capability_status_ledger.jsonl`
- `root_cause_issue_ledger.jsonl`
- `external_pattern_registry.jsonl`
- `financial_research_method_registry.jsonl`
- `full_chain_run_policy.zh-CN.md`
- `token_budget_policy.zh-CN.md`
- `done_definition_l4_scope_pass.zh-CN.md`
- `full_chain_preflight_checklist.json`

新增 runtime guard：

- `src/sec_agent/project_os_preflight.py`
- `scripts/eval_multi_agent/run_project_os_full_chain_preflight.py`
- `tests/test_project_os_preflight.py`

并把 Project OS preflight 接入 `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`：

- `--project-os-preflight-only`
- `--skip-project-os-preflight`
- `--project-os-preflight-allow-open-blockers`

## 当前结果

Project OS preflight 默认会读取：

- capability status ledger；
- root-cause issue ledger；
- full-chain preflight checklist；
- required Project OS files。

如果存在 `full_chain_blocker=true` 且 status 为 open/active/blocked 的 root-cause row，full-chain 入口会 fail closed。当前首批 ledger 明确保留 P30 真实单 case artifact proof、memo insight density 和 paid full-chain overuse risk 为 open blockers，所以 broad/paid full-chain 不应直接继续。

## 验证

本轮已运行：

- `python -m pytest tests/test_project_os_preflight.py -q`：`4 passed`
- `python -m py_compile src/sec_agent/project_os_preflight.py scripts/eval_multi_agent/run_project_os_full_chain_preflight.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`：通过
- `python scripts/eval_multi_agent/run_project_os_full_chain_preflight.py`：按预期 `blocked`，列出 3 个 open full-chain blockers
- `python scripts/eval_multi_agent/run_project_os_full_chain_preflight.py --allow-open-blockers`：按预期 `diagnostic_override`
- `python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --project-os-preflight-only --run-id p31_project_os_preflight_probe`：按预期 `blocked`
- 两个新增 skill 均通过 `quick_validate.py`
- `git diff --check`：通过，仅有既有 CRLF/LF warning
- 针对本轮新增/修改文件的 key-like secret scan：无命中

## 边界

P31 不证明最终 memo 质量变好；它只保证后续不会在已知 blocker 下靠 full-chain 烧 token。下一步如果要继续真实 AI/Semis 单 case，需要先看 Project OS blocker，明确是关闭 blocker 后运行，还是用户批准 diagnostic override。
