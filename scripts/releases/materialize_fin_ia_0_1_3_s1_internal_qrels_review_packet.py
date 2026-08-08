from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_internal_qrels_review import (  # noqa: E402
    RUN_SCOPE,
    build_internal_qrels_review_packet,
    load_bound_internal_qrels_inputs,
    load_internal_qrels_review_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_qrels_review_policy_v1_0.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_qrels_review_packet_v1_0.json"
)


def main() -> int:
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise RuntimeError("internal_qrels_project_os_preflight_blocked")
    policy = load_internal_qrels_review_policy(POLICY_PATH, repo_root=ROOT)
    inputs = load_bound_internal_qrels_inputs(policy, repo_root=ROOT)
    result = build_internal_qrels_review_packet(policy=policy, inputs=inputs)
    body = dict(result)
    body.pop("review_digest", None)
    body.update(
        {
            "policy_digest": canonical_digest(policy),
            "project_os_preflight": {
                "status": str(preflight["status"]),
                "run_scope": str(preflight["run_scope"]),
                "registry_version": str(preflight.get("registry_version") or ""),
            },
            "implementation": {
                "module_ref": "src/sec_agent/s1_internal_qrels_review.py",
                "materializer_ref": (
                    "scripts/releases/materialize_fin_ia_0_1_3_s1_internal_"
                    "qrels_review_packet.py"
                ),
                "policy_ref": POLICY_PATH.relative_to(ROOT).as_posix(),
            },
        }
    )
    output = {**body, "review_digest": canonical_digest(body)}
    if OUTPUT_PATH.exists():
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        if existing.get("review_digest") != output["review_digest"]:
            raise RuntimeError("internal_qrels_review_result_path_already_occupied")
        output = existing
    else:
        OUTPUT_PATH.write_text(
            json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(
        json.dumps(
            {
                "status": output["status"],
                "target_in_pool": [
                    output["strict_current_target_in_pool_count"],
                    output["target_count"],
                ],
                "target_recall": output["strict_current_target_recall"],
                "exact_sql_candidates": output[
                    "all_target_exact_sql_candidate_count"
                ],
                "gap_counts": output["gap_counts"],
                "review_digest": output["review_digest"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
