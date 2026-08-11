from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback
from typing import Any, Mapping

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.app import create_app  # noqa: E402
from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.case_service import (  # noqa: E402
    CasePrincipal,
    CaseService,
)
from apps.workbench.backend.application.evidence_service import (  # noqa: E402
    EvidenceService,
)
from apps.workbench.backend.application.fin_0_1_2_s3_t03_exact_live_runner import (  # noqa: E402
    claim_supervised_execution_identity,
    execute_bound_s3_t03,
    finalize_supervisor_exit,
    load_bound_s3_t03_execution_envelope,
    business_input_digest,
)
from apps.workbench.backend.application.local_research_service import (  # noqa: E402
    P36LocalResearchService,
)
from apps.workbench.backend.application.research_runtime import (  # noqa: E402
    S3ThreeCellPreparedExecution,
    prepare_s3_three_cell_bounded_agent_exact_input,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


SUPERVISION_CONTRACT_REF = "fin_0_1_2.s3_t03.exact_live_supervision:v1"
ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_fresh_exact_admission_r1.json"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_fresh_exact_"
    "admission_issuance_v1_0.json"
)
EXACT_INPUT_MANIFEST = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_nvda_exact_product_input_v1_0.json"
)
EXPECTED_ADMISSION_SHA256 = (
    "89254b2246ee8cced822edb93f4b5d9a3a4b6adc7f0223f1edade53d188d1720"
)
EXPECTED_ISSUANCE_SHA256 = (
    "41db08cb6fc08ceb6210ceffbaae15c19ea73502b0ff8c895c1d9d2f75b787dd"
)
EXPECTED_ADMISSION_DIGEST = (
    "eed177b1124c8db930193196f71eb653b85a2b24d9c92a192251984def4fd1c8"
)
TENANT_ID = "tenant-fin01-s3-t09-preflight"
PROJECT_ID = "project-fin01-s3-t09-preflight"
ACTOR_ID = "analyst-fin01-s3-t09-preflight"
PERMISSIONS = frozenset(
    {
        "case:create",
        "case:read",
        "planning:write",
        "planning:review",
        "planning:read",
        "execution:write",
        "execution:read",
        "activity:read",
        "evidence:read",
    }
)


class Fin012S3T03SupervisedLiveError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExecutionTarget:
    admission_id: str
    admission_digest: str
    admission_ref: str
    runtime_root_ref: str
    execution_identity: str
    case_id: str
    case_version: int
    as_of: str
    decision_surface_contract_ref: str
    input_head_digest: str
    stable_business_input_digest: str
    complete_input_digest: str
    preparation_digest: str
    work_unit_id: str
    attempt_id: str
    research_run_id: str
    maximum_input_tokens: int
    maximum_output_tokens: int
    maximum_total_cost_usd: float
    maximum_wall_clock_seconds: int


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(_canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Fin012S3T03SupervisedLiveError("s3_t03_json_object_required")
    return value


def load_target() -> ExecutionTarget:
    if _sha256(ADMISSION) != EXPECTED_ADMISSION_SHA256:
        raise Fin012S3T03SupervisedLiveError("s3_t03_admission_file_drift")
    if _sha256(ISSUANCE) != EXPECTED_ISSUANCE_SHA256:
        raise Fin012S3T03SupervisedLiveError("s3_t03_issuance_file_drift")
    issuance = _load_json(ISSUANCE)
    manifest = _load_json(EXACT_INPUT_MANIFEST)
    issued = issuance.get("issued_admission") or {}
    binding = issuance.get("exact_binding") or {}
    budget = issuance.get("execution_envelope") or {}
    if issuance.get("status") != "issued_unconsumed_zero_call_preflight_pass":
        raise Fin012S3T03SupervisedLiveError("s3_t03_issuance_not_eligible")
    if issued.get("consumed") is not False or issued.get("execution_started") is not False:
        raise Fin012S3T03SupervisedLiveError("s3_t03_admission_already_consumed")
    return ExecutionTarget(
        admission_id=str(issued["admission_id"]),
        admission_digest=str(issued["admission_digest"]),
        admission_ref=str(issued["admission_ref"]),
        runtime_root_ref=str(issued["runtime_root"]),
        execution_identity=str(issued["execution_identity"]),
        case_id=str(binding["case_id"]),
        case_version=int(binding["case_version"]),
        as_of=str(binding["as_of"]),
        decision_surface_contract_ref=str(
            manifest["case"]["decision_surface_contract_ref"]
        ),
        input_head_digest=str(binding["input_head_digest"]),
        stable_business_input_digest=str(binding["stable_business_input_digest"]),
        complete_input_digest=str(binding["complete_input_digest"]),
        preparation_digest=str(binding["preparation_digest"]),
        work_unit_id=str(binding["predicted_work_unit_id"]),
        attempt_id=str(binding["predicted_attempt_id"]),
        research_run_id=str(binding["predicted_research_run_id"]),
        maximum_input_tokens=int(budget["maximum_input_tokens"]),
        maximum_output_tokens=int(budget["maximum_output_tokens_total"]),
        maximum_total_cost_usd=float(budget["maximum_total_cost_usd"]),
        maximum_wall_clock_seconds=int(budget["maximum_wall_clock_seconds"]),
    )


def load_admission(target: ExecutionTarget) -> S3ThreeCellBoundedAgentAdmission:
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(_load_json(ADMISSION))
    admission.assert_profile_admissible()
    if (
        admission.admission_id != target.admission_id
        or canonical_digest(admission.digest_payload()) != target.admission_digest
        or target.admission_digest != EXPECTED_ADMISSION_DIGEST
        or admission.input_digest != target.complete_input_digest
        or admission.max_provider_calls != 9
        or admission.max_semantic_model_calls != 9
        or admission.max_network_calls != 9
        or admission.max_transport_attempts_per_call != 1
        or admission.retry_budget != 0
        or admission.max_total_cost_usd != 0.06
    ):
        raise Fin012S3T03SupervisedLiveError("s3_t03_admission_binding_mismatch")
    return admission


def _headers() -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": ",".join(sorted(PERMISSIONS)),
    }


