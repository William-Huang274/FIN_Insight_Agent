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
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.canonical_runtime import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import build_preflight  # noqa: E402
from sec_agent.providers import (  # noqa: E402
    ChatCompletionResult,
    ChatCompletionToolStepResult,
    ModelGatewayError,
    execute_chat_completion_exact_once,
    execute_chat_completion_tool_step_exact_once,
    load_chat_completion_profile,
)
from sec_agent.research.current_dynamic_writer import (  # noqa: E402
    CURRENT_DYNAMIC_WRITER_RUN_SCOPE,
    CurrentDynamicWriterError,
    compile_r10_protected_writer_messages,
    compile_r10_writer_evaluation,
    expected_current_dynamic_writer_budget,
    validate_r10_protected_writer_draft,
)
from sec_agent.research.multi_agent_report_authority import (  # noqa: E402
    MultiAgentReportAuthorityError,
    protected_report_draft_tool,
    render_protected_report,
)


DEFAULT_DECISION_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_scope_decision_v1_0.json"
)
DEFAULT_PREFLIGHT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_project_os_preflight_v1_0.json"
)
DEFAULT_AUTHORITY_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_live_authority_v1_0.json"
)
DEFAULT_PUBLIC_RESULT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_live_result_v1_0.json"
)
DEFAULT_RUN_ID = "FIN_0_1_3_S3_DELL_R10_PROTECTED_WRITER_LIVE_R11"
DEFAULT_CAPTURE_ROOT_REF = (
    ".codex_runtime/model_runs/fin_0_1_3_s3_dell_R10_protected_writer_live_r11"
)
DEFAULT_PRIVATE_ROOT_REF = (
    "data/workbench_private/fin_0_1_3_s3_current_dynamic_multi_agent/"
    "dell-R10-protected-writer-live-r11"
)
AUTHORITY_SCHEMA_VERSION = (
    "fin_ia_s3_current_dynamic_multi_agent_protected_writer_live_authority_v1_0"
)
PRIVATE_RESULT_SCHEMA_VERSION = (
    "fin_ia_s3_current_dynamic_multi_agent_protected_writer_full_result_v1_0"
)
PUBLIC_RESULT_SCHEMA_VERSION = (
    "fin_ia_s3_current_dynamic_multi_agent_protected_writer_public_result_v1_0"
)
_TOOL_NAME = "submit_protected_report_draft"


class CurrentDynamicWriterLiveError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        phase: str = "",
        provider_steps: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        self.code = code
        self.phase = phase
        self.provider_steps = [deepcopy(dict(row)) for row in provider_steps]
        super().__init__(code)


def _resolve(ref: str | Path) -> Path:
    path = Path(ref)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _relative(path: str | Path) -> str:
    return _resolve(path).relative_to(ROOT.resolve()).as_posix()


def _load(ref: str | Path) -> dict[str, Any]:
    value = json.loads(_resolve(ref).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_json_object_required", phase="binding"
        )
    return value


def _sha(ref: str | Path) -> str:
    return hashlib.sha256(_resolve(ref).read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write_new(ref: str | Path, value: Mapping[str, Any]) -> None:
    path = _resolve(ref)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_output_identity_consumed",
            phase="materialization",
        ) from exc


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_git_command_failed", phase="binding"
        )
    return completed.stdout.strip()


def _git_blob_sha256(*, commit: str, ref: str) -> str:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{ref}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_git_blob_missing", phase="binding"
        )
    return hashlib.sha256(completed.stdout).hexdigest()


def _clean_synced_head() -> str:
    head = _git("rev-parse", "HEAD").lower()
    upstream = _git("rev-parse", "@{upstream}").lower()
    status = _git("status", "--porcelain")
    if len(head) != 40 or head != upstream or status:
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_repository_not_clean_synced",
            phase="binding",
        )
    return head


