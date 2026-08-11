from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.financial_research_current_source_reparse import (  # noqa: E402
    RUN_SCOPE,
    execute_current_source_reparse,
    load_current_source_reparse_policy,
    validate_current_source_reparse_result,
)
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_three_held_out_"
    "current_source_reparse_successor_r9_policy_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_three_held_out_"
    "current_source_reparse_successor_r9_result_v1_0.json"
)
RUNTIME_ROOT = ROOT / (
    "data/workbench_private/fin_0_1_3_s1_three_held_out_"
    "current_source_reparse/zero-call-r9"
)


def main() -> int:
    if RESULT_PATH.exists():
        raise RuntimeError("three_held_out_current_source_reparse_output_exists")
    project_os = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if project_os.get("status") != "pass":
        raise RuntimeError("three_held_out_current_source_reparse_project_os_preflight_failed")
    policy = load_current_source_reparse_policy(POLICY_PATH, repo_root=ROOT)
    result = execute_current_source_reparse(
        policy=policy,
        repo_root=ROOT,
        runtime_root=RUNTIME_ROOT,
    )
    validate_current_source_reparse_result(result)
    if result["status"] != "source_object_migration_pass_index_rebuild_admitted":
        raise RuntimeError("three_held_out_current_source_reparse_status_unexpected")
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "result_digest": result["result_digest"],
                "case_summaries": [
                    {
                        "case_key": row["case_key"],
                        "observed_counts": row["observed_counts"],
                        "projected_slot_ids": row["projected_slot_ids"],
                        "finding_counts": row["finding_counts"],
                    }
                    for row in result["case_results"]
                ],
                "mutation_results": result["mutation_results"],
                "observed_calls": result["observed_calls"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
