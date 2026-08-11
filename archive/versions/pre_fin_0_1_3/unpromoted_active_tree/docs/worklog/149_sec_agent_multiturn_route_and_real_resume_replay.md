# 149 SEC Agent Multiturn Route Rerun And Real Resume Replay

## Summary

- Date: 2026-05-22
- Task: Rerun the GPT-generated harness/multi-turn cases and run a real partial/resume state replay.
- Status: completed.

## Work Completed

Ran the reviewed GPT-generated multi-turn tool-harness case set again on cloud DeepSeek:

- Eval set: `eval_sets/sec_agent_multiturn_tool_harness_eval_reviewed_v1.json`
- Backend: DeepSeek `deepseek-v4-pro`
- Mode: `route_only=true`, `execute_tools=false`
- Cloud report: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/cloud_tool_controller_reviewed_v1_route_deepseek_rerun_latest.json`
- Local report: `reports/quality/cloud_tool_controller_reviewed_v1_route_deepseek_rerun_latest.json`

Result:

- `run_id=20260522_223339_tool_controller_reviewed_v1_deepseek`
- `scenario_count=5`
- `turn_count=18`
- `tool_pass_count=18`
- `arg_pass_count=18`
- `all_pass=true`
- `failure_count=0`

Then created a real resume replay from the all-green NVDA memo case:

- Source completed run: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_200800_60a9e00112`
- Replay run root: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/real_partial_resume_replay_synthesize_20260522`
- Local summary: `reports/quality/cloud_multiturn_route_and_real_resume_replay_20260522.json`

Replay method:

1. Copied the completed run into a replay folder.
2. Rewrote `sec_agent_state.json` `output_dir` and artifact paths to the replay folder.
3. Deleted synthesis/downstream artifacts only:
   - `runtime_evidence_pack.json`
   - `qwen/agent_outputs.jsonl`
   - `qwen/claim_verification.jsonl`
   - `post_gates/sec_benchmark_post_gates_summary.json`
   - `qwen/input_output.md`
4. Kept upstream artifacts intact:
   - `query_contract`
   - `retrieved_context`
   - `runtime_exact_value_ledger`
   - `evidence_coverage_matrix`
   - `judgment_plan`
5. Created a harness session pointing at the replay state.
6. Called `resume_analysis execute=false` to inspect the boundary.
7. Called `resume_analysis execute=true` to run the actual resume.

## Resume Replay Result

Before execution, `resume_analysis execute=false` reported:

- `next_ready_node=synthesize_memo`
- `missing_artifacts=[evidence_pack, memo_answer, claim_verification, deterministic_gates, rendered_answer]`
- `complete_artifacts=[evidence_coverage_matrix, judgment_plan, query_contract, retrieved_context, runtime_exact_value_ledger]`
- `digest_mismatch_artifacts=[]`

After `resume_analysis execute=true`:

- `resume_action=executed`
- `resumed_from_node=synthesize_memo`
- `elapsed_sec=82.5983`
- `final_status=completed`
- `final_missing_artifacts=[]`
- `final_digest_mismatch_artifacts=[]`
- `complete_artifacts` includes all 10 graph artifacts
- Post-gates: `all_pass=true`, `failed_gates=[]`, `qwen_answer_ratio=1.0`

Preserved upstream artifact digests after replay:

- `query_contract=4d540b1bdffd0e24`
- `retrieved_context=917402cfe318935b`
- `runtime_exact_value_ledger=94bf842bd8557383`
- `evidence_coverage_matrix=4e47be39f2a2b435`
- `judgment_plan=873a40b1df1ddae1`

This confirms the resume path did not rerun retrieval, ledger, coverage, or Judgment Plan for this replay. It resumed from `synthesize_memo` and regenerated downstream artifacts.

## Outputs

- `reports/quality/cloud_tool_controller_reviewed_v1_route_deepseek_rerun_latest.json`
- `reports/quality/cloud_multiturn_route_and_real_resume_replay_20260522.json`
- `reports/quality/real_partial_resume_replay_synthesize_20260522/graph_runner_summary.json`
- `reports/quality/real_partial_resume_replay_synthesize_20260522/graph_resume_report.json`
- `reports/quality/real_partial_resume_replay_synthesize_20260522/sec_agent_state.json`
- `reports/quality/real_partial_resume_replay_synthesize_20260522/post_gates/sec_benchmark_post_gates_summary.json`

## Safety Notes

- API key was injected only through the immediate remote process environment.
- No key/password was written to repo files, reports, or worklogs.
- Secret pattern scan on fetched reports found `0` matches.

## Current Boundaries

- The partial replay is a controlled replay created from a real completed all-green run by deleting downstream artifacts, not a naturally interrupted production run.
- The replay validates `synthesize_memo` resume. It does not validate resume from earlier nodes such as `build_coverage_matrix` on an actual cloud artifact.
- Full30 memo eval was not resumed in this run.