def _principal() -> CasePrincipal:
    return CasePrincipal(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        actor_id=ACTOR_ID,
        permissions=PERMISSIONS,
    )


def prepare_exact_input(
    preparation_root: Path,
    target: ExecutionTarget,
    admission: S3ThreeCellBoundedAgentAdmission,
) -> S3ThreeCellPreparedExecution:
    """Rehydrate the frozen internal NVDA dogfood input without test imports."""

    local_service, evidence_service, case, accepted = rehydrate_exact_input_services(
        preparation_root
    )
    prepared = prepare_s3_three_cell_bounded_agent_exact_input(
        local_service,
        evidence_service,
        str(case["case_id"]),
        _principal(),
        decision_surface_contract_ref=str(accepted["contract_version_id"]),
        execution_identity=target.execution_identity,
    )
    observed = {
        "case_id": prepared.case_id,
        "case_version": prepared.case_version,
        "as_of": prepared.input_pack.as_of,
        "decision_surface_contract_ref": prepared.decision_surface_contract_ref,
        "input_head_digest": prepared.input_pack.input_head_digest,
        "stable_business_input_digest": business_input_digest(prepared.input_pack),
        "complete_input_digest": prepared.input_digest,
        "preparation_digest": prepared.preparation_digest,
        "work_unit_id": prepared.work_unit_id,
        "attempt_id": prepared.attempt_id,
        "research_run_id": prepared.research_run_id,
    }
    expected = {
        "case_id": target.case_id,
        "case_version": target.case_version,
        "as_of": target.as_of,
        "decision_surface_contract_ref": target.decision_surface_contract_ref,
        "input_head_digest": target.input_head_digest,
        "stable_business_input_digest": target.stable_business_input_digest,
        "complete_input_digest": target.complete_input_digest,
        "preparation_digest": target.preparation_digest,
        "work_unit_id": target.work_unit_id,
        "attempt_id": target.attempt_id,
        "research_run_id": target.research_run_id,
    }
    if observed != expected or admission.input_digest != prepared.input_digest:
        raise Fin012S3T03SupervisedLiveError("s3_t03_exact_input_rehydrate_drift")
    return prepared


