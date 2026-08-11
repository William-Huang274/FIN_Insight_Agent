from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentInputPack,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_three_case_transfer import (
    EXPECTED_CASES,
    Fin012S4T05TransferError,
    compile_current_case_agent_input,
)
from sec_agent.canonical_runtime.models import canonical_digest


CONTRACT_REF = "fin_0_1_2.S4.T05_B.current_product_identity:v1"


def compile_current_product_case_identity(
    case_key: str,
    *,
    t01_entry_digest: str,
    evidence_pack_digest: str,
) -> str:
    """Derive a current product Case ID without changing the frozen T05-A compiler."""

    if case_key not in EXPECTED_CASES:
        raise Fin012S4T05TransferError("s4_t05_b_current_case_identity_case_invalid")
    for value in (t01_entry_digest, evidence_pack_digest):
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise Fin012S4T05TransferError(
                "s4_t05_b_current_case_identity_digest_invalid"
            )
    identity_digest = canonical_digest(
        {
            "contract_ref": CONTRACT_REF,
            "case_key": case_key,
            "t01_entry_digest": t01_entry_digest,
            "evidence_pack_digest": evidence_pack_digest,
            "identity_role": "current_evidence_agent_product_case",
        }
    )
    return (
        f"fin012-s4-t05-{case_key.lower()}-current-evidence-"
        f"{identity_digest[:20]}"
    )


def compile_t05_b_current_product_agent_input(
    baseline: S3ThreeCellBoundedAgentInputPack,
    evidence_pack: Mapping[str, Any],
    *,
    case_key: str,
) -> S3ThreeCellBoundedAgentInputPack:
    """Rebind a compiled current-evidence input to a non-oracle product identity."""

    compiled = compile_current_case_agent_input(
        baseline,
        evidence_pack,
        case_key=case_key,
    )
    t01_entry_digest = str(evidence_pack.get("t01_entry_digest") or "")
    evidence_pack_digest = str(evidence_pack.get("evidence_pack_digest") or "")
    current_case_id = compile_current_product_case_identity(
        case_key,
        t01_entry_digest=t01_entry_digest,
        evidence_pack_digest=evidence_pack_digest,
    )
    input_head_digest = canonical_digest(
        (t01_entry_digest, evidence_pack_digest, current_case_id)
    )
    paired = deepcopy(compiled.paired_baseline_contract)
    paired["shared_input_head_digest"] = input_head_digest
    draft = compiled.model_copy(
        update={
            "case_id": current_case_id,
            "input_head_digest": input_head_digest,
            "paired_baseline_contract": paired,
        }
    )
    return draft.model_copy(
        update={
            "input_digest": canonical_digest(
                draft.model_dump(mode="json", exclude={"input_digest"})
            )
        }
    )


__all__ = [
    "CONTRACT_REF",
    "compile_current_product_case_identity",
    "compile_t05_b_current_product_agent_input",
]
