from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Mapping
import uuid


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.llm_gateway import chat_completion  # noqa: E402
from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402
from sec_agent.s2_same_evidence_experiment_runtime import (  # noqa: E402
    SECTION_IDS,
    load_frozen_blind_inputs,
    load_runtime_policy,
)
from sec_agent.s2_same_evidence_layered_evaluation import evaluate_raw_chain  # noqa: E402
from sec_agent.s2_same_evidence_supervision import (  # noqa: E402
    compile_case_scoped_supervision_boundary,
)
from sec_agent.s2_same_evidence_supervisor_runtime import (  # noqa: E402
    CORRECTED_NODE_ENVELOPE_SCHEMA,
    S2SupervisorRuntimeError,
    _capture_provider_call,
    _compile_corrected_node_context,
    _corrected_node_kwargs,
    _validate_and_store_node,
    compile_correction_objectives,
    compile_fixture_supervisor_plan,
    compile_numeric_fact_views,
    compile_supervisor_plan_spec,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


AUTHORITY_REF = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_06d_minimal_natural_"
    "corrected_node_canary_authority_v1_0.json"
)
PROOF_REF = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_06c_correction_contract_"
    "independent_fresh_zero_call_proof_result_v1_0.json"
)
RAW_RUN_ID = "fin013_s2_05_exp_a_dell_f9e9264951d69da5ed86"
RAW_ROOT = ROOT / ".codex_runtime/fin013_s2_05/runs" / RAW_RUN_ID / "raw_model_only"
CANARY_ROOT = ROOT / ".codex_runtime/fin013_s2_06/canaries/DELL_U3_v1"
AUTHORITY_ROOT = CANARY_ROOT / "authorities"
RUN_ROOT = CANARY_ROOT / "runs"
LEDGER = CANARY_ROOT / "shared/admission_ledger.sqlite"
CANARY_SCOPE = "FIN_0_1_3_S2_06D_DELL_U3_NATURAL_CORRECTED_NODE_CANARY_V1"
TARGET_NODE = "specialist:U3"


class CanaryError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CanaryError("s2_06d_json_object_required")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0:
        raise CanaryError("s2_06d_git_failed:" + ":".join(args))
    return result.stdout.strip()


def validate_repository() -> str:
    if _git("status", "--porcelain"):
        raise CanaryError("s2_06d_repository_not_clean")
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{upstream}"):
        raise CanaryError("s2_06d_repository_not_synced")
    return head


def _validate_authority() -> dict[str, Any]:
    authority = _load(AUTHORITY_REF)
    body = {key: value for key, value in authority.items() if key != "decision_digest"}
    if authority.get("decision_digest") != canonical_digest(body):
        raise CanaryError("s2_06d_authority_digest_drift")
    if (
        authority.get("status") != "one_minimal_DELL_U3_natural_canary_authorized"
        or authority.get("authority", {}).get("provider_call_ceiling") != 1
        or authority.get("authority", {}).get("retry_count") != 0
        or authority.get("authority", {}).get("formal_DELL_proof_authorized") is not False
    ):
        raise CanaryError("s2_06d_authority_invalid")
    proof = _load(PROOF_REF)
    binding = authority["proof_binding"]
    if (
        _sha256(PROOF_REF) != binding["sha256"]
        or proof.get("result_digest") != binding["result_digest"]
        or proof.get("acceptance_boundary", {}).get("RC_P36_148_engineering_repair")
        != "independent_fresh_proof_pass"
    ):
        raise CanaryError("s2_06d_proof_binding_drift")
    script_ref = authority["implementation_binding"]["runner_ref"]
    if Path(script_ref).as_posix() != Path(__file__).resolve().relative_to(ROOT).as_posix():
        raise CanaryError("s2_06d_runner_ref_invalid")
    if _sha256(Path(__file__).resolve()) != authority["implementation_binding"]["runner_sha256"]:
        raise CanaryError("s2_06d_runner_binding_drift")
    return authority


def _load_raw_outputs() -> dict[str, Any]:
    captures: list[tuple[int, str, dict[str, Any]]] = []
    for path in sorted((RAW_ROOT / "captures").glob("*.json")):
        row = _load(path)
        captures.append(
            (
                int(row["call_index"]),
                str(row["node_type"]),
                json.loads(str(row["gateway_result"]["content"])),
            )
        )
    captures.sort(key=lambda item: item[0])
    grouped: dict[str, list[dict[str, Any]]] = {}
    for _, node_type, output in captures:
        grouped.setdefault(node_type, []).append(output)
    return {
        "lead": grouped["lead_planning"][0],
        "specialists": grouped["specialist_judgment"],
        "synthesis": grouped["cross_cell_synthesis"][0],
        "writer": grouped["writer"][0],
        "verifier": grouped["verifier"][0],
    }


