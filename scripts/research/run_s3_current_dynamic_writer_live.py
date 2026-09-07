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
    CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_DECISION_SCHEMA_VERSION,
    CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_DECISION_STATUS,
    CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_RUN_SCOPE,
    CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_ZERO_CALL_SCHEMA_VERSION,
    CURRENT_DYNAMIC_WRITER_ZERO_CALL_SCHEMA_VERSION,
    CurrentDynamicWriterError,
    compile_r10_protected_writer_messages,
    compile_r10_writer_evaluation,
    expected_current_dynamic_writer_budget,
    expected_current_dynamic_writer_submission_successor_budget,
    find_r10_protected_writer_surface_findings,
    validate_r10_protected_writer_draft,
)
from sec_agent.research.multi_agent_report_authority import (  # noqa: E402
    MultiAgentReportAuthorityError,
    protected_report_draft_tool,
    render_protected_report,
)


DEFAULT_DECISION_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_scope_decision_v1_2.json"
)
DEFAULT_PREFLIGHT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_project_os_preflight_v1_2.json"
)
DEFAULT_AUTHORITY_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_live_authority_v1_2.json"
)
DEFAULT_PUBLIC_RESULT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_live_result_v1_2.json"
)
DEFAULT_RUN_ID = "FIN_0_1_3_S3_DELL_R10_PROTECTED_WRITER_LIVE_R13"
DEFAULT_CAPTURE_ROOT_REF = (
    ".codex_runtime/model_runs/fin_0_1_3_s3_dell_R10_protected_writer_live_r13"
)
DEFAULT_PRIVATE_ROOT_REF = (
    "data/workbench_private/fin_0_1_3_s3_current_dynamic_multi_agent/"
    "dell-R10-protected-writer-live-r13"
)
SUBMISSION_SUCCESSOR_DECISION_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_submission_successor_scope_decision_v1_0.json"
)
SUBMISSION_SUCCESSOR_ZERO_CALL_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_submission_successor_zero_call_result_v1_0.json"
)
SUBMISSION_SUCCESSOR_PREFLIGHT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_submission_successor_project_os_preflight_v1_0.json"
)
SUBMISSION_SUCCESSOR_AUTHORITY_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_submission_successor_live_authority_v1_0.json"
)
SUBMISSION_SUCCESSOR_PUBLIC_RESULT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_submission_successor_live_result_v1_0.json"
)
SUBMISSION_SUCCESSOR_RUN_ID = (
    "FIN_0_1_3_S3_DELL_R10_PROTECTED_WRITER_SUBMISSION_SUCCESSOR_LIVE_R14"
)
SUBMISSION_SUCCESSOR_CAPTURE_ROOT_REF = (
    ".codex_runtime/model_runs/fin_0_1_3_s3_dell_R10_"
    "protected_writer_submission_successor_live_r14"
)
SUBMISSION_SUCCESSOR_PRIVATE_ROOT_REF = (
    "data/workbench_private/fin_0_1_3_s3_current_dynamic_multi_agent/"
    "dell-R10-protected-writer-submission-successor-live-r14"
)
SUBMISSION_SUCCESSOR_AUTHORITY_SCHEMA_VERSION = (
    "fin_ia_s3_current_dynamic_multi_agent_protected_writer_"
    "submission_successor_live_authority_v1_0"
)
R13_AUTHORITY_REF = DEFAULT_AUTHORITY_REF
R13_PUBLIC_RESULT_REF = DEFAULT_PUBLIC_RESULT_REF
R13_PRIVATE_RESULT_REF = DEFAULT_PRIVATE_ROOT_REF + "/full_result.json"
R13_ANALYSIS_REQUEST_REF = (
    DEFAULT_CAPTURE_ROOT_REF
    + "/"
    + DEFAULT_RUN_ID
    + "/writer-analysis/model_visible_request.json"
)
R13_ANALYSIS_RESPONSE_REF = (
    DEFAULT_CAPTURE_ROOT_REF
    + "/"
    + DEFAULT_RUN_ID
    + "/writer-analysis/provider_response.json"
)
R13_SUBMISSION_REQUEST_REF = (
    DEFAULT_CAPTURE_ROOT_REF
    + "/"
    + DEFAULT_RUN_ID
    + "/writer-submission-1/model_visible_request.json"
)
R13_SUBMISSION_RESPONSE_REF = (
    DEFAULT_CAPTURE_ROOT_REF
    + "/"
    + DEFAULT_RUN_ID
    + "/writer-submission-1/provider_response.json"
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
_R13_EXPECTED_SURFACE_FINDINGS = [
    {
        "path": "sections[1].clauses[1].model_text",
        "matches": ["point", "two"],
    },
    {"path": "sections[2].clauses[2].model_text", "matches": ["point"]},
    {"path": "sections[3].clauses[1].model_text", "matches": ["three"]},
    {"path": "sections[4].clauses[3].model_text", "matches": ["two"]},
    {"path": "remaining_gaps[0].model_text", "matches": ["three"]},
]


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
    _validate_file_binding(binding)
    ref = str(binding.get("ref") or "")
    value = _load(ref)
    field = str(binding.get("digest_field") or "")
    if field and value.get(field) != binding.get("digest"):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_binding_digest_drift", phase="binding"
        )
    return value


def _validate_file_binding(binding: Mapping[str, Any]) -> None:
    """Validate an opaque file binding without assuming a JSON payload."""
    ref = str(binding.get("ref") or "")
    if not ref or _sha(ref) != str(binding.get("sha256") or ""):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_live_binding_sha_drift", phase="binding"
        )


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
        _validate_file_binding(binding)
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