def rehydrate_exact_input_services(
    preparation_root: Path,
) -> tuple[P36LocalResearchService, EvidenceService, Mapping[str, Any], Mapping[str, Any]]:
    """Build the frozen NVDA case once for prospective or issued identities."""

    case_service = CaseService.for_fixture_root(
        preparation_root / "canonical-runtime", repo_root=ROOT
    )
    local_service = P36LocalResearchService.from_case_service(
        case_service, repo_root=ROOT
    )
    evidence_service = EvidenceService.from_case_service(
        case_service, repo_root=ROOT
    )
    app = create_app(
        preparation_root / "setup-workbench.sqlite",
        p02_case_service=case_service,
        p03_evidence_service=evidence_service,
        p36_local_research_service=local_service,
    )
    with TestClient(app) as client:
        created_response = client.post(
            "/api/v1/cases",
            headers=_headers(),
            json={
                "query": (
                    "Execute the FIN 0.1 NVDA S3 T09 exact three-cell "
                    "preflight fixture"
                ),
                "as_of": "2026-07-21T00:00:00Z",
                "language": "en",
                "source_policy_ref": "fixture:internal-only",
                "idempotency_key": "t09-preflight-case",
            },
        )
        if created_response.status_code != 202:
            raise Fin012S3T03SupervisedLiveError(
                f"s3_t03_case_rehydrate_failed:{created_response.status_code}"
            )
        case = created_response.json()
        compiled_response = client.post(
            f"/api/v1/cases/{case['case_id']}/planning/compile",
            headers=_headers(),
            json={
                "expected_case_version": case["case_version"],
                "expected_summary_version": case["summary_version"],
                "compiler_policy_ref": "fixture:p36-three-cell-v1",
                "pack_selection_ref": "fixture:p36-ai-infrastructure-v1",
                "actor_ref": ACTOR_ID,
                "idempotency_key": "t09-preflight-compile",
            },
        )
        if compiled_response.status_code != 202:
            raise Fin012S3T03SupervisedLiveError(
                f"s3_t03_plan_rehydrate_failed:{compiled_response.status_code}"
            )
        compiled = compiled_response.json()
        accepted_response = client.post(
            f"/api/v1/cases/{case['case_id']}/planning/checkpoint",
            headers=_headers(),
            json={
                "decision": "accept",
                "expected_case_version": case["case_version"],
                "expected_decision_surface_contract_version": compiled[
                    "contract_version"
                ],
                "expected_checkpoint_version": compiled["checkpoint_version"],
                "actor_ref": ACTOR_ID,
                "idempotency_key": "t09-preflight-accept",
            },
        )
        if accepted_response.status_code != 202:
            raise Fin012S3T03SupervisedLiveError(
                f"s3_t03_checkpoint_rehydrate_failed:{accepted_response.status_code}"
            )
        accepted = accepted_response.json()
    return local_service, evidence_service, case, accepted


def _default_completion(**kwargs: Any) -> Mapping[str, Any]:
    from sec_agent.llm_gateway import chat_completion

    payload = dict(kwargs)
    payload["max_transport_attempts"] = 1
    return chat_completion(**payload)


def _wait_for_launch_receipt(supervision_root: Path) -> dict[str, Any]:
    expected_root = str(
        os.environ.get("FIN_IA_0_1_2_S3_T03_SUPERVISION_ROOT") or ""
    ).strip()
    contract = str(
        os.environ.get("FIN_IA_0_1_2_S3_T03_SUPERVISION_CONTRACT_REF") or ""
    ).strip()
    if Path(expected_root).resolve() != supervision_root.resolve():
        raise Fin012S3T03SupervisedLiveError("s3_t03_supervision_root_mismatch")
    if contract != SUPERVISION_CONTRACT_REF:
        raise Fin012S3T03SupervisedLiveError("s3_t03_supervision_contract_mismatch")
    path = supervision_root / "launch-receipt.json"
    deadline = time.monotonic() + 5
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not path.exists():
        raise Fin012S3T03SupervisedLiveError("s3_t03_launch_receipt_missing")
    receipt = _load_json(path)
    if (
        receipt.get("contract_ref") != SUPERVISION_CONTRACT_REF
        or int(receipt.get("child_pid") or 0) != os.getpid()
        or receipt.get("automatic_retry_count") != 0
        or receipt.get("fallback_count") != 0
        or receipt.get("relaunch_count") != 0
    ):
        raise Fin012S3T03SupervisedLiveError("s3_t03_launch_receipt_invalid")
    return receipt