def build_material() -> dict[str, Any]:
    _validate_authority()
    policy = load_runtime_policy(ROOT)
    case_input = next(
        row for row in load_frozen_blind_inputs(ROOT, policy)["cases"]
        if row["case_key"] == "DELL"
    )
    raw_terminal = _load(RAW_ROOT / "layered_terminal_result.json")
    raw_outputs = _load_raw_outputs()
    evaluation = evaluate_raw_chain(
        raw_outputs, case_input=case_input, policy=policy, section_ids=SECTION_IDS,
    )
    boundary = compile_case_scoped_supervision_boundary(
        evaluation,
        case_key="DELL",
        raw_run_id=RAW_RUN_ID,
        raw_terminal_digest=raw_terminal["terminal_result_digest"],
    )
    spec = compile_supervisor_plan_spec(
        boundary=boundary, case_input=case_input, raw_outputs=raw_outputs,
    )
    plan = compile_fixture_supervisor_plan(spec)
    directive = next(
        row for row in plan["node_directives"] if row["node_ref"] == TARGET_NODE
    )
    objectives = compile_correction_objectives(spec)
    if directive["correction_ids"] != ["DELL-CORR-023"]:
        raise CanaryError("s2_06d_target_correction_drift")
    return {
        "policy": policy,
        "case_input": case_input,
        "raw_outputs": raw_outputs,
        "boundary": boundary,
        "spec": spec,
        "directive": directive,
        "correction_objectives": objectives,
        "numeric_fact_views": compile_numeric_fact_views(case_input),
        "raw_outputs_digest": canonical_digest(raw_outputs),
        "boundary_digest": canonical_digest(boundary),
    }


