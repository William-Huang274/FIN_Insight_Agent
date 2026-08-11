from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402
from sec_agent.s2_same_evidence_experiment_runtime import (  # noqa: E402
    POLICY_REF,
    SECTION_IDS,
    load_frozen_blind_inputs,
    load_runtime_policy,
)
from sec_agent.s2_same_evidence_layered_evaluation import evaluate_raw_chain  # noqa: E402
from sec_agent.s2_same_evidence_supervision import (  # noqa: E402
    compile_case_scoped_supervision_boundary,
)
from sec_agent.s2_same_evidence_supervisor_runtime import (  # noqa: E402
    compile_capacity_proof,
    compile_corrected_admission_candidate,
    compile_fixture_supervisor_plan,
    compile_supervisor_plan_spec,
    compile_supervisor_request,
    validate_supervisor_plan,
)


AUTHORITY_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s2_06_three_case_supervisor_"
    "admission_authority_decision_v1_0.json"
)
SUPPORT_REF = (
    "scripts/releases/"
    "fin_ia_0_1_3_s2_06_supervisor_execution_support.py"
)
ISSUER_REF = (
    "scripts/releases/"
    "issue_fin_ia_0_1_3_s2_06_dell_supervisor_admission.py"
)
RUNNER_REF = (
    "scripts/releases/"
    "run_fin_ia_0_1_3_s2_06_supervisor.py"
)
IMPLEMENTATION_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s2_06_three_case_unified_"
    "supervisor_zero_call_implementation_v1_0.json"
)
CASE_RUNS = {
    "DELL": "fin013_s2_05_exp_a_dell_f9e9264951d69da5ed86",
    "MU": "fin013_s2_05_exp_a_mu_d94afa12295f83b18870",
    "NVDA": "fin013_s2_05_exp_a_nvda_04b01685650a1af46f43",
}
RAW_RUN_ROOT = ROOT / ".codex_runtime" / "fin013_s2_05" / "runs"
SUPERVISOR_ROOT = ROOT / ".codex_runtime" / "fin013_s2_06"
SHARED_LEDGER = SUPERVISOR_ROOT / "shared" / "supervisor_admission_ledger.sqlite"


class SupervisorExecutionSupportError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SupervisorExecutionSupportError("s2_06_json_object_required")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise SupervisorExecutionSupportError(
            "s2_06_git_command_failed:" + ":".join(args)
        )
    return completed.stdout.strip()


def validate_repository() -> str:
    if git("status", "--porcelain"):
        raise SupervisorExecutionSupportError("s2_06_repository_not_clean")
    head = git("rev-parse", "HEAD")
    upstream = git("rev-parse", "@{upstream}")
    if head != upstream:
        raise SupervisorExecutionSupportError("s2_06_repository_not_synced")
    authority = validate_authority_and_bindings()
    baseline = str(authority["evidence_binding"]["evaluated_baseline_git_commit"])
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", baseline, head],
        cwd=ROOT,
        check=False,
    )
    if ancestor.returncode != 0:
        raise SupervisorExecutionSupportError("s2_06_head_not_authority_descendant")
    return head


def validate_authority_and_bindings() -> dict[str, Any]:
    authority = load_json(ROOT / AUTHORITY_REF)
    body = {key: value for key, value in authority.items() if key != "decision_digest"}
    auth = authority.get("authority") or {}
    campaign = authority.get("campaign_contract") or {}
    if (
        authority.get("decision_digest") != canonical_digest(body)
        or authority.get("status")
        != "authority_pass_bounded_sequential_campaign_approved_admissions_unissued_execution_not_started"
        or auth.get("decision_outcome")
        != "approve_bounded_sequential_three_case_campaign"
        or auth.get("case_admission_issuance_eligible_after_clean_synced_preflight")
        is not True
        or auth.get("automatic_execution_from_this_decision") is not False
        or campaign.get("case_order") != ["DELL", "MU", "NVDA"]
        or campaign.get("retry_count") != 0
        or campaign.get("fallback_count") != 0
        or campaign.get("hard_provider_call_ceiling")
        != {"per_case": 11, "campaign": 33}
    ):
        raise SupervisorExecutionSupportError("s2_06_authority_invalid")

    evidence = authority.get("evidence_binding") or {}
    for name in ("predecessor_authority", "shared_implementation", "independent_fresh_proof"):
        binding = evidence.get(name) or {}
        ref = str(binding.get("ref") or "")
        expected = str(binding.get("sha256") or "")
        if not ref or not expected or sha256(ROOT / ref) != expected:
            raise SupervisorExecutionSupportError(
                "s2_06_authority_evidence_binding_drift:" + name
            )

    implementation = load_json(ROOT / IMPLEMENTATION_REF)
    implementation_body = {
        key: value
        for key, value in implementation.items()
        if key != "implementation_digest"
    }
    if implementation.get("implementation_digest") != canonical_digest(
        implementation_body
    ):
        raise SupervisorExecutionSupportError("s2_06_implementation_digest_drift")
    for binding in implementation["implementation"].values():
        ref = str(binding["ref"])
        if sha256(ROOT / ref) != str(binding["sha256"]):
            raise SupervisorExecutionSupportError(
                "s2_06_implementation_file_drift:" + ref
            )
    return authority


