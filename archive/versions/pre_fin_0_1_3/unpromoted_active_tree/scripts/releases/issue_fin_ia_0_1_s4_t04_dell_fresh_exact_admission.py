from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from scripts.releases.prepare_fin_ia_0_1_s4_t04_dell_source_grounded_input_and_fresh_proof import (
    DECISION_PATH,
    PLANNING_PROFILE_PATH,
    PROSPECTIVE_ADMISSION_PATH,
    RUNTIME_ROOT,
    SOURCE_PACK_PATH,
    _case_service,
    _database_logical_digest,
    _execution_identity_presence,
    _logical_counts,
    prepare,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


ADMISSION = PROSPECTIVE_ADMISSION_PATH
ISSUANCE = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t04_dell_fresh_exact_admission_issuance_v1_0.json"
)
EXPECTED_DECISION_STATUS = (
    "pass_source_grounded_exact_input_head_materialized_"
    "fresh_proof_frozen_admission_issuance_pending"
)
EXPECTED_SOURCE_PACK_SHA256 = (
    "1a173ac6097195bdc6d2dd0f3d43544a947069d6848786f4fe9ca9eb805c8ec9"
)
EXPECTED_ADMISSION_DIGEST = (
    "da035e71d9eee81e9c76c5243a396bafaacfc29cd1f01e66eb1a66b8b757a60f"
)
NEXT_ACTION = (
    "S4-T05-DELL-EXACT-R2-EXECUTION-AND-PAIRED-ASSESSMENT-"
    "AUTHORITY-DECISION"
)
CODE_BINDING_PATHS = (
    Path("src/sec_agent/s4_case_runtime.py"),
    Path("apps/workbench/backend/application/bounded_agent_executor.py"),
    Path("apps/workbench/backend/application/research_runtime.py"),
    Path(
        "scripts/releases/"
        "prepare_fin_ia_0_1_s4_t04_dell_source_grounded_input_and_fresh_proof.py"
    ),
    Path(
        "scripts/releases/"
        "run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py"
    ),
    Path(
        "scripts/releases/"
        "issue_fin_ia_0_1_s4_t04_dell_fresh_exact_admission.py"
    ),
)


class S4DellExactAdmissionIssuanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4DellExactAdmissionIssuanceError(code)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_digest(root: Path) -> str:
    rows = []
    for path in sorted(row for row in root.rglob("*") if row.is_file()):
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha256(path),
                "byte_size": path.stat().st_size,
            }
        )
    return canonical_digest(rows)


def _exact_code_bindings() -> dict[str, str]:
    return {
        path.as_posix(): _sha256(ROOT / path)
        for path in CODE_BINDING_PATHS
    }


def _assert_frozen_proof_reprepared(
    frozen: Mapping[str, Any], regenerated: Mapping[str, Any]
) -> None:
    _require(
        regenerated == frozen,
        "s4_dell_frozen_proof_reprepare_mismatch",
    )
    _require(
        regenerated.get("status") == EXPECTED_DECISION_STATUS,
        "s4_dell_frozen_proof_status_mismatch",
    )
    materialized = regenerated["canonical_materialization"]
    _require(
        materialized["idempotent_second_materialization"] is True
        and materialized["logical_digest_after_first_materialization"]
        == materialized["logical_digest_after_second_materialization"],
        "s4_dell_materialization_not_logically_idempotent",
    )
    proof = regenerated["fresh_agent_proof"]
    _require(
        proof["decision"] == "frozen_unissued_unconsumed"
        and proof["double_prepare_parity"] is True
        and all(proof["freshness_and_nonreuse"].values()),
        "s4_dell_fresh_proof_not_issuable",
    )