def compile_admission(*, head: str, material: Mapping[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    nonce = uuid.uuid4().hex[:16]
    body = {
        "schema_version": "fin_ia_0_1_3_s2_06d_minimal_natural_canary_admission_v1_0",
        "admission_id": "fin013-s2-06d-dell-u3-" + nonce,
        "scope": CANARY_SCOPE,
        "case_key": "DELL",
        "node_ref": TARGET_NODE,
        "correction_ids": ["DELL-CORR-023"],
        "run_id": "fin013_s2_06d_dell_u3_canary_" + nonce,
        "attempt_id": "fin013_s2_06d_dell_u3_canary_" + nonce + "_attempt_1",
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
        "execution_git_commit": head,
        "authority_decision_digest": _validate_authority()["decision_digest"],
        "raw_outputs_digest": material["raw_outputs_digest"],
        "boundary_digest": material["boundary_digest"],
        "corrected_node_envelope_schema": CORRECTED_NODE_ENVELOPE_SCHEMA,
        "provider_call_ceiling": 1,
        "retry_count": 0,
        "fallback_count": 0,
        "formal_DELL_proof_authorized": False,
    }
    return {**body, "admission_digest": canonical_digest(body)}


def validate_admission(
    admission: Mapping[str, Any], *, head: str, material: Mapping[str, Any]
) -> None:
    body = {key: value for key, value in admission.items() if key != "admission_digest"}
    if canonical_digest(body) != admission.get("admission_digest"):
        raise CanaryError("s2_06d_admission_digest_invalid")
    expected = {
        "scope": CANARY_SCOPE,
        "case_key": "DELL",
        "node_ref": TARGET_NODE,
        "correction_ids": ["DELL-CORR-023"],
        "execution_git_commit": head,
        "raw_outputs_digest": material["raw_outputs_digest"],
        "boundary_digest": material["boundary_digest"],
        "provider_call_ceiling": 1,
        "retry_count": 0,
        "fallback_count": 0,
        "formal_DELL_proof_authorized": False,
    }
    if any(admission.get(key) != value for key, value in expected.items()):
        raise CanaryError("s2_06d_admission_binding_invalid")
    expires = datetime.fromisoformat(str(admission["expires_at"]).replace("Z", "+00:00"))
    if datetime.now(timezone.utc) >= expires:
        raise CanaryError("s2_06d_admission_expired")


def execute_canary(
    *, admission: Mapping[str, Any], material: Mapping[str, Any],
    provider_call: Callable[..., Mapping[str, Any]], runtime_root: Path,
    ledger_path: Path, observed_at: str,
) -> dict[str, Any]:
    if runtime_root.exists():
        raise CanaryError("s2_06d_runtime_root_exists")
    captures = runtime_root / "canary/captures"
    captures.mkdir(parents=True)
    ledger = SharedAdmissionConsumptionLedger(ledger_path)
    ledger.reserve(
        admission_digest=str(admission["admission_digest"]),
        admission_id=str(admission["admission_id"]), scope=CANARY_SCOPE,
        run_id=str(admission["run_id"]), attempt_id=str(admission["attempt_id"]),
        runtime_identity="s2_06d_minimal_natural_corrected_node_canary_v1",
        reserved_at=observed_at,
    )
    outputs = deepcopy(material["raw_outputs"])
    node_type, node_id, context = _compile_corrected_node_context(
        node_ref=TARGET_NODE, outputs=outputs, raw_outputs=material["raw_outputs"],
        case_input=material["case_input"], directive=material["directive"],
        correction_objectives=material["correction_objectives"],
        numeric_fact_views=material["numeric_fact_views"],
    )
    receipts: list[dict[str, Any]] = []
    status = "terminal_completed"
    code = "s2_06d_canary_pass"
    try:
        kwargs = _corrected_node_kwargs(
            node_type=node_type, node_id=node_id, context=context,
            case_input=material["case_input"], policy=material["policy"],
            corrected_run_id=str(admission["run_id"]),
        )
        _, parsed = _capture_provider_call(
            kwargs=kwargs, provider_call=provider_call, captures_dir=captures,
            capture_track="corrected_candidate", case_key="DELL",
            node_type=node_type, node_id=node_id, call_index=1,
        )
        _validate_and_store_node(
            node_ref=TARGET_NODE, parsed=parsed, outputs=outputs,
            case_input=material["case_input"], policy=material["policy"],
            correction_contract=context, closure_receipts=receipts,
        )
    except Exception as exc:
        status = "terminal_failed_no_retry"
        code = getattr(exc, "code", str(exc))
    capture_files = sorted(captures.glob("*.json"))
    terminal_body = {
        "schema_version": "fin_ia_0_1_3_s2_06d_minimal_natural_canary_terminal_v1_0",
        "status": status,
        "terminal_phase": TARGET_NODE,
        "terminal_code": code,
        "case_key": "DELL",
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "admission_digest": admission["admission_digest"],
        "provider_calls": len(capture_files),
        "captures": [str(path.relative_to(runtime_root)).replace("\\", "/") for path in capture_files],
        "correction_closure_receipts": receipts,
        "retry_count": 0,
        "fallback_count": 0,
        "formal_DELL_proof_executed": False,
        "corrected_candidate_frozen": False,
        "observed_at": observed_at,
    }
    terminal = {**terminal_body, "terminal_result_digest": canonical_digest(terminal_body)}
    (runtime_root / "terminal_result.json").write_text(
        json.dumps(terminal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]), attempt_id=str(admission["attempt_id"]),
        terminal_status=status, terminal_phase=TARGET_NODE, terminal_code=code,
        terminal_result_digest=terminal["terminal_result_digest"],
        finalized_at=observed_at,
    )
    return terminal


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--issue", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--admission", type=Path)
    args = parser.parse_args()
    head = validate_repository()
    material = build_material()
    credential_env = str(material["policy"]["provider"]["api_key_env"])
    if not os.environ.get(credential_env, "").strip():
        raise CanaryError("s2_06d_credential_absent")
    if args.preflight:
        print(json.dumps({
            "status": "preflight_pass", "execution_git_commit": head,
            "case_key": "DELL", "node_ref": TARGET_NODE,
            "correction_ids": ["DELL-CORR-023"], "provider_call_ceiling": 1,
            "retry_count": 0, "credential_present": True,
            "credential_value_read_or_persisted": False,
            "formal_DELL_proof_authorized": False,
        }, indent=2, sort_keys=True))
        return 0
    if args.issue:
        admission = compile_admission(head=head, material=material)
        AUTHORITY_ROOT.mkdir(parents=True, exist_ok=True)
        path = AUTHORITY_ROOT / (str(admission["admission_id"]) + ".json")
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(admission, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": "admission_issued", "admission_path": str(path), **admission}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.admission is None:
        parser.error("--execute requires --admission")
    admission = _load(args.admission.resolve())
    validate_admission(admission, head=head, material=material)
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    terminal = execute_canary(
        admission=admission, material=material, provider_call=chat_completion,
        runtime_root=RUN_ROOT / str(admission["run_id"]), ledger_path=LEDGER,
        observed_at=observed_at,
    )
    print(json.dumps(terminal, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if terminal["status"] == "terminal_completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
