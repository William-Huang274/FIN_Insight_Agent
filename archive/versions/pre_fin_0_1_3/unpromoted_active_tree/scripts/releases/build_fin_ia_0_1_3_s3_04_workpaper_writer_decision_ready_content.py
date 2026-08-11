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
from sec_agent.s3_workpaper_writer_content_program import (  # noqa: E402
    compile_s3_workpaper_writer_content_program,
    load_s3_workpaper_writer_content_policy,
)


DEFAULT_POLICY = ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_workpaper_writer_content_policy_v1_0.json"
DEFAULT_CLAIM = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_02_claim_and_observable_wwc_v1_0.json"
DEFAULT_SYNTHESIS = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_03_cross_cell_synthesis_v1_0.json"
DEFAULT_OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_04_workpaper_writer_decision_ready_content_v1_0.json"
RECORDED_AT = "2026-08-06T16:17:09+08:00"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile FIN 0.1.3 S3-04 decision-ready Workpaper/Writer engineering preview.")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--claim", type=Path, default=DEFAULT_CLAIM)
    parser.add_argument("--synthesis", type=Path, default=DEFAULT_SYNTHESIS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    policy = load_s3_workpaper_writer_content_policy(args.policy)
    claim = _load(args.claim)
    synthesis = _load(args.synthesis)
    program = compile_s3_workpaper_writer_content_program(
        policy=policy, claim_decision=claim, synthesis_decision=synthesis
    )
    record = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s3_04_workpaper_writer_decision_v1_0",
        "recorded_at": RECORDED_AT,
        "acceptance": {
            "S3_04": "engineering_pass",
            "decision_ready_content_contracts": "3/3",
            "content_lenses": "24/24",
            "all_natural_workpapers": 0,
            "fixture_mixed_previews": "3/3_not_product_delivery",
            "planned_cells_promoted_as_findings": 0,
            "eight_dimension_case_passes": 0
        },
        "workpaper_writer_content_program": program,
        "canary_disposition": {
            "new_provider_output_schema": False,
            "model_visible_writer_input_activated": False,
            "additional_paid_canary_now": "not_required",
            "reason": "S3-04 compiles and validates a local no-source Writer packet and deterministic engineering preview only. Provider-visible Writer activation remains deferred to the single formal full chain after S3-05 deterministic gates."
        },
        "model_provider_network_source_business_runs": [0, 0, 0, 0, 0],
        "stage_boundary": {
            "S3_04": "engineering_pass",
            "S3_05": "next_not_started",
            "writer_runtime_natural_output": False,
            "product_delivery": False,
            "full_chain": False,
            "product_acceptance": False,
            "release": False
        },
        "known_boundary": "The three Workpapers are substantive deterministic engineering previews over mixed natural/fixture Claim authority. They expose uncovered research lenses and must not be shown as completed business research or used for product/release acceptance.",
        "current_next": "FIN-0.1.3-013-S3-05-EIGHT-DIMENSION-VERIFIER-PAIRED-QUALITY-GATE-ENTRY-AUDIT"
    }
    record["record_digest"] = canonical_digest(record)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(args.output), "record_digest": record["record_digest"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