def _binding(ref: str, *, digest_field: str = "") -> dict[str, Any]:
    row: dict[str, Any] = {"ref": ref, "sha256": _sha(ref)}
    if digest_field:
        value = _load(ref).get(digest_field)
        if not isinstance(value, str) or not value:
            raise CurrentDynamicWriterLiveError(
                "current_dynamic_writer_live_binding_digest_missing",
                phase="binding",
            )
        row.update({"digest_field": digest_field, "digest": value})
    return row


def _validate_binding(binding: Mapping[str, Any]) -> dict[str, Any]:
    ref = str(binding.get("ref") or "")
    if not ref or _sha(ref) != str(binding.get("sha256") or ""):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_binding_sha_drift", phase="binding"
        )
    value = _load(ref)
    field = str(binding.get("digest_field") or "")
    if field and value.get(field) != binding.get("digest"):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_binding_digest_drift", phase="binding"
        )
    return value


def _authority_body(authority: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in authority.items()
        if key != "authority_digest"
    }


def issue_authority(
    *,
    decision_ref: str = DEFAULT_DECISION_REF,
    preflight_ref: str = DEFAULT_PREFLIGHT_REF,
    authority_ref: str = DEFAULT_AUTHORITY_REF,
    public_result_ref: str = DEFAULT_PUBLIC_RESULT_REF,
    run_id: str = DEFAULT_RUN_ID,
    capture_root_ref: str = DEFAULT_CAPTURE_ROOT_REF,
    private_root_ref: str = DEFAULT_PRIVATE_ROOT_REF,
) -> dict[str, Any]:
    head = _clean_synced_head()
    output_paths = {
        "project_os_preflight_ref": preflight_ref,
        "live_authority_ref": authority_ref,
        "public_result_ref": public_result_ref,
        "private_full_result_ref": private_root_ref.rstrip("/") + "/full_result.json",
        "capture_root_ref": capture_root_ref,
    }
    for name, ref in output_paths.items():
        path = _resolve(ref)
        try:
            path.relative_to(ROOT.resolve())
        except ValueError as exc:
            raise CurrentDynamicWriterLiveError(
                "current_dynamic_writer_live_output_outside_repository:" + name,
                phase="binding",
            ) from exc
        if path.exists():
            raise CurrentDynamicWriterLiveError(
                "current_dynamic_writer_live_fresh_output_required:" + name,
                phase="binding",
            )
    decision = _load(decision_ref)
    if (
        decision.get("run_scope_id") != CURRENT_DYNAMIC_WRITER_RUN_SCOPE
        or decision.get("execution_budget")
        != expected_current_dynamic_writer_budget()
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_decision_invalid", phase="binding"
        )
    preflight = build_preflight(
        root=ROOT,
        decision_ref=decision_ref,
        environment={"DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY", "")},
        check_repository=True,
    )
    _write_new(preflight_ref, preflight)
    result_paths = {
        "public_result_ref": public_result_ref,
        "private_full_result_ref": private_root_ref.rstrip("/") + "/full_result.json",
        "capture_root_ref": capture_root_ref,
    }
    body = {
        "schema_version": AUTHORITY_SCHEMA_VERSION,
        "status": "signed_exact_run_DELL_R10_protected_writer",
        "signed_at": _now(),
        "implementation_commit": head,
        "case_key": "DELL",
        "run_scope_id": CURRENT_DYNAMIC_WRITER_RUN_SCOPE,
        "run_id": run_id,
        "decision": _binding(decision_ref, digest_field="decision_digest"),
        "project_os_preflight": _binding(preflight_ref),
        "bound_inputs": deepcopy(decision["bound_inputs"]),
        "implementation_bindings": deepcopy(decision["implementation_bindings"]),
        "execution_budget": deepcopy(decision["execution_budget"]),
        "token_budget_basis": deepcopy(decision["token_budget_basis"]),
        "output_contract": result_paths,
        "authority_boundary": {
            "one_writer_analysis_call": True,
            "maximum_two_writer_submission_attempts": True,
            "transport_retries": 0,
            "upstream_agent_calls": 0,
            "new_S1_S2_retrieval_source_or_candidate_calls": 0,
            "writer_result_requires_independent_post_run_assessment": True,
            "S3_product_publication_and_release_authorized": False,
        },
    }
    authority = {**body, "authority_digest": canonical_digest(body)}
    _write_new(authority_ref, authority)
    return authority