def issue_submission_successor_authority(
    *,
    decision_ref: str = SUBMISSION_SUCCESSOR_DECISION_REF,
    preflight_ref: str = SUBMISSION_SUCCESSOR_PREFLIGHT_REF,
    authority_ref: str = SUBMISSION_SUCCESSOR_AUTHORITY_REF,
    public_result_ref: str = SUBMISSION_SUCCESSOR_PUBLIC_RESULT_REF,
    run_id: str = SUBMISSION_SUCCESSOR_RUN_ID,
    capture_root_ref: str = SUBMISSION_SUCCESSOR_CAPTURE_ROOT_REF,
    private_root_ref: str = SUBMISSION_SUCCESSOR_PRIVATE_ROOT_REF,
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
                "current_dynamic_writer_submission_successor_output_outside_"
                "repository:" + name,
                phase="binding",
            ) from exc
        if path.exists():
            raise CurrentDynamicWriterLiveError(
                "current_dynamic_writer_submission_successor_fresh_output_required:"
                + name,
                phase="binding",
            )
    decision = _load(decision_ref)
    if not (
        decision.get("schema_version")
        == CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_DECISION_SCHEMA_VERSION
        and decision.get("status")
        == CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_DECISION_STATUS
        and decision.get("run_scope_id")
        == CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_RUN_SCOPE
        and decision.get("execution_budget")
        == expected_current_dynamic_writer_submission_successor_budget()
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_decision_invalid",
            phase="binding",
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
    boundary = {
        "writer_analysis_calls": 0,
        "maximum_writer_submission_attempts": 1,
        "reuse_R13_visible_analysis_and_rejected_submission": True,
        "transport_retries": 0,
        "upstream_agent_calls": 0,
        "new_S1_S2_retrieval_source_or_candidate_calls": 0,
        "writer_result_requires_independent_post_run_assessment": True,
        "S3_product_publication_and_release_authorized": False,
    }
    body = {
        "schema_version": SUBMISSION_SUCCESSOR_AUTHORITY_SCHEMA_VERSION,
        "status": "signed_exact_run_DELL_R13_bound_writer_submission_successor",
        "signed_at": _now(),
        "implementation_commit": head,
        "case_key": "DELL",
        "run_scope_id": CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_RUN_SCOPE,
        "run_id": run_id,
        "decision": _binding(decision_ref, digest_field="decision_digest"),
        "project_os_preflight": _binding(preflight_ref),
        "bound_inputs": deepcopy(decision["bound_inputs"]),
        "implementation_bindings": deepcopy(decision["implementation_bindings"]),
        "execution_budget": deepcopy(decision["execution_budget"]),
        "token_budget_basis": deepcopy(decision["token_budget_basis"]),
        "output_contract": result_paths,
        "authority_boundary": boundary,
    }
    authority = {**body, "authority_digest": canonical_digest(body)}
    _write_new(authority_ref, authority)
    return authority


def _validate_submission_successor_authority(
    authority: Mapping[str, Any], *, authority_ref: str
) -> dict[str, Any]:
    expected_boundary = {
        "writer_analysis_calls": 0,
        "maximum_writer_submission_attempts": 1,
        "reuse_R13_visible_analysis_and_rejected_submission": True,
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
        and authority.get("schema_version")
        == SUBMISSION_SUCCESSOR_AUTHORITY_SCHEMA_VERSION
        and authority.get("status")
        == "signed_exact_run_DELL_R13_bound_writer_submission_successor"
        and authority.get("case_key") == "DELL"
        and authority.get("run_scope_id")
        == CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_RUN_SCOPE
        and authority.get("execution_budget")
        == expected_current_dynamic_writer_submission_successor_budget()
        and authority.get("authority_boundary") == expected_boundary
        and authority.get("authority_digest")
        == canonical_digest(_authority_body(authority))
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_authority_invalid",
            phase="binding",
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
            "current_dynamic_writer_submission_successor_authority_commit_chain_invalid",
            phase="binding",
        )
    decision = _validate_binding(authority["decision"])
    preflight = _validate_binding(authority["project_os_preflight"])
    if not (
        preflight.get("status") == "pass_current_decision_bound_preflight"
        and preflight.get("decision_ref") == authority["decision"]["ref"]
        and preflight.get("decision_sha256") == authority["decision"]["sha256"]
        and preflight.get("run_scope_id")
        == CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_RUN_SCOPE
        and (preflight.get("repository") or {}).get("head")
        == implementation_commit
        and (preflight.get("repository") or {}).get("clean") is True
        and (preflight.get("repository") or {}).get("synced") is True
        and preflight.get("model_calls") == 0
        and preflight.get("provider_calls") == 0
        and authority.get("bound_inputs") == decision.get("bound_inputs")
        and authority.get("implementation_bindings")
        == decision.get("implementation_bindings")
        and authority.get("execution_budget") == decision.get("execution_budget")
        and authority.get("token_budget_basis") == decision.get("token_budget_basis")
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_projection_drift",
            phase="binding",
        )
    for binding in (authority.get("bound_inputs") or {}).values():
        _validate_binding(binding)
    for binding in authority.get("implementation_bindings") or ():
        _validate_file_binding(binding)
        ref = str(binding.get("ref") or "")
        if _git_blob_sha256(commit=implementation_commit, ref=ref) != str(
            binding.get("sha256") or ""
        ):
            raise CurrentDynamicWriterLiveError(
                "current_dynamic_writer_submission_successor_implementation_blob_drift",
                phase="binding",
            )
    output = deepcopy(dict(authority.get("output_contract") or {}))
    if set(output) != {
        "public_result_ref",
        "private_full_result_ref",
        "capture_root_ref",
    } or len(set(str(value) for value in output.values())) != 3:
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_output_contract_invalid",
            phase="binding",
        )
    for ref in output.values():
        _relative(str(ref))
        if _resolve(str(ref)).exists():
            raise CurrentDynamicWriterLiveError(
                "current_dynamic_writer_submission_successor_output_identity_consumed",
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


def _submission_successor_source_bindings() -> dict[str, dict[str, Any]]:
    authority = _load(R13_AUTHORITY_REF)
    r13_bound = authority.get("bound_inputs") or {}
    inherited_names = (
        "R10_private_full_result",
        "R10_assessment",
        "writer_authority_catalog",
        "writer_protection_contract",
        "submission_profile",
    )
    if not all(isinstance(r13_bound.get(name), Mapping) for name in inherited_names):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_R13_inputs_missing",
            phase="zero_call",
        )
    return {
        "R13_authority": _binding(
            R13_AUTHORITY_REF, digest_field="authority_digest"
        ),
        "R13_public_result": _binding(
            R13_PUBLIC_RESULT_REF, digest_field="result_digest"
        ),
        "R13_private_full_result": _binding(
            R13_PRIVATE_RESULT_REF, digest_field="full_result_digest"
        ),
        "R13_analysis_request": _binding(
            R13_ANALYSIS_REQUEST_REF, digest_field="request_digest"
        ),
        "R13_analysis_response": _binding(
            R13_ANALYSIS_RESPONSE_REF, digest_field="response_digest"
        ),
        "R13_submission_request": _binding(
            R13_SUBMISSION_REQUEST_REF, digest_field="request_digest"
        ),
        "R13_submission_response": _binding(
            R13_SUBMISSION_RESPONSE_REF, digest_field="response_digest"
        ),
        **{
            name: deepcopy(dict(r13_bound[name]))
            for name in inherited_names
        },
    }


