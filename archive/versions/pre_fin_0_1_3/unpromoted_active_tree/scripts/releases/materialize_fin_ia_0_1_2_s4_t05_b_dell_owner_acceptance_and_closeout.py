from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.releases.assess_fin_ia_0_1_2_s4_t05_b_dell_current_evidence_product_pair import (  # noqa: E402
    DEFAULT_OUTPUT as FORMAL_ASSESSMENT,
    validate_formal_paired_assessment,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


EXPECTED_ASSESSMENT_DIGEST = (
    "c86bf7bfa55d2dd15eab3f27557ffe5c1e5038e40f4820bec5659aa30d2383c4"
)
EXPECTED_ASSESSMENT_SHA256 = (
    "165607b9f5561e55e893f4b1e7cbb7af0ae26490ec25e336e36bc46c7b0f8d79"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_owner_acceptance_"
    "and_closeout_v1_0.json"
)


class T05BDellOwnerAcceptanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T05BDellOwnerAcceptanceError(code)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "s4_t05_b_owner_json_object_required")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize() -> dict[str, Any]:
    assessment = validate_formal_paired_assessment(_load(FORMAL_ASSESSMENT))
    _require(
        assessment.get("assessment_digest") == EXPECTED_ASSESSMENT_DIGEST
        and _sha256(FORMAL_ASSESSMENT) == EXPECTED_ASSESSMENT_SHA256,
        "s4_t05_b_owner_formal_assessment_drift",
    )
    owner_request = assessment["owner_decision_request"]
    _require(
        owner_request.get("recommended_decision")
        == "accept_current_DELL_R2_with_RC_P36_119_deferred"
        and owner_request.get("material_gain_accepted") is None,
        "s4_t05_b_owner_request_not_pending_expected_decision",
    )
    body = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t05_b_dell_owner_acceptance_and_closeout_v1_0"
        ),
        "decision_id": "FIN-0.1.2-S4-T05-B-DELL-OWNER-ACCEPTANCE-R1",
        "recorded_at": "2026-08-05T15:25:00+08:00",
        "status": "owner_accepted_DELL_current_R2_T05_B_closed",
        "authority": {
            "user_message": "接受",
            "user_message_interpreted_as": (
                "explicit_acceptance_of_the_presented_DELL_owner_decision"
            ),
            "formal_assessment_presented_before_decision": True,
            "owner_acceptance_authorized": True,
            "T05_C_entry_authorized": True,
            "T05_C_execution_started": False,
        },
        "source_formal_assessment": {
            "ref": FORMAL_ASSESSMENT.relative_to(ROOT).as_posix(),
            "sha256": EXPECTED_ASSESSMENT_SHA256,
            "assessment_digest": EXPECTED_ASSESSMENT_DIGEST,
            "L1_L2_L3_L4": [
                assessment["L1_deterministic_integrity"]["status"],
                assessment["L2_evidence_reliability_and_coverage"]["status"],
                assessment["L3_agent_gain"]["status"],
                assessment["L4_final_delivery"]["status"],
            ],
        },
        "owner_decision": {
            "decision": "accept_current_DELL_R2_with_RC_P36_119_deferred",
            "material_gain_accepted": True,
            "owner_comment": "接受",
            "accepted_product_scope": (
                "current source-grounded DELL R2 within FIN 0.1.2 S4-T05-B"
            ),
        },
        "acceptance_effect": {
            "S4_T05_B": "pass_closed_owner_accepted",
            "DELL_current_R2": True,
            "S4_T05_C_entry": "authorized_not_started",
            "MU_current_R2": False,
            "post_transfer_NVDA_R2": False,
        },
        "preserved_boundaries": {
            "RC_P36_119": "open_nonblocking_deferred_T08_T10_S5",
            "RC_P36_115": "open_S5_cross_runtime_lock",
            "qualified_human_review": False,
            "NVDA_R3": False,
            "S4_product_acceptance": False,
            "S5_entered": False,
            "release": "not_qualified",
            "production": "not_qualified",
            "additional_model_provider_network_source_calls": 0,
        },
        "observed_counts": {
            "owner_decisions": 1,
            "new_model_calls": 0,
            "new_provider_calls": 0,
            "new_execution_network_calls": 0,
            "new_source_network_calls": 0,
            "exact_live_reruns": 0,
            "T05_C_runs": 0,
        },
        "recommended_next": (
            "FIN-0.1.2-S4-T05-C-MU-CURRENT-R2-FRESH-ZERO-CALL-"
            "ENTRY-AND-DEPENDENCY-DECISION"
        ),
    }
    return validate_owner_acceptance(
        {**body, "decision_digest": canonical_digest(body)}
    )


def validate_owner_acceptance(value: Mapping[str, Any]) -> dict[str, Any]:
    body = {
        key: row for key, row in value.items() if key != "decision_digest"
    }
    _require(
        value.get("decision_digest") == canonical_digest(body),
        "s4_t05_b_owner_decision_digest_mismatch",
    )
    authority = value.get("authority") or {}
    decision = value.get("owner_decision") or {}
    effect = value.get("acceptance_effect") or {}
    boundary = value.get("preserved_boundaries") or {}
    counts = value.get("observed_counts") or {}
    _require(
        value.get("status") == "owner_accepted_DELL_current_R2_T05_B_closed"
        and authority.get("user_message") == "接受"
        and authority.get("owner_acceptance_authorized") is True
        and decision.get("material_gain_accepted") is True
        and decision.get("decision")
        == "accept_current_DELL_R2_with_RC_P36_119_deferred"
        and effect.get("S4_T05_B") == "pass_closed_owner_accepted"
        and effect.get("DELL_current_R2") is True,
        "s4_t05_b_owner_acceptance_semantics_invalid",
    )
    _require(
        authority.get("T05_C_entry_authorized") is True
        and authority.get("T05_C_execution_started") is False
        and effect.get("S4_T05_C_entry") == "authorized_not_started"
        and effect.get("MU_current_R2") is False
        and boundary.get("RC_P36_119")
        == "open_nonblocking_deferred_T08_T10_S5"
        and boundary.get("release") == "not_qualified"
        and boundary.get("production") == "not_qualified"
        and counts.get("owner_decisions") == 1
        and counts.get("T05_C_runs") == 0,
        "s4_t05_b_owner_acceptance_boundary_invalid",
    )
    return dict(value)


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
    decision = materialize()
    _write_atomic(args.output.resolve(), decision)
    print(
        json.dumps(
            {
                "status": decision["status"],
                "output": args.output.resolve().as_posix(),
                "decision_digest": decision["decision_digest"],
                "DELL_current_R2": decision["acceptance_effect"][
                    "DELL_current_R2"
                ],
                "next": decision["recommended_next"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