def _validate_authority(
    authority: Mapping[str, Any], *, authority_ref: str
) -> dict[str, Any]:
    expected_boundary = {
        "one_writer_analysis_call": True,
        "maximum_two_writer_submission_attempts": True,
        "transport_retries": 0,
        "upstream_agent_calls": 0,
        "new_S1_S2_retrieval_source_or_candidate_calls": 0,
        "writer_result_requires_independent_post_run_assessment": True,
        "S3_product_publication_and_release_authorized": False,
    }
    expected_keys = {
        "schema_version",
        "status",
        "signed_at",
        "implementation_commit",
        "case_key",
        "run_scope_id",
        "run_id",
        "decision",
        "project_os_preflight",
        "bound_inputs",
        "implementation_bindings",
        "execution_budget",
        "token_budget_basis",
        "output_contract",
        "authority_boundary",
        "authority_digest",
    }
    if not (
        set(authority) == expected_keys
        and
        authority.get("schema_version") == AUTHORITY_SCHEMA_VERSION
        and authority.get("status") == "signed_exact_run_DELL_R10_protected_writer"
        and authority.get("case_key") == "DELL"
        and authority.get("run_scope_id") == CURRENT_DYNAMIC_WRITER_RUN_SCOPE
        and authority.get("execution_budget")
        == expected_current_dynamic_writer_budget()
        and authority.get("authority_boundary") == expected_boundary
        and authority.get("authority_digest")
        == canonical_digest(_authority_body(authority))
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_authority_invalid", phase="binding"
        )
    head = _clean_synced_head()
    implementation_commit = str(authority.get("implementation_commit") or "").lower()
    authority_rel = _relative(authority_ref)
    preflight_ref = str((authority.get("project_os_preflight") or {}).get("ref") or "")
    if not (
        len(implementation_commit) == 40
        and _git("merge-base", implementation_commit, head).lower()
        == implementation_commit
        and _git("rev-list", "--count", f"{implementation_commit}..{head}") == "1"
        and set(_git("diff", "--name-only", implementation_commit, head).splitlines())
        == {preflight_ref, authority_rel}
        and _git_blob_sha256(commit=head, ref=authority_rel) == _sha(authority_ref)
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_authority_commit_chain_invalid",
            phase="binding",
        )
    decision = _validate_binding(authority["decision"])
    preflight = _validate_binding(authority["project_os_preflight"])
    if not (
        preflight.get("status") == "pass_current_decision_bound_preflight"
        and preflight.get("decision_ref") == authority["decision"]["ref"]
        and preflight.get("decision_sha256") == authority["decision"]["sha256"]
        and preflight.get("run_scope_id") == CURRENT_DYNAMIC_WRITER_RUN_SCOPE
        and (preflight.get("repository") or {}).get("head")
        == implementation_commit
        and (preflight.get("repository") or {}).get("clean") is True
        and (preflight.get("repository") or {}).get("synced") is True
        and preflight.get("model_calls") == 0
        and preflight.get("provider_calls") == 0
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_preflight_invalid", phase="binding"
        )
    if not (
        authority.get("bound_inputs") == decision.get("bound_inputs")
        and authority.get("implementation_bindings")
        == decision.get("implementation_bindings")
        and authority.get("execution_budget") == decision.get("execution_budget")
        and authority.get("token_budget_basis") == decision.get("token_budget_basis")
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_decision_projection_drift", phase="binding"
        )
    for binding in (authority.get("bound_inputs") or {}).values():
        _validate_binding(binding)
    for binding in authority.get("implementation_bindings") or ():
        _validate_binding(binding)
        ref = str(binding.get("ref") or "")
        if _git_blob_sha256(commit=implementation_commit, ref=ref) != str(
            binding.get("sha256") or ""
        ):
            raise CurrentDynamicWriterLiveError(
                "current_dynamic_writer_live_implementation_blob_drift",
                phase="binding",
            )
    output = deepcopy(dict(authority.get("output_contract") or {}))
    if set(output) != {
        "public_result_ref",
        "private_full_result_ref",
        "capture_root_ref",
    } or len(set(str(value) for value in output.values())) != 3:
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_output_contract_invalid", phase="binding"
        )
    for ref in output.values():
        _relative(str(ref))
        if _resolve(str(ref)).exists():
            raise CurrentDynamicWriterLiveError(
                "current_dynamic_writer_live_output_identity_consumed",
                phase="binding",
            )
    return decision


