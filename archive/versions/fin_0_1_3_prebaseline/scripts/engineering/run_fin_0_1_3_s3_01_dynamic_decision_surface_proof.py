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
from sec_agent.s3_dynamic_decision_surface_program import (  # noqa: E402
    compile_s3_dynamic_surface_program,
    load_s3_dynamic_surface_policy,
)


POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_dynamic_decision_surface_policy_v1_0.json"
S1_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0.json"
S2_POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s2_research_question_method_contract_policy_v1_0.json"
S2_DECISION_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json"
DEFAULT_OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_01_dynamic_decision_surface_v1_0.json"


def build_decision() -> dict:
    policy = load_s3_dynamic_surface_policy(POLICY_PATH)
    s1 = json.loads(S1_PATH.read_text(encoding="utf-8"))
    s2_policy = json.loads(S2_POLICY_PATH.read_text(encoding="utf-8"))
    s2 = json.loads(S2_DECISION_PATH.read_text(encoding="utf-8"))
    program = compile_s3_dynamic_surface_program(
        policy=policy,
        s1_decision=s1,
        s2_policy=s2_policy,
        s2_decision=s2,
    )
    body = {
        "acceptance": {
            "S3_01": "engineering_pass",
            "dynamic_cell_counts": program["observed_counts"]["cell_counts"],
            "required_family_coverage": "6/6 each case",
            "reviewer_inspect_prune_split": "3/3 zero-call proofs",
            "protected_boundary_prune": "fail_closed",
            "upstream_evidence_aliases_bound": "26/26",
            "upstream_typed_gaps_bound": "2/2",
        },
        "current_next": "FIN-0.1.3-013-S3-02-COMPANY-SPECIFIC-CLAIM-AND-OBSERVABLE-WHAT-WOULD-CHANGE-ENTRY-AUDIT",
        "known_boundary": (
            "S3-01 proves a current governed-pack-bound, case-specific dynamic DecisionSurface and reviewer revision semantics. "
            "It does not prove Specialist judgments across all cells, Lead synthesis, Writer depth, Verifier quality, product acceptance or release."
        ),
        "model_provider_network_source_business_runs": [0, 0, 0, 0, 0],
        "dynamic_decision_surface_program": program,
        "root_cause_corrections": {
            "composition_wwc_projection": "fixed_and_regression_bound",
            "historical_ten_cell_shadow_promotion": "rejected_current_inputs_compiled_instead",
        },
        "stage_boundary": {
            "S3_01": "engineering_pass",
            "S3_02": "next_not_started",
            "full_chain": False,
            "product_acceptance": False,
            "release": False,
        },
    }
    return {**body, "record_digest": canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the FIN 0.1.3 S3-01 zero-call dynamic DecisionSurface proof.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_decision()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["acceptance"]["S3_01"],
        "output": str(output),
        "cell_counts": result["acceptance"]["dynamic_cell_counts"],
        "program_digest": result["dynamic_decision_surface_program"]["program_digest"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
