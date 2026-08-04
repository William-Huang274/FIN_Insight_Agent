from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3ThreeCellBoundedAgentAdmission,
)
from apps.workbench.backend.application.fin_0_1_2_s4_natural_case_entry import (  # noqa: E402
    load_current_fin_0_1_2_s4_t01_case_entry,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t04_current_evidence_research import (  # noqa: E402
    compile_current_t04_execution_envelope,
    prepare_current_nvda_agent_execution,
    validate_current_nvda_evidence_pack,
)
from apps.workbench.backend.application.research_runtime import (  # noqa: E402
    prepare_s3_three_cell_bounded_agent_exact_input,
)
from scripts.releases.run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live import (  # noqa: E402
    _principal,
    rehydrate_exact_input_services,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


PACK = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t04_nvda_current_evidence_pack_v1_0.json"
)
TEMPLATE = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s3_t03_nvda_replacement_fresh_exact_admission_r2.json"
)
ADMISSION_REF = (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t04_nvda_current_evidence_fresh_exact_admission_r1.json"
)
EXECUTION_IDENTITY = "fin012-s4-t04-nvda-current-evidence-exact-live-r1"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("s4_t04_admission_source_object_required")
    return value


def render_issuance() -> tuple[dict[str, Any], dict[str, Any]]:
    pack = validate_current_nvda_evidence_pack(_load(PACK))
    template = S3ThreeCellBoundedAgentAdmission.model_validate(_load(TEMPLATE))
    with tempfile.TemporaryDirectory(prefix="fin012-s4-t04-admission-") as temporary:
        local, evidence, case, accepted = rehydrate_exact_input_services(
            Path(temporary)
        )
        baseline = prepare_s3_three_cell_bounded_agent_exact_input(
            local,
            evidence,
            str(case["case_id"]),
            _principal(),
            decision_surface_contract_ref=str(accepted["contract_version_id"]),
            execution_identity=EXECUTION_IDENTITY,
        )
    prepared = prepare_current_nvda_agent_execution(
        baseline,
        pack,
        t01_entry=load_current_fin_0_1_2_s4_t01_case_entry("NVDA"),
        principal=_principal(),
        execution_identity=EXECUTION_IDENTITY,
    )
    admission = template.model_copy(
        update={
            "admission_id": "fin012-s4-t04-nvda-current-evidence-exact-admission-r1",
            "execution_mode": "exact_live_fin_0_1_2_s4_t04_current_evidence_r1",
            "case_id": prepared.case_id,
            "case_version": prepared.case_version,
            "as_of": prepared.input_pack.as_of,
            "input_digest": prepared.input_digest,
        }
    )
    admission.assert_profile_admissible()
    if (
        admission.model != "deepseek-v4-pro"
        or admission.max_provider_calls != 9
        or admission.max_semantic_model_calls != 9
        or admission.max_network_calls != 9
        or admission.max_transport_attempts_per_call != 1
        or admission.retry_budget != 0
        or admission.max_total_cost_usd != 0.06
        or admission.source_network_calls_allowed
        or admission.external_tool_calls_allowed
        or admission.live_business_case_head_writes_allowed
    ):
        raise ValueError("s4_t04_admission_budget_or_model_drift")
    admission_payload = admission.model_dump(mode="json")
    admission_digest = canonical_digest(admission.digest_payload())
    envelope = compile_current_t04_execution_envelope(
        prepared,
        pack,
        admission_ref=ADMISSION_REF,
    )
    issuance_body = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t04_current_evidence_fresh_exact_admission_"
            "issuance_v1_0"
        ),
        "status": "issued_unconsumed_zero_call_preflight_pass",
        "issued_admission": {
            "admission_id": admission.admission_id,
            "admission_digest": admission_digest,
            "admission_ref": ADMISSION_REF,
            "execution_identity": EXECUTION_IDENTITY,
            "consumed": False,
            "execution_started": False,
        },
        "exact_binding": {
            "case_id": prepared.case_id,
            "case_version": prepared.case_version,
            "as_of": prepared.input_pack.as_of,
            "complete_input_digest": prepared.input_digest,
            "preparation_digest": prepared.preparation_digest,
            "predicted_work_unit_id": prepared.work_unit_id,
            "predicted_attempt_id": prepared.attempt_id,
            "predicted_research_run_id": prepared.research_run_id,
            "evidence_pack_digest": pack["evidence_pack_digest"],
            "t03_terminal_digest": pack["t03_terminal_digest"],
        },
        "execution_envelope": envelope,
        "observed_counts": {
            "credential_reads_or_probes": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "business_artifacts": 0,
        },
        "authority_boundary": {
            "user_sequence_authorized_continuation": True,
            "admission_issuance_authorized": True,
            "exact_live_execution_authorized_after_fresh_preflight": True,
            "automatic_retry_or_second_live": False,
            "owner_acceptance_auto_granted": False,
        },
    }
    issuance = {
        **issuance_body,
        "issuance_digest": canonical_digest(issuance_body),
    }
    return admission_payload, issuance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("admission", "issuance"), required=True)
    args = parser.parse_args()
    admission, issuance = render_issuance()
    print(
        json.dumps(
            admission if args.kind == "admission" else issuance,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