def _analysis_messages(messages: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    output = [deepcopy(dict(row)) for row in messages]
    output[0]["content"] = (
        output[0]["content"]
        + " Do not submit the tool yet. Produce a content-complete planning memo "
        "covering thesis, section topology, exact claim and authority selections, "
        "counterthesis, gaps, what-would-change, and every protection check."
    )
    output[1]["content"] += (
        "\nPlanning phase only: return the complete Writer plan as visible prose; "
        "the following strict submission call will render the report contract."
    )
    return output


def _submission_messages(
    messages: Sequence[Mapping[str, str]], analysis: str
) -> list[dict[str, Any]]:
    return [
        *[deepcopy(dict(row)) for row in messages],
        {"role": "assistant", "content": analysis},
        {
            "role": "user",
            "content": (
                "Using the completed plan, now submit exactly one full protected "
                "report draft tool call. Recheck every R10 protection and reference "
                "scope before submission. Do not return prose outside the tool call."
            ),
        },
    ]


def _tool_payload(step: ChatCompletionToolStepResult) -> tuple[str, dict[str, Any]]:
    if step.finish_reason == "length":
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_submission_length",
            phase="submission",
            provider_steps=[step.as_dict()],
        )
    calls = list(step.tool_calls)
    if len(calls) != 1:
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_tool_call_count_invalid",
            phase="submission",
            provider_steps=[step.as_dict()],
        )
    call = calls[0]
    function = call.get("function") or {}
    call_id = str(call.get("id") or "")
    if not (
        call_id
        and isinstance(function, Mapping)
        and function.get("name") == _TOOL_NAME
        and isinstance(function.get("arguments"), str)
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_tool_call_identity_invalid",
            phase="submission",
            provider_steps=[step.as_dict()],
        )
    try:
        payload = json.loads(str(function["arguments"]))
    except json.JSONDecodeError as exc:
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_tool_arguments_json_invalid",
            phase="submission",
            provider_steps=[step.as_dict()],
        ) from exc
    if not isinstance(payload, dict):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_tool_arguments_object_required",
            phase="submission",
            provider_steps=[step.as_dict()],
        )
    return call_id, payload


def _capture_receipt(step: Mapping[str, Any]) -> dict[str, Any]:
    request_ref = _relative(str(step["request_capture_ref"]))
    response_ref = _relative(str(step["response_capture_ref"]))
    return {
        "request_ref": request_ref,
        "request_sha256": _sha(request_ref),
        "request_digest": step["request_digest"],
        "response_ref": response_ref,
        "response_sha256": _sha(response_ref),
        "response_digest": step["response_digest"],
        "finish_reason": step["finish_reason"],
        "usage": deepcopy(dict(step.get("usage") or {})),
    }


def _aggregate_step_usage(
    provider_steps: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    prompt_tokens = 0
    completion_tokens = 0
    reasoning_tokens = 0
    for row in provider_steps:
        usage = row.get("usage") or {}
        details = usage.get("completion_tokens_details") or {}
        prompt_tokens += int(usage.get("prompt_tokens") or 0)
        completion_tokens += int(usage.get("completion_tokens") or 0)
        reasoning_tokens += int(
            usage.get("reasoning_tokens")
            or details.get("reasoning_tokens")
            or 0
        )
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
    }