def render_issuance() -> tuple[dict[str, Any], dict[str, Any]]:
    _require(not ADMISSION.exists(), "s4_dell_admission_already_exists")
    _require(not ISSUANCE.exists(), "s4_dell_issuance_already_exists")
    _require(
        _sha256(SOURCE_PACK_PATH) == EXPECTED_SOURCE_PACK_SHA256,
        "s4_dell_source_pack_digest_drift",
    )

    frozen_bytes = DECISION_PATH.read_bytes()
    frozen = json.loads(frozen_bytes)
    regenerated = prepare(RUNTIME_ROOT)
    _assert_frozen_proof_reprepared(frozen, regenerated)
    _require(
        DECISION_PATH.read_bytes() == frozen_bytes,
        "s4_dell_frozen_decision_byte_drift",
    )

    materialized = regenerated["canonical_materialization"]
    proof = regenerated["fresh_agent_proof"]
    prospective = proof["prospective_admission"]
    payload = prospective["payload"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    digest = canonical_digest(admission.digest_payload())
    _require(
        digest
        == prospective["digest"]
        == EXPECTED_ADMISSION_DIGEST,
        "s4_dell_admission_digest_mismatch",
    )
    _require(
        admission.company == "DELL"
        and admission.research_profile_ref
        == "fin01.s4.research_profile.dell_oem_three_cell:v1"
        and admission.execution_mode
        == "exact_live_s4_dell_source_grounded_three_cell_r1"
        and admission.retry_budget == 0
        and admission.max_transport_attempts_per_call == 1
        and admission.source_network_calls_allowed is False
        and admission.external_tool_calls_allowed is False
        and admission.live_business_case_head_writes_allowed is False,
        "s4_dell_admission_contract_binding_mismatch",
    )

    provider_callback_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal provider_callback_calls
        provider_callback_calls += 1
        raise AssertionError("provider_callback_forbidden_during_s4_issuance")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    _require(
        provider_callback_calls == 0,
        "s4_dell_provider_called_during_issuance",
    )

    canonical_root = RUNTIME_ROOT / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    logical_digest_before = _database_logical_digest(database_path)
    object_digest_before = _tree_digest(object_root)
    planning_profile = json.loads(
        PLANNING_PROFILE_PATH.read_text(encoding="utf-8")
    )
    service = _case_service(canonical_root, planning_profile)
    prepared_identity = {
        "work_unit_id": proof["work_unit_id"],
        "attempt_id": proof["attempt_id"],
        "research_run_id": proof["research_run_id"],
    }
    freshness = _execution_identity_presence(service, prepared_identity)
    _require(
        all(freshness.values()),
        "s4_dell_fresh_identity_reused_before_issuance",
    )
    logical_counts = _logical_counts(
        database_path, materialized["case_id"]
    )
    _require(
        all(
            logical_counts[table] == 0
            for table in (
                "canonical_work_units",
                "canonical_attempts",
                "canonical_research_run_versions",
                "canonical_artifact_versions",
            )
        ),
        "s4_dell_execution_state_exists_before_issuance",
    )
    maximum_output_tokens = (
        3 * admission.specialist_max_output_tokens
        + admission.lead_max_output_tokens
        + admission.writer_max_output_tokens
        + admission.verifier_max_output_tokens
    )
    code_bindings = _exact_code_bindings()
    issuance = {
        "schema_version": (
            "fin_ia_0_1_s4_t04_dell_fresh_exact_admission_"
            "issuance_v1_0"
        ),
        "issuance_id": "S4-T04-DELL-FRESH-EXACT-ADMISSION-ISSUANCE-R1",
        "issued_at": datetime.now(
            timezone(timedelta(hours=8))
        ).isoformat(timespec="seconds"),
        "status": "issued_unconsumed_zero_call_preflight_pass",
        "authority": {
            "user_instruction": "继续",
            "fresh_exact_admission_issuance_authorized": True,
            "admission_consumption_or_exact_live_execution_authorized": False,
            "automatic_retry_fallback_patch_or_rerun_authorized": False,
            "paired_comparison_or_Human_review_authorized": False,
            "S4_T05_or_later_authorized": False,
        },
        "source_decision_ref": DECISION_PATH.relative_to(ROOT).as_posix(),
        "source_decision_sha256": _sha256(DECISION_PATH),
        "source_pack_ref": SOURCE_PACK_PATH.relative_to(ROOT).as_posix(),
        "source_pack_sha256": _sha256(SOURCE_PACK_PATH),
        "issued_admission": {
            "admission_ref": ADMISSION.relative_to(ROOT).as_posix(),
            "admission_id": admission.admission_id,
            "admission_digest": digest,
            "runtime_root": RUNTIME_ROOT.relative_to(ROOT).as_posix(),
            "work_unit_idempotency_key": proof["execution_identity"],
            "fresh_identity": True,
            "execution_enabled": True,
            "consumed": False,
            "execution_started": False,
        },
        "exact_binding": {
            "case_id": materialized["case_id"],
            "case_version": materialized["case_version"],
            "decision_surface_contract_ref": materialized[
                "decision_surface_contract_ref"
            ],
            "as_of": admission.as_of,
            "input_head_digest": materialized["input_head_digest"],
            "input_object_ref": materialized["input_object_ref"],
            "input_digest": proof["input_digest"],
            "preparation_digest": proof["preparation_digest"],
            "predicted_work_unit_id": proof["work_unit_id"],
            "predicted_attempt_id": proof["attempt_id"],
            "predicted_research_run_id": proof["research_run_id"],
            "research_profile_ref": admission.research_profile_ref,
            "provider": admission.provider,
            "model": admission.model,
            "model_ref": admission.model_ref,
            "base_url": admission.base_url,
            "credential_env": admission.api_key_env,
            "output_contract_ref": admission.output_contract_ref,
            "specialist_transport_ref": admission.transport_ref,
            "research_lead_transport_ref": (
                admission.research_lead_transport_ref
            ),
            "memo_writer_transport_ref": (
                admission.memo_writer_transport_ref
            ),
            "scoped_identity_contract_ref": (
                admission.scoped_identity_contract_ref
            ),
            "claim_fact_link_policy_ref": (
                admission.claim_fact_link_policy_ref
            ),
            "provider_output_capture_policy_ref": (
                admission.provider_output_capture_policy_ref
            ),
        },
        "execution_envelope": {
            "maximum_semantic_model_calls": admission.max_semantic_model_calls,
            "maximum_provider_calls": admission.max_provider_calls,
            "maximum_network_calls": admission.max_network_calls,
            "maximum_transport_attempts_per_call": (
                admission.max_transport_attempts_per_call
            ),
            "retry_budget": admission.retry_budget,
            "maximum_output_tokens_total": maximum_output_tokens,
            "maximum_total_cost_usd": admission.max_total_cost_usd,
            "source_network_calls_allowed": False,
            "external_tool_calls_allowed": False,
            "live_business_case_head_writes_allowed": False,
            "automatic_retry_repair_fallback_or_rerun_allowed": False,
            "first_credible_failure": "terminal_fail_closed_stop",
        },
        "proof_reverification": {
            "generator_rerun_before_materialization": True,
            "frozen_and_regenerated_decision_byte_equal": True,
            "double_prepare_equal": True,
            "source_pack_digest_equal": True,
            "canonical_logical_digest": logical_digest_before,
            "canonical_execution_counts": logical_counts,
            "freshness_and_nonreuse": freshness,
            "exact_code_bindings": code_bindings,
            "exact_code_binding_count": len(code_bindings),
            "runtime_dispatch_consumes_source_grounded_S4_pack": True,
            "runner_preflight_dispatches_to_S4_exact_prepare": True,
        },
        "zero_call_preflight": {
            "provider_callback_invoked": False,
            "credential_presence_checked": False,
            "credential_value_read_output_or_persisted": False,
            "transport_retry_environment_zero": (
                os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") == "0"
            ),
            "exact_live_execution_precondition": (
                "LLM_GATEWAY_TRANSPORT_RETRIES must equal 0 and the "
                "configured provider credential must be present"
            ),
        },
        "issuance_boundary": {
            "admission_issued": True,
            "admission_consumed": False,
            "execution_started": False,
            "supervisor_launched": False,
            "model_or_provider_call_started": False,
            "business_artifact_materialization_performed": False,
            "paired_comparison_performed": False,
            "human_review_performed": False,
        },
        "observed_counts": {
            "new_admissions": 1,
            "admission_consumptions": 0,
            "work_units_created": 0,
            "attempts_created": 0,
            "research_runs_created": 0,
            "artifacts_created": 0,
            "model_calls": 0,
            "provider_calls": provider_callback_calls,
            "execution_network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
        },
        "next_action": NEXT_ACTION,
    }
    _require(
        _database_logical_digest(database_path) == logical_digest_before
        and _tree_digest(object_root) == object_digest_before
        and all(
            _execution_identity_presence(
                service, prepared_identity
            ).values()
        ),
        "s4_dell_issuance_changed_canonical_runtime",
    )
    return payload, issuance


def _write_and_validate(
    payload: Mapping[str, Any], issuance: Mapping[str, Any]
) -> None:
    temporary_paths: list[Path] = []
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix=".s4-dell-admission-",
            dir=ADMISSION.parent,
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temporary_admission = Path(handle.name)
            temporary_paths.append(temporary_admission)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix=".s4-dell-issuance-",
            dir=ISSUANCE.parent,
            delete=False,
        ) as handle:
            json.dump(issuance, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temporary_issuance = Path(handle.name)
            temporary_paths.append(temporary_issuance)

        target = load_execution_target(temporary_issuance)
        loaded = _load_admission(temporary_admission, target)
        _require(
            loaded.admission_id
            == issuance["issued_admission"]["admission_id"],
            "s4_dell_runner_load_admission_id_mismatch",
        )
        os.replace(temporary_admission, ADMISSION)
        temporary_paths.remove(temporary_admission)
        os.replace(temporary_issuance, ISSUANCE)
        temporary_paths.remove(temporary_issuance)
    finally:
        for path in temporary_paths:
            path.unlink(missing_ok=True)


def main() -> int:
    payload, issuance = render_issuance()
    _write_and_validate(payload, issuance)
    print(json.dumps(issuance, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
