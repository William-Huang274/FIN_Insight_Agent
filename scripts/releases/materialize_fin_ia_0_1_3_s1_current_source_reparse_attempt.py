from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.financial_research_current_source_reparse import (  # noqa: E402
    execute_current_source_reparse,
    load_current_source_reparse_policy,
    validate_current_source_reparse_result,
)
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402


PREFLIGHT_RUN_SCOPE = "S1_IMMUTABLE_SUPPLEMENTAL_DENSE_INDEX_REPLACEMENT_BUILD"


def _repo_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise RuntimeError("current_source_reparse_attempt_path_outside_repo") from exc
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--runtime-root", required=True)
    args = parser.parse_args()

    policy_path = _repo_path(args.policy)
    result_path = _repo_path(args.result)
    runtime_root = _repo_path(args.runtime_root)
    if result_path.exists():
        raise RuntimeError("current_source_reparse_attempt_output_exists")
    if runtime_root.exists():
        raise RuntimeError("current_source_reparse_attempt_runtime_root_exists")
    project_os = run_project_os_preflight(ROOT, run_scope=PREFLIGHT_RUN_SCOPE)
    if project_os.get("status") != "pass":
        raise RuntimeError("current_source_reparse_attempt_project_os_preflight_failed")
    policy = load_current_source_reparse_policy(policy_path, repo_root=ROOT)
    result = execute_current_source_reparse(
        policy=policy,
        repo_root=ROOT,
        runtime_root=runtime_root,
    )
    validate_current_source_reparse_result(result)
    if result["status"] != "source_object_migration_pass_index_rebuild_admitted":
        raise RuntimeError("current_source_reparse_attempt_status_unexpected")
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "attempt_id": result["attempt_id"],
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
