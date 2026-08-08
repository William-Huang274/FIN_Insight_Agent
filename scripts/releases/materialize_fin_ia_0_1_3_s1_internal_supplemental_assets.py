from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_internal_supplemental_assets import (  # noqa: E402
    RUN_SCOPE,
    build_internal_supplemental_assets,
    load_internal_supplemental_asset_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_supplemental_asset_policy_v1_0.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_supplemental_asset_manifest_v1_0.json"
)


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("internal_supplemental_asset_manifest_already_exists")
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise RuntimeError("internal_supplemental_asset_project_os_preflight_blocked")
    policy = load_internal_supplemental_asset_policy(POLICY_PATH, repo_root=ROOT)
    result = build_internal_supplemental_assets(policy=policy, repo_root=ROOT)
    output = {
        **result,
        "project_os_preflight": {
            "status": str(preflight["status"]),
            "run_scope": str(preflight["run_scope"]),
            "open_full_chain_blocker_count": int(
                preflight.get("open_full_chain_blocker_count") or 0
            ),
        },
        "implementation": {
            "module_ref": "src/sec_agent/s1_internal_supplemental_assets.py",
            "materializer_ref": (
                "scripts/releases/materialize_fin_ia_0_1_3_s1_internal_"
                "supplemental_assets.py"
            ),
            "policy_ref": POLICY_PATH.relative_to(ROOT).as_posix(),
        },
    }
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": output["status"],
                "record_counts": output["record_counts"],
                "uncovered_expected_source_refs": output[
                    "uncovered_expected_source_refs"
                ],
                "manifest_digest": output["manifest_digest"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