def _serialized_json_sha256(value: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        value, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_submission_successor_zero_call() -> dict[str, Any]:
    source = _submission_successor_source_bindings()
    values = {name: _validate_binding(binding) for name, binding in source.items()}
    authority = values["R13_authority"]
    public = values["R13_public_result"]
    private = values["R13_private_full_result"]
    analysis_request = values["R13_analysis_request"]
    analysis_response = values["R13_analysis_response"]
    submission_request = values["R13_submission_request"]
    submission_response = values["R13_submission_response"]
    authority_output = authority.get("output_contract") or {}
    public_manifest = public.get("capture_manifest") or []
    private_manifest = private.get("capture_manifest") or []

    def capture_matches(
        row: Mapping[str, Any], request_name: str, response_name: str
    ) -> bool:
        request_binding = source[request_name]
        response_binding = source[response_name]
        return (
            row.get("request_ref") == request_binding["ref"]
            and row.get("request_sha256") == request_binding["sha256"]
            and row.get("request_digest") == request_binding["digest"]
            and row.get("response_ref") == response_binding["ref"]
            and row.get("response_sha256") == response_binding["sha256"]
            and row.get("response_digest") == response_binding["digest"]
            and row.get("response_present") is True
            and row.get("status_code") == 200
        )

    analysis_choices = (analysis_response.get("response_body") or {}).get(
        "choices"
    ) or []
    submission_choices = (submission_response.get("response_body") or {}).get(
        "choices"
    ) or []
    if len(analysis_choices) != 1 or len(submission_choices) != 1:
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_capture_choice_invalid",
            phase="zero_call",
        )
    analysis_choice = analysis_choices[0]
    analysis_message = analysis_choice.get("message") or {}
    analysis_content = str(analysis_message.get("content") or "")
    submission_choice = submission_choices[0]
    rejected_message = submission_choice.get("message") or {}
    calls = rejected_message.get("tool_calls") or []
    if not (
        len(calls) == 1
        and isinstance((calls[0].get("function") or {}).get("arguments"), str)
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_rejected_call_invalid",
            phase="zero_call",
        )
    raw_arguments = str(calls[0]["function"]["arguments"])
    try:
        json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        json_error = exc
    else:
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_rejected_JSON_now_valid",
            phase="zero_call",
        )
    diagnostic_payload = json.loads(
        raw_arguments[: json_error.pos] + raw_arguments[json_error.pos + 1 :]
    )
    surface_findings = find_r10_protected_writer_surface_findings(
        diagnostic_payload
    )

    r10_private = values["R10_private_full_result"]
    assessment = values["R10_assessment"]
    catalog = values["writer_authority_catalog"]
    protection = values["writer_protection_contract"]
    lead = r10_private["lead_bundle"]["rounds"][0]["decision"]
    writer_gate = compile_r10_writer_evaluation(
        assessment=assessment,
        lead_decision=lead,
        protection=protection,
    )
    base_messages = compile_r10_protected_writer_messages(
        workpapers=r10_private["final_workpapers"],
        writer_gate=writer_gate,
        authority_catalog=catalog,
        protection=protection,
    )
    analysis_messages = _analysis_messages(base_messages)
    initial_submission_messages = _submission_messages(
        base_messages, analysis_content
    )
    tool = protected_report_draft_tool(authority_catalog=catalog)
    profile = values["submission_profile"]
    prior_zero_binding = (authority.get("bound_inputs") or {}).get(
        "zero_call_result"
    )
    if not isinstance(prior_zero_binding, Mapping):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_prior_zero_missing",
            phase="zero_call",
        )
    prior_zero = _validate_binding(prior_zero_binding)
    try:
        validate_r10_protected_writer_draft(
            diagnostic_payload,
            authority_catalog=catalog,
            protection=protection,
        )
    except CurrentDynamicWriterError as exc:
        diagnostic_rejection_code = exc.code
    else:
        diagnostic_rejection_code = ""

    feedback = {
        "status": "rejected",
        "error_code": (
            "current_dynamic_writer_live_tool_arguments_json_invalid_and_"
            "protected_surface_forbidden"
        ),
        "details": {
            "json_error_message": json_error.msg,
            "json_error_position": json_error.pos,
            "argument_characters": len(raw_arguments),
            "extra_closing_bracket_at_error": (
                raw_arguments[json_error.pos] == "]"
            ),
            "diagnostic_removed_character": raw_arguments[json_error.pos],
            "diagnostic_payload_promotable": False,
            "protected_surface_findings": deepcopy(surface_findings),
            "protected_surface_paths": [
                row["path"] for row in surface_findings
            ],
            "authority_expansion_allowed": False,
            "business_conclusion_feedback_added": False,
        },
        "required_action": (
            "Return the complete tool arguments as one valid JSON object. Remove "
            "the extra closing bracket and rewrite every listed model_text so it "
            "contains no spelled numeric or ordinal token. Preserve all existing "
            "R10 evidence, claim, authority, gap, and protection scopes; add no "
            "evidence, numeric fact, authority, or business conclusion."
        ),
        "resubmit_complete_report_once": True,
    }
    feedback_text = json.dumps(
        feedback,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    successor_messages = [
        *deepcopy(initial_submission_messages),
        {
            "role": "assistant",
            "content": str(rejected_message.get("content") or ""),
            "tool_calls": deepcopy(list(calls)),
        },
        {
            "role": "tool",
            "tool_call_id": str(calls[0].get("id") or ""),
            "content": feedback_text,
        },
    ]
    expected_usage = {
        "prompt_tokens": 109769,
        "completion_tokens": 14282,
        "reasoning_tokens": 0,
    }
    expected_execution = {
        "candidate_promotions": 0,
        "external_source_network_calls": 0,
        "fallbacks": 0,
        "maximum_new_provider_calls": 3,
        "new_S1_S2_requests": 0,
        "new_provider_calls_attempted": 2,
        "new_provider_http_200": 2,
        "new_retrieval_rounds": 0,
        "retries": 0,
        "upstream_agent_calls": 0,
        "writer_analysis_calls": 1,
        "writer_submission_attempts": 1,
    }
    checks = {
        "R13_authority_canonical_and_exact_run_bound": (
            authority.get("status")
            == "signed_exact_run_DELL_R10_protected_writer"
            and authority.get("run_id") == DEFAULT_RUN_ID
            and authority.get("authority_digest")
            == canonical_digest(_authority_body(authority))
        ),
        "R13_public_private_terminal_results_canonical": (
            public.get("status") == "terminal_protected_writer_failure_preserved"
            and private.get("status")
            == "terminal_protected_writer_failure_preserved"
            and _canonical_payload_valid(public, "result_digest")
            and _canonical_payload_valid(private, "full_result_digest")
        ),
        "R13_output_and_authority_lineage_exact": (
            authority_output.get("public_result_ref") == R13_PUBLIC_RESULT_REF
            and authority_output.get("private_full_result_ref")
            == R13_PRIVATE_RESULT_REF
            and authority_output.get("capture_root_ref")
            == DEFAULT_CAPTURE_ROOT_REF
            and public.get("authority_ref") == R13_AUTHORITY_REF
            and public.get("authority_sha256") == source["R13_authority"]["sha256"]
            and public.get("authority_digest") == authority.get("authority_digest")
            and private.get("authority_ref") == R13_AUTHORITY_REF
            and private.get("authority_sha256")
            == source["R13_authority"]["sha256"]
            and private.get("authority_digest") == authority.get("authority_digest")
            and public.get("private_full_result_ref") == R13_PRIVATE_RESULT_REF
            and public.get("private_full_result_sha256")
            == source["R13_private_full_result"]["sha256"]
            and public.get("private_full_result_digest")
            == private.get("full_result_digest")
        ),
        "R13_failure_and_usage_exact": (
            (public.get("failure") or {}).get("code")
            == "current_dynamic_writer_live_tool_arguments_json_invalid"
            and public.get("execution") == expected_execution
            and private.get("execution") == expected_execution
            and public.get("usage") == expected_usage
            and private.get("usage") == expected_usage
        ),
        "R13_capture_manifests_equal_and_complete": (
            public_manifest == private_manifest and len(public_manifest) == 2
        ),
        "R13_analysis_capture_bound": (
            len(public_manifest) == 2
            and public_manifest[0].get("attempt_id") == "writer-analysis"
            and capture_matches(
                public_manifest[0],
                "R13_analysis_request",
                "R13_analysis_response",
            )
        ),
        "R13_submission_capture_bound": (
            len(public_manifest) == 2
            and public_manifest[1].get("attempt_id") == "writer-submission-1"
            and capture_matches(
                public_manifest[1],
                "R13_submission_request",
                "R13_submission_response",
            )
        ),
        "R13_capture_objects_complete_HTTP200": (
            analysis_request.get("run_id") == DEFAULT_RUN_ID
            and submission_request.get("run_id") == DEFAULT_RUN_ID
            and analysis_response.get("run_id") == DEFAULT_RUN_ID
            and submission_response.get("run_id") == DEFAULT_RUN_ID
            and analysis_response.get("status_code") == 200
            and submission_response.get("status_code") == 200
            and analysis_response.get("response_body_complete") is True
            and submission_response.get("response_body_complete") is True
            and analysis_response.get("truncated") is False
            and submission_response.get("truncated") is False
        ),
        "R13_visible_analysis_complete_and_reusable": (
            analysis_choice.get("finish_reason") == "stop"
            and len(analysis_content) == 19637
            and not analysis_message.get("tool_calls")
        ),
        "R13_analysis_request_rebuild_byte_equal": (
            (analysis_request.get("request_body") or {}).get("messages")
            == analysis_messages
        ),
        "R13_submission_request_rebuild_byte_equal": (
            (submission_request.get("request_body") or {}).get("messages")
            == initial_submission_messages
            and (submission_request.get("request_body") or {}).get("tools")
            == [tool]
        ),
        "R13_submission_profile_unchanged_non_thinking": (
            profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and profile.get("request_defaults")
            == {
                "max_tokens": 12000,
                "stream": False,
                "thinking": {"type": "disabled"},
            }
            and (profile.get("authority") or {}).get("retry_count") == 0
        ),
        "R13_rejected_tool_identity_exact": (
            submission_choice.get("finish_reason") == "tool_calls"
            and len(calls) == 1
            and (calls[0].get("function") or {}).get("name") == _TOOL_NAME
            and bool(str(calls[0].get("id") or ""))
        ),
        "R13_rejected_arguments_error_exact": (
            json_error.pos == 31343
            and len(raw_arguments) == 31345
            and raw_arguments[json_error.pos] == "]"
        ),
        "single_bracket_removal_is_diagnostic_only": (
            isinstance(diagnostic_payload, dict)
            and feedback["details"]["diagnostic_payload_promotable"] is False
            and diagnostic_rejection_code
            == "current_dynamic_writer_protected_surface_forbidden"
        ),
        "all_five_initial_surface_findings_enumerated": (
            surface_findings == _R13_EXPECTED_SURFACE_FINDINGS
        ),
        "feedback_adds_no_authority_or_business_conclusion": (
            feedback["details"]["authority_expansion_allowed"] is False
            and feedback["details"]["business_conclusion_feedback_added"]
            is False
        ),
        "successor_messages_reuse_analysis_and_rejected_call": (
            successor_messages[:-2] == initial_submission_messages
            and successor_messages[-2].get("tool_calls") == list(calls)
            and successor_messages[-1].get("content") == feedback_text
        ),
        "R10_authority_catalog_and_protection_unchanged": all(
            authority["bound_inputs"].get(name) == source[name]
            for name in (
                "R10_private_full_result",
                "R10_assessment",
                "writer_authority_catalog",
                "writer_protection_contract",
                "submission_profile",
            )
        ),
        "prior_R13_zero_call_positive_seam_preserved": (
            prior_zero.get("schema_version")
            == CURRENT_DYNAMIC_WRITER_ZERO_CALL_SCHEMA_VERSION
            and _canonical_payload_valid(prior_zero, "result_digest")
            and all((prior_zero.get("checks") or {}).values())
            and (prior_zero.get("checks") or {}).get(
                "positive_fake_tool_call_validates"
            )
            is True
            and (prior_zero.get("checks") or {}).get(
                "positive_fake_report_renders_deterministically"
            )
            is True
        ),
        "zero_model_provider_network_calls": True,
    }
    if not all(checks.values()):
        failed = ",".join(
            sorted(name for name, passed in checks.items() if not passed)
        )
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_zero_call_failed:"
            + failed,
            phase="zero_call",
        )
    zero_body = {
        "schema_version": (
            CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_ZERO_CALL_SCHEMA_VERSION
        ),
        "status": (
            "R13_bound_protected_writer_submission_successor_zero_call_proven"
        ),
        "recorded_at": _now(),
        "case_key": "DELL",
        "run_scope_id": CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_RUN_SCOPE,
        "source_bindings": source,
        "R13_lineage_receipt": {
            "authority_digest": authority["authority_digest"],
            "public_result_digest": public["result_digest"],
            "private_full_result_digest": private["full_result_digest"],
            "prior_zero_call_ref": prior_zero_binding["ref"],
            "prior_zero_call_sha256": prior_zero_binding["sha256"],
            "prior_zero_call_result_digest": prior_zero_binding["digest"],
        },
        "diagnostic_receipt": {
            "rejected_arguments_sha256": hashlib.sha256(
                raw_arguments.encode("utf-8")
            ).hexdigest(),
            "json_error_message": json_error.msg,
            "json_error_position": json_error.pos,
            "argument_characters": len(raw_arguments),
            "removed_character": raw_arguments[json_error.pos],
            "single_character_removal_parses": True,
            "diagnostic_payload_promotable": False,
            "validator_rejection_code": diagnostic_rejection_code,
            "protected_surface_findings": surface_findings,
        },
        "submission_feedback": feedback,
        "model_visible_scale": {
            "R13_analysis_prompt_tokens": 46277,
            "R13_analysis_completion_tokens": 4798,
            "R13_submission_prompt_tokens": 63492,
            "R13_submission_completion_tokens": 9484,
            "reused_analysis_characters": len(analysis_content),
            "rejected_arguments_characters": len(raw_arguments),
            "tool_schema_characters": len(
                json.dumps(tool, ensure_ascii=False, sort_keys=True)
            ),
            "feedback_characters": len(feedback_text),
            "successor_message_count": len(successor_messages),
        },
        "execution_budget": (
            expected_current_dynamic_writer_submission_successor_budget()
        ),
        "execution": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "writer_analysis_calls": 0,
            "writer_submission_attempts": 0,
            "upstream_agent_calls": 0,
            "new_S1_S2_requests": 0,
            "new_retrieval_rounds": 0,
            "candidate_promotions": 0,
        },
        "checks": checks,
        "known_boundary": (
            "This zero-call proof binds the immutable R13 analysis, rejected "
            "submission, exact JSON error, and five initial protected-surface "
            "findings. It authorizes no call by itself, adds no evidence or "
            "business conclusion, and permits at most one separately authorized "
            "non-thinking strict submission. Any failure is terminal with no "
            "automated Writer successor; independent post-Writer assessment, S3, "
            "product, publication, and release remain unauthorized."
        ),
    }
    return {**zero_body, "result_digest": canonical_digest(zero_body)}