def child_preflight(supervision_root: Path) -> dict[str, Any]:
    _wait_for_launch_receipt(supervision_root)
    target = load_target()
    admission = load_admission(target)
    envelope = load_bound_s3_t03_execution_envelope(ROOT)
    if not os.environ.get(admission.api_key_env):
        raise Fin012S3T03SupervisedLiveError("s3_t03_provider_credential_missing")
    if os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") != "0":
        raise Fin012S3T03SupervisedLiveError("s3_t03_transport_retries_not_zero")
    with tempfile.TemporaryDirectory(
        prefix="fin012-s3-t03-preparation-", dir=supervision_root
    ) as temporary:
        prepared = prepare_exact_input(Path(temporary), target, admission)
    provider_calls = 0

    def _forbidden_provider(**_: Any) -> Mapping[str, Any]:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("s3_t03_preflight_provider_call_forbidden")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=_forbidden_provider
    )
    if provider_calls != 0 or not callable(_default_completion):
        raise Fin012S3T03SupervisedLiveError("s3_t03_preflight_wiring_invalid")
    result = {
        "schema_version": "fin_ia_0_1_2_s3_t03_child_zero_call_preflight_v1_0",
        "status": "pass_child_exact_input_transport_wiring_zero_call",
        "admission_digest": target.admission_digest,
        "envelope_digest": envelope["envelope_digest"],
        "execution_identity": prepared.execution_identity,
        "complete_input_digest": prepared.input_digest,
        "stable_business_input_digest": business_input_digest(prepared.input_pack),
        "credential_present": True,
        "credential_value_read_output_or_persisted": False,
        "provider_health_probe_performed": False,
        "transport_retries": 0,
        "provider_callback_calls": provider_calls,
        "model_provider_network_calls": [0, 0, 0],
    }
    _atomic_write_json(supervision_root / "child-preflight-result.json", result)
    return result


def child_execute(runtime_root: Path, supervision_root: Path) -> dict[str, Any]:
    _wait_for_launch_receipt(supervision_root)
    target = load_target()
    admission = load_admission(target)
    envelope = load_bound_s3_t03_execution_envelope(ROOT)
    if not os.environ.get(admission.api_key_env):
        raise Fin012S3T03SupervisedLiveError("s3_t03_provider_credential_missing")
    if os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") != "0":
        raise Fin012S3T03SupervisedLiveError("s3_t03_transport_retries_not_zero")
    with tempfile.TemporaryDirectory(
        prefix="fin012-s3-t03-preparation-", dir=supervision_root
    ) as temporary:
        prepared = prepare_exact_input(Path(temporary), target, admission)
        result = execute_bound_s3_t03(
            runtime_root=runtime_root,
            prepared=prepared,
            admission=admission,
            execution_envelope=envelope,
            completion=_default_completion,
        )
    return result


def _child_command(mode: str, runtime_root: Path, supervision_root: Path) -> list[str]:
    entrypoint = Path(
        os.environ.get("FIN_IA_0_1_2_S3_T03_SUPERVISOR_ENTRYPOINT")
        or Path(__file__).resolve()
    ).resolve()
    return [
        sys.executable,
        str(entrypoint),
        mode,
        "--runtime-root",
        str(runtime_root.resolve()),
        "--supervision-root",
        str(supervision_root.resolve()),
    ]


def _write_launch_receipt(
    supervision_root: Path,
    *,
    command: list[str],
    child_pid: int,
    timeout_seconds: int,
    mode: str,
) -> dict[str, Any]:
    command_projection = [
        "<python>" if index == 0 else Path(value).name if index == 1 else value
        for index, value in enumerate(command)
    ]
    receipt = {
        "schema_version": "fin_ia_0_1_2_s3_t03_supervised_launch_receipt_v1_0",
        "contract_ref": SUPERVISION_CONTRACT_REF,
        "mode": mode,
        "process_topology": "parent_direct_child_entrypoint",
        "child_pid": child_pid,
        "command_projection": command_projection,
        "command_digest": canonical_digest(command_projection),
        "parent_enforced_timeout_seconds": timeout_seconds,
        "parent_may_terminate_child_on_timeout": True,
        "automatic_retry_count": 0,
        "fallback_count": 0,
        "replay_count": 0,
        "relaunch_count": 0,
        "credential_value_persisted": False,
    }
    _atomic_write_json(supervision_root / "launch-receipt.json", receipt)
    return receipt