def load_case_material(case_key: str) -> dict[str, Any]:
    if case_key not in CASE_RUNS:
        raise SupervisorExecutionSupportError("s2_06_case_not_allowed")
    authority = validate_authority_and_bindings()
    policy = load_runtime_policy(ROOT)
    blind = load_frozen_blind_inputs(ROOT, policy)
    case_input = next(
        row for row in blind["cases"] if str(row.get("case_key")) == case_key
    )
    raw_run_id = CASE_RUNS[case_key]
    raw_root = RAW_RUN_ROOT / raw_run_id / "raw_model_only"
    terminal = load_json(raw_root / "layered_terminal_result.json")
    if (
        terminal.get("run_id") != raw_run_id
        or terminal.get("case_key") != case_key
        or terminal.get("status") != "terminal_completed_layered_raw_evaluation"
    ):
        raise SupervisorExecutionSupportError("s2_06_raw_terminal_invalid")
    raw_outputs = load_raw_outputs(raw_root / "captures")
    evaluation = evaluate_raw_chain(
        raw_outputs,
        case_input=case_input,
        policy=policy,
        section_ids=SECTION_IDS,
    )
    boundary = compile_case_scoped_supervision_boundary(
        evaluation,
        case_key=case_key,
        raw_run_id=raw_run_id,
        raw_terminal_digest=str(terminal["terminal_result_digest"]),
    )
    spec = compile_supervisor_plan_spec(
        boundary=boundary,
        case_input=case_input,
        raw_outputs=raw_outputs,
    )
    fixture_plan = compile_fixture_supervisor_plan(spec)
    validate_supervisor_plan(fixture_plan, spec)
    capacity = compile_capacity_proof(
        plan=fixture_plan,
        spec=spec,
        raw_outputs=raw_outputs,
    )
    request = compile_supervisor_request(
        spec=spec,
        raw_outputs=raw_outputs,
        policy=policy,
        corrected_run_id="preflight-" + case_key.lower(),
    )
    expected = authority["case_capacity"][case_key]
    observed = {
        "findings": int(evaluation["finding_count"]),
        "corrections": len(boundary["corrections"]),
        "node_directives": len(fixture_plan["node_directives"]),
        "supervisor_request_characters": len(request["messages"][1]["content"]),
        "corrected_graph_calls": int(capacity["corrected_graph_calls"]),
        "provider_calls": int(capacity["provider_calls"]),
        "pass": bool(capacity["pass"]),
    }
    if observed != expected:
        raise SupervisorExecutionSupportError("s2_06_case_capacity_binding_drift")
    return {
        "authority": authority,
        "policy": policy,
        "case_input": case_input,
        "raw_terminal": terminal,
        "raw_outputs": raw_outputs,
        "evaluation": evaluation,
        "boundary": boundary,
        "spec": spec,
        "capacity": capacity,
        "observed_capacity": observed,
        "raw_outputs_digest": canonical_digest(raw_outputs),
        "evaluation_digest": canonical_digest(evaluation),
        "boundary_digest": canonical_digest(boundary),
        "policy_sha256": sha256(ROOT / POLICY_REF),
    }


