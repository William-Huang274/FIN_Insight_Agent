from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.financial_research_core_unchanged_transfer import (  # noqa: E402
    TRANSFER_RUN_SCOPE,
    execute_core_unchanged_transfer,
    load_core_unchanged_transfer_policy,
)
from sec_agent.financial_research_source_object_vertical import (  # noqa: E402
    normalized_sha256,
)
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_mu_nvda_"
    "core_unchanged_transfer_policy_v1_0.json"
)
MODULE_PATH = ROOT / "src/sec_agent/financial_research_core_unchanged_transfer.py"
TRANSFER_OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_mu_nvda_"
    "core_unchanged_transfer_result_v1_0.json"
)
CASE_OUTPUT_PATHS = {
    "MU": ROOT
    / "configs/releases/fin_ia_0_1_3_s1_mu_financial_source_object_transfer_result_v1_0.json",
    "NVDA": ROOT
    / "configs/releases/fin_ia_0_1_3_s1_nvda_financial_source_object_transfer_result_v1_0.json",
}


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    outputs = [TRANSFER_OUTPUT_PATH, *CASE_OUTPUT_PATHS.values()]
    if any(path.exists() for path in outputs):
        raise RuntimeError("mu_nvda_core_unchanged_transfer_output_exists")
    preflight = run_project_os_preflight(ROOT, run_scope=TRANSFER_RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise RuntimeError("mu_nvda_core_unchanged_transfer_preflight_blocked")
    policy = load_core_unchanged_transfer_policy(POLICY_PATH, repo_root=ROOT)
    executed = execute_core_unchanged_transfer(policy=policy, repo_root=ROOT)
    if (
        executed["transfer_result"]["status"]
        != "engineering_pass_core_unchanged_transfer"
    ):
        raise RuntimeError("mu_nvda_core_unchanged_transfer_acceptance_failed")
    for case_key, result in executed["case_results"].items():
        _write_json(CASE_OUTPUT_PATHS[case_key], result)

    transfer_body = dict(executed["transfer_result"])
    transfer_body.pop("result_digest", None)
    transfer_body.update(
        {
            "attempt_id": "S1-MU-NVDA-CORE-UNCHANGED-TRANSFER-R1",
            "policy_sha256": normalized_sha256(POLICY_PATH),
            "project_os_preflight": {
                "status": str(preflight["status"]),
                "run_scope": str(preflight["run_scope"]),
                "open_full_chain_blocker_count": int(
                    preflight.get("open_full_chain_blocker_count") or 0
                ),
            },
            "implementation": {
                "module_ref": MODULE_PATH.relative_to(ROOT).as_posix(),
                "module_sha256": normalized_sha256(MODULE_PATH),
                "materializer_ref": (
                    "scripts/releases/materialize_fin_ia_0_1_3_s1_"
                    "mu_nvda_core_unchanged_transfer.py"
                ),
                "policy_ref": POLICY_PATH.relative_to(ROOT).as_posix(),
            },
        }
    )
    transfer_result = {
        **transfer_body,
        "result_digest": canonical_digest(transfer_body),
    }
    _write_json(TRANSFER_OUTPUT_PATH, transfer_result)
    print(
        json.dumps(
            {
                "status": transfer_result["status"],
                "attempt_id": transfer_result["attempt_id"],
                "case_summaries": transfer_result["case_summaries"],
                "observed_calls": transfer_result["observed_calls"],
                "result_digest": transfer_result["result_digest"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
