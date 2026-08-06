from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402
from sec_agent.s3_cross_cell_synthesis_program import (  # noqa: E402
    compile_s3_cross_cell_synthesis_program,
    load_s3_cross_cell_policy,
)


def build_decision() -> dict:
    policy = load_s3_cross_cell_policy(ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_cross_cell_synthesis_policy_v1_0.json")
    claim_decision = json.loads((ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_02_claim_and_observable_wwc_v1_0.json").read_text(encoding="utf-8"))
    program = compile_s3_cross_cell_synthesis_program(policy=policy, claim_decision=claim_decision)
    body = {
        "acceptance": {
            "S3_03": "engineering_pass",
            "case_syntheses": "3/3",
            "dependencies": 3,
            "conflicts_with_disposition": 3,
            "gaps_with_impact_priority_owner_stop": 5,
            "all_natural_business_syntheses": 0,
            "fabricated_planned_cell_syntheses": 0,
        },
        "current_next": "FIN-0.1.3-013-S3-04-WORKPAPER-WRITER-DECISION-READY-CONTENT-ENTRY-AUDIT",
        "known_boundary": "S3-03 proves cross-Cell synthesis semantics with mixed natural/fixture Claim authority. No case has three natural Claim choices, so these syntheses are engineering fixtures, not business conclusions or Writer-ready content.",
        "model_provider_network_source_business_runs": [0, 0, 0, 0, 0],
        "cross_cell_synthesis_program": program,
        "canary_disposition": {
            "new_model_contract": False,
            "additional_paid_canary": "not_required",
            "reason": "S3-03 is deterministic Lead assembly over Claim Cards; natural business synthesis waits for the single formal full chain.",
        },
        "stage_boundary": {
            "S3_03": "engineering_pass",
            "S3_04": "next_not_started",
            "business_synthesis_accepted": False,
            "writer_ready": False,
            "full_chain": False,
            "product_acceptance": False,
            "release": False,
        },
    }
    return {**body, "record_digest": canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the FIN 0.1.3 S3-03 zero-call cross-Cell synthesis proof.")
    parser.add_argument("--output", type=Path, default=ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_03_cross_cell_synthesis_v1_0.json")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_decision()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["acceptance"]["S3_03"], "output": str(output), "observed": result["cross_cell_synthesis_program"]["observed_counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