def _log_receipt(path: Path) -> dict[str, Any]:
    data = path.read_bytes() if path.exists() else b""
    return {
        "ref": path.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def _run_child(
    *,
    command: list[str],
    runtime_root: Path,
    supervision_root: Path,
    timeout_seconds: int,
    mode: str,
    finalize_missing_terminal: bool,
) -> dict[str, Any]:
    supervision_root.mkdir(parents=True, exist_ok=False)
    stdout_path = supervision_root / "child.stdout.log"
    stderr_path = supervision_root / "child.stderr.log"
    child_environment = os.environ.copy()
    child_environment["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), str(ROOT / "src"), child_environment.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    child_environment["LLM_GATEWAY_TRANSPORT_RETRIES"] = "0"
    child_environment["FIN_IA_0_1_2_S3_T03_SUPERVISION_ROOT"] = str(
        supervision_root.resolve()
    )
    child_environment["FIN_IA_0_1_2_S3_T03_SUPERVISION_CONTRACT_REF"] = (
        SUPERVISION_CONTRACT_REF
    )
    started = time.monotonic()
    timed_out = False
    process: subprocess.Popen[bytes] | None = None
    launch: dict[str, Any] | None = None
    launch_error: BaseException | None = None
    exit_code: int | None = None
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        try:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=child_environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
            )
            launch = _write_launch_receipt(
                supervision_root,
                command=command,
                child_pid=process.pid,
                timeout_seconds=timeout_seconds,
                mode=mode,
            )
            try:
                exit_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                exit_code = process.wait(timeout=30)
        except BaseException as exc:
            launch_error = exc
            if process is not None and process.poll() is None:
                process.kill()
                exit_code = process.wait(timeout=30)
            elif process is not None:
                exit_code = process.returncode
            _atomic_write_json(
                supervision_root / "launch-failure-receipt.json",
                {
                    "schema_version": (
                        "fin_ia_0_1_2_s3_t03_supervised_launch_failure_"
                        "receipt_v1_0"
                    ),
                    "contract_ref": SUPERVISION_CONTRACT_REF,
                    "mode": mode,
                    "child_pid": process.pid if process is not None else None,
                    "failure_type": type(exc).__name__,
                    "child_terminated_if_started": process is not None,
                    "automatic_retry_count": 0,
                    "fallback_count": 0,
                    "replay_count": 0,
                    "relaunch_count": 0,
                    "credential_value_persisted": False,
                },
            )
    result_path = runtime_root / "execution-result.json"
    if finalize_missing_terminal and not result_path.exists():
        envelope = load_bound_s3_t03_execution_envelope(ROOT)
        finalize_supervisor_exit(
            runtime_root=runtime_root,
            execution_envelope=envelope,
            exit_code=exit_code,
            reason=(
                "parent_launch_failure"
                if launch_error is not None
                else "parent_timeout"
                if timed_out
                else "child_exit_without_terminal"
            ),
        )
    exit_receipt = {
        "schema_version": "fin_ia_0_1_2_s3_t03_supervised_exit_receipt_v1_0",
        "contract_ref": SUPERVISION_CONTRACT_REF,
        "mode": mode,
        "child_pid": launch["child_pid"] if launch is not None else None,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "launch_failed": launch_error is not None,
        "launch_failure_type": (
            type(launch_error).__name__ if launch_error is not None else None
        ),
        "wall_clock_seconds": round(time.monotonic() - started, 6),
        "terminal_materialized": result_path.exists(),
        "stdout": _log_receipt(stdout_path),
        "stderr": _log_receipt(stderr_path),
        "automatic_retry_count": 0,
        "fallback_count": 0,
        "replay_count": 0,
        "relaunch_count": 0,
        "credential_value_persisted": False,
    }
    if result_path.exists():
        exit_receipt["execution_result"] = {
            "sha256": _sha256(result_path),
            "bytes": result_path.stat().st_size,
        }
    _atomic_write_json(supervision_root / "exit-receipt.json", exit_receipt)
    if launch_error is not None and not finalize_missing_terminal:
        raise Fin012S3T03SupervisedLiveError(
            "s3_t03_child_launch_failed_during_zero_call_preflight"
        ) from launch_error
    return exit_receipt


def run_zero_call_preflight(output_path: Path) -> dict[str, Any]:
    target = load_target()
    admission = load_admission(target)
    target_runtime_root = ROOT / target.runtime_root_ref
    if target_runtime_root.exists():
        raise Fin012S3T03SupervisedLiveError("s3_t03_target_runtime_not_fresh")
    if not os.environ.get(admission.api_key_env):
        raise Fin012S3T03SupervisedLiveError("s3_t03_provider_credential_missing")
    with tempfile.TemporaryDirectory(prefix="fin012-s3-t03-supervision-preflight-") as temp:
        temporary = Path(temp)
        supervision_root = temporary / "supervision"
        disposable_runtime = temporary / "runtime-not-claimed"
        command = _child_command(
            "child-preflight", disposable_runtime, supervision_root
        )
        exit_receipt = _run_child(
            command=command,
            runtime_root=disposable_runtime,
            supervision_root=supervision_root,
            timeout_seconds=120,
            mode="zero_call_preflight",
            finalize_missing_terminal=False,
        )
        child_result = _load_json(supervision_root / "child-preflight-result.json")
        if (
            exit_receipt["exit_code"] != 0
            or exit_receipt["timed_out"]
            or child_result["provider_callback_calls"] != 0
            or disposable_runtime.exists()
        ):
            raise Fin012S3T03SupervisedLiveError("s3_t03_child_preflight_failed")
        result = {
            "schema_version": (
                "fin_ia_0_1_2_s3_t03_bound_launcher_parent_supervisor_"
                "zero_call_preflight_v1_0"
            ),
            "status": "pass_real_child_parent_supervisor_zero_call_preflight",
            "admission_digest": target.admission_digest,
            "execution_identity": target.execution_identity,
            "complete_input_digest": target.complete_input_digest,
            "stable_business_input_digest": target.stable_business_input_digest,
            "child_process_launch_count": 1,
            "child_preflight_result_digest": canonical_digest(child_result),
            "process_topology": "parent_direct_child_entrypoint",
            "parent_timeout_enforced": True,
            "parent_abnormal_exit_terminal_recovery_wired": True,
            "credential_present": True,
            "credential_value_read_output_or_persisted": False,
            "provider_health_probe_performed": False,
            "target_runtime_root_absent_before_and_after": not target_runtime_root.exists(),
            "admission_consumed": False,
            "execution_started": False,
            "transport_retries": 0,
            "maximum_transport_attempts_per_call": 1,
            "budget": {
                "maximum_provider_calls": admission.max_provider_calls,
                "maximum_input_tokens": target.maximum_input_tokens,
                "maximum_output_tokens": target.maximum_output_tokens,
                "maximum_total_cost_usd": target.maximum_total_cost_usd,
                "maximum_wall_clock_seconds": target.maximum_wall_clock_seconds,
            },
            "observed_counts": {
                "model_calls": 0,
                "provider_calls": 0,
                "execution_network_calls": 0,
                "source_network_calls": 0,
                "external_tool_calls": 0,
                "business_runs": 0,
                "business_artifacts": 0,
            },
        }
    _atomic_write_json(output_path.resolve(), result)
    return result


def _load_later_execution_authority(
    authority_path: Path, target: ExecutionTarget
) -> dict[str, Any]:
    authority = _load_json(authority_path)
    permission = authority.get("authority") or {}
    source = authority.get("source_authority") or {}
    execution = authority.get("exact_execution_target") or {}
    if (
        authority.get("status")
        != "authorized_exact_once_execution_not_started"
        or permission.get("future_exact_live_execution_authorized") is not True
        or permission.get("current_turn_admission_consumption_or_execution_authorized")
        is not False
        or source.get("admission_digest") != target.admission_digest
        or execution.get("execution_identity") != target.execution_identity
    ):
        raise Fin012S3T03SupervisedLiveError("s3_t03_later_execution_authority_invalid")
    return authority


def supervise_exact_execution(
    *,
    supervision_root: Path,
    execution_authority: Path,
) -> dict[str, Any]:
    target = load_target()
    admission = load_admission(target)
    _load_later_execution_authority(execution_authority, target)
    runtime_root = (ROOT / target.runtime_root_ref).resolve()
    if runtime_root.exists() or supervision_root.exists():
        raise Fin012S3T03SupervisedLiveError("s3_t03_exact_identity_or_supervision_reuse")
    if not os.environ.get(admission.api_key_env):
        raise Fin012S3T03SupervisedLiveError("s3_t03_provider_credential_missing")
    envelope = load_bound_s3_t03_execution_envelope(ROOT)
    claim_supervised_execution_identity(
        runtime_root,
        envelope,
        supervision_root=supervision_root,
    )
    command = _child_command("child-execute", runtime_root, supervision_root)
    return _run_child(
        command=command,
        runtime_root=runtime_root,
        supervision_root=supervision_root,
        timeout_seconds=target.maximum_wall_clock_seconds,
        mode="exact_live",
        finalize_missing_terminal=True,
    )


def fixture_child(runtime_root: Path, supervision_root: Path, behavior: str) -> int:
    if os.environ.get("FIN_IA_S3_T03_ALLOW_TEST_FIXTURE_CHILD") != "1":
        raise Fin012S3T03SupervisedLiveError("s3_t03_fixture_child_not_allowed")
    _wait_for_launch_receipt(supervision_root)
    if behavior == "exit":
        return 17
    if behavior == "sleep":
        time.sleep(60)
        return 0
    raise Fin012S3T03SupervisedLiveError("s3_t03_fixture_behavior_invalid")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "FIN 0.1.2 S3-T03 NVDA admission-bound child and parent supervisor."
        )
    )
    parser.add_argument(
        "mode",
        choices=(
            "preflight",
            "supervise",
            "inspect",
            "child-preflight",
            "child-execute",
            "fixture-child",
        ),
    )
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--supervision-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--execution-authority", type=Path)
    parser.add_argument("--fixture-behavior", choices=("exit", "sleep"))
    args = parser.parse_args()
    target = load_target()
    runtime_root = args.runtime_root or ROOT / target.runtime_root_ref
    if args.mode == "preflight":
        output = args.output or ROOT / (
            ".codex_runtime/fin012_s3_t03_nvda_launcher_supervisor_preflight.json"
        )
        result = run_zero_call_preflight(output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.mode == "supervise":
        if args.supervision_root is None or args.execution_authority is None:
            raise Fin012S3T03SupervisedLiveError(
                "s3_t03_supervision_root_and_later_authority_required"
            )
        result = supervise_exact_execution(
            supervision_root=args.supervision_root,
            execution_authority=args.execution_authority,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.mode == "inspect":
        result_path = runtime_root / "execution-result.json"
        if not result_path.exists():
            raise Fin012S3T03SupervisedLiveError("s3_t03_execution_result_missing")
        result = _load_json(result_path)
        summary = {
            "status": result.get("status"),
            "terminal_status": (result.get("terminal") or {}).get("status"),
            "capture_count": len(result.get("capture_objects") or []),
            "artifact_count": len(result.get("artifacts") or []),
            "business_promotable": result.get("business_promotable"),
            "result_sha256": _sha256(result_path),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.supervision_root is None:
        raise Fin012S3T03SupervisedLiveError("s3_t03_child_supervision_root_required")
    if args.mode == "child-preflight":
        child_preflight(args.supervision_root)
        return 0
    if args.mode == "child-execute":
        result = child_execute(runtime_root, args.supervision_root)
        return 0 if result.get("status") == "success" else 2
    return fixture_child(
        runtime_root,
        args.supervision_root,
        str(args.fixture_behavior or ""),
    )


def _entrypoint() -> int:
    try:
        return main()
    except BaseException:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(_entrypoint())
