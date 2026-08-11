from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for value in (ROOT, ROOT / "src"):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402
from sec_agent.s3_research_quality_gate import (  # noqa: E402
    compile_s3_research_quality_gate_program,
    load_s3_research_quality_gate_policy,
)


DEFAULT_POLICY = ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_research_quality_gate_policy_v1_0.json"
DEFAULT_CLAIM = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_02_claim_and_observable_wwc_v1_0.json"
DEFAULT_WRITER = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_04_workpaper_writer_decision_ready_content_v1_0.json"
DEFAULT_OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_05_research_quality_gate_v1_0.json"
RECORDED_AT = "2026-08-06T18:05:00+08:00"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile FIN 0.1.3 S3-05 eight-dimension research quality gate.")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--claim", type=Path, default=DEFAULT_CLAIM)
    parser.add_argument("--writer", type=Path, default=DEFAULT_WRITER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    policy = load_s3_research_quality_gate_policy(args.policy)
    program = compile_s3_research_quality_gate_program(
        policy=policy,
        claim_decision=_load(args.claim),
        writer_decision=_load(args.writer),
    )
    record = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s3_05_research_quality_gate_decision_v1_0",
        "recorded_at": RECORDED_AT,
        "acceptance": {
            "S3_05_deterministic_gate": "engineering_pass",
            "rubric_dimensions_compiled": "8/8",
            "case_gate_contexts": "3/3",
            "current_fixture_previews_formally_scored": 0,
            "formal_case_passes": 0,
            "paired_assessments": 0,
            "qualified_human_content_acceptances": 0,
        },
        "research_quality_gate_program": program,
        "admission_disposition": {
            "formal_full_chain_authorized_now": False,
            "reason": "The deterministic gate is executable, but every current case remains fixture-mixed and lacks a verifier-bound natural final delivery, L1/L2 result, sealed reviewer packet, and distinct paired Run/Artifact identities. A separate fresh admission-readiness audit must bind those surfaces before one formal full chain.",
            "automatic_exact_live_or_retry": False,
        },
        "model_provider_network_source_business_runs": [0, 0, 0, 0, 0],
        "stage_boundary": {
            "S3_05_deterministic_contract": "engineering_pass",
            "natural_final_delivery": False,
            "formal_case_quality_pass": False,
            "paired_material_gain": False,
            "qualified_human_content_acceptance": False,
            "S3_product_proof": False,
            "S4_entry": False,
            "release": False,
        },
        "known_boundary": "This record proves fail-closed quality, paired and human-decision contracts. It intentionally does not score fixture previews or claim that DELL, MU or NVDA meet the 24/32 product threshold.",
        "current_next": "FIN-0.1.3-S3-FORMAL-ANCHOR-FULL-CHAIN-ADMISSION-READINESS-AUDIT",
    }
    record["record_digest"] = canonical_digest(record)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(args.output), "record_digest": record["record_digest"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