def build_submission_successor_scope_decision(
    zero: Mapping[str, Any],
) -> dict[str, Any]:
    scale = zero.get("model_visible_scale") or {}
    zero_binding = {
        "ref": SUBMISSION_SUCCESSOR_ZERO_CALL_REF,
        "sha256": _serialized_json_sha256(zero),
        "digest_field": "result_digest",
        "digest": zero["result_digest"],
    }
    body = {
        "schema_version": (
            CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_DECISION_SCHEMA_VERSION
        ),
        "status": CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": (
            "MULTI_AGENT::DELL::R10_PROTECTED_WRITER_SUBMISSION_SUCCESSOR"
        ),
        "run_scope_id": CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_RUN_SCOPE,
        "evidence_mode": (
            "immutable_R13_analysis_rejected_submission_exact_feedback_"
            "zero_new_evidence"
        ),
        "next_authorized_scope": (
            CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_RUN_SCOPE
        ),
        "replacement_is_capture_bound_remaining_submission_not_retry": True,
        "credential_presence_required": True,
        "R13_terminal_public_private_and_capture_chain_required": True,
        "reuse_R13_visible_analysis_required": True,
        "reuse_R13_rejected_submission_as_feedback_required": True,
        "exact_JSON_and_protected_surface_feedback_required": True,
        "same_R10_authority_catalog_and_protection_required": True,
        "protected_report_contract_required": True,
        "deterministic_renderer_required": True,
        "writer_live_authorized_after_full_gate_clean_preflight_and_fresh_authority": True,
        "new_writer_analysis_authorized": False,
        "writer_analysis_continuation_authorized": False,
        "additional_writer_submission_after_successor_authorized": False,
        "new_S1_S2_authorized": False,
        "new_retrieval_authorized": False,
        "external_source_network_authorized": False,
        "upstream_agent_rerun_authorized": False,
        "candidate_promotion_authorized": False,
        "independent_post_writer_assessment_required": True,
        "S3_acceptance_authorized": False,
        "heterogeneous_generalization_authorized": False,
        "product_publication_authorized": False,
        "release_authorized": False,
        "bound_inputs": {
            **deepcopy(dict(zero["source_bindings"])),
            "submission_successor_zero_call_result": zero_binding,
        },
        "implementation_bindings": [
            _binding("src/sec_agent/research/current_dynamic_writer.py"),
            _binding("src/sec_agent/research/multi_agent_report_authority.py"),
            _binding("src/sec_agent/research/source_bound_numeric_authority.py"),
            _binding("src/sec_agent/project_os_preflight.py"),
            _binding("scripts/research/run_s3_current_dynamic_writer_zero_call.py"),
            _binding("scripts/research/run_s3_current_dynamic_writer_live.py"),
        ],
        "execution_budget": (
            expected_current_dynamic_writer_submission_successor_budget()
        ),
        "token_budget_basis": {
            "writer_submission_json_and_surface_feedback": {
                "node_purpose": (
                    "Reuse the completed R13 Writer plan and rejected tool call, "
                    "then submit one complete protected report after exact local "
                    "JSON and spelled-numeric surface feedback."
                ),
                "input_scale": (
                    f"The rejected R13 submission used "
                    f"{scale.get('R13_submission_prompt_tokens')} prompt tokens; "
                    f"the reused plan has {scale.get('reused_analysis_characters')} "
                    f"characters, the rejected arguments have "
                    f"{scale.get('rejected_arguments_characters')} characters, "
                    f"and the strict schema has "
                    f"{scale.get('tool_schema_characters')} characters."
                ),
                "required_outputs": [
                    "exactly_one_submit_protected_report_draft_tool_call",
                    "complete_report_topic_thesis_sections_gaps_and_confidence",
                    "claim_evidence_authority_and_gap_reference_scopes",
                    "zero_spelled_numeric_or_ordinal_model_owned_surfaces",
                    "all_R10_material_and_L3_protections_preserved",
                ],
                "schema_burden": (
                    "The response must be one deeply nested strict tool object "
                    "whose clauses carry typed claim, Evidence, presentation "
                    "authority, and gap references and pass deterministic render."
                ),
                "materiality_quality_risk": (
                    "High: syntax repair alone is insufficient; any authority "
                    "expansion, spelled numeric surface, cohort conversion, exact "
                    "cash attribution, or product inference invalidates the report."
                ),
                "comparable_run_evidence": (
                    "R13 returned a complete tool call at 9484 completion tokens "
                    "under the same 12000-token non-thinking profile; its only "
                    "parse error is exact and five initial surface paths are known."
                ),
                "reasoning_profile": (
                    "deepseek-v4-pro thinking disabled strict tool submission"
                ),
                "maximum_completion_tokens": 12000,
                "maximum_calls": 1,
                "stop_and_truncation_behavior": (
                    "Stop after the first valid contract. Length, transport, JSON, "
                    "schema, reference, or protection failure is terminal; no retry, "
                    "continuation, profile tuning, or automated Writer successor is "
                    "permitted."
                ),
            }
        },
        "authority_statement": (
            "After the full repository gate, clean synced implementation commit, "
            "repository-aware Project OS preflight, and fresh exact-run authority, "
            "permit exactly one non-thinking strict Writer submission that reuses "
            "the immutable R13 visible analysis and rejected tool call with only "
            "the recorded JSON and five protected-surface findings as feedback. "
            "Permit no new analysis, continuation, upstream Agent, retrieval, "
            "source, authority, profile, retry, Candidate, product, publication, "
            "or release action; any failure ends automated Writer succession."
        ),
    }
    return {**body, "decision_digest": canonical_digest(body)}


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
        f"This exact {authority['run_id']} Writer authority ended in a preserved "
        "terminal failure. "
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


