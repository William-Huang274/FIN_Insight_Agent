from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.fin_0_1_2_s3_t04_product_surface import (  # noqa: E402
    materialize_verified_product_surface,
    validate_verified_product_surface,
)
from scripts.releases.run_fin_ia_0_1_2_s4_t04_nvda_current_evidence_capacity_reproof_exact_live import (  # noqa: E402
    ADMISSION,
    EXECUTION_IDENTITY,
    EXPECTED_ADMISSION_DIGEST,
    EXPECTED_ISSUANCE_DIGEST,
    ISSUANCE,
)
from scripts.releases.run_fin_ia_0_1_2_s4_t04_nvda_current_evidence_exact_live import (  # noqa: E402
    load_exact_target_for,
    prepare_exact_current_input,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


EXACT_RESULT = ROOT / (
    ".codex_runtime/"
    "fin012-s4-t04-nvda-current-evidence-capacity-reproof-exact-live-r3/"
    "execution-result.json"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t04_nvda_current_evidence_r3_"
    "verified_product_surface_and_read_only_assessment_v1_0.json"
)


class S4T04ProductSurfaceMaterializationError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T04ProductSurfaceMaterializationError(code)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "s4_t04_product_surface_json_required")
    return value


def _artifact_map(result: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row["artifact_type"]): row["payload"]
        for row in result.get("artifacts", ())
        if isinstance(row, Mapping) and isinstance(row.get("payload"), Mapping)
    }


def materialize() -> dict[str, Any]:
    before_sha = hashlib.sha256(EXACT_RESULT.read_bytes()).hexdigest()
    _require(
        before_sha
        == "6f06be07041afc6c46d991ea9372ff487293bf7f1ba9ded96f2194659b302fc9",
        "s4_t04_R3_exact_result_drift",
    )
    exact_result = _load(EXACT_RESULT)
    admission, issuance = load_exact_target_for(
        admission_path=ADMISSION,
        issuance_path=ISSUANCE,
        expected_admission_digest=EXPECTED_ADMISSION_DIGEST,
        expected_issuance_digest=EXPECTED_ISSUANCE_DIGEST,
        execution_identity=EXECUTION_IDENTITY,
    )
    with tempfile.TemporaryDirectory(
        prefix="fin012-s4-t04-r3-product-surface-"
    ) as temporary:
        prepared = prepare_exact_current_input(
            Path(temporary),
            admission,
            issuance,
            execution_identity=EXECUTION_IDENTITY,
        )
    surface = materialize_verified_product_surface(
        execution_result=exact_result,
        input_pack=prepared.input_pack.model_dump(mode="json"),
    )
    validate_verified_product_surface(surface)
    _require(
        hashlib.sha256(EXACT_RESULT.read_bytes()).hexdigest() == before_sha,
        "s4_t04_R3_exact_result_was_modified",
    )

    artifacts = _artifact_map(exact_result)
    judgment = artifacts["bounded_agent_judgment"]
    specialists = judgment.get("specialist_outputs") or []
    tasks = [
        task
        for specialist in specialists
        for task in specialist.get("what_would_change", ())
    ]
    generic_task_count = sum(
        "绑定权威观察"
        in str(
            (task.get("decision_rule") or {}).get(
                "threshold_or_observation"
            )
            or ""
        )
        for task in tasks
    )
    qualification = surface["fixture_evidence_qualification"]
    assessment = {
        "L1_deterministic_integrity": "pass_from_R3_independent_assessment",
        "L2_authority_coverage": (
            "pass_two_evidence_cells_one_numeric_authority_cell"
        ),
        "L3_agent_gain": "limited_positive_formal_paired_baseline_pending",
        "L4_final_delivery": "pass_after_local_verified_rendering",
        "qualified_evidence_cells": qualification["qualified_evidence_cells"],
        "qualified_authority_cells": qualification[
            "qualified_authority_cells"
        ],
        "claim_count": sum(
            len(row.get("judgment_layer") or ()) for row in specialists
        ),
        "what_would_change_task_count": len(tasks),
        "generic_what_would_change_task_count": generic_task_count,
        "cross_cell_dependency_conflict_gap_counts": [
            len(
                (judgment.get("cross_cell_lead") or {}).get(
                    "cross_cell_dependencies"
                )
                or ()
            ),
            len(
                (judgment.get("cross_cell_lead") or {}).get(
                    "conflict_adjudications"
                )
                or ()
            ),
            len(
                (judgment.get("cross_cell_lead") or {}).get("remaining_gaps")
                or ()
            ),
        ],
        "formal_distinct_deterministic_baseline_run": "not_materialized",
        "formal_paired_assessment": "not_performed",
        "owner_acceptance": False,
    }
    record_body = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t04_nvda_current_evidence_r3_"
            "verified_product_surface_and_read_only_assessment_v1_0"
        ),
        "status": (
            "RC_P36_118_zero_call_repaired_surface_pass_"
            "formal_paired_and_owner_pending"
        ),
        "source_exact_result": {
            "ref": EXACT_RESULT.relative_to(ROOT).as_posix(),
            "sha256": before_sha,
            "terminal_object_digest": exact_result["terminal_object"]["digest"],
            "immutable": True,
        },
        "product_surface": surface,
        "read_only_assessment": assessment,
        "observed_counts": {
            "new_model_calls": 0,
            "new_provider_calls": 0,
            "new_execution_network_calls": 0,
            "new_source_network_calls": 0,
            "new_external_tool_calls": 0,
            "exact_live_reruns": 0,
            "R4_attempts": 0,
        },
        "acceptance_boundary": {
            "RC_P36_118_engineering": "fixture_and_R3_replay_pass",
            "S4_T04_product_acceptance": (
                "pending_formal_distinct_baseline_paired_assessment_and_owner"
            ),
            "current_source_grounded_NVDA_R2": False,
            "S4_T05_entry": "blocked",
        },
        "recommended_next": (
            "FIN-0.1.2-S4-T04-DISTINCT-ZERO-CALL-DETERMINISTIC-BASELINE-"
            "FORMAL-PAIRED-ASSESSMENT-AND-OWNER-DECISION"
        ),
    }
    return {**record_body, "record_digest": canonical_digest(record_body)}


def _write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists():
        existing = _load(path)
        _require(
            existing.get("schema_version") == value.get("schema_version"),
            "s4_t04_product_surface_output_schema_mismatch",
        )
        if path.read_text(encoding="utf-8") == encoded:
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = materialize()
    _write_atomic(args.output.resolve(), result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": args.output.resolve().as_posix(),
                "record_digest": result["record_digest"],
                "preview_digest": result["product_surface"][
                    "final_delivery_preview"
                ]["final_delivery_preview_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
