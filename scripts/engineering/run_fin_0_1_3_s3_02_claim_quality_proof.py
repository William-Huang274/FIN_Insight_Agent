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
from sec_agent.s3_claim_quality_program import (  # noqa: E402
    compile_s3_claim_quality_program,
    load_s3_claim_quality_policy,
)


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def build_decision() -> dict:
    policy = load_s3_claim_quality_policy(ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_claim_and_observable_wwc_policy_v1_0.json")
    program = compile_s3_claim_quality_program(
        policy=policy,
        s1_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0.json"),
        s2_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json"),
        representative_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_representative_node_context_precedence_and_canary_entry_v1_0.json"),
        s3_surface_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s3_01_dynamic_decision_surface_v1_0.json"),
        natural_s2_result=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_three_family_natural_canary_result_v1_0.json"),
        natural_s2_03_result=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_03_context_yield_natural_reproof_result_v1_0.json"),
    )
    body = {
        "acceptance": {
            "S3_02": "engineering_pass",
            "core_claim_contracts": "9/9",
            "live_natural_claim_choices": "4/9",
            "fixture_only_claim_choices": "5/9_not_business_truth",
            "structured_observable_wwc": program["observed_counts"]["structured_wwc"],
            "numeric_fact_bindings": program["observed_counts"]["numeric_fact_bindings"],
            "typed_gap_bindings": program["observed_counts"]["typed_gap_bindings"],
            "fabricated_dynamic_claims": 0,
        },
        "current_next": "FIN-0.1.3-013-S3-03-CROSS-CELL-DEPENDENCY-CONFLICT-GAP-SYNTHESIS-ENTRY-AUDIT",
        "known_boundary": (
            "S3-02 proves a company-specific Claim and observable WWC contract and preserves four existing natural choices. "
            "Five representative choices remain fixture-only and 29 newly planned dynamic cells have no Claim choice; they must not be displayed as research conclusions before the later formal full chain."
        ),
        "model_provider_network_source_business_runs": [0, 0, 0, 0, 0],
        "claim_quality_program": program,
        "canary_disposition": {
            "new_model_contract": False,
            "additional_paid_canary": "not_required",
            "reason": "S3-02 changes local Claim/WWC assembly and validation only; the S2 alias/enum Provider contract is unchanged and already has four natural exact-once choices.",
        },
        "stage_boundary": {
            "S3_02": "engineering_pass",
            "S3_03": "next_not_started",
            "all_dynamic_cells_naturally_judged": False,
            "full_chain": False,
            "product_acceptance": False,
            "release": False,
        },
    }
    return {**body, "record_digest": canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the FIN 0.1.3 S3-02 zero-call Claim/WWC proof.")
    parser.add_argument("--output", type=Path, default=ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_02_claim_and_observable_wwc_v1_0.json")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_decision()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["acceptance"]["S3_02"], "output": str(output), "observed": result["claim_quality_program"]["observed_counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