def compile_governed_admission(
    *,
    material: Mapping[str, Any],
    corrected_run_id: str,
    corrected_attempt_id: str,
    admission_id: str,
    issued_at: str,
    expires_at: str,
    credential_present: bool,
    execution_git_commit: str,
) -> dict[str, Any]:
    admission = compile_corrected_admission_candidate(
        spec=material["spec"],
        raw_outputs=material["raw_outputs"],
        corrected_run_id=corrected_run_id,
        corrected_attempt_id=corrected_attempt_id,
        admission_id=admission_id,
        issued_at=issued_at,
        expires_at=expires_at,
        credential_present=credential_present,
        provider_execution_authorized=True,
    )
    body = {
        key: deepcopy(value)
        for key, value in admission.items()
        if key != "admission_digest"
    }
    body["governance_binding"] = expected_governance_binding(
        material=material,
        execution_git_commit=execution_git_commit,
    )
    return {**body, "admission_digest": canonical_digest(body)}


def expected_governance_binding(
    *, material: Mapping[str, Any], execution_git_commit: str
) -> dict[str, Any]:
    authority = material["authority"]
    implementation = load_json(ROOT / IMPLEMENTATION_REF)
    return {
        "authority_ref": AUTHORITY_REF,
        "authority_decision_digest": authority["decision_digest"],
        "implementation_digest": implementation["implementation_digest"],
        "execution_git_commit": execution_git_commit,
        "policy_ref": POLICY_REF,
        "policy_sha256": material["policy_sha256"],
        "execution_entrypoint_bindings": {
            SUPPORT_REF: sha256(ROOT / SUPPORT_REF),
            ISSUER_REF: sha256(ROOT / ISSUER_REF),
            RUNNER_REF: sha256(ROOT / RUNNER_REF),
        },
        "raw_outputs_digest": material["raw_outputs_digest"],
        "evaluation_digest": material["evaluation_digest"],
        "boundary_digest": material["boundary_digest"],
        "case_expected_provider_calls": material["capacity"]["provider_calls"],
        "retry_count": 0,
        "fallback_count": 0,
    }


def validate_admission_governance(
    admission: Mapping[str, Any], *, material: Mapping[str, Any], execution_git_commit: str
) -> None:
    body = {
        key: deepcopy(value)
        for key, value in admission.items()
        if key != "admission_digest"
    }
    if admission.get("admission_digest") != canonical_digest(body):
        raise SupervisorExecutionSupportError("s2_06_admission_digest_invalid")
    if admission.get("governance_binding") != expected_governance_binding(
        material=material,
        execution_git_commit=execution_git_commit,
    ):
        raise SupervisorExecutionSupportError("s2_06_admission_governance_drift")


def load_raw_outputs(capture_root: Path) -> dict[str, Any]:
    captures: list[tuple[int, str, dict[str, Any]]] = []
    for path in sorted(capture_root.glob("*.json")):
        row = load_json(path)
        content = row.get("gateway_result", {}).get("content")
        if not isinstance(content, str):
            raise SupervisorExecutionSupportError(
                "s2_06_raw_capture_content_missing:" + path.name
            )
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise SupervisorExecutionSupportError(
                "s2_06_raw_capture_output_not_object:" + path.name
            )
        captures.append((int(row["call_index"]), str(row["node_type"]), parsed))
    captures.sort(key=lambda row: row[0])
    by_type: dict[str, list[dict[str, Any]]] = {}
    for _, node_type, content in captures:
        by_type.setdefault(node_type, []).append(content)
    for node_type in ("lead_planning", "cross_cell_synthesis", "writer", "verifier"):
        if len(by_type.get(node_type, [])) != 1:
            raise SupervisorExecutionSupportError(
                "s2_06_required_raw_capture_missing:" + node_type
            )
    specialists = by_type.get("specialist_judgment", [])
    if not 6 <= len(specialists) <= 8 or len(captures) != len(specialists) + 4:
        raise SupervisorExecutionSupportError("s2_06_raw_capture_topology_invalid")
    return {
        "lead": by_type["lead_planning"][0],
        "specialists": specialists,
        "synthesis": by_type["cross_cell_synthesis"][0],
        "writer": by_type["writer"][0],
        "verifier": by_type["verifier"][0],
    }
