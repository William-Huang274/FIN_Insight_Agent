from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402


CONTEXT = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s2_03_context_yield_and_capacity_zero_call_v1_0.json"
QUALITY = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_05_research_quality_gate_v1_0.json"
POLICY = ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_execution_policy_v1_0.json"
OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_admission_readiness_v1_0.json"
CODE_REFS = (
    "src/sec_agent/s3_formal_anchor_runtime.py",
    "scripts/releases/run_fin_ia_0_1_3_repair_closeout_s3_formal_anchor.py",
    "src/sec_agent/s3_claim_quality_program.py",
    "src/sec_agent/s3_cross_cell_synthesis_program.py",
    "src/sec_agent/s3_workpaper_writer_content_program.py",
    "src/sec_agent/s3_research_quality_gate.py",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    context = _load(CONTEXT)
    quality = _load(QUALITY)
    policy = _load(POLICY)
    rows = context["role_scoped_contexts"]
    record = {
        "schema_version": "fin_ia_0_1_3_s3_formal_anchor_admission_readiness_v1_0",
        "recorded_at": "2026-08-06T19:10:00+08:00",
        "status": "engineering_pass_fresh_admission_eligible_after_clean_synced_commit",
        "authority": {
            "user_instruction": "继续",
            "formal_full_chain_scope": "nine bounded Specialist selectors followed by local Claim, Lead, Workpaper and quality-gate compilation",
            "admission_issued": False,
            "execution_started": False,
            "automatic_retry_fallback_or_second_run": False,
        },
        "entry_corrections": {
            "missing_FIN_0_1_3_formal_runner": "closed_by_exact_once_capture_first_nine_request_runner",
            "fixture_count_frozen_successor_validators": "closed_by_authority_derived_claim_lead_writer_quality_validation",
            "writer_model_free_text_required": False,
            "writer_model_free_text_reason": "The accepted architecture keeps model authority at bounded judgment aliases and compiles final content locally; the rubric explicitly permits reducing model surface when local composition is equal or better.",
        },
        "zero_call_full_fake_proof": {
            "provider_callbacks": 9,
            "capture_first_objects": 9,
            "natural_claim_cards": 9,
            "all_natural_case_syntheses": 3,
            "all_natural_workpapers": 3,
            "quality_gate_entries": 3,
            "formal_scores_or_human_acceptances": 0,
            "first_failure_stop_proven_at_call": 4,
            "skipped_after_failure": 5,
            "shared_admission_second_consumption": "fail_closed",
            "focused_tests": "5 passed before materialized-record assertion",
        },
        "capacity": {
            "request_count": len(rows),
            "aggregate_compact_characters": sum(int(row["capacity"]["compact_characters"]) for row in rows),
            "maximum_single_request_compact_characters": max(int(row["capacity"]["compact_characters"]) for row in rows),
            "maximum_provider_calls": policy["budget"]["maximum_provider_calls"],
            "retry_count": policy["budget"]["retry_count"],
            "fallback_count": policy["budget"]["fallback_count"],
        },
        "bindings": {
            "context_program_sha256": _sha(CONTEXT),
            "quality_gate_sha256": _sha(QUALITY),
            "execution_policy_sha256": _sha(POLICY),
            "code_sha256": {ref: _sha(ROOT / ref) for ref in CODE_REFS},
        },
        "admission_disposition": {
            "eligible_after_clean_synced_commit": True,
            "credential_presence_required": True,
            "one_fresh_admission": True,
            "one_exact_once_execution": True,
            "provider": policy["provider"]["backend"],
            "model": policy["provider"]["model"],
            "request_count": 9,
            "retry_or_fallback": 0,
        },
        "stage_boundary": {
            "S3_05_deterministic_gate": "engineering_pass",
            "formal_anchor_runner": "engineering_pass_full_fake",
            "formal_anchor_live": False,
            "formal_case_quality_pass": False,
            "paired_material_gain": False,
            "qualified_human_content_acceptance": False,
            "S3_product_proof": False,
            "S4_entry": False,
            "release": False,
        },
        "model_provider_network_source_business_runs": [0, 0, 0, 0, 0],
        "known_boundary": "Full-fake proves exact-once execution and all-natural successor materialization shape, not DeepSeek natural output quality, final L1/L2, eight-dimension scores, paired gain, human content acceptance or product pass.",
        "current_next": "COMMIT_PUSH_THEN_ISSUE_ONE_FRESH_S3_FORMAL_ANCHOR_ADMISSION_AND_EXECUTE_EXACT_ONCE",
    }
    record["record_digest"] = canonical_digest(record)
    OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": record["status"], "output": str(OUTPUT), "record_digest": record["record_digest"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
