from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.fin_0_1_2_s4_t05_current_case_product_surface import (  # noqa: E402
    materialize_current_case_deterministic_baseline,
    materialize_current_case_verified_product_surface,
    validate_current_case_pair_readiness,
)
from scripts.releases.materialize_fin_ia_0_1_2_s4_t05_d_nvda_agent_exact_live_result_and_assessment import (  # noqa: E402
    AGENT_INPUT,
    EXACT_RESULT,
    EXPECTED_RESULT_SHA256,
    OUTPUT as EXACT_ASSESSMENT,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


BASELINE_RUNTIME = ROOT / (
    ".codex_runtime/"
    "fin012-s4-t05d-nvda-current-evidence-deterministic-baseline-r1"
)
BASELINE_RESULT = BASELINE_RUNTIME / "execution-result.json"
BASELINE_EXECUTION_IDENTITY = (
    "fin012-s4-t05d-nvda-current-evidence-deterministic-baseline-r1"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t05_d_nvda_verified_product_surface_"
    "and_paired_readiness_v1_0.json"
)


class T05DNVDAProductSurfaceMaterializationError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T05DNVDAProductSurfaceMaterializationError(code)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "s4_t05_d_nvda_surface_json_object_required")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize() -> tuple[dict[str, Any], dict[str, Any]]:
    before_sha = _sha256(EXACT_RESULT)
    _require(
        before_sha == EXPECTED_RESULT_SHA256,
        "s4_t05_d_nvda_surface_exact_result_drift",
    )
    exact_result = _load(EXACT_RESULT)
    input_pack = _load(AGENT_INPUT)
    exact_assessment = _load(EXACT_ASSESSMENT)
    surface = materialize_current_case_verified_product_surface(
        execution_result=exact_result,
        input_pack=input_pack,
        expected_case_ticker="NVDA",
    )
    baseline = materialize_current_case_deterministic_baseline(
        input_pack=input_pack,
        expected_case_ticker="NVDA",
        execution_identity=BASELINE_EXECUTION_IDENTITY,
    )
    readiness = validate_current_case_pair_readiness(
        exact_result=exact_result,
        baseline_result=baseline,
        surface_result=surface,
        expected_case_ticker="NVDA",
    )
    _require(
        _sha256(EXACT_RESULT) == before_sha,
        "s4_t05_d_nvda_surface_exact_result_was_modified",
    )
    preview = surface["final_delivery_preview"]
    verifier = surface["final_delivery_verification"]
    qualification = surface["fixture_evidence_qualification"]
    independent_l1 = exact_assessment["independent_L1"]
    output_counts = exact_assessment["agent_output_counts"]
    body = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t05_d_nvda_verified_product_surface_and_"
            "paired_readiness_v1_0"
        ),
        "recorded_at": "2026-08-05T18:30:00+08:00",
        "status": (
            "NVDA_zero_call_product_surface_L4_pass_paired_readiness_pass_"
            "formal_paired_and_owner_pending"
        ),
        "source_exact_result": {
            "ref": EXACT_RESULT.relative_to(ROOT).as_posix(),
            "sha256": before_sha,
            "terminal_object_digest": exact_result["terminal_object"]["digest"],
            "immutable": True,
        },
        "source_independent_assessment": {
            "ref": EXACT_ASSESSMENT.relative_to(ROOT).as_posix(),
            "sha256": _sha256(EXACT_ASSESSMENT),
            "assessment_digest": exact_assessment["assessment_digest"],
        },
        "product_surface": surface,
        "deterministic_baseline": {
            "ref": BASELINE_RESULT.relative_to(ROOT).as_posix(),
            "execution_identity": baseline["execution_identity"],
            "result_digest": baseline["result_digest"],
            "business_promotable": False,
        },
        "paired_readiness": readiness,
        "layered_assessment": {
            "L1_deterministic_integrity": independent_l1["status"],
            "L2_authority_coverage": "pass_three_of_three_cells",
            "L3_agent_gain": "pending_formal_paired_assessment",
            "L4_final_delivery": "pass_after_case_generic_local_rendering",
            "agent_output_counts": output_counts,
            "qualified_evidence_cells": qualification[
                "qualified_evidence_cells"
            ],
            "qualified_authority_cells": qualification[
                "qualified_authority_cells"
            ],
            "preview_digest": preview["final_delivery_preview_digest"],
            "local_verifier_digest": verifier["verification_digest"],
            "internal_token_currency_duplication_or_unlocalized_limitation": 0,
        },
        "observed_counts": {
            "new_model_calls": 0,
            "new_provider_calls": 0,
            "new_execution_network_calls": 0,
            "new_source_network_calls": 0,
            "new_external_tool_calls": 0,
            "exact_live_reruns": 0,
            "deterministic_baseline_runs": 1,
            "formal_paired_assessments": 0,
            "owner_decisions": 0,
        },
        "acceptance_boundary": {
            "S4_T05_D_NVDA_engineering": "pass",
            "S4_T05_D_NVDA_agent_exact_live": "pass",
            "S4_T05_D_NVDA_final_delivery": "pass",
            "post_transfer_NVDA_R2": False,
            "formal_paired_L1_L4": "pending",
            "owner_acceptance": "pending",
            "S4_T06_entry": "blocked_pending_T05_D_owner_acceptance",
            "RC_P36_119": "deferred_nonblocking_T08_T10_S5",
            "RC_P36_122": "MU_specific_deferred_not_reclassified_as_NVDA_finding",
            "RC_P36_115": "open_blocks_S5_not_T05_D_surface",
        },
        "recommended_next": (
            "FIN-0.1.2-S4-T05-D-NVDA-FORMAL-PAIRED-L1-L4-ASSESSMENT-"
            "AND-OWNER-DECISION"
        ),
    }
    return baseline, {**body, "record_digest": canonical_digest(body)}


def _write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == encoded:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    baseline, record = materialize()
    _write_atomic(BASELINE_RESULT, baseline)
    _write_atomic(args.output.resolve(), record)
    print(
        json.dumps(
            {
                "status": record["status"],
                "output": args.output.resolve().as_posix(),
                "record_digest": record["record_digest"],
                "preview_digest": record["layered_assessment"][
                    "preview_digest"
                ],
                "local_verifier_digest": record["layered_assessment"][
                    "local_verifier_digest"
                ],
                "paired_readiness": record["paired_readiness"]["status"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
