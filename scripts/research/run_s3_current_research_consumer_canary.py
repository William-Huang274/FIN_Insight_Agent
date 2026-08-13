from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "src"):
    value = str(candidate)
    if value not in sys.path:
        sys.path.insert(0, value)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from apps.workbench.backend.application.research_evidence_pack_service import (  # noqa: E402
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from apps.workbench.backend.application.research_retrieval_service import (  # noqa: E402
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)
from sec_agent.providers.chat_completions import (  # noqa: E402
    ChatCompletionResult,
    ChatCompletionToolStepResult,
    ModelGatewayError,
    execute_chat_completion_exact_once,
    execute_chat_completion_tool_step_exact_once,
    load_chat_completion_profile,
)
from sec_agent.research.bounded_finance_loop import (  # noqa: E402
    validate_deepseek_ga_json_profile,
    validate_deepseek_ga_profile,
)
from sec_agent.research.current_consumer import (  # noqa: E402
    CurrentResearchConsumerError,
    compile_current_research_deliverable,
    compile_current_research_input,
    compile_current_research_messages,
    parse_current_research_output,
)
from sec_agent.research.reviewed_evidence_pack import (  # noqa: E402
    canonical_digest,
)
from sec_agent.research.paired_submission import (  # noqa: E402
    PairedResearchSubmission,
    compile_paired_research_submission,
    run_paired_research_submission,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths  # noqa: E402
from sec_agent.runtime_resource_registry import (  # noqa: E402
    read_registered_runtime_json,
)


AUTHORITY_SCHEMA = "fin_ia_current_research_consumer_canary_authority_v1_1"
RESULT_SCHEMA = "fin_ia_current_research_consumer_canary_result_v1_1"
FULL_SCHEMA = "fin_ia_current_research_consumer_canary_full_v1_1"
PAIRED_AUTHORITY_SCHEMA = (
    "fin_ia_s3_deepseek_ga_single_cell_paired_authority_v1_0"
)
PAIRED_RESULT_SCHEMA = "fin_ia_s3_deepseek_ga_single_cell_paired_result_v1_0"
PAIRED_FULL_SCHEMA = "fin_ia_s3_deepseek_ga_single_cell_paired_full_v1_0"


class CurrentResearchConsumerCanaryError(RuntimeError):
    """The natural synthesis canary was not exactly authorized."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _resolve(ref: str) -> Path:
    relative = PurePosixPath(str(ref or ""))
    if relative.is_absolute() or "\\" in str(ref) or ".." in relative.parts:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_path_invalid"
        )
    path = ROOT.joinpath(*relative.parts).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_path_escape"
        ) from exc
    return path


def _relative(path: str | Path) -> str:
    return Path(path).resolve().relative_to(ROOT).as_posix()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CurrentResearchConsumerCanaryError(
            f"research_consumer_canary_json_object_required:{path.name}"
        )
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError as exc:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_exact_once_output_exists"
        ) from exc


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_git_boundary_unavailable"
        )
    return completed.stdout.strip()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def validate_authority(
    payload: Mapping[str, Any],
    *,
    authority_path: Path,
) -> dict[str, Path]:
    if not (
        payload.get("schema_version") == AUTHORITY_SCHEMA
        and payload.get("status") == "signed_exact_once_research_synthesis_authority"
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_authority_status_invalid"
        )
    case_key = str(payload.get("case_key") or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9.-]{1,16}", case_key):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_case_key_invalid"
        )
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_implementation_commit_invalid"
        )
    if _git("rev-parse", "HEAD").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_implementation_head_drift"
        )
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_implementation_upstream_drift"
        )
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    allowed = f"?? {_relative(authority_path)}"
    if [line for line in status.splitlines() if line] != [allowed]:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_worktree_not_clean"
        )
    budget = payload.get("budget")
    if not (
        isinstance(budget, Mapping)
        and dict(budget)
        == {
            "model_calls": 1,
            "transport_attempts": 1,
            "retries": 0,
            "fallbacks": 0,
            "external_retrieval_calls": 0,
            "planner_calls": 0,
            "current_product_pointer_mutations": 0,
        }
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_budget_invalid"
        )
    bound = payload.get("bound_inputs")
    output = payload.get("output_contract")
    if not isinstance(bound, Mapping) or not isinstance(output, Mapping):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_authority_shape_invalid"
        )
    pairs = (
        ("consumer_policy_ref", "consumer_policy_sha256"),
        ("objective_ref", "objective_sha256"),
        ("planner_atoms_ref", "planner_atoms_sha256"),
        ("current_evidence_pack_result_ref", "current_evidence_pack_result_sha256"),
        ("runtime_registry_ref", "runtime_registry_sha256"),
        ("clean_zero_call_result_ref", "clean_zero_call_result_sha256"),
        ("provider_profile_ref", "provider_profile_sha256"),
        ("runner_ref", "runner_sha256"),
    )
    paths: dict[str, Path] = {}
    for ref_key, digest_key in pairs:
        path = _resolve(str(bound.get(ref_key) or ""))
        if not path.is_file() or _sha(path) != str(bound.get(digest_key) or ""):
            raise CurrentResearchConsumerCanaryError(
                f"research_consumer_canary_bound_input_drift:{ref_key}"
            )
        paths[ref_key] = path
    expected_message_digest = str(
        bound.get("model_visible_messages_sha256") or ""
    )
    if not re.fullmatch(r"[0-9a-f]{64}", expected_message_digest):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_message_digest_invalid"
        )
    required_output = {
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
        "result_id",
        "run_id",
        "attempt_id",
        "product_publication",
    }
    if not (
        set(output) == required_output
        and output.get("product_publication") == "forbidden"
        and str(output.get("result_id") or "")
        and str(output.get("run_id") or "")
        and str(output.get("attempt_id") or "")
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_output_contract_invalid"
        )
    capture_dir = (
        _resolve(str(output["capture_root_ref"]))
        / str(output["run_id"])
        / str(output["attempt_id"])
    )
    if (
        capture_dir.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_exact_once_identity_consumed"
        )
    return paths


def _services() -> tuple[ResearchEvidencePackService, ResearchRetrievalService]:
    runtime_paths = resolve_runtime_paths(ROOT)
    evidence_config = read_registered_runtime_json(
        ROOT, "application.config.current_research_evidence_pack_projection"
    )
    evidence = ResearchEvidencePackService(
        config=evidence_config,
        result=read_registered_runtime_json(
            ROOT, str(evidence_config["source_result_resource_id"])
        ),
        private_object_root=(
            runtime_paths.reviewed_evidence_root
            / str(evidence_config["private_object_root_relative"])
        ),
        private_root_base=runtime_paths.reviewed_evidence_root,
    )
    retrieval = ResearchRetrievalService(
        snapshot=read_registered_runtime_json(
            ROOT, "application.result.current_research_retrieval_snapshot"
        ),
        ranking_comparison=read_registered_runtime_json(
            ROOT, "application.result.current_s1c_ranking_comparison_projection"
        ),
        kernel=read_registered_runtime_json(
            ROOT, "application.config.current_financial_research_kernel"
        ),
        route_policy=read_registered_runtime_json(
            ROOT, "application.config.current_query_object_fact_route_policy"
        ),
        planning_policy=read_registered_runtime_json(
            ROOT, "application.config.current_research_planning_policy"
        ),
        hybrid_candidate_runtime=None,
        company_financial_fact_mart_path=(
            runtime_paths.company_financial_fact_mart_path
        ),
    )
    return evidence, retrieval


def _compile_runtime_input(
    paths: Mapping[str, Path],
    *,
    case_key: str,
    required_cell_ids: Sequence[str] | None = None,
    submission_transport: str = "json",
) -> tuple[dict[str, Any], dict[str, Any], tuple[dict[str, str], ...]]:
    evidence_service, retrieval_service = _services()
    read = frozenset({"current_product:read"})
    objective = _json(paths["objective_ref"])
    if str(objective.get("case_key") or "").strip().upper() != case_key:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_objective_case_drift"
        )
    evidence_pack = evidence_service.get_case(
        case_key, ResearchEvidencePackPrincipal("current", read)
    )
    controlled = retrieval_service.execute_controlled_plan(
        case_key,
        objective,
        _json(paths["planner_atoms_ref"]),
        ResearchRetrievalPrincipal("current", read),
    )
    research_input = compile_current_research_input(
        policy=_json(paths["consumer_policy_ref"]),
        evidence_pack=evidence_pack,
        controlled_plan=controlled,
    )
    return (
        evidence_pack,
        research_input,
        compile_current_research_messages(
            research_input,
            required_cell_ids=required_cell_ids,
            submission_transport=submission_transport,
        ),
    )


def _terminal_summary(
    *,
    authority: Mapping[str, Any],
    authority_path: Path,
    research_input: Mapping[str, Any],
    provider_result: ChatCompletionResult | None,
    status: str,
    failure_phase: str,
    failure_code: str,
    model_call_attempted: bool,
    transport_attempted: bool,
    provider_identity: Mapping[str, Any] | None = None,
    request_capture_ref: str = "",
    response_capture_ref: str = "",
    full_result_ref: str = "",
    full_result_sha256: str = "",
    deliverable_digest: str = "",
) -> dict[str, Any]:
    output = authority["output_contract"]
    provider = provider_result.as_dict() if provider_result is not None else {}
    identity = provider_identity or {}
    summary_body = {
        "schema_version": RESULT_SCHEMA,
        "status": status,
        "recorded_at": _now(),
        "result_id": str(output["result_id"]),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": str(authority["implementation_commit"]),
        "bindings": {
            "case_key": research_input["case_identity"]["case_key"],
            "research_as_of": research_input["case_identity"]["research_as_of"],
            "research_input_digest": research_input["research_input_digest"],
            "evidence_pack_artifact_digest": research_input[
                "evidence_pack_binding"
            ]["artifact_digest"],
            "evidence_pack_payload_digest": research_input[
                "evidence_pack_binding"
            ]["pack_payload_digest"],
            "deliverable_digest": deliverable_digest,
        },
        "provider": {
            "provider_id": provider.get(
                "provider_id", identity.get("provider_id", "")
            ),
            "model": provider.get("model", identity.get("model", "")),
            "finish_reason": provider.get("finish_reason", ""),
            "usage": provider.get("usage", {}),
            "request_capture_ref": (
                _relative(provider["request_capture_ref"])
                if provider.get("request_capture_ref")
                else request_capture_ref
            ),
            "response_capture_ref": (
                _relative(provider["response_capture_ref"])
                if provider.get("response_capture_ref")
                else response_capture_ref
            ),
            "request_digest": provider.get("request_digest", ""),
            "response_digest": provider.get("response_digest", ""),
            "private_reasoning_fields_redacted": provider.get(
                "private_reasoning_fields_redacted", 0
            ),
        },
        "terminal": {
            "failure_phase": failure_phase,
            "failure_code": failure_code,
            "model_calls": int(model_call_attempted),
            "transport_attempts": int(transport_attempted),
            "retries": 0,
            "fallbacks": 0,
            "external_retrieval_calls": 0,
            "planner_calls": 0,
            "product_publication": False,
        },
        "full_result_ref": full_result_ref,
        "full_result_sha256": full_result_sha256,
        "acceptance": {
            "deterministic_contract_pass": status == "completed_contract_valid",
            "natural_research_quality_proven": False,
            "qualified_human_acceptance": False,
            "s3_product_acceptance": False,
            "workbench_publication": False,
            "release_ready": False,
        },
        "known_boundary": str(authority["known_boundary"]),
    }
    return {**summary_body, "result_digest": canonical_digest(summary_body)}


def run(
    authority_path: Path,
    *,
    executor: Callable[..., ChatCompletionResult] = execute_chat_completion_exact_once,
) -> dict[str, Any]:
    authority = _json(authority_path)
    paths = validate_authority(authority, authority_path=authority_path)
    case_key = str(authority["case_key"]).strip().upper()
    _, research_input, messages = _compile_runtime_input(
        paths,
        case_key=case_key,
    )
    clean_zero = _json(paths["clean_zero_call_result_ref"])
    if not (
        clean_zero.get("status")
        == "engineering_pass_zero_call_current_consumer_contract_successor"
        and clean_zero.get("bindings", {}).get("research_input_digest")
        == research_input["research_input_digest"]
        and clean_zero.get("bindings", {}).get("evidence_pack_artifact_digest")
        == research_input["evidence_pack_binding"]["artifact_digest"]
        and clean_zero.get("bindings", {}).get("evidence_pack_payload_digest")
        == research_input["evidence_pack_binding"]["pack_payload_digest"]
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_clean_zero_binding_drift"
        )
    message_digest = canonical_digest(list(messages))
    if message_digest != authority["bound_inputs"][
        "model_visible_messages_sha256"
    ]:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_model_message_drift"
        )
    output = authority["output_contract"]
    provider_result: ChatCompletionResult | None = None
    provider_identity: dict[str, str] = {}
    model_call_attempted = False
    transport_attempted = False
    request_capture_ref = ""
    response_capture_ref = ""
    try:
        profile = load_chat_completion_profile(
            _json(paths["provider_profile_ref"])
        )
        provider_identity = {
            "provider_id": profile.provider_id,
            "model": profile.model,
        }
        model_call_attempted = True
        transport_attempted = True
        provider_result = executor(
            profile=profile,
            messages=messages,
            capture_root=_resolve(str(output["capture_root_ref"])),
            run_id=str(output["run_id"]),
            attempt_id=str(output["attempt_id"]),
        )
        if provider_result.finish_reason != "stop":
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_canary_finish_reason_invalid"
            )
        judgment = parse_current_research_output(provider_result.content)
        deliverable = compile_current_research_deliverable(
            research_input=research_input,
            judgment_output=judgment,
        )
        full_body = {
            "schema_version": FULL_SCHEMA,
            "status": "completed_contract_valid",
            "authority_ref": _relative(authority_path),
            "authority_sha256": _sha(authority_path),
            "research_input": research_input,
            "model_visible_messages_sha256": message_digest,
            "provider_result": provider_result.as_dict(),
            "judgment_output": judgment,
            "structured_deliverable": deliverable,
            "product_publication": False,
        }
        full_digest = canonical_digest(full_body)
        private_root = _resolve(str(output["private_output_root_ref"]))
        full_path = private_root / f"full_result_{full_digest}.json"
        _write_new(full_path, {**full_body, "result_digest": full_digest})
        summary = _terminal_summary(
            authority=authority,
            authority_path=authority_path,
            research_input=research_input,
            provider_result=provider_result,
            status="completed_contract_valid",
            failure_phase="",
            failure_code="",
            model_call_attempted=model_call_attempted,
            transport_attempted=transport_attempted,
            provider_identity=provider_identity,
            full_result_ref=_relative(full_path),
            full_result_sha256=_sha(full_path),
            deliverable_digest=str(deliverable["deliverable_digest"]),
        )
    except (ModelGatewayError, CurrentResearchConsumerError, CurrentResearchConsumerCanaryError) as exc:
        if isinstance(exc, ModelGatewayError):
            phase = "provider_transport_or_response"
            code = exc.code
            response_capture_ref = (
                _relative(exc.capture_ref) if exc.capture_ref else ""
            )
            if exc.capture_ref:
                request_path = Path(exc.capture_ref).with_name(
                    "model_visible_request.json"
                )
                if request_path.is_file():
                    request_capture_ref = _relative(request_path)
        elif isinstance(exc, CurrentResearchConsumerError):
            phase = "research_output_parse_or_contract"
            code = exc.code
        else:
            phase = "post_provider_terminal_validation"
            code = exc.code
        summary = _terminal_summary(
            authority=authority,
            authority_path=authority_path,
            research_input=research_input,
            provider_result=provider_result,
            status="terminal_failed_no_retry",
            failure_phase=phase,
            failure_code=code,
            model_call_attempted=model_call_attempted,
            transport_attempted=transport_attempted,
            provider_identity=provider_identity,
            request_capture_ref=request_capture_ref,
            response_capture_ref=response_capture_ref,
        )
    _write_new(_resolve(str(output["public_result_ref"])), summary)
    return summary


def validate_paired_authority(
    payload: Mapping[str, Any],
    *,
    authority_path: Path,
) -> dict[str, Path]:
    if not (
        payload.get("schema_version") == PAIRED_AUTHORITY_SCHEMA
        and payload.get("status")
        == "signed_exact_once_deepseek_ga_single_cell_paired_canary"
        and payload.get("case_key") == "DELL"
        and payload.get("cell_id") == "CELL::value_capture"
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_authority_invalid"
        )
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_commit_invalid"
        )
    if _git("rev-parse", "HEAD").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_head_drift"
        )
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_upstream_drift"
        )
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    allowed = f"?? {_relative(authority_path)}"
    if [line for line in status.splitlines() if line] != [allowed]:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_worktree_not_clean"
        )
    budget = payload.get("execution_budget")
    if not (
        isinstance(budget, Mapping)
        and dict(budget)
        == {
            "maximum_model_calls": 2,
            "maximum_transport_attempts": 2,
            "maximum_calls_per_lane": 1,
            "retries": 0,
            "fallbacks": 0,
            "planner_calls": 0,
            "external_retrieval_calls": 0,
            "tool_executions": 0,
            "current_product_pointer_mutations": 0,
        }
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_budget_invalid"
        )
    bound = payload.get("bound_inputs")
    output = payload.get("output_contract")
    if not isinstance(bound, Mapping) or not isinstance(output, Mapping):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_shape_invalid"
        )
    required_ref_keys = {
        "consumer_policy_ref",
        "objective_ref",
        "planner_atoms_ref",
        "current_evidence_pack_result_ref",
        "runtime_registry_ref",
        "clean_zero_call_result_ref",
        "json_profile_ref",
        "strict_profile_ref",
        "runner_ref",
        "paired_submission_ref",
    }
    ref_keys = [key for key in bound if key.endswith("_ref")]
    digest_keys = {
        "research_input_digest",
        "json_messages_digest",
        "strict_messages_digest",
        "business_payload_digest",
        "strict_tool_schema_digest",
    }
    expected = {
        value
        for key in ref_keys
        for value in (key, key[:-4] + "_sha256")
    } | digest_keys
    if set(ref_keys) != required_ref_keys or set(bound) != expected:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_bindings_invalid"
        )
    paths: dict[str, Path] = {}
    for key in ref_keys:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(
            bound.get(key[:-4] + "_sha256") or ""
        ):
            raise CurrentResearchConsumerCanaryError(
                f"research_consumer_paired_bound_input_drift:{key}"
            )
        paths[key] = path
    required_output = {
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
        "run_id",
        "json_attempt_id",
        "strict_attempt_id",
        "product_publication",
    }
    if not (
        set(output) == required_output
        and output.get("product_publication") == "forbidden"
        and all(
            str(output.get(key) or "")
            for key in required_output - {"product_publication"}
        )
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_output_invalid"
        )
    capture_run = (
        _resolve(str(output["capture_root_ref"])) / str(output["run_id"])
    )
    if (
        capture_run.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_identity_consumed"
        )
    return paths


def _compile_paired_inputs(
    paths: Mapping[str, Path],
    *,
    case_key: str,
    cell_id: str,
) -> tuple[
    dict[str, Any],
    tuple[dict[str, str], ...],
    tuple[dict[str, str], ...],
    dict[str, Any],
    str,
]:
    _, research_input, _ = _compile_runtime_input(
        paths,
        case_key=case_key,
        required_cell_ids=[cell_id],
        submission_transport="json",
    )
    kernel_payload = read_registered_runtime_json(
        ROOT, "application.config.current_financial_research_kernel"
    )
    kernel = load_financial_research_kernel(kernel_payload)
    route = load_query_object_fact_route_policy(
        read_registered_runtime_json(
            ROOT, "application.config.current_query_object_fact_route_policy"
        ),
        kernel,
    )
    paired = compile_paired_research_submission(
        research_input=research_input,
        kernel=kernel,
        route_policy=route,
        cell_id=cell_id,
    )
    return (
        research_input,
        paired.json_messages,
        paired.strict_messages,
        dict(paired.strict_tool),
        paired.business_payload_digest,
    )


def _paired_lane_public(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value[key]
        for key in (
            "lane",
            "status",
            "failure_phase",
            "failure_code",
            "provider",
            "deliverable_digest",
            "failure_request_capture_ref",
            "failure_response_capture_ref",
        )
    }


def run_paired(
    authority_path: Path,
    *,
    json_executor: Callable[..., ChatCompletionResult] = (
        execute_chat_completion_exact_once
    ),
    strict_executor: Callable[..., ChatCompletionToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> dict[str, Any]:
    authority = _json(authority_path)
    paths = validate_paired_authority(
        authority, authority_path=authority_path
    )
    cell_id = str(authority["cell_id"])
    (
        research_input,
        json_messages,
        strict_messages,
        strict_tool,
        business_payload_digest,
    ) = _compile_paired_inputs(
        paths,
        case_key=str(authority["case_key"]),
        cell_id=cell_id,
    )
    actual = {
        "research_input_digest": research_input["research_input_digest"],
        "json_messages_digest": canonical_digest(list(json_messages)),
        "strict_messages_digest": canonical_digest(list(strict_messages)),
        "business_payload_digest": business_payload_digest,
        "strict_tool_schema_digest": canonical_digest(strict_tool),
    }
    bound = authority["bound_inputs"]
    if any(str(bound[key]) != str(value) for key, value in actual.items()):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_runtime_binding_drift"
        )
    clean = _json(paths["clean_zero_call_result_ref"])
    if not (
        clean.get("status")
        == "zero_call_engineering_and_fresh_process_proof_pass"
        and clean.get("normalized_proof", {}).get("research_input_digest")
        == research_input["research_input_digest"]
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_clean_proof_drift"
        )
    json_profile = load_chat_completion_profile(
        _json(paths["json_profile_ref"])
    )
    strict_profile = load_chat_completion_profile(
        _json(paths["strict_profile_ref"])
    )
    validate_deepseek_ga_json_profile(json_profile)
    validate_deepseek_ga_profile(strict_profile, strict_tools=True)
    output = authority["output_contract"]
    private_root = _resolve(str(output["private_output_root_ref"]))
    paired_submission = PairedResearchSubmission(
        json_messages=json_messages,
        strict_messages=strict_messages,
        strict_tool=strict_tool,
        business_payload_digest=business_payload_digest,
    )
    full_core = run_paired_research_submission(
        research_input=research_input,
        submission=paired_submission,
        json_profile=json_profile,
        strict_profile=strict_profile,
        capture_root=_resolve(str(output["capture_root_ref"])),
        run_id=str(output["run_id"]),
        json_attempt_id=str(output["json_attempt_id"]),
        strict_attempt_id=str(output["strict_attempt_id"]),
        cell_id=cell_id,
        capture_ref_formatter=_relative,
        lane_recorder=lambda lane, value: _write_new(
            private_root / f"{lane}.json", value
        ),
        json_executor=json_executor,
        strict_executor=strict_executor,
    )
    full_body = {
        "schema_version": PAIRED_FULL_SCHEMA,
        "recorded_at": _now(),
        "research_input_digest": research_input["research_input_digest"],
        "business_payload_digest": business_payload_digest,
        **full_core,
    }
    full = {
        **full_body,
        "full_result_digest": canonical_digest(full_body),
    }
    _write_new(private_root / "full_result.json", full)
    json_lane = full["json_lane"]
    strict_lane = full["strict_lane"]
    both = (
        json_lane["status"] == "contract_valid"
        and strict_lane["status"] == "contract_valid"
    )
    body = {
        "schema_version": PAIRED_RESULT_SCHEMA,
        "status": (
            "paired_contract_valid_content_assessment_pending"
            if both
            else "paired_terminal_mixed_or_failed_no_retry"
        ),
        "recorded_at": _now(),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": authority["case_key"],
        "cell_id": cell_id,
        "research_input_digest": research_input["research_input_digest"],
        "business_payload_digest": business_payload_digest,
        "same_business_payload": True,
        "json_lane": _paired_lane_public(json_lane),
        "strict_lane": _paired_lane_public(strict_lane),
        "execution": {
            "model_calls": 1 + int(not full["strict_skipped"]),
            "transport_attempts": 1 + int(not full["strict_skipped"]),
            "retries": 0,
            "fallbacks": 0,
            "planner_calls": 0,
            "external_retrieval_calls": 0,
            "tool_executions": 0,
            "tool_choice_sent": False,
            "product_publication": False,
        },
        "full_result_ref": _relative(private_root / "full_result.json"),
        "full_result_sha256": _sha(private_root / "full_result.json"),
        "acceptance": {
            "json_transport_and_contract_pass": (
                json_lane["status"] == "contract_valid"
            ),
            "strict_beta_transport_and_contract_pass": (
                strict_lane["status"] == "contract_valid"
            ),
            "paired_content_assessment_pending": both,
            "five_cell_live_authorized": False,
            "s3_product_acceptance": False,
            "qualified_human_acceptance": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    summary = {**body, "result_digest": canonical_digest(body)}
    _write_new(_resolve(str(output["public_result_ref"])), summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    args = parser.parse_args(argv)
    authority_path = _resolve(args.authority)
    authority = _json(authority_path)
    result = (
        run_paired(authority_path)
        if authority.get("schema_version") == PAIRED_AUTHORITY_SCHEMA
        else run(authority_path)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return (
        0
        if result["status"]
        in {
            "completed_contract_valid",
            "paired_contract_valid_content_assessment_pending",
        }
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
