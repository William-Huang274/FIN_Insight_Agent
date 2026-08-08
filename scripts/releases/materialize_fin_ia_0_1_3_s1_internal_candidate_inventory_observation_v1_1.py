from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_internal_candidate_ceiling import (  # noqa: E402
    RUN_SCOPE,
    canonical_observation_digest,
    execute_internal_candidate_inventory,
    load_bound_integration_proof,
    load_internal_candidate_ceiling_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_candidate_ceiling_policy_v1_1.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_candidate_"
    "inventory_observation_v1_1.json"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the corrected bounded read-only FIN 0.1.3 internal "
            "candidate inventory observation."
        )
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--attempt-id", default="")
    parser.add_argument("--supersedes-observation", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise RuntimeError("internal_candidate_ceiling_project_os_preflight_blocked")
    policy = load_internal_candidate_ceiling_policy(POLICY_PATH, repo_root=ROOT)
    proof = load_bound_integration_proof(policy, repo_root=ROOT)
    result = execute_internal_candidate_inventory(
        policy=policy,
        integration_proof=proof,
        repo_root=ROOT,
    )
    body = dict(result)
    body.pop("result_digest", None)
    body.update(
        {
            "policy_digest": canonical_digest(policy),
            "supersedes_observation": (
                "configs/releases/fin_ia_0_1_3_s1_internal_candidate_"
                "inventory_observation_v1_0.json"
            ),
            "project_os_preflight": {
                "status": str(preflight["status"]),
                "run_scope": str(preflight["run_scope"]),
                "registry_version": str(preflight.get("registry_version") or ""),
                "open_full_chain_blocker_count": int(
                    preflight.get("open_full_chain_blocker_count") or 0
                ),
            },
            "implementation": {
                "module_ref": "src/sec_agent/s1_internal_candidate_ceiling.py",
                "materializer_ref": (
                    "scripts/releases/materialize_fin_ia_0_1_3_s1_internal_"
                    "candidate_inventory_observation_v1_1.py"
                ),
                "policy_ref": POLICY_PATH.relative_to(ROOT).as_posix(),
            },
        }
    )
    if args.attempt_id:
        body["attempt_id"] = str(args.attempt_id)
    if args.supersedes_observation:
        body["supersedes_observation"] = str(args.supersedes_observation)
    output = {**body, "result_digest": canonical_observation_digest(body)}
    target = args.output.resolve()
    if target.exists():
        existing = json.loads(target.read_text(encoding="utf-8"))
        if existing.get("result_digest") != output["result_digest"]:
            raise RuntimeError("internal_candidate_ceiling_result_path_already_occupied")
        output = existing
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    summary = {
        "status": output["status"],
        "bundles": output["observed_counts"]["bundles"],
        "terminals": output["observed_counts"]["physical_request_terminals"],
        "candidate_counts_by_route": output["observed_counts"][
            "candidate_counts_by_route"
        ],
        "typed_gap_counts": output["observed_counts"]["typed_gap_counts"],
        "milvus_status": output["resource_qualification"]["milvus_dense"][
            "status"
        ],
        "qrels_state": output["qrels_state"],
        "result_digest": output["result_digest"],
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
