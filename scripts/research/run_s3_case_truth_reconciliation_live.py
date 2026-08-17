from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.providers import (
    ChatCompletionToolStepResult,
    ModelGatewayError,
    execute_chat_completion_tool_step_exact_once,
    load_chat_completion_profile,
    project_deepseek_strict_tool,
)
from sec_agent.research.case_truth_reconciliation import (
    CaseTruthReconciliationError,
    compile_case_truth_packet,
    compile_case_truth_reconciliation_submission,
    compile_cell_judgment_claim_document,
    validate_case_truth_reconciliation,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest


AUTHORITY_SCHEMA_VERSION = (
    "fin_ia_s3_case_truth_reconciliation_live_authority_v1_0"
)
RESULT_SCHEMA_VERSION = "fin_ia_s3_case_truth_reconciliation_live_result_v1_0"
EXPECTED_STATUS = "signed_exact_once_R7_case_truth_semantic_canary"


class CaseTruthLiveError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CaseTruthLiveError("case_truth_live_json_object_required")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: str | Path) -> str:
    return Path(path).resolve().relative_to(ROOT).as_posix()


def _resolve(value: str) -> Path:
    path = (ROOT / value).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise CaseTruthLiveError("case_truth_live_path_escape") from exc
    return path


def _write_new(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError as exc:
        raise CaseTruthLiveError(
            "case_truth_live_exact_once_output_exists"
        ) from exc


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode:
        raise CaseTruthLiveError("case_truth_live_git_unavailable")
    return result.stdout.strip()


def _validate_authority(
    authority: Mapping[str, Any], *, authority_path: Path
) -> tuple[dict[str, Path], Path, Path, Path, str]:
    if not (
        authority.get("schema_version") == AUTHORITY_SCHEMA_VERSION
        and authority.get("status") == EXPECTED_STATUS
        and authority.get("case_key") == "DELL"
    ):
        raise CaseTruthLiveError("case_truth_live_authority_status_invalid")
    clean = authority.get("clean_implementation")
    budget = authority.get("execution_budget")
    bound = authority.get("bound_inputs")
    output = authority.get("output_contract")
    targets = authority.get("pre_registered_targets")
    if not all(
        isinstance(row, Mapping)
        for row in (clean, budget, bound, output, targets)
    ):
        raise CaseTruthLiveError("case_truth_live_authority_shape_invalid")
    assert isinstance(clean, Mapping)
    assert isinstance(budget, Mapping)
    assert isinstance(bound, Mapping)
    assert isinstance(output, Mapping)
    assert isinstance(targets, Mapping)
    commit = str(clean.get("implementation_commit") or "").lower()
    if dict(clean) != {
        "implementation_commit": commit,
        "head_must_equal_implementation_commit": True,
        "upstream_must_equal_implementation_commit": True,
        "tracked_worktree_must_be_clean": True,
        "only_authority_may_be_untracked": True,
    }:
        raise CaseTruthLiveError("case_truth_live_clean_binding_invalid")
    if (
        _git("rev-parse", "HEAD").lower() != commit
        or _git("rev-parse", "@{upstream}").lower() != commit
    ):
        raise CaseTruthLiveError("case_truth_live_repository_binding_drift")
    status = [
        row
        for row in _git(
            "status", "--porcelain=v1", "--untracked-files=all"
        ).splitlines()
        if row
    ]
    if status != [f"?? {_relative(authority_path)}"]:
        raise CaseTruthLiveError("case_truth_live_worktree_not_clean")
    if dict(budget) != {
        "maximum_model_calls": 1,
        "maximum_provider_calls": 1,
        "maximum_transport_attempts": 1,
        "retries": 0,
        "fallbacks": 0,
        "protocol_switches": 0,
        "network_source_calls": 0,
        "embedding_calls": 0,
        "candidate_promotions": 0,
        "research_rewrites": 0,
        "report_generations": 0,
        "product_publication": "forbidden",
    }:
        raise CaseTruthLiveError("case_truth_live_budget_invalid")
    expected_refs = {
        "r7_public_result_ref",
        "r7_private_result_ref",
        "zero_call_result_ref",
        "provider_profile_ref",
    }
    ref_keys = {key for key in bound if str(key).endswith("_ref")}
    expected_keys = {
        value
        for key in expected_refs
        for value in (key, key[:-4] + "_sha256")
    } | {
        "expected_case_truth_packet_digest",
        "expected_claim_document_digest",
    }
    if ref_keys != expected_refs or set(bound) != expected_keys:
        raise CaseTruthLiveError("case_truth_live_bound_inputs_invalid")
    paths: dict[str, Path] = {}
    for key in sorted(expected_refs):
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(bound[key[:-4] + "_sha256"]):
            raise CaseTruthLiveError(f"case_truth_live_bound_input_drift:{key}")
        paths[key] = path
    private_path = _resolve(str(output.get("private_output_ref") or ""))
    public_path = _resolve(str(output.get("public_result_ref") or ""))
    capture_root = _resolve(str(output.get("capture_root_ref") or ""))
    if private_path.exists() or public_path.exists():
        raise CaseTruthLiveError("case_truth_live_identity_consumed")
    if not (
        output.get("run_id")
        and output.get("attempt_id")
        and output.get("product_publication") == "forbidden"
    ):
        raise CaseTruthLiveError("case_truth_live_output_contract_invalid")
    required_targets = targets.get("required_false_absence_detections")
    accepted_gap = targets.get("required_legitimate_absence")
    if not (
        targets.get("required_surface_count") == 15
        and isinstance(required_targets, list)
        and len(required_targets) == 3
        and isinstance(accepted_gap, Mapping)
        and targets.get("semantic_assessment_after_run_required") is True
    ):
        raise CaseTruthLiveError("case_truth_live_targets_invalid")
    return paths, capture_root, private_path, public_path, commit


def _tool_arguments(step: ChatCompletionToolStepResult) -> dict[str, Any]:
    if step.finish_reason == "length":
        raise CaseTruthLiveError("case_truth_live_length_stop")
    if len(step.tool_calls) != 1:
        raise CaseTruthLiveError("case_truth_live_tool_call_count_invalid")
    call = step.tool_calls[0]
    function = call.get("function")
    if not (
        isinstance(function, Mapping)
        and function.get("name") == "submit_case_truth_reconciliation"
    ):
        raise CaseTruthLiveError("case_truth_live_tool_name_invalid")
    try:
        arguments = json.loads(str(function.get("arguments") or ""))
    except json.JSONDecodeError as exc:
        raise CaseTruthLiveError(
            "case_truth_live_tool_arguments_invalid_json"
        ) from exc
    if not isinstance(arguments, dict):
        raise CaseTruthLiveError("case_truth_live_tool_arguments_invalid")
    return arguments


def assess_pre_registered_targets(
    *,
    arguments: Mapping[str, Any],
    receipt: Mapping[str, Any],
    targets: Mapping[str, Any],
) -> dict[str, Any]:
    assertions = {
        (
            str(surface.get("claim_surface_id") or ""),
            str(assertion.get("truth_alias") or ""),
            str(assertion.get("asserted_state") or ""),
        )
        for surface in arguments.get("surface_assertions") or []
        if isinstance(surface, Mapping)
        for assertion in surface.get("assertions") or []
        if isinstance(assertion, Mapping)
    }
    findings = {
        (
            str(row.get("claim_surface_id") or ""),
            str(row.get("truth_alias") or ""),
            str(row.get("finding_code") or ""),
        )
        for row in receipt.get("findings") or []
        if isinstance(row, Mapping)
    }
    target_results = []
    for row in targets["required_false_absence_detections"]:
        key = (
            str(row["claim_surface_id"]),
            str(row["truth_alias"]),
            "absent_from_current_case",
        )
        finding_key = (
            key[0],
            key[1],
            "asserted_absent_but_present_in_case",
        )
        target_results.append(
            {
                "claim_surface_id": key[0],
                "truth_alias": key[1],
                "model_extracted_required_assertion": key in assertions,
                "local_authority_rejected_false_absence": finding_key in findings,
            }
        )
    accepted = targets["required_legitimate_absence"]
    accepted_key = (
        str(accepted["claim_surface_id"]),
        str(accepted["truth_alias"]),
        "absent_from_current_case",
    )
    legitimate_selected = accepted_key in assertions
    legitimate_rejected = any(
        row[0] == accepted_key[0] and row[1] == accepted_key[1]
        for row in findings
    )
    target_pass = all(
        row["model_extracted_required_assertion"]
        and row["local_authority_rejected_false_absence"]
        for row in target_results
    )
    surface_count = len(arguments.get("surface_assertions") or [])
    return {
        "required_false_absence_detections": target_results,
        "all_required_false_absences_extracted_and_rejected": target_pass,
        "legitimate_profit_bridge_absence_extracted": legitimate_selected,
        "legitimate_profit_bridge_absence_preserved": (
            legitimate_selected and not legitimate_rejected
        ),
        "surface_count": surface_count,
        "automatic_critical_targets_pass": (
            target_pass
            and legitimate_selected
            and not legitimate_rejected
            and surface_count == int(targets["required_surface_count"])
        ),
        "semantic_content_assessment_pending": True,
    }


def run(
    authority_path: Path,
    *,
    executor: Callable[..., ChatCompletionToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> dict[str, Any]:
    authority = _json(authority_path)
    paths, capture_root, private_path, public_path, commit = _validate_authority(
        authority, authority_path=authority_path
    )
    r7_public = _json(paths["r7_public_result_ref"])
    r7_private = _json(paths["r7_private_result_ref"])
    zero_call = _json(paths["zero_call_result_ref"])
    if not (
        r7_public.get("private_full_result_sha256")
        == _sha(paths["r7_private_result_ref"])
        and r7_private.get("case_key") == "DELL"
        and zero_call.get("status")
        == "zero_call_case_truth_reconciliation_engineering_pass"
    ):
        raise CaseTruthLiveError("case_truth_live_predecessor_binding_invalid")
    research_input = r7_private["dynamic_projection"]["claim_surface_projection"][
        "claim_surface_research_input"
    ]
    packet = compile_case_truth_packet(research_input)
    document = compile_cell_judgment_claim_document(r7_private["judgment_output"])
    bound = authority["bound_inputs"]
    if not (
        packet["case_truth_packet_digest"]
        == bound["expected_case_truth_packet_digest"]
        and document["claim_document_digest"]
        == bound["expected_claim_document_digest"]
        and packet["case_truth_packet_digest"]
        == zero_call["r7_replay"]["case_truth_packet_digest"]
    ):
        raise CaseTruthLiveError("case_truth_live_truth_input_digest_drift")
    messages, canonical_tool = compile_case_truth_reconciliation_submission(
        case_truth_packet=packet,
        claim_document=document,
    )
    wire_tool, projection = project_deepseek_strict_tool(canonical_tool)
    profile = load_chat_completion_profile(_json(paths["provider_profile_ref"]))
    if not (
        profile.provider_id == "deepseek"
        and profile.model == "deepseek-v4-pro"
        and profile.base_url.rstrip("/") == "https://api.deepseek.com/beta"
        and profile.endpoint == "/chat/completions"
        and dict(profile.request_defaults)
        == {
            "max_tokens": 8000,
            "stream": False,
            "thinking": {"type": "enabled"},
            "reasoning_effort": "low",
        }
        and projection["finance_contract_weakened"] is False
    ):
        raise CaseTruthLiveError("case_truth_live_profile_or_projection_invalid")

    provider_step: dict[str, Any] = {}
    arguments: dict[str, Any] = {}
    receipt: dict[str, Any] = {}
    target_assessment: dict[str, Any] = {}
    failure_phase = ""
    failure_code = ""
    failure_capture_ref = ""
    model_call_attempted = False
    try:
        model_call_attempted = True
        step = executor(
            profile=profile,
            messages=messages,
            tools=[wire_tool],
            capture_root=capture_root,
            run_id=str(authority["output_contract"]["run_id"]),
            attempt_id=str(authority["output_contract"]["attempt_id"]),
            tool_choice=None,
        )
        provider_step = step.as_dict()
        arguments = _tool_arguments(step)
        receipt = validate_case_truth_reconciliation(
            arguments,
            case_truth_packet=packet,
            claim_document=document,
        )
        target_assessment = assess_pre_registered_targets(
            arguments=arguments,
            receipt=receipt,
            targets=authority["pre_registered_targets"],
        )
    except ModelGatewayError as exc:
        failure_phase = "provider_transport_or_response"
        failure_code = exc.code
        failure_capture_ref = _relative(exc.capture_ref) if exc.capture_ref else ""
    except (CaseTruthLiveError, CaseTruthReconciliationError) as exc:
        failure_phase = "tool_call_or_local_semantic_validation"
        failure_code = getattr(exc, "code", type(exc).__name__)
        if provider_step and provider_step.get("response_capture_ref"):
            failure_capture_ref = _relative(provider_step["response_capture_ref"])

    execution = {
        "model_calls_attempted": 1 if model_call_attempted else 0,
        "provider_calls_attempted": 1 if model_call_attempted else 0,
        "transport_attempts": 1 if model_call_attempted else 0,
        "retries": 0,
        "fallbacks": 0,
        "protocol_switches": 0,
        "network_source_calls": 0,
        "embedding_calls": 0,
        "candidate_promotions": 0,
        "research_rewrites": 0,
        "report_generations": 0,
        "product_publication": False,
    }
    private_unsigned = {
        "schema_version": "fin_ia_s3_case_truth_reconciliation_live_private_v1_0",
        "run_id": authority["output_contract"]["run_id"],
        "implementation_commit": commit,
        "case_key": "DELL",
        "case_truth_packet": packet,
        "claim_document": document,
        "provider_step": provider_step,
        "model_submission": arguments,
        "local_reconciliation_receipt": receipt,
        "pre_registered_target_assessment": target_assessment,
        "failure": {
            "phase": failure_phase,
            "code": failure_code,
            "capture_ref": failure_capture_ref,
        },
        "execution": execution,
    }
    private_payload = {
        **private_unsigned,
        "private_result_digest": canonical_digest(private_unsigned),
    }
    _write_new(private_path, private_payload)
    public_unsigned = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": (
            "completed_semantic_content_assessment_pending"
            if receipt
            else "terminal_failed_no_retry"
        ),
        "run_id": authority["output_contract"]["run_id"],
        "recorded_at": authority["signed_at"],
        "implementation_commit": commit,
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "private_result_ref": _relative(private_path),
        "private_result_sha256": _sha(private_path),
        "provider": {
            "provider_id": provider_step.get("provider_id", "deepseek"),
            "model": provider_step.get("model", "deepseek-v4-pro"),
            "finish_reason": provider_step.get("finish_reason", ""),
            "usage": provider_step.get("usage", {}),
            "request_capture_ref": (
                _relative(provider_step["request_capture_ref"])
                if provider_step.get("request_capture_ref")
                else ""
            ),
            "response_capture_ref": (
                _relative(provider_step["response_capture_ref"])
                if provider_step.get("response_capture_ref")
                else ""
            ),
            "private_reasoning_persisted": False,
        },
        "contract": {
            "case_truth_packet_digest": packet["case_truth_packet_digest"],
            "claim_document_digest": document["claim_document_digest"],
            "claim_surface_count": len(document["claim_surfaces"]),
            "tool_projection_digest": projection["projection_digest"],
            "finance_contract_weakened": False,
            "local_reconciliation_status": receipt.get("status", ""),
            "local_finding_codes": [
                row["finding_code"] for row in receipt.get("findings") or []
            ],
        },
        "pre_registered_target_assessment": target_assessment,
        "failure": {
            "phase": failure_phase,
            "code": failure_code,
            "capture_ref": failure_capture_ref,
        },
        "execution": execution,
        "acceptance": {
            "provider_call_completed": bool(provider_step),
            "strict_tool_call_parsed": bool(arguments),
            "local_exhaustive_validation_completed": bool(receipt),
            "automatic_critical_targets_pass": bool(
                target_assessment.get("automatic_critical_targets_pass")
            ),
            "semantic_content_assessment_complete": False,
            "natural_semantic_extraction_accepted": False,
            "r7_repaired": False,
            "dell_five_cell_accepted": False,
            "generalization_accepted": False,
            "s3_accepted": False,
            "release_ready": False,
        },
        "known_boundary": (
            "This one-call canary only tests natural semantic classification of "
            "the immutable R7 cell claim surfaces. Even automatic critical-target "
            "success requires a separate full-surface content assessment. It does "
            "not rewrite R7, generate a report, authorize an affected-node successor, "
            "prove DELL or cross-case quality, publish to Workbench, accept S3 or release."
        ),
    }
    public_payload = {
        **public_unsigned,
        "result_digest": canonical_digest(public_unsigned),
    }
    _write_new(public_path, public_payload)
    return public_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    args = parser.parse_args()
    result = run(_resolve(args.authority))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
