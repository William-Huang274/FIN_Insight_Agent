from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.canonical_runtime import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import build_preflight  # noqa: E402
from sec_agent.providers import (  # noqa: E402
    ChatCompletionToolStepResult,
    execute_chat_completion_tool_step_exact_once,
    load_chat_completion_profile,
)
from sec_agent.research.multi_agent_report_authority import (  # noqa: E402
    apply_protected_report_reference_patch,
    compile_protected_report_reference_patch_messages,
    compile_protected_report_reference_patch_receipt,
    compile_protected_report_remap_messages,
    protected_report_reference_patch_tool,
    protected_report_draft_tool,
    render_protected_report,
    validate_protected_report_remap_draft,
)
from sec_agent.research.multi_agent_report_remap import (  # noqa: E402
    REPORT_REMAP_FULL_RESULT_SCHEMA_VERSION,
    REPORT_REMAP_LIVE_AUTHORITY_SCHEMA_VERSION,
    REPORT_REMAP_PUBLIC_RESULT_SCHEMA_VERSION,
    REPORT_REMAP_REFERENCE_PATCH_FULL_RESULT_SCHEMA_VERSION,
    REPORT_REMAP_REFERENCE_PATCH_LIVE_AUTHORITY_SCHEMA_VERSION,
    REPORT_REMAP_REFERENCE_PATCH_PUBLIC_RESULT_SCHEMA_VERSION,
    validate_report_remap_scope_decision,
)


DEFAULT_DECISION_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_"
    "protected_report_remap_scope_decision_v1_0.json"
)
DEFAULT_PREFLIGHT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_"
    "protected_report_remap_project_os_preflight_v1_0.json"
)
DEFAULT_AUTHORITY_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_"
    "protected_report_remap_live_authority_v1_0.json"
)
DEFAULT_PUBLIC_RESULT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_"
    "protected_report_remap_live_result_v1_0.json"
)
DEFAULT_RUN_ID = "FIN_0_1_3_S3_DELL_MULTI_AGENT_PROTECTED_REPORT_REMAP_20260821"
DEFAULT_CAPTURE_ROOT_REF = (
    "data/captures/fin_0_1_3_s3_dell_multi_agent_"
    "protected_report_remap_20260821"
)
DEFAULT_PRIVATE_ROOT_REF = (
    "data/workbench_private/model_runs/fin_0_1_3_s3_dell_multi_agent_"
    "protected_report_remap_20260821"
)
_TOOL_NAME = "submit_protected_report_draft"
_PATCH_TOOL_NAME = "submit_protected_report_reference_patch"


class ReportRemapLiveError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        phase: str = "",
        attempts: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        self.code = code
        self.phase = phase
        self.attempts = [deepcopy(dict(row)) for row in attempts]
        super().__init__(code)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve(ref: str | Path) -> Path:
    path = Path(ref)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportRemapLiveError(
            "report_remap_live_json_invalid", phase="binding"
        ) from exc
    if not isinstance(value, dict):
        raise ReportRemapLiveError(
            "report_remap_live_json_object_required", phase="binding"
        )
    return value


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise ReportRemapLiveError(
            "report_remap_live_output_identity_consumed", phase="materialization"
        ) from exc


def _git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    value = completed.stdout.strip().lower()
    if completed.returncode != 0 or len(value) != 40:
        raise ReportRemapLiveError(
            "report_remap_live_git_head_invalid", phase="binding"
        )
    return value


def _binding(ref: str, *, digest_field: str = "") -> dict[str, Any]:
    path = _resolve(ref)
    payload = _json(path)
    row: dict[str, Any] = {"ref": _relative(path), "sha256": _sha(path)}
    if digest_field:
        digest = payload.get(digest_field)
        if not isinstance(digest, str) or not digest:
            raise ReportRemapLiveError(
                "report_remap_live_binding_digest_missing", phase="binding"
            )
        row.update({"digest_field": digest_field, "digest": digest})
    return row