def _canonical_payload_valid(value: Mapping[str, Any], digest_field: str) -> bool:
    body = deepcopy(dict(value))
    supplied = str(body.pop(digest_field, ""))
    return bool(supplied) and supplied == canonical_digest(body)


def _validated_submission_successor_context(
    bound: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    expected_names = {
        "R13_authority",
        "R13_public_result",
        "R13_private_full_result",
        "R13_analysis_request",
        "R13_analysis_response",
        "R13_submission_request",
        "R13_submission_response",
        "R10_private_full_result",
        "R10_assessment",
        "writer_authority_catalog",
        "writer_protection_contract",
        "submission_profile",
        "submission_successor_zero_call_result",
    }
    if set(bound) != expected_names:
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_bound_inputs_invalid",
            phase="binding",
        )
    values = {name: _validate_binding(binding) for name, binding in bound.items()}
    r13_authority = values["R13_authority"]
    r13_public = values["R13_public_result"]
    r13_private = values["R13_private_full_result"]
    zero = values["submission_successor_zero_call_result"]
    if not (
        r13_authority.get("status")
        == "signed_exact_run_DELL_R10_protected_writer"
        and r13_authority.get("run_id")
        == "FIN_0_1_3_S3_DELL_R10_PROTECTED_WRITER_LIVE_R13"
        and r13_authority.get("authority_digest")
        == canonical_digest(_authority_body(r13_authority))
        and r13_public.get("status")
        == "terminal_protected_writer_failure_preserved"
        and r13_private.get("status")
        == "terminal_protected_writer_failure_preserved"
        and _canonical_payload_valid(r13_public, "result_digest")
        and _canonical_payload_valid(r13_private, "full_result_digest")
        and r13_public.get("private_full_result_ref")
        == bound["R13_private_full_result"]["ref"]
        and r13_public.get("private_full_result_sha256")
        == bound["R13_private_full_result"]["sha256"]
        and r13_public.get("private_full_result_digest")
        == r13_private.get("full_result_digest")
        and r13_public.get("authority_ref") == bound["R13_authority"]["ref"]
        and r13_public.get("authority_sha256")
        == bound["R13_authority"]["sha256"]
        and r13_public.get("authority_digest")
        == r13_authority.get("authority_digest")
        and r13_private.get("authority_ref") == bound["R13_authority"]["ref"]
        and r13_private.get("authority_sha256")
        == bound["R13_authority"]["sha256"]
        and r13_private.get("authority_digest")
        == r13_authority.get("authority_digest")
        and (r13_public.get("failure") or {}).get("code")
        == "current_dynamic_writer_live_tool_arguments_json_invalid"
        and (r13_public.get("execution") or {}).get("new_provider_calls_attempted")
        == 2
        and (r13_public.get("execution") or {}).get("writer_analysis_calls") == 1
        and (r13_public.get("execution") or {}).get(
            "writer_submission_attempts"
        )
        == 1
        and (r13_public.get("execution") or {}).get("retries") == 0
        and zero.get("schema_version")
        == CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_ZERO_CALL_SCHEMA_VERSION
        and zero.get("status")
        == "R13_bound_protected_writer_submission_successor_zero_call_proven"
        and zero.get("run_scope_id")
        == CURRENT_DYNAMIC_WRITER_SUBMISSION_SUCCESSOR_RUN_SCOPE
        and _canonical_payload_valid(zero, "result_digest")
        and all((zero.get("checks") or {}).values())
        and len(zero.get("checks") or {}) >= 20
        and zero.get("source_bindings")
        == {
            name: binding
            for name, binding in bound.items()
            if name != "submission_successor_zero_call_result"
        }
        and zero.get("execution_budget")
        == expected_current_dynamic_writer_submission_successor_budget()
        and (zero.get("execution") or {}).get("model_calls") == 0
        and (zero.get("execution") or {}).get("provider_calls") == 0
        and (zero.get("execution") or {}).get("network_calls") == 0
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_lineage_invalid",
            phase="binding",
        )
    for name in (
        "R10_private_full_result",
        "R10_assessment",
        "writer_authority_catalog",
        "writer_protection_contract",
        "submission_profile",
    ):
        if r13_authority["bound_inputs"].get(name) != bound[name]:
            raise CurrentDynamicWriterLiveError(
                "current_dynamic_writer_submission_successor_R13_binding_drift:"
                + name,
                phase="binding",
            )
    analysis_request = values["R13_analysis_request"]
    analysis_response = values["R13_analysis_response"]
    submission_request = values["R13_submission_request"]
    submission_response = values["R13_submission_response"]
    public_manifest = r13_public.get("capture_manifest") or []
    private_manifest = r13_private.get("capture_manifest") or []
    analysis_choices = (analysis_response.get("response_body") or {}).get("choices") or []
    submission_choices = (submission_response.get("response_body") or {}).get(
        "choices"
    ) or []
    if not (
        analysis_request.get("attempt_id") == "writer-analysis"
        and analysis_response.get("attempt_id") == "writer-analysis"
        and submission_request.get("attempt_id") == "writer-submission-1"
        and submission_response.get("attempt_id") == "writer-submission-1"
        and analysis_response.get("status_code") == 200
        and analysis_response.get("response_body_complete") is True
        and analysis_response.get("truncated") is False
        and submission_response.get("status_code") == 200
        and submission_response.get("response_body_complete") is True
        and submission_response.get("truncated") is False
        and len(analysis_choices) == 1
        and len(submission_choices) == 1
        and public_manifest == private_manifest
        and len(public_manifest) == 2
        and public_manifest[0].get("request_ref")
        == bound["R13_analysis_request"]["ref"]
        and public_manifest[0].get("request_sha256")
        == bound["R13_analysis_request"]["sha256"]
        and public_manifest[0].get("request_digest")
        == bound["R13_analysis_request"]["digest"]
        and public_manifest[0].get("response_ref")
        == bound["R13_analysis_response"]["ref"]
        and public_manifest[0].get("response_sha256")
        == bound["R13_analysis_response"]["sha256"]
        and public_manifest[0].get("response_digest")
        == bound["R13_analysis_response"]["digest"]
        and public_manifest[1].get("request_ref")
        == bound["R13_submission_request"]["ref"]
        and public_manifest[1].get("request_sha256")
        == bound["R13_submission_request"]["sha256"]
        and public_manifest[1].get("request_digest")
        == bound["R13_submission_request"]["digest"]
        and public_manifest[1].get("response_ref")
        == bound["R13_submission_response"]["ref"]
        and public_manifest[1].get("response_sha256")
        == bound["R13_submission_response"]["sha256"]
        and public_manifest[1].get("response_digest")
        == bound["R13_submission_response"]["digest"]
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_capture_invalid",
            phase="binding",
        )
    analysis_choice = analysis_choices[0]
    analysis_message = analysis_choice.get("message") or {}
    analysis_content = str(analysis_message.get("content") or "")
    submission_choice = submission_choices[0]
    rejected_message = submission_choice.get("message") or {}
    calls = rejected_message.get("tool_calls") or []
    if not (
        analysis_choice.get("finish_reason") == "stop"
        and len(analysis_content) == 19637
        and not analysis_message.get("tool_calls")
        and submission_choice.get("finish_reason") == "tool_calls"
        and len(calls) == 1
        and (calls[0].get("function") or {}).get("name") == _TOOL_NAME
        and isinstance((calls[0].get("function") or {}).get("arguments"), str)
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_frontier_invalid",
            phase="binding",
        )
    raw_arguments = str(calls[0]["function"]["arguments"])
    try:
        json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        json_error = exc
    else:
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_rejected_JSON_now_valid",
            phase="binding",
        )
    feedback = deepcopy(dict(zero.get("submission_feedback") or {}))
    expected_paths = [row["path"] for row in _R13_EXPECTED_SURFACE_FINDINGS]
    details = feedback.get("details") or {}
    if not (
        feedback.get("status") == "rejected"
        and feedback.get("error_code")
        == "current_dynamic_writer_live_tool_arguments_json_invalid_and_"
        "protected_surface_forbidden"
        and details.get("json_error_position") == json_error.pos == 31343
        and details.get("argument_characters") == len(raw_arguments) == 31345
        and details.get("extra_closing_bracket_at_error") is True
        and details.get("diagnostic_removed_character") == "]"
        and details.get("diagnostic_payload_promotable") is False
        and details.get("protected_surface_findings")
        == _R13_EXPECTED_SURFACE_FINDINGS
        and details.get("protected_surface_paths") == expected_paths
        and details.get("authority_expansion_allowed") is False
        and details.get("business_conclusion_feedback_added") is False
        and feedback.get("required_action")
        == (
            "Return the complete tool arguments as one valid JSON object. Remove "
            "the extra closing bracket and rewrite every listed model_text so it "
            "contains no spelled numeric or ordinal token. Preserve all existing "
            "R10 evidence, claim, authority, gap, and protection scopes; add no "
            "evidence, numeric fact, authority, or business conclusion."
        )
        and feedback.get("resubmit_complete_report_once") is True
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_feedback_invalid",
            phase="binding",
        )
    r10_private = values["R10_private_full_result"]
    assessment = values["R10_assessment"]
    catalog = values["writer_authority_catalog"]
    protection = values["writer_protection_contract"]
    lead = r10_private["lead_bundle"]["rounds"][0]["decision"]
    writer_gate = compile_r10_writer_evaluation(
        assessment=assessment,
        lead_decision=lead,
        protection=protection,
    )
    base_messages = compile_r10_protected_writer_messages(
        workpapers=r10_private["final_workpapers"],
        writer_gate=writer_gate,
        authority_catalog=catalog,
        protection=protection,
    )
    if (analysis_request.get("request_body") or {}).get("messages") != _analysis_messages(
        base_messages
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_analysis_message_drift",
            phase="binding",
        )
    initial_submission_messages = _submission_messages(base_messages, analysis_content)
    tool = protected_report_draft_tool(authority_catalog=catalog)
    submission_body = submission_request.get("request_body") or {}
    if not (
        submission_body.get("messages") == initial_submission_messages
        and submission_body.get("tools") == [tool]
        and submission_body.get("tool_choice")
        == {"type": "function", "function": {"name": _TOOL_NAME}}
        and (submission_body.get("thinking") or {}).get("type") == "disabled"
    ):
        raise CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_submission_message_drift",
            phase="binding",
        )
    assistant_message = {
        "role": "assistant",
        "content": str(rejected_message.get("content") or ""),
        "tool_calls": deepcopy(list(calls)),
    }
    messages = [
        *deepcopy(initial_submission_messages),
        assistant_message,
        {
            "role": "tool",
            "tool_call_id": str(calls[0].get("id") or ""),
            "content": json.dumps(
                feedback,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    ]
    return {
        "analysis_content": analysis_content,
        "writer_gate": writer_gate,
        "catalog": catalog,
        "protection": protection,
        "submission_profile": values["submission_profile"],
        "tool": tool,
        "messages": messages,
        "feedback": feedback,
        "R13_public_result_digest": r13_public["result_digest"],
        "R13_private_full_result_digest": r13_private["full_result_digest"],
    }


def _materialize_submission_successor_failure(
    *,
    authority: Mapping[str, Any],
    authority_ref: str,
    decision: Mapping[str, Any],
    exc: Exception,
) -> dict[str, Any]:
    phase, code, provider_steps, exception_capture_ref = _failure_identity(exc)
    output = authority["output_contract"]
    captures = _capture_manifest_from_root(_resolve(output["capture_root_ref"]))
    usage = {
        "prompt_tokens": sum(int(row["prompt_tokens"]) for row in captures),
        "completion_tokens": sum(int(row["completion_tokens"]) for row in captures),
        "reasoning_tokens": sum(int(row["reasoning_tokens"]) for row in captures),
    }
    recorded_at = _now()
    failure = {
        "phase": phase,
        "code": code,
        "exception_capture_ref": exception_capture_ref,
        "provider_failure": isinstance(exc, ModelGatewayError),
        "failure_preserved_without_retry": True,
    }
    execution = {
        "new_provider_calls_attempted": len(captures),
        "new_provider_http_200": sum(row["status_code"] == 200 for row in captures),
        "maximum_new_provider_calls": 1,
        "writer_analysis_calls": 0,
        "reused_R13_writer_analysis": True,
        "writer_submission_attempts": len(captures),
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
        "The single R13-bound JSON and protected-surface feedback submission "
        "successor ended in a preserved terminal failure. No automated Writer "
        "successor, retry, profile tuning, upstream Agent, retrieval, publication "
        "or release action is authorized after this result."
    )
    private_body = {
        "schema_version": PRIVATE_RESULT_SCHEMA_VERSION,
        "status": "terminal_protected_writer_submission_successor_failure_preserved",
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
    private = {**private_body, "full_result_digest": canonical_digest(private_body)}
    private_ref = str(output["private_full_result_ref"])
    _write_new(private_ref, private)
    public_body = {
        "schema_version": PUBLIC_RESULT_SCHEMA_VERSION,
        "status": "terminal_protected_writer_submission_successor_failure_preserved",
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


def _run_submission_successor_once(
    *,
    authority_ref: str,
    authority: Mapping[str, Any],
    decision: Mapping[str, Any],
    submission_executor: Callable[..., ChatCompletionToolStepResult],
) -> dict[str, Any]:
    context = _validated_submission_successor_context(authority["bound_inputs"])
    profile = load_chat_completion_profile(context["submission_profile"])
    run_id = str(authority["run_id"])
    step = submission_executor(
        profile=profile,
        messages=context["messages"],
        tools=[context["tool"]],
        tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
        capture_root=_resolve(authority["output_contract"]["capture_root_ref"]),
        run_id=run_id,
        attempt_id="writer-submission-json-and-surface-feedback-successor",
    )
    call_id, payload = _tool_payload(step)
    trusted = validate_r10_protected_writer_draft(
        payload,
        authority_catalog=context["catalog"],
        protection=context["protection"],
    )
    rendered = render_protected_report(
        trusted, authority_catalog=context["catalog"]
    )
    provider_steps = [step.as_dict()]
    captures = [_capture_receipt(provider_steps[0])]
    usage = _aggregate_step_usage(provider_steps)
    execution = {
        "new_provider_calls_attempted": 1,
        "new_provider_http_200": 1,
        "maximum_new_provider_calls": 1,
        "writer_analysis_calls": 0,
        "reused_R13_writer_analysis": True,
        "writer_submission_attempts": 1,
        "retries": 0,
        "fallbacks": 0,
        "upstream_agent_calls": 0,
        "new_S1_S2_requests": 0,
        "new_retrieval_rounds": 0,
        "external_source_network_calls": 0,
        "candidate_promotions": 0,
    }
    acceptance = {
        "protected_contract_pass": True,
        "writer_protection_contract_pass": True,
        "independent_post_writer_L1_L2_pass": False,
        "eight_dimension_quality_pass": False,
        "S3_pass": False,
        "product_acceptance": False,
        "publication": False,
        "release_ready": False,
    }
    known_boundary = (
        "A rendered R13-bound protected report candidate exists after one JSON and "
        "protected-surface feedback submission. Independent L1/L2, eight-dimension "
        "quality, S3, product, publication and release acceptance remain false."
    )
    recorded_at = _now()
    lineage = {
        "R13_public_result_digest": context["R13_public_result_digest"],
        "R13_private_full_result_digest": context["R13_private_full_result_digest"],
        "R13_analysis_reused": True,
        "R13_rejected_submission_reused_as_feedback": True,
        "new_analysis_or_continuation": False,
    }
    private_body = {
        "schema_version": PRIVATE_RESULT_SCHEMA_VERSION,
        "status": "completed_protected_writer_report_assessment_pending",
        "recorded_at": recorded_at,
        "case_key": "DELL",
        "run_id": run_id,
        "implementation_commit": authority["implementation_commit"],
        "authority_ref": authority_ref,
        "authority_sha256": _sha(authority_ref),
        "authority_digest": authority["authority_digest"],
        "decision_digest": decision["decision_digest"],
        "writer_gate": context["writer_gate"],
        "writer_analysis": context["analysis_content"],
        "submission_successor_lineage": lineage,
        "submission_feedback": context["feedback"],
        "accepted_tool_call_id": call_id,
        "protected_draft": trusted,
        "rendered_report": rendered,
        "provider_steps": provider_steps,
        "capture_manifest": captures,
        "usage": usage,
        "execution": execution,
        "acceptance": acceptance,
        "known_boundary": known_boundary,
    }
    private = {**private_body, "full_result_digest": canonical_digest(private_body)}
    private_ref = str(authority["output_contract"]["private_full_result_ref"])
    _write_new(private_ref, private)
    public_body = {
        "schema_version": PUBLIC_RESULT_SCHEMA_VERSION,
        "status": "completed_protected_writer_report_assessment_pending",
        "recorded_at": recorded_at,
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
        "submission_successor_lineage": lineage,
        "capture_manifest": captures,
        "usage": usage,
        "execution": execution,
        "acceptance": acceptance,
        "known_boundary": known_boundary,
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(str(authority["output_contract"]["public_result_ref"]), public)
    return public


def run_submission_successor(
    *,
    authority_ref: str = SUBMISSION_SUCCESSOR_AUTHORITY_REF,
    submission_executor: Callable[..., ChatCompletionToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> dict[str, Any]:
    authority = _load(authority_ref)
    decision = _validate_submission_successor_authority(
        authority, authority_ref=authority_ref
    )
    try:
        return _run_submission_successor_once(
            authority_ref=authority_ref,
            authority=authority,
            decision=decision,
            submission_executor=submission_executor,
        )
    except Exception as exc:
        output = authority["output_contract"]
        if any(
            _resolve(str(output[name])).exists()
            for name in ("public_result_ref", "private_full_result_ref")
        ):
            raise
        terminal = _materialize_submission_successor_failure(
            authority=authority,
            authority_ref=authority_ref,
            decision=decision,
            exc=exc,
        )
        preserved = CurrentDynamicWriterLiveError(
            "current_dynamic_writer_submission_successor_terminal_failure_preserved:"
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
    build_submission = sub.add_parser("build-submission-successor-zero")
    build_submission.add_argument("--write", action="store_true")
    issue_submission = sub.add_parser("issue-submission-successor-authority")
    issue_submission.add_argument(
        "--decision-ref", default=SUBMISSION_SUCCESSOR_DECISION_REF
    )
    issue_submission.add_argument(
        "--preflight-ref", default=SUBMISSION_SUCCESSOR_PREFLIGHT_REF
    )
    issue_submission.add_argument(
        "--authority-ref", default=SUBMISSION_SUCCESSOR_AUTHORITY_REF
    )
    submission_live = sub.add_parser("submission-successor-live")
    submission_live.add_argument(
        "--authority-ref", default=SUBMISSION_SUCCESSOR_AUTHORITY_REF
    )
    args = parser.parse_args()
    if args.command == "issue-authority":
        result = issue_authority(
            decision_ref=args.decision_ref,
            preflight_ref=args.preflight_ref,
            authority_ref=args.authority_ref,
        )
    elif args.command == "live":
        result = run_live(authority_ref=args.authority_ref)
    elif args.command == "build-submission-successor-zero":
        zero = build_submission_successor_zero_call()
        decision = build_submission_successor_scope_decision(zero)
        if args.write:
            if _resolve(SUBMISSION_SUCCESSOR_ZERO_CALL_REF).exists() or _resolve(
                SUBMISSION_SUCCESSOR_DECISION_REF
            ).exists():
                raise CurrentDynamicWriterLiveError(
                    "current_dynamic_writer_submission_successor_fresh_zero_and_"
                    "decision_required",
                    phase="materialization",
                )
            _write_new(SUBMISSION_SUCCESSOR_ZERO_CALL_REF, zero)
            _write_new(SUBMISSION_SUCCESSOR_DECISION_REF, decision)
        result = {
            "status": "written" if args.write else "zero_call_preview_pass",
            "zero_call_result_ref": SUBMISSION_SUCCESSOR_ZERO_CALL_REF,
            "zero_call_result_digest": zero["result_digest"],
            "zero_call_check_count": len(zero["checks"]),
            "scope_decision_ref": SUBMISSION_SUCCESSOR_DECISION_REF,
            "decision_digest": decision["decision_digest"],
            "execution": zero["execution"],
        }
    elif args.command == "issue-submission-successor-authority":
        result = issue_submission_successor_authority(
            decision_ref=args.decision_ref,
            preflight_ref=args.preflight_ref,
            authority_ref=args.authority_ref,
        )
    else:
        result = run_submission_successor(authority_ref=args.authority_ref)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
