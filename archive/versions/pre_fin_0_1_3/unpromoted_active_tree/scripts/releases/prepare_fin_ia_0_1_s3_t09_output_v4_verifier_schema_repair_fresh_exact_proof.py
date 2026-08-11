from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.releases.prepare_fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_proof import (
    prepare as prepare_claim_fact_proof,
)


RELEASES = ROOT / "configs" / "releases"
RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
EXECUTION_IDENTITY = (
    "fin01-s3-t09-three-cell-deepseek-output-v4-verifier-schema-repair-"
    "live-validation-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-output-v4-verifier-schema-repair-"
    "exact-admission-r1"
)
PROSPECTIVE_ADMISSION_FILE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_"
    "output_v4_verifier_schema_repair_exact_admission_r1.json"
)
DECISION_STATUS = (
    "pass_zero_call_output_v4_verifier_schema_repair_fresh_exact_proof_"
    "contract_frozen_bundled_issuance_and_one_live_authorized"
)
IMPLEMENTATION_STATUS = (
    "pass_zero_call_output_v4_verifier_schema_alignment_fixture_proven_"
    "fresh_exact_proof_pending"
)
FAILED_LIVE_STATUS = (
    "terminal_failed_hard_output_v4_verifier_prompt_validator_schema_drift_"
    "no_second_execution_authorized"
)


class VerifierSchemaRepairFreshProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise VerifierSchemaRepairFreshProofError(code)


def prepare(
    *,
    runtime_root: Path,
    repair_result_path: Path,
    failed_live_result_path: Path,
) -> dict[str, Any]:
    repair = json.loads(repair_result_path.read_text(encoding="utf-8"))
    failed_live = json.loads(failed_live_result_path.read_text(encoding="utf-8"))
    _require(
        repair.get("status") == IMPLEMENTATION_STATUS,
        "verifier_schema_repair_not_fixture_proven",
    )
    implementation = repair.get("implementation") or {}
    _require(
        implementation.get("request_builder_consumes_shared_predicate") is True
        and implementation.get("validator_consumes_shared_predicate") is True
        and implementation.get("fixture_checks_required_output_schema") is True
        and implementation.get("validator_relaxed") is False,
        "verifier_schema_repair_contract_incomplete",
    )
    _require(
        failed_live.get("status") == FAILED_LIVE_STATUS
        and failed_live.get("failure", {}).get("failure_code")
        == "s3_bounded_verifier_finding_schema_invalid"
        and failed_live.get("canonical_terminal_truth", {}).get("artifact_count")
        == 0,
        "verifier_schema_source_failure_truth_mismatch",
    )

    result = prepare_claim_fact_proof(
        runtime_root=runtime_root,
        implementation_result_path=RELEASES
        / "fin_ia_0_1_s3_t09_claim_fact_link_policy_closed_alias_"
        "zero_call_implementation_v1_0.json",
        final_failure_result_path=RELEASES
        / "fin_ia_0_1_s3_t09_research_lead_v5_profile_v3_final_"
        "exact_live_execution_result_v1_0.json",
        execution_identity=EXECUTION_IDENTITY,
        prospective_admission_id=PROSPECTIVE_ADMISSION_ID,
        prospective_admission_file=PROSPECTIVE_ADMISSION_FILE,
        execution_mode=(
            "exact_live_three_cell_deepseek_output_v4_verifier_"
            "schema_repair_r1"
        ),
        decision_status=DECISION_STATUS,
        decision_contract_ref=(
            "fin01.s3.output_v4_verifier_schema_repair_fresh_exact_proof:"
            "v1"
        ),
        additional_source_failed_result_paths=(failed_live_result_path,),
    )
    result["source_refs"]["output_v4_verifier_schema_repair"] = (
        repair_result_path.resolve().relative_to(ROOT).as_posix()
    )
    result["source_refs"]["output_v4_verifier_schema_failure"] = (
        failed_live_result_path.resolve().relative_to(ROOT).as_posix()
    )
    result["verifier_schema_repair_acceptance_contract"] = {
        "output_contract_ref": "fin01.s3.bounded_agent_three_cell_output:v4",
        "request_and_validator_shared_typed_contract_set": True,
        "required_finding_keys": [
            "layer",
            "status",
            "issue_codes",
            "artifact_or_claim_refs",
            "repair_owner",
        ],
        "all_four_layers_required": True,
        "lead_and_writer_digest_binding_required": True,
        "fixture_request_schema_conformance_required": True,
        "legacy_v1_v2_behavior_unchanged": True,
        "validator_relaxation_or_fallback_allowed": False,
    }
    result["experiment_governance"].update(
        {
            "hypothesis": (
                "The shared typed-Verifier contract predicate repairs the only "
                "known immediate output-v4 blocker while preserving the already "
                "observed ClaimFactLinkPolicy live path."
            ),
            "decision_target": (
                "One new exact run must reach terminal succeeded with six logical "
                "nodes, twelve calls, nine Artifacts, typed four-layer Verifier "
                "findings, valid digest bindings, valid Claim-to-Fact lineage and "
                "zero restricted-capture or canonical residue violations."
            ),
            "stop_condition": (
                "The first credible parse, schema, semantic, authority, identity, "
                "length, budget, terminalization, capture or artifact failure "
                "stops without retry, fallback, patch or second run."
            ),
            "decision_label": (
                "proceed_to_bundled_exact_admission_issuance_and_one_live_execution"
            ),
            "admission_issuance_authorized": True,
            "admission_consumption_authorized": True,
            "live_execution_authorized": True,
            "automatic_retry_fallback_patch_or_rerun_authorized": False,
            "paired_comparison_or_owner_acceptance_authorized": (
                "only_after_complete_live_success"
            ),
        }
    )
    result["next_action"] = (
        "S3-T09-OUTPUT-V4-VERIFIER-SCHEMA-REPAIR-FRESH-EXACT-"
        "ADMISSION-ISSUANCE-AND-ONE-LIVE-EXECUTION"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(
        runtime_root=args.runtime_root,
        repair_result_path=RELEASES
        / "fin_ia_0_1_s3_t09_output_v4_verifier_schema_alignment_"
        "zero_call_implementation_v1_0.json",
        failed_live_result_path=RELEASES
        / "fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_"
        "live_execution_result_v1_0.json",
    )
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