def _capture_manifest_from_root(capture_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not capture_root.is_dir():
        return rows
    for request_path in sorted(capture_root.rglob("model_visible_request.json")):
        request = _load(request_path)
        response_path = request_path.with_name("provider_response.json")
        response = _load(response_path) if response_path.is_file() else {}
        response_body = response.get("response_body")
        choices = (
            response_body.get("choices")
            if isinstance(response_body, Mapping)
            else None
        )
        choice = (
            choices[0]
            if isinstance(choices, list)
            and len(choices) == 1
            and isinstance(choices[0], Mapping)
            else {}
        )
        usage = (
            response_body.get("usage")
            if isinstance(response_body, Mapping)
            and isinstance(response_body.get("usage"), Mapping)
            else {}
        )
        details = (
            usage.get("completion_tokens_details")
            if isinstance(usage.get("completion_tokens_details"), Mapping)
            else {}
        )
        row = {
            "attempt_id": str(
                request.get("attempt_id") or request_path.parent.name
            ),
            "request_ref": _relative(request_path),
            "request_sha256": _sha(request_path),
            "request_digest": str(request.get("request_digest") or ""),
            "response_present": response_path.is_file(),
            "response_ref": (
                _relative(response_path) if response_path.is_file() else ""
            ),
            "response_sha256": (
                _sha(response_path) if response_path.is_file() else ""
            ),
            "response_digest": str(response.get("response_digest") or ""),
            "status_code": int(response.get("status_code") or 0),
            "finish_reason": str(choice.get("finish_reason") or ""),
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "reasoning_tokens": int(details.get("reasoning_tokens") or 0),
        }
        rows.append(row)
    return rows


def _failure_identity(
    exc: Exception,
) -> tuple[str, str, list[dict[str, Any]], str]:
    if isinstance(exc, CurrentDynamicWriterLiveError):
        return (
            exc.phase or "local_execution",
            exc.code,
            deepcopy(exc.provider_steps),
            "",
        )
    if isinstance(exc, ModelGatewayError):
        capture_ref = ""
        if exc.capture_ref:
            try:
                capture_ref = _relative(exc.capture_ref)
            except ValueError:
                capture_ref = "capture_ref_outside_repository"
        return "provider_transport_or_response", exc.code, [], capture_ref
    if isinstance(exc, (CurrentDynamicWriterError, MultiAgentReportAuthorityError)):
        return (
            "local_contract_or_semantic_validation",
            str(getattr(exc, "code", type(exc).__name__)),
            [],
            "",
        )
    return "unexpected_project_failure", type(exc).__name__, [], ""


def _materialize_terminal_failure(
    *,
    authority: Mapping[str, Any],
    authority_ref: str,
    decision: Mapping[str, Any],
    exc: Exception,
) -> dict[str, Any]:
    phase, code, provider_steps, exception_capture_ref = _failure_identity(exc)
    output = authority["output_contract"]
    capture_root = _resolve(output["capture_root_ref"])
    captures = _capture_manifest_from_root(capture_root)
    usage = {
        "prompt_tokens": sum(int(row["prompt_tokens"]) for row in captures),
        "completion_tokens": sum(
            int(row["completion_tokens"]) for row in captures
        ),
        "reasoning_tokens": sum(int(row["reasoning_tokens"]) for row in captures),
    }
    attempted = len(captures)
    http_200 = sum(row["status_code"] == 200 for row in captures)
    analysis_calls = sum(
        str(row["attempt_id"]).endswith("writer-analysis") for row in captures
    )
    submission_calls = sum(
        "writer-submission-" in str(row["attempt_id"]) for row in captures
    )
    recorded_at = _now()
    failure = {
        "phase": phase,
        "code": code,
        "exception_capture_ref": exception_capture_ref,
        "provider_failure": isinstance(exc, ModelGatewayError),
        "failure_preserved_without_retry": True,
    }
    execution = {
        "new_provider_calls_attempted": attempted,
        "new_provider_http_200": http_200,
        "maximum_new_provider_calls": expected_current_dynamic_writer_budget()[
            "maximum_new_model_calls"
        ],
        "writer_analysis_calls": analysis_calls,
        "writer_submission_attempts": submission_calls,
        "retries": 0,
        "fallbacks": 0,
        "upstream_agent_calls": 0,
        "new_S1_S2_requests": 0,
        "new_retrieval_rounds": 0,
        "external_source_network_calls": 0,
        "candidate_promotions": 0,
    }
    acceptance = {
        "protected_contract_pass": False,
        "writer_protection_contract_pass": False,
        "independent_post_writer_L1_L2_pass": False,
        "eight_dimension_quality_pass": False,
        "S3_pass": False,
        "product_acceptance": False,
        "publication": False,
        "release_ready": False,
    }
    known_boundary = (
        "This exact R11 Writer authority ended in a preserved terminal failure. "
        "No retry, fallback, upstream Agent, S1/S2, retrieval, source-network, "
        "promotion, product acceptance, publication or release action followed. "
        "Any successor requires a root-cause audit, a new zero-call proof and a "
        "fresh authority with a new output identity."
    )
    private_body = {
        "schema_version": PRIVATE_RESULT_SCHEMA_VERSION,
        "status": "terminal_protected_writer_failure_preserved",
        "recorded_at": recorded_at,
        "case_key": "DELL",
        "run_id": authority["run_id"],
        "implementation_commit": authority["implementation_commit"],
        "authority_ref": authority_ref,
        "authority_sha256": _sha(authority_ref),
        "authority_digest": authority["authority_digest"],
        "decision_digest": decision["decision_digest"],
        "failure": failure,
        "provider_steps_returned_before_failure": provider_steps,
        "capture_manifest": captures,
        "usage": usage,
        "execution": execution,
        "acceptance": acceptance,
        "known_boundary": known_boundary,
    }
    private = {
        **private_body,
        "full_result_digest": canonical_digest(private_body),
    }
    private_ref = str(output["private_full_result_ref"])
    _write_new(private_ref, private)
    public_body = {
        "schema_version": PUBLIC_RESULT_SCHEMA_VERSION,
        "status": "terminal_protected_writer_failure_preserved",
        "recorded_at": recorded_at,
        "case_key": "DELL",
        "run_id": authority["run_id"],
        "implementation_commit": authority["implementation_commit"],
        "authority_ref": authority_ref,
        "authority_sha256": _sha(authority_ref),
        "authority_digest": authority["authority_digest"],
        "private_full_result_ref": private_ref,
        "private_full_result_sha256": _sha(private_ref),
        "private_full_result_digest": private["full_result_digest"],
        "failure": failure,
        "capture_manifest": captures,
        "usage": usage,
        "execution": execution,
        "acceptance": acceptance,
        "known_boundary": known_boundary,
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(str(output["public_result_ref"]), public)
    return public


def _run_live_once(
    *,
    authority_ref: str,
    authority: Mapping[str, Any],
    decision: Mapping[str, Any],
    analysis_executor: Callable[..., ChatCompletionResult] = (
        execute_chat_completion_exact_once
    ),
    submission_executor: Callable[..., ChatCompletionToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> dict[str, Any]:
    bound = authority["bound_inputs"]
    r10_private = _validate_binding(bound["R10_private_full_result"])
    assessment = _validate_binding(bound["R10_assessment"])
    catalog = _validate_binding(bound["writer_authority_catalog"])
    protection = _validate_binding(bound["writer_protection_contract"])
    analysis_profile_raw = _validate_binding(bound["analysis_profile"])
    submission_profile_raw = _validate_binding(bound["submission_profile"])
    workpapers = r10_private["final_workpapers"]
    if catalog.get("workpaper_digests") != sorted(
        str(row["workpaper_digest"]) for row in workpapers
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_workpaper_catalog_drift", phase="binding"
        )
    lead = r10_private["lead_bundle"]["rounds"][0]["decision"]
    writer_gate = compile_r10_writer_evaluation(
        assessment=assessment,
        lead_decision=lead,
        protection=protection,
    )
    base_messages = compile_r10_protected_writer_messages(
        workpapers=workpapers,
        writer_gate=writer_gate,
        authority_catalog=catalog,
        protection=protection,
    )
    tool = protected_report_draft_tool(authority_catalog=catalog)
    analysis_profile = load_chat_completion_profile(analysis_profile_raw)
    submission_profile = load_chat_completion_profile(submission_profile_raw)
    run_id = str(authority["run_id"])
    capture_root = _resolve(authority["output_contract"]["capture_root_ref"])
    provider_steps: list[dict[str, Any]] = []
    analysis_step = analysis_executor(
        profile=analysis_profile,
        messages=_analysis_messages(base_messages),
        capture_root=capture_root,
        run_id=run_id,
        attempt_id="writer-analysis",
    )
    provider_steps.append(analysis_step.as_dict())
    if analysis_step.finish_reason == "length" or not analysis_step.content.strip():
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_analysis_incomplete",
            phase="analysis",
            provider_steps=provider_steps,
        )
    messages = _submission_messages(base_messages, analysis_step.content)
    trusted: dict[str, Any] | None = None
    submission_failures: list[dict[str, Any]] = []
    for attempt in (1, 2):
        step = submission_executor(
            profile=submission_profile,
            messages=messages,
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=f"writer-submission-{attempt}",
        )
        provider_steps.append(step.as_dict())
        call_id, payload = _tool_payload(step)
        try:
            trusted = validate_r10_protected_writer_draft(
                payload,
                authority_catalog=catalog,
                protection=protection,
            )
            break
        except (CurrentDynamicWriterError, MultiAgentReportAuthorityError) as exc:
            code = getattr(exc, "code", str(exc))
            details = getattr(exc, "details", {})
            failure = {
                "attempt": attempt,
                "code": code,
                "details": deepcopy(dict(details or {})),
            }
            submission_failures.append(failure)
            if attempt == 2:
                raise CurrentDynamicWriterLiveError(
                    "current_dynamic_writer_live_second_contract_rejection:" + code,
                    phase="submission",
                    provider_steps=provider_steps,
                ) from exc
            messages.extend(
                [
                    step.continuation_assistant_message(),
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(
                            {
                                "status": "rejected",
                                "error_code": code,
                                "details": details,
                                "instruction": (
                                    "Resubmit the complete report once, correcting all "
                                    "listed fields without changing evidence authority."
                                ),
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    },
                ]
            )
    if trusted is None:
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_submission_missing", phase="submission"
        )
    rendered = render_protected_report(trusted, authority_catalog=catalog)
    captures = [_capture_receipt(row) for row in provider_steps]
    usage = _aggregate_step_usage(provider_steps)
    private_body = {
        "schema_version": PRIVATE_RESULT_SCHEMA_VERSION,
        "status": "completed_protected_writer_report_assessment_pending",
        "recorded_at": _now(),
        "case_key": "DELL",
        "run_id": run_id,
        "implementation_commit": authority["implementation_commit"],
        "authority_ref": authority_ref,
        "authority_sha256": _sha(authority_ref),
        "authority_digest": authority["authority_digest"],
        "decision_digest": decision["decision_digest"],
        "writer_gate": writer_gate,
        "writer_analysis": analysis_step.content,
        "protected_draft": trusted,
        "rendered_report": rendered,
        "submission_failures": submission_failures,
        "provider_steps": provider_steps,
        "capture_manifest": captures,
        "usage": usage,
        "execution": {
            "new_provider_calls_attempted": len(provider_steps),
            "new_provider_http_200": len(provider_steps),
            "maximum_new_provider_calls": expected_current_dynamic_writer_budget()[
                "maximum_new_model_calls"
            ],
            "writer_analysis_calls": 1,
            "writer_submission_attempts": len(provider_steps) - 1,
            "retries": 0,
            "fallbacks": 0,
            "upstream_agent_calls": 0,
            "new_S1_S2_requests": 0,
            "new_retrieval_rounds": 0,
            "external_source_network_calls": 0,
            "candidate_promotions": 0,
        },
        "acceptance": {
            "protected_contract_pass": True,
            "writer_protection_contract_pass": True,
            "independent_post_writer_L1_L2_pass": False,
            "eight_dimension_quality_pass": False,
            "S3_pass": False,
            "product_acceptance": False,
            "publication": False,
            "release_ready": False,
        },
        "known_boundary": (
            "A rendered protected report candidate exists, but independent L1/L2, "
            "eight-dimension quality, S3, product, publication and release acceptance "
            "remain false until separate assessment."
        ),
    }
    private = {
        **private_body,
        "full_result_digest": canonical_digest(private_body),
    }
    private_ref = authority["output_contract"]["private_full_result_ref"]
    _write_new(private_ref, private)
    public_body = {
        "schema_version": PUBLIC_RESULT_SCHEMA_VERSION,
        "status": "completed_protected_writer_report_assessment_pending",
        "recorded_at": private["recorded_at"],
        "case_key": "DELL",
        "run_id": run_id,
        "implementation_commit": authority["implementation_commit"],
        "authority_ref": authority_ref,
        "authority_sha256": _sha(authority_ref),
        "authority_digest": authority["authority_digest"],
        "private_full_result_ref": private_ref,
        "private_full_result_sha256": _sha(private_ref),
        "private_full_result_digest": private["full_result_digest"],
        "draft_digest": trusted["draft_digest"],
        "rendered_report_digest": rendered["rendered_report_digest"],
        "capture_manifest": captures,
        "usage": usage,
        "execution": deepcopy(private["execution"]),
        "acceptance": deepcopy(private["acceptance"]),
        "known_boundary": private["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    public_ref = authority["output_contract"]["public_result_ref"]
    _write_new(public_ref, public)
    return public


def run_live(
    *,
    authority_ref: str = DEFAULT_AUTHORITY_REF,
    analysis_executor: Callable[..., ChatCompletionResult] = (
        execute_chat_completion_exact_once
    ),
    submission_executor: Callable[..., ChatCompletionToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> dict[str, Any]:
    authority = _load(authority_ref)
    decision = _validate_authority(authority, authority_ref=authority_ref)
    try:
        return _run_live_once(
            authority_ref=authority_ref,
            authority=authority,
            decision=decision,
            analysis_executor=analysis_executor,
            submission_executor=submission_executor,
        )
    except Exception as exc:
        output = authority["output_contract"]
        if any(
            _resolve(str(output[name])).exists()
            for name in ("public_result_ref", "private_full_result_ref")
        ):
            raise
        terminal = _materialize_terminal_failure(
            authority=authority,
            authority_ref=authority_ref,
            decision=decision,
            exc=exc,
        )
        preserved = CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_terminal_failure_preserved:"
            + str((terminal.get("failure") or {}).get("code") or "unknown"),
            phase="terminal_materialization",
        )
        preserved.terminal_public_result = terminal
        raise preserved from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    issue = sub.add_parser("issue-authority")
    issue.add_argument("--decision-ref", default=DEFAULT_DECISION_REF)
    issue.add_argument("--preflight-ref", default=DEFAULT_PREFLIGHT_REF)
    issue.add_argument("--authority-ref", default=DEFAULT_AUTHORITY_REF)
    live = sub.add_parser("live")
    live.add_argument("--authority-ref", default=DEFAULT_AUTHORITY_REF)
    args = parser.parse_args()
    if args.command == "issue-authority":
        result = issue_authority(
            decision_ref=args.decision_ref,
            preflight_ref=args.preflight_ref,
            authority_ref=args.authority_ref,
        )
    else:
        result = run_live(authority_ref=args.authority_ref)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