def _load_binding(binding: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    allowed = {"ref", "sha256", "digest_field", "digest", "decision_digest"}
    if not {"ref", "sha256"}.issubset(binding) or not set(binding).issubset(
        allowed
    ):
        raise ReportRemapLiveError(
            "report_remap_live_binding_shape_invalid", phase="binding"
        )
    path = _resolve(str(binding["ref"]))
    try:
        _relative(path)
    except ValueError as exc:
        raise ReportRemapLiveError(
            "report_remap_live_binding_outside_root", phase="binding"
        ) from exc
    if not path.is_file() or _sha(path) != str(binding["sha256"]):
        raise ReportRemapLiveError(
            "report_remap_live_binding_sha_drift", phase="binding"
        )
    payload = _json(path)
    field = str(binding.get("digest_field") or "")
    if field and payload.get(field) != binding.get("digest"):
        raise ReportRemapLiveError(
            "report_remap_live_binding_digest_drift", phase="binding"
        )
    return path, payload


def _authority_unsigned(authority: Mapping[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in authority.items() if key != "authority_digest"}


def _is_reference_patch_projection(projection: Mapping[str, Any]) -> bool:
    return projection.get("multi_agent_report_reference_patch") is True


def _authority_bound_input_names(
    projection: Mapping[str, Any],
) -> tuple[str, ...]:
    base = (
        "predecessor_private_full_result",
        "predecessor_content_assessment",
        "report_authority_catalog",
        "writer_submission_profile",
        "report_surface_zero_call_proof",
    )
    if not _is_reference_patch_projection(projection):
        return base
    return (
        *base,
        "failed_replacement_remap_live_authority",
        "failed_replacement_remap_public_result",
        "failed_replacement_remap_private_terminal_result",
        "report_reference_patch_zero_call_proof",
    )


def issue_authority(
    *,
    decision_ref: str = DEFAULT_DECISION_REF,
    preflight_ref: str = DEFAULT_PREFLIGHT_REF,
    authority_ref: str = DEFAULT_AUTHORITY_REF,
    run_id: str = DEFAULT_RUN_ID,
    capture_root_ref: str = DEFAULT_CAPTURE_ROOT_REF,
    private_root_ref: str = DEFAULT_PRIVATE_ROOT_REF,
    public_result_ref: str = DEFAULT_PUBLIC_RESULT_REF,
) -> dict[str, Any]:
    """Issue one fresh authority only from a clean, synced repository."""

    decision_path = _resolve(decision_ref)
    decision = _json(decision_path)
    projection = validate_report_remap_scope_decision(root=ROOT, decision=decision)
    preflight = build_preflight(
        root=ROOT,
        decision_ref=_relative(decision_path),
        environment=os.environ,
        check_repository=True,
    )
    preflight_path = _resolve(preflight_ref)
    _write_new(preflight_path, preflight)

    bound = decision["bound_inputs"]
    reference_patch = _is_reference_patch_projection(projection)
    authority_body = {
        "schema_version": (
            REPORT_REMAP_REFERENCE_PATCH_LIVE_AUTHORITY_SCHEMA_VERSION
            if reference_patch
            else REPORT_REMAP_LIVE_AUTHORITY_SCHEMA_VERSION
        ),
        "status": (
            "approved_for_one_writer_only_protected_report_reference_patch"
            if reference_patch
            else "approved_for_one_writer_only_protected_report_terminal_remap"
        ),
        "authorized_at": _now(),
        "implementation_commit": preflight["repository"]["head"],
        "run_scope_id": projection["run_scope_id"],
        "project_os_preflight": {
            "ref": _relative(preflight_path),
            "sha256": _sha(preflight_path),
        },
        "scope_decision": {
            "ref": _relative(decision_path),
            "sha256": _sha(decision_path),
            "decision_digest": decision["decision_digest"],
        },
        "bound_inputs": {
            name: deepcopy(bound[name])
            for name in _authority_bound_input_names(projection)
        },
        "execution_limits": deepcopy(projection["execution_limits"]),
        "token_budget_basis": deepcopy(projection["token_budget_basis"]),
        "outputs": {
            "run_id": run_id,
            "capture_root_ref": _relative(_resolve(capture_root_ref)),
            "private_output_root_ref": _relative(_resolve(private_root_ref)),
            "public_result_ref": _relative(_resolve(public_result_ref)),
        },
        "authority_statement": (
            (
                "Authorize exactly one fresh Writer-only reference-patch logical "
                "node with at most two bounded contract attempts over the second "
                "complete v1.1 payload. Permit only the five path-scoped reference "
                "bindings; report text and source-agent identities are immutable. "
                "Authorize zero analysis, continuation, upstream Agent, repair, "
                "Evaluator, retrieval, network or Candidate-promotion calls. The "
                "Harness validates and renders every protected surface."
            )
            if reference_patch
            else (
                "Authorize exactly one fresh Writer-only terminal remapping logical "
                "node with at most two bounded contract attempts. Reuse the immutable "
                "completed report and typed authority only. Authorize zero analysis, "
                "continuation, upstream Agent, repair, Evaluator, retrieval, network "
                "or Candidate-promotion calls. The Harness deterministically renders "
                "all protected numeric, temporal, identity and citation surfaces."
            )
        ),
    }
    authority = {
        **authority_body,
        "authority_digest": canonical_digest(authority_body),
    }
    _write_new(_resolve(authority_ref), authority)
    return authority


def validate_authority(
    authority_path: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    authority = _json(authority_path)
    expected = {
        "schema_version",
        "status",
        "authorized_at",
        "implementation_commit",
        "run_scope_id",
        "project_os_preflight",
        "scope_decision",
        "bound_inputs",
        "execution_limits",
        "token_budget_basis",
        "outputs",
        "authority_statement",
        "authority_digest",
    }
    allowed_authority_identities = {
        (
            REPORT_REMAP_LIVE_AUTHORITY_SCHEMA_VERSION,
            "approved_for_one_writer_only_protected_report_terminal_remap",
        ),
        (
            REPORT_REMAP_REFERENCE_PATCH_LIVE_AUTHORITY_SCHEMA_VERSION,
            "approved_for_one_writer_only_protected_report_reference_patch",
        ),
    }
    if set(authority) != expected or not (
        (authority["schema_version"], authority["status"])
        in allowed_authority_identities
        and authority["authority_digest"]
        == canonical_digest(_authority_unsigned(authority))
        and authority["implementation_commit"] == _git_head()
    ):
        raise ReportRemapLiveError(
            "report_remap_live_authority_identity_invalid", phase="binding"
        )
    _, decision = _load_binding(authority["scope_decision"])
    if authority["scope_decision"].get("decision_digest") != decision.get(
        "decision_digest"
    ):
        raise ReportRemapLiveError(
            "report_remap_live_decision_digest_drift", phase="binding"
        )
    projection = validate_report_remap_scope_decision(root=ROOT, decision=decision)
    reference_patch = _is_reference_patch_projection(projection)
    expected_authority_identity = (
        (
            REPORT_REMAP_REFERENCE_PATCH_LIVE_AUTHORITY_SCHEMA_VERSION,
            "approved_for_one_writer_only_protected_report_reference_patch",
        )
        if reference_patch
        else (
            REPORT_REMAP_LIVE_AUTHORITY_SCHEMA_VERSION,
            "approved_for_one_writer_only_protected_report_terminal_remap",
        )
    )
    if not (
        (authority["schema_version"], authority["status"])
        == expected_authority_identity
        and
        authority["run_scope_id"] == projection["run_scope_id"]
        and authority["execution_limits"] == projection["execution_limits"]
        and authority["token_budget_basis"] == projection["token_budget_basis"]
    ):
        raise ReportRemapLiveError(
            "report_remap_live_authority_budget_drift", phase="binding"
        )
    _, preflight = _load_binding(authority["project_os_preflight"])
    if not (
        preflight.get("status") == "pass_current_decision_bound_preflight"
        and preflight.get("decision_ref") == authority["scope_decision"]["ref"]
        and preflight.get("decision_sha256") == authority["scope_decision"]["sha256"]
        and preflight.get("run_scope_id") == authority["run_scope_id"]
        and (preflight.get("repository") or {}).get("head")
        == authority["implementation_commit"]
        and (preflight.get("repository") or {}).get("clean") is True
        and (preflight.get("repository") or {}).get("synced") is True
    ):
        raise ReportRemapLiveError(
            "report_remap_live_preflight_invalid", phase="binding"
        )
    required_bound = set(_authority_bound_input_names(projection))
    if set(authority["bound_inputs"]) != required_bound:
        raise ReportRemapLiveError(
            "report_remap_live_bound_inputs_invalid", phase="binding"
        )
    loaded: dict[str, dict[str, Any]] = {}
    for name in sorted(required_bound):
        _, loaded[name] = _load_binding(authority["bound_inputs"][name])
        if authority["bound_inputs"][name] != decision["bound_inputs"][name]:
            raise ReportRemapLiveError(
                "report_remap_live_bound_input_decision_drift", phase="binding"
            )
    outputs = authority["outputs"]
    if set(outputs) != {
        "run_id",
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
    }:
        raise ReportRemapLiveError(
            "report_remap_live_outputs_invalid", phase="binding"
        )
    for name in ("capture_root_ref", "private_output_root_ref", "public_result_ref"):
        path = _resolve(str(outputs[name]))
        try:
            _relative(path)
        except ValueError as exc:
            raise ReportRemapLiveError(
                "report_remap_live_output_outside_root", phase="binding"
            ) from exc
    source = loaded["predecessor_private_full_result"]
    assessment = loaded["predecessor_content_assessment"]
    proof = loaded["report_surface_zero_call_proof"]
    if not (
        isinstance(source.get("report"), Mapping)
        and isinstance(source.get("evaluations"), list)
        and len(source["evaluations"]) >= 1
        and source["evaluations"][-1].get("report_may_proceed") is True
        and source["report"].get("report_digest") == assessment.get("report_digest")
        and assessment.get("financial_truth_L1_pass") is False
        and proof.get("status") == "zero_call_structure_pass_terminal_remap_eligible"
    ):
        raise ReportRemapLiveError(
            "report_remap_live_source_state_invalid", phase="binding"
        )
    if reference_patch:
        failed = loaded["failed_replacement_remap_private_terminal_result"]
        proof = loaded["report_reference_patch_zero_call_proof"]
        failed_attempts = failed.get("contract_attempts") or []
        if not (
            failed.get("status")
            == "protected_report_terminal_remap_failure_preserved"
            and len(failed_attempts) == 2
            and proof.get("status")
            == "zero_call_reference_patch_structure_pass_fresh_live_eligible"
            and (proof.get("actual_replay") or {}).get("base_attempt_index")
            == 2
            and (proof.get("actual_replay") or {}).get("base_payload_digest")
            == projection["reference_patch_base_payload_digest"]
            and (proof.get("actual_replay") or {}).get("patch_receipt_digest")
            == projection["reference_patch_receipt_digest"]
        ):
            raise ReportRemapLiveError(
                "report_remap_live_reference_patch_state_invalid",
                phase="binding",
            )
    load_chat_completion_profile(loaded["writer_submission_profile"])
    return authority, loaded


def _submission_envelope(
    result: ChatCompletionToolStepResult,
    *,
    tool_name: str = _TOOL_NAME,
) -> tuple[str, str]:
    if len(result.tool_calls) != 1:
        raise ReportRemapLiveError(
            "report_remap_live_tool_call_count_invalid", phase="contract"
        )
    call = result.tool_calls[0]
    function = call.get("function") or {}
    if function.get("name") != tool_name:
        raise ReportRemapLiveError(
            "report_remap_live_tool_name_invalid", phase="contract"
        )
    call_id = str(call.get("id") or "")
    if not call_id:
        raise ReportRemapLiveError(
            "report_remap_live_tool_call_id_missing", phase="contract"
        )
    return call_id, str(function.get("arguments") or "")


def _parse_submission(
    result: ChatCompletionToolStepResult,
    *,
    tool_name: str = _TOOL_NAME,
) -> tuple[str, dict[str, Any]]:
    call_id, arguments = _submission_envelope(result, tool_name=tool_name)
    try:
        payload = json.loads(arguments)
    except json.JSONDecodeError as exc:
        code = (
            "report_remap_live_tool_arguments_truncated_at_output_budget"
            if result.finish_reason == "length"
            else "report_remap_live_tool_arguments_json_invalid"
        )
        raise ReportRemapLiveError(
            code, phase="contract"
        ) from exc
    if not isinstance(payload, dict):
        raise ReportRemapLiveError(
            "report_remap_live_tool_arguments_object_required", phase="contract"
        )
    return call_id, payload


def _capture_ref(value: object) -> str:
    path = Path(str(value or ""))
    if not str(value or ""):
        return ""
    try:
        return _relative(path)
    except (OSError, ValueError):
        return path.as_posix()


def execute_contract_attempts(
    *,
    profile: Any,
    source_report: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    authority_catalog: Mapping[str, Any],
    capture_root: Path,
    run_id: str,
    executor: Callable[..., ChatCompletionToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Run one logical Writer node with at most two contract attempts."""

    messages = list(
        compile_protected_report_remap_messages(
            source_report=source_report,
            evaluation=evaluation,
            authority_catalog=authority_catalog,
        )
    )
    tool = protected_report_draft_tool(authority_catalog=authority_catalog)
    attempts: list[dict[str, Any]] = []
    last_error = "report_remap_live_contract_not_started"
    for number in (1, 2):
        attempt_id = f"WRITER-PROTECTED-REMAP-CONTRACT-ATTEMPT-{number:02d}"
        try:
            result = executor(
                profile=profile,
                messages=messages,
                tools=[tool],
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=attempt_id,
                tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
            )
        except Exception as exc:
            attempts.append(
                {
                    "attempt_id": attempt_id,
                    "phase": "provider_transport",
                    "status": "terminal_transport_failure",
                    "failure_code": str(getattr(exc, "code", "") or type(exc).__name__),
                    "capture_ref": _capture_ref(
                        getattr(exc, "capture_ref", "")
                    ),
                }
            )
            raise ReportRemapLiveError(
                "report_remap_live_provider_transport_failure",
                phase="provider_transport",
                attempts=attempts,
            ) from exc
        result_receipt = result.as_dict()
        result_receipt["request_capture_ref"] = _capture_ref(
            result_receipt.get("request_capture_ref")
        )
        result_receipt["response_capture_ref"] = _capture_ref(
            result_receipt.get("response_capture_ref")
        )
        receipt = {
            "attempt_id": attempt_id,
            "phase": "contract_submission",
            "status": "provider_response_captured",
            **result_receipt,
        }
        try:
            tool_call_id, payload = _parse_submission(result)
            draft = validate_protected_report_remap_draft(
                payload,
                authority_catalog=authority_catalog,
                source_report=source_report,
            )
            rendered = render_protected_report(
                draft, authority_catalog=authority_catalog
            )
        except Exception as exc:
            last_error = str(getattr(exc, "code", "") or str(exc) or type(exc).__name__)
            receipt.update(
                {
                    "status": "contract_rejected",
                    "failure_code": last_error,
                }
            )
            attempts.append(receipt)
            if number == 2:
                break
            call_id = ""
            try:
                call_id, _ = _submission_envelope(result)
            except ReportRemapLiveError:
                pass
            if not call_id:
                raise ReportRemapLiveError(
                    "report_remap_live_unrepairable_tool_envelope",
                    phase="contract",
                    attempts=attempts,
                ) from exc
            messages.extend(
                [
                    result.continuation_assistant_message(),
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(
                            {
                                "status": "rejected",
                                "failure_code": last_error,
                                "instruction": (
                                    "Correct only the protected report contract. "
                                    "Do not change research meaning or topology. "
                                    "Return the complete contract from the beginning, "
                                    "use one concise clause per source section, and "
                                    "select only the minimum refs needed for each clause."
                                ),
                                "remaining_contract_attempts": 1,
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    },
                ]
            )
            continue
        receipt.update(
            {
                "status": "contract_validated_and_rendered",
                "draft_digest": draft["draft_digest"],
                "rendered_report_digest": rendered["rendered_report_digest"],
            }
        )
        attempts.append(receipt)
        return draft, rendered, attempts
    raise ReportRemapLiveError(
        last_error, phase="contract", attempts=attempts
    )


def execute_reference_patch_attempts(
    *,
    profile: Any,
    base_payload: Mapping[str, Any],
    source_report: Mapping[str, Any],
    authority_catalog: Mapping[str, Any],
    capture_root: Path,
    run_id: str,
    executor: Callable[..., ChatCompletionToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
]:
    """Correct only failed reference bindings in one immutable complete payload."""

    patch_receipt = compile_protected_report_reference_patch_receipt(
        base_payload, authority_catalog=authority_catalog
    )
    messages = list(
        compile_protected_report_reference_patch_messages(
            base_payload=base_payload,
            patch_receipt=patch_receipt,
            authority_catalog=authority_catalog,
        )
    )
    tool = protected_report_reference_patch_tool(
        patch_receipt=patch_receipt,
        authority_catalog=authority_catalog,
    )
    attempts: list[dict[str, Any]] = []
    last_error = "report_remap_reference_patch_not_started"
    for number in (1, 2):
        attempt_id = f"WRITER-PROTECTED-REFERENCE-PATCH-ATTEMPT-{number:02d}"
        try:
            result = executor(
                profile=profile,
                messages=messages,
                tools=[tool],
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=attempt_id,
                tool_choice={
                    "type": "function",
                    "function": {"name": _PATCH_TOOL_NAME},
                },
            )
        except Exception as exc:
            attempts.append(
                {
                    "attempt_id": attempt_id,
                    "phase": "provider_transport",
                    "status": "terminal_transport_failure",
                    "failure_code": str(
                        getattr(exc, "code", "") or type(exc).__name__
                    ),
                    "capture_ref": _capture_ref(
                        getattr(exc, "capture_ref", "")
                    ),
                }
            )
            raise ReportRemapLiveError(
                "report_remap_live_provider_transport_failure",
                phase="provider_transport",
                attempts=attempts,
            ) from exc
        result_receipt = result.as_dict()
        result_receipt["request_capture_ref"] = _capture_ref(
            result_receipt.get("request_capture_ref")
        )
        result_receipt["response_capture_ref"] = _capture_ref(
            result_receipt.get("response_capture_ref")
        )
        receipt = {
            "attempt_id": attempt_id,
            "phase": "reference_patch_submission",
            "status": "provider_response_captured",
            **result_receipt,
        }
        try:
            tool_call_id, patch_payload = _parse_submission(
                result, tool_name=_PATCH_TOOL_NAME
            )
            draft = apply_protected_report_reference_patch(
                patch_payload,
                base_payload=base_payload,
                patch_receipt=patch_receipt,
                authority_catalog=authority_catalog,
                source_report=source_report,
            )
            rendered = render_protected_report(
                draft, authority_catalog=authority_catalog
            )
        except Exception as exc:
            last_error = str(
                getattr(exc, "code", "")
                or str(exc)
                or type(exc).__name__
            )
            failure_details = deepcopy(
                dict(getattr(exc, "details", {}) or {})
            )
            receipt.update(
                {
                    "status": "contract_rejected",
                    "failure_code": last_error,
                    "failure_details": failure_details,
                }
            )
            attempts.append(receipt)
            if number == 2:
                break
            call_id = ""
            try:
                call_id, _ = _submission_envelope(
                    result, tool_name=_PATCH_TOOL_NAME
                )
            except ReportRemapLiveError:
                pass
            if not call_id:
                raise ReportRemapLiveError(
                    "report_remap_live_unrepairable_tool_envelope",
                    phase="contract",
                    attempts=attempts,
                ) from exc
            messages.extend(
                [
                    result.continuation_assistant_message(),
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(
                            {
                                "status": "rejected",
                                "failure_code": last_error,
                                "failure_details": failure_details,
                                "instruction": (
                                    "Correct only the complete reference patch. "
                                    "Return every target path exactly once. Do not "
                                    "write report prose or modify source-agent identity."
                                ),
                                "remaining_contract_attempts": 1,
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    },
                ]
            )
            continue
        receipt.update(
            {
                "status": "reference_patch_validated_and_rendered",
                "patch_receipt_digest": patch_receipt[
                    "patch_receipt_digest"
                ],
                "draft_digest": draft["draft_digest"],
                "rendered_report_digest": rendered["rendered_report_digest"],
            }
        )
        attempts.append(receipt)
        return draft, rendered, attempts, patch_receipt
    raise ReportRemapLiveError(
        last_error, phase="contract", attempts=attempts
    )


def _result_execution(
    *, attempts: Sequence[Mapping[str, Any]], success: bool
) -> dict[str, Any]:
    return {
        "logical_model_node_count": 1,
        "maximum_logical_model_nodes": 1,
        "contract_attempt_count": len(attempts),
        "maximum_contract_attempts": 2,
        "analysis_call_count": 0,
        "writer_continuation_call_count": 0,
        "upstream_agent_call_count": 0,
        "repair_call_count": 0,
        "evaluator_call_count": 0,
        "external_source_network_calls": 0,
        "candidate_promotions": 0,
        "scope_compliant": (
            1 <= len(attempts) <= 2
            and all(row.get("phase") != "analysis" for row in attempts)
        ),
        "terminal_contract_valid": success,
        "credential_value_persisted": False,
        "provider_private_reasoning_persisted": False,
    }


def _materialize(
    *,
    authority_path: Path,
    authority: Mapping[str, Any],
    attempts: Sequence[Mapping[str, Any]],
    draft: Mapping[str, Any] | None,
    rendered: Mapping[str, Any] | None,
    failure: BaseException | None,
    source_report_digest: str,
    patch_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    outputs = authority["outputs"]
    private_root = _resolve(str(outputs["private_output_root_ref"]))
    public_path = _resolve(str(outputs["public_result_ref"]))
    success = draft is not None and rendered is not None and failure is None
    reference_patch = (
        authority.get("schema_version")
        == REPORT_REMAP_REFERENCE_PATCH_LIVE_AUTHORITY_SCHEMA_VERSION
    )
    execution = _result_execution(attempts=attempts, success=success)
    patch_projection = (
        {
            "base_contract_ref": authority["bound_inputs"][
                "failed_replacement_remap_private_terminal_result"
            ]["ref"],
            "base_contract_attempt_index": 2,
            "base_payload_digest": str(
                (patch_receipt or {}).get("base_payload_digest") or ""
            ),
            "patch_receipt_digest": str(
                (patch_receipt or {}).get("patch_receipt_digest") or ""
            ),
            "target_paths": list((patch_receipt or {}).get("target_paths") or []),
            "model_text_mutation_authorized": False,
            "source_agent_mutation_authorized": False,
            "reference_binding_mutation_authorized": True,
        }
        if reference_patch
        else None
    )
    full_body = {
        "schema_version": (
            REPORT_REMAP_REFERENCE_PATCH_FULL_RESULT_SCHEMA_VERSION
            if reference_patch
            else REPORT_REMAP_FULL_RESULT_SCHEMA_VERSION
        ),
        "status": (
            (
                "protected_report_reference_patch_completed"
                if success
                else "protected_report_reference_patch_failure_preserved"
            )
            if reference_patch
            else (
                "protected_report_terminal_remap_completed"
                if success
                else "protected_report_terminal_remap_failure_preserved"
            )
        ),
        "recorded_at": _now(),
        "run_id": outputs["run_id"],
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "authority_digest": authority["authority_digest"],
        "implementation_commit": authority["implementation_commit"],
        "source_report_ref": authority["bound_inputs"][
            "predecessor_private_full_result"
        ]["ref"],
        "source_report_digest": source_report_digest,
        "reference_patch": patch_projection,
        "contract_attempts": [deepcopy(dict(row)) for row in attempts],
        "draft": deepcopy(dict(draft)) if draft else None,
        "rendered_report": deepcopy(dict(rendered)) if rendered else None,
        "failure": (
            None
            if failure is None
            else {
                "phase": str(getattr(failure, "phase", "") or "unknown"),
                "failure_code": str(
                    getattr(failure, "code", "")
                    or str(failure)
                    or type(failure).__name__
                ),
                "failure_type": type(failure).__name__,
                "failure_details": deepcopy(
                    dict(getattr(failure, "details", {}) or {})
                ),
            }
        ),
        "execution": execution,
        "acceptance": {
            "protected_report_contract_valid": success,
            "reference_patch_contract_valid": (
                success if reference_patch else False
            ),
            "deterministic_surface_render_pass": success,
            "legacy_report_relabelled_pass": False,
            "independent_financial_truth_L1_assessment_pending": success,
            "formal_eight_dimension_assessment_pending": success,
            "qualified_human_acceptance": False,
            "S1_pass": False,
            "S3_pass": False,
            "heterogeneous_generalization": False,
            "workbench_publication": False,
            "release_ready": False,
        },
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    full_path = private_root / (
        "full_result.json" if success else "terminal_failure.json"
    )
    _write_new(full_path, full)
    public_body = {
        "schema_version": (
            REPORT_REMAP_REFERENCE_PATCH_PUBLIC_RESULT_SCHEMA_VERSION
            if reference_patch
            else REPORT_REMAP_PUBLIC_RESULT_SCHEMA_VERSION
        ),
        "status": full["status"],
        "recorded_at": full["recorded_at"],
        "run_id": full["run_id"],
        "authority_ref": full["authority_ref"],
        "authority_sha256": full["authority_sha256"],
        "authority_digest": full["authority_digest"],
        "implementation_commit": full["implementation_commit"],
        "source_report_ref": full["source_report_ref"],
        "source_report_digest": full["source_report_digest"],
        "reference_patch": full["reference_patch"],
        "rendered_report": full["rendered_report"],
        "failure": full["failure"],
        "execution": execution,
        "acceptance": full["acceptance"],
        "full_result_ref": _relative(full_path),
        "full_result_sha256": _sha(full_path),
        "known_boundary": (
            (
                "This result covers one Writer-only reference patch over the "
                "immutable second complete v1.1 contract payload. It may change "
                "only five path-scoped reference bindings; report prose and "
                "source-agent identities remain immutable. It does not rerun "
                "research and does not by itself prove financial-truth L1, content "
                "quality, S1, S3, generalization, qualified-human acceptance, "
                "Workbench publication or release."
            )
            if reference_patch
            else (
                "This result covers one Writer-only terminal contract remap over an "
                "immutable completed DELL report. It does not rerun research and does "
                "not by itself prove content gain, S1, S3, generalization, qualified-"
                "human acceptance, Workbench publication or release."
            )
        ),
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(public_path, public)
    return public


def run(authority_path: Path) -> dict[str, Any]:
    authority: dict[str, Any] | None = None
    attempts: list[dict[str, Any]] = []
    source_report_digest = ""
    patch_receipt: dict[str, Any] | None = None
    try:
        authority, loaded = validate_authority(authority_path)
        outputs = authority["outputs"]
        profile = load_chat_completion_profile(loaded["writer_submission_profile"])
        source_full = loaded["predecessor_private_full_result"]
        source_report_digest = str(
            source_full["report"].get("report_digest") or ""
        )
        if (
            authority.get("schema_version")
            == REPORT_REMAP_REFERENCE_PATCH_LIVE_AUTHORITY_SCHEMA_VERSION
        ):
            failed = loaded[
                "failed_replacement_remap_private_terminal_result"
            ]
            base_attempt = (failed.get("contract_attempts") or [])[1]
            base_call = (base_attempt.get("tool_calls") or [])[0]
            base_payload = json.loads(
                str((base_call.get("function") or {}).get("arguments") or "")
            )
            patch_receipt = compile_protected_report_reference_patch_receipt(
                base_payload,
                authority_catalog=loaded["report_authority_catalog"],
            )
            draft, rendered, attempts, returned_patch_receipt = (
                execute_reference_patch_attempts(
                    profile=profile,
                    base_payload=base_payload,
                    source_report=source_full["report"],
                    authority_catalog=loaded["report_authority_catalog"],
                    capture_root=_resolve(str(outputs["capture_root_ref"])),
                    run_id=str(outputs["run_id"]),
                )
            )
            if returned_patch_receipt != patch_receipt:
                raise ReportRemapLiveError(
                    "report_remap_live_reference_patch_receipt_drift",
                    phase="contract",
                    attempts=attempts,
                )
        else:
            draft, rendered, attempts = execute_contract_attempts(
                profile=profile,
                source_report=source_full["report"],
                evaluation=source_full["evaluations"][-1],
                authority_catalog=loaded["report_authority_catalog"],
                capture_root=_resolve(str(outputs["capture_root_ref"])),
                run_id=str(outputs["run_id"]),
            )
        return _materialize(
            authority_path=authority_path,
            authority=authority,
            attempts=attempts,
            draft=draft,
            rendered=rendered,
            failure=None,
            source_report_digest=source_report_digest,
            patch_receipt=patch_receipt,
        )
    except Exception as exc:
        if authority is None:
            raise
        attempts = [
            deepcopy(dict(row))
            for row in getattr(exc, "attempts", attempts)
        ]
        return _materialize(
            authority_path=authority_path,
            authority=authority,
            attempts=attempts,
            draft=None,
            rendered=None,
            failure=exc,
            source_report_digest=source_report_digest,
            patch_receipt=patch_receipt,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue-authority", action="store_true")
    parser.add_argument("--decision", default=DEFAULT_DECISION_REF)
    parser.add_argument("--preflight", default=DEFAULT_PREFLIGHT_REF)
    parser.add_argument("--authority", default=DEFAULT_AUTHORITY_REF)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--capture-root", default=DEFAULT_CAPTURE_ROOT_REF)
    parser.add_argument("--private-root", default=DEFAULT_PRIVATE_ROOT_REF)
    parser.add_argument("--public-result", default=DEFAULT_PUBLIC_RESULT_REF)
    args = parser.parse_args(argv)
    result = (
        issue_authority(
            decision_ref=args.decision,
            preflight_ref=args.preflight,
            authority_ref=args.authority,
            run_id=args.run_id,
            capture_root_ref=args.capture_root,
            private_root_ref=args.private_root,
            public_result_ref=args.public_result,
        )
        if args.issue_authority
        else run(_resolve(args.authority))
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if "failure" not in str(result.get("status") or "") else 2


if __name__ == "__main__":
    raise SystemExit(main())
